"""비동기 폰트 빌드 작업 실행 및 진행률 추적 모듈.

세션 디렉터리(`storage/sessions/{session_token}/`)의 업로드된 PNG 페이지들을
칸 분할 → 벡터화 → 정규화 → TTF/WOFF2/ZIP 조립 순서로 처리하며,
작업 상태와 진행률(0~100%)을 `storage/jobs/{job_id}.json`에 기록합니다.
"""

from __future__ import annotations

import json
import secrets
from datetime import UTC, datetime
from pathlib import Path

from app.core.charsets import build_page_plans
from app.core.config import settings
from app.core.template_spec import DEFAULT_TEMPLATE_SPEC
from app.schemas.font_build import (
    FontBuildArtifacts,
    FontBuildJobResponse,
    FontBuildRequest,
    JobStatus,
)
from app.services.cell_splitter import split_page_into_cells
from app.services.font_builder import build_font_files
from app.services.glyph_normalizer import (
    NormalizedGlyph,
    merge_glyph_layers,
    normalize_vectorized_glyph,
)
from app.services.jamo_template_generator import (
    JAMO_POSITIONAL_GROUP_IDS,
    compose_hangul_syllables_from_jamo,
    get_jamo_page_plan_for_group,
)
from app.services.session_store import get_session
from app.services.vectorizer import VectorizedGlyph, vectorize_alpha_mask


def _jobs_root(base_dir: Path | None = None) -> Path:
    root = (base_dir or settings.storage_dir) / "jobs"
    root.mkdir(parents=True, exist_ok=True)
    return root


def _job_path(job_id: str, base_dir: Path | None = None) -> Path:
    if not job_id or "/" in job_id or "\\" in job_id or ".." in job_id:
        raise ValueError("유효하지 않은 작업 ID입니다.")
    return _jobs_root(base_dir) / f"{job_id}.json"


def _save_job(job: FontBuildJobResponse, base_dir: Path | None = None) -> None:
    _job_path(job.job_id, base_dir).write_text(
        job.model_dump_json(indent=2),
        encoding="utf-8",
    )


def get_build_job(job_id: str, base_dir: Path | None = None) -> FontBuildJobResponse | None:
    """작업 ID로 폰트 빌드 진행률 및 결과를 조회합니다."""
    path = _job_path(job_id, base_dir)
    if not path.is_file():
        return None
    data = json.loads(path.read_text(encoding="utf-8"))
    return FontBuildJobResponse(**data)


def create_build_job(
    request: FontBuildRequest,
    base_dir: Path | None = None,
) -> FontBuildJobResponse:
    """새 폰트 빌드 작업을 queued 상태로 등록합니다."""
    now = datetime.now(UTC).isoformat()
    job = FontBuildJobResponse(
        job_id=secrets.token_urlsafe(12),
        session_token=request.session_token,
        status="queued",
        progress=0,
        message="폰트 생성 작업을 대기 중입니다.",
        created_at=now,
        updated_at=now,
    )
    _save_job(job, base_dir)
    return job


def _update_job(
    job_id: str,
    status: JobStatus,
    progress: int,
    message: str,
    error: str | None = None,
    artifacts: FontBuildArtifacts | None = None,
    base_dir: Path | None = None,
) -> FontBuildJobResponse:
    current = get_build_job(job_id, base_dir)
    if current is None:
        raise ValueError(f"작업을 찾을 수 없습니다: {job_id}")
    updated = current.model_copy(
        update={
            "status": status,
            "progress": progress,
            "message": message,
            "updated_at": datetime.now(UTC).isoformat(),
            "error": error,
            "artifacts": artifacts,
        }
    )
    _save_job(updated, base_dir)
    return updated


def run_font_build_job(
    job_id: str,
    request: FontBuildRequest,
    base_dir: Path | None = None,
) -> FontBuildJobResponse:
    """실제 폰트 빌드 파이프라인을 실행하고 단계별 진행률을 갱신합니다."""
    storage_root = base_dir or settings.storage_dir
    try:
        _update_job(
            job_id,
            "running",
            5,
            "업로드된 템플릿 이미지를 불러오는 중...",
            base_dir=base_dir,
        )
        session = get_session(request.session_token, base_dir=storage_root)
        if session is None:
            raise ValueError("세션을 찾을 수 없거나 만료되었습니다.")

        sdir = storage_root / "sessions" / request.session_token
        uploads_dir = sdir / "uploads"
        uploaded_pngs = sorted(uploads_dir.glob("page_*.png"))
        if not uploaded_pngs:
            raise ValueError("업로드된 템플릿 이미지가 없습니다. 먼저 이미지를 올려주세요.")

        # 1) 칸 분할
        _update_job(
            job_id,
            "running",
            15,
            "템플릿을 칸 단위로 분할하는 중...",
            base_dir=base_dir,
        )
        all_pages = build_page_plans(
            session.preset_id,
            cells_per_page=DEFAULT_TEMPLATE_SPEC.cells_per_page,
        )
        expected_chars = [
            ch
            for page in all_pages
            if page.group_id not in JAMO_POSITIONAL_GROUP_IDS
            for ch in page.chars
        ]

        direct_cells = []
        jamo_slot_cells: list[tuple[str, object]] = []
        for png_path in uploaded_pngs:
            # 파일명 page_01.png → 페이지 번호 추출
            stem_parts = png_path.stem.split("_")
            page_num = int(stem_parts[1])
            if page_num < 1 or page_num > len(all_pages):
                continue
            page_plan = all_pages[page_num - 1]
            cells = split_page_into_cells(
                image_path=png_path,
                preset_id=session.preset_id,
                page_number=page_num,
                spec=DEFAULT_TEMPLATE_SPEC,
            )

            if page_plan.group_id in JAMO_POSITIONAL_GROUP_IDS:
                jamo_page = get_jamo_page_plan_for_group(
                    page_plan.group_id, page_plan.page_number, page_plan.total_pages
                )
                if jamo_page is not None:
                    for idx, cell in enumerate(cells):
                        if not cell.is_empty and idx < len(jamo_page.slots):
                            jamo_slot_cells.append((jamo_page.slots[idx].slot_id, cell))
            else:
                direct_cells.extend(c for c in cells if not c.is_empty)

        if not direct_cells and not jamo_slot_cells:
            raise ValueError("작성된 글자가 없습니다. 최소 1글자 이상 그린 뒤 다시 시도해 주세요.")

        # 2) 벡터화 + em 박스 정규화 (진행률 20% → 75%)
        handwritten_glyphs: dict[int, NormalizedGlyph] = {}
        jamo_vectors: dict[str, VectorizedGlyph] = {}
        total = len(direct_cells) + len(jamo_slot_cells)
        processed = 0

        for cell in direct_cells:
            vectorized = vectorize_alpha_mask(cell.alpha)
            normalized = normalize_vectorized_glyph(
                char=cell.char,
                vectorized=vectorized,
                spec=DEFAULT_TEMPLATE_SPEC,
                letter_spacing_delta=request.letter_spacing,
                scale_factor=request.scale_factor,
            )
            if normalized is not None:
                handwritten_glyphs[normalized.codepoint] = normalized
            processed += 1
            if processed % max(1, total // 10) == 0 or processed == total:
                pct = 20 + int((processed / total) * 55)
                _update_job(
                    job_id,
                    "running",
                    pct,
                    f"글자 윤곽선을 추출하고 정규화하는 중... ({processed}/{total})",
                    base_dir=base_dir,
                )

        for slot_id, cell in jamo_slot_cells:
            vectorized = vectorize_alpha_mask(cell.alpha)
            if vectorized.contours:
                jamo_vectors[slot_id] = vectorized
            processed += 1
            if processed % max(1, total // 10) == 0 or processed == total:
                pct = 20 + int((processed / total) * 55)
                _update_job(
                    job_id,
                    "running",
                    pct,
                    f"조합용 자모 윤곽선을 추출하는 중... ({processed}/{total})",
                    base_dir=base_dir,
                )

        composed_glyphs: dict[int, NormalizedGlyph] = {}
        if jamo_vectors:
            _update_job(
                job_id,
                "running",
                78,
                "한글 자모(6-2-2벌)를 완성형 음절로 조합하는 중...",
                base_dir=base_dir,
            )
            composed_glyphs = compose_hangul_syllables_from_jamo(
                jamo_vectors=jamo_vectors,
                spec=DEFAULT_TEMPLATE_SPEC,
                letter_spacing_delta=request.letter_spacing,
                scale_factor=request.scale_factor,
            )

        # 조합형 레이어 위에 직접 그린 글자(영문/숫자/단독 자모 등)를 우선 병합
        final_glyphs = merge_glyph_layers(composed_glyphs, handwritten_glyphs)

        # 3) fontTools로 TTF / WOFF2 / ZIP 조립
        _update_job(
            job_id,
            "running",
            85,
            "TTF 및 WOFF2 폰트 파일을 조립하는 중...",
            base_dir=base_dir,
        )
        build_dir = sdir / "build"
        pkg = build_font_files(
            glyphs=final_glyphs,
            output_dir=build_dir,
            font_name=request.font_name,
            author_name=request.author_name,
            letter_spacing=request.letter_spacing,
        )

        # 세션 최신 빌드 결과 매니페스트 저장 (다운로드/미리보기 엔드포인트용)
        included_set = set(pkg.included_chars)
        missing_chars = [ch for ch in expected_chars if ch not in included_set]

        artifacts = FontBuildArtifacts(
            ttf_filename=pkg.ttf_path.name,
            woff2_filename=pkg.woff2_path.name,
            zip_filename=pkg.zip_path.name,
            preview_woff2_url=f"/api/fonts/{request.session_token}/preview.woff2",
            download_ttf_url=f"/api/fonts/{request.session_token}/download/ttf",
            download_woff2_url=f"/api/fonts/{request.session_token}/download/woff2",
            download_zip_url=f"/api/fonts/{request.session_token}/download/zip",
            included_chars=list(pkg.included_chars),
            missing_chars=missing_chars,
        )
        (build_dir / "latest.json").write_text(
            artifacts.model_dump_json(indent=2),
            encoding="utf-8",
        )

        return _update_job(
            job_id,
            "completed",
            100,
            f"폰트 생성이 완료되었습니다! (총 {len(pkg.included_chars)}자 포함)",
            artifacts=artifacts,
            base_dir=base_dir,
        )
    except Exception as exc:
        return _update_job(
            job_id,
            "failed",
            100,
            "폰트 생성 중 오류가 발생했습니다.",
            error=str(exc),
            base_dir=base_dir,
        )
