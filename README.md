# WARGENERALS (将台)

> **Multi-agent wargame simulating military command chains** — how organizations command, coordinate, and report under friction. Not just how units fight, but how the *command machine* works. Built with Python, FastAPI, and pluggable LLM agents.

<p align="center">
  <strong>Multi-agent wargame for studying how military organizations command, coordinate and report — not just how units fight.</strong>
</p>

<p align="center">
  English | <a href="README.zh-CN.md">简体中文</a> | <a href="README.ja-JP.md">日本語</a>
</p>

<p align="center">
  <a href=".github/workflows/ci.yml"><img alt="CI" src="https://img.shields.io/badge/CI-passing-brightgreen"></a>
  <img alt="Python" src="https://img.shields.io/badge/python-3.10%2B-blue">
  <img alt="License" src="https://img.shields.io/badge/license-MIT-yellow">
  <img alt="LLM" src="https://img.shields.io/badge/LLM-optional%20(rule%20mode%20works%20offline)-orange">
</p>

<p align="center">
  <strong>Topics:</strong>
  <code>wargame</code> · <code>multi-agent</code> · <code>llm</code> · <code>command-and-control</code> ·
  <code>military-simulation</code> · <code>ai-agents</code> · <code>mission-command</code> ·
  <code>organizational-friction</code> · <code>normandy</code> · <code>fastapi</code>
</p>

## Why WARGENERALS

Most wargame projects simulate the battlefield. WARGENERALS simulates the **command
machine behind it**: how an intent from high command is decomposed layer by layer
into orders, how subordinates execute and report back, how peers coordinate, and
how information decays under latency and loss. The map is a backdrop; the
organization is the simulation.

```
Intent (HQ) → Plan (staff) → Orders (army→division→regiment) → Actions (engine) → Reports (upward)
     ▲                                                                                │
     └─────────────── latency · loss · distortion (organizational friction) ─────────┘
```

## Highlights

- **Multi-faction by design** — any number of factions with explicit *war
  relations* (`WAR_PAIRS`): allied factions can stand adjacent without firing at
  each other. The bundled Normandy scenario runs three factions (US / UK-Canada /
  Germany), each with its own command chain, intelligence and score.
- **Deterministic engine, LLM only decides** — movement, attrition, supply,
  reconnaissance, weather, air interdiction, depot capture and objectives are all
  resolved by a seeded, reproducible engine. LLMs (or a rule fallback) only emit
  typed messages and orders; hallucinated orders are rejected by schema checks.
- **Isolation is enforced, not promised** — each faction has its own message bus,
  intel store and memory. Cross-faction messages raise at the bus layer. Even
  inside one faction, agents share nothing: a corps commander knows exactly what
  his subordinates reported, nothing more.
- **Agents with character** — every position carries a scenario-defined personality
  ("Montgomery-style caution", "fanatic 12th SS", "delayed German high command that
  hoards its panzer reserve"), injected into LLM role cards, with per-position
  behavior overrides (e.g. alert thresholds).
- **Organizational friction as a knob** — message latency and loss rates are live
  parameters: watch commanders decide on late, incomplete information.
- **After-action metrics** — order volume, acknowledgement rate and delay, report
  counts, decision counts, message losses, objective scores, per faction, live.
- **AI scenario import** — paste any battle material (history article, OOB notes,
  news); an LLM classifies it into factions, units, objectives and intents, and the
  scenario becomes playable from the lobby.
- **Tactical agents at the front line** — every combat unit is bound to a
  lightweight tactical agent with local perception, autonomous action (engage on
  contact, withdraw when hurt, hold in place), and asynchronous reporting. The
  bottom of the command chain is AI-driven, not dead data.
- **Nine battlefield factors** — day/night cycle, fatigue & rest, morale &
  breakdown, electronic warfare, artillery suppression, supply lines (ammo/fuel/
  rations), fog of war & camouflage, command radius, combined-arms synergy,
  engineering & fortification, weather effects, unit experience, commander traits,
  and march/deployment formations — all interact in the combat formula.
- **COP-style command center UI** — modern military common operational picture
  interface with NATO-style unit symbols, procedural terrain textures, combat
  effects (explosions, artillery trajectories, fire lines), unit selection &
  detail panels, hover tooltips, force-ratio bars, and day/night progress.

## Quick start

```bash
pip install -e .            # deps: pydantic / fastapi / uvicorn / httpx
python -m wargame.cli serve # open http://127.0.0.1:8300, pick a scenario in the lobby
```

Without an LLM key the system automatically runs the **rule policy** — offline,
deterministic, reproducible — while the full `intent → plan → order → combat →
report` loop still executes.

LLM decision mode (any OpenAI-compatible endpoint; set it in the web settings panel):

```ini
LLM_API_KEY=sk-...                        # never commit this
LLM_BASE_URL=https://api.openai.com/v1    # or DeepSeek / Qwen / Ollama ...
LLM_MODEL=gpt-4o-mini
```

Headless mode:

```bash
python -m wargame.cli run --scenario normandy --ticks 40
python -m wargame.cli serve --scenario cross_river
```

## Scenarios

| Scenario | Description |
|---|---|
| River Crossing (`cross_river`) | Fictional training scenario: two bridges as bottlenecks, organizational friction in full view |
| Normandy 1944 (`normandy`) | Three-faction historical scenario: five-beach landing vs the Atlantic Wall and the panzer reserve |

Scenarios are plain data modules under `src/wargame/scenarios/`. Export the
unified interface (`SCENARIO_NAME`, `build_world()`, `FACTIONS`, `WAR_PAIRS`,
`DEFAULT_INTENTS`, `PLANS`, `RECON_TARGET`, optional `CAMP_NAMES`, `ORG_TITLES`,
`ORG_CONFIG`, `WEATHER`, `AIR_POWER`, `OBJECTIVES`, `REINFORCEMENTS`), register one
line in `scenarios/__init__.py`, and it appears in the lobby.

## Campaign mechanics (as exercised by the Normandy scenario)

- **Large map** 44×30 with zoom/pan; terrain: plain, bocage forest, hills, rivers &
  bridges, marsh (slows armor), rail/road corridors (movement highways).
- **Weather & air interdiction** — scripted weather (the June 6 storm grounds the
  air forces, as it did historically); air power strafes enemy units that moved.
- **Reinforcement schedule** — units arrive on time and attach to a named commander
  (101st Airborne, British 51st Highland, 12th SS, Panzer Lehr).
- **Supply depot capture** — depots can flip to the enemy and feed *them*.
- **Objectives & scoring** — cities carry victory values; control is scored live.

## Settings panel (⚙ in the web UI)

Live-tunable: combat strength / artillery power / entrenchment bonus / terrain
defense / supply rate & radius / recon scale / intel error / move speed / reporting
cadence / message latency & loss (friction) / LLM temperature & per-tick budget.
Engine defaults live in `DEFAULT_TUNING` (`engine/world.py`).

## After-action metrics (right panel)

Live per-faction command health: orders issued, **acknowledgement rate**, ack
delay, situation reports, requests, escalations, intel, decision counts, message
losses, isolation blocks, LLM fallbacks, remaining strength, objective scores.
Full event streams land in `runs/*/events.jsonl` for offline analysis.

## Architecture

```
src/wargame/
├── schemas.py        protocol: messages (8 kinds) / world actions / decisions
├── org.py            ORBAT: position = agent (role card + authority + config)
├── bus.py            faction bus: latency delivery + isolation checks + friction
├── camps.py          faction container: bus + agents + intel store
├── sim.py            scheduler: deliver → decide → engine → recon, JSONL event log
├── agents/
│   ├── base.py       Agent: mailbox + tasks + memory + SituationView (scoped view)
│   ├── rule_policy.py  rule brain (offline, deterministic, LLM fallback)
│   └── llm_policy.py   LLM brain (role card + situation → JSON decision)
├── engine/world.py   deterministic engine: movement/melee/arty/supply/recon/
│                     weather/air interdiction/depots/objectives
├── scenarios/        cross_river / normandy / dynamic (AI-imported)
└── web/              FastAPI (REST+SSE) + dark command-center frontend (no build step)
```

> Python package name is `wargame` (import path), distribution is `wargenerals`,
> brand is **WARGENERALS (将台)** — repo skeleton keeps the historical layout; a
> future major version may unify folder names.

## Testing

```bash
python -m pytest -q
```

Covers: command-chain flow (down and up), combat and intel occurrence, hard
cross-faction isolation blocks, seed determinism, intel-store purity, the
multi-faction Normandy scenario, the dynamic scenario builder, metrics.

## Contributing

Issues and PRs welcome. Please run `python -m pytest -q` before submitting, add
smoke tests for new mechanics/scenarios, write code comments in Chinese explaining
*why*, and **never commit** `.env`, API keys or tokens. See
[CONTRIBUTING.md](CONTRIBUTING.md) and [SECURITY.md](SECURITY.md).

## License

[MIT](LICENSE) © 2026 Wargenerals Contributors
