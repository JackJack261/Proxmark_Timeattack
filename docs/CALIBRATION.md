# Task 15 — On-Hardware Calibration Checklist

The game is fully implemented and its logic is unit-tested without hardware
(101 tests). But there was **no Proxmark3 available during development**, so
every `pm3` command string and output-parsing pattern is a **best-effort
guess**, isolated as named constants/regexes. This file is the checklist to
reconcile them against your real `pm3` client on Kali. Until this pass is
done, expect commands/parsers to need tuning.

## How to calibrate

1. Connect the Proxmark3. Run `pm3` and capture **real** output for each
   command the game uses:
   - `lf search`, `lf hid reader`, `lf em 410x reader` / `lf em 410x read`
   - `hf search`, `hf 14a info`, `hf mf info`
   - the iClass block read, and each write command
2. For any parser/detection whose real output differs from the sample,
   update the regex **and** replace the sample string in that module's test,
   then re-run `python -m pytest -q` until green.
3. Play the full game end-to-end with a T5577, a magic Mifare, and a
   writable iClass.

## Where the best-effort strings live

| Area | File | Constants / patterns |
|------|------|----------------------|
| LF/HF + chip detection | `pm3trainer/cards.py` | `LF_SEARCH_CMD`, `HF_SEARCH_CMD`, `T5577_INFO_CMD`, `MAGIC_INFO_CMD`, `ICLASS_INFO_CMD`, chip + password regexes |
| Output parsing | `pm3trainer/parsers.py` | `parse_hid`, `parse_em410x`, `parse_mifare_uid`, `parse_iclass_block`, `parse_search_kind` |
| HID create | `pm3trainer/challenges/lf_hid_create.py` | read cmd + `lf hid clone` template |
| EM create/read | `lf_em_create.py` (`CLONE_TEMPLATE`, read cmd) — `lf_em_read.py` imports `CLONE_TEMPLATE` |
| Mifare create/read | `hf_mf_create.py` (`SET_UID_TEMPLATE`, read cmd) — `hf_mf_read.py` imports `SET_UID_TEMPLATE` |
| iClass create | `hf_iclass_create.py` | `BLOCK` (=7), `READ_TEMPLATE`, `WRITE_TEMPLATE` |
| Session | `pm3trainer/session.py` | prompt regex `[usb] pm3 -->`, command-echo stripping, `start()` launcher `pm3 [port]`, EOF/TIMEOUT mapping |

## Specific things flagged during build — check these first

- **iClass (most likely to need changes):** real `hf iclass rdbl/wrbl`
  usually needs a **key** option (`-k` / `--ki`, elite/credit). The chosen
  data block `BLOCK = 7` may be key-protected on your cards. Pick a block
  you can actually write, and add the key option to `READ_TEMPLATE` /
  `WRITE_TEMPLATE`. If a template gains format fields beyond `{block}` /
  `{data}`, update `check()` and the test `.format()` calls too.
- **Card detection (T5577 calibrated):** detection uses `lf search` /
  `hf search` per band. A T5577 is recognized from `lf search`'s
  `Chipset... T55xx` line (confirmed on a real Iceman client) or from
  `lf t55xx detect`'s `Chip type......... T55x7` line for blank cards.
  Confirm `hf search` output still contains the HF markers
  `parse_search_kind` looks for.
- **Negation heuristic:** `parse_search_kind` and `cards._matches` skip any
  line containing `no` / `not` / `invalid` / `failed`. It fails *closed*
  (re-prompt, never a false positive), but check no real positive line
  carries one of those words (e.g. `T55x7 (not configured)`).
- **Magic Mifare detection** relies on a `Magic capabilities` line in
  `hf 14a info`, which may not appear for gen2 cards — adjust if so.
- **Password-protected T5577:** `lf t55xx detect` may not print a chip line
  for a password-protected tag, so verification could report "not a T5577".
- **Guard glued flag:** the guard now blocks glued password forms
  (`-p11223344`); confirm whether your `pm3` even accepts that form (the
  hardening is harmless either way).
- **Shared write templates:** EM and Mifare write commands each live in ONE
  constant (the create module) used by both the create and read challenge —
  fix once, both update.
- **Session behavior:** `Pm3Session` prompt-matching, command-echo handling,
  startup and timeouts were only stub-tested — validate them live.

## Safety note (do not regress)

The one destructive-command guard (`pm3trainer/guard.py`) blocks an
`lf t55xx read` that carries a password flag unless the card is known to
have a password set. This exists to prevent corrupting a passwordless
T5577. Keep it intact through any calibration changes.
