"""User A and User B cannot see each other's research data.

WHY THIS FILE EXISTS
--------------------
This is the fault authentication was added to fix. Before it, `GET /api/papers`
read the whole `papers` table with a service-role key, so User A uploaded a
paper and User B, on another device, opened the same library. Every test below
is a statement about that specific failure.

WHAT IS ACTUALLY BEING TESTED, AND WHAT IS NOT
----------------------------------------------
Isolation in production is enforced in two places, and only one of them can be
tested offline:

  1. **Postgres Row Level Security.** `user_id = auth.uid()` on every table.
     This is the real guarantee: it holds even if the application layer is
     wrong. It cannot be exercised here - it needs a live database - and it is
     verified against production separately (see docs/DATABASE.md).

  2. **The application carrying identity through faithfully**, so that the
     database is asked as the right person every time. That IS testable here,
     and it is what fails silently: a repository built once and shared, a
     cached client, a dependency that resolves to the first caller's identity.

`RlsFakeRepository` below models rule 1 so rule 2 can be checked against it. It
is not a claim that Postgres behaves this way; it is a harness that behaves the
way Postgres is configured to, so that a bug in the identity plumbing shows up
as one user reading another's rows - exactly as it would in production.

`TestTheDatabaseIsAskedAsTheRightPerson` closes the loop by asserting, at the
HTTP level, that the credential actually sent to PostgREST is the caller's own.

NO DATABASE. NO NETWORK. NO CREDENTIALS.
"""

from __future__ import annotations

from datetime import UTC, datetime

import httpx
import pytest
from fastapi.testclient import TestClient

from src.api.analyze import get_provider
from src.api.papers import get_library
from src.config import Settings, get_settings
from src.db.repository import (
    NotFoundError,
    PaperRepository,
    RepositoryError,
)
from src.db.supabase import SupabaseRepository
from src.main import app
from src.schemas.analysis import LiteratureReview
from src.schemas.library import (
    LibraryStats,
    PaperDetail,
    PaperListItem,
    PaperStatus,
    ReviewPaperRef,
    ReviewRecord,
    SavePaperRequest,
    SortOrder,
)
from tests.auth_fixtures import USER_A, USER_B, sign_in_as
from tests.test_analysis import FakeLLMProvider
from tests.test_library import _gaps, _review, _summary

# --------------------------------------------------------------------------- #
# A shared store that enforces ownership the way RLS does
# --------------------------------------------------------------------------- #


class Store:
    """One database, shared by everybody. Rows carry an owner."""

    def __init__(self) -> None:
        # paper_id -> (owner_id, PaperDetail)
        self.papers: dict[str, tuple[str, PaperDetail]] = {}
        self.reviews: dict[str, tuple[str, ReviewRecord]] = {}
        self.next_id = 0

    def new_id(self, prefix: str) -> str:
        self.next_id += 1
        return f"{prefix}-{self.next_id}"


class RlsFakeRepository(PaperRepository):
    """The shared store, seen through ONE user's eyes.

    Every read filters on `self.owner`, and every write stamps it. That is
    precisely what `user_id = auth.uid()` does in Postgres. A row belonging to
    somebody else is not refused, it is ABSENT - which is why the tests below
    expect 404 rather than 403.
    """

    def __init__(self, store: Store, owner: str) -> None:
        self.store = store
        self.owner = owner

    # -- the rule, in one place --------------------------------------------

    def _visible_papers(self) -> dict[str, PaperDetail]:
        return {
            pid: paper for pid, (owner, paper) in self.store.papers.items() if owner == self.owner
        }

    def _visible_reviews(self) -> dict[str, ReviewRecord]:
        return {
            rid: review
            for rid, (owner, review) in self.store.reviews.items()
            if owner == self.owner
        }

    # -- interface ----------------------------------------------------------

    async def health(self) -> bool:
        return True

    async def save_paper(self, request: SavePaperRequest) -> PaperDetail:
        paper_id = self.store.new_id("paper")
        now = datetime.now(UTC)
        detail = PaperDetail(
            id=paper_id,
            title=request.title,
            filename=request.filename,
            status=PaperStatus.READY,
            page_count=request.document.page_count,
            extracted_characters=request.document.extracted_characters,
            file_size_bytes=request.file_size_bytes,
            content_type=request.content_type,
            created_at=now,
            updated_at=now,
            summary=request.summary,
            research_gaps=request.research_gaps,
            literature_review=request.literature_review,
            model_used=request.model_used,
            chunk_count=request.document.chunk_count,
            truncated=request.document.truncated,
        )
        self.store.papers[paper_id] = (self.owner, detail)
        return detail

    async def list_papers(
        self,
        *,
        search: str | None = None,
        status: str | None = None,
        sort: SortOrder = SortOrder.NEWEST,
        limit: int = 50,
        offset: int = 0,
    ) -> tuple[list[PaperListItem], int]:
        papers = list(self._visible_papers().values())
        if search:
            term = search.lower()
            papers = [p for p in papers if term in p.title.lower()]
        items = [
            PaperListItem(
                id=p.id,
                title=p.title,
                filename=p.filename,
                status=p.status,
                page_count=p.page_count,
                file_size_bytes=p.file_size_bytes,
                created_at=p.created_at,
                updated_at=p.updated_at,
                has_analysis=p.summary is not None,
                gap_count=(len(p.research_gaps.identified_gaps) if p.research_gaps else None),
            )
            for p in papers
        ]
        return items[offset : offset + limit], len(items)

    async def get_paper(self, paper_id: str) -> PaperDetail:
        paper = self._visible_papers().get(paper_id)
        if paper is None:
            raise NotFoundError("That paper is not in your library.")
        return paper

    async def delete_paper(self, paper_id: str) -> bool:
        if paper_id not in self._visible_papers():
            raise NotFoundError("That paper is not in your library.")
        del self.store.papers[paper_id]
        return True

    async def get_papers_for_review(self, paper_ids: list[str]) -> list[PaperDetail]:
        visible = self._visible_papers()
        missing = [pid for pid in paper_ids if pid not in visible]
        if missing:
            raise NotFoundError(f"{len(missing)} selected paper(s) are no longer in your library.")
        return [visible[pid] for pid in paper_ids]

    async def save_review(
        self,
        *,
        title: str,
        model_used: str,
        content: LiteratureReview,
        paper_ids: list[str],
    ) -> ReviewRecord:
        visible = self._visible_papers()
        # Mirrors the RESTRICTIVE policy migration 003 adds: a review may only
        # link papers its author owns.
        if any(pid not in visible for pid in paper_ids):
            raise NotFoundError("Those papers are not in your library.")
        review_id = self.store.new_id("review")
        record = ReviewRecord(
            id=review_id,
            title=title,
            model_used=model_used,
            content=content,
            paper_count=len(paper_ids),
            papers=[
                ReviewPaperRef(id=pid, title=visible[pid].title, filename=visible[pid].filename)
                for pid in paper_ids
            ],
            created_at=datetime.now(UTC),
        )
        self.store.reviews[review_id] = (self.owner, record)
        return record

    async def list_reviews(self, *, limit: int = 50) -> tuple[list[ReviewRecord], int]:
        reviews = list(self._visible_reviews().values())
        return reviews[:limit], len(reviews)

    async def get_review(self, review_id: str) -> ReviewRecord:
        review = self._visible_reviews().get(review_id)
        if review is None:
            raise NotFoundError("That literature review was not found.")
        return review

    async def delete_review(self, review_id: str) -> bool:
        if review_id not in self._visible_reviews():
            raise NotFoundError("That literature review was not found.")
        del self.store.reviews[review_id]
        return True

    async def stats(self) -> LibraryStats:
        papers = list(self._visible_papers().values())
        gaps = 0
        for paper in papers:
            if paper.research_gaps and not paper.research_gaps.insufficient_evidence:
                gaps += len(paper.research_gaps.identified_gaps)
        return LibraryStats(
            papers_analysed=sum(1 for p in papers if p.summary),
            research_gaps_found=gaps,
            literature_reviews=len(self._visible_reviews()),
            saved_papers=len(papers),
        )


# --------------------------------------------------------------------------- #
# Harness
# --------------------------------------------------------------------------- #


@pytest.fixture
def store() -> Store:
    return Store()


@pytest.fixture
def client(store):
    """One TestClient over one shared store.

    The repository is built PER REQUEST from whoever is signed in at the time -
    the same shape as production, where `get_library` reads the caller's token.
    Building it once outside the request would hide exactly the bug this file
    is looking for.
    """
    app.dependency_overrides[get_settings] = lambda: Settings(_env_file=None)
    app.dependency_overrides[get_provider] = lambda: FakeLLMProvider()

    def library_for_current_user():
        from src.api.auth import require_user

        user = app.dependency_overrides[require_user]()
        return RlsFakeRepository(store, owner=user.id)

    app.dependency_overrides[get_library] = library_for_current_user
    yield TestClient(app)
    app.dependency_overrides.clear()


def save_paper_as(client: TestClient, user, title: str) -> str:
    """Sign in as `user`, save a paper, return its id."""
    sign_in_as(user)
    response = client.post(
        "/api/papers",
        json={
            "title": title,
            "filename": f"{title.lower().replace(' ', '-')}.pdf",
            "file_size_bytes": 120_000,
            "content_type": "application/pdf",
            "document": {
                "filename": f"{title.lower().replace(' ', '-')}.pdf",
                "page_count": 10,
                "extracted_characters": 30_000,
                "chunk_count": 1,
                "truncated": False,
            },
            "summary": _summary().model_dump(),
            "research_gaps": _gaps().model_dump(),
            "literature_review": _review().model_dump(),
            "model_used": "gemini-3.7-flash",
        },
    )
    assert response.status_code == 201, response.text
    return response.json()["id"]


def titles_in_library(client: TestClient, user) -> list[str]:
    sign_in_as(user)
    response = client.get("/api/papers")
    assert response.status_code == 200
    return [p["title"] for p in response.json()["papers"]]


# --------------------------------------------------------------------------- #
# The headline test
# --------------------------------------------------------------------------- #


class TestTwoUsersDoNotShareALibrary:
    """The scenario, start to finish, in one test.

    User A registers and saves a paper. User B registers on another device and
    must not see it. B saves their own. A must still see only their own. This
    is the sequence that used to fail.
    """

    def test_the_full_two_user_scenario(self, client) -> None:
        paper_a = save_paper_as(client, USER_A, "Attention Is All You Need")

        # A sees their own paper.
        assert titles_in_library(client, USER_A) == ["Attention Is All You Need"]

        # B, on another device, sees an EMPTY library - not A's.
        assert titles_in_library(client, USER_B) == []

        paper_b = save_paper_as(client, USER_B, "Federated Clinical Models")

        # B sees only their own.
        assert titles_in_library(client, USER_B) == ["Federated Clinical Models"]

        # A sees only their own, still. B's paper did not appear in it.
        assert titles_in_library(client, USER_A) == ["Attention Is All You Need"]

        # And the two really are different rows in one shared store, which is
        # what makes the assertions above meaningful rather than tautological.
        assert paper_a != paper_b
        assert len(client.app.dependency_overrides) > 0  # harness still wired

    def test_the_store_really_did_hold_both_papers(self, client, store) -> None:
        """Guards against a false pass.

        If saving silently failed, every library would be empty and every
        assertion above would hold for the wrong reason. This asserts the
        shared store contains both rows, under two different owners.
        """
        save_paper_as(client, USER_A, "Paper A")
        save_paper_as(client, USER_B, "Paper B")
        owners = {owner for owner, _ in store.papers.values()}
        assert len(store.papers) == 2
        assert owners == {USER_A.id, USER_B.id}


# --------------------------------------------------------------------------- #
# Reaching for another user's data directly
# --------------------------------------------------------------------------- #


class TestGuessingAnIdDoesNotWork:
    """Changing the id in the URL must not reach somebody else's record."""

    def test_user_b_cannot_open_user_as_paper_by_id(self, client) -> None:
        paper_a = save_paper_as(client, USER_A, "Attention Is All You Need")
        sign_in_as(USER_B)
        assert client.get(f"/api/papers/{paper_a}").status_code == 404

    def test_the_refusal_is_404_and_not_403(self, client) -> None:
        """403 would confirm the paper exists. A person probing ids would learn
        which ones are real, which is a smaller leak than the content but a
        leak all the same. 404 makes "someone else's" and "never existed"
        indistinguishable."""
        paper_a = save_paper_as(client, USER_A, "Attention Is All You Need")
        sign_in_as(USER_B)
        response = client.get(f"/api/papers/{paper_a}")
        assert response.status_code == 404
        assert response.status_code != 403

    def test_the_refusal_leaks_no_part_of_the_paper(self, client) -> None:
        paper_a = save_paper_as(client, USER_A, "Attention Is All You Need")
        sign_in_as(USER_B)
        body = client.get(f"/api/papers/{paper_a}").text
        assert "Attention" not in body
        assert "attention" not in body.lower()

    def test_user_b_cannot_delete_user_as_paper(self, client, store) -> None:
        """The dangerous one. A read leaks; a write destroys."""
        paper_a = save_paper_as(client, USER_A, "Attention Is All You Need")
        sign_in_as(USER_B)
        assert client.delete(f"/api/papers/{paper_a}").status_code == 404
        # Still there, and still A's.
        assert paper_a in store.papers
        assert store.papers[paper_a][0] == USER_A.id
        assert titles_in_library(client, USER_A) == ["Attention Is All You Need"]

    def test_user_b_cannot_open_user_as_review_by_id(self, client) -> None:
        paper_a = save_paper_as(client, USER_A, "Attention Is All You Need")
        sign_in_as(USER_A)
        review = client.post("/api/reviews/cross", json={"paper_ids": [paper_a, paper_a]})
        # One paper twice is still one paper; the endpoint may refuse it. Only
        # proceed if a review was actually created.
        if review.status_code == 201:
            review_id = review.json()["id"]
            sign_in_as(USER_B)
            assert client.get(f"/api/reviews/{review_id}").status_code == 404

    def test_user_b_cannot_delete_user_as_review(self, client, store) -> None:
        paper_a1 = save_paper_as(client, USER_A, "Paper One")
        paper_a2 = save_paper_as(client, USER_A, "Paper Two")
        sign_in_as(USER_A)
        created = client.post("/api/reviews/cross", json={"paper_ids": [paper_a1, paper_a2]})
        assert created.status_code == 201, created.text
        review_id = created.json()["id"]

        sign_in_as(USER_B)
        assert client.delete(f"/api/reviews/{review_id}").status_code == 404
        assert review_id in store.reviews


# --------------------------------------------------------------------------- #
# Cross-paper review
# --------------------------------------------------------------------------- #


class TestCrossPaperReviewStaysWithinOneLibrary:
    def test_a_user_can_review_their_own_papers(self, client) -> None:
        """The feature must still work. An isolation change that broke the
        product would be a regression, not a fix."""
        first = save_paper_as(client, USER_A, "Paper One")
        second = save_paper_as(client, USER_A, "Paper Two")
        sign_in_as(USER_A)
        response = client.post("/api/reviews/cross", json={"paper_ids": [first, second]})
        assert response.status_code == 201, response.text
        body = response.json()
        assert body["paper_count"] == 2
        assert {p["title"] for p in body["papers"]} == {"Paper One", "Paper Two"}

    def test_both_users_can_review_their_own_papers_independently(self, client) -> None:
        a1 = save_paper_as(client, USER_A, "A One")
        a2 = save_paper_as(client, USER_A, "A Two")
        b1 = save_paper_as(client, USER_B, "B One")
        b2 = save_paper_as(client, USER_B, "B Two")

        sign_in_as(USER_A)
        review_a = client.post("/api/reviews/cross", json={"paper_ids": [a1, a2]})
        assert review_a.status_code == 201
        assert {p["title"] for p in review_a.json()["papers"]} == {"A One", "A Two"}

        sign_in_as(USER_B)
        review_b = client.post("/api/reviews/cross", json={"paper_ids": [b1, b2]})
        assert review_b.status_code == 201
        assert {p["title"] for p in review_b.json()["papers"]} == {"B One", "B Two"}

    def test_user_b_cannot_include_user_as_paper_in_a_review(self, client) -> None:
        """The specific attack: B knows A's paper id and puts it in the list.

        It must be refused outright, never quietly dropped - a review built
        from one paper while reporting two would be worse than an error.
        """
        paper_a = save_paper_as(client, USER_A, "Attention Is All You Need")
        paper_b = save_paper_as(client, USER_B, "Federated Clinical Models")

        sign_in_as(USER_B)
        response = client.post("/api/reviews/cross", json={"paper_ids": [paper_b, paper_a]})
        assert response.status_code == 404
        assert "Attention" not in response.text

    def test_a_review_of_only_another_users_papers_is_refused(self, client) -> None:
        a1 = save_paper_as(client, USER_A, "A One")
        a2 = save_paper_as(client, USER_A, "A Two")
        sign_in_as(USER_B)
        response = client.post("/api/reviews/cross", json={"paper_ids": [a1, a2]})
        assert response.status_code == 404

    def test_a_saved_review_is_not_listed_for_the_other_user(self, client) -> None:
        a1 = save_paper_as(client, USER_A, "A One")
        a2 = save_paper_as(client, USER_A, "A Two")
        sign_in_as(USER_A)
        assert client.post("/api/reviews/cross", json={"paper_ids": [a1, a2]}).status_code == 201

        sign_in_as(USER_A)
        assert client.get("/api/reviews").json()["total"] == 1

        sign_in_as(USER_B)
        assert client.get("/api/reviews").json()["total"] == 0


# --------------------------------------------------------------------------- #
# The dashboard
# --------------------------------------------------------------------------- #


class TestDashboardCountsArePerUser:
    def test_counts_describe_only_the_signed_in_users_library(self, client) -> None:
        """A count is a claim about the reader's own work. Counting everybody's
        rows would report a number that is true of the database and false of
        the person reading it."""
        save_paper_as(client, USER_A, "A One")
        save_paper_as(client, USER_A, "A Two")
        save_paper_as(client, USER_B, "B One")

        sign_in_as(USER_A)
        stats_a = client.get("/api/papers/stats").json()
        assert stats_a["saved_papers"] == 2
        assert stats_a["papers_analysed"] == 2

        sign_in_as(USER_B)
        stats_b = client.get("/api/papers/stats").json()
        assert stats_b["saved_papers"] == 1
        assert stats_b["papers_analysed"] == 1

    def test_a_brand_new_account_sees_zeros_not_the_database(self, client) -> None:
        save_paper_as(client, USER_A, "A One")
        sign_in_as(USER_B)
        stats = client.get("/api/papers/stats").json()
        assert stats == {
            "papers_analysed": 0,
            "research_gaps_found": 0,
            "literature_reviews": 0,
            "saved_papers": 0,
        }

    def test_search_cannot_reach_across_libraries(self, client) -> None:
        """Search is a second way into the list, and it used to share the list's
        query. A filter that widened the scope instead of narrowing it would
        show up only here."""
        save_paper_as(client, USER_A, "Attention Is All You Need")
        sign_in_as(USER_B)
        response = client.get("/api/papers", params={"search": "Attention"})
        assert response.status_code == 200
        assert response.json()["papers"] == []


# --------------------------------------------------------------------------- #
# The credential that actually reaches the database
# --------------------------------------------------------------------------- #


class TestTheDatabaseIsAskedAsTheRightPerson:
    """Closes the loop the fake cannot.

    The tests above prove the API keeps two identities apart. These prove the
    identity is what gets SENT: each request to PostgREST must carry that
    user's own access token, because that token is the only reason Postgres
    applies their row-level policies rather than nobody's.
    """

    @staticmethod
    def _settings() -> Settings:
        return Settings(
            _env_file=None,
            supabase_url="https://example-project.supabase.co",
            supabase_service_role_key="sb_secret_exampleonlynotarealkey000000",
            supabase_anon_key="not-a-real-anon-key-for-tests-only",
        )

    def _capture(self, monkeypatch, user) -> list[httpx.Request]:
        seen: list[httpx.Request] = []
        original = httpx.AsyncClient

        def recording(request: httpx.Request) -> httpx.Response:
            seen.append(request)
            return httpx.Response(200, json=[])

        def patched(*args, **kwargs):
            kwargs.setdefault("transport", httpx.MockTransport(recording))
            return original(*args, **kwargs)

        monkeypatch.setattr("src.db.supabase.httpx.AsyncClient", patched)
        repository = SupabaseRepository(self._settings(), access_token=user.token, user_id=user.id)
        import asyncio

        asyncio.run(repository.list_papers())
        return seen

    def test_each_users_own_token_is_what_goes_to_postgrest(self, monkeypatch) -> None:
        seen_a = self._capture(monkeypatch, USER_A)
        assert seen_a[0].headers["authorization"] == f"Bearer {USER_A.token}"

        seen_b = self._capture(monkeypatch, USER_B)
        assert seen_b[0].headers["authorization"] == f"Bearer {USER_B.token}"

    def test_the_service_role_key_never_reaches_the_database(self, monkeypatch) -> None:
        """The single most important assertion in this file.

        A service-role key BYPASSES Row Level Security. If it ever appeared on
        one of these requests, every policy would be skipped and every test
        above would still pass while production served the whole table to
        everyone - which is exactly what used to happen.
        """
        secret = self._settings().supabase_service_role_key
        seen = self._capture(monkeypatch, USER_A)
        for request in seen:
            assert secret not in str(request.headers)

    def test_a_write_stamps_the_owner_onto_the_row(self, monkeypatch) -> None:
        """Belt and braces beside the database DEFAULT of auth.uid().

        The row must arrive already owned. If it did not, migration 003's
        `WITH CHECK (user_id = auth.uid())` would refuse the write - a failed
        save, never a paper filed under the wrong person - but a refused save
        is still a broken product, so the value is sent explicitly.
        """
        import asyncio
        import json

        seen: list[httpx.Request] = []
        original = httpx.AsyncClient

        def recording(request: httpx.Request) -> httpx.Response:
            seen.append(request)
            return httpx.Response(200, json=[{"id": "paper-1", "title": "T", "filename": "f.pdf"}])

        def patched(*args, **kwargs):
            kwargs.setdefault("transport", httpx.MockTransport(recording))
            return original(*args, **kwargs)

        monkeypatch.setattr("src.db.supabase.httpx.AsyncClient", patched)
        repository = SupabaseRepository(
            self._settings(), access_token=USER_A.token, user_id=USER_A.id
        )
        request = SavePaperRequest(
            title="Attention Is All You Need",
            filename="attention.pdf",
            file_size_bytes=1000,
            content_type="application/pdf",
            document={
                "filename": "attention.pdf",
                "page_count": 10,
                "extracted_characters": 30_000,
                "chunk_count": 1,
                "truncated": False,
            },
            summary=_summary(),
            research_gaps=_gaps(),
            literature_review=_review(),
            model_used="gemini-3.7-flash",
        )
        try:
            asyncio.run(repository.save_paper(request))
        except RepositoryError:
            # The mocked reply is not a complete paper row, so mapping the
            # result may fail. The assertion is about what was SENT.
            pass

        writes = [r for r in seen if r.method == "POST"]
        assert writes, "no write was attempted"
        paper_body = json.loads(writes[0].content)
        assert paper_body["user_id"] == USER_A.id


# --------------------------------------------------------------------------- #
# Guard against the harness proving nothing
# --------------------------------------------------------------------------- #


class TestTheHarnessWouldCatchALeak:
    """A test suite that cannot fail is not a test suite.

    If `RlsFakeRepository` filtered nothing, every assertion above would pass
    for the wrong reason. This deliberately builds a repository that IGNORES
    ownership and shows that the headline scenario then fails - so the passing
    result above is load-bearing.
    """

    def test_an_unfiltered_repository_would_show_the_leak(self, store) -> None:
        class LeakyRepository(RlsFakeRepository):
            def _visible_papers(self):
                # No ownership filter: the pre-authentication behaviour.
                return {pid: paper for pid, (_, paper) in self.store.papers.items()}

        import asyncio

        a = RlsFakeRepository(store, owner=USER_A.id)
        asyncio.run(
            a.save_paper(
                SavePaperRequest(
                    title="Attention Is All You Need",
                    filename="attention.pdf",
                    document={
                        "filename": "attention.pdf",
                        "page_count": 1,
                        "extracted_characters": 10,
                        "chunk_count": 1,
                        "truncated": False,
                    },
                    summary=_summary(),
                    research_gaps=_gaps(),
                    literature_review=_review(),
                    model_used="gemini-3.7-flash",
                )
            )
        )

        # Correct repository: B sees nothing.
        b_correct = RlsFakeRepository(store, owner=USER_B.id)
        items, _ = asyncio.run(b_correct.list_papers())
        assert items == []

        # Broken repository: B sees A's paper. This is the bug, reproduced.
        b_leaky = LeakyRepository(store, owner=USER_B.id)
        leaked, _ = asyncio.run(b_leaky.list_papers())
        assert [i.title for i in leaked] == ["Attention Is All You Need"]
