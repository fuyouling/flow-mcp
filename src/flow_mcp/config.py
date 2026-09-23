import os
from pathlib import Path
from pydantic import field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent


class Settings(BaseSettings):
    """Application settings — cluster-native, loaded from .env."""

    # ── Chrome ──────────────────────────────────────────────────────
    chrome_user_data_dir: str = str(PROJECT_ROOT / "chrome_data")
    chrome_profile_directory: str = "Default"
    chrome_binary_path: str = ""
    chrome_download_dir: str = str(PROJECT_ROOT / "downloads")
    browser_config_path: str = str(PROJECT_ROOT / "browser_config.yaml")

    # ── Google Flow ──────────────────────────────────────────────────
    google_flow_base_url: str = "https://flow.google.com"

    # ── Master 网络配置 ──────────────────────────────────────────────
    master_host: str = "0.0.0.0"
    master_http_port: int = 8765
    master_grpc_port: int = 50051
    master_asset_dir: str = str(PROJECT_ROOT / "data" / "assets")
    db_path: str = str(PROJECT_ROOT / "data" / "flow_mcp.db")

    # ── Worker 配置 ──────────────────────────────────────────────────
    master_http_url: str = "http://127.0.0.1:8765"
    master_grpc_target: str = "127.0.0.1:50051"
    worker_id: str = "master_local_worker"
    worker_account: str = ""

    # ── 日志 ────────────────────────────────────────────────────────
    log_level: str = "INFO"

    @field_validator(
        "chrome_user_data_dir",
        "chrome_download_dir",
        "browser_config_path",
        "master_asset_dir",
        "db_path",
        mode="before",
    )
    @classmethod
    def _normalize_path(cls, v: str) -> str:
        if not v:
            return v
        return str(Path(v).expanduser().resolve())

    model_config = SettingsConfigDict(
        env_file=(str(PROJECT_ROOT / ".env"), ".env"),
        env_file_encoding="utf-8",
        extra="ignore",
    )


_settings: Settings | None = None


def get_settings() -> Settings:
    global _settings
    if _settings is None:
        _settings = Settings()
    return _settings


def reset_settings() -> None:
    global _settings
    _settings = None
