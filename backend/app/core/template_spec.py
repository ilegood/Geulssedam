"""템플릿 규격 상수 정의.

칸 수, 해상도, 가이드선 비율 등 템플릿 관련 모든 수치를 한 곳에서 관리해
향후 문자 세트 확장이나 템플릿 버전 업그레이드를 쉽게 할 수 있도록 합니다.
"""

from dataclasses import dataclass


@dataclass(frozen=True)
class TemplateSpec:
    """단일 템플릿 페이지 규격."""

    version: str = "v1"
    rows: int = 10
    cols: int = 10
    cell_size_px: int = 512
    min_cell_size_px: int = 256
    recommended_cell_size_px: int = 512

    # 칸 내부 가이드선 비율 (칸 상단 = 0.0, 칸 하단 = 1.0 기준)
    ascender_ratio: float = 0.15
    x_height_ratio: float = 0.42
    baseline_ratio: float = 0.78
    descender_ratio: float = 0.92
    safe_margin_ratio: float = 0.08

    @property
    def cells_per_page(self) -> int:
        """페이지당 총 칸 수."""
        return self.rows * self.cols

    @property
    def page_width_px(self) -> int:
        """표준 템플릿 페이지 가로 해상도(px)."""
        return self.cols * self.cell_size_px

    @property
    def page_height_px(self) -> int:
        """표준 템플릿 페이지 세로 해상도(px)."""
        return self.rows * self.cell_size_px

    @property
    def min_page_width_px(self) -> int:
        """허용 최소 페이지 가로 해상도(px)."""
        return self.cols * self.min_cell_size_px

    @property
    def min_page_height_px(self) -> int:
        """허용 최소 페이지 세로 해상도(px)."""
        return self.rows * self.min_cell_size_px


DEFAULT_TEMPLATE_SPEC = TemplateSpec()
