# Contributing

## Working rules for this repository

* Dependency updates: search the whole repository for every occurrence of a dependency (build files, lockfiles, CI workflows, docs) before bumping. A partial bump — declaration updated but lockfile or a pinned action left behind — is the most common cause of "works locally, CI fails". Keep lockfiles in the same commit as the declaration. Move version-coupled toolchain upgrades together in one commit.
* Refactoring: pull latest main first, work on a fresh branch, keep commits atomic with messages that state the why, and always run the full check suite before pushing (for this repo: `python -m pytest -q`). A branch left behind main cannot be merged under the repository's branch protection.
* Merge conflicts: resolve conflicts in the working tree against the latest main; never force-push shared branches; never resolve a conflict by blindly taking either side — re-read both sides and keep both changes when they are both valid.
* Versioning: releases follow X.Y.Z starting at 0.0.0. Last digit = fixes, middle digit = feature work, first digit stays 0 until a stable release is declared. Bump the version in code, CHANGELOG.md and the tag in the same change.

Thanks for your interest in WARGENERALS — a multi-agent simulation of how
military *organizations* command, coordinate and report. New scenarios,
mechanics, metrics and documentation improvements are all welcome.

## Development setup

```bash
git clone <your-fork>
cd wargenerals
pip install -e .            # or pip install -e ".[dev]" for pytest
python -m pytest -q         # baseline must be green
python -m wargame.cli serve # open http://127.0.0.1:8300
```

## Before submitting

1. `python -m pytest -q` passes;
2. new mechanics/scenarios ship with a smoke test (see `tests/test_smoke.py`);
3. the engine stays **deterministic**: all randomness goes through the seeded
   `rng`, and tunable numbers live in `DEFAULT_TUNING` (`engine/world.py`) so
   the settings panel can expose them automatically;
4. isolation invariants are preserved: agents must never see data from other
   factions except through their own intel store (fed by reconnaissance);
5. **never commit** `.env`, API keys or tokens. The CI runs a secret scan.

## Adding a scenario

Create a module under `src/wargame/scenarios/` exporting the unified
interface:

```python
SCENARIO_NAME = "My Battle"
FACTIONS = [{"id": "a", "name": "Side A"}, {"id": "b", "name": "Side B"}]
WAR_PAIRS = [["a", "b"]]        # omit = all distinct factions at war
DEFAULT_INTENTS = {"a": "...", "b": "..."}
PLANS = {"a": [...], "b": [...]}
RECON_TARGET = {"a": [x, y], "b": [x, y]}

def build_world() -> World:
    ...
```

Optional: `CAMP_NAMES`, `ORG_TITLES`, `ORG_CONFIG` (per-position style and
behavior overrides), `WEATHER`, `AIR_POWER`, `OBJECTIVES`, `REINFORCEMENTS`.
Register one line in `scenarios/__init__.py` and it appears in the lobby.

## Commit style

- `feat: add …` / `fix: …` / `docs: …` / `test: …`
- one concern per PR
- for big design changes, open an issue first

## License

By contributing you agree that your contributions are licensed under the
[MIT License](LICENSE).
