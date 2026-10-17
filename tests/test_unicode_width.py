"""Spot checks for the unicode-width 0.2.0 port (the exhaustive check is tools/uw_difftest.py)."""
from mermaid_unicode.unicode_width import char_width, str_width


def test_ascii_and_controls():
    assert str_width("hello") == 5
    assert char_width("a") == 1
    assert char_width("\x00") is None
    assert char_width("\x7f") is None
    assert char_width("\x9f") is None
    assert char_width("\xa0") == 1


def test_crlf_is_one_column():
    assert str_width("\r\n") == 1
    assert str_width("\n") == 1
    assert str_width("\r") == 1


def test_wide_and_zero_width():
    assert str_width("日本語") == 6
    assert str_width("Ｈｅｌｌｏ") == 10
    assert str_width("é") == 1  # combining acute
    assert str_width("‍") == 0  # ZWJ alone
    assert str_width("ᅟ") == 2  # Hangul choseong filler
    assert str_width("៘") == 3  # Khmer sign beyyal


def test_emoji_sequences():
    assert str_width("😀") == 2
    assert str_width("👨‍👩‍👧") == 2  # ZWJ family
    assert str_width("👍\U0001f3fd") == 2  # modifier sequence
    assert str_width("❤️") == 2  # heart + VS16 = emoji presentation
    assert str_width("❤") == 1
    assert str_width("\U0001f1eb\U0001f1f7") == 2  # flag FR
    assert str_width("#️⃣") == 2  # keycap


def test_script_ligatures():
    assert str_width("لا") == 1  # Arabic lam-alef
    assert str_width("א‍ל") == 1  # Hebrew alef-ZWJ-lamed
    assert str_width("ꓹꓼ") == 1  # Lisu tone letters
    assert str_width("ⵏ⵿ⴾ") == 1  # Tifinagh joiner
