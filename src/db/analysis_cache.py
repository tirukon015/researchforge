"""The same-paper analysis cache: reuse a result instead of paying for it twice.

WHAT IT DOES
------------
Analysing a paper costs three model calls. When two people upload the same
document, the second one can reuse the first result rather than buying the
same answer again.

WHY THIS DOES NOT LIVE IN `SupabaseRepository`
----------------------------------------------
That class is scoped to one signed-in user and reaches Postgres with that
user's own token, so Row Level Security filters everything it sees. That is
exactly right for a personal library, and exactly wrong here: the cache is
shared by construction, and giving it a per-user policy would either break
reuse or open the table to enumeration.

So this is a separate, deliberately tiny class with a different access model,
and keeping it separate is what stops the two from being confused.

⚠️ THE PRIVACY DESIGN, IN FULL
-------------------------------
`analysis_cache` has **no user column** and RLS enabled with **no policy**, so
no browser key can read or write it at all. This class reaches it with the
SERVICE-ROLE key, which never leaves the server.

That inverts the rule the rest of the codebase follows, and the reason is that
the alternative is worse. A read policy for authenticated users would let any
account enumerate the table and read the analysis of every paper anyone had
ever uploaded, including unpublished work. Server-only access means a cached
analysis can be obtained in exactly one way: by uploading a document whose
text hashes to that entry. **You can only get the analysis of a paper you
already have.**

The surface is two operations, both keyed by a hash the caller demonstrably
possesses, and neither returning anything about any user. Nothing here can
answer "who uploaded this" - the table cannot, because it does not record it.

WHAT NEVER ENTERS THE CACHE
---------------------------
Only a complete, schema-validated analysis. A rate limit, a timeout, a
provider outage, a malformed reply, a partial result: none are stored. A
cached failure would be served to every future upload of that paper, turning
one bad minute into a permanent wrong answer.
"""

import logging
from typing import Any

import httpx

from src.config import Settings
from src.schemas.analysis import AnalysisResponse, LiteratureReview, ResearchGaps, Summary

logger = logging.getLogger(__name__)


class CachedAnalysis:
    """A validated analysis retrieved from the cache."""

    __slots__ = (
        "summary",
        "research_gaps",
        "literature_review",
        "model_used",
        "model_provider",
        "fallback_used",
        "fallback_provider",
        "processing_time_ms",
    )

    def __init__(
        self,
        *,
        summary: Summary,
        research_gaps: ResearchGaps,
        literature_review: LiteratureReview,
        model_used: str,
        model_provider: str | None,
        fallback_used: bool | None,
        fallback_provider: str | None,
        processing_time_ms: int | None,
    ) -> None:
        self.summary = summary
        self.research_gaps = research_gaps
        self.literature_review = literature_review
        self.model_used = model_used
        self.model_provider = model_provider
        self.fallback_used = fallback_used
        self.fallback_provider = fallback_provider
        self.processing_time_ms = processing_time_ms


class AnalysisCache:
    """Reusable analyses, keyed by document content.

    Every method fails SOFT. The cache is an optimisation: if it is
    unreachable, misconfigured, or holding something unreadable, the correct
    behaviour is to analyse the paper normally, not to fail the upload. A
    broken cache must never be able to take the product down.
    """

    def __init__(self, settings: Settings, timeout_seconds: float = 10.0) -> None:
        self._rest = settings.supabase_rest_url
        self._timeout = timeout_seconds
        key = settings.supabase_service_role_key.strip()
        # Service role: see the module note. This key never leaves the server
        # and is never used for any table that carries user data - the
        # per-user library is reached with the user's own token, as before.
        self._headers = {
            "apikey": key,
            "Authorization": f"Bearer {key}",
            "Content-Type": "application/json",
        }

    # ---------- reading ----------

    async def get(self, content_hash: str, analysis_version: str) -> CachedAnalysis | None:
        """The stored analysis for this document, or None.

        None covers every failure as well as a genuine miss, on purpose: the
        caller's response to both is identical - analyse the paper.
        """
        try:
            async with httpx.AsyncClient(timeout=self._timeout) as client:
                response = await client.get(
                    f"{self._rest}/analysis_cache",
                    headers=self._headers,
                    params={
                        "select": (
                            "id,summary,research_gaps,literature_review,model_used,"
                            "model_provider,fallback_used,fallback_provider,"
                            "processing_time_ms"
                        ),
                        "content_hash": f"eq.{content_hash}",
                        "analysis_version": f"eq.{analysis_version}",
                        "limit": 1,
                    },
                )
            if not response.is_success:
                logger.warning("analysis cache lookup failed: HTTP %s", response.status_code)
                return None
            rows = response.json()
        except Exception as exc:  # noqa: BLE001 - the cache must never break upload
            logger.warning("analysis cache unreachable: %s", type(exc).__name__)
            return None

        if not rows:
            return None
        row = rows[0]

        try:
            # Validated on the way OUT as well as in. The stored shape is jsonb,
            # so this is the only thing standing between a hand-edited row and
            # a response the frontend cannot render. A row that fails is
            # treated as a miss rather than as an error.
            cached = CachedAnalysis(
                summary=Summary.model_validate(row["summary"]),
                research_gaps=ResearchGaps.model_validate(row["research_gaps"]),
                literature_review=LiteratureReview.model_validate(row["literature_review"]),
                model_used=str(row.get("model_used") or ""),
                model_provider=row.get("model_provider"),
                fallback_used=row.get("fallback_used"),
                fallback_provider=row.get("fallback_provider"),
                processing_time_ms=row.get("processing_time_ms"),
            )
        except Exception as exc:  # noqa: BLE001
            logger.warning("cached analysis failed validation, ignoring it: %s", exc)
            return None

        # Best-effort usage counter, deliberately not awaited for correctness:
        # a failed counter update must not turn a cache hit into a miss.
        await self._record_hit(row["id"])
        return cached

    async def _record_hit(self, row_id: str) -> None:
        """Bump hit_count and last_used_at. Purely observational."""
        try:
            async with httpx.AsyncClient(timeout=self._timeout) as client:
                await client.post(
                    f"{self._rest}/rpc/touch_analysis_cache",
                    headers=self._headers,
                    json={"row_id": row_id},
                )
        except Exception:  # noqa: BLE001 - a statistic is not worth an error
            pass

    # ---------- writing ----------

    async def put(
        self,
        *,
        content_hash: str,
        analysis_version: str,
        analysis: AnalysisResponse,
    ) -> None:
        """Store a COMPLETE, VALIDATED analysis. Never a failure.

        `analysis` is an `AnalysisResponse`, which means it has already passed
        the same Pydantic validation the API returns to the client - there is
        no path by which a partial or malformed result reaches this method.

        Concurrency: two people can upload the same new paper at once, both
        miss, both analyse, and both write. `resolution=ignore-duplicates`
        turns the loser of that race into a no-op against the UNIQUE
        (content_hash, analysis_version) constraint, so there is never a
        duplicate row and neither request fails. No lock is held while the
        model is running - the write happens after, and only if it succeeded.
        """
        payload = {
            "content_hash": content_hash,
            "analysis_version": analysis_version,
            "summary": analysis.summary.model_dump(),
            "research_gaps": analysis.research_gaps.model_dump(),
            "literature_review": analysis.literature_review.model_dump(),
            "model_used": analysis.model_used,
            "model_provider": analysis.model_provider,
            "fallback_used": analysis.fallback_used,
            "fallback_provider": analysis.fallback_provider,
            "processing_time_ms": analysis.processing_time_ms,
        }
        try:
            async with httpx.AsyncClient(timeout=self._timeout) as client:
                response = await client.post(
                    f"{self._rest}/analysis_cache",
                    headers={
                        **self._headers,
                        # The loser of a race is ignored, not an error.
                        "Prefer": "resolution=ignore-duplicates,return=minimal",
                    },
                    json=payload,
                )
            if not response.is_success:
                logger.warning("could not store analysis in cache: HTTP %s", response.status_code)
        except Exception as exc:  # noqa: BLE001 - a failed cache write is not a failed analysis
            logger.warning("analysis cache write failed: %s", type(exc).__name__)


def get_analysis_cache(settings: Settings) -> AnalysisCache | None:
    """Build the cache, or None when this deployment cannot use one.

    Requires the SECRET key specifically. A publishable key in that slot
    cannot see past RLS, so it would read an empty cache forever and silently
    make every upload a miss - the same failure mode `has_database` already
    guards against for the library.
    """
    if not settings.has_database:
        return None
    return AnalysisCache(settings)


def build_cache_payload(cached: CachedAnalysis) -> dict[str, Any]:
    """The provenance fields to copy onto a reusing user's own analysis row.

    A reused result keeps the provenance of the run that PRODUCED it, so a
    stored analysis always names the model that actually wrote it - even
    though the owner may have switched providers since.
    """
    return {
        "model_used": cached.model_used,
        "model_provider": cached.model_provider,
        "fallback_used": cached.fallback_used,
        "fallback_provider": cached.fallback_provider,
        "processing_time_ms": cached.processing_time_ms,
    }
