"""Supabase implementation of `PaperRepository`, over PostgREST.

This file is the ONLY place Supabase or PostgREST details appear.

WHY HTTPX AND NOT THE supabase-py SDK
-------------------------------------
The SDK is a large dependency that mostly wraps the same REST calls this
file makes, and the deployed function is already carrying two model SDKs.
PostgREST is a small, stable, documented HTTP surface; using it directly
costs about a hundred lines and removes a dependency from the bundle.
httpx is already present (the Gemini SDK requires it) and is pinned
explicitly in requirements.txt because this module imports it directly.

SECURITY
--------
Every request here is authenticated with the SERVICE-ROLE key, which
bypasses Row Level Security. That is the correct posture for a trusted
backend and a catastrophic one for a browser, so the key is read from
settings, sent only in a request header, and never returned, logged, or
included in an error message - `_translate` deliberately reports status
codes and PostgREST's own message, never the request headers.
"""

import logging
from datetime import UTC, datetime
from typing import Any

import httpx

from src.config import Settings
from src.db.repository import (
    ConflictError,
    NotFoundError,
    PaperRepository,
    RepositoryError,
    RepositoryUnavailableError,
)
from src.schemas.analysis import LiteratureReview, ResearchGaps, Summary
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

logger = logging.getLogger(__name__)

# PostgREST maps sort choices onto order clauses. Confining the mapping
# here is what keeps `SortOrder` a product concept rather than a database
# one - and, because the API only ever passes an enum member, it also
# means no caller-supplied string can reach the query string.
_ORDER_BY: dict[SortOrder, str] = {
    SortOrder.NEWEST: "created_at.desc",
    SortOrder.OLDEST: "created_at.asc",
    SortOrder.TITLE: "title.asc",
}


def _parse_ts(value: Any) -> datetime:
    """Postgres timestamptz -> aware datetime, tolerant of the Z suffix."""
    if isinstance(value, datetime):
        return value
    if isinstance(value, str):
        try:
            return datetime.fromisoformat(value.replace("Z", "+00:00"))
        except ValueError:
            pass
    # A row that reached us without a timestamp is a bug in the migration,
    # not something to crash a whole library listing over.
    return datetime.now(UTC)


class SupabaseRepository(PaperRepository):
    """The research library, stored in Supabase Postgres."""

    def __init__(self, settings: Settings, timeout_seconds: float = 20.0) -> None:
        if not settings.has_database:
            raise RepositoryUnavailableError(
                "The research library is not connected. Set SUPABASE_URL and "
                "SUPABASE_SERVICE_ROLE_KEY on the server to enable saving papers."
            )
        self._rest = settings.supabase_rest_url
        self._timeout = timeout_seconds
        key = settings.supabase_service_role_key.strip()
        self._headers = {
            "apikey": key,
            "Authorization": f"Bearer {key}",
            "Content-Type": "application/json",
            # Ask PostgREST to return the rows it wrote, so a save needs
            # one round trip rather than a write followed by a read.
            "Prefer": "return=representation",
        }

    # ---------- plumbing ----------

    @staticmethod
    def _translate(exc: Exception) -> RepositoryError:
        """Driver exception -> project-owned error, with no secrets attached."""
        if isinstance(exc, httpx.TimeoutException):
            return RepositoryUnavailableError(
                "The research library did not respond in time. Please try again."
            )
        if isinstance(exc, httpx.RequestError):
            return RepositoryUnavailableError("Could not reach the research library.")
        return RepositoryError("The research library could not complete that request.")

    def _check(self, response: httpx.Response) -> None:
        """Raise a typed error for a non-2xx PostgREST reply."""
        if response.is_success:
            return

        # PostgREST returns a JSON body with `message` and `code`. The
        # code is what distinguishes "you cannot delete this" from a
        # generic failure, so it is read rather than guessed at from text.
        detail = ""
        code = ""
        try:
            body = response.json()
            detail = str(body.get("message") or "")
            code = str(body.get("code") or "")
        except Exception:  # noqa: BLE001 - a non-JSON error body is still an error
            pass

        if response.status_code in (401, 403):
            # Never echo the key or the header. Name the variable instead.
            raise RepositoryUnavailableError(
                "The research library rejected the server's credentials. "
                "Check SUPABASE_SERVICE_ROLE_KEY."
            )
        if response.status_code == 404:
            raise NotFoundError("That record was not found.")
        # 23503 = foreign key violation: the ON DELETE RESTRICT in 002.
        if code == "23503" or response.status_code == 409:
            raise ConflictError(
                "This paper is part of a saved literature review. Delete the "
                "review first, and the paper can then be removed."
            )
        if response.status_code >= 500:
            raise RepositoryUnavailableError("The research library is temporarily unavailable.")
        logger.warning("library request failed: %s %s", response.status_code, code)
        raise RepositoryError(detail or "The request was rejected by the library.")

    async def _request(self, method: str, path: str, **kwargs: Any) -> httpx.Response:
        try:
            async with httpx.AsyncClient(timeout=self._timeout) as client:
                response = await client.request(
                    method, f"{self._rest}{path}", headers=self._headers, **kwargs
                )
        except Exception as exc:
            raise self._translate(exc) from exc
        self._check(response)
        return response

    async def health(self) -> bool:
        try:
            await self._request("GET", "/papers", params={"select": "id", "limit": 1})
            return True
        except Exception:  # noqa: BLE001 - health must never raise
            return False

    # ---------- row mapping ----------

    @staticmethod
    def _list_item(row: dict[str, Any]) -> PaperListItem:
        analyses = row.get("analyses") or []
        analysis = analyses[0] if analyses else None

        gap_count: int | None = None
        if analysis:
            gaps = analysis.get("research_gaps") or {}
            # A gap analysis the model could not support reports no count
            # rather than zero: zero would read as "we looked and found
            # none", which is a different and stronger claim.
            if not gaps.get("insufficient_evidence"):
                gap_count = len(gaps.get("identified_gaps") or [])

        return PaperListItem(
            id=str(row["id"]),
            title=row.get("title") or row.get("filename") or "Untitled",
            filename=row.get("filename") or "",
            status=PaperStatus(row.get("status") or "ready"),
            page_count=row.get("page_count"),
            file_size_bytes=row.get("file_size_bytes"),
            created_at=_parse_ts(row.get("created_at")),
            updated_at=_parse_ts(row.get("updated_at")),
            has_analysis=analysis is not None,
            gap_count=gap_count,
        )

    @staticmethod
    def _detail(row: dict[str, Any]) -> PaperDetail:
        analyses = row.get("analyses") or []
        analysis = analyses[0] if analyses else None

        return PaperDetail(
            id=str(row["id"]),
            title=row.get("title") or row.get("filename") or "Untitled",
            filename=row.get("filename") or "",
            status=PaperStatus(row.get("status") or "ready"),
            page_count=row.get("page_count"),
            extracted_characters=row.get("extracted_characters"),
            file_size_bytes=row.get("file_size_bytes"),
            content_type=row.get("content_type"),
            created_at=_parse_ts(row.get("created_at")),
            updated_at=_parse_ts(row.get("updated_at")),
            # Validated on the way out as well as in. The column is jsonb,
            # so nothing but this stops a hand-edited row from reaching
            # the frontend in a shape it cannot render.
            summary=Summary.model_validate(analysis["summary"]) if analysis else None,
            research_gaps=(
                ResearchGaps.model_validate(analysis["research_gaps"]) if analysis else None
            ),
            literature_review=(
                LiteratureReview.model_validate(analysis["literature_review"]) if analysis else None
            ),
            model_used=analysis.get("model_used") if analysis else None,
            chunk_count=analysis.get("chunk_count") if analysis else None,
            truncated=analysis.get("truncated") if analysis else None,
        )

    # PostgREST embeds the related analysis in one round trip. Ordering by
    # created_at desc and limiting to 1 gives the most recent analysis per
    # paper without a second query per row.
    _ANALYSIS_EMBED = (
        "analyses(model_used,summary,research_gaps,literature_review,"
        "chunk_count,truncated,created_at.desc.limit.1)"
    )
    _PAPER_COLUMNS = (
        "id,title,filename,status,page_count,extracted_characters,"
        "file_size_bytes,content_type,created_at,updated_at"
    )

    # ---------- papers ----------

    async def save_paper(self, request: SavePaperRequest) -> PaperDetail:
        doc = request.document
        paper_payload = {
            "title": request.title.strip() or request.filename,
            "filename": request.filename,
            "file_size_bytes": request.file_size_bytes,
            "content_type": request.content_type,
            "page_count": doc.page_count,
            "extracted_characters": doc.extracted_characters,
            "status": PaperStatus.READY.value,
        }
        response = await self._request("POST", "/papers", json=paper_payload)
        rows = response.json()
        if not rows:
            raise RepositoryError("The library did not confirm the saved paper.")
        paper_id = str(rows[0]["id"])

        analysis_payload = {
            "paper_id": paper_id,
            "model_used": request.model_used,
            "summary": request.summary.model_dump(),
            "research_gaps": request.research_gaps.model_dump(),
            "literature_review": request.literature_review.model_dump(),
            "chunk_count": doc.chunk_count,
            "truncated": doc.truncated,
        }
        try:
            await self._request("POST", "/analyses", json=analysis_payload)
        except RepositoryError:
            # A paper row with no analysis is a half-saved record the user
            # would see as a broken library entry. Roll it back so the
            # save either happened or did not.
            try:
                await self._request("DELETE", "/papers", params={"id": f"eq.{paper_id}"})
            except RepositoryError:
                logger.error("could not roll back paper %s after analysis save", paper_id)
            raise

        return await self.get_paper(paper_id)

    async def list_papers(
        self,
        *,
        search: str | None = None,
        status: str | None = None,
        sort: SortOrder = SortOrder.NEWEST,
        limit: int = 50,
        offset: int = 0,
    ) -> tuple[list[PaperListItem], int]:
        params: dict[str, Any] = {
            "select": f"{self._PAPER_COLUMNS},{self._ANALYSIS_EMBED}",
            "order": _ORDER_BY.get(sort, _ORDER_BY[SortOrder.NEWEST]),
            "limit": limit,
            "offset": offset,
        }
        if status:
            params["status"] = f"eq.{status}"
        if search:
            # PostgREST reserves , . : ( ) in filter values. Stripping them
            # keeps a search for "et al., 2019" a search rather than a
            # syntax error or an injected filter.
            term = search.strip().translate(str.maketrans("", "", ",.:()*"))
            if term:
                params["or"] = f"(title.ilike.*{term}*,filename.ilike.*{term}*)"

        # `count=exact` returns the total in Content-Range, so one request
        # answers both "this page" and "how many altogether".
        headers = {**self._headers, "Prefer": "count=exact"}
        try:
            async with httpx.AsyncClient(timeout=self._timeout) as client:
                response = await client.get(f"{self._rest}/papers", headers=headers, params=params)
        except Exception as exc:
            raise self._translate(exc) from exc
        self._check(response)

        total = 0
        content_range = response.headers.get("content-range", "")
        if "/" in content_range:
            tail = content_range.split("/")[-1]
            if tail.isdigit():
                total = int(tail)

        items = [self._list_item(row) for row in response.json()]
        return items, total or len(items)

    async def get_paper(self, paper_id: str) -> PaperDetail:
        response = await self._request(
            "GET",
            "/papers",
            params={
                "select": f"{self._PAPER_COLUMNS},{self._ANALYSIS_EMBED}",
                "id": f"eq.{paper_id}",
                "limit": 1,
            },
        )
        rows = response.json()
        if not rows:
            raise NotFoundError("That paper is not in your library.")
        return self._detail(rows[0])

    async def delete_paper(self, paper_id: str) -> bool:
        response = await self._request("DELETE", "/papers", params={"id": f"eq.{paper_id}"})
        rows = response.json() if response.content else []
        if not rows:
            raise NotFoundError("That paper is not in your library.")
        return True

    async def get_papers_for_review(self, paper_ids: list[str]) -> list[PaperDetail]:
        if not paper_ids:
            return []
        id_list = ",".join(paper_ids)
        response = await self._request(
            "GET",
            "/papers",
            params={
                "select": f"{self._PAPER_COLUMNS},{self._ANALYSIS_EMBED}",
                "id": f"in.({id_list})",
            },
        )
        found = {str(row["id"]): row for row in response.json()}
        missing = [pid for pid in paper_ids if pid not in found]
        if missing:
            raise NotFoundError(f"{len(missing)} selected paper(s) are no longer in your library.")
        # Returned in the order the user selected, not the order Postgres
        # happened to return.
        return [self._detail(found[pid]) for pid in paper_ids]

    # ---------- literature reviews ----------

    async def save_review(
        self,
        *,
        title: str,
        model_used: str,
        content: LiteratureReview,
        paper_ids: list[str],
    ) -> ReviewRecord:
        response = await self._request(
            "POST",
            "/literature_reviews",
            json={
                "title": title,
                "model_used": model_used,
                "content": content.model_dump(),
                "paper_count": len(paper_ids),
            },
        )
        rows = response.json()
        if not rows:
            raise RepositoryError("The library did not confirm the saved review.")
        review_id = str(rows[0]["id"])

        links = [
            {"review_id": review_id, "paper_id": pid, "position": i}
            for i, pid in enumerate(paper_ids)
        ]
        try:
            await self._request("POST", "/literature_review_papers", json=links)
        except RepositoryError:
            # A review that cannot name its sources must not be kept: the
            # UI would show "based on N papers" with nothing behind it.
            try:
                await self._request(
                    "DELETE", "/literature_reviews", params={"id": f"eq.{review_id}"}
                )
            except RepositoryError:
                logger.error("could not roll back review %s", review_id)
            raise

        return await self.get_review(review_id)

    _REVIEW_SELECT = (
        "id,title,model_used,content,paper_count,created_at,"
        "literature_review_papers(position,papers(id,title,filename))"
    )

    @staticmethod
    def _review(row: dict[str, Any]) -> ReviewRecord:
        links = row.get("literature_review_papers") or []
        links = sorted(links, key=lambda link: link.get("position") or 0)
        papers: list[ReviewPaperRef] = []
        for link in links:
            paper = link.get("papers")
            if not paper:
                continue
            papers.append(
                ReviewPaperRef(
                    id=str(paper["id"]),
                    title=paper.get("title") or paper.get("filename") or "Untitled",
                    filename=paper.get("filename") or "",
                )
            )
        return ReviewRecord(
            id=str(row["id"]),
            title=row.get("title") or "Literature review",
            model_used=row.get("model_used") or "",
            content=LiteratureReview.model_validate(row["content"]),
            # Report the papers actually linked, not the stored counter,
            # so the figure the UI prints can never outrun the evidence.
            paper_count=len(papers) or int(row.get("paper_count") or 0),
            papers=papers,
            created_at=_parse_ts(row.get("created_at")),
        )

    async def list_reviews(self, *, limit: int = 50) -> tuple[list[ReviewRecord], int]:
        response = await self._request(
            "GET",
            "/literature_reviews",
            params={
                "select": self._REVIEW_SELECT,
                "order": "created_at.desc",
                "limit": limit,
            },
        )
        reviews = [self._review(row) for row in response.json()]
        return reviews, len(reviews)

    async def get_review(self, review_id: str) -> ReviewRecord:
        response = await self._request(
            "GET",
            "/literature_reviews",
            params={
                "select": self._REVIEW_SELECT,
                "id": f"eq.{review_id}",
                "limit": 1,
            },
        )
        rows = response.json()
        if not rows:
            raise NotFoundError("That literature review was not found.")
        return self._review(rows[0])

    async def delete_review(self, review_id: str) -> bool:
        response = await self._request(
            "DELETE", "/literature_reviews", params={"id": f"eq.{review_id}"}
        )
        rows = response.json() if response.content else []
        if not rows:
            raise NotFoundError("That literature review was not found.")
        return True

    # ---------- dashboard ----------

    async def _count(self, table: str, params: dict[str, Any] | None = None) -> int:
        """Count rows without transferring them.

        `limit=1` with `count=exact` asks PostgREST for the total in the
        Content-Range header and one row of payload, rather than the
        whole table just to call len() on it.
        """
        headers = {**self._headers, "Prefer": "count=exact"}
        query: dict[str, Any] = {"select": "id", "limit": 1, **(params or {})}
        try:
            async with httpx.AsyncClient(timeout=self._timeout) as client:
                response = await client.get(f"{self._rest}/{table}", headers=headers, params=query)
        except Exception as exc:
            raise self._translate(exc) from exc
        self._check(response)
        content_range = response.headers.get("content-range", "")
        tail = content_range.split("/")[-1] if "/" in content_range else ""
        return int(tail) if tail.isdigit() else 0

    async def stats(self) -> LibraryStats:
        saved_papers = await self._count("papers")
        papers_analysed = await self._count("analyses")
        reviews = await self._count("literature_reviews")

        # Gaps are counted from the stored analyses rather than kept in a
        # counter column, so the figure cannot drift away from the data
        # it claims to describe.
        response = await self._request(
            "GET", "/analyses", params={"select": "research_gaps", "limit": 1000}
        )
        gaps_found = 0
        for row in response.json():
            gaps = row.get("research_gaps") or {}
            if not gaps.get("insufficient_evidence"):
                gaps_found += len(gaps.get("identified_gaps") or [])

        return LibraryStats(
            papers_analysed=papers_analysed,
            research_gaps_found=gaps_found,
            literature_reviews=reviews,
            saved_papers=saved_papers,
        )
