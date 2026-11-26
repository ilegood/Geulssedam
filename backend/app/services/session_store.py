"""비회원 임시 링크(토큰) 기반 세션 저장소.

업로드 이미지와 검증 결과 JSON을 `storage/sessions/{session_token}/` 아래에 보관하며,
7일 보관 만료 시각(`expires_at`)을 메타데이터에 기록합니다.
"""

from __future__ import annotations

import json
import secrets
from datetime import UTC, datetime, timedelta
from pathlib import Path

from app.core.config import settings
from app.schemas.validation import (
    SessionInfoResponse,
    UploadedPageSummary,
    UploadValidationResponse,
)


def _sessions_root(base_dir: Path | None = None) -> Path:
    root = (base_dir or settings.storage_dir) / "sessions"
    root.mkdir(parents=True, exist_ok=True)
    return root


def _session_dir(session_token: str, base_dir: Path | None = None) -> Path:
    # 경로 탐색 문자 차단
    if not session_token or "/" in session_token or "\\" in session_token or ".." in session_token:
        raise ValueError("유효하지 않은 세션 토큰입니다.")
    return _sessions_root(base_dir) / session_token


def create_session(
    preset_id: str = "mvp",
    template_version: str = "v1",
    base_dir: Path | None = None,
) -> SessionInfoResponse:
    """새 비회원 임시 세션을 생성하고 메타데이터를 저장합니다."""
    token = secrets.token_urlsafe(18)
    now = datetime.now(UTC)
    expires_at = now + timedelta(days=settings.retention_days)

    sdir = _session_dir(token, base_dir)
    (sdir / "uploads").mkdir(parents=True, exist_ok=True)

    meta = {
        "session_token": token,
        "preset_id": preset_id,
        "template_version": template_version,
        "created_at": now.isoformat(),
        "expires_at": expires_at.isoformat(),
    }
    (sdir / "session.json").write_text(
        json.dumps(meta, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    return SessionInfoResponse(**meta, uploaded_pages=[])


def get_session(session_token: str, base_dir: Path | None = None) -> SessionInfoResponse | None:
    """세션 토큰으로 세션 정보와 업로드된 페이지 검증 요약을 조회합니다."""
    sdir = _session_dir(session_token, base_dir)
    meta_path = sdir / "session.json"
    if not meta_path.is_file():
        return None

    meta = json.loads(meta_path.read_text(encoding="utf-8"))
    uploads_dir = sdir / "uploads"
    uploaded_pages: list[UploadedPageSummary] = []

    if uploads_dir.is_dir():
        for val_path in sorted(uploads_dir.glob("page_*_validation.json")):
            val_data = json.loads(val_path.read_text(encoding="utf-8"))
            uploaded_pages.append(
                UploadedPageSummary(
                    page_number=val_data["page_number"],
                    overall_status=val_data["overall_status"],
                    summary=val_data.get("summary"),
                )
            )

    return SessionInfoResponse(**meta, uploaded_pages=uploaded_pages)


def save_uploaded_page(
    session_token: str,
    page_number: int,
    image_bytes: bytes,
    validation_result: UploadValidationResponse,
    base_dir: Path | None = None,
) -> Path:
    """검증을 통과한 업로드 PNG와 검증 결과 JSON을 세션 디렉터리에 저장합니다."""
    sdir = _session_dir(session_token, base_dir)
    uploads_dir = sdir / "uploads"
    uploads_dir.mkdir(parents=True, exist_ok=True)

    image_path = uploads_dir / f"page_{page_number:02d}.png"
    image_path.write_bytes(image_bytes)

    val_path = uploads_dir / f"page_{page_number:02d}_validation.json"
    val_path.write_text(
        validation_result.model_dump_json(indent=2),
        encoding="utf-8",
    )
    return image_path
