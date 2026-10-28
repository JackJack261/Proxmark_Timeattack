from pm3trainer import cards
from pm3trainer.cards import CardKind, verify_card
from pm3trainer.testing import FakeSession

# Real `lf search` output from an Iceman client for a T5577 holding EM410x data.
LF_SEARCH_T5577 = (
    "[=] Checking for known tags...\n"
    "[+] EM 410x ID 340073B7A4\n"
    "[+] EM410x ( RF/64 )\n"
    "[+] Valid EM410x ID found!\n"
    "\n"
    "[+] Chipset... T55xx\n"
    "[?] Hint: Try `lf t55xx` commands\n"
)
LF_SEARCH_NONE = "[=] Checking for known tags...\n[!] No known 125/134 kHz tags found\n"
T55_DETECT_OUT = (
    "[+] Chip type......... T55x7\n"
    "[+] Modulation........ ASK\n"
    "[+] Password set...... No\n"
)
HF_SEARCH_MIFARE = "[+] Valid ISO14443-A tag found\n[+] Valid Mifare Classic tag found\n"
HF_SEARCH_ICLASS = "[+] Valid iCLASS tag / PicoPass tag found\n"
MAGIC_INFO_OUT = "[+] UID: 01 02 03 04\n[+] Magic capabilities : Gen 1a\n"
ICLASS_INFO_OUT = "[+] CSN: 00 01 02 03 04 05 06 07\n[+] Credential : iCLASS / PicoPass\n"


def _session(**responses):
    return FakeSession({
        cards.LF_SEARCH_CMD: responses.get("lf", ""),
        cards.T5577_DETECT_CMD: responses.get("detect", ""),
        cards.HF_SEARCH_CMD: responses.get("hf", ""),
        cards.MAGIC_INFO_CMD: responses.get("magic", ""),
        cards.ICLASS_INFO_CMD: responses.get("iclass", ""),
    })


def test_verify_t5577_from_lf_search():
    # The real lf search output alone identifies the T5577 (no detect needed).
    s = _session(lf=LF_SEARCH_T5577)
    check = verify_card(s, CardKind.T5577)
    assert check.ok is True
    assert check.state.password_set is False
    assert s.sent == [cards.LF_SEARCH_CMD]  # detect not needed when lf search sees it


def test_verify_t5577_blank_card_via_detect_fallback():
    # A blank T5577 isn't seen by lf search; the detect fallback finds the chip.
    s = _session(lf=LF_SEARCH_NONE, detect=T55_DETECT_OUT)
    check = verify_card(s, CardKind.T5577)
    assert check.ok is True
    assert check.state.password_set is False
    assert cards.T5577_DETECT_CMD in s.sent


def test_verify_t5577_detects_password():
    out = T55_DETECT_OUT.replace("Password set...... No", "Password set...... Yes")
    s = _session(lf=LF_SEARCH_NONE, detect=out)
    check = verify_card(s, CardKind.T5577)
    assert check.ok is True
    assert check.state.password_set is True


def test_verify_wrong_kind_not_ok():
    s = _session(lf=LF_SEARCH_NONE, detect="", hf=HF_SEARCH_MIFARE)
    check = verify_card(s, CardKind.T5577)
    assert check.ok is False
    assert "T5577" in check.detail


def test_verify_magic_mifare_ok():
    s = _session(hf=HF_SEARCH_MIFARE, magic=MAGIC_INFO_OUT)
    check = verify_card(s, CardKind.MAGIC_MIFARE)
    assert check.ok is True


def test_verify_magic_mifare_plain_card_not_ok():
    s = _session(hf=HF_SEARCH_MIFARE, magic="[+] UID: 01 02 03 04\n")
    check = verify_card(s, CardKind.MAGIC_MIFARE)
    assert check.ok is False
    assert "magic" in check.detail.lower()


def test_verify_writable_iclass_ok():
    s = _session(hf=HF_SEARCH_ICLASS, iclass=ICLASS_INFO_OUT)
    check = verify_card(s, CardKind.WRITABLE_ICLASS)
    assert check.ok is True


def test_verify_no_t5577_not_ok():
    s = _session(lf=LF_SEARCH_NONE, detect="")
    check = verify_card(s, CardKind.T5577)
    assert check.ok is False
    assert "T5577" in check.detail
    assert check.state.password_set is None
