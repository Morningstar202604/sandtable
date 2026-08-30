# 将台 WARGENERALS

> **マルチエージェント兵棋シミュレーション**——軍隊の指揮連鎖が摩擦と遅延の中でどう指揮・協同・報告するかを再現。Python + FastAPI + プラガブル LLM エージェント。

<p align="center">
  <strong>多智能体による軍隊組織の指揮連鎖シミュレーション——部隊の戦い方ではなく、組織がどう指揮し・協同し・報告するかを再現する。</strong>
</p>

<p align="center">
  <a href="README.md">English</a> | <a href="README.zh-CN.md">简体中文</a> | 日本語
</p>

<p align="center">
  <a href=".github/workflows/ci.yml"><img alt="CI" src="https://img.shields.io/badge/CI-passing-brightgreen"></a>
  <img alt="Python" src="https://img.shields.io/badge/python-3.10%2B-blue">
  <img alt="License" src="https://img.shields.io/badge/license-MIT-yellow">
</p>

<p align="center">
  <strong>トピック：</strong>
  <code>ウォーゲーム</code> · <code>マルチエージェント</code> · <code>llm</code> · <code>指揮統制</code> ·
  <code>軍事シミュレーション</code> · <code>ai-agents</code> · <code>任務型指揮</code> ·
  <code>組織摩擦</code> · <code>ノルマンディー</code> · <code>fastapi</code>
</p>

## 将台 WARGENERALS について

ほとんどのウォーゲームは戦場をシミュレーションします。将台 WARGENERALS が模拟するのは
戦場の背後にある**指揮組織そのもの**です。上級司令部の意図がどう階層ごとに命令へ
分解され、下位部隊がどう自律的に実行・報告し、同級部隊がどう連携し、情報が
遅延と喪失の中でどう歪むか。地図は背景にすぎず、**組織こそがシミュレーションの主体**です。

```
意図(上級) → 計画(参謀) → 命令(軍→師団→連隊) → 行動(ワールドエンジン) → 報告(上へ)
     ▲                                                                    │
     └──────── 遅延・喪失・歪み（組織摩擦）────────┘
```

## 主な特徴

- **多陣営設計**——陣営数は赤青 2 者に限定されません。エンジンには「交戦関係」
  （WAR_PAIRS）があり、同盟同士は隣接しても発砲しません。同梱のノルマンディー
  シナリオは 米軍/英加軍/ドイツ軍 の 3 陣営で、各陣営が独立した指揮系統・情報・
  スコアを持ちます。
- **決定論的エンジン、LLM は意思決定のみ**——移動/戦闘/補給/偵察/天候/航空
  阻害/補給所争奪/目標スコアはすべて固定シードのエンジンが解決。LLM（または
  ルールフォールバック）は型付きメッセージと命令のみを出力し、幻覚的な命令は
  スキーマ検証で拒否されます。
- **分離は強制**——陣営ごとに独立したメッセージバスと情報ストアを持ち、
  陣営をまたぐメッセージはバス層で拒否されます。陣営内でもエージェント間の
  共有はゼロ：軍団長が知っているのは、届いた報告だけです。
- **個性を持つエージェント**——各ポジションにはシナリオ定義の指揮スタイルと
  歴史的性格（「モンゴメリー式の慎重さ」「狂信的な第12SS」「装甲予備を温存する
  迅速さを欠く独軍上部」）が LLM ロールカードに注入され、ポジション単位の
  動作パラメータ上書きも可能です。
- **組織摩擦のノブ**——メッセージの遅延率と喪失率はリアルタイム調整可能。
  指揮官が遅れた不完全な情報で意思決定する様子を観察できます。
- **アフターアクション指標**——命令数、応答率と遅延、報告数、決定回数、
  通信喪失、目標スコアを陣営別にリアルタイム集計。
- **AI シナリオインポート**——戦史資料を貼り付けると LLM が陣営/部隊/目標/
  意図を分類・抽出し、すぐ遊べるシナリオを生成します。

## クイックスタート

```bash
pip install -e .            # 依存: pydantic / fastapi / uvicorn / httpx
python -m wargame.cli serve # http://127.0.0.1:8300 を開いてロビーでシナリオを選択
```

LLM キーがなければ自動的に**ルールポリシー**で動作——オフラインで決定論的、
再現可能。「意図→計画→命令→交戦→報告」の全ループがそのまま回ります。

LLM 意思決定モード（OpenAI 互換エンドポイント全般、Web 設定パネルで設定可）：

```ini
LLM_API_KEY=sk-...                        # リポジトリにコミットしないこと
LLM_BASE_URL=https://api.openai.com/v1    # DeepSeek / Qwen / Ollama なども可
LLM_MODEL=gpt-4o-mini
```

ヘッドレスモード：

```bash
python -m wargame.cli run --scenario normandy --ticks 40
python -m wargame.cli serve --scenario cross_river
```

## シナリオ

| シナリオ | 説明 |
|---|---|
| 渡河攻堅（cross_river） | 架空の訓練シナリオ：2つの橋がボトルネック、組織摩擦が凝縮 |
| ノルマンディー1944（normandy） | 3 陣営の歴史シナリオ：5 海岸上陸 vs 大西洋の壁+装甲予備 |

シナリオは `src/wargame/scenarios/` 配下の純データモジュールです。統一インターフェース
（`SCENARIO_NAME` / `build_world()` / `FACTIONS` / `WAR_PAIRS` / `DEFAULT_INTENTS` /
`PLANS` / `RECON_TARGET`、オプションで `CAMP_NAMES` / `ORG_TITLES` / `ORG_CONFIG` /
`WEATHER` / `AIR_POWER` / `OBJECTIVES` / `REINFORCEMENTS`）を exports し、
`scenarios/__init__.py` に 1 行登録すればロビーに現れます。

## キャンペーン機構（ノルマンディーシナリオで実装済み）

- **大型マップ 44×30**：ホイールズーム/ドラッグ移動対応。地形は bocage の森、
  沼沢（装甲を遅滞）、鉄道・道路（機動回廊）などを含む。
- **天候と航空阻害**：D-Day の嵐で航空戦力が ground（史実どおり）。天候は
  スクリプトに従い推移し、移動した敵部隊を航空戦力が飽和攻撃します。
- **増援スケジュール**：101 空挺/英第51高地師団/第12SS/装甲教導師団が時刻表どおり
  到着し、指定の指揮官の指揮下に入ります。
- **補給所争奪**：補給所は敵に奪われ、奪った側の補給になります。
- **目標スコア**：都市には勝利点が付き、制圧状況がリアルタイム集計されます。

## 設定パネル（Web UI 右上 ⚙）

リアルタイム調整可能：戦闘強度/砲兵威力/陣地加成/地形防御/補給速度と半径/
偵察倍率/敵情誤差/移動速度/報告間隔/メッセージ遅延と喪失率（摩擦）/
LLM 温度と呼び出し予算。デフォルト値は `engine/world.py` の `DEFAULT_TUNING` に集約。

## アフターアクション指標（右パネル）

陣営別の指揮系統ヘルスをリアルタイム集計：命令数、**応答率と遅延**、状況報告、
上申、警報、偵察、決定回数、通信喪失、分離遮断、LLM フォールバック、残存戦力、
目標スコア。イベントは `runs/*/events.jsonl` に全量保存され、オフライン分析が可能。

## アーキテクチャ

```
src/wargame/
├── schemas.py        プロトコル：メッセージ(8種)/ワールドアクション/決定
├── org.py            編制表：ポジション=エージェント（ロールカード+権限+設定）
├── bus.py            陣営バス：遅延配信+分離ハードチェック+組織摩擦
├── camps.py          陣営コンテナ：バス+エージェント群+情報ストア
├── sim.py            スケジューラ：配信→決定→エンジン→偵察、JSONL イベントログ
├── agents/           base(エージェント) / rule_policy(ルール脳) / llm_policy(LLM 脳)
├── engine/world.py   決定論的エンジン
├── scenarios/        cross_river / normandy / dynamic(AI インポート)
└── web/              FastAPI(REST+SSE) + ダーク指揮センター UI（ビルド不要）
```

> Python パッケージ名は `wargame`（import パス）、配布パッケージ名は `wargenerals`、
> ブランド名は **将台 WARGENERALS**——リポジトリ構成は歴史的構造を維持しており、
> 今後のメジャーバージョンで統一する予定です。

## テスト

```bash
python -m pytest -q
```

指揮系統の流れ、交戦と偵察、陣営分離のハードブロック、シード再現性、情報ストアの
純度、多陣営ノルマンディー、AI 動的シナリオ、指標をカバーしています。

## コントリビューション

Issue・PR を歓迎します。提出前に `python -m pytest -q` を通すこと、新しい機構には
スモークテストを添えること、`.env`・API キー・トークンを**絶対にコミットしない**こと。
詳しくは [CONTRIBUTING.md](CONTRIBUTING.md) と [SECURITY.md](SECURITY.md) を参照。

## ライセンス

[MIT](LICENSE) © 2026 Wargenerals Contributors
