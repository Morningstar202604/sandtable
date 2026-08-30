# Changelog

All notable changes to this project are documented here.
Format: [Keep a Changelog](https://keepachangelog.com/en/1.1.0/);
versioning follows [Semantic Versioning](https://semver.org/).

## [Unreleased]

## [0.9.0] - 2026-08-30

### Changed
- **Rebrand to 将台 WARGENERALS** — new logo emblem (将台 = raised command pavilion:
  eave + star + crossed command batons) with inline SVG and matching favicon; product
  name updated across the app shell, FastAPI title and README set (en/zh-CN/ja-JP).
- **Visual retone — 参谋部 · 深邃军绿 × 牛皮纸台账** — background/panel palette
  shifted from navy-blue to deep olive military green; brass ledger marking retained;
  introduced kraft-paper archive tone (`--paper` token family); info/faction blue kept
  as the semantic "blue force / intelligence" color.
- Distribution name `sandtable` → `wargenerals` (import package stays `wargame`).

## [0.1.0] - 2026-08-29

Initial open-source release.

### Added
- **Multi-faction architecture** — any number of factions with explicit war
  relations (`WAR_PAIRS`); allied factions stand adjacent without firing.
- **Deterministic world engine** — movement, melee attrition, artillery,
  supply, reconnaissance with fog-of-war, scripted weather, air interdiction,
  capturable supply depots, scored objectives, timed reinforcement waves.
- **Position = agent** — mailbox + task queue + private memory per position;
  pluggable policies (rule brain / LLM brain with JSON schema + fallback).
- **Hard isolation** — per-faction message bus and intel store;
  cross-faction messages rejected at the bus layer, with live metrics.
- **Organizational friction knobs** — message latency multiplier and loss
  rate, live-tunable during a run.
- **Character & config per position** — command style / historical personality
  injected into LLM role cards, per-position behavior overrides
  (e.g. withdrawal thresholds).
- **Web command center** — scenario lobby, animated command-chain graph,
  map with zoom/pan, director/agent perspectives, live message feed,
  after-action metrics panel, settings with 20+ live parameters,
  AI scenario import.
- **AI scenario import** — paste battle material, an LLM extracts factions,
  units, objectives and intents into a playable dynamic scenario.
- **Scenarios**: River Crossing (fictional training), Normandy 1944
  (US / UK-Canada / Germany three-faction historical).
- **Events as source of truth** — every tick's events persisted to
  `runs/<timestamp>/events.jsonl` for replay and offline analysis.
- **Test suite** (8 tests): command-chain flow, combat/intel occurrence,
  isolation enforcement, seed determinism, intel purity, multi-faction
  Normandy, dynamic scenario builder, metrics.
