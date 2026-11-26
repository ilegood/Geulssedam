"""업로드 검증 및 비회원 세션 API Pydantic 스키마."""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field

Severity = Literal["ok", "warning", "error"]
CellStatus = Literal["ok", "warning", "error", "empty", "unused"]


class ValidationIssue(BaseModel):
    """단일 검증 이슈(경고 또는 오류)."""

    code: str = Field(..., description="이슈 식별 코드")
    severity: Literal["warning", "error"] = Field(..., description="심각도")
    message: str = Field(..., description="사용자에게 표시할 한국어 안내 메시지")


class CellMetrics(BaseModel):
    """칸별 측정 수치(디버깅 및 UI 상세 표시용)."""

    opaque_ratio: float = Field(..., description="불투명 글자 픽셀 비율 (0.0~1.0)")
    semitransparent_ratio: float = Field(..., description="유색 픽셀 중 반투명 픽셀 비율")
    estimated_stroke_ratio: float = Field(..., description="칸 크기 대비 추정 평균 획 두께 비율")
    edge_contact_pixels: int = Field(..., description="칸 경계 여백에 닿은 불투명 픽셀 수")


class CellValidationResult(BaseModel):
    """칸 단위 검증 결과."""

    index: int
    row: int
    col: int
    char: str | None
    codepoint: str | None
    status: CellStatus
    issues: list[ValidationIssue] = Field(default_factory=list)
    metrics: CellMetrics | None = None


class FileValidationResult(BaseModel):
    """파일 단위 검증 결과."""

    status: Severity
    width_px: int | None = None
    height_px: int | None = None
    cell_width_px: int | None = None
    cell_height_px: int | None = None
    has_alpha: bool = False
    image_format: str | None = None
    issues: list[ValidationIssue] = Field(default_factory=list)


class ValidationSummary(BaseModel):
    """페이지 검증 결과 요약."""

    total_cells: int
    assigned_cells: int
    ok_count: int
    warning_count: int
    error_count: int
    empty_count: int


class UploadValidationResponse(BaseModel):
    """업로드 및 파일/칸 단위 검증 통합 응답."""

    session_token: str | None = None
    template_version: str
    preset_id: str
    page_number: int
    overall_status: Severity
    saved: bool = Field(..., description="파일 단위 검증을 통과해 서버에 저장되었는지 여부")
    file_validation: FileValidationResult
    summary: ValidationSummary | None = None
    cells: list[CellValidationResult] = Field(default_factory=list)


class SessionCreateRequest(BaseModel):
    """비회원 임시 세션 생성 요청."""

    preset_id: str = Field(default="mvp", description="선택한 문자 범위 프리셋 ID")
    template_version: str = Field(default="v1", description="템플릿 버전")


class UploadedPageSummary(BaseModel):
    """세션 내 업로드된 페이지 요약."""

    page_number: int
    overall_status: Severity
    summary: ValidationSummary | None = None


class SessionInfoResponse(BaseModel):
    """비회원 임시 세션 조회 응답."""

    session_token: str
    preset_id: str
    template_version: str
    created_at: str
    expires_at: str
    uploaded_pages: list[UploadedPageSummary] = Field(default_factory=list)
