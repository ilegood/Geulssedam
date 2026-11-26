"""한글 조합형(6-2-2벌) 테스트 템플릿 생성기 단위 테스트."""

import json
from dataclasses import replace
from pathlib import Path

from PIL import Image

from app.core.charsets import build_page_plans
from app.core.template_spec import DEFAULT_TEMPLATE_SPEC
from app.services.jamo_template_generator import (
    JAMO_PRESET_ID,
    build_jamo_622_pages,
    compose_hangul_syllables_from_jamo,
    generate_jamo_templates,
)
from app.services.template_generator import generate_templates
from app.services.vectorizer import VectorizedGlyph, VectorPath


def test_build_jamo_622_pages_structure() -> None:
    """6-2-2벌 조합형 템플릿이 3페이지(57+57+96=210칸)로 구성되는지 검증합니다."""
    pages = build_jamo_622_pages()
    assert len(pages) == 3
    assert [len(p.slots) for p in pages] == [57, 57, 96]

    all_slots = [slot for page in pages for slot in page.slots]
    assert len(all_slots) == 210
    assert len({slot.slot_id for slot in all_slots}) == 210

    # 초성 1벌 첫 슬롯(ㄱ -> 가), 초성 4벌 첫 슬롯(ㄱ -> 각)
    assert pages[0].slots[0].jamo == "ㄱ"
    assert pages[0].slots[0].sample_syllable == "가"
    assert pages[1].slots[0].jamo == "ㄱ"
    assert pages[1].slots[0].sample_syllable == "각"


def test_generate_jamo_templates_all_formats(tmp_path: Path) -> None:
    """조합형 템플릿의 투명 PNG, 가이드 PNG, PDF, 메타 JSON 생성을 검증합니다."""
    test_spec = replace(DEFAULT_TEMPLATE_SPEC, cell_size_px=128)
    result = generate_jamo_templates(output_dir=tmp_path, spec=test_spec)

    assert result.preset_id == JAMO_PRESET_ID
    assert result.total_pages == 3
    assert result.total_slots == 210
    assert len(result.canvas_png_paths) == 3
    assert len(result.guide_png_paths) == 3
    assert result.pdf_path is not None and result.pdf_path.is_file()
    assert result.metadata_path is not None and result.metadata_path.is_file()

    with Image.open(result.canvas_png_paths[0]) as canvas_img:
        assert canvas_img.mode == "RGBA"
        assert canvas_img.size == (1280, 1280)
        assert canvas_img.getchannel("A").getextrema() == (0, 0)

    with Image.open(result.guide_png_paths[2]) as guide_img:
        assert guide_img.mode == "RGBA"
        assert guide_img.size == (1280, 1280)
        assert guide_img.getchannel("A").getextrema()[1] > 0

    assert result.pdf_path.read_bytes().startswith(b"%PDF-")

    meta = json.loads(result.metadata_path.read_text(encoding="utf-8"))
    assert meta["mode"] == "hangul_jamo_combinatorial"
    assert meta["beol_scheme"] == "6-2-2"
    assert meta["total_pages"] == 3
    assert meta["total_slots"] == 210
    assert meta["pages"][0]["cells"][0]["slot"]["slot_id"] == "cho_1_00"
    assert meta["pages"][0]["cells"][57]["slot"] is None


def test_hangul_jamo_and_combined_presets_include_basic_jamo(tmp_path: Path) -> None:
    """hangul_jamo(4P)와 latin_hangul_jamo(5P)에 기본 단독 자모가 포함되는지 검증합니다."""
    jamo_pages = build_page_plans("hangul_jamo")
    assert len(jamo_pages) == 4
    assert jamo_pages[0].group_id == "hangul_jamo_basic"
    assert len(jamo_pages[0].chars) == 40
    assert "ㄱ" in jamo_pages[0].chars and "ㅏ" in jamo_pages[0].chars

    combined_pages = build_page_plans("latin_hangul_jamo")
    assert len(combined_pages) == 5
    assert [len(p.chars) for p in combined_pages] == [92, 40, 57, 57, 96]

    test_spec = replace(DEFAULT_TEMPLATE_SPEC, cell_size_px=128)
    res = generate_templates("hangul_jamo", output_dir=tmp_path, spec=test_spec)
    assert res.total_pages == 4
    assert res.total_chars == 250
    assert res.pdf_path is not None and res.pdf_path.is_file()

    # cho_1_00(ㄱ) + jung_1_00(ㅏ) -> '가' 조합 검증
    sample_box = VectorizedGlyph(
        contours=(VectorPath(points=((100.0, 100.0), (200.0, 100.0), (200.0, 200.0))),),
        source_width=512,
        source_height=512,
        engine="opencv",
    )
    composed = compose_hangul_syllables_from_jamo(
        {"cho_1_00": sample_box, "jung_1_00": sample_box},
        spec=DEFAULT_TEMPLATE_SPEC,
    )
    assert ord("가") in composed
    assert composed[ord("가")].source == "composed"
