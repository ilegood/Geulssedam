"""칸 분할 → 벡터화 → 정규화 → TTF/WOFF2/ZIP 폰트 빌드 파이프라인 및 API 테스트."""

from __future__ import annotations

import io
import zipfile
from pathlib import Path

from fastapi.testclient import TestClient
from fontTools.ttLib import TTFont
from PIL import Image, ImageDraw

from app.core.config import settings
from app.main import app
from app.services.cell_splitter import split_page_into_cells
from app.services.font_builder import build_font_files
from app.services.glyph_normalizer import (
    NormalizedGlyph,
    merge_glyph_layers,
    normalize_vectorized_glyph,
)
from app.services.vectorizer import _parse_svg_polygon_paths, vectorize_alpha_mask

client = TestClient(app)


def _draw_sample_template_png(
    cell_size: int = 256,
    filled_indices: list[int] | None = None,
) -> bytes:
    """지정한 칸 인덱스에만 도형(도넛/사각형)이 그려진 10×10 투명 PNG를 생성합니다."""
    indices = filled_indices if filled_indices is not None else [0, 1, 2, 52, 53]
    size = cell_size * 10
    img = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    draw = ImageDraw.Draw(img)
    pad = int(cell_size * 0.22)
    stroke = max(16, cell_size // 12)

    for idx in indices:
        row = idx // 10
        col = idx % 10
        x0 = col * cell_size + pad
        y0 = row * cell_size + pad
        x1 = (col + 1) * cell_size - pad
        y1 = (row + 1) * cell_size - pad
        if idx % 2 == 0:
            draw.ellipse([x0, y0, x1, y1], outline=(0, 0, 0, 255), width=stroke)
        else:
            draw.rectangle([x0, y0, x1, y1], outline=(0, 0, 0, 255), width=stroke)

    buf = io.BytesIO()
    img.save(buf, format="PNG")
    return buf.getvalue()


def test_potrace_svg_hole_classification_preserves_donut_hole() -> None:
    """potrace SVG 파싱 시 도넛(O, ㅇ 등)의 내부 구멍이 is_hole=True로 판별되는지 검증합니다."""
    donut_svg = (
        '<?xml version="1.0" standalone="no"?>'
        '<svg xmlns="http://www.w3.org/2000/svg" width="512" height="512">'
        '<g transform="translate(0,512) scale(0.1,-0.1)">'
        '<path d="M1000 1000 L4000 1000 L4000 4000 L1000 4000 Z '
        'M1800 1800 L1800 3200 L3200 3200 L3200 1800 Z"/>'
        "</g></svg>"
    )
    paths = _parse_svg_polygon_paths(donut_svg, height=512)
    assert len(paths) == 2
    assert [p.is_hole for p in paths] == [False, True]


def test_split_vectorize_normalize_and_build_ttf_woff2(tmp_path: Path) -> None:
    """영문('A','B','C') + 숫자('0','1') 합성 PNG로 TTF/WOFF2/ZIP이 정상 조립되는지 검증합니다."""
    # latin_basic 인덱스: 0='A', 1='B', 2='C', 52='0', 53='1'
    png_path = tmp_path / "page_01.png"
    png_path.write_bytes(_draw_sample_template_png(cell_size=256, filled_indices=[0, 1, 2, 52, 53]))

    cells = split_page_into_cells(png_path, preset_id="latin_basic", page_number=1)
    non_empty = [c for c in cells if not c.is_empty]
    assert [c.char for c in non_empty] == ["A", "B", "C", "0", "1"]

    glyphs: dict[int, NormalizedGlyph] = {}
    for cell in non_empty:
        vec = vectorize_alpha_mask(cell.alpha)
        assert len(vec.contours) >= 1
        norm = normalize_vectorized_glyph(cell.char, vec, letter_spacing_delta=20)
        assert norm is not None
        assert norm.advance_width > 0
        glyphs[norm.codepoint] = norm

    pkg = build_font_files(
        glyphs=glyphs,
        output_dir=tmp_path / "out",
        font_name="TestHandFont",
        author_name="지민",
        letter_spacing=20,
    )

    assert pkg.ttf_path.is_file()
    assert pkg.woff2_path.is_file()
    assert pkg.zip_path.is_file()
    assert set(pkg.included_chars) == {"A", "B", "C", "0", "1"}

    # fontTools로 생성된 TTF 실제 파싱 검증
    with TTFont(str(pkg.ttf_path)) as tt:
        cmap = tt.getBestCmap()
        assert 0x0020 in cmap  # space 자동 포함
        assert ord("A") in cmap
        assert ord("0") in cmap
        assert ord("Z") not in cmap  # 미작성 글자 제외
        assert ".notdef" in tt.getGlyphOrder()
        # Windows / 클립스튜디오 호환 OS/2·DSIG·name 테이블 검증
        os2 = tt["OS/2"]
        assert os2.fsType == 0
        assert (os2.fsSelection & 0x0040) != 0  # REGULAR 비트
        assert (os2.ulCodePageRange1 & 1) != 0  # Latin 1 코드페이지
        assert "DSIG" in tt
        assert "ltag" not in tt

    # 생성된 WOFF2 시그니처(wOF2) 검증
    assert pkg.woff2_path.read_bytes()[:4] == b"wOF2"

    # ZIP 내부에 TTF, WOFF2, 라이선스/설치 안내 텍스트 포함 검증
    with zipfile.ZipFile(pkg.zip_path, "r") as zf:
        names = set(zf.namelist())
        assert pkg.ttf_path.name in names
        assert pkg.woff2_path.name in names
        assert "안내_및_라이선스.txt" in names
        readme = zf.read("안내_및_라이선스.txt").decode("utf-8")
        assert "상업적 용도" in readme


def test_hangul_and_override_layer_merge(tmp_path: Path) -> None:
    """한글 200자 페이지 빌드 및 혼합형(Override) 레이어 병합 우선순위를 검증합니다."""
    # hangul_200 인덱스 0='가', 1='간'
    png_path = tmp_path / "hangul_p1.png"
    png_path.write_bytes(_draw_sample_template_png(cell_size=256, filled_indices=[0, 1]))

    cells = split_page_into_cells(png_path, preset_id="hangul_200", page_number=1)
    non_empty = [c for c in cells if not c.is_empty]
    assert [c.char for c in non_empty] == ["가", "간"]

    handwritten: dict[int, NormalizedGlyph] = {}
    for cell in non_empty:
        norm = normalize_vectorized_glyph(cell.char, vectorize_alpha_mask(cell.alpha))
        assert norm is not None
        handwritten[norm.codepoint] = norm

    # 가상의 조합형 레이어에 동일 글자('가')가 있어도 직접 그린 완성형이 우선 덮어써야 함
    fake_composed = {
        ord("가"): NormalizedGlyph(
            char="가",
            codepoint=ord("가"),
            glyph_name="uniAC00",
            contours=(((0, 0), (0, 500), (500, 500), (500, 0)),),
            advance_width=600,
            lsb=50,
            source="composed",
        )
    }
    merged = merge_glyph_layers(fake_composed, handwritten)
    assert merged[ord("가")].source == "handwritten"

    pkg = build_font_files(merged, output_dir=tmp_path / "ko_out", font_name="HangulTest")
    with TTFont(str(pkg.ttf_path)) as tt:
        cmap = tt.getBestCmap()
        assert ord("가") in cmap
        assert ord("간") in cmap


def test_font_build_api_end_to_end(tmp_path: Path, monkeypatch) -> None:
    """업로드 → 비동기 폰트 빌드 요청 → 진행률 조회 → WOFF2 미리보기/ZIP 다운로드 통합 테스트."""
    monkeypatch.setattr(settings, "storage_dir", tmp_path)
    monkeypatch.setattr(settings, "task_backend", "background")

    # 1) 업로드 (자동 세션 발급)
    png_bytes = _draw_sample_template_png(cell_size=256, filled_indices=[0, 1, 52])
    up_res = client.post(
        "/api/uploads",
        data={"preset_id": "latin_basic", "page_number": "1"},
        files={"file": ("page_01.png", png_bytes, "image/png")},
    )
    assert up_res.status_code == 200
    token = up_res.json()["session_token"]

    # 2) 폰트 빌드 시작 (TestClient는 BackgroundTasks를 요청 직후 동기 완료함)
    build_res = client.post(
        "/api/fonts/build",
        json={
            "session_token": token,
            "font_name": "JiminHand",
            "author_name": "지민",
            "letter_spacing": 10,
            "scale_factor": 1.0,
        },
    )
    assert build_res.status_code == 202
    job_id = build_res.json()["job_id"]

    # 3) 작업 상태 조회
    job_res = client.get(f"/api/fonts/jobs/{job_id}")
    assert job_res.status_code == 200
    job_body = job_res.json()
    assert job_body["status"] == "completed"
    assert job_body["progress"] == 100
    assert set(job_body["artifacts"]["included_chars"]) == {"A", "B", "0"}
    assert "Z" in job_body["artifacts"]["missing_chars"]

    # 4) 미리보기 WOFF2 및 ZIP 다운로드 확인
    preview_res = client.get(job_body["artifacts"]["preview_woff2_url"])
    assert preview_res.status_code == 200
    assert preview_res.content[:4] == b"wOF2"

    zip_res = client.get(job_body["artifacts"]["download_zip_url"])
    assert zip_res.status_code == 200
    assert zip_res.content[:2] == b"PK"
