"""업로드된 10×10 템플릿 PNG를 칸 단위로 분할하는 모듈."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

import numpy as np
from PIL import Image

from app.core.charsets import build_page_plans
from app.core.template_spec import DEFAULT_TEMPLATE_SPEC, TemplateSpec
from app.core.validation_config import DEFAULT_VALIDATION_THRESHOLDS, ValidationThresholds


@dataclass(frozen=True)
class ExtractedCell:
    """템플릿 페이지에서 추출된 단일 글자 칸 데이터."""

    char: str
    codepoint: int
    row: int
    col: int
    page_number: int
    alpha: np.ndarray
    is_empty: bool


def split_page_into_cells(
    image_path: Path,
    preset_id: str,
    page_number: int,
    spec: TemplateSpec = DEFAULT_TEMPLATE_SPEC,
    thresholds: ValidationThresholds = DEFAULT_VALIDATION_THRESHOLDS,
) -> list[ExtractedCell]:
    """템플릿 PNG 이미지를 10×10 칸으로 분할해 문자별 알파 채널 배열을 반환합니다."""
    pages = build_page_plans(preset_id, cells_per_page=spec.cells_per_page)
    if page_number < 1 or page_number > len(pages):
        raise ValueError(f"유효하지 않은 페이지 번호입니다: {page_number}")
    page_plan = pages[page_number - 1]

    with Image.open(image_path) as img:
        rgba = np.array(img.convert("RGBA"), dtype=np.uint8)

    alpha_full = rgba[:, :, 3]
    height, width = alpha_full.shape
    cell_h = height / spec.rows
    cell_w = width / spec.cols

    extracted: list[ExtractedCell] = []
    for idx, char in enumerate(page_plan.chars):
        row = idx // spec.cols
        col = idx % spec.cols
        y0 = round(row * cell_h)
        y1 = round((row + 1) * cell_h)
        x0 = round(col * cell_w)
        x1 = round((col + 1) * cell_w)

        cell_alpha = alpha_full[y0:y1, x0:x1].copy()
        opaque_ratio = float(np.mean(cell_alpha >= thresholds.alpha_foreground_threshold))
        is_empty = opaque_ratio < thresholds.empty_cell_max_ratio

        extracted.append(
            ExtractedCell(
                char=char,
                codepoint=ord(char),
                row=row,
                col=col,
                page_number=page_number,
                alpha=cell_alpha,
                is_empty=is_empty,
            )
        )

    return extracted
