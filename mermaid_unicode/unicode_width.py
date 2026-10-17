"""Port of the `unicode-width` 0.2.0 crate (non-CJK path), Unicode 15.1.0.

`char_width(c)` mirrors `UnicodeWidthChar::width` (``None`` for control characters) and
`str_width(s)` mirrors `UnicodeWidthStr::width`, including the right-to-left state machine
that handles ``\\r\\n``, emoji ZWJ/modifier/presentation sequences and the script-specific
ligatures (Arabic Lam-Alef, Hebrew, Buginese, Khmer, Lisu, Old Turkic, Tifinagh).
"""
from __future__ import annotations

from bisect import bisect_right

from . import _uw_tables as T

# --- WidthInfo constants (u16 bit patterns, verbatim from tables.rs) -------------------------
DEFAULT = 0
LINE_FEED = 0b0000000000000001
EMOJI_MODIFIER = 0b0000000000000010
REGIONAL_INDICATOR = 0b0000000000000011
SEVERAL_REGIONAL_INDICATOR = 0b0000000000000100
EMOJI_PRESENTATION = 0b0000000000000101
ZWJ_EMOJI_PRESENTATION = 0b0001000000000110
VS16_ZWJ_EMOJI_PRESENTATION = 0b1001000000000110
KEYCAP_ZWJ_EMOJI_PRESENTATION = 0b0001000000000111
VS16_KEYCAP_ZWJ_EMOJI_PRESENTATION = 0b1001000000000111
REGIONAL_INDICATOR_ZWJ_PRESENTATION = 0b0000000000001001
EVEN_REGIONAL_INDICATOR_ZWJ_PRESENTATION = 0b0000000000001010
ODD_REGIONAL_INDICATOR_ZWJ_PRESENTATION = 0b0000000000001011
TAG_END_ZWJ_EMOJI_PRESENTATION = 0b0000000000010000
TAG_D1_END_ZWJ_EMOJI_PRESENTATION = 0b0000000000010001
TAG_D2_END_ZWJ_EMOJI_PRESENTATION = 0b0000000000010010
TAG_D3_END_ZWJ_EMOJI_PRESENTATION = 0b0000000000010011
TAG_A1_END_ZWJ_EMOJI_PRESENTATION = 0b0000000000011001
TAG_A2_END_ZWJ_EMOJI_PRESENTATION = 0b0000000000011010
TAG_A3_END_ZWJ_EMOJI_PRESENTATION = 0b0000000000011011
TAG_A4_END_ZWJ_EMOJI_PRESENTATION = 0b0000000000011100
TAG_A5_END_ZWJ_EMOJI_PRESENTATION = 0b0000000000011101
TAG_A6_END_ZWJ_EMOJI_PRESENTATION = 0b0000000000011110
VARIATION_SELECTOR_15 = 0b0100000000000000
VARIATION_SELECTOR_16 = 0b1000000000000000
JOINING_GROUP_ALEF = 0b0011000011111111
HEBREW_LETTER_LAMED = 0b0011100000000000
ZWJ_HEBREW_LETTER_LAMED = 0b0011110000000000
BUGINESE_LETTER_YA = 0b0011100000000001
ZWJ_BUGINESE_LETTER_YA = 0b0011110000000001
BUGINESE_VOWEL_SIGN_I_ZWJ_LETTER_YA = 0b0011110000000010
TIFINAGH_CONSONANT = 0b0011100000000011
ZWJ_TIFINAGH_CONSONANT = 0b0011110000000011
TIFINAGH_JOINER_CONSONANT = 0b0011110000000100
LISU_TONE_LETTER_MYA_NA_JEU = 0b0011110000000101
OLD_TURKIC_LETTER_ORKHON_I = 0b0011100000000110
ZWJ_OLD_TURKIC_LETTER_ORKHON_I = 0b0011110000000110
KHMER_COENG_ELIGIBLE_LETTER = 0b0011110000000111


def _is_ligature_transparent_info(info: int) -> bool:
    return (info & 0b0000_1000_0000_0000) == 0b0000_1000_0000_0000


def _set_zwj_bit(info: int) -> int:
    return info | 0b0000_0100_0000_0000


def _is_emoji_presentation(info: int) -> bool:
    return (info & 0b1000_0000_0000_0000) == 0b1000_0000_0000_0000


def _is_zwj_emoji_presentation(info: int) -> bool:
    return (info & 0b1011_0000_0000_0000) == 0b1001_0000_0000_0000


def _set_emoji_presentation(info: int) -> int:
    if (info & 0b0010_0000_0000_0000) == 0b0010_0000_0000_0000 or (
        info & 0b1001_0000_0000_0000
    ) == 0b0001_0000_0000_0000:
        return info | 0b1000_0000_0000_0000
    return VARIATION_SELECTOR_16


def _unset_emoji_presentation(info: int) -> int:
    if (info & 0b0010_0000_0000_0000) == 0b0010_0000_0000_0000:
        return info & 0b0111_1111_1111_1111
    return DEFAULT


def _is_text_presentation(info: int) -> bool:
    return (info & 0b0100_0000_0000_0000) == 0b0100_0000_0000_0000


def _set_text_presentation(info: int) -> int:
    if (info & 0b0010_0000_0000_0000) == 0b0010_0000_0000_0000:
        return info | 0b0100_0000_0000_0000
    return 0b0100_0000_0000_0000


def _unset_text_presentation(info: int) -> int:
    return info & 0b1011_1111_1111_1111


# --- table lookups ---------------------------------------------------------------------------
_LW_STARTS = T.LW_STARTS
_LW_WIDTH = T.LW_WIDTH
_LW_INFO = T.LW_INFO


def lookup_width(cp: int) -> tuple[int, int]:
    """`lookup_width(c) -> (u8 width, WidthInfo)` for a codepoint."""
    i = bisect_right(_LW_STARTS, cp) - 1
    return _LW_WIDTH[i], _LW_INFO[i]


def _in_ranges(starts, ends, cp: int) -> bool:
    i = bisect_right(starts, cp) - 1
    return i >= 0 and cp <= ends[i]


def is_transparent_zero_width(cp: int) -> bool:
    return _in_ranges(T.IS_TRANSPARENT_ZERO_WIDTH_STARTS, T.IS_TRANSPARENT_ZERO_WIDTH_ENDS, cp)


def is_ligature_transparent(cp: int) -> bool:
    return (
        cp == 0x34F
        or 0x17B4 <= cp <= 0x17B5
        or 0x180B <= cp <= 0x180D
        or cp == 0x180F
        or cp == 0x200D
        or 0xFE00 <= cp <= 0xFE0F
        or 0xE0100 <= cp <= 0xE01EF
    )


def starts_emoji_presentation_seq(cp: int) -> bool:
    return _in_ranges(
        T.STARTS_EMOJI_PRESENTATION_SEQ_STARTS, T.STARTS_EMOJI_PRESENTATION_SEQ_ENDS, cp
    )


def starts_non_ideographic_text_presentation_seq(cp: int) -> bool:
    return _in_ranges(
        T.STARTS_NON_IDEOGRAPHIC_TEXT_PRESENTATION_SEQ_STARTS,
        T.STARTS_NON_IDEOGRAPHIC_TEXT_PRESENTATION_SEQ_ENDS,
        cp,
    )


def is_emoji_modifier_base(cp: int) -> bool:
    return _in_ranges(T.IS_EMOJI_MODIFIER_BASE_STARTS, T.IS_EMOJI_MODIFIER_BASE_ENDS, cp)


# --- public API -----------------------------------------------------------------------------
def char_width(c: str) -> int | None:
    """`UnicodeWidthChar::width`: display width of one char, or ``None`` for control chars."""
    cp = ord(c)
    if cp < 0x7F:
        return 1 if cp >= 0x20 else None
    if cp >= 0xA0:
        return lookup_width(cp)[0]
    return None


def _width_in_str(cp: int, next_info: int) -> tuple[int, int]:
    if _is_emoji_presentation(next_info):
        if starts_emoji_presentation_seq(cp):
            width = 0 if _is_zwj_emoji_presentation(next_info) else 2
            return width, EMOJI_PRESENTATION
        next_info = _unset_emoji_presentation(next_info)
    if cp <= 0xA0:
        if cp == 0x0A:
            return 1, LINE_FEED
        if cp == 0x0D and next_info == LINE_FEED:
            return 0, DEFAULT
        return 1, DEFAULT
    # Fast path
    if next_info != DEFAULT:
        if cp == 0xFE0F:
            return 0, _set_emoji_presentation(next_info)
        if cp == 0xFE0E:
            return 0, _set_text_presentation(next_info)
        if _is_text_presentation(next_info):
            if starts_non_ideographic_text_presentation_seq(cp):
                return 1, DEFAULT
            next_info = _unset_text_presentation(next_info)
        if _is_ligature_transparent_info(next_info):
            if cp == 0x200D:
                return 0, _set_zwj_bit(next_info)
            if is_ligature_transparent(cp):
                return 0, next_info

        ni = next_info
        # Arabic Lam-Alef ligature
        if ni == JOINING_GROUP_ALEF:
            if cp == 0x644 or 0x6B5 <= cp <= 0x6B8 or cp == 0x76A or cp == 0x8A6 or cp == 0x8C7:
                return 0, DEFAULT
            if is_transparent_zero_width(cp):
                return 0, JOINING_GROUP_ALEF
        # Hebrew Alef-ZWJ-Lamed ligature
        if ni == ZWJ_HEBREW_LETTER_LAMED and cp == 0x05D0:
            return 0, DEFAULT
        # Khmer coeng signs
        if ni == KHMER_COENG_ELIGIBLE_LETTER and cp == 0x17D2:
            return -1, DEFAULT
        # Buginese <a, -i> ZWJ ya ligature
        if ni == ZWJ_BUGINESE_LETTER_YA and cp == 0x1A17:
            return 0, BUGINESE_VOWEL_SIGN_I_ZWJ_LETTER_YA
        if ni == BUGINESE_VOWEL_SIGN_I_ZWJ_LETTER_YA and cp == 0x1A15:
            return 0, DEFAULT
        # Tifinagh bi-consonants
        if ni in (TIFINAGH_CONSONANT, ZWJ_TIFINAGH_CONSONANT) and cp == 0x2D7F:
            return 1, TIFINAGH_JOINER_CONSONANT
        tif_cons = 0x2D31 <= cp <= 0x2D65 or cp == 0x2D6F
        if ni == ZWJ_TIFINAGH_CONSONANT and tif_cons:
            return 0, DEFAULT
        if ni == TIFINAGH_JOINER_CONSONANT and tif_cons:
            return -1, DEFAULT
        # Lisu tone letter combinations
        if ni == LISU_TONE_LETTER_MYA_NA_JEU and 0xA4F8 <= cp <= 0xA4FB:
            return 0, DEFAULT
        # Old Turkic ligature
        if ni == ZWJ_OLD_TURKIC_LETTER_ORKHON_I and cp == 0x10C32:
            return 0, DEFAULT
        # Emoji modifier
        if ni == EMOJI_MODIFIER and is_emoji_modifier_base(cp):
            return 0, EMOJI_PRESENTATION
        # Regional indicator
        regional = 0x1F1E6 <= cp <= 0x1F1FF
        if ni in (REGIONAL_INDICATOR, SEVERAL_REGIONAL_INDICATOR) and regional:
            return 1, SEVERAL_REGIONAL_INDICATOR
        # ZWJ emoji
        if (
            ni
            in (
                EMOJI_PRESENTATION,
                SEVERAL_REGIONAL_INDICATOR,
                EVEN_REGIONAL_INDICATOR_ZWJ_PRESENTATION,
                ODD_REGIONAL_INDICATOR_ZWJ_PRESENTATION,
                EMOJI_MODIFIER,
            )
            and cp == 0x200D
        ):
            return 0, ZWJ_EMOJI_PRESENTATION
        if ni == ZWJ_EMOJI_PRESENTATION and cp == 0x20E3:
            return 0, KEYCAP_ZWJ_EMOJI_PRESENTATION
        if ni == VS16_ZWJ_EMOJI_PRESENTATION and starts_emoji_presentation_seq(cp):
            return 0, EMOJI_PRESENTATION
        if ni == VS16_KEYCAP_ZWJ_EMOJI_PRESENTATION and (
            0x30 <= cp <= 0x39 or cp == 0x23 or cp == 0x2A
        ):
            return 0, EMOJI_PRESENTATION
        if ni == ZWJ_EMOJI_PRESENTATION and regional:
            return 1, REGIONAL_INDICATOR_ZWJ_PRESENTATION
        if (
            ni in (REGIONAL_INDICATOR_ZWJ_PRESENTATION, ODD_REGIONAL_INDICATOR_ZWJ_PRESENTATION)
            and regional
        ):
            return -1, EVEN_REGIONAL_INDICATOR_ZWJ_PRESENTATION
        if ni == EVEN_REGIONAL_INDICATOR_ZWJ_PRESENTATION and regional:
            return 3, ODD_REGIONAL_INDICATOR_ZWJ_PRESENTATION
        if ni == ZWJ_EMOJI_PRESENTATION and 0x1F3FB <= cp <= 0x1F3FF:
            return 0, EMOJI_MODIFIER
        if ni == ZWJ_EMOJI_PRESENTATION and cp == 0xE007F:
            return 0, TAG_END_ZWJ_EMOJI_PRESENTATION
        tag_alpha = 0xE0061 <= cp <= 0xE007A
        if ni == TAG_END_ZWJ_EMOJI_PRESENTATION and tag_alpha:
            return 0, TAG_A1_END_ZWJ_EMOJI_PRESENTATION
        if ni == TAG_A1_END_ZWJ_EMOJI_PRESENTATION and tag_alpha:
            return 0, TAG_A2_END_ZWJ_EMOJI_PRESENTATION
        if ni == TAG_A2_END_ZWJ_EMOJI_PRESENTATION and tag_alpha:
            return 0, TAG_A3_END_ZWJ_EMOJI_PRESENTATION
        if ni == TAG_A3_END_ZWJ_EMOJI_PRESENTATION and tag_alpha:
            return 0, TAG_A4_END_ZWJ_EMOJI_PRESENTATION
        if ni == TAG_A4_END_ZWJ_EMOJI_PRESENTATION and tag_alpha:
            return 0, TAG_A5_END_ZWJ_EMOJI_PRESENTATION
        if ni == TAG_A5_END_ZWJ_EMOJI_PRESENTATION and tag_alpha:
            return 0, TAG_A6_END_ZWJ_EMOJI_PRESENTATION
        tag_digit = 0xE0030 <= cp <= 0xE0039
        if (
            ni
            in (
                TAG_END_ZWJ_EMOJI_PRESENTATION,
                TAG_A1_END_ZWJ_EMOJI_PRESENTATION,
                TAG_A2_END_ZWJ_EMOJI_PRESENTATION,
                TAG_A3_END_ZWJ_EMOJI_PRESENTATION,
                TAG_A4_END_ZWJ_EMOJI_PRESENTATION,
            )
            and tag_digit
        ):
            return 0, TAG_D1_END_ZWJ_EMOJI_PRESENTATION
        if ni == TAG_D1_END_ZWJ_EMOJI_PRESENTATION and tag_digit:
            return 0, TAG_D2_END_ZWJ_EMOJI_PRESENTATION
        if ni == TAG_D2_END_ZWJ_EMOJI_PRESENTATION and tag_digit:
            return 0, TAG_D3_END_ZWJ_EMOJI_PRESENTATION
        if (
            ni
            in (
                TAG_A3_END_ZWJ_EMOJI_PRESENTATION,
                TAG_A4_END_ZWJ_EMOJI_PRESENTATION,
                TAG_A5_END_ZWJ_EMOJI_PRESENTATION,
                TAG_A6_END_ZWJ_EMOJI_PRESENTATION,
                TAG_D3_END_ZWJ_EMOJI_PRESENTATION,
            )
            and cp == 0x1F3F4
        ):
            return 0, EMOJI_PRESENTATION
        if ni == ZWJ_EMOJI_PRESENTATION and lookup_width(cp)[1] == EMOJI_PRESENTATION:
            return 0, EMOJI_PRESENTATION
        # Fallback
    w, info = lookup_width(cp)
    return w, info


_U64 = 1 << 64


def str_width(s: str) -> int:
    """`UnicodeWidthStr::width`: display width of a string (non-CJK)."""
    total = 0
    info = DEFAULT
    for c in reversed(s):
        add, info = _width_in_str(ord(c), info)
        total += add
        if total < 0:  # usize::wrapping_add_signed
            total += _U64
    return total
