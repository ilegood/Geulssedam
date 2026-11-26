"""알파 마스크 윤곽선 추출(벡터화) 및 곡선 단순화 모듈.

1순위: 시스템에 설치된 `potrace` CLI를 호출해 고정밀 윤곽선(SVG path) 추출
2순위(폴백): `potrace` 바이너리가 없는 환경(예: Windows 로컬)에서는 OpenCV
`findContours` + `approxPolyDP`로 곡선을 단순화해 동일한 윤곽선 구조로 반환합니다.
"""

from __future__ import annotations

import re
import shutil
import subprocess
import tempfile
import xml.etree.ElementTree as ET
from dataclasses import dataclass
from pathlib import Path

import cv2
import numpy as np

from app.core.validation_config import DEFAULT_VALIDATION_THRESHOLDS, ValidationThresholds

Point = tuple[float, float]


@dataclass(frozen=True)
class VectorPath:
    """픽셀 좌표계(원점 좌상단) 기준 단일 닫힌 윤곽선(폴리라인)."""

    points: tuple[Point, ...]
    is_hole: bool = False


@dataclass(frozen=True)
class VectorizedGlyph:
    """단일 칸의 벡터화 결과."""

    contours: tuple[VectorPath, ...]
    source_width: int
    source_height: int
    engine: str


def is_potrace_available() -> bool:
    """시스템 PATH에서 potrace 실행 파일 사용 가능 여부를 확인합니다."""
    return shutil.which("potrace") is not None


def _parse_svg_polygon_paths(svg_text: str, height: int) -> list[VectorPath]:
    """`potrace -s --flat` 출력 SVG의 path 문자열을 폴리라인 좌표 리스트로 변환합니다."""
    root = ET.fromstring(svg_text)
    ns = {"svg": "http://www.w3.org/2000/svg"}

    # potrace SVG의 <g transform="translate(0,H) scale(0.1,-0.1)"> 스케일 파싱
    scale_x, scale_y = 0.1, -0.1
    translate_y = float(height)
    group = root.find("svg:g", ns)
    if group is not None:
        transform = group.attrib.get("transform", "")
        t_match = re.search(r"translate\(([-\d.]+)[,\s]+([-\d.]+)\)", transform)
        s_match = re.search(r"scale\(([-\d.]+)[,\s]+([-\d.]+)\)", transform)
        if t_match:
            translate_y = float(t_match.group(2))
        if s_match:
            scale_x = float(s_match.group(1))
            scale_y = float(s_match.group(2))

    token_re = re.compile(r"[MmLlHhVvCcZz]|-?\d+(?:\.\d+)?")
    contours: list[VectorPath] = []

    for path_el in root.findall(".//svg:path", ns):
        d = path_el.attrib.get("d", "")
        tokens = token_re.findall(d)
        idx = 0
        cmd = ""
        cx, cy = 0.0, 0.0
        sx, sy = 0.0, 0.0
        current: list[Point] = []

        def to_pixel(px: float, py: float) -> Point:
            return (px * scale_x, translate_y + py * scale_y)

        while idx < len(tokens):
            tok = tokens[idx]
            if tok.isalpha():
                cmd = tok
                idx += 1
                if cmd in ("Z", "z"):
                    if len(current) >= 3:
                        contours.append(VectorPath(points=tuple(current)))
                    current = []
                    cx, cy = sx, sy
                continue

            if cmd == "M":
                cx, cy = float(tokens[idx]), float(tokens[idx + 1])
                sx, sy = cx, cy
                idx += 2
                current = [to_pixel(cx, cy)]
                cmd = "L"
            elif cmd == "m":
                cx += float(tokens[idx])
                cy += float(tokens[idx + 1])
                sx, sy = cx, cy
                idx += 2
                current = [to_pixel(cx, cy)]
                cmd = "l"
            elif cmd == "L":
                cx, cy = float(tokens[idx]), float(tokens[idx + 1])
                idx += 2
                current.append(to_pixel(cx, cy))
            elif cmd == "l":
                cx += float(tokens[idx])
                cy += float(tokens[idx + 1])
                idx += 2
                current.append(to_pixel(cx, cy))
            elif cmd == "H":
                cx = float(tokens[idx])
                idx += 1
                current.append(to_pixel(cx, cy))
            elif cmd == "h":
                cx += float(tokens[idx])
                idx += 1
                current.append(to_pixel(cx, cy))
            elif cmd == "V":
                cy = float(tokens[idx])
                idx += 1
                current.append(to_pixel(cx, cy))
            elif cmd == "v":
                cy += float(tokens[idx])
                idx += 1
                current.append(to_pixel(cx, cy))
            elif cmd == "C":
                # 3차 베지어 곡선을 4분할 샘플링하여 정밀 폴리라인으로 변환
                x1, y1 = float(tokens[idx]), float(tokens[idx + 1])
                x2, y2 = float(tokens[idx + 2]), float(tokens[idx + 3])
                x3, y3 = float(tokens[idx + 4]), float(tokens[idx + 5])
                idx += 6
                for step in range(1, 5):
                    t = step / 4.0
                    mt = 1.0 - t
                    bx = mt**3 * cx + 3 * mt**2 * t * x1 + 3 * mt * t**2 * x2 + t**3 * x3
                    by = mt**3 * cy + 3 * mt**2 * t * y1 + 3 * mt * t**2 * y2 + t**3 * y3
                    current.append(to_pixel(bx, by))
                cx, cy = x3, y3
            elif cmd == "c":
                x1, y1 = cx + float(tokens[idx]), cy + float(tokens[idx + 1])
                x2, y2 = cx + float(tokens[idx + 2]), cy + float(tokens[idx + 3])
                x3, y3 = cx + float(tokens[idx + 4]), cy + float(tokens[idx + 5])
                idx += 6
                for step in range(1, 5):
                    t = step / 4.0
                    mt = 1.0 - t
                    bx = mt**3 * cx + 3 * mt**2 * t * x1 + 3 * mt * t**2 * x2 + t**3 * x3
                    by = mt**3 * cy + 3 * mt**2 * t * y1 + 3 * mt * t**2 * y2 + t**3 * y3
                    current.append(to_pixel(bx, by))
                cx, cy = x3, y3
            else:
                idx += 1

        if len(current) >= 3:
            contours.append(VectorPath(points=tuple(current)))

    return _classify_contour_holes(contours)


def _classify_contour_holes(contours: list[VectorPath]) -> list[VectorPath]:
    """윤곽선 포함 깊이(짝수=외곽선, 홀수=내부 구멍)로 is_hole을 정확히 판별합니다."""
    if len(contours) <= 1:
        return contours

    polys = [
        np.array(c.points, dtype=np.float32).reshape((-1, 1, 2))
        for c in contours
    ]
    areas = [cv2.contourArea(p) for p in polys]

    classified: list[VectorPath] = []
    for i, contour in enumerate(contours):
        # 다각형 대표 점(첫 꼭짓점)이 더 큰 다른 윤곽선 내부에 몇 겹 포함되는지 계산
        test_pt = (float(contour.points[0][0]), float(contour.points[0][1]))
        depth = 0
        for j, other_poly in enumerate(polys):
            if i == j or areas[j] <= areas[i]:
                continue
            if cv2.pointPolygonTest(other_poly, test_pt, False) > 0:
                depth += 1
        classified.append(VectorPath(points=contour.points, is_hole=(depth % 2 == 1)))

    return classified


def _vectorize_with_potrace(binary_mask: np.ndarray) -> list[VectorPath]:
    """potrace CLI로 이진 마스크를 벡터화합니다."""
    cleaned_mask = _clean_binary_mask(binary_mask)
    height, width = cleaned_mask.shape
    cell_area = float(height * width)
    min_outer_area = max(4.0, cell_area * 0.00015)
    min_hole_area = max(8.0, cell_area * 0.0004)

    # potrace는 PBM(P4 또는 P1) 입력을 지원: 1=전경(검정), 0=배경(흰색)
    with tempfile.TemporaryDirectory() as tmpdir:
        pbm_path = Path(tmpdir) / "glyph.pbm"
        svg_path = Path(tmpdir) / "glyph.svg"

        packed = np.packbits(cleaned_mask, axis=1)
        header = f"P4\n{width} {height}\n".encode("ascii")
        pbm_path.write_bytes(header + packed.tobytes())

        subprocess.run(
            [
                "potrace",
                str(pbm_path),
                "-s",
                "--flat",
                "--turdsize",
                "12",
                "--opttolerance",
                "0.4",
                "-o",
                str(svg_path),
            ],
            check=True,
            capture_output=True,
        )
        svg_text = svg_path.read_text(encoding="utf-8")

    paths = _parse_svg_polygon_paths(svg_text, height=height)
    filtered: list[VectorPath] = []
    for path in paths:
        poly = np.array(path.points, dtype=np.float32).reshape((-1, 1, 2))
        area = cv2.contourArea(poly)
        if area < (min_hole_area if path.is_hole else min_outer_area):
            continue
        filtered.append(path)
    return filtered


def _clean_binary_mask(binary_mask: np.ndarray) -> np.ndarray:
    """질감 브러시로 생긴 미세 핀홀·잡티를 제거해 윤곽선 깨짐을 방지합니다."""
    height, width = binary_mask.shape
    cell_dim = min(height, width)
    if cell_dim < 128:
        return binary_mask

    # 칸 크기 비례 작은 타원 커널(512px 기준 3×3)로 1~2px 브러시 핀홀 닫기
    k_size = max(3, (cell_dim // 180) * 2 + 1)
    k_size = min(k_size, 5)
    kernel = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (k_size, k_size))
    return cv2.morphologyEx(binary_mask, cv2.MORPH_CLOSE, kernel)


def _vectorize_with_opencv(
    binary_mask: np.ndarray,
    simplify_ratio: float = 0.002,
) -> list[VectorPath]:
    """OpenCV findContours + approxPolyDP로 윤곽선 추출 및 곡선 단순화를 수행합니다."""
    height, width = binary_mask.shape
    cell_dim = min(height, width)
    cell_area = float(height * width)

    # 질감 브러시 핀홀 제거 후 윤곽선 추출
    cleaned_mask = _clean_binary_mask(binary_mask)

    contours_raw, hierarchy = cv2.findContours(
        cleaned_mask,
        cv2.RETR_CCOMP,
        cv2.CHAIN_APPROX_NONE,
    )
    if hierarchy is None or len(contours_raw) == 0:
        return []

    # 칸 크기에 비례한 최소 면적 (512px 기준 외곽선 ~39px², 내부 구멍 ~105px²)
    min_outer_area = max(4.0, cell_area * 0.00015)
    min_hole_area = max(8.0, cell_area * 0.0004)
    max_epsilon = max(1.0, cell_dim * 0.0035)

    hierarchy_arr = hierarchy[0]
    results: list[VectorPath] = []
    for idx, cnt in enumerate(contours_raw):
        # hierarchy[idx][3] != -1 이면 구멍(내부 윤곽선)
        is_hole = int(hierarchy_arr[idx][3]) != -1
        area = cv2.contourArea(cnt)
        if area < (min_hole_area if is_hole else min_outer_area):
            continue

        peri = cv2.arcLength(cnt, True)
        epsilon = min(max_epsilon, max(0.8, peri * simplify_ratio))
        approx = cv2.approxPolyDP(cnt, epsilon, True)
        if len(approx) < 3:
            continue

        pts = tuple((float(p[0][0]), float(p[0][1])) for p in approx)
        results.append(VectorPath(points=pts, is_hole=is_hole))

    return results


def vectorize_alpha_mask(
    alpha: np.ndarray,
    thresholds: ValidationThresholds = DEFAULT_VALIDATION_THRESHOLDS,
    prefer_potrace: bool = True,
) -> VectorizedGlyph:
    """알파 채널 배열에 임계값을 적용해 윤곽선을 추출하고 단순화합니다."""
    height, width = alpha.shape
    binary_mask = (alpha >= thresholds.alpha_foreground_threshold).astype(np.uint8)

    if not np.any(binary_mask):
        return VectorizedGlyph(
            contours=(),
            source_width=width,
            source_height=height,
            engine="none",
        )

    if prefer_potrace and is_potrace_available():
        try:
            paths = _vectorize_with_potrace(binary_mask)
            if paths:
                return VectorizedGlyph(
                    contours=tuple(paths),
                    source_width=width,
                    source_height=height,
                    engine="potrace",
                )
        except (subprocess.SubprocessError, OSError, ET.ParseError):
            pass

    paths = _vectorize_with_opencv(binary_mask)
    return VectorizedGlyph(
        contours=tuple(paths),
        source_width=width,
        source_height=height,
        engine="opencv",
    )
