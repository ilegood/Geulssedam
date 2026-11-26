"""한글 조합형(6-2-2벌) 테스트 템플릿 생성기 단위 테스트."""

import json
from dataclasses import replace
from pathlib import Path

from PIL import Image

from app.core.template_spec import DEFAULT_TEMPLATE_SPEC
from app.services.jamo_template_generator import (
    JAMO_PRESET_ID,
    build_jamo_622_pages,
    generate_jamo_templates,
)


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
