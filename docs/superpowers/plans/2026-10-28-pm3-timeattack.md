# Proxmark3 Time Attack Trainer Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** A timed terminal game that teaches Proxmark3 usage by having the player run real `pm3` commands on a connected device across 6 randomized LF/HF read and write challenges, with the game verifying each result on the same hardware.

**Architecture:** Pure logic (output parsers, the command guard, answer normalization, scoring) is isolated into hardware-free modules that are fully unit-tested with captured sample strings. All device I/O funnels through one `Pm3Session` interface; a `FakeSession` test double returns canned `pm3` output so cards, challenges, and the game loop are tested without a Proxmark. The real pexpect session and the exact `pm3` output formats are reconciled in a final on-hardware calibration task.

**Tech Stack:** Python 3, `pexpect` (device session), `pytest` (tests).

**Spec:** `docs/superpowers/specs/2026-10-28-pm3-timeattack-design.md`

## Global Constraints

- Platform: Kali Linux; one Proxmark3 at `/dev/ttyACM0` (port overridable).
- Client invoked as `pm3` or `proxmark3 <port>`; one persistent session for the whole game.
- Challenge order is fixed 1→6. Unlimited retries per challenge; the clock keeps running (time is the penalty).
- Reserved inputs at any command/answer prompt: `hint` (reveals next hint, `HINT_PENALTY = 30`s each, no cap) and `pass` (reveals solution, marks skipped, `PASS_PENALTY = 180`s). Matched case-insensitively on trimmed input.
- A challenge's recorded time = elapsed clock + hints_used×30 + (180 if skipped).
- The card-present + type-verify step happens **before** each challenge's clock starts.
- Exactly one destructive-command guard (the LF T55xx password-read rule); no other command filtering.
- All `pm3` output is ANSI-stripped before any parsing.
- Parsers return a "not found" result (never a false positive) on unexpected output.

## Review Focus

- **Unexpected/garbage `pm3` output** → every parser returns `None`, never a wrong-but-plausible value (tested in Task 1).
- **ANSI color codes in output** → stripped before parsing so matches still succeed (tested in Task 1).
- **Password-read on a card with no/unknown password** → guard blocks and nothing is sent to the device (tested in Task 2).
- **Device unplugged mid-command** (pexpect `EOF`) → `Pm3Disconnected` raised, not a hang or silent pass (tested in Task 5).
- **Command timeout** (pexpect `TIMEOUT`) → `Pm3Timeout` raised and the game offers a retry rather than crashing (tested in Tasks 5 and 13).

---

### Task 1: Output parsers

**Files:**
- Create: `pm3trainer/parsers.py`
- Create: `pm3trainer/__init__.py`
- Test: `tests/test_parsers.py`

**Interfaces:**
- Produces:
  - `strip_ansi(text: str) -> str`
  - `parse_hid(text: str) -> Optional[HidResult]` where `HidResult` is a dataclass `(fc: int, cn: int)`
  - `parse_em410x(text: str) -> Optional[str]` (10 hex chars, lowercase)
  - `parse_mifare_uid(text: str) -> Optional[str]` (hex, lowercase, no separators)
  - `parse_iclass_block(text: str, block: int) -> Optional[str]` (16 hex chars for that block)
  - `parse_search_kind(text: str) -> Optional[str]` → `"LF"`, `"HF"`, or `None`

Representative sample outputs are embedded in the tests; the real formats are reconciled against the device in Task 15, which updates these tests and parsers together.

- [ ] **Step 1: Write failing tests** in `tests/test_parsers.py`:
  - `test_strip_ansi_removes_color_codes` — input with `\x1b[32m…\x1b[0m`, asserts codes gone, text kept.
  - `test_parse_hid_extracts_fc_and_cn` — sample `lf hid reader` output with FC 240 / CN 2772, asserts `HidResult(240, 2772)`.
  - `test_parse_hid_returns_none_on_garbage` — unrelated text asserts `None`.
  - `test_parse_em410x_extracts_id` — sample `lf search` output, asserts the 10-hex id lowercased.
  - `test_parse_mifare_uid_extracts_uid` — sample `hf mf info` output, asserts uid hex lowercased, no separators.
  - `test_parse_iclass_block_extracts_data` — sample block dump, asserts 16-hex for the requested block.
  - `test_parse_search_kind_lf_vs_hf` — one LF sample → `"LF"`, one HF sample → `"HF"`, garbage → `None`.
  - `test_parsers_strip_ansi_before_matching` — a sample wrapped in ANSI codes still parses.

- [ ] **Step 2: Run tests, verify they fail** — `pytest tests/test_parsers.py -v` → FAIL (module/functions missing).

- [ ] **Step 3: Implement** the functions above in `pm3trainer/parsers.py`. Use tolerant regexes (label-anchored, not fixed columns); each parse function calls `strip_ansi` first and returns `None` when its pattern is absent.

- [ ] **Step 4: Run tests, verify they pass** — `pytest tests/test_parsers.py -v` → PASS.

- [ ] **Step 5: Commit** — `git add pm3trainer/parsers.py pm3trainer/__init__.py tests/test_parsers.py && git commit -m "feat: add pm3 output parsers"`

---

### Task 2: Command guard

**Files:**
- Create: `pm3trainer/guard.py`
- Test: `tests/test_guard.py`

**Interfaces:**
- Consumes: `CardState` dataclass defined here — `(password_set: Optional[bool])` (`None` = unknown).
- Produces:
  - `check(cmd: str, card: CardState) -> GuardResult` where `GuardResult` is `(allowed: bool, reason: str)`.

- [ ] **Step 1: Write failing tests** in `tests/test_guard.py`:
  - `test_blocks_t55xx_password_read_when_no_password` — `lf t55xx read -b 0 -p 11223344`, `CardState(password_set=False)` → `allowed is False`, reason mentions password.
  - `test_blocks_when_password_state_unknown` — same cmd, `CardState(password_set=None)` → `allowed is False` (default-deny).
  - `test_allows_t55xx_password_read_when_password_set` — same cmd, `CardState(password_set=True)` → `allowed is True`.
  - `test_allows_plain_t55xx_read_without_password` — `lf t55xx read -b 0`, any state → `allowed is True`.
  - `test_allows_unrelated_commands` — `lf hid clone ...` → `allowed is True`.
  - `test_recognizes_pwd_long_flag` — `--pwd` variant blocked under `password_set=False`.

- [ ] **Step 2: Run tests, verify they fail** — `pytest tests/test_guard.py -v`.

- [ ] **Step 3: Implement** `check` in `pm3trainer/guard.py`: detect an `lf t55xx read` (tokenized) carrying `-p`/`--pwd`; block unless `card.password_set is True`; otherwise allow.

- [ ] **Step 4: Run tests, verify they pass.**

- [ ] **Step 5: Commit** — `git commit -m "feat: add LF T55xx password-read guard"`

---

### Task 3: Answer normalization

**Files:**
- Create: `pm3trainer/answers.py`
- Test: `tests/test_answers.py`

**Interfaces:**
- Produces: `norm_hex(s: str) -> str` — lowercases, strips whitespace and `:`/`-`/space separators; used to compare player-typed hex answers in READ challenges.

- [ ] **Step 1: Write failing tests** in `tests/test_answers.py`:
  - `test_norm_hex_lowercases` — `"DEADBEEF"` → `"deadbeef"`.
  - `test_norm_hex_strips_separators` — `"de:ad be-ef"` → `"deadbeef"`.
  - `test_norm_hex_trims` — `"  04A1B2  "` → `"04a1b2"`.

- [ ] **Step 2: Run tests, verify they fail.**

- [ ] **Step 3: Implement** `norm_hex`.

- [ ] **Step 4: Run tests, verify they pass.**

- [ ] **Step 5: Commit** — `git commit -m "feat: add answer normalization"`

---

### Task 4: Scoring & high-score persistence

**Files:**
- Create: `pm3trainer/scoring.py`
- Test: `tests/test_scoring.py`

**Interfaces:**
- Produces:
  - Constants `HINT_PENALTY = 30.0`, `PASS_PENALTY = 180.0` (seconds).
  - `ChallengeResult` dataclass `(name: str, elapsed: float, hints_used: int = 0, skipped: bool = False)` with a computed property `total: float` = `elapsed + hints_used * HINT_PENALTY + (PASS_PENALTY if skipped else 0)`.
  - `total_seconds(results: list[ChallengeResult]) -> float` — sums each result's `total`.
  - `HighScores(path: str)` with `best() -> Optional[float]` and `record(total: float) -> bool` (writes JSON `{"best": <float>}`; returns `True` if this total is a new best).

- [ ] **Step 1: Write failing tests** in `tests/test_scoring.py` (use `tmp_path` for the file):
  - `test_result_total_plain` — no hints, not skipped → `total == elapsed`.
  - `test_result_total_with_hints` — `hints_used=2` → `total == elapsed + 60`.
  - `test_result_total_when_skipped` — `skipped=True` → `total == elapsed + 180`.
  - `test_total_seconds_sums_result_totals` — mix of plain/hinted/skipped results.
  - `test_best_is_none_when_file_absent`.
  - `test_record_first_total_is_new_best` — returns `True`, persists value.
  - `test_record_slower_total_is_not_best` — returns `False`, keeps old best.
  - `test_record_faster_total_updates_best` — returns `True`, overwrites.
  - `test_best_survives_new_instance` — new `HighScores` on same path reads prior best.

- [ ] **Step 2: Run tests, verify they fail.**

- [ ] **Step 3: Implement** `scoring.py`; `HighScores` tolerates a missing/corrupt file by treating best as absent.

- [ ] **Step 4: Run tests, verify they pass.**

- [ ] **Step 5: Commit** — `git commit -m "feat: add scoring and high-score persistence"`

---

### Task 5: Pm3Session + FakeSession

**Files:**
- Create: `pm3trainer/session.py`
- Create: `pm3trainer/testing.py` (test double, importable by later task tests)
- Test: `tests/test_session.py`

**Interfaces:**
- Produces:
  - `Pm3Session(port: Optional[str] = None)` with `start() -> None`, `run(cmd: str, timeout: float = 20.0) -> str`, `close() -> None`.
  - Exceptions `Pm3Timeout`, `Pm3Disconnected`.
  - `run` returns ANSI-stripped output captured between the sent command and the next `[usb] pm3 -->` prompt.
  - `FakeSession(responses: dict[str, str] | Callable[[str], str], *, fail: Optional[Exception] = None)` implementing the same `start/run/close`, with `.sent: list[str]` recording commands; used by all later tests.

- [ ] **Step 1: Write failing tests** in `tests/test_session.py`:
  - `test_fake_session_records_sent_and_returns_response` — maps a cmd→output, asserts `run` returns it and `sent` logs it.
  - `test_fake_session_raises_configured_error` — configured with `Pm3Timeout` → `run` raises it.
  - `test_run_strips_ansi_from_output` — drive `Pm3Session.run` against a stub spawn object (monkeypatched) emitting ANSI-wrapped text + prompt; assert returned text is stripped.
  - `test_run_raises_disconnected_on_eof` — stub spawn raises pexpect `EOF` → `run` raises `Pm3Disconnected`.
  - `test_run_raises_timeout` — stub spawn raises pexpect `TIMEOUT` → `run` raises `Pm3Timeout`.

- [ ] **Step 2: Run tests, verify they fail.**

- [ ] **Step 3: Implement** `session.py` and `testing.py`. `Pm3Session` wraps `pexpect.spawn`, waits on a prompt regex, maps pexpect `EOF`/`TIMEOUT` to the two exceptions, and routes output through `strip_ansi`. Keep the spawn object injectable (a module-level `_spawn` factory or constructor arg) so tests can substitute a stub; real pexpect behavior is validated live in Task 15.

- [ ] **Step 4: Run tests, verify they pass.**

- [ ] **Step 5: Commit** — `git commit -m "feat: add pm3 session driver and fake"`

---

### Task 6: Card presentation & type verification

**Files:**
- Create: `pm3trainer/cards.py`
- Test: `tests/test_cards.py`

**Interfaces:**
- Consumes: `Pm3Session`-like object; `parsers.parse_search_kind`; `CardState` from `guard`.
- Produces:
  - `CardKind` enum: `T5577`, `MAGIC_MIFARE`, `WRITABLE_ICLASS`.
  - `verify_card(session, expected: CardKind) -> CardCheck` where `CardCheck` is `(ok: bool, state: CardState, detail: str)`. Runs the appropriate search/info command, confirms LF/HF and chip, and sets `state.password_set` (False for freshly verified T5577 unless a password is detected).

- [ ] **Step 1: Write failing tests** in `tests/test_cards.py` using `FakeSession`:
  - `test_verify_t5577_ok` — fake returns T5577-identifying LF output → `ok is True`, kind matches, `state.password_set is False`.
  - `test_verify_wrong_kind_not_ok` — HF card output when expecting `T5577` → `ok is False`, `detail` explains.
  - `test_verify_magic_mifare_ok`.
  - `test_verify_writable_iclass_ok`.
  - `test_verify_no_card_not_ok` — empty/garbage output → `ok is False`.

- [ ] **Step 2: Run tests, verify they fail.**

- [ ] **Step 3: Implement** `cards.py`. Exact detection commands/strings are best-effort here and reconciled in Task 15.

- [ ] **Step 4: Run tests, verify they pass.**

- [ ] **Step 5: Commit** — `git commit -m "feat: add card type verification"`

---

### Task 7: Challenge base + Challenge 1 (LF HID CREATE)

**Files:**
- Create: `pm3trainer/challenges/__init__.py`
- Create: `pm3trainer/challenges/base.py`
- Create: `pm3trainer/challenges/lf_hid_create.py`
- Test: `tests/test_challenge_lf_hid.py`

**Interfaces:**
- Produces:
  - `Mode` enum `CREATE`, `READ`.
  - `Challenge` base with attributes `name: str`, `mode: Mode`, `required_card: CardKind`, `present_prompt: str`, `task_prompt: str`, `hints: list[str]` (ordered, first = nudge, last ≈ command with placeholders), `solution: str` (shown on pass); methods `setup(self, session) -> None` (default no-op) and `check(self, session, player_input: Optional[str]) -> bool`.
    - CREATE: the game runs the player's command first, then calls `check(session, None)`, which reads the card back and compares to the challenge's target.
    - READ: the game calls `setup(session)` once (writes random ground truth), then calls `check(session, answer)`.
    - `hints`/`solution` are consumed by the game loop (Task 13); the base just stores them.
  - `LfHidCreate(rng)` — randomizes FC (0–255) and CN (0–65535); `task_prompt` names them; `check` reads `lf hid reader`, parses via `parse_hid`, compares; `hints` and `solution` reference `lf hid clone` with the target FC/CN.

- [ ] **Step 1: Write failing tests** in `tests/test_challenge_lf_hid.py`:
  - `test_randomizes_fc_and_cn_in_range` — seeded `rng`, asserts ranges and that `task_prompt` contains both values.
  - `test_check_passes_when_card_matches` — `FakeSession` returns `lf hid reader` output matching the target → `check` returns `True`.
  - `test_check_fails_when_card_differs` — mismatching output → `False`.
  - `test_has_hints_and_solution` — `hints` is a non-empty list of strings and `solution` is a non-empty string.
  - `test_required_card_is_t5577` and `test_mode_is_create`.

- [ ] **Step 2: Run tests, verify they fail.**

- [ ] **Step 3: Implement** `base.py` and `lf_hid_create.py`.

- [ ] **Step 4: Run tests, verify they pass.**

- [ ] **Step 5: Commit** — `git commit -m "feat: add challenge base and LF HID create challenge"`

---

### Task 8: Challenge 2 (LF EM410x CREATE)

**Files:**
- Create: `pm3trainer/challenges/lf_em_create.py`
- Test: `tests/test_challenge_lf_em.py`

**Interfaces:**
- Produces: `LfEmCreate(rng)` — `mode=CREATE`, `required_card=T5577`; randomizes a 10-hex id; `check(session, None)` runs `lf search`, parses via `parse_em410x`, compares normalized. Follows the Task 7 base pattern, including `hints` and `solution` (referencing `lf em 410x clone` with the target id).

- [ ] **Step 1: Write failing tests**: `test_randomizes_10hex_id`, `test_check_passes_on_match`, `test_check_fails_on_mismatch`, `test_has_hints_and_solution`, `test_mode_and_card`.
- [ ] **Step 2: Run tests, verify they fail.**
- [ ] **Step 3: Implement** `lf_em_create.py`.
- [ ] **Step 4: Run tests, verify they pass.**
- [ ] **Step 5: Commit** — `git commit -m "feat: add LF EM410x create challenge"`

---

### Task 9: Challenge 3 (HF Mifare Classic CREATE)

**Files:**
- Create: `pm3trainer/challenges/hf_mf_create.py`
- Test: `tests/test_challenge_hf_mf.py`

**Interfaces:**
- Produces: `HfMfCreate(rng)` — `mode=CREATE`, `required_card=MAGIC_MIFARE`; randomizes a 4-byte UID (8 hex); `check(session, None)` runs `hf mf info`, parses via `parse_mifare_uid`, compares normalized. Includes `hints` and `solution` (referencing `hf mf csetuid` with the target UID), per the Task 7 pattern.

- [ ] **Step 1: Write failing tests**: `test_randomizes_4byte_uid`, `test_check_passes_on_match`, `test_check_fails_on_mismatch`, `test_has_hints_and_solution`, `test_mode_and_card`.
- [ ] **Step 2: Run tests, verify they fail.**
- [ ] **Step 3: Implement** `hf_mf_create.py`.
- [ ] **Step 4: Run tests, verify they pass.**
- [ ] **Step 5: Commit** — `git commit -m "feat: add HF Mifare create challenge"`

---

### Task 10: Challenge 4 (HF iClass CREATE)

**Files:**
- Create: `pm3trainer/challenges/hf_iclass_create.py`
- Test: `tests/test_challenge_hf_iclass.py`

**Interfaces:**
- Produces: `HfIclassCreate(rng)` — `mode=CREATE`, `required_card=WRITABLE_ICLASS`; randomizes 8 bytes (16 hex) for a target data block; `check(session, None)` reads that block, parses via `parse_iclass_block`, compares normalized. The exact write/read block command text is reconciled in Task 15; the challenge stores the block number and target as constants so only the command strings change. Includes `hints` and `solution` (referencing the iClass write for the target block), per the Task 7 pattern.

- [ ] **Step 1: Write failing tests**: `test_randomizes_block_data`, `test_check_passes_on_match`, `test_check_fails_on_mismatch`, `test_has_hints_and_solution`, `test_mode_and_card`.
- [ ] **Step 2: Run tests, verify they fail.**
- [ ] **Step 3: Implement** `hf_iclass_create.py`.
- [ ] **Step 4: Run tests, verify they pass.**
- [ ] **Step 5: Commit** — `git commit -m "feat: add HF iClass create challenge"`

---

### Task 11: Challenge 5 (LF EM410x READ)

**Files:**
- Create: `pm3trainer/challenges/lf_em_read.py`
- Test: `tests/test_challenge_lf_em_read.py`

**Interfaces:**
- Produces: `LfEmRead(rng)` — `mode=READ`, `required_card=T5577`; `setup(session)` writes a random 10-hex id to the card (same write command as Task 8) and stores it as ground truth; `check(session, answer)` compares `norm_hex(answer)` to the stored id. No device read in `check` (the player did the reading). Includes `hints` and `solution` (referencing `lf search` and how to read the EM id); `solution` reveals the stored ground-truth id.

- [ ] **Step 1: Write failing tests** using `FakeSession`:
  - `test_setup_writes_random_id_and_records_sent` — asserts a write command appears in `session.sent`.
  - `test_check_passes_when_answer_matches_ground_truth` — feed the stored id (mixed case/separators) → `True`.
  - `test_check_fails_on_wrong_answer` → `False`.
  - `test_has_hints_and_solution`.
  - `test_mode_is_read_and_card_is_t5577`.
- [ ] **Step 2: Run tests, verify they fail.**
- [ ] **Step 3: Implement** `lf_em_read.py`.
- [ ] **Step 4: Run tests, verify they pass.**
- [ ] **Step 5: Commit** — `git commit -m "feat: add LF EM410x read challenge"`

---

### Task 12: Challenge 6 (HF Mifare UID READ)

**Files:**
- Create: `pm3trainer/challenges/hf_mf_read.py`
- Test: `tests/test_challenge_hf_mf_read.py`

**Interfaces:**
- Produces: `HfMfRead(rng)` — `mode=READ`, `required_card=MAGIC_MIFARE`; `setup(session)` writes a random 4-byte UID (same write command as Task 9) and stores it; `check(session, answer)` compares `norm_hex(answer)` to the stored UID. Includes `hints` and `solution` (referencing `hf search` / `hf mf info`); `solution` reveals the stored ground-truth UID.

- [ ] **Step 1: Write failing tests**: `test_setup_writes_random_uid`, `test_check_passes_on_match`, `test_check_fails_on_mismatch`, `test_has_hints_and_solution`, `test_mode_and_card`.
- [ ] **Step 2: Run tests, verify they fail.**
- [ ] **Step 3: Implement** `hf_mf_read.py`.
- [ ] **Step 4: Run tests, verify they pass.**
- [ ] **Step 5: Commit** — `git commit -m "feat: add HF Mifare read challenge"`

---

### Task 13: Game loop & orchestrator

**Files:**
- Create: `pm3trainer/game.py`
- Test: `tests/test_game.py`

**Interfaces:**
- Consumes: a session object; the challenge list; `cards.verify_card`; `guard.check`; `scoring`; injectable `input_fn`, `output_fn`, and `clock` (callable returning float) for testing.
- Produces:
  - `build_challenges(rng) -> list[Challenge]` — the fixed ordered 6.
  - `run_game(session, challenges, *, input_fn, output_fn, clock, scores) -> list[ChallengeResult]`.
  - Per challenge: prompt to present card → `verify_card` loop until the right card (before clock) → `clock()` start → CREATE: read command, `guard.check`, on block print reason and re-loop, else `session.run` then `challenge.check(session, None)`; READ: `challenge.setup`, read answer, `challenge.check(session, answer)` → retry until pass → `clock()` stop → record `ChallengeResult(name, elapsed, hints_used, skipped)`. On `Pm3Timeout` print a message and re-loop; on `Pm3Disconnected` abort with a clear message.
  - **Reserved inputs** checked first at every command/answer prompt (case-insensitive, trimmed): `hint` reveals `challenge.hints[min(next_index, last)]`, increments `hints_used`, and re-loops without consuming a try; `pass` prints `challenge.solution`, sets `skipped=True`, stops the clock, and ends the challenge immediately (recorded as skipped). These are intercepted before `guard.check` and before any `session.run`, so they never reach the device.

- [ ] **Step 1: Write failing tests** in `tests/test_game.py` with `FakeSession`, scripted `input_fn`, a fake `clock` returning queued values, and captured `output_fn`:
  - `test_create_challenge_passes_on_correct_command` — card-ok output + matching readback; one correct command → one passing result, time from the fake clock.
  - `test_create_challenge_retries_until_correct` — first command mismatches, second matches → loops, single result, clock still advancing.
  - `test_guard_block_prevents_send_and_reloops` — a blocked password-read is never in `session.sent`, reason printed, then a valid command passes.
  - `test_wrong_card_reprompts_before_clock` — wrong-kind then right-kind; assert clock start is read only after the right card.
  - `test_read_challenge_setup_writes_and_checks_answer` — `setup` write recorded; correct typed answer passes.
  - `test_timeout_is_recoverable` — `FakeSession` raises `Pm3Timeout` once then succeeds; game re-loops and finishes.
  - `test_disconnect_aborts` — `Pm3Disconnected` → `run_game` stops with an abort signal (exception or sentinel) and a printed message.
  - `test_hint_reveals_and_increments_without_sending` — input `hint` then a correct command; assert a hint string was printed, `result.hints_used == 1`, and `hint` never appears in `session.sent`.
  - `test_multiple_hints_advance_then_cap` — several `hint` inputs advance through the list and stop at the last hint; `hints_used` counts each.
  - `test_pass_skips_and_reveals_solution` — input `pass`; assert the solution was printed, `result.skipped is True`, the challenge ends immediately, and nothing was sent to the device for it.

- [ ] **Step 2: Run tests, verify they fail.**

- [ ] **Step 3: Implement** `game.py` per the flow above.

- [ ] **Step 4: Run tests, verify they pass** — `pytest tests/test_game.py -v`.

- [ ] **Step 5: Commit** — `git commit -m "feat: add game loop and orchestrator"`

---

### Task 14: Entry point & wiring

**Files:**
- Create: `pm3trainer/__main__.py`
- Create: `pm3trainer.py` (thin launcher so `python3 pm3trainer.py` works)
- Create: `README.md`
- Test: `tests/test_entrypoint.py`

**Interfaces:**
- Consumes: everything above.
- Produces: `main(argv: list[str]) -> int` — parses optional `--port`, builds the real `Pm3Session`, seeds an `rng`, builds challenges, prints intro (including that `hint` and `pass` are available and their penalties), runs `run_game` with real `input`/`print`/`time.monotonic` and a `HighScores` at `scores.json`, prints the results table (per challenge: time including penalties, hints used, and a SKIPPED marker where applicable) + total + high-score line, closes the session, returns an exit code. Startup failure (`Pm3Disconnected` on `start()`) prints a clear message and returns non-zero. A `KeyboardInterrupt` (Ctrl-C) anywhere is caught, the session is closed cleanly in a `finally`, a short "quit" message is printed, and `main` returns a non-zero code — no traceback.

- [ ] **Step 1: Write failing tests** in `tests/test_entrypoint.py`:
  - `test_main_reports_clean_exit_when_session_fails_to_start` — monkeypatch session start to raise `Pm3Disconnected`; assert non-zero return and a helpful message, no traceback.
  - `test_main_parses_port_arg` — assert `--port /dev/ttyACM1` is passed to the session constructor (via monkeypatched session capturing the port).
  - `test_main_handles_keyboard_interrupt` — monkeypatch `run_game` to raise `KeyboardInterrupt`; assert the session's `close` was called, a quit message printed, non-zero return, no traceback.

- [ ] **Step 2: Run tests, verify they fail.**

- [ ] **Step 3: Implement** `__main__.py`, the `pm3trainer.py` launcher, and a `README.md` covering install (`apt install python3-pexpect`, `pytest`), required cards, and how to run.

- [ ] **Step 4: Run tests, verify they pass**, and run the full suite — `pytest -v`.

- [ ] **Step 5: Commit** — `git commit -m "feat: add entry point, launcher, and README"`

---

### Task 15: Live hardware calibration (manual verification)

**Files:**
- Modify: `pm3trainer/parsers.py`, `pm3trainer/cards.py`, and challenge command strings as needed.
- Modify: the corresponding tests to embed **real captured** `pm3` output.

This task has no new unit test of its own; it reconciles best-effort formats with the real client and is verified by acceptance steps on the device.

- [ ] **Step 1:** With a Proxmark3 connected, run `pm3` and capture real output for each command the game uses: `lf search`, `lf hid reader`, `lf em 410x reader`, `hf search`, `hf mf info`, the iClass block read, and each write command. Save the captures.
- [ ] **Step 2:** For any parser or detection whose real output differs from the sample, update the regex **and** replace the sample string in that module's test with the real capture; re-run `pytest -v` → PASS.
- [ ] **Step 3:** Confirm the exact iClass write/read block command strings (Task 10) against the client and fix them in `hf_iclass_create.py`.
- [ ] **Step 4:** Play the full game end-to-end on hardware with a T5577, a magic Mifare, and a writable iClass: verify each of the 6 challenges presents, verifies the card, times, and scores correctly; verify the guard blocks a password-read on a passwordless T5577 without touching the device; verify high score records.
- [ ] **Step 5: Commit** — `git commit -m "fix: calibrate parsers and commands against real hardware"`

---

## Notes

- Keep `pm3` command strings the player is expected to type documented in the README so they can learn them, but the game judges by **reading the card**, not by string-matching the command (except the guard).
- The whole suite must stay runnable without hardware (`pytest -v`); only Task 15 requires the device.
