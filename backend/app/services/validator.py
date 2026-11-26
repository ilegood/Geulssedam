"""업로드 파일 및 칸 단위 품질 검증 서비스.

템플릿 규격(TemplateSpec)과 검증 임계값(ValidationThresholds)을 기준으로:
1. 파일 단위 검증: PNG 형식, 알파 채널, 비율, 최소/권장 해상도, 배경 투명 여부
2. 칸 단위 검증: 빈 칸, 너무 꽉 참, 가장자리 잘림 의심, 획 두께 부족(distance transform),
   반투명 픽셀 과다, 가이드선 잔존 감지
"""

from __future__ import annotations

import io
from dataclasses import dataclass

import cv2
import numpy as np
from PIL import Image, UnidentifiedImageError

from app.core.charsets import build_page_plans
from app.core.template_spec import DEFAULT_TEMPLATE_SPEC, TemplateSpec
from app.core.validation_config import DEFAULT_VALIDATION_THRESHOLDS, ValidationThresholds
from app.schemas.validation import (
    CellMetrics,
    CellStatus,
    CellValidationResult,
    FileValidationResult,
    Severity,
    UploadValidationResponse,
    ValidationIssue,
    ValidationSummary,
)


@dataclass(frozen=True)
class _LoadedImage:
    alpha: np.ndarray
    width: int
    height: int
    image_format: str
    has_alpha: bool


def _load_image_bytes(image_bytes: bytes) -> tuple[_LoadedImage | None, FileValidationResult]:
    """바이트 스트림에서 이미지를 열고 파일 단위 기본 형식/알파 채널을 검사합니다."""
    try:
        with Image.open(io.BytesIO(image_bytes)) as img:
            img.load()
            img_format = (img.format or "").upper()
            width, height = img.size
            has_alpha = "A" in img.getbands()

            issues: list[ValidationIssue] = []
            if img_format != "PNG":
                issues.append(
                    ValidationIssue(
                        code="invalid_format",
                        severity="error",
                        message="PNG 형식의 이미지 파일만 업로드할 수 있어요.",
                    )
                )

            if not has_alpha:
                issues.append(
                    ValidationIssue(
                        code="missing_alpha",
                        severity="error",
                        message=(
                            "투명 배경(알파 채널)이 없는 이미지예요. "
                            "배경을 투명하게 내보낸 PNG로 다시 올려주세요."
                        ),
                    )
                )

            if issues:
                return None, FileValidationResult(
                    status="error",
                    width_px=width,
                    height_px=height,
                    has_alpha=has_alpha,
                    image_format=img_format or None,
                    issues=issues,
                )

            # 알파 채널만 추출해 대용량 PNG(5120×5120) 처리 시 메모리 사용량을 1/4로 절감
            alpha = np.array(img.getchannel("A"), dtype=np.uint8)
            return (
                _LoadedImage(
                    alpha=alpha,
                    width=width,
                    height=height,
                    image_format=img_format,
                    has_alpha=True,
                ),
                FileValidationResult(
                    status="ok",
                    width_px=width,
                    height_px=height,
                    has_alpha=True,
                    image_format=img_format,
                    issues=[],
                ),
            )
    except (UnidentifiedImageError, OSError):
        return None, FileValidationResult(
            status="error",
            has_alpha=False,
            issues=[
                ValidationIssue(
                    code="unreadable_image",
                    severity="error",
                    message="이미지 파일을 읽을 수 없어요. 손상되지 않은 PNG 파일을 올려주세요.",
                )
            ],
        )


def validate_file_level(
    loaded: _LoadedImage,
    spec: TemplateSpec = DEFAULT_TEMPLATE_SPEC,
    thresholds: ValidationThresholds = DEFAULT_VALIDATION_THRESHOLDS,
) -> FileValidationResult:
    """비율, 칸당 해상도(최소 256px/권장 512px), 투명 배경 여부를 검증합니다."""
    issues: list[ValidationIssue] = []
    width, height = loaded.width, loaded.height

    expected_ratio = spec.cols / spec.rows
    actual_ratio = width / height if height > 0 else 0.0
    if abs(actual_ratio - expected_ratio) > thresholds.aspect_ratio_tolerance:
        issues.append(
            ValidationIssue(
                code="invalid_aspect_ratio",
                severity="error",
                message=(
                    f"템플릿 비율({spec.cols}:{spec.rows})과 맞지 않아요. "
                    "템플릿 크기를 자르거나 늘리지 말고 그대로 저장해 주세요."
                ),
            )
        )

    cell_w = width // spec.cols
    cell_h = height // spec.rows
    min_cell_dim = min(cell_w, cell_h)

    if min_cell_dim < spec.min_cell_size_px:
        issues.append(
            ValidationIssue(
                code="resolution_too_low",
                severity="error",
                message=(
                    f"해상도가 너무 낮아 업로드할 수 없어요 "
                    f"(현재 칸당 {min_cell_dim}px, 최소 {spec.min_cell_size_px}px 이상 필요)."
                ),
            )
        )
    elif min_cell_dim < spec.recommended_cell_size_px:
        issues.append(
            ValidationIssue(
                code="resolution_below_recommended",
                severity="warning",
                message=(
                    f"칸당 {spec.recommended_cell_size_px}px 이상을 권장해요 "
                    f"(현재 칸당 {min_cell_dim}px). 해상도가 낮으면 곡선이 각져 보일 수 있어요."
                ),
            )
        )

    # 전체 배경이 불투명하게 칠해져 있는지 검사
    alpha = loaded.alpha
    opaque_page_ratio = float(np.mean(alpha >= thresholds.alpha_foreground_threshold))
    if opaque_page_ratio >= thresholds.opaque_background_ratio:
        issues.append(
            ValidationIssue(
                code="opaque_background",
                severity="warning",
                message=(
                    "배경이 투명하지 않고 칠해져 있는 것 같아요. "
                    "흰 배경 레이어를 숨긴 뒤 투명 PNG로 내보내 주세요."
                ),
            )
        )

    status: Severity = "ok"
    if any(item.severity == "error" for item in issues):
        status = "error"
    elif any(item.severity == "warning" for item in issues):
        status = "warning"

    return FileValidationResult(
        status=status,
        width_px=width,
        height_px=height,
        cell_width_px=cell_w,
        cell_height_px=cell_h,
        has_alpha=loaded.has_alpha,
        image_format=loaded.image_format,
        issues=issues,
    )


def _detect_guide_line(
    alpha: np.ndarray,
    thresholds: ValidationThresholds,
) -> bool:
    """칸 가로/세로를 길게 가로지르는 직선 패턴(가이드선 잔존)을 감지합니다."""
    # 가이드선은 반투명할 수도 있으므로 낮은 알파 임계값(24)으로 존재 여부 검사
    visible_mask = alpha >= 24
    if not np.any(visible_mask):
        return False

    row_coverage = visible_mask.mean(axis=1)
    col_coverage = visible_mask.mean(axis=0)
    span = thresholds.guide_line_span_ratio

    # 칸을 가로지르는 수평선 또는 수직선이 존재하면 가이드선 잔존으로 의심
    return bool(np.any(row_coverage >= span) or np.any(col_coverage >= span))


def validate_cell_alpha(
    cell_alpha: np.ndarray,
    index: int,
    row: int,
    col: int,
    char: str | None,
    thresholds: ValidationThresholds = DEFAULT_VALIDATION_THRESHOLDS,
) -> CellValidationResult:
    """단일 칸의 알파 채널 배열에 대해 품질 진단을 수행합니다."""
    codepoint = f"U+{ord(char):04X}" if char is not None else None
    if char is None:
        return CellValidationResult(
            index=index,
            row=row,
            col=col,
            char=None,
            codepoint=None,
            status="unused",
            issues=[],
            metrics=None,
        )

    height, width = cell_alpha.shape
    fg_mask = cell_alpha >= thresholds.alpha_foreground_threshold
    opaque_ratio = float(fg_mask.mean())

    visible_mask = cell_alpha >= thresholds.alpha_semitransparent_low
    semi_mask = (cell_alpha >= thresholds.alpha_semitransparent_low) & (
        cell_alpha <= thresholds.alpha_semitransparent_high
    )
    visible_count = int(visible_mask.sum())
    semi_ratio = float(semi_mask.sum() / visible_count) if visible_count > 0 else 0.0

    # 가이드선 잔존 감지 (빈 칸이더라도 연한 가이드선이 남아 있으면 경고)
    has_guide_line = _detect_guide_line(cell_alpha, thresholds)

    # 1) 빈 칸 판정
    if opaque_ratio < thresholds.empty_cell_max_ratio:
        issues: list[ValidationIssue] = [
            ValidationIssue(
                code="empty_cell",
                severity="warning",
                message="이 칸이 비어 있어요.",
            )
        ]
        if has_guide_line:
            issues.append(
                ValidationIssue(
                    code="guide_line_detected",
                    severity="warning",
                    message="가이드선이 남아 있는 것 같아요.",
                )
            )
        return CellValidationResult(
            index=index,
            row=row,
            col=col,
            char=char,
            codepoint=codepoint,
            status="empty",
            issues=issues,
            metrics=CellMetrics(
                opaque_ratio=round(opaque_ratio, 5),
                semitransparent_ratio=round(semi_ratio, 4),
                estimated_stroke_ratio=0.0,
                edge_contact_pixels=0,
            ),
        )

    issues = []

    # 2) 너무 꽉 찬 칸
    if opaque_ratio > thresholds.overfilled_cell_min_ratio:
        issues.append(
            ValidationIssue(
                code="overfilled_cell",
                severity="error",
                message="배경이 칠해졌거나 글자가 너무 커요.",
            )
        )

    # 3) 가장자리 잘림 의심
    m = max(1, min(thresholds.edge_clip_margin_px, min(height, width) // 4))
    border_mask = np.zeros_like(fg_mask, dtype=bool)
    border_mask[:m, :] = True
    border_mask[-m:, :] = True
    border_mask[:, :m] = True
    border_mask[:, -m:] = True
    edge_contact_pixels = int((fg_mask & border_mask).sum())

    if edge_contact_pixels >= thresholds.edge_clip_min_pixels:
        issues.append(
            ValidationIssue(
                code="edge_clipped",
                severity="warning",
                message="글자가 칸 경계에 닿아 있어요. 여백을 두고 그려주세요.",
            )
        )

    # 4) 획 두께 측정 (OpenCV distanceTransform: 중심축 최대 거리 * 2로 평균 획 두께 추정)
    dist_map = cv2.distanceTransform(fg_mask.astype(np.uint8), cv2.DIST_L2, 5)
    fg_dists = dist_map[fg_mask]
    # 획 중심선을 잘 반영하는 상위 25%(75백분위수) 거리 * 2로 평균 획 두께 추정
    cell_dim = float(min(height, width))
    if fg_dists.size > 0:
        raw_stroke = float(np.percentile(fg_dists, 75)) * 2.0
        estimated_stroke_px = min(raw_stroke, cell_dim)
    else:
        estimated_stroke_px = 0.0
    stroke_ratio = estimated_stroke_px / cell_dim if cell_dim > 0 else 0.0

    if stroke_ratio < thresholds.min_stroke_width_ratio:
        issues.append(
            ValidationIssue(
                code="thin_stroke",
                severity="warning",
                message="획이 너무 얇아요. 작은 크기에서 글자가 사라질 수 있어요.",
            )
        )

    # 5) 반투명 픽셀 과다
    if semi_ratio > thresholds.max_semitransparent_ratio:
        issues.append(
            ValidationIssue(
                code="semitransparent_excess",
                severity="warning",
                message="반투명 픽셀이 많아요. 번짐 브러시 대신 단단한 브러시를 권장해요.",
            )
        )

    # 6) 가이드선 잔존 의심
    if has_guide_line:
        issues.append(
            ValidationIssue(
                code="guide_line_detected",
                severity="warning",
                message="가이드선이 남아 있는 것 같아요.",
            )
        )

    status: CellStatus = "ok"
    if any(item.severity == "error" for item in issues):
        status = "error"
    elif any(item.severity == "warning" for item in issues):
        status = "warning"

    return CellValidationResult(
        index=index,
        row=row,
        col=col,
        char=char,
        codepoint=codepoint,
        status=status,
        issues=issues,
        metrics=CellMetrics(
            opaque_ratio=round(opaque_ratio, 5),
            semitransparent_ratio=round(semi_ratio, 4),
            estimated_stroke_ratio=round(stroke_ratio, 4),
            edge_contact_pixels=edge_contact_pixels,
        ),
    )


def validate_uploaded_page(
    image_bytes: bytes,
    preset_id: str,
    page_number: int,
    spec: TemplateSpec = DEFAULT_TEMPLATE_SPEC,
    thresholds: ValidationThresholds = DEFAULT_VALIDATION_THRESHOLDS,
    session_token: str | None = None,
) -> UploadValidationResponse:
    """업로드된 템플릿 페이지 PNG에 대해 파일 및 칸 단위 전체 검증을 수행합니다."""
    pages = build_page_plans(preset_id, cells_per_page=spec.cells_per_page)
    if page_number < 1 or page_number > len(pages):
        raise ValueError(
            f"유효하지 않은 페이지 번호입니다: {page_number} (1~{len(pages)} 범위만 허용)"
        )
    page_plan = pages[page_number - 1]

    loaded, basic_result = _load_image_bytes(image_bytes)
    if loaded is None:
        return UploadValidationResponse(
            session_token=session_token,
            template_version=spec.version,
            preset_id=preset_id,
            page_number=page_number,
            overall_status="error",
            saved=False,
            file_validation=basic_result,
            summary=None,
            cells=[],
        )

    file_val = validate_file_level(loaded, spec=spec, thresholds=thresholds)
    if file_val.status == "error":
        return UploadValidationResponse(
            session_token=session_token,
            template_version=spec.version,
            preset_id=preset_id,
            page_number=page_number,
            overall_status="error",
            saved=False,
            file_validation=file_val,
            summary=None,
            cells=[],
        )

    # 파일 단위 검증을 통과한 경우 10×10 칸으로 분할하여 칸별 진단 수행
    alpha_full = loaded.alpha
    cell_h = loaded.height / spec.rows
    cell_w = loaded.width / spec.cols

    cell_results: list[CellValidationResult] = []
    for idx in range(spec.cells_per_page):
        row = idx // spec.cols
        col = idx % spec.cols
        y0 = round(row * cell_h)
        y1 = round((row + 1) * cell_h)
        x0 = round(col * cell_w)
        x1 = round((col + 1) * cell_w)
        char = page_plan.chars[idx] if idx < len(page_plan.chars) else None

        cell_alpha = alpha_full[y0:y1, x0:x1]
        cell_results.append(
            validate_cell_alpha(
                cell_alpha=cell_alpha,
                index=idx,
                row=row,
                col=col,
                char=char,
                thresholds=thresholds,
            )
        )

    ok_count = sum(1 for c in cell_results if c.status == "ok")
    warning_count = sum(1 for c in cell_results if c.status == "warning")
    error_count = sum(1 for c in cell_results if c.status == "error")
    empty_count = sum(1 for c in cell_results if c.status == "empty")

    summary = ValidationSummary(
        total_cells=spec.cells_per_page,
        assigned_cells=len(page_plan.chars),
        ok_count=ok_count,
        warning_count=warning_count,
        error_count=error_count,
        empty_count=empty_count,
    )

    overall: Severity = "ok"
    if error_count > 0:
        overall = "error"
    elif file_val.status == "warning" or warning_count > 0 or empty_count > 0:
        overall = "warning"

    return UploadValidationResponse(
        session_token=session_token,
        template_version=spec.version,
        preset_id=preset_id,
        page_number=page_number,
        overall_status=overall,
        saved=True,
        file_validation=file_val,
        summary=summary,
        cells=cell_results,
    )
