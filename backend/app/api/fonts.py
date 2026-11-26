"""폰트 빌드 실행, 진행률 조회, 미리보기 WOFF2 및 다운로드 API 라우터."""

from __future__ import annotations

import base64
import io
import json
from dataclasses import replace
from typing import Literal

import numpy as np
from fastapi import APIRouter, BackgroundTasks, HTTPException, status
from fastapi.responses import FileResponse
from PIL import Image

from app.core.config import settings
from app.core.template_spec import DEFAULT_TEMPLATE_SPEC
from app.core.validation_config import DEFAULT_VALIDATION_THRESHOLDS
from app.schemas.font_build import FontBuildJobResponse, FontBuildRequest
from app.services.cell_splitter import split_page_into_cells
from app.services.glyph_normalizer import DEFAULT_SIDE_BEARING, UNITS_PER_EM
from app.services.session_store import get_session
from app.workers.build_jobs import create_build_job, get_build_job, run_font_build_job

router = APIRouter(prefix="/api/fonts", tags=["fonts"])


@router.post("/build", response_model=FontBuildJobResponse, status_code=status.HTTP_202_ACCEPTED)
def start_font_build(
    payload: FontBuildRequest,
    background_tasks: BackgroundTasks,
) -> FontBuildJobResponse:
    """업로드된 세션의 템플릿 이미지로 비동기 폰트 빌드 작업을 시작합니다."""
    try:
        session = get_session(payload.session_token)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc

    if session is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="세션을 찾을 수 없거나 만료되었습니다.",
        )

    job = create_build_job(payload)

    if settings.task_backend == "rq":
        try:
            from redis import Redis
            from rq import Queue

            conn = Redis.from_url(settings.redis_url)
            queue = Queue("fontbuilder", connection=conn)
            queue.enqueue(run_font_build_job, job.job_id, payload)
        except Exception:
            # Redis 연결 불가 시 안전하게 BackgroundTasks로 폴백
            background_tasks.add_task(run_font_build_job, job.job_id, payload)
    else:
        background_tasks.add_task(run_font_build_job, job.job_id, payload)

    return job


@router.get("/jobs/{job_id}", response_model=FontBuildJobResponse)
def read_build_job_status(job_id: str) -> FontBuildJobResponse:
    """비동기 폰트 빌드 작업의 현재 상태와 진행률(0~100%)을 조회합니다."""
    try:
        job = get_build_job(job_id)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc

    if job is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="폰트 생성 작업을 찾을 수 없습니다.",
        )
    return job


def _resolve_artifact_path(session_token: str, fmt: Literal["ttf", "woff2", "zip"]) -> tuple[
    str, str
]:
    """세션의 최신 빌드 산출물 경로와 파일명을 반환합니다."""
    if not session_token or "/" in session_token or "\\" in session_token or ".." in session_token:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="유효하지 않은 토큰입니다.",
        )

    build_dir = settings.storage_dir / "sessions" / session_token / "build"
    latest_path = build_dir / "latest.json"
    if not latest_path.is_file():
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="생성된 폰트 파일이 없습니다. 먼저 폰트를 생성해 주세요.",
        )

    latest = json.loads(latest_path.read_text(encoding="utf-8"))
    key = f"{fmt}_filename"
    filename = latest.get(key)
    file_path = build_dir / filename if filename else None
    if file_path is None or not file_path.is_file():
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="요청한 폰트 파일을 찾을 수 없습니다.",
        )
    return str(file_path), filename


@router.get("/{session_token}/glyph-previews")
def get_glyph_previews(session_token: str) -> dict[str, object]:
    """자간·크기 실시간 미리보기용 글리프 썸네일과 치수를 반환합니다."""
    try:
        session = get_session(session_token)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc

    if session is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="세션을 찾을 수 없거나 만료되었습니다.",
        )

    uploads_dir = settings.storage_dir / "sessions" / session_token / "uploads"
    spec = replace(DEFAULT_TEMPLATE_SPEC, version=session.template_version)
    threshold = DEFAULT_VALIDATION_THRESHOLDS.alpha_foreground_threshold

    glyph_previews: dict[str, dict[str, object]] = {}
    if uploads_dir.is_dir():
        for page_file in sorted(uploads_dir.glob("page_*.png")):
            stem_parts = page_file.stem.split("_")
            if len(stem_parts) != 2 or not stem_parts[1].isdigit():
                continue
            page_num = int(stem_parts[1])
            try:
                cells = split_page_into_cells(
                    image_path=page_file,
                    preset_id=session.preset_id,
                    page_number=page_num,
                    spec=spec,
                )
            except ValueError:
                continue

            for cell in cells:
                if cell.is_empty:
                    continue
                ys, xs = np.where(cell.alpha >= threshold)
                if len(xs) == 0 or len(ys) == 0:
                    continue

                x0, x1 = int(xs.min()), int(xs.max())
                y0, y1 = int(ys.min()), int(ys.max())
                cell_h = float(cell.alpha.shape[0])
                baseline_px = cell_h * spec.baseline_ratio
                em_per_px = UNITS_PER_EM / cell_h

                crop_alpha = cell.alpha[y0 : y1 + 1, x0 : x1 + 1]
                ch, cw = crop_alpha.shape
                rgba = np.zeros((ch, cw, 4), dtype=np.uint8)
                rgba[:, :, 0] = 30
                rgba[:, :, 1] = 41
                rgba[:, :, 2] = 59
                rgba[:, :, 3] = crop_alpha

                img = Image.fromarray(rgba, mode="RGBA")
                max_side = 96
                if max(cw, ch) > max_side:
                    img.thumbnail((max_side, max_side), Image.Resampling.LANCZOS)

                buf = io.BytesIO()
                img.save(buf, format="PNG", optimize=True)
                b64 = base64.b64encode(buf.getvalue()).decode("ascii")

                glyph_previews[cell.char] = {
                    "data_url": f"data:image/png;base64,{b64}",
                    "width_em": round((x1 - x0 + 1) * em_per_px, 2),
                    "height_em": round((y1 - y0 + 1) * em_per_px, 2),
                    "ascent_em": round((baseline_px - y0) * em_per_px, 2),
                }

    return {
        "session_token": session_token,
        "units_per_em": UNITS_PER_EM,
        "default_side_bearing": DEFAULT_SIDE_BEARING,
        "glyphs": glyph_previews,
    }


@router.get("/{session_token}/preview.woff2")
def get_preview_woff2(session_token: str) -> FileResponse:
    """웹 미리보기용 WOFF2 폰트 파일을 반환합니다."""
    file_path, filename = _resolve_artifact_path(session_token, "woff2")
    return FileResponse(
        path=file_path,
        media_type="font/woff2",
        filename=filename,
        headers={"Cache-Control": "no-store"},
    )


@router.get("/{session_token}/download/{fmt}")
def download_font_artifact(
    session_token: str,
    fmt: Literal["ttf", "woff2", "zip"],
) -> FileResponse:
    """생성된 TTF, WOFF2 또는 설치 안내·라이선스 포함 ZIP 파일을 다운로드합니다."""
    file_path, filename = _resolve_artifact_path(session_token, fmt)
    media_types = {
        "ttf": "font/ttf",
        "woff2": "font/woff2",
        "zip": "application/zip",
    }
    return FileResponse(
        path=file_path,
        media_type=media_types[fmt],
        filename=filename,
    )
