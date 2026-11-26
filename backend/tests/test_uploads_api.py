"""업로드·세션·프리셋 API 통합 테스트."""

from __future__ import annotations

import io
from pathlib import Path

from fastapi.testclient import TestClient
from PIL import Image, ImageDraw

from app.core.config import settings
from app.main import app

client = TestClient(app)


def _make_sample_page_png(cell_size: int = 256, fill_cells: int = 3) -> bytes:
    """테스트용 10×10 투명 PNG 페이지를 합성합니다."""
    size = cell_size * 10
    img = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    draw = ImageDraw.Draw(img)
    pad = int(cell_size * 0.22)
    stroke = max(14, cell_size // 12)

    for idx in range(fill_cells):
        row = idx // 10
        col = idx % 10
        x0 = col * cell_size + pad
        y0 = row * cell_size + pad
        x1 = (col + 1) * cell_size - pad
        y1 = (row + 1) * cell_size - pad
        draw.ellipse([x0, y0, x1, y1], outline=(0, 0, 0, 255), width=stroke)

    buf = io.BytesIO()
    img.save(buf, format="PNG")
    return buf.getvalue()


def test_list_template_presets() -> None:
    """GET /api/templates/presets가 MVP 프리셋 정보를 반환하는지 확인합니다."""
    res = client.get("/api/templates/presets")
    assert res.status_code == 200
    body = res.json()
    preset_ids = {p["id"] for p in body["presets"]}
    assert {"latin_basic", "hangul_200", "mvp"}.issubset(preset_ids)


def test_session_and_upload_lifecycle(tmp_path: Path, monkeypatch) -> None:
    """세션 생성 → PNG 업로드/검증 → 세션 조회 흐름을 검증합니다."""
    monkeypatch.setattr(settings, "storage_dir", tmp_path)

    # 1) 세션 생성
    create_res = client.post("/api/sessions", json={"preset_id": "latin_basic"})
    assert create_res.status_code == 201
    token = create_res.json()["session_token"]

    # 2) 정상 규격(2560×2560, 3칸 작성) PNG 업로드
    png_bytes = _make_sample_page_png(cell_size=256, fill_cells=3)
    upload_res = client.post(
        "/api/uploads",
        data={
            "preset_id": "latin_basic",
            "page_number": "1",
            "session_token": token,
        },
        files={"file": ("page_01.png", png_bytes, "image/png")},
    )
    assert upload_res.status_code == 200
    body = upload_res.json()
    assert body["saved"] is True
    assert body["session_token"] == token
    assert body["summary"]["ok_count"] == 3
    assert body["summary"]["empty_count"] == 89
    assert len(body["cells"]) == 100

    # 3) 세션 조회 시 업로드된 페이지가 포함되어야 함
    session_res = client.get(f"/api/sessions/{token}")
    assert session_res.status_code == 200
    session_body = session_res.json()
    assert len(session_body["uploaded_pages"]) == 1
    assert session_body["uploaded_pages"][0]["page_number"] == 1


def test_upload_rejects_low_resolution_with_422(tmp_path: Path, monkeypatch) -> None:
    """최소 해상도 미만 파일 업로드 시 HTTP 422와 구조화된 오류를 반환해야 합니다."""
    monkeypatch.setattr(settings, "storage_dir", tmp_path)

    small_img = Image.new("RGBA", (1000, 1000), (0, 0, 0, 0))
    buf = io.BytesIO()
    small_img.save(buf, format="PNG")

    res = client.post(
        "/api/uploads",
        data={"preset_id": "latin_basic", "page_number": "1"},
        files={"file": ("small.png", buf.getvalue(), "image/png")},
    )
    assert res.status_code == 422
    body = res.json()
    assert body["saved"] is False
    assert body["file_validation"]["status"] == "error"
    assert any(i["code"] == "resolution_too_low" for i in body["file_validation"]["issues"])
