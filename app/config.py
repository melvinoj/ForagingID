from pathlib import Path
from pydantic_settings import BaseSettings
from pydantic import Field, field_validator


class Settings(BaseSettings):
    # API Keys
    plantnet_api_key: str = ""
    inaturalist_app_id: str = ""
    inaturalist_app_secret: str = ""
    # Personal API token from https://www.inaturalist.org/users/api_token
    # Required for the computer-vision scoring endpoint (POST /computervision/score_image).
    # Taxa autocomplete works without a token.
    inaturalist_api_token: str = ""

    # Anthropic Claude API key — used for AI-drafted species fields (taste notes,
    # medicinal notes, recipe). Leave empty to skip AI draft generation.
    # Get a key at: https://console.anthropic.com/
    anthropic_api_key: str = ""
    # Model to use for AI drafts. Default is Sonnet for voice-matched recipe /
    # medicinal content; Haiku is classification-only and lower quality here.
    anthropic_model: str = "claude-sonnet-4-6"

    # OpenAI key — used ONLY for server-side Whisper transcription of encounter
    # audio (POST /v1/audio/transcriptions). Leave empty to disable the
    # Transcribe button. Transcription is a deliberate laptop step, never
    # automatic on capture. Get a key at: https://platform.openai.com/api-keys
    openai_api_key: str = ""
    # Whisper model + per-minute cost estimate shown in the UI (£0.006/min).
    whisper_model: str = "whisper-1"

    # OpenRouteService — walking routes on the Walk panel (foot-hiking profile)
    ors_api_key: str = ""

    # Thunderforest — Outdoors base layer on the map (optional)
    # Get a free key at: https://www.thunderforest.com/
    thunderforest_api_key: str = ""

    # Paths
    # Default photo source: external folder — photos are read in place, never copied.
    # Override via PHOTO_LIBRARY_PATH env var or .env file.
    photo_library_path: Path = Path("~/Documents/Pictures").expanduser()
    data_dir: Path = Path("./data")
    uploads_dir: Path = Path("./uploads")   # browser-uploaded images (pending review)

    @field_validator("photo_library_path", mode="before")
    @classmethod
    def expand_photo_path(cls, v: object) -> Path:
        """Expand ~ in photo_library_path regardless of how the value was set."""
        return Path(str(v)).expanduser()
    thumbnails_dir: Path = Path("./data/thumbnails")
    cache_dir: Path = Path("./data/cache")
    database_url: str = "sqlite+aiosqlite:///./data/foragingid.db"

    # Processing
    thumbnail_size: int = 300
    batch_size: int = 50
    min_confidence_threshold: float = 0.3
    plant_detect_confidence: float = 0.5

    # Server
    host: str = "127.0.0.1"
    port: int = 8000
    debug: bool = False

    model_config = {"env_file": ".env", "env_file_encoding": "utf-8", "env_ignore_empty": True}

    @property
    def phone_foraging_dir(self) -> Path:
        """
        Syncthing watch directory — photos synced automatically from phone.
        Read-only: files here are never moved or deleted by the app.
        Resolves to: ~/Local(unsynced)/PhoneForaging

        Fallback only — the live path comes from the photo_library_path DB
        setting (see syncthing._watch_dir()). Note there is no space in
        "Local(unsynced)": this literal must match the directory on disk, or
        clearing the DB override leaves P1 watching a non-existent folder.
        """
        return Path("~/Local(unsynced)/PhoneForaging").expanduser()

    @property
    def species_resources_dir(self) -> Path:
        """Uploaded images and PDFs attached to species cards."""
        return Path(__file__).resolve().parent.parent / "media" / "species_resources"

    @property
    def encounters_media_dir(self) -> Path:
        """
        Absolute path for encounter audio/media files.
        Resolves to: <project_root>/media/encounters/
        """
        return Path(__file__).resolve().parent.parent / "media" / "encounters"

    @property
    def confirmed_plants_dir(self) -> Path:
        """
        Absolute path to the confirmed_plants folder — always inside the ForagingID
        project directory so confirmed photos are git-tracked alongside the DB.
        Resolves to: <project_root>/photos/confirmed_plants/
        """
        return Path(__file__).resolve().parent.parent / "photos" / "confirmed_plants"

    @property
    def phone_uploads_dir(self) -> Path:
        """
        Permanent storage for phone browser uploads.
        Always inside the ForagingID project directory — git-tracked, never in /tmp.
        Resolves to: <project_root>/uploads/

        Path integrity rule: observations with file_path inside this directory
        are SAFE — never abandon them even if the scan folder moves or is re-linked.
        """
        return Path(__file__).resolve().parent.parent / "uploads"

    @property
    def pipeline2_dir(self) -> Path:
        """
        Permanent storage for Pipeline 2 (Syncthing / Takeout batch) images.
        Files are COPIED here on ingest so observations are never HD-dependent.
        Resolves to: <project_root>/photos/pipeline2/

        Path integrity rule: all P2 observations with file_path inside this
        directory are project-local and safe after the external HD is removed.
        """
        return Path(__file__).resolve().parent.parent / "photos" / "pipeline2"

    def ensure_dirs(self):
        for d in [
            self.data_dir, self.thumbnails_dir, self.cache_dir,
            self.uploads_dir,       # legacy relative path (kept for compat)
            self.phone_uploads_dir, # permanent project-rooted uploads
            self.pipeline2_dir,     # P2 batch copies (HD-independent)
            self.confirmed_plants_dir,
            self.encounters_media_dir,
        ]:
            Path(d).mkdir(parents=True, exist_ok=True)


settings = Settings()
