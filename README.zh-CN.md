# 将台 WARGENERALS

> **多智能体兵棋推演系统**，模拟军队指挥链如何在摩擦与延迟中指挥、协同与反馈。不只模拟部队怎么打，更模拟*指挥机器*如何运转。Python + FastAPI + 可插拔 LLM 智能体。

<p align="center">
  <strong>研究一支军队如何把指挥员的意图逐层分解为命令、在延迟与丢失中执行并反馈——地图只是背景板，组织本身才是被模拟的对象。</strong>
</p>

<p align="center">
  <a href="README.md">English</a> | 简体中文 | <a href="README.ja-JP.md">日本語</a>
</p>

<p align="center">
  <a href=".github/workflows/ci.yml"><img alt="CI" src="https://img.shields.io/badge/CI-passing-brightgreen"></a>
  <img alt="Python" src="https://img.shields.io/badge/python-3.10%2B-blue">
  <img alt="License" src="https://img.shields.io/badge/license-MIT-yellow">
  <img alt="LLM" src="https://img.shields.io/badge/LLM-%E5%8F%AF%E9%80%89%EF%BC%88%E8%A7%84%E5%88%99%E6%A8%A1%E5%BC%8F%E7%A6%BB%E7%BA%BF%E5%8F%AF%E8%B7%91%EF%BC%89-orange">
  <img alt="Tests" src="https://img.shields.io/badge/tests-47%20passing-green">
</p>

<p align="center">
  <strong>标签：</strong>
  <code>兵棋推演</code> · <code>多智能体</code> · <code>llm</code> · <code>指挥控制</code> ·
  <code>军事仿真</code> · <code>ai-agents</code> · <code>任务式指挥</code> ·
  <code>组织摩擦</code> · <code>斯大林格勒</code> · <code>诺曼底</code> · <code>fastapi</code>
</p>

## 界面预览

<p align="center">
  <img src="docs/screenshot.png" alt="将台指挥台——实时态势图、指挥链与战况电文" width="860">
</p>

指挥台是单页深色 COP 界面——中央实时态势图，左侧指挥链，右侧战况电文与讲评面板。

## 目录

- [界面预览](#界面预览)
- [为什么做将台](#为什么做将台wargenerals)
- [核心特性](#核心特性)
- [快速开始](#快速开始)
- [战役场景](#战役场景)
- [Web 指挥台使用指南](#web-指挥台使用指南)
- [指挥与控制模型](#指挥与控制模型)
- [LLM 模式](#llm-模式)
- [命令行（headless）](#命令行headless)
- [战役机制](#战役机制)
- [复盘与回放](#复盘与回放)
- [设置面板](#设置面板)
- [架构](#架构)
- [开发](#开发)
- [FAQ 与排障](#faq-与排障)
- [贡献](#贡献)
- [许可](#许可)

## 为什么做将台（WARGENERALS）

多数兵棋项目模拟的是战场，将台模拟的是战场背后的**指挥机器**：
上级意图如何被层层分解为命令、下级如何自主执行并反馈、同级如何横向协同、
信息如何在延迟与丢失中失真。地图只是背景板，**组织本身才是被模拟的对象**。

```
意图(上级) → 方案(参谋) → 命令(军→师→团) → 行动(世界引擎) → 报告/告警(上行)
     ▲                                                          │
     └────────────── 延迟 · 丢失 · 失真（组织摩擦）──────────────┘
```

每个阵营都是一个**闭环**：它只知道自己报告送回来的东西，只能通过自己的侦察
看到敌人，命令会在通信降级时迟到或丢失。你不是在直接操作部队——你是在观察
（并作为*导演部*扰动）一台必须自行运转的组织机器。

## 核心特性

**指挥机器**

- **多方阵营设计**——任意数量阵营 + 显式"交战关系"（`WAR_PAIRS`）：同盟接壤不交战。
  诺曼底即三方（美军/英加军/德军），各自独立指挥链、情报与计分。
- **隔离是硬约束**——每阵营独立消息总线与情报库，跨阵营消息在总线层直接拒绝；
  阵营内智能体同样零共享：军长知道的，仅仅是报告送达的那些。
- **有性格的智能体**——每个职位带场景定义的指挥风格与历史性格（"蒙哥马利式的谨慎"、
  "狂热的第12SS"、"扣押装甲预备队的迟缓德军统帅部"），注入 LLM 角色卡，并支持
  职位级行为参数覆盖（如告警兵力阈值）。
- **组织摩擦旋钮**——消息延迟、丢失率与电子战干扰实时可调：观察指挥员基于迟到、
  不完整的信息决策，关键命令被干扰截断。
- **一线战术 Agent**——每个作战单元绑定轻量战术 Agent，具备本地感知、自主行动
  （遇敌接战/受创后撤/就地防御）与异步上报。指挥链最底层由 AI 驱动，而非死数据。

**确定性引擎**

- **确定性引擎，LLM 只做决策**——机动/交战/补给/侦察/天气/空军遮断/补给站争夺/
  目标计分全部由固定种子引擎结算（同一种子 ⇒ 同一场战役）。LLM（或规则降级）
  只产出类型化消息与命令，幻觉命令在 schema 校验处被拦截。
- **九大战场因素**——昼夜、疲劳与休整、士气与崩溃、电子战、炮火压制、补给线
  （弹药/燃料/食品）、战争迷雾与伪装、指挥范围、兵种协同、工程与工事、天气影响、
  部队经验、指挥官特质、行军/战斗队形——全部在战斗公式中交互叠加。

**指挥台（Web UI）**

- **COP 指挥中心界面**——NATO 军事符号、程序化地形纹理、战斗特效（爆炸/炮击弹道/
  火力线）、单位选中与详情面板、悬停提示、兵力对比条、昼夜进度指示。
- **战役简报**——每个场景都带作战简报，开推前先读；推演中每 5 拍产出指挥摘要
  （天气/目标控制/兵力对比）。
- **导演部（导调）**——推演中随时向任意职位注入情况（新任务、敌军集结、天气骤变、
  情报通报），或编写*导调剧本*在指定拍自动触发。

**LLM 与复盘**

- **AI 想定导入**——把战役资料（战史、兵力描述、新闻）粘进大厅，LLM 自动分类提取
  阵营/部队/目标/意图，即刻生成可推演场景。
- **复盘指标与回放**——各方的实时指挥链健康度、战力/得分/目标控制曲线、
  Markdown 复盘报告，以及 `runs/*/events.jsonl` 全量事件日志供离线回放。
- **斯大林格勒场景**——以伏尔加河与火车站为焦点的城市攻防战：雪暴→阴→晴天气脚本、
  街道争夺、双方增援。

## 快速开始

需要 **Python 3.10+**。无需 LLM Key 即可运行——内置规则策略完全离线、确定性。

```bash
# 1. 安装
python -m venv .venv
source .venv/bin/activate        # Windows: .venv\Scripts\activate
pip install -e .

# 2. 启动 Web 指挥台
python -m wargame.cli serve      # → http://127.0.0.1:8300
```

打开指挥台，在开始页选择场景、阅读简报，然后开始推演。要启用 LLM 决策，在
**设置**面板或 `.env` 中配置 Key——见 [LLM 模式](#llm-模式)。

## 战役场景

| 场景 | id | 说明 |
|---|---|---|
| 渡河攻坚 | `cross_river` | 虚构训练场景：两座桥为瓶颈，组织摩擦展露无遗 |
| 诺曼底 1944 | `normandy` | 三方历史场景：五滩头登陆 vs 大西洋壁垒与装甲预备队 |
| 斯大林格勒 1942 | `stalingrad` | 双方城市消耗战：伏尔加河与火车站，雪暴→阴→晴脚本，双方增援 |

场景是 `src/wargame/scenarios/` 下的纯数据模块，导出统一接口（`SCENARIO_NAME`、
`build_world()`、`FACTIONS`、`WAR_PAIRS`、`DEFAULT_INTENTS`、`PLANS`、
`RECON_TARGET`，以及可选的 `CAMP_NAMES`、`ORG_TITLES`、`ORG_CONFIG`、`WEATHER`、
`AIR_POWER`、`OBJECTIVES`、`REINFORCEMENTS`、`BRIEFING`），在
`scenarios/__init__.py` 注册一行即可出现在开始页。见 [开发](#开发) 的新增步骤。

## Web 指挥台使用指南

指挥台是单页深色指挥中心界面，分两种模式：

**开始/设置区**（左侧导航：想定库 / 兵力编成 / 导演部设定 / 智能体调试）：

- **想定库**——浏览场景、阅读简报、AI 导入想定、调战役参数。
- **兵力编成**——查看每个职位的角色卡、权限与行为参数覆盖。
- **导演部设定**——设置各阵营开局意图、调组织摩擦、编排导调剧本。
- **智能体调试**——实时查看每个智能体的信箱/任务/记忆/决策历史，回放 LLM 原始
  请求与响应，导出整场推演 JSON 或 Markdown 复盘报告。

**指挥台（推演视图）**：

- **地图**——可缩放画布：NATO 符号、程序化地形、战斗特效、昼夜暗化、兵力对比条。
- **战况电文**——指挥链上的每条消息（意图→方案→命令→确认→报告→请示→告警→情报），
  分类着色、可按类型过滤。
- **一线分队**——每个战术 Agent 的实时状态与最近行动。
- **导演部讲评**——实时指挥链健康度 + 战力/得分/目标控制曲线；一键导出 Markdown
  复盘报告。

## 指挥与控制模型

- **任务式指挥（Auftragstaktik）**——命令携带意图而非步骤，下级自选打法并沿链条上报。
- **消息种类**——`intent`（上级意图）、`plan`（参谋方案）、`order`（命令下行）、
  `ack`（确认上行）、`sitrep`（态势报告上行）、`request`/`escalation`（请示/告警上行）、
  `intel`（情报通报）。
- **摩擦**——每条消息经总线携带可配置的延迟、丢失率与电子战干扰；高优先级消息部分
  受保护，模拟军事冗余信道。
- **隔离**——每阵营一条总线、一个情报库、一份记忆；除共享世界引擎（与敌方火力）外
  概不相通。
- **导演部**——可随时向任意职位注入情况，或用剧本在指定拍自动触发。推演是一场可扰动
  的进行中的实验。

## LLM 模式

设置 `LLM_API_KEY` 后，智能体经任意 OpenAI 兼容端点以**原生工具调用**（结构化输出）
决策；失败时优雅回退到 JSON 提示词路径，再到确定性**规则策略**。全部可用环境变量切换：

| 变量 | 默认 | 含义 |
|---|---|---|
| `LLM_API_KEY` | （空） | API Key。空 ⇒ 规则策略（离线）。切勿提交到仓库。 |
| `LLM_BASE_URL` | `https://api.openai.com/v1` | 任意 OpenAI 兼容端点（OpenAI / DeepSeek / Qwen / Ollama …） |
| `LLM_MODEL` | `gpt-4o-mini` | 模型名 |
| `WARGAME_LLM_TOOLS` | `1` | 用原生工具调用结构化输出；`0` = JSON 提示词路径 |
| `WARGAME_LLM_RETRY` | `2` | 单次请求重试次数（指数退避） |
| `WARGAME_LLM_TIMEOUT` | `90` | 单次请求超时（秒） |
| `WARGAME_MAX_LLM_CALLS` | `40` | 每拍 LLM 调用预算上限（防 token 失控） |
| `WARGAME_LLM_FALLBACK` | `1` | 失败自动降级规则策略；`0` = 直接暴露错误 |
| `WARGAME_LLM_TOP_P` | `1` | 核采样 |
| `WARGAME_LLM_FREQ_PENALTY` / `WARGAME_LLM_PRESENCE_PENALTY` | `0` | 采样惩罚 |
| `WARGAME_SEED` | `7` | 世界随机种子（同种子 ⇒ 同一场战役） |

可在工作目录旁的 `.env`、Web **设置**面板或环境变量中设置。每次 LLM 决策都会在
trace 中完整记录（prompt/响应/延迟/尝试次数），可在智能体调试中心回放。

## 命令行（headless）

```bash
# 无头跑一场战役（默认规则策略），打印人读日志，落盘 events.jsonl
python -m wargame.cli run --scenario normandy --ticks 40
python -m wargame.cli run --scenario stalingrad --ticks 60 --policy llm --seed 7

# 自定义端口启动 Web 指挥台
python -m wargame.cli serve --host 127.0.0.1 --port 8300
python -m wargame.cli serve --scenario stalingrad
```

参数：`--ticks N`、`--policy auto|rule|llm`、`--seed N`、`--scenario <id>`、
`--no-intents`（不注入默认意图）。

## 战役机制

**诺曼底 1944**——44×30 大地图（篱墙、丘陵、河流与桥梁、减速装甲的沼泽、公路/铁路
走廊）；脚本化天气（6 月 6 日风暴如史实般瘫痪空中力量）；空军遮断扫射移动中的敌军；
增援计划（101 空降师、英军第 51 高地师、12SS、装甲教导师）按时抵达并归属指定指挥官；
补给站可被夺取并反哺*敌方*；胜利城市实时计分。

**斯大林格勒 1942**——密集的 20×14 城市网格，伏尔加河切过东翼、火车站是关键目标；
街道是机动走廊、废墟提供掩体、城区机动更慢；天气自雪暴→阴→晴逐步转好；双方均有
脚本化增援（苏军近卫步兵、德军第 6 集团军预备队）。

## 复盘与回放

- **实时指标（右侧面板）**——各方：命令下行、确认率与延迟、态势报告、请示、告警、
  情报、决策次数、电文中断、隔离拦截、LLM 降级、剩余兵力与目标得分。
- **讲评曲线**——战力、得分与目标控制时间线实时绘制。
- **复盘报告**——智能体调试中心可导出 Markdown 报告（总览/指挥链健康度/目标控制
  时序/关键事件），汇总整场推演。
- **事件日志与回放**——每个事件以 JSONL 落在 `runs/<run>/events.jsonl`；
  `src/wargame/replay.py` 可据此离线重建整场推演（坏行自动跳过），复盘报告即
  复用同一条数据管道。

## 设置面板

Web 界面实时可调：战斗力、炮火威力、工事加成、地形防御、补给速率与半径、侦察强度、
情报误差、机动速度、上报节奏、消息延迟与丢失（摩擦）、LLM 温度与每拍预算。
引擎默认值在 `DEFAULT_TUNING`（`src/wargame/engine/world.py`）。

## 架构

```
src/wargame/
├── schemas.py        协议：消息（8 种）/ 世界动作 / 决策
├── org.py            编成：职位 = 智能体（角色卡 + 权限 + 配置）
├── bus.py            阵营总线：延迟投递 + 隔离校验 + 摩擦
├── camps.py          阵营容器：总线 + 智能体 + 情报库
├── sim.py            调度：投递→决策→引擎→侦察，JSONL 事件日志、逐拍指标
├── replay.py         JSONL 回放加载器 + Markdown 复盘报告生成器
├── agents/
│   ├── base.py       Agent：信箱 + 任务 + 记忆 + SituationView（受限视野）
│   ├── rule_policy.py  规则大脑（离线、确定性、LLM 降级）
│   ├── llm_policy.py   LLM 大脑（角色卡 + 态势 → 工具调用 / JSON 决策）
│   └── tactical.py    一线战术 Agent（本地感知 + 自主行动）
├── engine/world.py   确定性引擎：机动/近战/炮击/补给/侦察/天气/空军遮断/
│                     补给站/目标/疲劳/士气
├── scenarios/        cross_river / normandy / stalingrad / dynamic（AI 导入）
└── web/              FastAPI（REST + SSE）+ 深色指挥中心前端（零构建）
```

每拍调度：**投递**（带摩擦延迟的信件）→ **决策**（每个被唤醒的智能体产出消息与命令）
→ **引擎**（机动/交战/补给/天气…）→ **侦察**（情报流入各自阵营情报库）。全部事件经
SSE 推送到浏览器，并追加到 `runs/*/events.jsonl`。

> Python 包名是 `wargame`（导入路径），发行名是 `wargenerals`，品牌为**将台
> WARGENERALS**。仓库保留历史目录布局；未来大版本可能统一目录名。

## 开发

```bash
python -m pytest -q             # 47 项测试：指挥链/隔离/确定性/场景/LLM 路径/回放
python -m ruff check src tests  # 零告警
```

**新增场景**——创建 `src/wargame/scenarios/<name>.py` 导出统一接口（见
[战役场景](#战役场景)），在 `scenarios/__init__.py` 注册，在 `tests/` 补一条冒烟
测试，跑通全量。**新增职位/机制**——引擎确定且有种子；别让随机性进入智能体，战役才能
复现。

## FAQ 与排障

- **没有 LLM Key 是不是不跑？**——不是：规则策略离线跑通全链路。设 `LLM_API_KEY`
  即切换为 LLM 决策。
- **LLM 决策异常或推演卡住？**——设 `WARGAME_LLM_FALLBACK=0` 直接暴露底层错误，
  而非静默降级；核对 `LLM_BASE_URL`/`LLM_MODEL`；原始请求/响应可在智能体调试中心查看。
- **8300 端口被占用？**——`python -m wargame.cli serve --port <其他端口>`。
- **终端中文乱码？**——CLI 已强制 UTF-8；Windows 请用 UTF-8 终端（如 `chcp 65001`）。
- **同一种子结果不同？**——请确保策略模式一致：规则与 LLM 本就是两种策略。

## 贡献

欢迎 Issue 与 PR。提交前请确保：`python -m pytest -q` 全绿、`ruff check` 零告警、
新机制/场景有冒烟测试、代码注释用中文说明*为什么*，并且**绝不提交** `.env`、API Key
或 token（CI 的密钥泄漏扫描会让构建失败）。参见 [CONTRIBUTING.md](CONTRIBUTING.md)
与 [SECURITY.md](SECURITY.md)。

## 许可

[MIT](LICENSE) © 2026 Wargenerals Contributors
