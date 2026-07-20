import asyncio
import logging
import time as _time
import traceback
from contextlib import asynccontextmanager
from pathlib import Path

_T_MAIN_IMPORT_START = _time.perf_counter()

from fastapi import FastAPI, Request
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse, JSONResponse, Response
from starlette.types import Scope, Receive, Send

from app.config import settings
from app.database import AsyncSessionLocal, init_db
from app.services.settings_service import load_settings_from_db
from app.api import observations, map, ingest, identify, culinary, scan, reidentify, syncthing, connections, audit, settings as settings_api, recipes, sharing, notes as notes_api, enrich as enrich_api, dev as dev_api, trust as trust_api
from app.api import resources as resources_api
from app.api import walk as walk_api
from app.api import about as about_api
from app.api import nearby as nearby_api
from app.api import edibility as edibility_api
from app.api import find as find_api
from app.api import taxonomy as taxonomy_api
from app.api import encounters as encounters_api
from app.api import chat as chat_api
from app.api import data_sources as data_sources_api
from app.api import personal_lists as personal_lists_api
from app.api import notifications as notifications_api
from app.api import recorded_walks as recorded_walks_api
from app.api import itis as itis_api
from app.api import foray_sessions as foray_sessions_api
from app.api import processes as processes_api
from app.api import lists_pdf as lists_pdf_api
from app.api import queue_api
from app.api import workshop_tokens as workshop_tokens_api
from app.api import bulk_actions as bulk_actions_api
from app.api import timeline as timeline_api
from app.models import foray_session as _foray_session_models  # noqa: F401 — ensures ForagingSession tables are in Base.metadata
from app.models import notes as _notes_models          # noqa: F401 — ensures MapNote is in Base.metadata
from app.models import data_source as _data_source_models  # noqa: F401 — ensures DataSource is in Base.metadata
from app.models import walk as _walk_models            # noqa: F401 — ensures SavedWalk is in Base.metadata
from app.models import scan_session as _scan_session_models  # noqa: F401 — ensures ScanSession is in Base.metadata
from app.models import encounter as _encounter_models  # noqa: F401 — ensures Encounter is in Base.metadata
from app.models import personal_list as _personal_list_models  # noqa: F401 — ensures PersonalList tables are in Base.metadata
from app.models import notification as _notification_models  # noqa: F401 — ensures NotificationDismissal is in Base.metadata
from app.models import recorded_walk as _recorded_walk_models  # noqa: F401 — ensures RecordedWalk tables are in Base.metadata
from app.models.species import SpeciesResource as _SpeciesResource  # noqa: F401 — ensures species_resources is in Base.metadata
from app.models import process as _process_models  # noqa: F401 — ensures BackgroundProcess is in Base.metadata
from app.models import workshop as _workshop_models  # noqa: F401 — ensures WorkshopParticipant/GuestToken in Base.metadata
from app.models.observation import DeletedHash as _DeletedHash  # noqa: F401 — ensures deleted_hashes is in Base.metadata
from app.models.species import SpeciesSynonym as _SpeciesSynonym  # noqa: F401 — ensures species_synonyms is in Base.metadata
from app.models.species import SpeciesEdibilityHistory as _SpeciesEdibilityHistory  # noqa: F401 — ensures species_edibility_history is in Base.metadata
from app.models import user as _user_models  # noqa: F401 — ensures User (users) is in Base.metadata

log = logging.getLogger(__name__)

_T_MAIN_IMPORTS_DONE = _time.perf_counter()
print(f"[TIMING] main.py: module-level imports complete: {_T_MAIN_IMPORTS_DONE - _T_MAIN_IMPORT_START:.1f}s", flush=True)


class NoCacheStaticFiles(StaticFiles):
    """StaticFiles that adds Cache-Control: no-cache so browsers always
    revalidate thumbnails. Prevents stale green/blank thumbnails after
    regen_thumbnails.py regenerates files on disk."""

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        async def patched_send(message: dict) -> None:
            if message["type"] == "http.response.start":
                headers = dict(message.get("headers", []))
                headers[b"cache-control"] = b"no-cache, must-revalidate"
                message["headers"] = list(headers.items())
            await send(message)

        await super().__call__(scope, receive, patched_send)


def _warn_if_inat_token_expiring() -> None:
    """
    A1.1 — decode the iNaturalist JWT on server start and log a warning if it
    is already expired or expires within 4 hours. Surfaces token problems at
    boot rather than only when the Settings dashboard is opened. iNaturalist
    tokens last ~24h, so a stale token silently disables dual-source ID.
    """
    from app.services.api_dashboard import _inat_token_status, INAT_EXPIRY_WARN_SECONDS

    token = settings.inaturalist_api_token
    if not token:
        log.warning(
            "iNaturalist token not configured — dual-source identification disabled. "
            "Add INATURALIST_API_TOKEN (Settings → API Dashboard, or .env)."
        )
        return

    info = _inat_token_status(token)
    remaining = info.get("expires_in_seconds")
    if remaining is None:
        # Not a decodable JWT — can't assess expiry here; dashboard will probe live.
        log.warning("iNaturalist token is not a decodable JWT — expiry cannot be verified at startup.")
        return

    if remaining <= 0:
        log.warning(
            "iNaturalist token EXPIRED %d minutes ago — identification will skip iNaturalist. "
            "Refresh at inaturalist.org/users/api_token and paste into Settings → API Dashboard.",
            abs(remaining) // 60,
        )
        # Seed the owner-facing status so the in-app banner shows from boot, not only
        # after the first scan hits the expired token.
        from app.integrations.inaturalist import record_inat_status
        record_inat_status("token_expired", "expired at startup")
    elif remaining < INAT_EXPIRY_WARN_SECONDS:
        log.warning(
            "iNaturalist token expires in %d minutes (< 4h) — refresh soon at "
            "inaturalist.org/users/api_token to avoid identification gaps.",
            remaining // 60,
        )
    else:
        log.info("iNaturalist token valid — expires in ~%d hours.", remaining // 3600)


@asynccontextmanager
async def lifespan(app: FastAPI):
    _ls0 = _time.perf_counter()
    print(f"[TIMING] lifespan: start", flush=True)

    settings.ensure_dirs()
    _ls1 = _time.perf_counter()
    print(f"[TIMING] lifespan: ensure_dirs: {_ls1 - _ls0:.1f}s", flush=True)

    await init_db()
    _ls2 = _time.perf_counter()
    print(f"[TIMING] lifespan: init_db (wall): {_ls2 - _ls1:.1f}s", flush=True)

    async with AsyncSessionLocal() as session:
        await load_settings_from_db(session)
    _ls3 = _time.perf_counter()
    print(f"[TIMING] lifespan: load_settings_from_db: {_ls3 - _ls2:.1f}s", flush=True)

    _warn_if_inat_token_expiring()
    _ls4 = _time.perf_counter()
    print(f"[TIMING] lifespan: _warn_if_inat_token_expiring: {_ls4 - _ls3:.1f}s", flush=True)

    from app.api.queue_api import recover_stale_jobs
    await recover_stale_jobs()
    # Same recovery for background_processes: a row killed mid-run would
    # otherwise stay 'running' forever and never leave /api/processes/active.
    from app.services.background_processes import recover_stale_processes
    await recover_stale_processes()
    _ls5 = _time.perf_counter()
    print(f"[TIMING] lifespan: recover_stale_jobs: {_ls5 - _ls4:.1f}s", flush=True)

    task = asyncio.create_task(syncthing._auto_scan_loop())
    _ls6 = _time.perf_counter()
    print(f"[TIMING] lifespan: create_task(syncthing): {_ls6 - _ls5:.1f}s", flush=True)

    # Orphan sweep — recovers rows committed at stage='ingested' that never
    # reached identify. Takes the same pipeline mutex as P1/the archive scan, so
    # it can never compete with a live scan for the single SQLite writer.
    from app.services.orphan_sweep import orphan_sweep_loop
    sweep_task = asyncio.create_task(orphan_sweep_loop())
    print(f"[TIMING] lifespan: TOTAL startup: {_ls6 - _ls0:.1f}s", flush=True)

    yield
    task.cancel()
    sweep_task.cancel()


app = FastAPI(
    title="ForagingID",
    description="Local-first plant foraging intelligence system",
    version="0.1.0",
    lifespan=lifespan,
)


# ---------------------------------------------------------------------------
# Global exception handler — always returns JSON, never plain text.
# Without this, Starlette's ServerErrorMiddleware returns "Internal Server
# Error" as plain text, which breaks fetch(...).json() on the client.
# ---------------------------------------------------------------------------

@app.exception_handler(Exception)
async def _global_exception_handler(request: Request, exc: Exception) -> JSONResponse:
    tb = traceback.format_exc()
    log.error("Unhandled exception on %s %s:\n%s", request.method, request.url.path, tb)
    return JSONResponse(
        status_code=500,
        content={"detail": "Internal server error", "error": type(exc).__name__},
    )

# API routers
app.include_router(observations.router)
app.include_router(map.router)
app.include_router(ingest.router)
app.include_router(identify.router)
app.include_router(culinary.router)
app.include_router(scan.router)
app.include_router(reidentify.router)
app.include_router(syncthing.router)
app.include_router(connections.router)
app.include_router(audit.router)
app.include_router(settings_api.router)
app.include_router(recipes.router)
app.include_router(sharing.router)
app.include_router(notes_api.router)
app.include_router(enrich_api.router)
app.include_router(dev_api.router)
app.include_router(walk_api.router)
app.include_router(about_api.router)
app.include_router(nearby_api.router)
app.include_router(trust_api.router)
app.include_router(chat_api.router)
app.include_router(edibility_api.router)
app.include_router(find_api.router)
app.include_router(taxonomy_api.router)
app.include_router(encounters_api.router)
app.include_router(resources_api.router)
app.include_router(data_sources_api.router)
app.include_router(personal_lists_api.router)
app.include_router(notifications_api.router)
app.include_router(recorded_walks_api.router)
app.include_router(itis_api.router)
app.include_router(foray_sessions_api.router)
app.include_router(processes_api.router)
app.include_router(lists_pdf_api.router)
app.include_router(queue_api.router)
app.include_router(workshop_tokens_api.router)
app.include_router(bulk_actions_api.router)
app.include_router(timeline_api.router)


# ---------------------------------------------------------------------------
# Guest mode middleware — runs before route handlers.
# Detects ngrok-origin requests and enforces read-only restrictions.
# ---------------------------------------------------------------------------
_GUEST_BLOCKED_PATHS = {"/scan", "/review", "/settings", "/workshops"}


@app.middleware("http")
async def _guest_middleware(request: Request, call_next) -> Response:
    tier = sharing.classify_host(request)
    if tier == "denied":
        # Unrecognised host: not localhost/LAN (curator) and not the ngrok tunnel
        # (guest). Block outright so a custom domain / stray tunnel can't reach the app.
        log.warning(
            "Denied request from unrecognised host %r (%s %s)",
            request.headers.get("host"), request.method, request.url.path,
        )
        return JSONResponse(status_code=403, content={"detail": "Forbidden host"})
    if tier == "guest":
        # Bare root → guest landing page (deep links like /?species=… keep their
        # query string and fall through to the map so guests can still follow them).
        if (
            request.url.path == "/"
            and not request.url.query
            and request.method in ("GET", "HEAD")
        ):
            return FileResponse("frontend/landing.html", headers={"Cache-Control": "no-store"})
        # Redirect restricted pages to the landing page
        if request.url.path in _GUEST_BLOCKED_PATHS:
            from fastapi.responses import RedirectResponse
            return RedirectResponse(url="/", status_code=302)
        # Block all write operations except the walk export, encounter creation,
        # and recorded-walk sync (owner's device syncing pending walks via tunnel)
        if request.method not in ("GET", "HEAD", "OPTIONS"):
            if request.url.path not in (
                "/api/sharing/export-walk",
                "/api/encounters",
                "/api/recorded-walks",
                "/api/recorded-walks/audio-upload",
            ):
                return JSONResponse(
                    status_code=403,
                    content={"detail": "Guest mode — read-only access"},
                )
    return await call_next(request)

# Serve thumbnails — NoCacheStaticFiles ensures browsers revalidate after regen
thumbnails_dir = Path(settings.thumbnails_dir)
if thumbnails_dir.exists():
    app.mount("/thumbnails", NoCacheStaticFiles(directory=str(thumbnails_dir)), name="thumbnails")

# Serve uploads — same no-cache policy
uploads_dir = Path(settings.uploads_dir)
uploads_dir.mkdir(parents=True, exist_ok=True)
app.mount("/uploads-files", NoCacheStaticFiles(directory=str(uploads_dir)), name="uploads-files")

# Serve recorded walk audio notes
rec_walks_media_dir = Path("media/recorded_walks")
rec_walks_media_dir.mkdir(parents=True, exist_ok=True)
app.mount("/media/recorded-walks", StaticFiles(directory=str(rec_walks_media_dir)), name="recorded-walks-media")

# Serve encounter media (audio files)
encounters_media_dir = settings.encounters_media_dir
encounters_media_dir.mkdir(parents=True, exist_ok=True)
app.mount("/media/encounters", StaticFiles(directory=str(encounters_media_dir)), name="encounters-media")

species_resources_dir = settings.species_resources_dir
species_resources_dir.mkdir(parents=True, exist_ok=True)
app.mount("/media/species-resources", StaticFiles(directory=str(species_resources_dir)), name="species-resources-media")

# Serve frontend static files
frontend_dir = Path("frontend/static")
if frontend_dir.exists():
    # NoCacheStaticFiles ensures browsers always revalidate JS/CSS on each request,
    # preventing the service worker from serving stale cached versions of changed files.
    app.mount("/static", NoCacheStaticFiles(directory=str(frontend_dir)), name="static")


_NO_STORE = {"Cache-Control": "no-store"}


@app.get("/", include_in_schema=False)
async def serve_map():
    return FileResponse("frontend/index.html", headers=_NO_STORE)


@app.get("/map", include_in_schema=False)
async def serve_map_alias():
    # Stable map URL. Guests reach the map here via the landing-page CTA, since
    # bare "/" serves the guest landing page (see _guest_middleware).
    return FileResponse("frontend/index.html", headers=_NO_STORE)


@app.get("/review", include_in_schema=False)
async def serve_review():
    return FileResponse("frontend/review.html", headers=_NO_STORE)


@app.get("/species", include_in_schema=False)
async def serve_species():
    return FileResponse("frontend/species.html", headers=_NO_STORE)


@app.get("/sightings", include_in_schema=False)
async def serve_sightings():
    return FileResponse("frontend/sightings.html", headers=_NO_STORE)


@app.get("/taxonomy", include_in_schema=False)
async def serve_taxonomy():
    return FileResponse("frontend/taxonomy.html", headers=_NO_STORE)


@app.get("/scan", include_in_schema=False)
async def serve_scan():
    return FileResponse("frontend/scan.html", headers=_NO_STORE)


@app.get("/lists", include_in_schema=False)
async def serve_lists():
    return FileResponse("frontend/lists.html", headers=_NO_STORE)


@app.get("/lists/print", include_in_schema=False)
async def serve_lists_print():
    return FileResponse("frontend/print.html", headers=_NO_STORE)


@app.get("/settings", include_in_schema=False)
async def serve_settings():
    return FileResponse("frontend/settings.html", headers=_NO_STORE)


@app.get("/workshops", include_in_schema=False)
async def serve_workshops():
    return FileResponse("frontend/workshops.html", headers=_NO_STORE)


@app.get("/about", include_in_schema=False)
async def serve_about():
    return FileResponse("frontend/about.html", headers=_NO_STORE)


@app.get("/scratch-filename-test", include_in_schema=False)
async def serve_scratch_filename_test():
    p = Path("frontend/scratch-filename-test.html")
    if not p.exists():
        raise HTTPException(404)
    return FileResponse(str(p), headers=_NO_STORE)


@app.get("/encounters", include_in_schema=False)
async def serve_encounters():
    return FileResponse("frontend/encounters.html", headers=_NO_STORE)


@app.get("/seasons", include_in_schema=False)
async def serve_seasons():
    return FileResponse("frontend/seasons.html", headers=_NO_STORE)


@app.get("/my-season", include_in_schema=False)
async def redirect_my_season(request: Request):
    """Backwards-compat redirect: /my-season → /encounters (merged page).
    Query string is preserved so deep links like /my-season?species=ID still work."""
    from fastapi.responses import RedirectResponse
    qs = request.url.query
    target = "/encounters?" + qs if qs else "/encounters"
    return RedirectResponse(url=target, status_code=301)


@app.get("/upload", include_in_schema=False)
async def redirect_upload():
    """Backwards-compat redirect: /upload → /scan"""
    from fastapi.responses import RedirectResponse
    return RedirectResponse(url="/scan", status_code=301)


@app.get("/sw.js", include_in_schema=False)
async def serve_service_worker():
    # Served from root so the worker controls the whole origin (scope "/").
    # no-store on the SW file itself so updates ship immediately; the worker
    # manages its own asset caches internally.
    return FileResponse(
        "frontend/static/sw.js",
        media_type="application/javascript",
        headers={"Cache-Control": "no-store", "Service-Worker-Allowed": "/"},
    )


@app.get("/health")
async def health():
    return {"status": "ok", "version": "0.2.0"}
