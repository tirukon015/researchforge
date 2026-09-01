"""`SupabaseRepository` driven against a mock PostgREST.

WHY THIS FILE EXISTS
--------------------
Until now this layer had never executed. `test_library.py` covers the API
through an in-memory fake, which proves the endpoints and the status mapping
but says nothing about whether the Supabase implementation builds correct
PostgREST requests or reads its replies properly. That gap only closes the
moment a real database appears, and by then a mistake costs a debugging
session against production.

httpx's `MockTransport` closes it now. Every request the repository makes is
intercepted and asserted on: the URL, the query string, the headers, the body.
Every reply is one PostgREST would actually send, including its `Content-Range`
count header and its error codes.

This is not a claim that the live database behaves this way. It is a claim that
given PostgREST's documented behaviour, this code does the right thing. The
remaining risk is that PostgREST differs from its documentation, which is a far
smaller surface than the whole layer being unexercised.

NO NETWORK. NO CREDENTIALS. The key below is an obvious fake.
"""

import asyncio
import json

import httpx
import pytest

from src.config import Settings
from src.db.repository import (
    ConflictError,
    NotFoundError,
    RepositoryError,
    RepositoryUnavailableError,
)
from src.db.supabase import SupabaseRepository
from src.schemas.analysis import DocumentInfo, LiteratureReview, ResearchGaps, Summary
from src.schemas.library import SavePaperRequest, SortOrder

FAKE_URL = "https://example-project.supabase.co"
FAKE_KEY = "not-a-real-key-for-tests-only"


def settings() -> Settings:
    return Settings(
        _env_file=None,
        supabase_url=FAKE_URL,
        supabase_service_role_key=FAKE_KEY,
    )


def run(coro):
    """Drive one coroutine. Avoids adding an async test plugin for six tests."""
    return asyncio.run(coro)


@pytest.fixture(autouse=True)
def _patch_client(monkeypatch):
    """Route every AsyncClient the repository builds through the mock."""
    holder: dict[str, httpx.MockTransport] = {}
    original = httpx.AsyncClient

    def patched(*args, **kwargs):
        if "transport" not in kwargs and "mock" in holder:
            kwargs["transport"] = holder["mock"]
        return original(*args, **kwargs)

    monkeypatch.setattr("src.db.supabase.httpx.AsyncClient", patched)
    return holder


def mock(_patch_client, handler):
    """Install a handler and return the list of requests it will record."""
    seen: list[httpx.Request] = []

    def recording(request: httpx.Request) -> httpx.Response:
        seen.append(request)
        return handler(request)

    _patch_client["mock"] = httpx.MockTransport(recording)
    return seen


def repo() -> SupabaseRepository:
    return SupabaseRepository(settings())


# --------------------------------------------------------------------------- #
# Row fixtures, shaped as PostgREST returns them
# --------------------------------------------------------------------------- #

ANALYSIS_JSON = {
    "model_used": "gemini-3.7-flash",
    "summary": {
        "research_problem": "Whether attention alone suffices.",
        "methodology": "Attention only.",
        "key_findings": ["Higher BLEU."],
        "conclusion": "Recurrence is not required.",
        "insufficient_evidence": [],
    },
    "research_gaps": {
        "stated_limitations": ["Text only."],
        "identified_gaps": [
            {"gap": "G1", "why_it_matters": "Bounds it.", "evidence": "Section 7."},
            {"gap": "G2", "why_it_matters": "Bounds it.", "evidence": "Section 7."},
        ],
        "insufficient_evidence": False,
        "evidence_note": "",
    },
    "literature_review": {
        "scope_note": "Within the paper.",
        "major_themes": ["Transduction"],
        "relevant_findings": [],
        "comparisons": [],
        "research_trends": [],
        "limitations": [],
        "future_directions": [],
        "insufficient_evidence": False,
    },
    "chunk_count": 1,
    "truncated": False,
}

PAPER_ROW = {
    "id": "11111111-1111-1111-1111-111111111111",
    "title": "Attention Paper",
    "filename": "attention.pdf",
    "status": "ready",
    "page_count": 15,
    "extracted_characters": 40000,
    "file_size_bytes": 2215244,
    "content_type": "application/pdf",
    "created_at": "2026-09-01T10:00:00+00:00",
    "updated_at": "2026-09-01T10:00:00Z",
    "analyses": [ANALYSIS_JSON],
}


def save_request() -> SavePaperRequest:
    return SavePaperRequest(
        title="Attention Paper",
        filename="attention.pdf",
        file_size_bytes=2215244,
        content_type="application/pdf",
        document=DocumentInfo(
            filename="attention.pdf",
            page_count=15,
            extracted_characters=40000,
            chunk_count=1,
            truncated=False,
        ),
        summary=Summary.model_validate(ANALYSIS_JSON["summary"]),
        research_gaps=ResearchGaps.model_validate(ANALYSIS_JSON["research_gaps"]),
        literature_review=LiteratureReview.model_validate(ANALYSIS_JSON["literature_review"]),
        model_used="gemini-3.7-flash",
    )


def json_response(payload, status=200, headers=None) -> httpx.Response:
    return httpx.Response(status, json=payload, headers=headers or {})


# --------------------------------------------------------------------------- #
# Configuration and credentials
# --------------------------------------------------------------------------- #


class TestConstruction:
    def test_refuses_to_build_without_configuration(self) -> None:
        with pytest.raises(RepositoryUnavailableError) as exc:
            SupabaseRepository(Settings(_env_file=None))
        assert "SUPABASE_URL" in str(exc.value)

    def test_authenticates_with_the_service_role_key_on_both_headers(self, _patch_client) -> None:
        """PostgREST wants the key in `apikey`; PostgreSQL role selection reads
        the bearer token. Both are required, and both must carry the key."""
        seen = mock(_patch_client, lambda r: json_response([PAPER_ROW]))
        run(repo().get_paper("11111111-1111-1111-1111-111111111111"))
        headers = seen[0].headers
        assert headers["apikey"] == FAKE_KEY
        assert headers["authorization"] == f"Bearer {FAKE_KEY}"

    def test_a_trailing_slash_on_the_url_does_not_double_up(self) -> None:
        s = Settings(
            _env_file=None,
            supabase_url=FAKE_URL + "/",
            supabase_service_role_key=FAKE_KEY,
        )
        assert SupabaseRepository(s)._rest == f"{FAKE_URL}/rest/v1"


# --------------------------------------------------------------------------- #
# Reading
# --------------------------------------------------------------------------- #


class TestGetPaper:
    def test_maps_a_postgrest_row_onto_the_detail_model(self, _patch_client) -> None:
        mock(_patch_client, lambda r: json_response([PAPER_ROW]))
        paper = run(repo().get_paper("11111111-1111-1111-1111-111111111111"))
        assert paper.title == "Attention Paper"
        assert paper.page_count == 15
        assert paper.summary is not None
        assert len(paper.research_gaps.identified_gaps) == 2
        assert paper.model_used == "gemini-3.7-flash"

    def test_parses_both_timestamp_forms_postgres_returns(self, _patch_client) -> None:
        """created_at arrives with an offset, updated_at with a Z suffix."""
        mock(_patch_client, lambda r: json_response([PAPER_ROW]))
        paper = run(repo().get_paper("x"))
        assert paper.created_at.year == 2026
        assert paper.updated_at.tzinfo is not None

    def test_an_empty_result_is_not_found_rather_than_a_crash(self, _patch_client) -> None:
        mock(_patch_client, lambda r: json_response([]))
        with pytest.raises(NotFoundError):
            run(repo().get_paper("missing"))

    def test_requests_the_analysis_in_the_same_round_trip(self, _patch_client) -> None:
        """A second query per paper would make the library slower the more it
        is used."""
        seen = mock(_patch_client, lambda r: json_response([PAPER_ROW]))
        run(repo().get_paper("abc"))
        assert len(seen) == 1
        assert "analyses(" in seen[0].url.params["select"]
        assert seen[0].url.params["id"] == "eq.abc"


class TestListPapers:
    def _ok(self, rows, total):
        return lambda r: json_response(
            rows, headers={"content-range": f"0-{max(len(rows) - 1, 0)}/{total}"}
        )

    def test_reads_the_total_from_the_content_range_header(self, _patch_client) -> None:
        """The total is what lets the interface say "12 of 40" honestly."""
        mock(_patch_client, self._ok([PAPER_ROW], 40))
        items, total = run(repo().list_papers(limit=1))
        assert len(items) == 1
        assert total == 40

    def test_asks_postgrest_for_an_exact_count(self, _patch_client) -> None:
        seen = mock(_patch_client, self._ok([PAPER_ROW], 1))
        run(repo().list_papers())
        assert seen[0].headers["prefer"] == "count=exact"

    @pytest.mark.parametrize(
        ("sort", "expected"),
        [
            (SortOrder.NEWEST, "created_at.desc"),
            (SortOrder.OLDEST, "created_at.asc"),
            (SortOrder.TITLE, "title.asc"),
        ],
    )
    def test_each_sort_maps_to_its_order_clause(self, _patch_client, sort, expected) -> None:
        seen = mock(_patch_client, self._ok([], 0))
        run(repo().list_papers(sort=sort))
        assert seen[0].url.params["order"] == expected

    def test_status_filter_is_sent_as_an_equality(self, _patch_client) -> None:
        seen = mock(_patch_client, self._ok([], 0))
        run(repo().list_papers(status="ready"))
        assert seen[0].url.params["status"] == "eq.ready"

    def test_search_becomes_an_or_across_title_and_filename(self, _patch_client) -> None:
        seen = mock(_patch_client, self._ok([], 0))
        run(repo().list_papers(search="attention"))
        clause = seen[0].url.params["or"]
        assert "title.ilike.*attention*" in clause
        assert "filename.ilike.*attention*" in clause

    def test_reserved_postgrest_characters_are_stripped_from_a_search(self, _patch_client) -> None:
        """PostgREST reserves , . : ( ) inside a filter value. Left in, a search
        for "et al., 2019" is a syntax error at best and an injected filter at
        worst.

        The assertion targets the search TERM specifically, between the ilike
        wildcards. The surrounding clause is allowed to contain those same
        characters, because there they are PostgREST's own syntax.
        """
        seen = mock(_patch_client, self._ok([], 0))
        run(repo().list_papers(search="et al., 2019 (draft):"))
        clause = seen[0].url.params["or"]

        term = clause.split("title.ilike.*", 1)[1].split("*", 1)[0]
        assert term == "et al 2019 draft"
        for reserved in ",.:()":
            assert reserved not in term

    def test_a_search_of_only_reserved_characters_sends_no_filter(self, _patch_client) -> None:
        seen = mock(_patch_client, self._ok([], 0))
        run(repo().list_papers(search="...,,,"))
        assert "or" not in seen[0].url.params

    def test_a_gap_count_is_omitted_when_the_analysis_had_insufficient_evidence(
        self, _patch_client
    ) -> None:
        """Zero would read as "we looked and found none", a stronger claim than
        "we could not support an answer"."""
        row = json.loads(json.dumps(PAPER_ROW))
        row["analyses"][0]["research_gaps"]["insufficient_evidence"] = True
        mock(_patch_client, self._ok([row], 1))
        items, _ = run(repo().list_papers())
        assert items[0].gap_count is None

    def test_a_paper_with_no_analysis_is_listed_without_one(self, _patch_client) -> None:
        row = json.loads(json.dumps(PAPER_ROW))
        row["analyses"] = []
        mock(_patch_client, self._ok([row], 1))
        items, _ = run(repo().list_papers())
        assert items[0].has_analysis is False
        assert items[0].gap_count is None


# --------------------------------------------------------------------------- #
# Writing
# --------------------------------------------------------------------------- #


class TestSavePaper:
    def test_writes_the_paper_then_its_analysis(self, _patch_client) -> None:
        def handler(request: httpx.Request) -> httpx.Response:
            if request.method == "POST" and request.url.path.endswith("/papers"):
                return json_response([{"id": "new-id"}], status=201)
            if request.method == "POST" and request.url.path.endswith("/analyses"):
                return json_response([{"id": "analysis-id"}], status=201)
            return json_response([PAPER_ROW])

        seen = mock(_patch_client, handler)
        run(repo().save_paper(save_request()))

        paths = [r.url.path for r in seen]
        assert paths[0].endswith("/papers")
        assert paths[1].endswith("/analyses")

        paper_body = json.loads(seen[0].content)
        assert paper_body["title"] == "Attention Paper"
        assert paper_body["status"] == "ready"
        assert paper_body["page_count"] == 15

        analysis_body = json.loads(seen[1].content)
        assert analysis_body["paper_id"] == "new-id"
        assert analysis_body["model_used"] == "gemini-3.7-flash"
        assert analysis_body["summary"]["research_problem"]

    def test_a_failed_analysis_write_rolls_the_paper_back(self, _patch_client) -> None:
        """A paper row with no analysis is a half-saved record the user would
        see as a broken library entry."""

        def handler(request: httpx.Request) -> httpx.Response:
            if request.url.path.endswith("/analyses"):
                return json_response({"message": "boom", "code": "XX000"}, status=400)
            if request.method == "DELETE":
                return json_response([{"id": "new-id"}])
            return json_response([{"id": "new-id"}], status=201)

        seen = mock(_patch_client, handler)
        with pytest.raises(RepositoryError):
            run(repo().save_paper(save_request()))

        deletes = [r for r in seen if r.method == "DELETE"]
        assert len(deletes) == 1
        assert deletes[0].url.params["id"] == "eq.new-id"


class TestDeletePaper:
    def test_deletes_by_id(self, _patch_client) -> None:
        seen = mock(_patch_client, lambda r: json_response([{"id": "abc"}]))
        assert run(repo().delete_paper("abc")) is True
        assert seen[0].method == "DELETE"
        assert seen[0].url.params["id"] == "eq.abc"

    def test_deleting_nothing_is_not_found(self, _patch_client) -> None:
        """PostgREST returns 200 with an empty list when the filter matched no
        rows, so success alone does not mean something was deleted."""
        mock(_patch_client, lambda r: json_response([]))
        with pytest.raises(NotFoundError):
            run(repo().delete_paper("ghost"))

    def test_a_foreign_key_violation_becomes_a_conflict(self, _patch_client) -> None:
        """23503 is the ON DELETE RESTRICT from migration 002 firing: a saved
        review was built from this paper."""
        mock(
            _patch_client,
            lambda r: json_response(
                {"message": "violates foreign key constraint", "code": "23503"},
                status=409,
            ),
        )
        with pytest.raises(ConflictError) as exc:
            run(repo().delete_paper("abc"))
        assert "review" in str(exc.value).lower()


class TestPapersForReview:
    def test_preserves_the_order_the_user_selected(self, _patch_client) -> None:
        second = json.loads(json.dumps(PAPER_ROW))
        second["id"] = "22222222-2222-2222-2222-222222222222"
        second["title"] = "Second Paper"
        # PostgREST returns rows in its own order, not the order asked for.
        mock(_patch_client, lambda r: json_response([second, PAPER_ROW]))
        papers = run(
            repo().get_papers_for_review(["11111111-1111-1111-1111-111111111111", second["id"]])
        )
        assert [p.title for p in papers] == ["Attention Paper", "Second Paper"]

    def test_a_missing_paper_fails_rather_than_returning_fewer(self, _patch_client) -> None:
        """A review claiming five sources must not be built from four."""
        mock(_patch_client, lambda r: json_response([PAPER_ROW]))
        with pytest.raises(NotFoundError):
            run(repo().get_papers_for_review(["11111111-1111-1111-1111-111111111111", "missing"]))


class TestSaveReview:
    def test_writes_the_review_then_its_paper_links(self, _patch_client) -> None:
        review_row = {
            "id": "rev-1",
            "title": "A review",
            "model_used": "gemini-3.7-flash",
            "content": ANALYSIS_JSON["literature_review"],
            "paper_count": 2,
            "created_at": "2026-09-01T10:00:00Z",
            "literature_review_papers": [
                {"position": 0, "papers": {"id": "p1", "title": "One", "filename": "1.pdf"}},
                {"position": 1, "papers": {"id": "p2", "title": "Two", "filename": "2.pdf"}},
            ],
        }

        def handler(request: httpx.Request) -> httpx.Response:
            if request.method == "POST" and request.url.path.endswith("/literature_reviews"):
                return json_response([{"id": "rev-1"}], status=201)
            if request.url.path.endswith("/literature_review_papers"):
                return json_response([{}, {}], status=201)
            return json_response([review_row])

        seen = mock(_patch_client, handler)
        record = run(
            repo().save_review(
                title="A review",
                model_used="gemini-3.7-flash",
                content=LiteratureReview.model_validate(ANALYSIS_JSON["literature_review"]),
                paper_ids=["p1", "p2"],
            )
        )

        links = json.loads(seen[1].content)
        assert [link["paper_id"] for link in links] == ["p1", "p2"]
        assert [link["position"] for link in links] == [0, 1]
        assert record.paper_count == 2
        assert [p.title for p in record.papers] == ["One", "Two"]

    def test_a_failed_link_write_rolls_the_review_back(self, _patch_client) -> None:
        """A review that cannot name its sources must not be kept: the interface
        would show "based on N papers" with nothing behind it."""

        def handler(request: httpx.Request) -> httpx.Response:
            if request.url.path.endswith("/literature_review_papers"):
                return json_response({"message": "boom", "code": "XX000"}, status=400)
            if request.method == "DELETE":
                return json_response([{"id": "rev-1"}])
            return json_response([{"id": "rev-1"}], status=201)

        seen = mock(_patch_client, handler)
        with pytest.raises(RepositoryError):
            run(
                repo().save_review(
                    title="A review",
                    model_used="m",
                    content=LiteratureReview.model_validate(ANALYSIS_JSON["literature_review"]),
                    paper_ids=["p1"],
                )
            )
        assert any(r.method == "DELETE" for r in seen)

    def test_the_reported_paper_count_follows_the_links_not_the_counter(
        self, _patch_client
    ) -> None:
        """The stored counter could drift. The figure the interface prints must
        never outrun the evidence behind it."""
        review_row = {
            "id": "rev-1",
            "title": "A review",
            "model_used": "m",
            "content": ANALYSIS_JSON["literature_review"],
            "paper_count": 99,  # deliberately wrong
            "created_at": "2026-09-01T10:00:00Z",
            "literature_review_papers": [
                {"position": 0, "papers": {"id": "p1", "title": "One", "filename": "1.pdf"}},
            ],
        }
        mock(_patch_client, lambda r: json_response([review_row]))
        record = run(repo().get_review("rev-1"))
        assert record.paper_count == 1


# --------------------------------------------------------------------------- #
# Stats and failures
# --------------------------------------------------------------------------- #


class TestStats:
    def test_counts_come_from_content_range_not_from_payloads(self, _patch_client) -> None:
        def handler(request: httpx.Request) -> httpx.Response:
            table = request.url.path.rsplit("/", 1)[-1]
            totals = {"papers": 7, "analyses": 5, "literature_reviews": 2}
            if table in totals and request.url.params.get("limit") == "1":
                return json_response(
                    [{"id": "x"}], headers={"content-range": f"0-0/{totals[table]}"}
                )
            return json_response([ANALYSIS_JSON])

        mock(_patch_client, handler)
        stats = run(repo().stats())
        assert stats.saved_papers == 7
        assert stats.papers_analysed == 5
        assert stats.literature_reviews == 2
        assert stats.research_gaps_found == 2


class TestFailureTranslation:
    @pytest.mark.parametrize("status", [401, 403])
    def test_a_rejected_key_is_unavailable_and_never_echoes_the_key(
        self, _patch_client, status
    ) -> None:
        mock(
            _patch_client,
            lambda r: json_response({"message": "bad key", "code": "PGRST301"}, status),
        )
        with pytest.raises(RepositoryUnavailableError) as exc:
            run(repo().get_paper("abc"))
        message = str(exc.value)
        assert "SUPABASE_SERVICE_ROLE_KEY" in message
        assert FAKE_KEY not in message

    def test_a_server_error_is_unavailable(self, _patch_client) -> None:
        mock(_patch_client, lambda r: httpx.Response(500, text="upstream down"))
        with pytest.raises(RepositoryUnavailableError):
            run(repo().get_paper("abc"))

    def test_a_timeout_is_reported_as_unavailable(self, _patch_client) -> None:
        def handler(request: httpx.Request) -> httpx.Response:
            raise httpx.ReadTimeout("too slow", request=request)

        mock(_patch_client, handler)
        with pytest.raises(RepositoryUnavailableError) as exc:
            run(repo().get_paper("abc"))
        assert "did not respond" in str(exc.value)

    def test_a_connection_failure_is_reported_as_unavailable(self, _patch_client) -> None:
        def handler(request: httpx.Request) -> httpx.Response:
            raise httpx.ConnectError("no route", request=request)

        mock(_patch_client, handler)
        with pytest.raises(RepositoryUnavailableError) as exc:
            run(repo().get_paper("abc"))
        assert "reach" in str(exc.value).lower()

    def test_a_non_json_error_body_still_raises_cleanly(self, _patch_client) -> None:
        mock(_patch_client, lambda r: httpx.Response(400, text="<html>nope</html>"))
        with pytest.raises(RepositoryError) as exc:
            run(repo().get_paper("abc"))
        assert "<html>" not in str(exc.value)

    def test_health_reports_false_instead_of_raising(self, _patch_client) -> None:
        """Health must never throw: it is called to find out whether things are
        broken."""

        def handler(request: httpx.Request) -> httpx.Response:
            raise httpx.ConnectError("no route", request=request)

        mock(_patch_client, handler)
        assert run(repo().health()) is False

    def test_health_reports_true_when_reachable(self, _patch_client) -> None:
        mock(_patch_client, lambda r: json_response([]))
        assert run(repo().health()) is True
