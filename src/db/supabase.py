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

SECURITY: WHO THESE REQUESTS ARE MADE AS
----------------------------------------
Every request here is made as **the signed-in user**, not as the server.
The `apikey` header carries the project's public key (which only routes
the request to the right project) and `Authorization` carries that user's
own access token. Postgres therefore evaluates `auth.uid()` as that
person, and the Row Level Security policies from migration 002 filter
every read and every write.

This is deliberately NOT the service-role key. A service key bypasses RLS
entirely, which would leave user isolation resting on this file
remembering to add `user_id = ...` to every query it will ever contain -
one forgotten filter, one new endpoint, and User A sees User B's papers.
Handing PostgREST the caller's token instead makes the DATABASE the thing
that enforces ownership, so a missing filter yields nothing rather than
everything.

The practical consequence, and it is intentional: an unauthenticated
request reads zero rows, because `user_id = auth.uid()` is never true
when `auth.uid()` is NULL. Nothing in this codebase can opt out of that.

No key and no token is ever returned, logged, or included in an error
message - `_translate` reports status codes and PostgREST's own message,
never the request headers.
"""

import logging
from datetime import UTC, datetime
from typing import Any

import httpx

from src.config import Settings
from src.db.repository import (
    AuthExpiredError,
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


class _SchemaBehindError(RepositoryError):
    """A column this code asks for does not exist in the database yet.

    Internal to this module. Raised when PostgREST reports 42703
    (undefined_column), which happens in the window between deploying code that
    reads a new column and running the migration that adds it.
    """


# Whether the database has migration 004's provenance columns on `analyses`.
#
# MODULE level, not per-instance: a repository is built per request, so an
# instance flag would re-learn the same fact on every single call. This is
# discovered once per warm process and then costs nothing.
#
# It starts optimistic and is only ever turned OFF. The failure it guards
# against is one-directional - a column cannot un-exist during a process's
# lifetime - and a serverless cold start re-learns it anyway, so a deploy that
# follows the migration picks the columns up without anyone doing anything.
_PROVENANCE_COLUMNS_PRESENT = True

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

    def __init__(
        self,
        settings: Settings,
        access_token: str,
        user_id: str,
        timeout_seconds: float = 20.0,
    ) -> None:
        """Open the library AS ONE USER.

        `access_token` is that user's Supabase JWT. It is required, with no
        default: an optional token would make "no token" a silent, valid state
        whose queries return an empty library rather than an error, which is
        the exact failure mode the publishable-key guard below exists to catch.

        `user_id` is the same person's id, written onto every row this
        repository creates. Migration 003 also defaults the column to
        `auth.uid()`, so this is belt and braces rather than the only
        safeguard - and it is the belt, not the braces: if the two ever
        disagreed, the `WITH CHECK (user_id = auth.uid())` policy refuses the
        write instead of storing a row under the wrong owner.
        """
        if not settings.has_database:
            if settings.supabase_key_is_publishable:
                # Deliberately refused rather than attempted. This key WOULD
                # connect, and would then read zero rows through RLS forever,
                # which looks like an empty library rather than a broken one.
                raise RepositoryUnavailableError(
                    "SUPABASE_SERVICE_ROLE_KEY holds a Supabase publishable "
                    "key. That is a public browser key and cannot bypass Row "
                    "Level Security, so it would read an empty library and "
                    "fail every write. The project's secret server-side key "
                    "is required."
                )
            raise RepositoryUnavailableError(
                "The research library is not connected. Set SUPABASE_URL and "
                "SUPABASE_SERVICE_ROLE_KEY on the server to enable saving papers."
            )
        if not settings.supabase_anon_key.strip():
            # The public key is what PostgREST requires in `apikey`. Without
            # it there is no way to make a request as the user at all, and
            # falling back to the service key would silently disable RLS -
            # turning a configuration gap into a data leak.
            raise RepositoryUnavailableError(
                "The research library is not connected. SUPABASE_ANON_KEY must "
                "be set on the server so each request can be made as the "
                "signed-in user."
            )
        token = access_token.strip()
        if not token:
            raise RepositoryUnavailableError(
                "The research library can only be opened for a signed-in user."
            )

        self._rest = settings.supabase_rest_url
        self._timeout = timeout_seconds
        self._user_id = user_id.strip()
        self._headers = {
            # Public key: identifies the PROJECT.
            "apikey": settings.supabase_anon_key.strip(),
            # User token: identifies the PERSON. This is what makes
            # auth.uid() resolve, and therefore what makes RLS filter.
            "Authorization": f"Bearer {token}",
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
            # Requests are made with the USER'S token, so the overwhelmingly
            # likely cause is that the token aged out mid-session, not that
            # the server is misconfigured. Saying "check the server key" here
            # would send a person to fix something they cannot see and do not
            # own. Never echoes the key or the header either way.
            raise AuthExpiredError(
                "Your session has expired. Please sign in again to reach your library."
            )
        if response.status_code == 404:
            raise NotFoundError("That record was not found.")
        # 42703 = undefined_column. The code is ahead of the schema; the caller
        # retries with the older column list rather than failing the request.
        if code == "42703":
            raise _SchemaBehindError(detail or "A required column does not exist yet.")
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
        # A caller may override the headers wholesale (the settings upsert
        # needs a different `Prefer`). Popping it keeps the default path
        # allocation-free and makes the override explicit at the call site.
        headers = kwargs.pop("headers", None) or self._headers
        try:
            async with httpx.AsyncClient(timeout=self._timeout) as client:
                response = await client.request(
                    method, f"{self._rest}{path}", headers=headers, **kwargs
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
            model_provider=analysis.get("model_provider") if analysis else None,
            fallback_used=analysis.get("fallback_used") if analysis else None,
            fallback_provider=analysis.get("fallback_provider") if analysis else None,
            processing_time_ms=analysis.get("processing_time_ms") if analysis else None,
        )

    # PostgREST embeds the related analysis in one round trip, which is what
    # avoids a second query per row when the library lists thirty papers.
    #
    # Ordering and limiting an EMBEDDED resource is done with separate query
    # parameters, not inside the select parentheses. Writing
    # `analyses(...,created_at.desc.limit.1)` looks plausible and is rejected
    # by PostgREST with "failed to parse select parameter" - see
    # `_ANALYSIS_PARAMS`, which carries the ordering instead.
    # The columns every deployment has.
    _ANALYSIS_BASE = (
        "model_used,summary,research_gaps,literature_review,chunk_count,truncated,created_at"
    )
    # Added by migration 004. Requested only while we believe they exist.
    _ANALYSIS_PROVENANCE = "model_provider,fallback_used,fallback_provider,processing_time_ms"

    @staticmethod
    def _analysis_embed() -> str:
        """The `analyses(...)` embed, matched to what the database actually has.

        Asking PostgREST for a column that does not exist fails the WHOLE
        request with a 400, so this cannot simply always ask: deploying this
        code before running migration 004 would take the entire library offline
        rather than merely omitting four fields. `_detail` reads them with
        `.get()`, so their absence is already harmless once they are not asked
        for.
        """
        columns = SupabaseRepository._ANALYSIS_BASE
        if _PROVENANCE_COLUMNS_PRESENT:
            columns = f"{columns},{SupabaseRepository._ANALYSIS_PROVENANCE}"
        return f"analyses({columns})"

    async def _with_schema_fallback(self, attempt):
        """Run `attempt`, retrying once without the provenance columns.

        `attempt` is called with no arguments and reads the module flag through
        `_analysis_embed`, so the retry automatically asks for less.
        """
        global _PROVENANCE_COLUMNS_PRESENT
        try:
            return await attempt()
        except _SchemaBehindError:
            if not _PROVENANCE_COLUMNS_PRESENT:
                raise
            logger.warning(
                "the analyses table has no provenance columns; run migration "
                "004 to record which model produced each analysis. Continuing "
                "without them."
            )
            _PROVENANCE_COLUMNS_PRESENT = False
            return await attempt()

    # Most recent analysis per paper. `limit` on an embedded resource applies
    # per parent row, so this is one analysis each, not one across the page.
    _ANALYSIS_PARAMS = {
        "analyses.order": "created_at.desc",
        "analyses.limit": 1,
    }
    _PAPER_COLUMNS = (
        "id,title,filename,status,page_count,extracted_characters,"
        "file_size_bytes,content_type,created_at,updated_at"
    )

    # ---------- papers ----------

    async def save_paper(self, request: SavePaperRequest) -> PaperDetail:
        global _PROVENANCE_COLUMNS_PRESENT
        doc = request.document
        paper_payload = {
            "title": request.title.strip() or request.filename,
            "filename": request.filename,
            "file_size_bytes": request.file_size_bytes,
            "content_type": request.content_type,
            "page_count": doc.page_count,
            "extracted_characters": doc.extracted_characters,
            "status": PaperStatus.READY.value,
            # The owner, written explicitly. Migration 003 also defaults this
            # column to auth.uid(), and the RLS policy refuses any row where
            # the two disagree - so a paper can only ever be stored under the
            # person who uploaded it.
            "user_id": self._user_id,
        }
        response = await self._request("POST", "/papers", json=paper_payload)
        rows = response.json()
        if not rows:
            raise RepositoryError("The library did not confirm the saved paper.")
        paper_id = str(rows[0]["id"])

        analysis_payload = {
            "paper_id": paper_id,
            "user_id": self._user_id,
            "model_used": request.model_used,
            "summary": request.summary.model_dump(),
            "research_gaps": request.research_gaps.model_dump(),
            "literature_review": request.literature_review.model_dump(),
            "chunk_count": doc.chunk_count,
            "truncated": doc.truncated,
        }
        if _PROVENANCE_COLUMNS_PRESENT:
            # Provenance. Omitted entirely - not sent as NULL - when the
            # database predates migration 004, because PostgREST rejects an
            # INSERT naming a column that does not exist.
            analysis_payload.update(
                {
                    "model_provider": request.model_provider,
                    "fallback_used": request.fallback_used,
                    "fallback_provider": request.fallback_provider,
                    "processing_time_ms": request.processing_time_ms,
                }
            )
        try:
            try:
                await self._request("POST", "/analyses", json=analysis_payload)
            except _SchemaBehindError:
                # Migration 004 has not run. Drop the four provenance keys and
                # save the analysis itself, which matters far more than the
                # metadata about it.
                _PROVENANCE_COLUMNS_PRESENT = False
                logger.warning(
                    "saving without provenance columns; run migration 004 to "
                    "record which model produced each analysis"
                )
                for key in (
                    "model_provider",
                    "fallback_used",
                    "fallback_provider",
                    "processing_time_ms",
                ):
                    analysis_payload.pop(key, None)
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
        async def attempt() -> tuple[list[PaperListItem], int]:
            params: dict[str, Any] = {
                # Rebuilt inside `attempt` so a retry asks for fewer columns.
                "select": f"{self._PAPER_COLUMNS},{self._analysis_embed()}",
                "order": _ORDER_BY.get(sort, _ORDER_BY[SortOrder.NEWEST]),
                "limit": limit,
                "offset": offset,
                **self._ANALYSIS_PARAMS,
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
                    response = await client.get(
                        f"{self._rest}/papers", headers=headers, params=params
                    )
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

        return await self._with_schema_fallback(attempt)

    async def get_paper(self, paper_id: str) -> PaperDetail:
        async def attempt() -> PaperDetail:
            response = await self._request(
                "GET",
                "/papers",
                params={
                    "select": f"{self._PAPER_COLUMNS},{self._analysis_embed()}",
                    "id": f"eq.{paper_id}",
                    "limit": 1,
                    **self._ANALYSIS_PARAMS,
                },
            )
            rows = response.json()
            if not rows:
                raise NotFoundError("That paper is not in your library.")
            return self._detail(rows[0])

        return await self._with_schema_fallback(attempt)

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

        async def attempt() -> list[PaperDetail]:
            response = await self._request(
                "GET",
                "/papers",
                params={
                    "select": f"{self._PAPER_COLUMNS},{self._analysis_embed()}",
                    "id": f"in.({id_list})",
                    **self._ANALYSIS_PARAMS,
                },
            )
            found = {str(row["id"]): row for row in response.json()}
            missing = [pid for pid in paper_ids if pid not in found]
            if missing:
                raise NotFoundError(
                    f"{len(missing)} selected paper(s) are no longer in your library."
                )
            # Returned in the order the user selected, not the order Postgres
            # happened to return.
            return [self._detail(found[pid]) for pid in paper_ids]

        return await self._with_schema_fallback(attempt)

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
                "user_id": self._user_id,
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

    # ---------- global configuration ----------

    async def is_owner(self, user_id: str) -> bool:
        """Whether this account is listed in `app_owners`.

        The RLS policy on that table lets a user read ONLY their own row, so
        this query returns one row or none and cannot be used to enumerate the
        other owners.
        """
        response = await self._request(
            "GET",
            "/app_owners",
            params={"select": "user_id", "user_id": f"eq.{user_id}", "limit": 1},
        )
        return bool(response.json())

    async def get_active_provider(self, default: str) -> str:
        """The stored primary provider, or `default` when none is stored."""
        response = await self._request(
            "GET",
            "/system_settings",
            params={
                "select": "value",
                "key": "eq.active_ai_provider",
                "limit": 1,
            },
        )
        rows = response.json()
        if not rows:
            return default
        value = str(rows[0].get("value") or "").strip().lower()
        return value or default

    async def set_active_provider(self, provider: str, *, updated_by: str) -> None:
        """Upsert the primary provider.

        `resolution=merge-duplicates` makes this one round trip whether or not
        the row already exists. The database refuses the write outright if the
        caller is not an owner - the API layer checks too, but this is the
        check that holds even if the API layer is wrong.
        """
        await self._request(
            "POST",
            "/system_settings",
            headers={**self._headers, "Prefer": "resolution=merge-duplicates"},
            json={
                "key": "active_ai_provider",
                "value": provider,
                "updated_by": updated_by,
                "updated_at": datetime.now(UTC).isoformat(),
            },
        )
