from pm3trainer.answers import norm_hex


def test_norm_hex_lowercases():
    assert norm_hex("DEADBEEF") == "deadbeef"


def test_norm_hex_strips_separators():
    assert norm_hex("de:ad be-ef") == "deadbeef"


def test_norm_hex_trims():
    assert norm_hex("  04A1B2  ") == "04a1b2"
