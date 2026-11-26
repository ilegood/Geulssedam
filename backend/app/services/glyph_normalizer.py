"""글리프 em 박스 정규화(베이스라인 정렬) 및 자간 계산 모듈.

향후 3번 혼합 방식(직접 그린 완성형 우선 + 벌 기반 자모 조합 생성)을 쉽게 통합할 수 있도록
완성형/조합형 모두 동일한 `NormalizedGlyph` 데이터 모델을 출력하도록 인터페이스를 분리합니다.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal, Protocol

from app.core.template_spec import DEFAULT_TEMPLATE_SPEC, TemplateSpec
from app.services.vectorizer import VectorizedGlyph

FontPoint = tuple[int, int]
GlyphSourceType = Literal["handwritten", "composed"]

UNITS_PER_EM = 1000
FONT_ASCENT = 800
FONT_DESCENT = -200
DEFAULT_SIDE_BEARING = 60


@dataclass(frozen=True)
class NormalizedGlyph:
    """폰트 빌더에 전달되는 표준화된 글리프 윤곽선 모델."""

    char: str
    codepoint: int
    glyph_name: str
    contours: tuple[tuple[FontPoint, ...], ...]
    advance_width: int
    lsb: int
    source: GlyphSourceType = "handwritten"


class GlyphProvider(Protocol):
    """글리프 공급자 인터페이스 (완성형 손글씨 / 향후 조합형 엔진 공용)."""

    def provide_glyphs(self) -> dict[int, NormalizedGlyph]:
        """유니코드 코드포인트 → NormalizedGlyph 매핑을 반환합니다."""
        ...


def _signed_area(points: list[FontPoint]) -> float:
    """다각형의 부호 있는 넓이를 계산합니다(폰트 좌표계에서 양수=반시계, 음수=시계)."""
    area = 0.0
    n = len(points)
    for i in range(n):
        x1, y1 = points[i]
        x2, y2 = points[(i + 1) % n]
        area += (x1 * y2) - (x2 * y1)
    return area * 0.5


def make_glyph_name(codepoint: int) -> str:
    """유니코드 코드포인트에 대한 안전한 PostScript 글리프 이름을 생성합니다."""
    if codepoint <= 0xFFFF:
        return f"uni{codepoint:04X}"
    return f"u{codepoint:X}"


def normalize_vectorized_glyph(
    char: str,
    vectorized: VectorizedGlyph,
    spec: TemplateSpec = DEFAULT_TEMPLATE_SPEC,
    units_per_em: int = UNITS_PER_EM,
    side_bearing: int = DEFAULT_SIDE_BEARING,
    letter_spacing_delta: int = 0,
    scale_factor: float = 1.0,
) -> NormalizedGlyph | None:
    """픽셀 좌표계 윤곽선을 em 박스(베이스라인 y=0)로 정규화하고 자간을 계산합니다."""
    if not vectorized.contours or vectorized.source_height <= 0:
        return None

    cell_h = float(vectorized.source_height)
    baseline_px = cell_h * spec.baseline_ratio
    scale = (units_per_em / cell_h) * scale_factor

    # 1단계: 베이스라인 기준 Y축 반전 변환
    transformed: list[tuple[list[tuple[float, float]], bool]] = []
    min_x = float("inf")
    max_x = float("-inf")

    for path in vectorized.contours:
        pts: list[tuple[float, float]] = []
        for px, py in path.points:
            fx = px * scale
            fy = (baseline_px - py) * scale
            min_x = min(min_x, fx)
            max_x = max(max_x, fx)
            pts.append((fx, fy))
        if len(pts) >= 3:
            transformed.append((pts, path.is_hole))

    if not transformed or min_x == float("inf"):
        return None

    # 2단계: 좌측 여백(lsb) 기준 X 좌표 정렬 + TrueType winding direction 보정
    # TrueType 외곽선은 시계 방향(부호 면적 < 0), 구멍(내부)은 반시계 방향(부호 면적 > 0)
    lsb = max(10, side_bearing + letter_spacing_delta // 2)
    rsb = max(10, side_bearing + letter_spacing_delta - (letter_spacing_delta // 2))

    final_contours: list[tuple[FontPoint, ...]] = []
    for pts, is_hole in transformed:
        shifted: list[FontPoint] = [
            (round(fx - min_x + lsb), round(fy))
            for fx, fy in pts
        ]
        # 연속 중복 점 제거
        deduped: list[FontPoint] = []
        for pt in shifted:
            if not deduped or deduped[-1] != pt:
                deduped.append(pt)
        if len(deduped) > 1 and deduped[0] == deduped[-1]:
            deduped.pop()
        if len(deduped) < 3:
            continue

        area = _signed_area(deduped)
        # 외곽선(is_hole=False)은 시계 방향(area < 0), 구멍(is_hole=True)은 반시계(area > 0)
        if (not is_hole and area > 0) or (is_hole and area < 0):
            deduped.reverse()

        final_contours.append(tuple(deduped))

    if not final_contours:
        return None

    glyph_width = max(1, round(max_x - min_x))
    advance_width = max(120, glyph_width + lsb + rsb)
    codepoint = ord(char)

    return NormalizedGlyph(
        char=char,
        codepoint=codepoint,
        glyph_name=make_glyph_name(codepoint),
        contours=tuple(final_contours),
        advance_width=advance_width,
        lsb=lsb,
        source="handwritten",
    )


def merge_glyph_layers(
    *layers: dict[int, NormalizedGlyph],
) -> dict[int, NormalizedGlyph]:
    """여러 글리프 소스 레이어를 우선순위대로 병합합니다.

    뒤에 전달된 레이어(예: 직접 그린 완성형)가 앞선 레이어(예: 향후 조합형)를 덮어씁니다.
    """
    merged: dict[int, NormalizedGlyph] = {}
    for layer in layers:
        merged.update(layer)
    return merged
