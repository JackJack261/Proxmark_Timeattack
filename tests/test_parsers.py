from pm3trainer.parsers import (
    HidResult,
    parse_em410x,
    parse_hid,
    parse_iclass_block,
    parse_mifare_uid,
    parse_search_kind,
    strip_ansi,
)

HID_OUT = """\
[=] Reading HID Prox...
[+] [H10301  ] HID H10301 26-bit                FC: 240  CN: 2772    parity ( ok )
[+] DemodBuffer:
[+] 1D555556AA9A5A9A6A5A9556
"""

EM_OUT = """\
[=] Checking for known tags...
[+] EM 410x ID 0F0368568B
[+] EM410x ( RF/64 )
[+] Unique TAG ID  : F0C0A16AD1
[+] Valid EM410x ID found!
"""

MF_OUT = """\
[=] --- ISO14443-a Information ---------------------
[+]  UID: 04 A1 B2 C3 D4 E5 F6
[+] ATQA: 00 44
[+]  SAK: 00 [2]
[+] Prng detection: weak
"""

ICLASS_OUT = """\
[=] --- Tag Information ---------------------
[=] block 05/0x05 : 00 11 22 33 44 55 66 77
[=] block 06/0x06 : 12 34 56 78 9A BC DE F0
[=] block 07/0x07 : AA BB CC DD EE FF 00 11
"""

LF_SEARCH = "[+] Valid EM410x ID found!\n"
HF_SEARCH = "[+] Valid iCLASS tag / PicoPass tag found\n"


def test_strip_ansi_removes_color_codes():
    assert strip_ansi("\x1b[32mhello\x1b[0m world") == "hello world"


def test_parse_hid_extracts_fc_and_cn():
    assert parse_hid(HID_OUT) == HidResult(240, 2772)


def test_parse_hid_returns_none_on_garbage():
    assert parse_hid("[!] No known/supported 125 kHz tags found") is None


def test_parse_em410x_extracts_id():
    assert parse_em410x(EM_OUT) == "0f0368568b"
    assert parse_em410x("nothing here") is None


def test_parse_mifare_uid_extracts_uid():
    assert parse_mifare_uid(MF_OUT) == "04a1b2c3d4e5f6"
    assert parse_mifare_uid("nothing here") is None


def test_parse_iclass_block_extracts_data():
    assert parse_iclass_block(ICLASS_OUT, 6) == "123456789abcdef0"
    assert parse_iclass_block(ICLASS_OUT, 7) == "aabbccddeeff0011"
    assert parse_iclass_block(ICLASS_OUT, 9) is None


def test_parse_search_kind_lf_vs_hf():
    assert parse_search_kind(LF_SEARCH) == "LF"
    assert parse_search_kind(HF_SEARCH) == "HF"
    assert parse_search_kind("garbage") is None


def test_parsers_strip_ansi_before_matching():
    def wrap(s):
        return "\x1b[32m" + s.replace("\n", "\x1b[0m\n\x1b[32m") + "\x1b[0m"

    assert parse_hid(wrap(HID_OUT)) == HidResult(240, 2772)
    assert parse_em410x(wrap(EM_OUT)) == "0f0368568b"
    assert parse_mifare_uid(wrap(MF_OUT)) == "04a1b2c3d4e5f6"
    assert parse_iclass_block(wrap(ICLASS_OUT), 6) == "123456789abcdef0"
    assert parse_search_kind(wrap(LF_SEARCH)) == "LF"
