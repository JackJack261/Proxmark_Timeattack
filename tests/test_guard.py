from pm3trainer.guard import CardState, GuardResult, check

PWD_READ = "lf t55xx read -b 0 -p 11223344"


def test_blocks_t55xx_password_read_when_no_password():
    result = check(PWD_READ, CardState(password_set=False))
    assert result.allowed is False
    assert "password" in result.reason.lower()


def test_blocks_when_password_state_unknown():
    result = check(PWD_READ, CardState(password_set=None))
    assert result.allowed is False


def test_allows_t55xx_password_read_when_password_set():
    result = check(PWD_READ, CardState(password_set=True))
    assert result.allowed is True


def test_allows_plain_t55xx_read_without_password():
    for state in (False, None, True):
        result = check("lf t55xx read -b 0", CardState(password_set=state))
        assert result.allowed is True


def test_allows_unrelated_commands():
    result = check("lf hid clone -w H10301 --fc 240 --cn 2772", CardState(password_set=False))
    assert result.allowed is True


def test_recognizes_pwd_long_flag():
    result = check("lf t55xx read -b 0 --pwd 11223344", CardState(password_set=False))
    assert result.allowed is False


def test_guard_result_is_a_value_object():
    assert GuardResult(allowed=True, reason="") == GuardResult(True, "")


def test_blocks_glued_short_password_flag():
    cmd = "lf t55xx read -b 0 -p11223344"
    for state in (False, None):
        assert check(cmd, CardState(password_set=state)).allowed is False
    assert check(cmd, CardState(password_set=True)).allowed is True


def test_blocks_glued_long_password_flag():
    cmd = "lf t55xx read --pwd11223344"
    assert check(cmd, CardState(password_set=False)).allowed is False
    assert check(cmd, CardState(password_set=True)).allowed is True
