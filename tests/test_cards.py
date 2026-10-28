from pm3trainer import cards
from pm3trainer.cards import CardKind, verify_card
from pm3trainer.testing import FakeSession

LF_SEARCH_OUT = "[+] Valid T55xx tag found\n"
HF_SEARCH_OUT_MIFARE = "[+] ISO14443-a Information\n[+] Valid Mifare Classic tag found\n"
HF_SEARCH_OUT_ICLASS = "[+] Valid iCLASS tag / PicoPass tag found\n"

T55_DETECT_OUT = (
    "[=] Chip Type      : T55x7\n"
    "[=] Modulation     : ASK\n"
    "[=] Password set   : No\n"
)
MAGIC_INFO_OUT = (
    "[+] UID: 01 02 03 04\n"
    "[+] Magic capabilities : Gen 1a\n"
)
ICLASS_INFO_OUT = (
    "[+] CSN: 00 01 02 03 04 05 06 07\n"
    "[+] Credential : iCLASS / PicoPass\n"
)


def _session(**responses):
    return FakeSession({
        cards.SEARCH_CMD: responses.get("search", ""),
        cards.T5577_INFO_CMD: responses.get("t5577", ""),
        cards.MAGIC_INFO_CMD: responses.get("magic", ""),
        cards.ICLASS_INFO_CMD: responses.get("iclass", ""),
    })


def test_verify_t5577_ok():
    s = _session(search=LF_SEARCH_OUT, t5577=T55_DETECT_OUT)
    check = verify_card(s, CardKind.T5577)
    assert check.ok is True
    assert check.state.password_set is False


def test_verify_t5577_detects_password():
    out = T55_DETECT_OUT.replace("Password set   : No", "Password set   : Yes")
    s = _session(search=LF_SEARCH_OUT, t5577=out)
    check = verify_card(s, CardKind.T5577)
    assert check.ok is True
    assert check.state.password_set is True


def test_verify_wrong_kind_not_ok():
    s = _session(search=HF_SEARCH_OUT_MIFARE, magic=MAGIC_INFO_OUT)
    check = verify_card(s, CardKind.T5577)
    assert check.ok is False
    assert "HF" in check.detail
    assert "LF" in check.detail


def test_verify_magic_mifare_ok():
    s = _session(search=HF_SEARCH_OUT_MIFARE, magic=MAGIC_INFO_OUT)
    check = verify_card(s, CardKind.MAGIC_MIFARE)
    assert check.ok is True


def test_verify_magic_mifare_plain_card_not_ok():
    s = _session(search=HF_SEARCH_OUT_MIFARE, magic="[+] UID: 01 02 03 04\n")
    check = verify_card(s, CardKind.MAGIC_MIFARE)
    assert check.ok is False
    assert "magic" in check.detail.lower()


def test_verify_writable_iclass_ok():
    s = _session(search=HF_SEARCH_OUT_ICLASS, iclass=ICLASS_INFO_OUT)
    check = verify_card(s, CardKind.WRITABLE_ICLASS)
    assert check.ok is True


def test_verify_no_card_not_ok():
    s = _session(search="[!] No known/supported tag found\n")
    check = verify_card(s, CardKind.T5577)
    assert check.ok is False
    assert "no card" in check.detail.lower()
    assert check.state.password_set is None


def test_verify_empty_output_not_ok():
    s = _session()
    check = verify_card(s, CardKind.WRITABLE_ICLASS)
    assert check.ok is False
