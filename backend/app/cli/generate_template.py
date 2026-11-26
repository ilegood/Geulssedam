"""글씨담(Geulssedam) 템플릿 생성 CLI.

사용 예시:
    python -m app.cli.generate_template --preset mvp --output ../storage/templates/v1
"""

from __future__ import annotations

import argparse
from collections.abc import Sequence
from dataclasses import replace
from pathlib import Path

from app.core.charsets import TEMPLATE_PRESETS
from app.core.template_spec import DEFAULT_TEMPLATE_SPEC
from app.services.template_generator import generate_templates


def build_parser() -> argparse.ArgumentParser:
    """CLI 인자 파서를 구성합니다."""
    parser = argparse.ArgumentParser(
        prog="generate_template",
        description=(
            "글씨담 손글씨 템플릿(투명 PNG, 가이드 레이어 PNG, PDF, 좌표 JSON)을 생성합니다."
        ),
    )
    parser.add_argument(
        "--preset",
        default="mvp",
        choices=sorted(TEMPLATE_PRESETS.keys()),
        help="생성할 문자 세트 프리셋 (기본값: mvp)",
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=Path("../storage/templates/v1"),
        help="생성 파일 저장 디렉터리 (기본값: ../storage/templates/v1)",
    )
    parser.add_argument(
        "--formats",
        default="png,guide,pdf,meta",
        help="쉼표로 구분된 출력 형식 목록: png,guide,pdf,meta (기본값: 전체)",
    )
    parser.add_argument(
        "--cell-size",
        type=int,
        default=DEFAULT_TEMPLATE_SPEC.cell_size_px,
        help=f"칸 크기(px) 오버라이드 (기본값: {DEFAULT_TEMPLATE_SPEC.cell_size_px})",
    )
    parser.add_argument(
        "--version",
        default=DEFAULT_TEMPLATE_SPEC.version,
        help=f"템플릿 버전 식별자 (기본값: {DEFAULT_TEMPLATE_SPEC.version})",
    )
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    """템플릿 생성 CLI 진입점."""
    parser = build_parser()
    args = parser.parse_args(argv)

    if args.cell_size < 64:
        parser.error("--cell-size는 64 이상이어야 합니다.")

    spec = replace(
        DEFAULT_TEMPLATE_SPEC,
        version=args.version,
        cell_size_px=args.cell_size,
    )
    formats = [item.strip() for item in args.formats.split(",") if item.strip()]

    result = generate_templates(
        preset_id=args.preset,
        output_dir=args.output,
        spec=spec,
        formats=formats,
    )

    print("[글씨담 템플릿 생성 완료]")
    print(f"- 프리셋: {result.preset_id} ({result.total_chars}자, 총 {result.total_pages}페이지)")
    print(
        f"- 규격: {spec.version} | {spec.cols}x{spec.rows}칸 | "
        f"{spec.page_width_px}x{spec.page_height_px}px (칸당 {spec.cell_size_px}px)"
    )
    print(f"- 저장 위치: {result.output_dir.resolve()}")
    if result.canvas_png_paths:
        print(f"- 투명 PNG: {len(result.canvas_png_paths)}개")
    if result.guide_png_paths:
        print(f"- 가이드 PNG: {len(result.guide_png_paths)}개")
    if result.pdf_path:
        print(f"- 인쇄용 PDF: {result.pdf_path.name}")
    if result.metadata_path:
        print(f"- 좌표 메타데이터: {result.metadata_path.name}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
