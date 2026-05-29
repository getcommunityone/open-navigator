"""Static file serving with HTTP caching for the public ``/data`` tree.

The census-map marts, per-state ZCTA tiles, and the jurisdiction-quality
snapshot are large (hundreds of KB to several MB), change only on a
pipeline/vintage cadence, and are read far more than they are written. That is
the textbook profile for browser/CDN caching.

``StaticFiles`` already emits ``ETag`` and ``Last-Modified`` (so conditional
requests get a cheap ``304``), but without an explicit ``Cache-Control`` the
client revalidates on *every* request. ``CachedStaticFiles`` stamps a
``max-age`` so the cache is actually used, with ``stale-while-revalidate`` so a
CDN can serve the cached copy while refreshing in the background.
"""

from typing import Any, MutableMapping

from starlette.responses import Response
from starlette.staticfiles import StaticFiles


class CachedStaticFiles(StaticFiles):
    """``StaticFiles`` that adds ``Cache-Control`` to successful responses."""

    def __init__(self, *args: Any, max_age: int = 3600, **kwargs: Any) -> None:
        # 1 hour is conservative for these (filenames aren't content-hashed, so
        # after a data refresh clients pick it up within the hour — and the
        # ETag means even an in-window revalidation is a 304, not a re-download).
        self.max_age = max_age
        super().__init__(*args, **kwargs)

    async def get_response(self, path: str, scope: MutableMapping[str, Any]) -> Response:
        response = await super().get_response(path, scope)
        # Stamp 2xx and 304 (a 304 revalidation should stay cacheable too); skip
        # 404s so a missing tile isn't cached as "absent".
        if response.status_code < 400:
            response.headers["Cache-Control"] = (
                f"public, max-age={self.max_age}, stale-while-revalidate=86400"
            )
        return response
