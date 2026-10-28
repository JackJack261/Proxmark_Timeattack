from pm3trainer.scoring import (
    HINT_PENALTY,
    PASS_PENALTY,
    ChallengeResult,
    HighScores,
    total_seconds,
)


def test_result_total_plain():
    assert ChallengeResult("a", 42.5).total == 42.5


def test_result_total_with_hints():
    assert ChallengeResult("a", 10.0, hints_used=2).total == 10.0 + 60.0


def test_result_total_when_skipped():
    assert ChallengeResult("a", 10.0, skipped=True).total == 10.0 + 180.0


def test_total_seconds_sums_result_totals():
    results = [
        ChallengeResult("plain", 10.0),
        ChallengeResult("hinted", 20.0, hints_used=1),
        ChallengeResult("skipped", 5.0, skipped=True),
    ]
    assert total_seconds(results) == 10.0 + (20.0 + HINT_PENALTY) + (5.0 + PASS_PENALTY)


def test_best_is_none_when_file_absent(tmp_path):
    assert HighScores(str(tmp_path / "scores.json")).best() is None


def test_record_first_total_is_new_best(tmp_path):
    hs = HighScores(str(tmp_path / "scores.json"))
    assert hs.record(100.0) is True
    assert hs.best() == 100.0


def test_record_slower_total_is_not_best(tmp_path):
    hs = HighScores(str(tmp_path / "scores.json"))
    hs.record(100.0)
    assert hs.record(150.0) is False
    assert hs.best() == 100.0


def test_record_faster_total_updates_best(tmp_path):
    hs = HighScores(str(tmp_path / "scores.json"))
    hs.record(100.0)
    assert hs.record(80.0) is True
    assert hs.best() == 80.0


def test_best_survives_new_instance(tmp_path):
    path = str(tmp_path / "scores.json")
    HighScores(path).record(90.0)
    assert HighScores(path).best() == 90.0


def test_corrupt_file_is_treated_as_no_best(tmp_path):
    path = tmp_path / "scores.json"
    path.write_text("{not json", encoding="utf-8")
    hs = HighScores(str(path))
    assert hs.best() is None
    assert hs.record(50.0) is True
    assert hs.best() == 50.0
