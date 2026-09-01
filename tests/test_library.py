"""The research library API, driven by an in-memory repository.

NO DATABASE, NO NETWORK, NO KEYS. `FakeRepository` satisfies the same
`PaperRepository` interface the Supabase implementation does, so these tests
exercise the real endpoints, the real schemas and the real status-code mapping
without any of them needing Postgres. That is the point of the interface.

What is deliberately NOT tested here: that PostgREST behaves as
`src/db/supabase.py` expects. That needs a live database and is called out as
untested in docs/DATABASE.md rather than faked with a mock that would only
prove the mock agrees with itself.
"""

from datetime import UTC, datetime

import pytest
from fastapi.testclient import TestClient

from src.api.analyze import get_provider
from src.api.papers import get_library
from src.config import Settings, get_settings
from src.db.repository import (
    ConflictError,
    NotFoundError,
    PaperRepository,
    RepositoryUnavailableError,
)
from src.main import app
from src.schemas.analysis import LiteratureReview, ResearchGap, ResearchGaps, Summary
from src.schemas.library import (
    LibraryStats,
    PaperDetail,
    PaperListItem,
    PaperStatus,
    ReviewPaperRef,
    ReviewRecord,
    SortOrder,
)
from tests.test_analysis import FakeLLMProvider

# --------------------------------------------------------------------------- #
# Fixtures for the stored shapes
# --------------------------------------------------------------------------- #


def _summary() -> Summary:
    return Summary(
        research_problem="Whether attention alone suffices.",
        methodology="Encoder-decoder built only from attention.",
        key_findings=["Higher BLEU at lower cost.", "Trains in less time."],
        conclusion="Recurrence is not required.",
        insufficient_evidence=[],
    )


def _gaps(count: int = 2) -> ResearchGaps:
    return ResearchGaps(
        stated_limitations=["Text only."],
        identified_gaps=[
            ResearchGap(
                gap=f"Gap {i}",
                why_it_matters="It bounds the claim.",
                evidence="Section 7 says so.",
            )
            for i in range(count)
        ],
        insufficient_evidence=False,
        evidence_note="",
    )


def _review() -> LiteratureReview:
    return LiteratureReview(
        scope_note="Prior work discussed within the paper.",
        major_themes=["Sequence transduction"],
        relevant_findings=["Recurrent models dominated."],
        comparisons=["Compared against ByteNet."],
        research_trends=["Toward parallelism."],
        limitations=["Prior work was sequential."],
        future_directions=["Apply beyond text."],
        insufficient_evidence=False,
    )


def _detail(paper_id: str, title: str, *, analysed: bool = True, gaps: int = 2) -> PaperDetail:
    now = datetime.now(UTC)
    return PaperDetail(
        id=paper_id,
        title=title,
        filename=f"{title.lower().replace(' ', '-')}.pdf",
        status=PaperStatus.READY,
        page_count=15,
        extracted_characters=40_000,
        file_size_bytes=2_215_244,
        content_type="application/pdf",
        created_at=now,
        updated_at=now,
        summary=_summary() if analysed else None,
        research_gaps=_gaps(gaps) if analysed else None,
        literature_review=_review() if analysed else None,
        model_used="gemini-3.7-flash" if analysed else None,
        chunk_count=1 if analysed else None,
        truncated=False if analysed else None,
    )


# --------------------------------------------------------------------------- #
# The fake
# --------------------------------------------------------------------------- #


class FakeRepository(PaperRepository):
    """An in-memory library. Same contract, no Postgres."""

    def __init__(self, papers: list[PaperDetail] | None = None, *, fail_with=None):
        self.papers: dict[str, PaperDetail] = {p.id: p for p in (papers or [])}
        self.reviews: dict[str, ReviewRecord] = {}
        self.fail_with = fail_with
        self.deleted: list[str] = []
        self.saved_review_paper_ids: list[str] = []

    def _guard(self):
        if self.fail_with is not None:
            raise self.fail_with

    async def health(self) -> bool:
        return self.fail_with is None

    async def save_paper(self, request):
        self._guard()
        detail = _detail(f"id-{len(self.papers) + 1}", request.title)
        self.papers[detail.id] = detail
        return detail

    async def list_papers(
        self, *, search=None, status=None, sort=SortOrder.NEWEST, limit=50, offset=0
    ):
        self._guard()
        rows = list(self.papers.values())
        if search:
            term = search.lower()
            rows = [p for p in rows if term in p.title.lower() or term in p.filename.lower()]
        if status:
            rows = [p for p in rows if p.status.value == status]
        if sort is SortOrder.TITLE:
            rows.sort(key=lambda p: p.title)
        elif sort is SortOrder.OLDEST:
            rows.sort(key=lambda p: p.created_at)
        else:
            rows.sort(key=lambda p: p.created_at, reverse=True)
        total = len(rows)
        page = rows[offset : offset + limit]
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
                gap_count=(
                    len(p.research_gaps.identified_gaps)
                    if p.research_gaps and not p.research_gaps.insufficient_evidence
                    else None
                ),
            )
            for p in page
        ]
        return items, total

    async def get_paper(self, paper_id):
        self._guard()
        if paper_id not in self.papers:
            raise NotFoundError("That paper is not in your library.")
        return self.papers[paper_id]

    async def delete_paper(self, paper_id):
        self._guard()
        if paper_id not in self.papers:
            raise NotFoundError("That paper is not in your library.")
        del self.papers[paper_id]
        self.deleted.append(paper_id)
        return True

    async def get_papers_for_review(self, paper_ids):
        self._guard()
        missing = [pid for pid in paper_ids if pid not in self.papers]
        if missing:
            raise NotFoundError(f"{len(missing)} selected paper(s) are no longer in your library.")
        return [self.papers[pid] for pid in paper_ids]

    async def save_review(self, *, title, model_used, content, paper_ids):
        self._guard()
        self.saved_review_paper_ids = list(paper_ids)
        record = ReviewRecord(
            id=f"rev-{len(self.reviews) + 1}",
            title=title,
            model_used=model_used,
            content=content,
            paper_count=len(paper_ids),
            papers=[
                ReviewPaperRef(
                    id=pid, title=self.papers[pid].title, filename=self.papers[pid].filename
                )
                for pid in paper_ids
            ],
            created_at=datetime.now(UTC),
        )
        self.reviews[record.id] = record
        return record

    async def list_reviews(self, *, limit=50):
        self._guard()
        rows = list(self.reviews.values())[:limit]
        return rows, len(rows)

    async def get_review(self, review_id):
        self._guard()
        if review_id not in self.reviews:
            raise NotFoundError("That literature review was not found.")
        return self.reviews[review_id]

    async def delete_review(self, review_id):
        self._guard()
        if review_id not in self.reviews:
            raise NotFoundError("That literature review was not found.")
        del self.reviews[review_id]
        return True

    async def stats(self):
        self._guard()
        gaps = sum(
            len(p.research_gaps.identified_gaps)
            for p in self.papers.values()
            if p.research_gaps and not p.research_gaps.insufficient_evidence
        )
        return LibraryStats(
            papers_analysed=sum(1 for p in self.papers.values() if p.summary),
            research_gaps_found=gaps,
            literature_reviews=len(self.reviews),
            saved_papers=len(self.papers),
        )


@pytest.fixture
def library():
    repo = FakeRepository([_detail("p1", "Attention Paper"), _detail("p2", "Bert Paper", gaps=3)])
    app.dependency_overrides[get_library] = lambda: repo
    app.dependency_overrides[get_settings] = lambda: Settings(_env_file=None)
    app.dependency_overrides[get_provider] = lambda: FakeLLMProvider()
    yield repo
    app.dependency_overrides.clear()


@pytest.fixture
def client(library):
    return TestClient(app)


# --------------------------------------------------------------------------- #
# Availability
# --------------------------------------------------------------------------- #


class TestLibraryAvailability:
    def test_without_a_database_the_library_reports_503_not_an_empty_list(self) -> None:
        """An empty list is a claim: "you have no papers". A deployment with no
        database is not in a position to make it."""
        app.dependency_overrides.clear()
        r = TestClient(app).get("/api/papers")
        assert r.status_code == 503
        assert "not connected" in r.json()["detail"]

    def test_health_reports_whether_the_library_is_configured(self) -> None:
        app.dependency_overrides.clear()
        body = TestClient(app).get("/health").json()
        assert body["library"] is False

    def test_health_never_leaks_the_database_url_or_key(self) -> None:
        app.dependency_overrides.clear()
        body = TestClient(app).get("/health").json()
        assert set(body) == {
            "status",
            "app_name",
            "version",
            "environment",
            "library",
        }

    def test_storage_failure_surfaces_as_503(self, client, library) -> None:
        library.fail_with = RepositoryUnavailableError("The library is unreachable.")
        assert client.get("/api/papers").status_code == 503


# --------------------------------------------------------------------------- #
# Listing, search, filter, sort
# --------------------------------------------------------------------------- #


class TestListPapers:
    def test_lists_saved_papers_with_a_total(self, client) -> None:
        body = client.get("/api/papers").json()
        assert body["total"] == 2
        assert {p["title"] for p in body["papers"]} == {"Attention Paper", "Bert Paper"}

    def test_gap_count_comes_from_the_stored_analysis(self, client) -> None:
        body = client.get("/api/papers").json()
        counts = {p["title"]: p["gap_count"] for p in body["papers"]}
        assert counts == {"Attention Paper": 2, "Bert Paper": 3}

    def test_search_matches_title(self, client) -> None:
        body = client.get("/api/papers", params={"search": "attention"}).json()
        assert body["total"] == 1
        assert body["papers"][0]["title"] == "Attention Paper"

    def test_search_matches_filename(self, client) -> None:
        body = client.get("/api/papers", params={"search": "bert-paper.pdf"}).json()
        assert body["total"] == 1

    def test_search_with_no_matches_is_an_empty_list_not_an_error(self, client) -> None:
        body = client.get("/api/papers", params={"search": "nothing"}).json()
        assert body == {"papers": [], "total": 0}

    def test_filter_by_status(self, client) -> None:
        assert client.get("/api/papers", params={"status": "ready"}).json()["total"] == 2
        assert client.get("/api/papers", params={"status": "failed"}).json()["total"] == 0

    def test_invalid_status_is_rejected(self, client) -> None:
        assert client.get("/api/papers", params={"status": "banana"}).status_code == 422

    def test_sort_by_title(self, client) -> None:
        body = client.get("/api/papers", params={"sort": "title"}).json()
        assert [p["title"] for p in body["papers"]] == ["Attention Paper", "Bert Paper"]

    def test_invalid_sort_is_rejected(self, client) -> None:
        assert client.get("/api/papers", params={"sort": "sideways"}).status_code == 422

    def test_paging_reports_the_full_total_not_the_page_length(self, client) -> None:
        """Otherwise the interface under-reports on every page but the last."""
        body = client.get("/api/papers", params={"limit": 1}).json()
        assert len(body["papers"]) == 1
        assert body["total"] == 2


# --------------------------------------------------------------------------- #
# Detail and delete
# --------------------------------------------------------------------------- #


class TestPaperDetail:
    def test_returns_the_stored_analysis(self, client) -> None:
        body = client.get("/api/papers/p1").json()
        assert body["title"] == "Attention Paper"
        assert body["summary"]["research_problem"]
        assert len(body["research_gaps"]["identified_gaps"]) == 2
        assert body["literature_review"]["major_themes"]

    def test_unknown_paper_is_404(self, client) -> None:
        assert client.get("/api/papers/nope").status_code == 404


class TestDeletePaper:
    def test_deletes(self, client, library) -> None:
        r = client.delete("/api/papers/p1")
        assert r.status_code == 200
        assert r.json() == {"id": "p1", "deleted": True}
        assert "p1" not in library.papers

    def test_unknown_paper_is_404(self, client) -> None:
        assert client.delete("/api/papers/nope").status_code == 404

    def test_paper_used_by_a_saved_review_is_409_not_a_silent_cascade(
        self, client, library
    ) -> None:
        """Cascading would leave the review claiming more sources than it can
        still name, which is quieter and worse than refusing."""
        library.fail_with = ConflictError("This paper is part of a saved review.")
        r = client.delete("/api/papers/p1")
        assert r.status_code == 409
        assert "review" in r.json()["detail"].lower()


# --------------------------------------------------------------------------- #
# Stats
# --------------------------------------------------------------------------- #


class TestStats:
    def test_counts_come_from_stored_rows(self, client) -> None:
        body = client.get("/api/papers/stats").json()
        assert body == {
            "papers_analysed": 2,
            "research_gaps_found": 5,
            "literature_reviews": 0,
            "saved_papers": 2,
        }

    def test_stats_is_not_shadowed_by_the_paper_id_route(self, client) -> None:
        """/api/papers/stats must not be read as a paper whose id is "stats"."""
        assert client.get("/api/papers/stats").status_code == 200


# --------------------------------------------------------------------------- #
# Cross-paper review
# --------------------------------------------------------------------------- #


class TestCrossReview:
    def test_generates_and_saves_a_review_over_the_selected_papers(self, client, library) -> None:
        r = client.post("/api/reviews/cross", json={"paper_ids": ["p1", "p2"]})
        assert r.status_code == 201
        body = r.json()
        assert body["paper_count"] == 2
        assert {p["title"] for p in body["papers"]} == {"Attention Paper", "Bert Paper"}
        assert body["content"]["major_themes"]

    def test_the_review_records_which_papers_it_used(self, client, library) -> None:
        """The interface says "based on N papers". This is the record of which."""
        client.post("/api/reviews/cross", json={"paper_ids": ["p2", "p1"]})
        assert library.saved_review_paper_ids == ["p2", "p1"]

    def test_fewer_than_two_papers_is_rejected(self, client) -> None:
        """A cross-paper review of one paper is that paper's own review, which
        already exists."""
        assert client.post("/api/reviews/cross", json={"paper_ids": ["p1"]}).status_code == 422
        assert client.post("/api/reviews/cross", json={"paper_ids": []}).status_code == 422

    def test_a_missing_paper_fails_rather_than_reviewing_the_rest(self, client) -> None:
        """A review that quietly covered one of two selected papers would still
        be reported as covering two."""
        r = client.post("/api/reviews/cross", json={"paper_ids": ["p1", "ghost"]})
        assert r.status_code == 404

    def test_a_paper_without_an_analysis_is_rejected(self, client, library) -> None:
        library.papers["p3"] = _detail("p3", "Unanalysed", analysed=False)
        r = client.post("/api/reviews/cross", json={"paper_ids": ["p1", "p3"]})
        assert r.status_code == 422
        assert "Unanalysed" in r.json()["detail"]

    def test_a_custom_title_is_used(self, client) -> None:
        body = client.post(
            "/api/reviews/cross",
            json={"paper_ids": ["p1", "p2"], "title": "Transformers survey"},
        ).json()
        assert body["title"] == "Transformers survey"

    def test_omitting_the_title_produces_a_dated_default(self, client) -> None:
        body = client.post("/api/reviews/cross", json={"paper_ids": ["p1", "p2"]}).json()
        assert "2 papers" in body["title"]

    def test_unknown_fields_are_rejected(self, client) -> None:
        r = client.post("/api/reviews/cross", json={"paper_ids": ["p1", "p2"], "colour": "blue"})
        assert r.status_code == 422


class TestReviewRetrieval:
    def test_saved_reviews_are_listed_and_retrievable(self, client) -> None:
        created = client.post("/api/reviews/cross", json={"paper_ids": ["p1", "p2"]}).json()
        listed = client.get("/api/reviews").json()
        assert listed["total"] == 1
        fetched = client.get(f"/api/reviews/{created['id']}").json()
        assert fetched["id"] == created["id"]

    def test_unknown_review_is_404(self, client) -> None:
        assert client.get("/api/reviews/nope").status_code == 404

    def test_reviews_can_be_deleted(self, client) -> None:
        created = client.post("/api/reviews/cross", json={"paper_ids": ["p1", "p2"]}).json()
        assert client.delete(f"/api/reviews/{created['id']}").status_code == 200
        assert client.get(f"/api/reviews/{created['id']}").status_code == 404


# --------------------------------------------------------------------------- #
# Prompt construction
# --------------------------------------------------------------------------- #


class TestCrossReviewPrompt:
    def test_every_selected_paper_appears_in_the_prompt(self) -> None:
        from src.services.cross_review import build_prompt

        prompt = build_prompt([_detail("p1", "Alpha"), _detail("p2", "Beta")])
        assert "Alpha" in prompt
        assert "Beta" in prompt
        assert "2 papers" in prompt

    def test_the_prompt_forbids_reaching_outside_the_supplied_set(self) -> None:
        from src.services.cross_review import build_prompt

        prompt = build_prompt([_detail("p1", "Alpha"), _detail("p2", "Beta")])
        assert "only sources" in prompt.lower()

    def test_an_empty_section_is_named_rather_than_left_blank(self) -> None:
        from src.services.cross_review import build_paper_block

        paper = _detail("p1", "Alpha", analysed=False)
        block = build_paper_block(paper, 1, 1)
        assert "Not available from this paper." in block
