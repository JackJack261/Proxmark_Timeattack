"""Run scoring and best-time persistence."""
import json
import os
from dataclasses import dataclass
from typing import Optional

HINT_PENALTY = 30.0
PASS_PENALTY = 180.0


@dataclass
class ChallengeResult:
    name: str
    elapsed: float
    hints_used: int = 0
    skipped: bool = False

    @property
    def total(self) -> float:
        penalty = self.hints_used * HINT_PENALTY
        if self.skipped:
            penalty += PASS_PENALTY
        return self.elapsed + penalty


def total_seconds(results: list[ChallengeResult]) -> float:
    return sum(r.total for r in results)


class HighScores:
    def __init__(self, path: str):
        self.path = path

    def best(self) -> Optional[float]:
        try:
            with open(self.path, "r", encoding="utf-8") as f:
                value = json.load(f)["best"]
            return float(value)
        except (OSError, ValueError, KeyError, TypeError):
            return None

    def record(self, total: float) -> bool:
        current = self.best()
        if current is not None and total >= current:
            return False
        tmp_path = self.path + ".tmp"
        try:
            with open(tmp_path, "w", encoding="utf-8") as f:
                json.dump({"best": float(total)}, f)
            os.replace(tmp_path, self.path)
        except OSError:
            try:
                os.remove(tmp_path)
            except OSError:
                pass
            return False
        return True
