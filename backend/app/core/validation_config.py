"""업로드 파일 및 칸 단위 품질 검증 임계값 설정.

모든 임계값을 이 모듈에서 중앙 관리하여 튜닝과 테스트가 용이하도록 합니다.
"""

from dataclasses import dataclass


@dataclass(frozen=True)
class ValidationThresholds:
    """파일 및 칸별 품질 진단 임계값."""

    # 파일 단위 검증
    aspect_ratio_tolerance: float = 0.01  # 허용 비율 오차 (1%)
    # 불투명 픽셀 비율이 이 이상이면 배경이 투명하지 않다고 판단
    opaque_background_ratio: float = 0.85

    # 알파 채널 기준값 (0~255)
    alpha_foreground_threshold: int = 128  # 글자 픽셀로 인정할 최소 알파값
    alpha_semitransparent_low: int = 16
    alpha_semitransparent_high: int = 239

    # 칸 단위 검증
    empty_cell_max_ratio: float = 0.002  # 불투명 픽셀 비율이 이 미만이면 빈 칸
    overfilled_cell_min_ratio: float = 0.65  # 불투명 픽셀 비율이 이 초과이면 너무 꽉 참
    edge_clip_margin_px: int = 3  # 칸 경계에서 검사할 가장자리 픽셀 폭
    edge_clip_min_pixels: int = 5  # 경계에 닿은 픽셀이 이 이상이면 잘림 의심
    min_stroke_width_ratio: float = 0.03  # 칸 크기 대비 최소 평균 획 두께 (3%)
    max_semitransparent_ratio: float = 0.35  # 전체 유색 픽셀 중 반투명 픽셀 비율 상한
    # 칸 가로/세로를 가로지르는 직선 길이 비율 (가이드선 잔존 감지)
    guide_line_span_ratio: float = 0.85


DEFAULT_VALIDATION_THRESHOLDS = ValidationThresholds()
