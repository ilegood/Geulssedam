"""fontTools 기반 TTF / WOFF2 폰트 조립 및 ZIP 패키징 모듈."""

from __future__ import annotations

import re
import zipfile
from dataclasses import dataclass
from pathlib import Path

from fontTools.fontBuilder import FontBuilder
from fontTools.pens.ttGlyphPen import TTGlyphPen
from fontTools.ttLib import TTFont, newTable

from app.services.glyph_normalizer import (
    FONT_ASCENT,
    FONT_DESCENT,
    UNITS_PER_EM,
    NormalizedGlyph,
)

LICENSE_SUMMARY = (
    "본 폰트의 저작권은 직접 글씨를 작성한 사용자 본인에게 귀속되며, "
    "개인적·상업적 용도로 자유롭게 사용할 수 있습니다. "
    "(타인의 저작물·기존 폰트를 모방하여 생성한 경우 발생하는 책임은 사용자에게 있습니다.)"
)


@dataclass(frozen=True)
class BuiltFontPackage:
    """빌드 완료된 폰트 파일 경로 및 요약 정보."""

    font_name: str
    font_slug: str
    ttf_path: Path
    woff2_path: Path
    zip_path: Path
    included_chars: tuple[str, ...]


def _sanitize_slug(name: str) -> str:
    """파일명 및 PostScript 이름으로 안전한 ASCII 슬러그를 생성합니다."""
    cleaned = re.sub(r"[^A-Za-z0-9_-]+", "", name.strip())
    return cleaned or "GeulssedamHandwriting"


def _build_notdef_glyph() -> object:
    """필수 .notdef 글리프(직사각형 외곽선 + 내부 구멍)를 생성합니다."""
    pen = TTGlyphPen(None)
    # 외곽선 (시계 방향)
    pen.moveTo((60, 0))
    pen.lineTo((60, 700))
    pen.lineTo((440, 700))
    pen.lineTo((440, 0))
    pen.closePath()
    # 내부 구멍 (반시계 방향)
    pen.moveTo((110, 50))
    pen.lineTo((390, 50))
    pen.lineTo((390, 650))
    pen.lineTo((110, 650))
    pen.closePath()
    return pen.glyph()


def _build_empty_glyph() -> object:
    """공백(space) 등 윤곽선이 없는 빈 글리프를 생성합니다."""
    pen = TTGlyphPen(None)
    return pen.glyph()


def _build_tt_glyph(glyph: NormalizedGlyph) -> object:
    """NormalizedGlyph의 닫힌 폴리라인 윤곽선을 TrueType 글리프로 변환합니다."""
    pen = TTGlyphPen(None)
    for contour in glyph.contours:
        if len(contour) < 3:
            continue
        pen.moveTo(contour[0])
        for pt in contour[1:]:
            pen.lineTo(pt)
        pen.closePath()
    return pen.glyph()


def _make_readme_text(font_name: str, author_name: str, included_count: int) -> str:
    """ZIP 다운로드에 함께 동봉할 설치 안내 및 라이선스 문서를 생성합니다."""
    return (
        f"========================================\n"
        f"  {font_name} — 글씨담 (Geulssedam)\n"
        f"========================================\n\n"
        f"- 제작자: {author_name}\n"
        f"- 포함된 글자 수: {included_count}자 (공백 포함)\n\n"
        f"[설치 방법]\n"
        f"1. Windows: .ttf 파일을 우클릭 → [모든 사용자용으로 설치]를 권장합니다.\n"
        f"   (클립스튜디오·포토샵 등 그래픽 프로그램은 설치 후 재시작해야 폰트가 표시됩니다.)\n"
        f"2. macOS: .ttf 파일을 더블 클릭해 서체 관리자에서 [서체 설치]를 누르세요.\n"
        f"3. 웹페이지: .woff2 파일을 CSS @font-face로 불러와 사용할 수 있습니다.\n\n"
        f"[권리 및 라이선스 안내]\n"
        f"{LICENSE_SUMMARY}\n"
    )


def build_font_files(
    glyphs: dict[int, NormalizedGlyph],
    output_dir: Path,
    font_name: str = "MyHandwriting",
    author_name: str = "Geulssedam User",
    letter_spacing: int = 0,
) -> BuiltFontPackage:
    """정규화된 글리프 맵으로부터 TTF, WOFF2, ZIP 패키지를 생성합니다."""
    if not glyphs:
        raise ValueError("폰트를 생성할 글자가 하나도 없습니다. 최소 1글자 이상 그려주세요.")

    output_dir.mkdir(parents=True, exist_ok=True)
    slug = _sanitize_slug(font_name)
    display_name = font_name.strip() or slug

    sorted_glyphs = [glyphs[cp] for cp in sorted(glyphs.keys())]

    glyph_order: list[str] = [".notdef", "space"]
    cmap: dict[int, str] = {0x0020: "space"}
    glyf_table: dict[str, object] = {
        ".notdef": _build_notdef_glyph(),
        "space": _build_empty_glyph(),
    }
    space_width = max(180, 320 + letter_spacing)
    metrics: dict[str, tuple[int, int]] = {
        ".notdef": (500, 60),
        "space": (space_width, 0),
    }

    for glyph in sorted_glyphs:
        if glyph.codepoint == 0x0020:
            continue
        glyph_order.append(glyph.glyph_name)
        cmap[glyph.codepoint] = glyph.glyph_name
        glyf_table[glyph.glyph_name] = _build_tt_glyph(glyph)
        metrics[glyph.glyph_name] = (glyph.advance_width, glyph.lsb)

    # 글리프 실제 Y 범위를 반영해 Windows 클리핑 방지
    max_y = FONT_ASCENT
    min_y = FONT_DESCENT
    has_hangul = False
    for glyph in sorted_glyphs:
        if 0xAC00 <= glyph.codepoint <= 0xD7A3 or 0x3131 <= glyph.codepoint <= 0x318E:
            has_hangul = True
        for contour in glyph.contours:
            for _, y in contour:
                max_y = max(max_y, y)
                min_y = min(min_y, y)

    # Windows GDI / 클립스튜디오 호환 코드페이지 비트 (bit 0: Latin 1, bit 19: Korean Wansung)
    codepage_range_1 = 1 << 0
    if has_hangul:
        codepage_range_1 |= 1 << 19

    fb = FontBuilder(UNITS_PER_EM, isTTF=True)
    fb.setupGlyphOrder(glyph_order)
    fb.setupCharacterMap(cmap)
    fb.setupGlyf(glyf_table)
    fb.setupHorizontalMetrics(metrics)
    fb.setupHorizontalHeader(ascent=FONT_ASCENT, descent=FONT_DESCENT)
    fb.setupNameTable(
        {
            "familyName": display_name,
            "styleName": "Regular",
            "uniqueFontIdentifier": f"Geulssedam-{slug}-Regular",
            "fullName": display_name,
            "psName": f"{slug}-Regular",
            "version": "Version 1.000",
            "designer": author_name,
            "manufacturer": "Geulssedam (글씨담)",
            "licenseDescription": LICENSE_SUMMARY,
        },
        windows=True,
        mac=False,
    )
    fb.setupOS2(
        version=4,
        usWeightClass=400,
        usWidthClass=5,
        fsType=0,  # Installable Embedding (제한 없음)
        fsSelection=0x00C0,  # REGULAR (0x0040) | USE_TYPO_METRICS (0x0080)
        achVendID="GLSD",
        sTypoAscender=FONT_ASCENT,
        sTypoDescender=FONT_DESCENT,
        sTypoLineGap=200,
        usWinAscent=max(FONT_ASCENT, max_y),
        usWinDescent=max(abs(FONT_DESCENT), abs(min_y)),
        ulCodePageRange1=codepage_range_1,
        ulCodePageRange2=0,
        sxHeight=500,
        sCapHeight=700,
    )
    fb.font["OS/2"].recalcUnicodeRanges(fb.font)
    fb.setupPost()

    # Windows / 일부 그래픽 툴(클립스튜디오 등) 호환용 빈 DSIG 테이블 추가
    dsig = newTable("DSIG")
    dsig.ulVersion = 1
    dsig.usFlag = 0
    dsig.usNumSigs = 0
    dsig.signatureRecords = []
    fb.font["DSIG"] = dsig

    ttf_path = output_dir / f"{slug}.ttf"
    woff2_path = output_dir / f"{slug}.woff2"
    zip_path = output_dir / f"{slug}.zip"

    fb.save(str(ttf_path))

    # 저장된 TTF를 다시 열어 WOFF2로 변환 (brotli 압축)
    woff2_font = TTFont(str(ttf_path))
    woff2_font.flavor = "woff2"
    woff2_font.save(str(woff2_path))
    woff2_font.close()

    # TTF + WOFF2 + 설치 안내/라이선스 README를 ZIP으로 패키징
    readme_text = _make_readme_text(display_name, author_name, len(sorted_glyphs))
    with zipfile.ZipFile(zip_path, mode="w", compression=zipfile.ZIP_DEFLATED) as zf:
        zf.write(ttf_path, arcname=ttf_path.name)
        zf.write(woff2_path, arcname=woff2_path.name)
        zf.writestr("안내_및_라이선스.txt", readme_text.encode("utf-8"))

    return BuiltFontPackage(
        font_name=display_name,
        font_slug=slug,
        ttf_path=ttf_path,
        woff2_path=woff2_path,
        zip_path=zip_path,
        included_chars=tuple(g.char for g in sorted_glyphs),
    )
