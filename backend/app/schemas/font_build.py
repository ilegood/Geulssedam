"""폰트 빌드 요청 및 비동기 작업 진행률 Pydantic 스키마."""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field

JobStatus = Literal["queued", "running", "completed", "failed"]


class FontBuildRequest(BaseModel):
    """폰트 생성 작업 요청."""

    session_token: str = Field(..., description="업로드가 완료된 임시 세션 토큰")
    font_name: str = Field(
        default="MyHandwriting",
        min_length=1,
        max_length=40,
        description="생성할 폰트 이름 (영문 권장, 파일명 및 메타정보에 사용)",
    )
    author_name: str = Field(
        default="Geulssedam User",
        min_length=1,
        max_length=40,
        description="제작자 이름 (폰트 메타정보에 기록)",
    )
    letter_spacing: int = Field(
        default=0,
        ge=-100,
        le=300,
        description="전체 자간 조절 값 (font units, 기본 0)",
    )
    scale_factor: float = Field(
        default=1.0,
        ge=0.6,
        le=1.5,
        description="전체 글자 크기 보정 배율 (기본 1.0)",
    )


class FontBuildArtifacts(BaseModel):
    """생성된 폰트 산출물 정보."""

    ttf_filename: str
    woff2_filename: str
    zip_filename: str
    preview_woff2_url: str
    download_ttf_url: str
    download_woff2_url: str
    download_zip_url: str
    included_chars: list[str]
    missing_chars: list[str]


class FontBuildJobResponse(BaseModel):
    """비동기 폰트 빌드 작업 상태 및 진행률 응답."""

    job_id: str
    session_token: str
    status: JobStatus
    progress: int = Field(..., ge=0, le=100, description="진행률 (0~100)")
    message: str = Field(..., description="현재 단계 안내 메시지")
    created_at: str
    updated_at: str
    error: str | None = None
    artifacts: FontBuildArtifacts | None = None
