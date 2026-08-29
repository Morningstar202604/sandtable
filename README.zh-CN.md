# Sandtable

<p align="center">
  <strong>多智能体军队指挥链推演系统——模拟的重点是"军队这台组织机器如何指挥、协同与反馈"，而不只是部队怎么打。</strong>
</p>

<p align="center">
  <a href="README.md">English</a> | 简体中文 | <a href="README.ja-JP.md">日本語</a>
</p>

<p align="center">
  <a href=".github/workflows/ci.yml"><img alt="CI" src="https://img.shields.io/badge/CI-passing-brightgreen"></a>
  <img alt="Python" src="https://img.shields.io/badge/python-3.10%2B-blue">
  <img alt="License" src="https://img.shields.io/badge/license-MIT-yellow">
  <img alt="LLM" src="https://img.shields.io/badge/LLM-%E5%8F%AF%E9%80%89%EF%BC%88%E8%A7%84%E5%88%99%E6%A8%A1%E5%BC%8F%E7%A6%BB%E7%BA%BF%E5%8F%AF%E8%B7%91%EF%BC%89-orange">
</p>

## 为什么做 Sandtable

多数兵棋项目模拟的是战场，Sandtable 模拟的是战场背后的**指挥机器**：
上级意图如何被层层分解为命令、下级如何自主执行并反馈、同级如何横向协同、
信息如何在延迟与丢失中失真。地图只是背景板，**组织本身才是被模拟的对象**。

```
意图(上级) → 方案(参谋) → 命令(军→师→团) → 行动(世界引擎) → 报告/告警(上行)
     ▲                                                          │
     └────────────── 延迟 · 丢失 · 失真（组织摩擦）──────────────┘
```

## 核心特性

- **多方阵营**——任意数量阵营 + 显式"交战关系"（WAR_PAIRS）：同盟接壤不交战。
  内置诺曼底场景即三方（美军/英加军/德军），各自独立指挥链、情报与计分。
- **确定性引擎，LLM 只做决策**——机动/交战/补给/侦察/天气/空军遮断/补给站
  争夺/目标计分全部由固定种子引擎结算；LLM（或规则降级）只产出类型化消息
  与命令，幻觉命令在 schema 校验处被拦截。
- **隔离是硬约束**——每阵营独立消息总线与情报库，跨阵营消息在总线层直接拒绝；
  阵营内智能体同样零共享：军长知道的，仅仅是报告送达的那些。
- **有性格的智能体**——每个职位带场景定义的指挥风格与历史性格
  （"蒙哥马利式的谨慎"、"狂热的第12SS"、"扣押装甲预备队的迟缓德军统帅部"），
  注入 LLM 角色卡，并支持职位级行为参数覆盖（如告警兵力阈值）。
- **组织摩擦旋钮**——消息延迟与丢失率实时可调：观察指挥员基于迟到、
  不完整的信息决策。
- **复盘指标**——各方的命令量、确认率与延迟、报告/请示/告警量、决策次数、
  电文中断、目标得分，实时统计。
- **AI 场景导入**——把战役资料（战史、兵力描述、新闻）粘进大厅，LLM 自动
  分类提取阵营/部队/目标/意图，即刻生成可推演场景。

## 快速开始

```bash
pip install -e .            # 依赖：pydantic / fastapi / uvicorn / httpx
python -m wargame.cli serve # 打开 http://127.0.0.1:8300，在主界面选择场景
```

无 LLM Key 时自动使用**规则策略**——离线、确定性、可复现，
"意图→方案→命令→交战→反馈"全链路照常运转。

LLM 决策（任何 OpenAI 兼容端点，可在网页设置面板填写）：

```ini
LLM_API_KEY=sk-...                        # 永远不要提交到仓库
LLM_BASE_URL=https://api.openai.com/v1    # 或 DeepSeek / 通义 / Ollama 等
LLM_MODEL=gpt-4o-mini
```

命令行模式：

```bash
python -m wargame.cli run --scenario normandy --ticks 40
python -m wargame.cli serve --scenario cross_river
```

## 场景

| 场景 | 说明 |
|---|---|
| 渡河攻坚（cross_river） | 虚构训练场景：两座桥是瓶颈，组织摩擦集中体现 |
| 诺曼底登陆 1944（normandy） | 三方历史场景：五滩上陆 vs 大西洋壁垒+装甲预备队 |

场景是纯数据模块（`src/wargame/scenarios/`），导出统一接口
（`SCENARIO_NAME` / `build_world()` / `FACTIONS` / `WAR_PAIRS` / `DEFAULT_INTENTS` /
`PLANS` / `RECON_TARGET`，可选 `CAMP_NAMES`、`ORG_TITLES`、`ORG_CONFIG`、
`WEATHER`、`AIR_POWER`、`OBJECTIVES`、`REINFORCEMENTS`），在 `scenarios/__init__.py`
注册一行即可出现在主界面。

## 战役级机制（诺曼底场景实测）

- **大地图 44×30**：滚轮缩放 / 拖拽平移；地形含树篱(bocage)、沼泽（迟滞装甲）、
  铁路公路（机动走廊）；
- **天气与空军遮断**：D-Day 风暴瘫痪空中力量（史实），天气按脚本演变；
- **增援批次**：101 空降 / 英51高地师 / 12SS / 装甲教导师按时刻表入场；
- **补给站争夺**：可被敌军夺占反哺对方；
- **目标计分**：城市带分值，控制权实时计入复盘得分。

## 设置面板（网页右上 ⚙）

实时可调：战斗强度 / 炮兵威力 / 工事加成 / 地形加成 / 补给速率与半径 /
侦察倍率 / 敌情误差 / 移速倍率 / 报告节奏 / 消息延迟与丢失率 / LLM 温度与预算。
默认值集中在 `engine/world.py` 的 `DEFAULT_TUNING`。

## 复盘指标（右栏页签）

实时统计各方：命令下行量、**确认率与确认延迟**、态势报告/请示/告警、情报、
决策次数、电文中断、隔离拦截、LLM 降级、剩余兵力、目标得分。
事件全量落盘 `runs/*/events.jsonl`，可离线分析。

## 架构

```
src/wargame/
├── schemas.py        协议：消息(8类)/世界动作/决策
├── org.py            编制表：职位即智能体（角色卡+权限+职位级配置）
├── bus.py            阵营消息总线：延迟投递+隔离硬校验+组织摩擦
├── camps.py          阵营容器：总线+智能体组+情报库
├── sim.py            编排：投递→决策→引擎→侦察，事件流落盘 JSONL
├── agents/           base(智能体) / rule_policy(规则脑) / llm_policy(LLM 脑)
├── engine/world.py   确定性引擎（机动/交战/炮兵/补给/侦察/天气/空军/目标）
├── scenarios/        cross_river / normandy / dynamic(AI 导入)
└── web/              FastAPI(REST+SSE) + 深色指挥中心前端（无构建依赖）
```

> 包名 `wargame`、产品名 Sandtable——历史原因，后续大版本可能统一。

## 测试

```bash
python -m pytest -q
```

覆盖：指挥链贯通、交战与情报、阵营隔离硬拦截、同种子可复现、情报纯净、
多方诺曼底场景、AI 动态场景构建、复盘指标。

## 贡献

欢迎 Issue 与 PR：提交前 `python -m pytest -q` 全绿；新机制/新场景附带冒烟
测试；代码注释用中文、只写"为什么"；**绝不提交** `.env`、密钥与令牌。
详见 [CONTRIBUTING.md](CONTRIBUTING.md) 与 [SECURITY.md](SECURITY.md)。

## 许可证

[MIT](LICENSE) © 2026 Sandtable Contributors
