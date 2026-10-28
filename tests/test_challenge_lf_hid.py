import random

from pm3trainer.cards import CardKind
from pm3trainer.challenges.base import Challenge, Mode
from pm3trainer.challenges.lf_hid_create import READ_COMMAND, LfHidCreate
from pm3trainer.testing import FakeSession


def _reader_output(fc: int, cn: int) -> str:
    return f"[+] [H10301] HID H10301 26-bit;  FC: {fc}  CN: {cn}    parity ok\n"


def _make(seed: int = 1) -> LfHidCreate:
    return LfHidCreate(random.Random(seed))


def test_randomizes_fc_and_cn_in_range():
    for seed in range(50):
        c = _make(seed)
        assert 0 <= c.fc <= 255
        assert 0 <= c.cn <= 65535
        assert str(c.fc) in c.task_prompt
        assert str(c.cn) in c.task_prompt


def test_same_seed_gives_same_target():
    a, b = _make(7), _make(7)
    assert (a.fc, a.cn) == (b.fc, b.cn)


def test_check_passes_when_card_matches():
    c = _make()
    session = FakeSession({READ_COMMAND: _reader_output(c.fc, c.cn)})
    assert c.check(session, None) is True
    assert session.sent == [READ_COMMAND]


def test_check_fails_when_card_differs():
    c = _make()
    session = FakeSession({READ_COMMAND: _reader_output(c.fc, (c.cn + 1) % 65536)})
    assert c.check(session, None) is False
    session = FakeSession({READ_COMMAND: _reader_output((c.fc + 1) % 256, c.cn)})
    assert c.check(session, None) is False


def test_check_fails_when_nothing_readable():
    c = _make()
    session = FakeSession({READ_COMMAND: "[!] No data found!\n"})
    assert c.check(session, None) is False
    assert "No HID credential" in c.feedback


def test_check_feedback_names_what_the_card_holds():
    c = _make()
    session = FakeSession({READ_COMMAND: _reader_output(c.fc, (c.cn + 1) % 65536)})
    assert c.check(session, None) is False
    assert c.feedback == f"The card reads as FC {c.fc} CN {(c.cn + 1) % 65536}."


def test_check_passes_on_real_multi_format_output():
    # Real Iceman `lf hid reader`: one line per Wiegand format that decodes.
    c = _make()
    out = (
        "[+] [ind26   ] Indala 26-bit                  FC: 12  CN: 4321  parity ( ok )\n"
        f"[+] [H10301  ] HID H10301 26-bit              FC: {c.fc}  CN: {c.cn}  parity ( ok )\n"
        "[=] found 2 matching 26-bit formats\n"
        "[=] raw: 000000000000002006ec0c86\n"
    )
    assert c.check(FakeSession({READ_COMMAND: out}), None) is True


def test_has_hints_and_solution():
    c = _make()
    assert isinstance(c.hints, list) and c.hints
    assert all(isinstance(h, str) and h for h in c.hints)
    assert isinstance(c.solution, str) and c.solution
    assert "lf hid clone" in c.solution
    assert str(c.fc) in c.solution and str(c.cn) in c.solution


def test_required_card_is_t5577():
    assert _make().required_card is CardKind.T5577


def test_mode_is_create():
    assert _make().mode is Mode.CREATE


def test_is_a_challenge():
    assert isinstance(_make(), Challenge)
