"""파일 및 칸 단위 업로드 검증 로직 단위 테스트.

테스트용 샘플 이미지는 모두 Pillow/NumPy로 코드에서 직접 합성합니다.
"""

from __future__ import annotations

import io

import numpy as np
from PIL import Image, ImageDraw

from app.services.validator import validate_cell_alpha, validate_uploaded_page


def _encode_image(img: Image.Image, fmt: str = "PNG") -> bytes:
    buf = io.BytesIO()
    img.save(buf, format=fmt)
    return buf.getvalue()


def _make_clean_glyph_cell(size: int = 256, stroke_width: int = 18) -> np.ndarray:
    """여백과 충분한 획 두께를 가진 정상 글자(O 모양) 알파 채널을 합성합니다."""
    img = Image.new("L", (size, size), 0)
    draw = ImageDraw.Draw(img)
    pad = int(size * 0.22)
    draw.ellipse([pad, pad, size - pad, size - pad], outline=255, width=stroke_width)
    return np.array(img, dtype=np.uint8)


def test_file_rejects_non_png() -> None:
    """JPEG 등 PNG가 아닌 파일은 거부(error)되어야 합니다."""
    img = Image.new("RGB", (2560, 2560), (255, 255, 255))
    res = validate_uploaded_page(
        _encode_image(img, fmt="JPEG"),
        preset_id="latin_basic",
        page_number=1,
    )
    assert res.overall_status == "error"
    assert not res.saved
    codes = {i.code for i in res.file_validation.issues}
    assert "invalid_format" in codes


def test_file_rejects_png_without_alpha() -> None:
    """알파 채널이 없는 RGB PNG는 거부(error)되어야 합니다."""
    img = Image.new("RGB", (2560, 2560), (255, 255, 255))
    res = validate_uploaded_page(_encode_image(img), preset_id="latin_basic", page_number=1)
    assert res.overall_status == "error"
    assert not res.saved
    assert any(i.code == "missing_alpha" for i in res.file_validation.issues)


def test_file_rejects_wrong_aspect_ratio() -> None:
    """10×10(1:1) 비율과 다른 이미지는 거부(error)되어야 합니다."""
    img = Image.new("RGBA", (3000, 2560), (0, 0, 0, 0))
    res = validate_uploaded_page(_encode_image(img), preset_id="latin_basic", page_number=1)
    assert res.overall_status == "error"
    assert any(i.code == "invalid_aspect_ratio" for i in res.file_validation.issues)


def test_file_rejects_resolution_below_minimum() -> None:
    """칸당 256px 미만(전체 2,560px 미만)은 거부(error)되어야 합니다."""
    img = Image.new("RGBA", (2000, 2000), (0, 0, 0, 0))
    res = validate_uploaded_page(_encode_image(img), preset_id="latin_basic", page_number=1)
    assert res.overall_status == "error"
    assert any(i.code == "resolution_too_low" for i in res.file_validation.issues)


def test_file_warns_below_recommended_resolution() -> None:
    """칸당 256px 이상 512px 미만은 허용하되 품질 경고(warning)를 반환해야 합니다."""
    img = Image.new("RGBA", (2560, 2560), (0, 0, 0, 0))
    res = validate_uploaded_page(_encode_image(img), preset_id="latin_basic", page_number=1)
    assert res.saved is True
    assert res.file_validation.status == "warning"
    assert any(i.code == "resolution_below_recommended" for i in res.file_validation.issues)


def test_file_warns_opaque_background() -> None:
    """투명 배경이 아닌 불투명 흰 배경 RGBA PNG는 경고를 반환해야 합니다."""
    img = Image.new("RGBA", (2560, 2560), (255, 255, 255, 255))
    res = validate_uploaded_page(_encode_image(img), preset_id="latin_basic", page_number=1)
    assert any(i.code == "opaque_background" for i in res.file_validation.issues)


def test_cell_ok_clean_glyph() -> None:
    """정상 두께와 여백을 가진 글자 칸은 ok 상태여야 합니다."""
    alpha = _make_clean_glyph_cell(size=256, stroke_width=20)
    cell = validate_cell_alpha(alpha, index=0, row=0, col=0, char="A")
    assert cell.status == "ok"
    assert cell.issues == []
    assert cell.metrics is not None
    assert cell.metrics.estimated_stroke_ratio >= 0.03


def test_cell_empty() -> None:
    """아무것도 그려지지 않은 칸은 empty 상태와 빈 칸 메시지를 반환해야 합니다."""
    alpha = np.zeros((256, 256), dtype=np.uint8)
    cell = validate_cell_alpha(alpha, index=0, row=0, col=0, char="A")
    assert cell.status == "empty"
    assert any(i.code == "empty_cell" for i in cell.issues)


def test_cell_overfilled() -> None:
    """불투명 픽셀이 과도하게 채워진 칸은 overfilled_cell 오류를 반환해야 합니다."""
    alpha = np.full((256, 256), 255, dtype=np.uint8)
    cell = validate_cell_alpha(alpha, index=0, row=0, col=0, char="A")
    assert cell.status == "error"
    assert any(i.code == "overfilled_cell" for i in cell.issues)


def test_cell_edge_clipped() -> None:
    """칸 가장자리에 글자가 닿아 있으면 edge_clipped 경고를 반환해야 합니다."""
    alpha = _make_clean_glyph_cell(size=256, stroke_width=20)
    # 상단 경계에 닿는 획 추가
    alpha[0:20, 110:140] = 255
    cell = validate_cell_alpha(alpha, index=0, row=0, col=0, char="A")
    assert any(i.code == "edge_clipped" for i in cell.issues)


def test_cell_thin_stroke() -> None:
    """획 두께가 칸 크기의 3% 미만이면 thin_stroke 경고를 반환해야 합니다."""
    alpha = _make_clean_glyph_cell(size=256, stroke_width=2)
    cell = validate_cell_alpha(alpha, index=0, row=0, col=0, char="A")
    assert any(i.code == "thin_stroke" for i in cell.issues)


def test_cell_semitransparent_excess() -> None:
    """반투명 픽셀 비율이 과다하면 semitransparent_excess 경고를 반환해야 합니다."""
    img = Image.new("L", (256, 256), 0)
    draw = ImageDraw.Draw(img)
    # 반투명(알파 160) 브러시로 넓게 그림
    draw.ellipse([50, 50, 206, 206], outline=160, width=24)
    alpha = np.array(img, dtype=np.uint8)
    cell = validate_cell_alpha(alpha, index=0, row=0, col=0, char="A")
    assert any(i.code == "semitransparent_excess" for i in cell.issues)


def test_cell_guide_line_detected() -> None:
    """칸을 가로지르는 직선 가이드선이 남아 있으면 guide_line_detected 경고를 반환해야 합니다."""
    alpha = _make_clean_glyph_cell(size=256, stroke_width=20)
    # 베이스라인 위치에 칸 전체를 가로지르는 연한 가이드선 추가
    alpha[200:202, 5:251] = 180
    cell = validate_cell_alpha(alpha, index=0, row=0, col=0, char="A")
    assert any(i.code == "guide_line_detected" for i in cell.issues)
