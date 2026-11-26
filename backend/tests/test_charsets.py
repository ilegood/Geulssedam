"""문자 세트 정의 및 페이지 분할 단위 테스트."""

import pytest

from app.core.charsets import (
    BASIC_SYMBOLS,
    CHARSET_GROUPS,
    DIGITS,
    HANGUL_COMMON_200,
    LATIN_LOWER,
    LATIN_UPPER,
    CharsetGroup,
    TemplatePreset,
    build_page_plans,
    register_charset_group,
    register_template_preset,
)


def test_mvp_charset_counts_and_uniqueness() -> None:
    """MVP 기본 문자 세트의 개수와 중복 없음을 검증합니다."""
    assert len(LATIN_UPPER) == 26
    assert len(LATIN_LOWER) == 26
    assert len(DIGITS) == 10
    assert len(BASIC_SYMBOLS) == 30
    assert len(HANGUL_COMMON_200) == 200

    latin_chars = CHARSET_GROUPS["latin_basic"].chars
    hangul_chars = CHARSET_GROUPS["hangul_200"].chars

    assert len(latin_chars) == 92
    assert len(set(latin_chars)) == 92
    assert len(hangul_chars) == 200
    assert len(set(hangul_chars)) == 200
    assert set(latin_chars).isdisjoint(set(hangul_chars))


def test_mvp_page_plans_split_by_group() -> None:
    """MVP 프리셋이 영문/숫자/특수문자 1페이지 + 한글 200자 2페이지로 분할되는지 검증합니다."""
    pages = build_page_plans("mvp", cells_per_page=100)
    assert len(pages) == 3

    assert pages[0].page_number == 1
    assert pages[0].total_pages == 3
    assert pages[0].group_id == "latin_basic"
    assert len(pages[0].chars) == 92

    assert pages[1].page_number == 2
    assert pages[1].group_id == "hangul_200"
    assert len(pages[1].chars) == 100

    assert pages[2].page_number == 3
    assert pages[2].group_id == "hangul_200"
    assert len(pages[2].chars) == 100


def test_unknown_preset_raises_value_error() -> None:
    """존재하지 않는 프리셋 요청 시 예외가 발생하는지 확인합니다."""
    with pytest.raises(ValueError, match="알 수 없는 프리셋"):
        build_page_plans("nonexistent")


def test_register_custom_extension_charset() -> None:
    """향후 한글 2,350자 등 확장 문자 세트를 동적으로 등록·분할할 수 있는지 검증합니다."""
    sample_chars = tuple(chr(0xAC00 + i) for i in range(250))
    custom_group = CharsetGroup(
        id="test_hangul_ext",
        name="테스트 확장 한글",
        description="확장성 검증용 250자",
        chars=sample_chars,
        stage="phase2",
    )
    register_charset_group(custom_group)
    register_template_preset(
        TemplatePreset(
            id="test_ext_preset",
            name="테스트 확장 프리셋",
            description="확장 프리셋",
            group_ids=("test_hangul_ext",),
            stage="phase2",
        )
    )

    pages = build_page_plans("test_ext_preset", cells_per_page=100)
    assert len(pages) == 3
    assert [len(p.chars) for p in pages] == [100, 100, 50]

    # 테스트 후 레지스트리 원복
    CHARSET_GROUPS.pop("test_hangul_ext", None)
    from app.core.charsets import TEMPLATE_PRESETS

    TEMPLATE_PRESETS.pop("test_ext_preset", None)
