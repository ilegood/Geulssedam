"""한글 벌 기반 자모 조합형(6-2-2벌) 테스트 템플릿 생성기.

한글 11,172자 조합 확장을 사전 테스트할 수 있도록 6-2-2벌 자모 템플릿을 생성합니다.
- 1페이지 (57칸): 초성 1~3벌 (받침 없는 세로/가로/복합모음)
- 2페이지 (57칸): 초성 4~6벌 (받침 있는 세로/가로/복합모음)
- 3페이지 (96칸): 중성 1~2벌 (42칸) + 종성 1~2벌 (54칸)
총 210칸(3페이지), 기존 10×10칸(5,120×5,120px) 규격과 동일합니다.
"""

from __future__ import annotations

import json
from collections.abc import Iterable
from dataclasses import dataclass
from pathlib import Path
from typing import Literal

from PIL import Image, ImageDraw
from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.units import mm
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.pdfgen import canvas as rl_canvas

from app.core.template_spec import DEFAULT_TEMPLATE_SPEC, TemplateSpec
from app.services.glyph_normalizer import NormalizedGlyph, normalize_vectorized_glyph
from app.services.template_generator import (
    COLOR_GRID_BORDER,
    COLOR_HEADER_MARK,
    COLOR_LABEL_TEXT,
    COLOR_SAFE_MARGIN,
    SUPPORTED_FORMATS,
    _draw_dashed_line,
    _load_pil_font,
    find_system_font_path,
    render_canvas_png,
)
from app.services.vectorizer import VectorizedGlyph

JAMO_POSITIONAL_GROUP_IDS = frozenset(
    {"hangul_jamo_cho13", "hangul_jamo_cho46", "hangul_jamo_jung_jong"}
)

JamoRole = Literal["choseong", "jungseong", "jongseong"]

JAMO_PRESET_ID = "hangul_jamo_622"
JAMO_PRESET_NAME = "한글 조합형 테스트 (6-2-2벌, 210칸)"

CHOSEONG_LIST: tuple[str, ...] = (
    "ㄱ", "ㄲ", "ㄴ", "ㄷ", "ㄸ", "ㄹ", "ㅁ", "ㅂ", "ㅃ", "ㅅ",
    "ㅆ", "ㅇ", "ㅈ", "ㅉ", "ㅊ", "ㅋ", "ㅌ", "ㅍ", "ㅎ",
)
JUNGSEONG_LIST: tuple[str, ...] = (
    "ㅏ", "ㅐ", "ㅑ", "ㅒ", "ㅓ", "ㅔ", "ㅕ", "ㅖ", "ㅗ", "ㅘ",
    "ㅙ", "ㅚ", "ㅛ", "ㅜ", "ㅝ", "ㅞ", "ㅟ", "ㅠ", "ㅡ", "ㅢ", "ㅣ",
)
JONGSEONG_LIST: tuple[str, ...] = (
    "ㄱ", "ㄲ", "ㄳ", "ㄴ", "ㄵ", "ㄶ", "ㄷ", "ㄹ", "ㄺ", "ㄻ",
    "ㄼ", "ㄽ", "ㄾ", "ㄿ", "ㅀ", "ㅁ", "ㅂ", "ㅄ", "ㅅ", "ㅆ",
    "ㅇ", "ㅈ", "ㅊ", "ㅋ", "ㅌ", "ㅍ", "ㅎ",
)

VERTICAL_VOWELS = frozenset({"ㅏ", "ㅐ", "ㅑ", "ㅒ", "ㅓ", "ㅔ", "ㅕ", "ㅖ", "ㅣ"})
HORIZONTAL_VOWELS = frozenset({"ㅗ", "ㅛ", "ㅜ", "ㅠ", "ㅡ"})
COMPOUND_VOWELS = frozenset({"ㅘ", "ㅙ", "ㅚ", "ㅝ", "ㅞ", "ㅟ", "ㅢ"})

# 역할별 배치 영역 가이드 박스 색상 (RGBA)
ROLE_FILL_COLORS: dict[JamoRole, tuple[int, int, int, int]] = {
    "choseong": (59, 130, 246, 36),   # 파랑 (초성)
    "jungseong": (16, 185, 129, 36),  # 초록 (중성)
    "jongseong": (245, 158, 11, 40),  # 주황 (종성)
}
ROLE_STROKE_COLORS: dict[JamoRole, tuple[int, int, int, int]] = {
    "choseong": (37, 99, 235, 150),
    "jungseong": (5, 150, 105, 150),
    "jongseong": (217, 119, 6, 160),
}
ROLE_PDF_FILL_HEX: dict[JamoRole, str] = {
    "choseong": "#eff6ff",
    "jungseong": "#ecfdf5",
    "jongseong": "#fffbeb",
}
ROLE_PDF_STROKE_HEX: dict[JamoRole, str] = {
    "choseong": "#93c5fd",
    "jungseong": "#6ee7b7",
    "jongseong": "#fcd34d",
}
COLOR_SYLLABLE_HINT = (148, 163, 184, 88)


@dataclass(frozen=True)
class JamoSlot:
    """조합형 템플릿의 단일 자모 슬롯 정의."""

    slot_id: str
    role: JamoRole
    beol: int
    beol_label: str
    beol_desc: str
    jamo: str
    sample_syllable: str
    # 칸 내부 상대 좌표 (x0, y0, x1, y1), 0.0~1.0
    target_box: tuple[float, float, float, float]


@dataclass(frozen=True)
class JamoPagePlan:
    """조합형 템플릿 단일 페이지 배치 계획."""

    page_number: int
    total_pages: int
    section_id: str
    section_name: str
    section_guide: str
    slots: tuple[JamoSlot, ...]


@dataclass(frozen=True)
class GeneratedJamoTemplateResult:
    """조합형 템플릿 생성 결과 요약."""

    preset_id: str
    template_version: str
    output_dir: Path
    total_pages: int
    total_slots: int
    canvas_png_paths: tuple[Path, ...]
    guide_png_paths: tuple[Path, ...]
    pdf_path: Path | None
    metadata_path: Path | None


def _compose_syllable(cho_idx: int, jung_idx: int, jong_idx: int = 0) -> str:
    """초성(0~18), 중성(0~20), 종성(0~27, 0은 없음) 인덱스로 완성형 음절을 만듭니다."""
    return chr(0xAC00 + (cho_idx * 21 + jung_idx) * 28 + jong_idx)


def _jungseong_box(vowel: str, has_jongseong: bool) -> tuple[float, float, float, float]:
    """모음 유형과 받침 유무에 따른 중성 권장 배치 영역을 반환합니다."""
    if not has_jongseong:
        if vowel in VERTICAL_VOWELS:
            return (0.56, 0.20, 0.82, 0.84)
        if vowel in HORIZONTAL_VOWELS:
            return (0.18, 0.54, 0.82, 0.80)
        return (0.18, 0.20, 0.82, 0.84)

    if vowel in VERTICAL_VOWELS:
        return (0.56, 0.20, 0.82, 0.60)
    if vowel in HORIZONTAL_VOWELS:
        return (0.18, 0.44, 0.82, 0.60)
    return (0.18, 0.20, 0.82, 0.62)


def build_jamo_622_pages() -> list[JamoPagePlan]:
    """6-2-2벌 조합형 템플릿의 3페이지(총 210칸) 슬롯 계획을 생성합니다."""
    # 초성 6벌 정의: (벌번호, 짧은라벨, 설명, 예시중성인덱스, 예시종성인덱스, 배치영역)
    # 중성 인덱스: ㅏ=0, ㅗ=8, ㅘ=9 / 종성 인덱스: 없음=0, ㄱ=1
    cho_beols: tuple[tuple[int, str, str, int, int, tuple[float, float, float, float]], ...] = (
        (1, "초1", "받침X·세로모음(가)", 0, 0, (0.18, 0.22, 0.56, 0.76)),
        (2, "초2", "받침X·가로모음(고)", 8, 0, (0.24, 0.22, 0.76, 0.56)),
        (3, "초3", "받침X·복합모음(과)", 9, 0, (0.20, 0.22, 0.56, 0.56)),
        (4, "초4", "받침O·세로모음(각)", 0, 1, (0.18, 0.20, 0.56, 0.56)),
        (5, "초5", "받침O·가로모음(곡)", 8, 1, (0.24, 0.20, 0.76, 0.46)),
        (6, "초6", "받침O·복합모음(곽)", 9, 1, (0.20, 0.20, 0.56, 0.46)),
    )

    page1_slots: list[JamoSlot] = []
    for beol, label, desc, jung_i, jong_i, box in cho_beols[:3]:
        for cho_i, jamo in enumerate(CHOSEONG_LIST):
            page1_slots.append(
                JamoSlot(
                    slot_id=f"cho_{beol}_{cho_i:02d}",
                    role="choseong",
                    beol=beol,
                    beol_label=label,
                    beol_desc=desc,
                    jamo=jamo,
                    sample_syllable=_compose_syllable(cho_i, jung_i, jong_i),
                    target_box=box,
                )
            )

    page2_slots: list[JamoSlot] = []
    for beol, label, desc, jung_i, jong_i, box in cho_beols[3:]:
        for cho_i, jamo in enumerate(CHOSEONG_LIST):
            page2_slots.append(
                JamoSlot(
                    slot_id=f"cho_{beol}_{cho_i:02d}",
                    role="choseong",
                    beol=beol,
                    beol_label=label,
                    beol_desc=desc,
                    jamo=jamo,
                    sample_syllable=_compose_syllable(cho_i, jung_i, jong_i),
                    target_box=box,
                )
            )

    page3_slots: list[JamoSlot] = []
    # 중성 1벌 (받침 없음, 예시 초성 ㅇ=11)
    for jung_i, vowel in enumerate(JUNGSEONG_LIST):
        page3_slots.append(
            JamoSlot(
                slot_id=f"jung_1_{jung_i:02d}",
                role="jungseong",
                beol=1,
                beol_label="중1",
                beol_desc="받침 없는 모음",
                jamo=vowel,
                sample_syllable=_compose_syllable(11, jung_i, 0),
                target_box=_jungseong_box(vowel, has_jongseong=False),
            )
        )
    # 중성 2벌 (받침 있음, 예시 초성 ㅇ=11, 종성 ㄴ=4)
    for jung_i, vowel in enumerate(JUNGSEONG_LIST):
        page3_slots.append(
            JamoSlot(
                slot_id=f"jung_2_{jung_i:02d}",
                role="jungseong",
                beol=2,
                beol_label="중2",
                beol_desc="받침 있는 모음",
                jamo=vowel,
                sample_syllable=_compose_syllable(11, jung_i, 4),
                target_box=_jungseong_box(vowel, has_jongseong=True),
            )
        )
    # 종성 1벌 (세로·복합모음 아래, 예시 ㅇ+ㅏ+종성)
    for idx, jamo in enumerate(JONGSEONG_LIST):
        jong_i = idx + 1
        page3_slots.append(
            JamoSlot(
                slot_id=f"jong_1_{jong_i:02d}",
                role="jongseong",
                beol=1,
                beol_label="종1",
                beol_desc="세로·복합모음 받침",
                jamo=jamo,
                sample_syllable=_compose_syllable(11, 0, jong_i),
                target_box=(0.22, 0.58, 0.78, 0.84),
            )
        )
    # 종성 2벌 (가로모음 아래, 예시 ㅇ+ㅗ+종성)
    for idx, jamo in enumerate(JONGSEONG_LIST):
        jong_i = idx + 1
        page3_slots.append(
            JamoSlot(
                slot_id=f"jong_2_{jong_i:02d}",
                role="jongseong",
                beol=2,
                beol_label="종2",
                beol_desc="가로모음 받침",
                jamo=jamo,
                sample_syllable=_compose_syllable(11, 8, jong_i),
                target_box=(0.22, 0.60, 0.78, 0.84),
            )
        )

    return [
        JamoPagePlan(
            page_number=1,
            total_pages=3,
            section_id="choseong_no_jong",
            section_name="초성 1~3벌 (받침 없는 글자용, 57칸)",
            section_guide=(
                "파란 영역 안에 해당 자음(초성)만 그려주세요. "
                "연한 글자는 위치 참고용 예시입니다."
            ),
            slots=tuple(page1_slots),
        ),
        JamoPagePlan(
            page_number=2,
            total_pages=3,
            section_id="choseong_with_jong",
            section_name="초성 4~6벌 (받침 있는 글자용, 57칸)",
            section_guide=(
                "받침 공간이 아래에 들어가므로 파란 영역에 맞춰 "
                "초성을 조금 납작·작게 그려주세요."
            ),
            slots=tuple(page2_slots),
        ),
        JamoPagePlan(
            page_number=3,
            total_pages=3,
            section_id="jungseong_and_jongseong",
            section_name="중성 1~2벌(42칸) + 종성 1~2벌(54칸)",
            section_guide="초록 영역에는 모음(중성)만, 주황 영역에는 받침(종성)만 그려주세요.",
            slots=tuple(page3_slots),
        ),
    ]


def get_jamo_page_plan_for_group(
    group_id: str,
    page_number: int,
    total_pages: int,
) -> JamoPagePlan | None:
    """문자 그룹 ID에 해당하는 6-2-2벌 JamoPagePlan을 페이지 번호에 맞춰 반환합니다."""
    group_index_map = {
        "hangul_jamo_cho13": 0,
        "hangul_jamo_cho46": 1,
        "hangul_jamo_jung_jong": 2,
    }
    idx = group_index_map.get(group_id)
    if idx is None:
        return None
    base = build_jamo_622_pages()[idx]
    return JamoPagePlan(
        page_number=page_number,
        total_pages=total_pages,
        section_id=base.section_id,
        section_name=base.section_name,
        section_guide=base.section_guide,
        slots=base.slots,
    )


def draw_jamo_pdf_page(
    pdf: rl_canvas.Canvas,
    page: JamoPagePlan,
    spec: TemplateSpec,
    font_name: str,
) -> None:
    """기존 PDF 캔버스에 6-2-2벌 조합형 단일 페이지를 그립니다."""
    page_w, page_h = A4
    margin_x = 15 * mm
    grid_size = page_w - 2 * margin_x
    cell_pt = grid_size / spec.cols
    grid_bottom = 25 * mm
    grid_top = grid_bottom + grid_size

    pdf.setFillColor(colors.HexColor("#1e293b"))
    pdf.setFont(font_name, 13.5)
    pdf.drawString(
        margin_x,
        page_h - 17 * mm,
        f"글씨담 (Geulssedam) 한글 조합형(6-2-2벌) 템플릿 — {spec.version}",
    )

    pdf.setFont(font_name, 9)
    pdf.setFillColor(colors.HexColor("#475569"))
    pdf.drawString(
        margin_x,
        page_h - 24 * mm,
        f"구성: {page.section_name} | 페이지: {page.page_number} / {page.total_pages}",
    )
    pdf.drawString(
        margin_x,
        page_h - 30 * mm,
        f"작성 팁: {page.section_guide}",
    )

    for idx in range(spec.cells_per_page):
        row = idx // spec.cols
        col = idx % spec.cols
        x0 = margin_x + col * cell_pt
        y_top = grid_top - row * cell_pt
        y_bottom = y_top - cell_pt

        if idx < len(page.slots):
            slot = page.slots[idx]
            tx0, ty0, tx1, ty1 = slot.target_box
            bx = x0 + cell_pt * tx0
            by_bottom = y_top - cell_pt * ty1
            bw = cell_pt * (tx1 - tx0)
            bh = cell_pt * (ty1 - ty0)

            pdf.setFillColor(colors.HexColor(ROLE_PDF_FILL_HEX[slot.role]))
            pdf.setStrokeColor(colors.HexColor(ROLE_PDF_STROKE_HEX[slot.role]))
            pdf.setLineWidth(0.45)
            pdf.rect(bx, by_bottom, bw, bh, stroke=1, fill=1)

        pdf.setStrokeColor(colors.HexColor("#94a3b8"))
        pdf.setLineWidth(0.5)
        pdf.rect(x0, y_bottom, cell_pt, cell_pt, stroke=1, fill=0)

        if idx < len(page.slots):
            slot = page.slots[idx]
            pdf.setFillColor(colors.HexColor("#475569"))
            pdf.setFont(font_name, 4.8)
            pdf.drawString(
                x0 + 1.5,
                y_top - 5.8,
                f"{slot.beol_label} {slot.jamo}({slot.sample_syllable})",
            )

            pdf.setFillColor(colors.HexColor("#cbd5e1"))
            pdf.setFont(font_name, cell_pt * 0.62)
            pdf.drawCentredString(
                x0 + cell_pt / 2,
                y_bottom + cell_pt * 0.22,
                slot.sample_syllable,
            )

    pdf.setFillColor(colors.HexColor("#64748b"))
    pdf.setFont(font_name, 8)
    pdf.drawString(
        margin_x,
        14 * mm,
        "범례: 파랑=초성 영역 · 초록=중성 영역 · 주황=종성 영역 | "
        f"표준 {spec.page_width_px}x{spec.page_height_px}px (칸당 {spec.cell_size_px}px)",
    )
    pdf.drawRightString(
        page_w - margin_x,
        14 * mm,
        f"Jamo 6-2-2 {spec.version} | Page {page.page_number}/{page.total_pages}",
    )
    pdf.showPage()


def compose_hangul_syllables_from_jamo(
    jamo_vectors: dict[str, VectorizedGlyph],
    spec: TemplateSpec = DEFAULT_TEMPLATE_SPEC,
    letter_spacing_delta: int = 0,
    scale_factor: float = 1.0,
) -> dict[int, NormalizedGlyph]:
    """벡터화된 6-2-2벌 자모 슬롯들을 조합해 한글 완성형 음절 글리프 맵을 생성합니다."""
    if not jamo_vectors:
        return {}

    composed: dict[int, NormalizedGlyph] = {}
    for cho_i in range(19):
        for jung_i, vowel in enumerate(JUNGSEONG_LIST):
            is_vert = vowel in VERTICAL_VOWELS
            is_horiz = vowel in HORIZONTAL_VOWELS
            for jong_i in range(28):
                has_jong = jong_i > 0
                if not has_jong:
                    cho_beol = 1 if is_vert else (2 if is_horiz else 3)
                    jung_beol = 1
                else:
                    cho_beol = 4 if is_vert else (5 if is_horiz else 6)
                    jung_beol = 2

                cho_vec = jamo_vectors.get(f"cho_{cho_beol}_{cho_i:02d}")
                jung_vec = jamo_vectors.get(f"jung_{jung_beol}_{jung_i:02d}")
                if cho_vec is None or jung_vec is None:
                    continue

                contours = list(cho_vec.contours) + list(jung_vec.contours)
                if has_jong:
                    jong_beol = 2 if is_horiz else 1
                    jong_vec = jamo_vectors.get(f"jong_{jong_beol}_{jong_i:02d}")
                    if jong_vec is None:
                        continue
                    contours.extend(jong_vec.contours)

                syllable = _compose_syllable(cho_i, jung_i, jong_i)
                combined = VectorizedGlyph(
                    contours=tuple(contours),
                    source_width=cho_vec.source_width,
                    source_height=cho_vec.source_height,
                    engine=cho_vec.engine,
                )
                normalized = normalize_vectorized_glyph(
                    char=syllable,
                    vectorized=combined,
                    spec=spec,
                    letter_spacing_delta=letter_spacing_delta,
                    scale_factor=scale_factor,
                )
                if normalized is not None:
                    composed[normalized.codepoint] = NormalizedGlyph(
                        char=normalized.char,
                        codepoint=normalized.codepoint,
                        glyph_name=normalized.glyph_name,
                        contours=normalized.contours,
                        advance_width=normalized.advance_width,
                        lsb=normalized.lsb,
                        source="composed",
                    )

    return composed


def _build_jamo_page_metadata(page: JamoPagePlan, spec: TemplateSpec) -> dict[str, object]:
    """조합형 템플릿 단일 페이지의 메타데이터 딕셔너리를 생성합니다."""
    cell = spec.cell_size_px
    cells: list[dict[str, object]] = []

    for idx in range(spec.cells_per_page):
        row = idx // spec.cols
        col = idx % spec.cols
        x = col * cell
        y = row * cell
        slot = page.slots[idx] if idx < len(page.slots) else None

        if slot is not None:
            tx0, ty0, tx1, ty1 = slot.target_box
            slot_payload: dict[str, object] | None = {
                "slot_id": slot.slot_id,
                "role": slot.role,
                "beol": slot.beol,
                "beol_label": slot.beol_label,
                "beol_desc": slot.beol_desc,
                "jamo": slot.jamo,
                "sample_syllable": slot.sample_syllable,
                "target_box_ratio": [tx0, ty0, tx1, ty1],
                "target_box_px": {
                    "x0": round(x + cell * tx0),
                    "y0": round(y + cell * ty0),
                    "x1": round(x + cell * tx1),
                    "y1": round(y + cell * ty1),
                },
            }
        else:
            slot_payload = None

        cells.append(
            {
                "index": idx,
                "row": row,
                "col": col,
                "x": x,
                "y": y,
                "width": cell,
                "height": cell,
                "slot": slot_payload,
            }
        )

    return {
        "page_number": page.page_number,
        "total_pages": page.total_pages,
        "section_id": page.section_id,
        "section_name": page.section_name,
        "section_guide": page.section_guide,
        "slot_count": len(page.slots),
        "canvas_png": f"page_{page.page_number:02d}_canvas.png",
        "guide_png": f"page_{page.page_number:02d}_guide.png",
        "cells": cells,
    }


def render_jamo_guide_png(
    page: JamoPagePlan,
    spec: TemplateSpec,
    output_path: Path,
    font_path: Path | None = None,
) -> Path:
    """배치 영역 박스와 예시 음절 힌트가 포함된 조합형 가이드 레이어 PNG를 생성합니다."""
    cell = spec.cell_size_px
    img = Image.new("RGBA", (spec.page_width_px, spec.page_height_px), (0, 0, 0, 0))
    draw = ImageDraw.Draw(img, "RGBA")

    hint_font = _load_pil_font(font_path, max(16, int(cell * 0.66)))
    label_font = _load_pil_font(font_path, max(10, int(cell * 0.062)))
    mark_font = _load_pil_font(font_path, max(12, int(cell * 0.045)))

    border_w = max(1, cell // 256)
    dash = max(4, cell // 40)
    gap = max(3, cell // 60)

    for idx in range(spec.cells_per_page):
        row = idx // spec.cols
        col = idx % spec.cols
        x0 = col * cell
        y0 = row * cell
        x1 = x0 + cell - 1
        y1 = y0 + cell - 1

        # 칸 외곽선 & 안전 여백
        draw.rectangle([x0, y0, x1, y1], outline=COLOR_GRID_BORDER, width=border_w)
        margin = int(cell * spec.safe_margin_ratio)
        draw.rectangle(
            [x0 + margin, y0 + margin, x1 - margin, y1 - margin],
            outline=COLOR_SAFE_MARGIN,
            width=1,
        )

        # 중앙 십자 보조 점선 (자모 균형 참고용)
        mid_x = x0 + cell // 2
        mid_y = y0 + cell // 2
        _draw_dashed_line(
            draw, x0 + margin, mid_y, x1 - margin, mid_y, (203, 213, 225, 110), 1, dash, gap
        )
        _draw_dashed_line(
            draw, mid_x, y0 + margin, mid_x, y1 - margin, (203, 213, 225, 110), 1, dash, gap
        )

        if idx < len(page.slots):
            slot = page.slots[idx]
            tx0, ty0, tx1, ty1 = slot.target_box
            bx0 = x0 + int(cell * tx0)
            by0 = y0 + int(cell * ty0)
            bx1 = x0 + int(cell * tx1)
            by1 = y0 + int(cell * ty1)

            # 자모 배치 권장 영역 하이라이트 박스
            draw.rectangle(
                [bx0, by0, bx1, by1],
                fill=ROLE_FILL_COLORS[slot.role],
                outline=ROLE_STROKE_COLORS[slot.role],
                width=max(1, border_w),
            )

            # 연한 예시 완성 음절 힌트 (칸 중앙)
            bbox = draw.textbbox((0, 0), slot.sample_syllable, font=hint_font)
            text_w = bbox[2] - bbox[0]
            text_h = bbox[3] - bbox[1]
            text_x = x0 + (cell - text_w) // 2 - bbox[0]
            text_y = y0 + int(cell * 0.52) - text_h // 2 - bbox[1]
            draw.text(
                (text_x, text_y),
                slot.sample_syllable,
                fill=COLOR_SYLLABLE_HINT,
                font=hint_font,
            )

            # 칸 좌상단 라벨: 번호 + 벌 + 자모 + (예시)
            label = f"{idx + 1:02d} {slot.beol_label} {slot.jamo} ({slot.sample_syllable})"
            draw.text(
                (x0 + margin, y0 + max(2, margin // 5)),
                label,
                fill=COLOR_LABEL_TEXT,
                font=label_font,
            )

    page_mark = (
        f"Geulssedam {spec.version} | {JAMO_PRESET_ID} | {page.section_id} | "
        f"P{page.page_number:02d}/{page.total_pages:02d}"
    )
    pad = max(6, int(cell * 0.02))
    draw.text(
        (pad, spec.page_height_px - int(cell * 0.065)),
        page_mark,
        fill=COLOR_HEADER_MARK,
        font=mark_font,
    )

    img.save(output_path, format="PNG", optimize=True)
    return output_path


def render_jamo_template_pdf(
    pages: list[JamoPagePlan],
    spec: TemplateSpec,
    output_path: Path,
    font_path: Path | None = None,
) -> Path:
    """인쇄·참고용 6-2-2벌 조합형 PDF 템플릿을 생성합니다."""
    pdf = rl_canvas.Canvas(str(output_path), pagesize=A4)
    page_w, page_h = A4

    font_name = "Helvetica"
    if font_path is not None and font_path.suffix.lower() == ".ttf":
        try:
            registered_name = "GeulssedamHintFont"
            if registered_name not in pdfmetrics.getRegisteredFontNames():
                pdfmetrics.registerFont(TTFont(registered_name, str(font_path)))
            font_name = registered_name
        except Exception:
            font_name = "Helvetica"

    margin_x = 15 * mm
    grid_size = page_w - 2 * margin_x
    cell_pt = grid_size / spec.cols
    grid_bottom = 25 * mm
    grid_top = grid_bottom + grid_size

    for page in pages:
        pdf.setFillColor(colors.HexColor("#1e293b"))
        pdf.setFont(font_name, 13.5)
        pdf.drawString(
            margin_x,
            page_h - 17 * mm,
            f"글씨담 (Geulssedam) 한글 조합형(6-2-2벌) 테스트 템플릿 — {spec.version}",
        )

        pdf.setFont(font_name, 9)
        pdf.setFillColor(colors.HexColor("#475569"))
        pdf.drawString(
            margin_x,
            page_h - 24 * mm,
            f"구성: {page.section_name} | 페이지: {page.page_number} / {page.total_pages}",
        )
        pdf.drawString(
            margin_x,
            page_h - 30 * mm,
            f"작성 팁: {page.section_guide}",
        )

        for idx in range(spec.cells_per_page):
            row = idx // spec.cols
            col = idx % spec.cols
            x0 = margin_x + col * cell_pt
            y_top = grid_top - row * cell_pt
            y_bottom = y_top - cell_pt

            if idx < len(page.slots):
                slot = page.slots[idx]
                tx0, ty0, tx1, ty1 = slot.target_box
                bx = x0 + cell_pt * tx0
                by_bottom = y_top - cell_pt * ty1
                bw = cell_pt * (tx1 - tx0)
                bh = cell_pt * (ty1 - ty0)

                pdf.setFillColor(colors.HexColor(ROLE_PDF_FILL_HEX[slot.role]))
                pdf.setStrokeColor(colors.HexColor(ROLE_PDF_STROKE_HEX[slot.role]))
                pdf.setLineWidth(0.45)
                pdf.rect(bx, by_bottom, bw, bh, stroke=1, fill=1)

            # 칸 외곽선
            pdf.setStrokeColor(colors.HexColor("#94a3b8"))
            pdf.setLineWidth(0.5)
            pdf.rect(x0, y_bottom, cell_pt, cell_pt, stroke=1, fill=0)

            if idx < len(page.slots):
                slot = page.slots[idx]
                pdf.setFillColor(colors.HexColor("#475569"))
                pdf.setFont(font_name, 4.8)
                pdf.drawString(
                    x0 + 1.5,
                    y_top - 5.8,
                    f"{slot.beol_label} {slot.jamo}({slot.sample_syllable})",
                )

                pdf.setFillColor(colors.HexColor("#cbd5e1"))
                pdf.setFont(font_name, cell_pt * 0.50)
                pdf.drawCentredString(
                    x0 + cell_pt / 2,
                    y_bottom + cell_pt * 0.24,
                    slot.sample_syllable,
                )

        pdf.setFillColor(colors.HexColor("#64748b"))
        pdf.setFont(font_name, 8)
        pdf.drawString(
            margin_x,
            14 * mm,
            "범례: 파랑=초성 영역 · 초록=중성 영역 · 주황=종성 영역 | "
            f"표준 {spec.page_width_px}x{spec.page_height_px}px (칸당 {spec.cell_size_px}px)",
        )
        pdf.drawRightString(
            page_w - margin_x,
            14 * mm,
            f"Jamo 6-2-2 {spec.version} | Page {page.page_number}/{page.total_pages}",
        )
        pdf.showPage()

    pdf.save()
    return output_path


def generate_jamo_templates(
    output_dir: Path,
    spec: TemplateSpec = DEFAULT_TEMPLATE_SPEC,
    formats: Iterable[str] = ("png", "guide", "pdf", "meta"),
) -> GeneratedJamoTemplateResult:
    """6-2-2벌 한글 조합형 테스트 템플릿(PNG, 가이드 PNG, PDF, 메타 JSON)을 생성합니다."""
    selected_formats = {fmt.strip().lower() for fmt in formats if fmt.strip()}
    invalid = selected_formats - SUPPORTED_FORMATS
    if invalid:
        raise ValueError(f"지원하지 않는 출력 형식입니다: {', '.join(sorted(invalid))}")

    pages = build_jamo_622_pages()
    output_dir.mkdir(parents=True, exist_ok=True)
    font_path = find_system_font_path()

    canvas_paths: list[Path] = []
    guide_paths: list[Path] = []
    page_metas: list[dict[str, object]] = []

    for page in pages:
        if "png" in selected_formats:
            canvas_path = output_dir / f"page_{page.page_number:02d}_canvas.png"
            render_canvas_png(spec, canvas_path)
            canvas_paths.append(canvas_path)

        if "guide" in selected_formats:
            guide_path = output_dir / f"page_{page.page_number:02d}_guide.png"
            render_jamo_guide_png(page, spec, guide_path, font_path=font_path)
            guide_paths.append(guide_path)

        page_metas.append(_build_jamo_page_metadata(page, spec))

    pdf_path: Path | None = None
    if "pdf" in selected_formats:
        pdf_path = output_dir / f"template_{JAMO_PRESET_ID}_{spec.version}.pdf"
        render_jamo_template_pdf(pages, spec, pdf_path, font_path=font_path)

    metadata_path: Path | None = None
    total_slots = sum(len(page.slots) for page in pages)
    if "meta" in selected_formats:
        metadata_path = output_dir / "metadata.json"
        metadata_payload = {
            "service": "Geulssedam",
            "mode": "hangul_jamo_combinatorial",
            "beol_scheme": "6-2-2",
            "template_version": spec.version,
            "preset_id": JAMO_PRESET_ID,
            "preset_name": JAMO_PRESET_NAME,
            "total_pages": len(pages),
            "total_slots": total_slots,
            "spec": {
                "rows": spec.rows,
                "cols": spec.cols,
                "cells_per_page": spec.cells_per_page,
                "cell_size_px": spec.cell_size_px,
                "page_width_px": spec.page_width_px,
                "page_height_px": spec.page_height_px,
            },
            "pdf_file": pdf_path.name if pdf_path is not None else None,
            "pages": page_metas,
        }
        metadata_path.write_text(
            json.dumps(metadata_payload, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )

    return GeneratedJamoTemplateResult(
        preset_id=JAMO_PRESET_ID,
        template_version=spec.version,
        output_dir=output_dir,
        total_pages=len(pages),
        total_slots=total_slots,
        canvas_png_paths=tuple(canvas_paths),
        guide_png_paths=tuple(guide_paths),
        pdf_path=pdf_path,
        metadata_path=metadata_path,
    )
