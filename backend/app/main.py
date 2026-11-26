"""FastAPI 애플리케이션 엔트리포인트."""

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

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


@app.exception_handler(Exception)
async def unhandled_exception_handler(request: Request, exc: Exception) -> JSONResponse:
    """예상치 못한 서버 오류 시에도 CORS 헤더가 유지되는 일관된 JSON 오류를 반환합니다."""
    return JSONResponse(
        status_code=500,
        content={
            "detail": f"서버 처리 중 오류가 발생했습니다: {type(exc).__name__}",
        },
    )


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
