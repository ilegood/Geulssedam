"""템플릿 생성기 및 CLI 단위 테스트."""

import json
from dataclasses import replace
from pathlib import Path

from PIL import Image

from app.cli.generate_template import main as cli_main
from app.core.template_spec import DEFAULT_TEMPLATE_SPEC
from app.services.template_generator import generate_templates


def test_generate_templates_all_formats(tmp_path: Path) -> None:
    """투명 PNG, 가이드 레이어 PNG, PDF, 좌표 JSON이 규격대로 생성되는지 검증합니다."""
    # 테스트 속도 향상을 위해 칸 크기를 128px(전체 1280x1280px)로 축소해 검증
    test_spec = replace(DEFAULT_TEMPLATE_SPEC, cell_size_px=128)
    result = generate_templates(preset_id="mvp", output_dir=tmp_path, spec=test_spec)

    assert result.total_pages == 3
    assert result.total_chars == 292
    assert len(result.canvas_png_paths) == 3
    assert len(result.guide_png_paths) == 3
    assert result.pdf_path is not None and result.pdf_path.is_file()
    assert result.metadata_path is not None and result.metadata_path.is_file()

    # 1) 투명 배경 드로잉용 PNG 검증: RGBA, 크기 일치, 완전 투명(알파 최댓값 0)
    with Image.open(result.canvas_png_paths[0]) as canvas_img:
        assert canvas_img.mode == "RGBA"
        assert canvas_img.size == (1280, 1280)
        alpha_min, alpha_max = canvas_img.getchannel("A").getextrema()
        assert alpha_min == 0 and alpha_max == 0

    # 2) 가이드 레이어 PNG 검증: RGBA, 크기 일치, 가이드선/힌트가 그려져 불투명 픽셀 존재
    with Image.open(result.guide_png_paths[0]) as guide_img:
        assert guide_img.mode == "RGBA"
        assert guide_img.size == (1280, 1280)
        _, guide_alpha_max = guide_img.getchannel("A").getextrema()
        assert guide_alpha_max > 0

    # 3) PDF 헤더 검증
    pdf_bytes = result.pdf_path.read_bytes()
    assert pdf_bytes.startswith(b"%PDF-")

    # 4) 메타데이터 JSON 좌표 및 문자 매핑 검증
    meta = json.loads(result.metadata_path.read_text(encoding="utf-8"))
    assert meta["template_version"] == "v1"
    assert meta["preset_id"] == "mvp"
    assert meta["total_pages"] == 3
    assert meta["total_chars"] == 292
    assert meta["spec"]["page_width_px"] == 1280
    assert meta["spec"]["page_height_px"] == 1280

    first_page = meta["pages"][0]
    assert first_page["char_count"] == 92
    assert len(first_page["cells"]) == 100

    first_cell = first_page["cells"][0]
    assert first_cell["char"] == "A"
    assert first_cell["codepoint"] == "U+0041"
    assert (first_cell["x"], first_cell["y"]) == (0, 0)
    assert (first_cell["width"], first_cell["height"]) == (128, 128)
    assert first_cell["guides"]["baseline_y"] == round(128 * test_spec.baseline_ratio)

    # 1페이지 93번째 칸(인덱스 92)부터는 빈 칸이어야 함
    assert first_page["cells"][92]["char"] is None
    assert first_page["cells"][92]["codepoint"] is None


def test_cli_generate_template(tmp_path: Path) -> None:
    """CLI 명령으로 템플릿이 정상 생성되는지 검증합니다."""
    exit_code = cli_main(
        [
            "--preset",
            "latin_basic",
            "--output",
            str(tmp_path),
            "--cell-size",
            "128",
            "--formats",
            "png,guide,meta",
        ]
    )
    assert exit_code == 0
    assert (tmp_path / "page_01_canvas.png").is_file()
    assert (tmp_path / "page_01_guide.png").is_file()
    assert (tmp_path / "metadata.json").is_file()
    assert not (tmp_path / "template_latin_basic_v1.pdf").exists()
