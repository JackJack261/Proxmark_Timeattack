from pm3trainer import cards
from pm3trainer.cards import CardKind, verify_card
from pm3trainer.testing import FakeSession

# Real Iceman `lf search` output for an EM410x-programmed T5577 (trimmed).
LF_SEARCH_OUT = (
    "[=] Note: False Positives ARE possible\n"
    "[=] Checking for known tags...\n"
    "[+] EM 410x ID 340073B7A4\n"
    "[+] EM410x ( RF/64 )\n"
    "[+] Valid EM410x ID found!\n"
    "\n"
    "[+] Chipset... T55xx\n"
    "[?] Hint: Try lf t55xx commands\n"
)
# An LF tag that is not a T5577 (no chipset line).
LF_SEARCH_OUT_PLAIN_EM = "[+] EM 410x ID 340073B7A4\n[+] Valid EM410x ID found!\n"
LF_SEARCH_OUT_NONE = "[-] No known 125/134 kHz tags found!\n"
HF_SEARCH_OUT_MIFARE = "[+] ISO14443-a Information\n[+] Valid Mifare Classic tag found\n"
HF_SEARCH_OUT_ICLASS = "[+] Valid iCLASS tag / PicoPass tag found\n"

# Iceman `lf t55xx detect` format.
T55_DETECT_OUT = (
    "[=]  Chip type......... T55x7\n"
    "[=]  Modulation........ ASK\n"
    "[=]  Bit rate.......... 5 - RF/64\n"
    "[=]  Password set...... No\n"
)
T55_DETECT_FAIL = "[!] Could not detect modulation automatically. Try setting it manually with 'lf t55xx config'\n"
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
        cards.LF_SEARCH_CMD: responses.get("lf", ""),
        cards.HF_SEARCH_CMD: responses.get("hf", ""),
        cards.T5577_INFO_CMD: responses.get("t5577", ""),
        cards.MAGIC_INFO_CMD: responses.get("magic", ""),
        cards.ICLASS_INFO_CMD: responses.get("iclass", ""),
    })


def test_verify_t5577_ok():
    s = _session(lf=LF_SEARCH_OUT, t5577=T55_DETECT_OUT)
    check = verify_card(s, CardKind.T5577)
    assert check.ok is True
    assert check.state.password_set is False


def test_verify_t5577_from_real_lf_search_alone():
    # The user's real card: lf search shows the chipset, detect output unhelpful.
    s = _session(lf=LF_SEARCH_OUT, t5577=T55_DETECT_FAIL)
    check = verify_card(s, CardKind.T5577)
    assert check.ok is True
    assert check.state.password_set is False


def test_verify_blank_t5577_via_detect_fallback():
    s = _session(lf=LF_SEARCH_OUT_NONE, t5577=T55_DETECT_OUT)
    check = verify_card(s, CardKind.T5577)
    assert check.ok is True


def test_verify_t5577_old_client_format():
    out = "[=] Chip Type      : T55x7\n[=] Password set   : No\n"
    s = _session(t5577=out)
    assert verify_card(s, CardKind.T5577).ok is True


def test_verify_t5577_detects_password():
    out = T55_DETECT_OUT.replace("Password set...... No", "Password set...... Yes")
    s = _session(lf=LF_SEARCH_OUT, t5577=out)
    check = verify_card(s, CardKind.T5577)
    assert check.ok is True
    assert check.state.password_set is True


def test_verify_t5577_detects_password_old_format():
    out = "[=] Chip Type      : T55x7\n[=] Password set   : Yes\n"
    s = _session(t5577=out)
    assert verify_card(s, CardKind.T5577).state.password_set is True


def test_verify_t5577_plain_lf_tag_not_ok():
    s = _session(lf=LF_SEARCH_OUT_PLAIN_EM, t5577=T55_DETECT_FAIL)
    check = verify_card(s, CardKind.T5577)
    assert check.ok is False
    assert "does not look like a T5577" in check.detail


def test_verify_t5577_hint_line_alone_not_ok():
    # "Try lf t55xx commands" must not count as a chip detection.
    s = _session(lf="[?] Hint: Try lf t55xx commands\n")
    assert verify_card(s, CardKind.T5577).ok is False


def test_verify_hf_card_for_t5577_not_ok():
    s = _session(hf=HF_SEARCH_OUT_MIFARE, magic=MAGIC_INFO_OUT)
    check = verify_card(s, CardKind.T5577)
    assert check.ok is False
    assert "T5577" in check.detail


def test_verify_lf_card_for_hf_challenge_not_ok():
    s = _session(lf=LF_SEARCH_OUT)
    check = verify_card(s, CardKind.MAGIC_MIFARE)
    assert check.ok is False
    assert "No HF card" in check.detail


def test_verify_magic_mifare_ok():
    s = _session(hf=HF_SEARCH_OUT_MIFARE, magic=MAGIC_INFO_OUT)
    check = verify_card(s, CardKind.MAGIC_MIFARE)
    assert check.ok is True


def test_verify_magic_mifare_plain_card_not_ok():
    s = _session(hf=HF_SEARCH_OUT_MIFARE, magic="[+] UID: 01 02 03 04\n")
    check = verify_card(s, CardKind.MAGIC_MIFARE)
    assert check.ok is False
    assert "magic" in check.detail.lower()


def test_verify_writable_iclass_ok():
    s = _session(hf=HF_SEARCH_OUT_ICLASS, iclass=ICLASS_INFO_OUT)
    check = verify_card(s, CardKind.WRITABLE_ICLASS)
    assert check.ok is True


def test_verify_no_card_not_ok():
    s = _session(lf=LF_SEARCH_OUT_NONE, t5577=T55_DETECT_FAIL)
    check = verify_card(s, CardKind.T5577)
    assert check.ok is False
    assert "no t5577" in check.detail.lower()
    assert check.state.password_set is None


def test_verify_empty_output_not_ok():
    s = _session()
    check = verify_card(s, CardKind.WRITABLE_ICLASS)
    assert check.ok is False
