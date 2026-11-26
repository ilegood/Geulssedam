"""환경 변수 기반 애플리케이션 설정."""

from pathlib import Path
from typing import Literal

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """백엔드 전역 설정."""

    app_name: str = "글씨담 (Geulssedam) API"
    app_version: str = "0.1.0"
    app_env: Literal["development", "production", "test"] = "development"

    # 비동기 작업 백엔드: 로컬 기본은 background, Docker/운영은 rq
    task_backend: Literal["background", "rq"] = "background"
    redis_url: str = "redis://localhost:6379/0"

    # 저장소 및 업로드 제한
    storage_dir: Path = Path("../storage")
    retention_days: int = 7
    max_upload_mb: int = 50

    # CORS 허용 오리진 (쉼표 구분)
    cors_origins: str = "http://localhost:5173"

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    @property
    def cors_origin_list(self) -> list[str]:
        """쉼표로 구분된 CORS 오리진 문자열을 리스트로 변환합니다."""
        return [origin.strip() for origin in self.cors_origins.split(",") if origin.strip()]

    @property
    def max_upload_bytes(self) -> int:
        """최대 업로드 크기를 바이트 단위로 반환합니다."""
        return self.max_upload_mb * 1024 * 1024


settings = Settings()
