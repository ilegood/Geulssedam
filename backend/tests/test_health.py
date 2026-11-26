"""기본 헬스체크 및 설정 테스트."""

from fastapi.testclient import TestClient

from app.core.template_spec import DEFAULT_TEMPLATE_SPEC
from app.main import app

client = TestClient(app)


def test_health_check() -> None:
    """GET /health가 정상 응답과 템플릿 기본 규격을 반환하는지 검증합니다."""
    response = client.get("/health")
    assert response.status_code == 200

    body = response.json()
    assert body["status"] == "ok"
    assert body["template_version"] == DEFAULT_TEMPLATE_SPEC.version
    assert body["template_page_px"] == [5120, 5120]
