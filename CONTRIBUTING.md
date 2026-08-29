# Contributing

Thanks for your interest in Sandtable — a multi-agent simulation of how
military *organizations* command, coordinate and report. New scenarios,
mechanics, metrics and documentation improvements are all welcome.

## Development setup

```bash
git clone <your-fork>
cd sandtable
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
