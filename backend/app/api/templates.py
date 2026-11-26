"""템플릿 파일(투명 PNG, 가이드 레이어 PNG, PDF, 전체 ZIP) 다운로드 API 라우터."""

from __future__ import annotations

import zipfile
from pathlib import Path
from typing import Literal

from fastapi import APIRouter, HTTPException, Query, status
from fastapi.responses import FileResponse

from app.core.charsets import get_preset
from app.core.config import settings
from app.core.template_spec import DEFAULT_TEMPLATE_SPEC
from app.services.jamo_template_generator import JAMO_PRESET_ID, generate_jamo_templates
from app.services.template_generator import generate_templates

router = APIRouter(prefix="/api/templates", tags=["templates"])


def _ensure_generated_jamo_templates() -> Path:
    """조합형(6-2-2벌) 테스트 템플릿 산출물이 캐시에 없으면 생성하고 디렉터리를 반환합니다."""
    out_dir = settings.storage_dir / "templates" / DEFAULT_TEMPLATE_SPEC.version / JAMO_PRESET_ID
    meta_path = out_dir / "metadata.json"
    if not meta_path.is_file():
        generate_jamo_templates(
            output_dir=out_dir,
            spec=DEFAULT_TEMPLATE_SPEC,
            formats=("png", "guide", "pdf", "meta"),
        )
    return out_dir


def _ensure_generated_templates(preset_id: str) -> Path:
    """요청한 프리셋의 템플릿 산출물이 캐시에 없으면 생성하고 디렉터리를 반환합니다."""
    try:
        get_preset(preset_id)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc

    out_dir = settings.storage_dir / "templates" / DEFAULT_TEMPLATE_SPEC.version / preset_id
    meta_path = out_dir / "metadata.json"
    if not meta_path.is_file():
        generate_templates(
            preset_id=preset_id,
            output_dir=out_dir,
            spec=DEFAULT_TEMPLATE_SPEC,
            formats=("png", "guide", "pdf", "meta"),
        )
    return out_dir


def _ensure_template_zip(preset_id: str, out_dir: Path) -> Path:
    """프리셋의 모든 템플릿 파일을 묶은 ZIP을 생성(캐시)하고 경로를 반환합니다."""
    zip_path = out_dir / f"geulssedam_{preset_id}_{DEFAULT_TEMPLATE_SPEC.version}.zip"
    if zip_path.is_file():
        return zip_path

    with zipfile.ZipFile(zip_path, mode="w", compression=zipfile.ZIP_DEFLATED) as zf:
        for file_path in sorted(out_dir.iterdir()):
            if file_path.is_file() and file_path.suffix in {".png", ".pdf", ".json"}:
                zf.write(file_path, arcname=file_path.name)
    return zip_path


@router.get("/jamo/download/{kind}")
def download_jamo_template_file(
    kind: Literal["zip", "pdf", "canvas", "guide", "meta"],
    page: int = Query(default=1, ge=1, le=3, description="canvas/guide 다운로드 시 페이지 번호"),
) -> FileResponse:
    """실험용 한글 조합형(6-2-2벌, 210칸/3페이지) 템플릿 파일을 다운로드합니다."""
    out_dir = _ensure_generated_jamo_templates()

    if kind == "zip":
        target = _ensure_template_zip(JAMO_PRESET_ID, out_dir)
        media_type = "application/zip"
    elif kind == "pdf":
        target = out_dir / f"template_{JAMO_PRESET_ID}_{DEFAULT_TEMPLATE_SPEC.version}.pdf"
        media_type = "application/pdf"
    elif kind == "meta":
        target = out_dir / "metadata.json"
        media_type = "application/json"
    elif kind == "canvas":
        target = out_dir / f"page_{page:02d}_canvas.png"
        media_type = "image/png"
    else:
        target = out_dir / f"page_{page:02d}_guide.png"
        media_type = "image/png"

    if not target.is_file():
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="요청한 조합형 템플릿 파일을 찾을 수 없습니다.",
        )

    return FileResponse(path=str(target), media_type=media_type, filename=target.name)


@router.get("/{preset_id}/download/{kind}")
def download_template_file(
    preset_id: str,
    kind: Literal["zip", "pdf", "canvas", "guide", "meta"],
    page: int = Query(default=1, ge=1, description="canvas/guide 다운로드 시 페이지 번호"),
) -> FileResponse:
    """선택한 문자 범위 프리셋의 템플릿 파일을 다운로드합니다."""
    out_dir = _ensure_generated_templates(preset_id)

    if kind == "zip":
        target = _ensure_template_zip(preset_id, out_dir)
        media_type = "application/zip"
    elif kind == "pdf":
        target = out_dir / f"template_{preset_id}_{DEFAULT_TEMPLATE_SPEC.version}.pdf"
        media_type = "application/pdf"
    elif kind == "meta":
        target = out_dir / "metadata.json"
        media_type = "application/json"
    elif kind == "canvas":
        target = out_dir / f"page_{page:02d}_canvas.png"
        media_type = "image/png"
    else:
        target = out_dir / f"page_{page:02d}_guide.png"
        media_type = "image/png"

    if not target.is_file():
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="요청한 템플릿 파일을 찾을 수 없습니다.",
        )

    return FileResponse(path=str(target), media_type=media_type, filename=target.name)
