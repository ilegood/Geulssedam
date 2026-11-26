"""템플릿 생성기 서비스.

지정한 문자 세트 프리셋과 템플릿 규격(TemplateSpec)을 바탕으로 다음 산출물을 생성합니다.
1. 투명 배경 드로잉용 PNG (canvas) — 사용자가 글자를 그리는 빈 투명 레이어
2. 가이드/힌트 레이어 PNG (guide) — 칸 경계, 베이스라인/x-height 가이드선, 연한 정답 글자 힌트
3. 인쇄용 PDF — A4 세로 페이지에 헤더(버전/페이지 번호/작성 안내)와 10×10 그리드
4. 좌표 메타데이터 JSON — 템플릿 버전, 페이지별 칸 좌표, 가이드선 Y좌표, 매핑 문자
"""

from __future__ import annotations

import json
from collections.abc import Iterable
from dataclasses import dataclass
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont
from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.units import mm
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.pdfgen import canvas as rl_canvas

from app.core.charsets import PagePlan, build_page_plans, get_preset
from app.core.template_spec import DEFAULT_TEMPLATE_SPEC, TemplateSpec

# 가이드 레이어 색상 (RGBA)
COLOR_GRID_BORDER = (160, 174, 192, 190)
COLOR_SAFE_MARGIN = (203, 213, 225, 110)
COLOR_ASCENDER = (147, 197, 253, 150)
COLOR_X_HEIGHT = (96, 165, 250, 165)
COLOR_BASELINE = (239, 68, 68, 195)
COLOR_DESCENDER = (147, 197, 253, 150)
COLOR_HINT_CHAR = (148, 163, 184, 95)
COLOR_LABEL_TEXT = (71, 85, 105, 190)
COLOR_HEADER_MARK = (30, 41, 59, 175)

# 한글 지원 시스템 폰트 후보 경로 (Windows / Linux / macOS)
CANDIDATE_FONT_PATHS: tuple[str, ...] = (
    "C:/Windows/Fonts/malgun.ttf",
    "C:/Windows/Fonts/malgunsl.ttf",
    "C:/Windows/Fonts/NanumGothic.ttf",
    "/usr/share/fonts/opentype/noto/NotoSansCJK-Regular.ttc",
    "/usr/share/fonts/truetype/noto/NotoSansKR-Regular.ttf",
    "/usr/share/fonts/truetype/nanum/NanumGothic.ttf",
    "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
    "/System/Library/Fonts/AppleSDGothicNeo.ttc",
)

SUPPORTED_FORMATS = frozenset({"png", "guide", "pdf", "meta"})


@dataclass(frozen=True)
class GeneratedTemplateResult:
    """템플릿 생성 결과 요약."""

    preset_id: str
    template_version: str
    output_dir: Path
    total_pages: int
    total_chars: int
    canvas_png_paths: tuple[Path, ...]
    guide_png_paths: tuple[Path, ...]
    pdf_path: Path | None
    metadata_path: Path | None


def find_system_font_path() -> Path | None:
    """한글·영문 렌더링이 가능한 시스템 폰트 파일을 탐색합니다."""
    for candidate in CANDIDATE_FONT_PATHS:
        path = Path(candidate)
        if path.is_file():
            return path
    return None


def _load_pil_font(font_path: Path | None, size: int) -> ImageFont.ImageFont:
    """Pillow용 폰트를 로드합니다. 시스템 폰트가 없으면 기본 폰트로 폴백합니다."""
    if font_path is not None:
        try:
            return ImageFont.truetype(str(font_path), size=size)
        except OSError:
            pass
    return ImageFont.load_default()


def _draw_dashed_line(
    draw: ImageDraw.ImageDraw,
    x0: int,
    y0: int,
    x1: int,
    y1: int,
    fill: tuple[int, int, int, int],
    width: int = 2,
    dash_len: int = 12,
    gap_len: int = 8,
) -> None:
    """수평 또는 수직 점선을 그립니다."""
    if y0 == y1:
        x = x0
        while x < x1:
            end_x = min(x + dash_len, x1)
            draw.line([(x, y0), (end_x, y1)], fill=fill, width=width)
            x += dash_len + gap_len
    elif x0 == x1:
        y = y0
        while y < y1:
            end_y = min(y + dash_len, y1)
            draw.line([(x0, y), (x1, end_y)], fill=fill, width=width)
            y += dash_len + gap_len
    else:
        draw.line([(x0, y0), (x1, y1)], fill=fill, width=width)


def build_page_metadata(page: PagePlan, spec: TemplateSpec) -> dict[str, object]:
    """단일 페이지의 칸 좌표 및 문자 매핑 메타데이터 딕셔너리를 생성합니다."""
    cell_size = spec.cell_size_px
    cells: list[dict[str, object]] = []

    for idx in range(spec.cells_per_page):
        row = idx // spec.cols
        col = idx % spec.cols
        x = col * cell_size
        y = row * cell_size
        char = page.chars[idx] if idx < len(page.chars) else None

        cells.append(
            {
                "index": idx,
                "row": row,
                "col": col,
                "char": char,
                "codepoint": f"U+{ord(char):04X}" if char is not None else None,
                "x": x,
                "y": y,
                "width": cell_size,
                "height": cell_size,
                "guides": {
                    "ascender_y": round(y + cell_size * spec.ascender_ratio),
                    "x_height_y": round(y + cell_size * spec.x_height_ratio),
                    "baseline_y": round(y + cell_size * spec.baseline_ratio),
                    "descender_y": round(y + cell_size * spec.descender_ratio),
                },
            }
        )

    return {
        "page_number": page.page_number,
        "total_pages": page.total_pages,
        "group_id": page.group_id,
        "group_name": page.group_name,
        "char_count": len(page.chars),
        "canvas_png": f"page_{page.page_number:02d}_canvas.png",
        "guide_png": f"page_{page.page_number:02d}_guide.png",
        "cells": cells,
    }


def render_canvas_png(spec: TemplateSpec, output_path: Path) -> Path:
    """사용자가 글자를 그리는 완전 투명 배경 PNG를 생성합니다."""
    img = Image.new("RGBA", (spec.page_width_px, spec.page_height_px), (0, 0, 0, 0))
    img.save(output_path, format="PNG", optimize=True)
    return output_path


def render_guide_png(
    page: PagePlan,
    spec: TemplateSpec,
    output_path: Path,
    font_path: Path | None = None,
) -> Path:
    """칸 경계, 가이드선, 연한 정답 글자 힌트가 그려진 별도 가이드 레이어 PNG를 생성합니다."""
    cell = spec.cell_size_px
    img = Image.new("RGBA", (spec.page_width_px, spec.page_height_px), (0, 0, 0, 0))
    draw = ImageDraw.Draw(img)

    hint_font = _load_pil_font(font_path, max(16, int(cell * 0.46)))
    label_font = _load_pil_font(font_path, max(10, int(cell * 0.055)))
    mark_font = _load_pil_font(font_path, max(12, int(cell * 0.045)))

    border_w = max(1, cell // 256)
    line_w = max(1, cell // 256)
    dash = max(4, cell // 40)
    gap = max(3, cell // 60)

    for idx in range(spec.cells_per_page):
        row = idx // spec.cols
        col = idx % spec.cols
        x0 = col * cell
        y0 = row * cell
        x1 = x0 + cell - 1
        y1 = y0 + cell - 1

        # 칸 외곽선
        draw.rectangle([x0, y0, x1, y1], outline=COLOR_GRID_BORDER, width=border_w)

        # 안전 여백 박스
        margin = int(cell * spec.safe_margin_ratio)
        draw.rectangle(
            [x0 + margin, y0 + margin, x1 - margin, y1 - margin],
            outline=COLOR_SAFE_MARGIN,
            width=1,
        )

        # 타이포그래피 가이드선 (ascender / x-height / baseline / descender)
        asc_y = y0 + int(cell * spec.ascender_ratio)
        xh_y = y0 + int(cell * spec.x_height_ratio)
        base_y = y0 + int(cell * spec.baseline_ratio)
        desc_y = y0 + int(cell * spec.descender_ratio)

        _draw_dashed_line(
            draw, x0 + margin, asc_y, x1 - margin, asc_y, COLOR_ASCENDER, line_w, dash, gap
        )
        _draw_dashed_line(
            draw, x0 + margin, xh_y, x1 - margin, xh_y, COLOR_X_HEIGHT, line_w, dash, gap
        )
        draw.line([(x0 + margin, base_y), (x1 - margin, base_y)], fill=COLOR_BASELINE, width=line_w)
        _draw_dashed_line(
            draw, x0 + margin, desc_y, x1 - margin, desc_y, COLOR_DESCENDER, line_w, dash, gap
        )

        if idx < len(page.chars):
            char = page.chars[idx]
            # 칸 좌상단 번호 + 정답 문자 라벨
            label = f"{idx + 1:02d} {char}"
            draw.text(
                (x0 + margin, y0 + max(2, margin // 4)),
                label,
                fill=COLOR_LABEL_TEXT,
                font=label_font,
            )

            # 중앙 연한 정답 글자 힌트 (베이스라인 근방 중앙 정렬)
            bbox = draw.textbbox((0, 0), char, font=hint_font)
            text_w = bbox[2] - bbox[0]
            text_h = bbox[3] - bbox[1]
            text_x = x0 + (cell - text_w) // 2 - bbox[0]
            text_y = y0 + int(cell * 0.50) - text_h // 2 - bbox[1]
            draw.text((text_x, text_y), char, fill=COLOR_HINT_CHAR, font=hint_font)

    # 페이지 버전 및 번호 식별 워터마크 (좌하단 안전 여백 내)
    page_mark = (
        f"Geulssedam {spec.version} | {page.group_id} | "
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


def render_template_pdf(
    pages: list[PagePlan],
    preset_name: str,
    spec: TemplateSpec,
    output_path: Path,
    font_path: Path | None = None,
) -> Path:
    """인쇄용 다중 페이지 PDF 템플릿을 생성합니다."""
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
        # 상단 헤더 영역
        pdf.setFillColor(colors.HexColor("#1e293b"))
        pdf.setFont(font_name, 14)
        pdf.drawString(
            margin_x,
            page_h - 18 * mm,
            f"글씨담 (Geulssedam) 손글씨 템플릿 — {spec.version}",
        )

        pdf.setFont(font_name, 9.5)
        pdf.setFillColor(colors.HexColor("#475569"))
        pdf.drawString(
            margin_x,
            page_h - 25 * mm,
            f"세트: {preset_name} | 그룹: {page.group_name} | "
            f"페이지: {page.page_number} / {page.total_pages}",
        )
        pdf.drawString(
            margin_x,
            page_h - 31 * mm,
            "안내: 칸 안쪽 여백을 두고 단색·단단한 브러시로 그려주세요. "
            "업로드 전 가이드 레이어는 숨겨주세요.",
        )

        # 10×10 그리드 및 칸별 가이드선/힌트
        for idx in range(spec.cells_per_page):
            row = idx // spec.cols
            col = idx % spec.cols
            x0 = margin_x + col * cell_pt
            y_top = grid_top - row * cell_pt
            y_bottom = y_top - cell_pt

            # 칸 외곽선
            pdf.setStrokeColor(colors.HexColor("#94a3b8"))
            pdf.setLineWidth(0.5)
            pdf.rect(x0, y_bottom, cell_pt, cell_pt, stroke=1, fill=0)

            # 베이스라인(빨간 실선) & x-height(파란 점선)
            inner_pad = cell_pt * spec.safe_margin_ratio
            base_y = y_top - cell_pt * spec.baseline_ratio
            xh_y = y_top - cell_pt * spec.x_height_ratio

            pdf.setStrokeColor(colors.HexColor("#fca5a5"))
            pdf.setLineWidth(0.4)
            pdf.line(x0 + inner_pad, base_y, x0 + cell_pt - inner_pad, base_y)

            pdf.setStrokeColor(colors.HexColor("#bfdbfe"))
            pdf.setDash(2, 2)
            pdf.line(x0 + inner_pad, xh_y, x0 + cell_pt - inner_pad, xh_y)
            pdf.setDash()

            if idx < len(page.chars):
                char = page.chars[idx]
                # 좌상단 작은 라벨
                pdf.setFillColor(colors.HexColor("#64748b"))
                pdf.setFont(font_name, 5.5)
                pdf.drawString(x0 + 1.5, y_top - 6.5, f"{idx + 1:02d}")

                # 중앙 연한 힌트 글자
                pdf.setFillColor(colors.HexColor("#cbd5e1"))
                pdf.setFont(font_name, cell_pt * 0.48)
                pdf.drawCentredString(x0 + cell_pt / 2, base_y + cell_pt * 0.06, char)

        # 하단 푸터
        pdf.setFillColor(colors.HexColor("#64748b"))
        pdf.setFont(font_name, 8)
        pdf.drawString(
            margin_x,
            14 * mm,
            f"규격: {spec.cols}x{spec.rows}칸 · 표준 {spec.page_width_px}x{spec.page_height_px}px "
            f"(칸당 {spec.cell_size_px}px 권장, 최소 {spec.min_cell_size_px}px)",
        )
        pdf.drawRightString(
            page_w - margin_x,
            14 * mm,
            f"Template {spec.version} | Page {page.page_number}/{page.total_pages}",
        )

        pdf.showPage()

    pdf.save()
    return output_path


def generate_templates(
    preset_id: str,
    output_dir: Path,
    spec: TemplateSpec = DEFAULT_TEMPLATE_SPEC,
    formats: Iterable[str] = ("png", "guide", "pdf", "meta"),
) -> GeneratedTemplateResult:
    """선택한 프리셋에 대해 PNG, 가이드 레이어 PNG, PDF, 메타데이터 JSON을 생성합니다."""
    selected_formats = {fmt.strip().lower() for fmt in formats if fmt.strip()}
    invalid = selected_formats - SUPPORTED_FORMATS
    if invalid:
        raise ValueError(f"지원하지 않는 출력 형식입니다: {', '.join(sorted(invalid))}")

    preset = get_preset(preset_id)
    pages = build_page_plans(preset_id, cells_per_page=spec.cells_per_page)
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
            render_guide_png(page, spec, guide_path, font_path=font_path)
            guide_paths.append(guide_path)

        page_metas.append(build_page_metadata(page, spec))

    pdf_path: Path | None = None
    if "pdf" in selected_formats:
        pdf_path = output_dir / f"template_{preset_id}_{spec.version}.pdf"
        render_template_pdf(pages, preset.name, spec, pdf_path, font_path=font_path)

    metadata_path: Path | None = None
    total_chars = sum(len(page.chars) for page in pages)
    if "meta" in selected_formats:
        metadata_path = output_dir / "metadata.json"
        metadata_payload = {
            "service": "Geulssedam",
            "template_version": spec.version,
            "preset_id": preset.id,
            "preset_name": preset.name,
            "total_pages": len(pages),
            "total_chars": total_chars,
            "spec": {
                "rows": spec.rows,
                "cols": spec.cols,
                "cells_per_page": spec.cells_per_page,
                "cell_size_px": spec.cell_size_px,
                "min_cell_size_px": spec.min_cell_size_px,
                "recommended_cell_size_px": spec.recommended_cell_size_px,
                "page_width_px": spec.page_width_px,
                "page_height_px": spec.page_height_px,
                "guide_ratios": {
                    "ascender": spec.ascender_ratio,
                    "x_height": spec.x_height_ratio,
                    "baseline": spec.baseline_ratio,
                    "descender": spec.descender_ratio,
                    "safe_margin": spec.safe_margin_ratio,
                },
            },
            "pdf_file": pdf_path.name if pdf_path is not None else None,
            "pages": page_metas,
        }
        metadata_path.write_text(
            json.dumps(metadata_payload, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )

    return GeneratedTemplateResult(
        preset_id=preset.id,
        template_version=spec.version,
        output_dir=output_dir,
        total_pages=len(pages),
        total_chars=total_chars,
        canvas_png_paths=tuple(canvas_paths),
        guide_png_paths=tuple(guide_paths),
        pdf_path=pdf_path,
        metadata_path=metadata_path,
    )
