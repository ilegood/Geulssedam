"""FastAPI 애플리케이션 엔트리포인트."""

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.fonts import router as fonts_router
from app.api.templates import router as templates_router
from app.api.uploads import router as uploads_router
from app.core.config import settings
from app.core.template_spec import DEFAULT_TEMPLATE_SPEC

app = FastAPI(
    title=settings.app_name,
    version=settings.app_version,
    description="투명 배경 PNG 손글씨 템플릿을 TTF/WOFF2 폰트로 변환하는 API",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origin_list,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(templates_router)
app.include_router(uploads_router)
app.include_router(fonts_router)


@app.get("/health", tags=["system"])
def health_check() -> dict[str, object]:
    """서버 상태 및 기본 템플릿 규격 요약을 반환합니다."""
    return {
        "status": "ok",
        "service": settings.app_name,
        "version": settings.app_version,
        "task_backend": settings.task_backend,
        "template_version": DEFAULT_TEMPLATE_SPEC.version,
        "template_page_px": [
            DEFAULT_TEMPLATE_SPEC.page_width_px,
            DEFAULT_TEMPLATE_SPEC.page_height_px,
        ],
    }
