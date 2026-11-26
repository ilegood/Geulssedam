"""템플릿 프리셋, 비회원 세션, 업로드 및 검증 API 라우터."""

from __future__ import annotations

from dataclasses import replace
from typing import Annotated

from fastapi import APIRouter, File, Form, HTTPException, UploadFile, status
from fastapi.responses import JSONResponse

from app.core.charsets import TEMPLATE_PRESETS, build_page_plans, get_preset
from app.core.config import settings
from app.core.template_spec import DEFAULT_TEMPLATE_SPEC
from app.schemas.validation import (
    SessionCreateRequest,
    SessionInfoResponse,
    UploadValidationResponse,
)
from app.services.session_store import create_session, get_session, save_uploaded_page
from app.services.validator import validate_uploaded_page

router = APIRouter(prefix="/api", tags=["uploads"])


@router.get("/templates/presets")
def list_template_presets() -> dict[str, object]:
    """선택 가능한 문자 범위 프리셋 목록과 페이지 수·글자 수를 반환합니다."""
    presets = []
    for preset in TEMPLATE_PRESETS.values():
        pages = build_page_plans(preset.id, cells_per_page=DEFAULT_TEMPLATE_SPEC.cells_per_page)
        presets.append(
            {
                "id": preset.id,
                "name": preset.name,
                "description": preset.description,
                "stage": preset.stage,
                "total_pages": len(pages),
                "total_chars": sum(len(p.chars) for p in pages),
            }
        )
    return {
        "template_version": DEFAULT_TEMPLATE_SPEC.version,
        "presets": presets,
    }


@router.post("/sessions", response_model=SessionInfoResponse, status_code=status.HTTP_201_CREATED)
def create_guest_session(payload: SessionCreateRequest) -> SessionInfoResponse:
    """회원가입 없이 작업할 수 있는 임시 링크(토큰) 세션을 생성합니다."""
    try:
        get_preset(payload.preset_id)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc

    return create_session(
        preset_id=payload.preset_id,
        template_version=payload.template_version,
    )


@router.get("/sessions/{session_token}", response_model=SessionInfoResponse)
def read_guest_session(session_token: str) -> SessionInfoResponse:
    """임시 세션 정보와 업로드된 페이지별 검증 요약을 조회합니다."""
    try:
        session = get_session(session_token)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc

    if session is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="세션을 찾을 수 없거나 만료되었습니다.",
        )
    return session


@router.post(
    "/uploads",
    response_model=UploadValidationResponse,
    responses={
        413: {"description": "업로드 파일 용량 초과"},
        422: {"description": "파일 단위 규격 검증 실패", "model": UploadValidationResponse},
    },
)
async def upload_template_page(
    file: Annotated[UploadFile, File(description="투명 배경 템플릿 PNG 파일")],
    preset_id: Annotated[str, Form(description="문자 세트 프리셋 ID")] = "mvp",
    page_number: Annotated[int, Form(ge=1, description="업로드하는 템플릿 페이지 번호")] = 1,
    template_version: Annotated[
        str, Form(description="템플릿 버전")
    ] = DEFAULT_TEMPLATE_SPEC.version,
    session_token: Annotated[
        str | None, Form(description="기존 임시 세션 토큰(생략 시 자동 발급)")
    ] = None,
) -> UploadValidationResponse | JSONResponse:
    """템플릿 PNG를 업로드받아 파일·칸 단위 품질 검증을 수행하고 결과를 반환합니다."""
    image_bytes = await file.read()
    if len(image_bytes) > settings.max_upload_bytes:
        raise HTTPException(
            status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
            detail=(
                f"파일 크기가 너무 큽니다. 최대 {settings.max_upload_mb}MB까지 "
                "업로드할 수 있어요."
            ),
        )

    # 세션 토큰 확인 또는 자동 발급
    active_token = session_token
    if active_token:
        try:
            existing = get_session(active_token)
        except ValueError as exc:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc
        if existing is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="지정한 세션 토큰을 찾을 수 없습니다.",
            )
    else:
        try:
            get_preset(preset_id)
        except ValueError as exc:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc
        active_token = create_session(
            preset_id=preset_id,
            template_version=template_version,
        ).session_token

    spec = replace(DEFAULT_TEMPLATE_SPEC, version=template_version)
    try:
        result = validate_uploaded_page(
            image_bytes=image_bytes,
            preset_id=preset_id,
            page_number=page_number,
            spec=spec,
            session_token=active_token,
        )
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc

    if result.file_validation.status == "error":
        return JSONResponse(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            content=result.model_dump(),
        )

    save_uploaded_page(
        session_token=active_token,
        page_number=page_number,
        image_bytes=image_bytes,
        validation_result=result,
    )
    return result
