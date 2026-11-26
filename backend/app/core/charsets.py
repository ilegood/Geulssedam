"""문자 세트 정의 및 페이지 분할 모듈.

MVP 문자 범위(영문 대소문자 52자, 숫자 10자, 기본 특수문자 30자, 한글 자주 쓰는 200자)를
중앙에서 관리하며, 향후 KS X 1001 2,350자 등 확장 문자 세트를 쉽게 등록할 수 있게 설계합니다.
"""

from __future__ import annotations

from dataclasses import dataclass

LATIN_UPPER: str = "ABCDEFGHIJKLMNOPQRSTUVWXYZ"
LATIN_LOWER: str = "abcdefghijklmnopqrstuvwxyz"
DIGITS: str = "0123456789"
BASIC_SYMBOLS: str = ".,!?'\"-():;/@#&*+=~_[]{}<>%$^`"

# 한글 기본 단독 자모 40자 (자음 19자 + 모음 21자: ㅋㅋㅋ, ㅎㅎ, ㅠㅠ, ㄱㄴㄷ, ㅏㅑ 등)
HANGUL_BASIC_JAMO: str = (
    "ㄱㄲㄴㄷㄸㄹㅁㅂㅃㅅㅆㅇㅈㅉㅊㅋㅌㅍㅎ"
    "ㅏㅐㅑㅒㅓㅔㅕㅖㅗㅘㅙㅚㅛㅜㅝㅞㅟㅠㅡㅢㅣ"
)

# 6-2-2벌 조합용 자모 시퀀스 (페이지별 배치용)
_JAMO_CHO_19: str = "ㄱㄲㄴㄷㄸㄹㅁㅂㅃㅅㅆㅇㅈㅉㅊㅋㅌㅍㅎ"
_JAMO_JUNG_21: str = "ㅏㅐㅑㅒㅓㅔㅕㅖㅗㅘㅙㅚㅛㅜㅝㅞㅟㅠㅡㅢㅣ"
_JAMO_JONG_27: str = "ㄱㄲㄳㄴㄵㄶㄷㄹㄺㄻㄼㄽㄾㄿㅀㅁㅂㅄㅅㅆㅇㅈㅊㅋㅌㅍㅎ"

HANGUL_JAMO_CHO13: str = _JAMO_CHO_19 * 3  # 57칸 (초성 1~3벌)
HANGUL_JAMO_CHO46: str = _JAMO_CHO_19 * 3  # 57칸 (초성 4~6벌)
HANGUL_JAMO_JUNG_JONG: str = (_JAMO_JUNG_21 * 2) + (_JAMO_JONG_27 * 2)  # 96칸 (중성 2벌 + 종성 2벌)

# 한국어 일상 문장·문서에서 빈도가 높은 대표 한글 음절 200자 (가나다순, 중복 없음)
HANGUL_COMMON_200: str = (
    "가간갈감강개거건것게경고과구국그글금기길"
    "김까꿈끝나난날남내너네년노놀누눈느늘니다"
    "단달담당대더데도동두드들등때또라람랑래러"
    "레려로루르를리마만말망매머면명모무문물미"
    "민바박반발방배백버번법별병보복부분불비빛"
    "사산살삼상새생서선설성세소손수시식신실심"
    "쓰아안알애야양어언얼에여연열영예오온올와"
    "요용우운울원위유은을음의이인일입자작잘장"
    "재저전정제조좋주중지진질집차창천초추치카"
    "코크키타태토트파편포표피하한할함해현화회"
)


@dataclass(frozen=True)
class CharsetGroup:
    """단일 문자 그룹 정의."""

    id: str
    name: str
    description: str
    chars: tuple[str, ...]
    stage: str = "mvp"

    @property
    def count(self) -> int:
        """포함된 문자 개수를 반환합니다."""
        return len(self.chars)


@dataclass(frozen=True)
class TemplatePreset:
    """사용자가 선택하는 템플릿 프리셋(하나 이상의 문자 그룹 조합)."""

    id: str
    name: str
    description: str
    group_ids: tuple[str, ...]
    stage: str = "mvp"


@dataclass(frozen=True)
class PagePlan:
    """단일 템플릿 페이지의 문자 배치 계획."""

    page_number: int
    total_pages: int
    group_id: str
    group_name: str
    chars: tuple[str, ...]


# 기본 문자 그룹 레지스트리
CHARSET_GROUPS: dict[str, CharsetGroup] = {
    "latin_basic": CharsetGroup(
        id="latin_basic",
        name="영문·숫자·기본 특수문자",
        description="영문 대소문자 52자, 숫자 10자, 기본 특수문자 30자 (총 92자)",
        chars=tuple(LATIN_UPPER + LATIN_LOWER + DIGITS + BASIC_SYMBOLS),
        stage="active",
    ),
    "hangul_jamo_basic": CharsetGroup(
        id="hangul_jamo_basic",
        name="한글 기본 단독 자모 (ㄱ~ㅎ, ㅏ~ㅣ)",
        description="단독 자음 19자 + 모음 21자 = 40자 (ㅋㅋㅋ, ㅠㅠ, ㄱㄴㄷ, ㅏㅑ 등)",
        chars=tuple(HANGUL_BASIC_JAMO),
        stage="active",
    ),
    "hangul_jamo_cho13": CharsetGroup(
        id="hangul_jamo_cho13",
        name="한글 초성 1~3벌 (받침 없는 글자용)",
        description="받침 없는 세로/가로/복합모음 조합용 초성 57칸",
        chars=tuple(HANGUL_JAMO_CHO13),
        stage="active",
    ),
    "hangul_jamo_cho46": CharsetGroup(
        id="hangul_jamo_cho46",
        name="한글 초성 4~6벌 (받침 있는 글자용)",
        description="받침 있는 세로/가로/복합모음 조합용 초성 57칸",
        chars=tuple(HANGUL_JAMO_CHO46),
        stage="active",
    ),
    "hangul_jamo_jung_jong": CharsetGroup(
        id="hangul_jamo_jung_jong",
        name="한글 중성 1~2벌 + 종성 1~2벌",
        description="받침 유무별 중성 42칸 + 모음 유형별 종성 54칸 (총 96칸)",
        chars=tuple(HANGUL_JAMO_JUNG_JONG),
        stage="active",
    ),
    "hangul_200": CharsetGroup(
        id="hangul_200",
        name="한글 자주 쓰는 200자",
        description="일상 문장과 문서에서 자주 쓰이는 한글 음절 200자",
        chars=tuple(HANGUL_COMMON_200),
        stage="legacy",
    ),
}

# 기본 템플릿 프리셋 레지스트리 (UI 노출 메인 3종: active)
TEMPLATE_PRESETS: dict[str, TemplatePreset] = {
    "latin_basic": TemplatePreset(
        id="latin_basic",
        name="영문·숫자·특수문자",
        description="영문 대소문자, 숫자, 기본 특수문자 92자 (1페이지)",
        group_ids=("latin_basic",),
        stage="active",
    ),
    "hangul_jamo": TemplatePreset(
        id="hangul_jamo",
        name="한글 조합형 (기본 자모 + 6-2-2벌)",
        description="기본 단독 자모 40자(ㄱ~ㅎ, ㅏ~ㅣ) + 6-2-2벌 210칸 = 총 250칸 (4페이지)",
        group_ids=(
            "hangul_jamo_basic",
            "hangul_jamo_cho13",
            "hangul_jamo_cho46",
            "hangul_jamo_jung_jong",
        ),
        stage="active",
    ),
    "latin_hangul_jamo": TemplatePreset(
        id="latin_hangul_jamo",
        name="영문 + 한글 조합형 전체 세트",
        description=(
            "영문·숫자·특수문자(1P) + 한글 기본 자모(1P) + "
            "한글 조합형 6-2-2벌(3P) = 총 342칸 (5페이지)"
        ),
        group_ids=(
            "latin_basic",
            "hangul_jamo_basic",
            "hangul_jamo_cho13",
            "hangul_jamo_cho46",
            "hangul_jamo_jung_jong",
        ),
        stage="active",
    ),
    "hangul_200": TemplatePreset(
        id="hangul_200",
        name="한글 자주 쓰는 200자",
        description="한글 대표 음절 200자 (2페이지)",
        group_ids=("hangul_200",),
        stage="legacy",
    ),
    "mvp": TemplatePreset(
        id="mvp",
        name="MVP 전체 세트 (영문+숫자+특수문자+한글 200자)",
        description="기본 92자(1페이지) + 한글 200자(2페이지) = 총 292자 (3페이지)",
        group_ids=("latin_basic", "hangul_200"),
        stage="legacy",
    ),
}

ACTIVE_PRESET_IDS: tuple[str, ...] = ("latin_basic", "hangul_jamo", "latin_hangul_jamo")


def register_charset_group(group: CharsetGroup) -> None:
    """확장 문자 그룹(예: KS X 1001 2,350자)을 레지스트리에 등록합니다."""
    if len(set(group.chars)) != len(group.chars):
        raise ValueError(f"문자 그룹 '{group.id}'에 중복 문자가 포함되어 있습니다.")
    CHARSET_GROUPS[group.id] = group


def register_template_preset(preset: TemplatePreset) -> None:
    """확장 템플릿 프리셋을 레지스트리에 등록합니다."""
    for group_id in preset.group_ids:
        if group_id not in CHARSET_GROUPS:
            raise ValueError(f"등록되지 않은 문자 그룹입니다: {group_id}")
    TEMPLATE_PRESETS[preset.id] = preset


def get_preset(preset_id: str) -> TemplatePreset:
    """프리셋 ID로 템플릿 프리셋을 조회합니다."""
    if preset_id not in TEMPLATE_PRESETS:
        available = ", ".join(sorted(TEMPLATE_PRESETS.keys()))
        raise ValueError(f"알 수 없는 프리셋입니다: '{preset_id}' (사용 가능: {available})")
    return TEMPLATE_PRESETS[preset_id]


def build_page_plans(preset_id: str, cells_per_page: int = 100) -> list[PagePlan]:
    """프리셋의 문자 그룹을 페이지 단위 배치 계획으로 분할합니다.

    문자 그룹 경계마다 새 페이지로 시작하므로 MVP 기준
    영문/숫자/특수문자 1페이지 + 한글 200자 2페이지 = 총 3페이지가 됩니다.
    """
    if cells_per_page <= 0:
        raise ValueError("페이지당 칸 수는 1 이상이어야 합니다.")

    preset = get_preset(preset_id)
    raw_pages: list[tuple[CharsetGroup, tuple[str, ...]]] = []

    for group_id in preset.group_ids:
        group = CHARSET_GROUPS[group_id]
        for start in range(0, len(group.chars), cells_per_page):
            chunk = group.chars[start : start + cells_per_page]
            raw_pages.append((group, chunk))

    total_pages = len(raw_pages)
    return [
        PagePlan(
            page_number=idx + 1,
            total_pages=total_pages,
            group_id=group.id,
            group_name=group.name,
            chars=chunk,
        )
        for idx, (group, chunk) in enumerate(raw_pages)
    ]
