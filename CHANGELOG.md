# Changelog

All notable changes to this project are documented here.
Format: [Keep a Changelog](https://keepachangelog.com/en/1.1.0/);
versioning follows [Semantic Versioning](https://semver.org/).

## [Unreleased]

## [0.9.4] - 2026-09-01

### Added — 朝向指示、视角过渡、炮击弹道
- **单位朝向指示箭头** — NATO图标上显示facing方向箭头，接战时变为红色高亮，清晰指示部队推进/防御方向
- **视角切换扫描线过渡** — 导演/红军/蓝军视角切换时，军事风格水平扫描线从上到下扫过+整体淡入，0.6秒完成
- **炮击弹道抛物线动画** — fire事件触发时，从炮兵位置到目标画抛物线虚线弹道，弹丸带发光尾迹飞行，落点爆炸（径向渐变+扩散圈）
- **炮兵开火修复** — 修复ew_jamming=0.3导致PLAN/ORDER关键消息被电子战干扰丢失、指挥链断裂、炮兵始终无order的严重bug

### Fixed
- **ew_jamming上限** 从0.6降至0.2（0.3以上会导致指挥链关键消息大量丢失）
- **高优先级消息保护** — priority<=1的消息（作战命令/方案）ew_jamming影响降至40%，延迟增幅降至50%，模拟军事通信的冗余校验机制
- **朝向箭头颜色变量** 修复`c is not defined` JS错误（变量名应为sideColor）

## [0.9.3] - 2026-09-01

### Added — 战斗特效与移动动画
- **战斗特效系统** — 从事件流实时提取战斗动作，在地图上渲染视觉特效：
  - 爆炸（explosion）：combat事件触发，径向渐变闪光+扩散圈，0.8秒衰减
  - 大爆炸（bigExplosion）：单位全损时触发，更大更亮+碎片飞溅，1.2秒衰减
  - 火力线（fireline）：战术Agent攻击时，从攻击方到目标的虚线弹道+命中闪光
- **单位移动平滑插值** — 记录单位渲染位置，每帧lerp到目标位置（18%/帧），移动流畅不跳变；距离过远时直接对齐（避免重置后缓慢漂移）
- **智能动画循环** — 有单位移动或活跃特效时持续rAF重绘，动画结束后自动停止，零性能浪费
- **特效生命周期管理** — 每个特效有start/duration，过期自动移除；上限60个防止内存膨胀

## [0.9.2] - 2026-09-01

### Changed — 前端美学升级与性能优化
- **地图渲染全面重构** — 离屏canvas缓存地形层（性能提升：地形只在map/尺寸变化时重绘）；程序化地形纹理（河流渐变光泽、森林树点、丘陵等高线、城镇建筑块、桥梁木纹）；NATO军事符号风格单位图标（步兵菱形/装甲方形/炮兵圆形/侦察三角形，渐变填充+白色边框+内部兵种符号+精致兵力条）；状态光环径向渐变（接战红脉冲/防御青/后撤金/推进绿）；夜间暗化+单位微光+扫描线+暗角。
- **requestAnimationFrame节流** — drawMap合并频繁调用（拖拽/缩放/fetchState），避免重复渲染。
- **战术面板节流** — fetchState每1.2秒触发的战术面板刷新节流到2秒一次，减少DOM重建。
- **面板美学增强** — 指挥链节点悬停发光/激活脉冲/连接线渐变；电文流入场动画/时间轴左侧线/类型色边框/战术事件绿色底/告警橙色底/丢包红色底；一线分队卡片玻璃拟态/状态色边框/接战脉冲/全损灰度；顶栏运行指示灯脉冲/昼夜徽章三色发光；按钮涟漪微交互/launch-hero军事绿渐变；面板标题军事标注竖线；滚动条美化。
- **URL参数直达** — `?deck=1` 直接进入指挥台（调试/分享用）。
- **修复** — COP覆盖层CSS误将.deck从position:fixed改为relative导致地图容器高度异常（21262px）、地形层被推出视口；.map-wrap缺少flex:1导致canvas撑大容器。

## [0.9.1] - 2026-09-01

### Added — 战役特征增强（v6 "真实大型战役"）
- **昼夜循环** — 24 拍一昼夜（昼6/昏6/夜6/昏6 区间划分），夜间侦察半径、炮兵射程、近战伤害、机动速度全面受限；可开关。
- **疲劳与休整** — 连续机动/交火累积疲劳，待机/防御恢复；疲劳越高战力越差，疲劳过高分队自主休整。
- **士气状态机** — steady → shaken → breaking（溃退）→ reorg（重组）；受创冲击、低士气崩溃、脱离接触恢复、重组后按比例恢复兵力。打的是"组织崩溃"而非单纯血条。
- **炮火压制（软杀伤）** — 被炮击目标进入"被压制"状态，战力与机动双降、持续数拍。
- **电子战/通信干扰** — `ew_jamming` 参数叠加到消息丢失率与延迟，战场电磁环境恶化指挥链路。
- **方向性侧翼** — 从目标背后/侧向进攻，阵地防御优势失效（`flank_dir_bonus`）。
- **战术Agent 全面升级** — 一线分队 LLM 驱动（节流唤醒、规则兜底）；更多战术行为：夜间保守、疲劳休整、士气重组上报、受创自主后撤/就地防御、接触/告警/例行上报；决策日志。
- **调试 API** — `/api/debug/tactical`：每个战术Agent 的实时状态、最近决策回放。

### Changed
- **前端 COP 指挥中心重构** — 从"牛皮纸台账"改为现代军事指挥中心（通用作战图 COP）语言：战术网格底纹、深炭指挥舱、玻璃拟态浮动面板、硬朗军事按钮、电报风电文流。
- **地图单位状态可视化** — 战术Agent 状态点（接战红脉冲/防御青/后撤金/推进绿）、被压制红框闪烁、士气濒崩暗罩、疲劳三角警示。
- **新增"一线分队"面板** — 指挥台右侧实时展示每个战术Agent 的分队状态/兵力/士气/疲劳/坐标/最近决策。
- **顶栏昼夜/天气指示** — 昼/昏/夜 与当前天气实时显示。
- **新增 20+ 战役参数** — 昼夜、疲劳、士气、压制、电子战、方向侧翼全部进入设置面板与调参API。

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

## v0.9.5 — 单位选中系统 + 详情面板

### 新增
- **单位点击选中**：点击地图上的作战单位，显示选中高亮框（脉冲外发光 + 虚线矩形 + 四角装饰 + 单位名称标签）
- **单位详情面板**：左上角浮动卡片，显示类型/坐标/兵力/补给/疲劳/士气/状态/战术Agent状态
- **键盘快捷键**：按 1-9 快速选中对应单位，Esc 取消选中
- **选中音效反馈**：选中单位时播放提示音

### 修复
- 士气百分比显示错误（10000% → 100%）
- 全局click事件监听器作用域问题（移至全局作用域）
- 命中检测阈值优化（cs*0.5 → cs*0.6）

### 验证
- 23个Python文件语法检查通过
- 浏览器实测：红军/蓝军单位选中、切换、取消均正常
- 详情面板数据正确显示（兵力/补给/疲劳/士气/战术状态）

## v0.9.6 — 前端交互与显示全面优化

### 地图交互优化
- **单位悬停提示（Tooltip）**：鼠标悬停在单位上时显示浮动卡片（名称/类型/兵力/坐标/状态）
- **选中自动聚焦**：点击/键盘选中单位后，地图平滑缩放并聚焦到该单位
- **拖拽边界限制**：防止地图拖拽超出可视范围
- **双击重置视角**：双击地图平滑复位缩放和平移
- **缩放按钮动画**：缩放复位按钮改为弹性动画
- **悬停光标变化**：悬停单位显示pointer，拖拽显示grab

### 数据显示优化
- **昼夜进度条**：顶栏新增昼夜进度条，随推演推进太阳/月亮图标移动，渐变背景反映时段
- **双方兵力对比条**：地图下方新增红蓝兵力对比条，实时显示双方总兵力比值
- **兵力条精致化**：渐变兵力条+低兵力颜色警告（绿/黄/红）

### 面板交互优化
- **指挥链节点点击**：点击指挥链节点自动聚焦到下辖单位并显示详情
- **电文流展开/收起**：点击电文卡片展开详细内容，带平滑高度动画
- **Tab切换动画**：右侧面板tab切换带下划线发光动画
- **指挥链悬停效果**：节点悬停时右移+发光背景
- **电文流悬停效果**：电文悬停时背景高亮+左边框变色

### 微交互与性能
- **按钮点击涟漪**：所有按钮点击时产生径向涟漪效果
- **面板内容淡入**：电文/战术卡片入场滑入动画
- **运行指示灯呼吸**：推演运行时指示灯呼吸脉冲
- **面板标题军事标注线**：左侧渐变竖线装饰
- **滚动条美化**：细窄青色滚动条
- **CSS性能优化**：will-change、contain、transform: translateZ(0) 硬件加速
- **电文流上限**：300条自动清理旧电文

### 验证
- 浏览器实测：hover提示/选中聚焦/指挥链点击/电文展开全部正常
- 昼夜进度条和兵力对比条实时更新正确
- 23个Python文件语法检查通过

## v0.9.7 — 九大战场因素：让战役真正复杂起来

### 新增九大战场因素

#### 第一梯队（战役核心机制）
1. **后勤补给线系统**
   - 弹药/燃料/食品三类资源分离计算
   - 补给线路径检测，敌军围困补给站即切断
   - 弹药不足→战力折扣，燃料不足→机动折扣，断粮→士气下降
   - 补给线切断/恢复事件上报

2. **战争迷雾与侦察增强**
   - 伪装状态（camouflaged）：伪装单位更难被侦察发现，有40%概率不被发现
   - 情报带时间戳，支持过期判断
   - 侦察单位默认伪装，视野范围受地形/昼夜/天气影响

3. **指挥范围与控制**
   - 指挥官单位（is_commander）带指挥光环（默认6格）
   - 单位超出指挥范围→战力折扣25%
   - 指挥官阵亡→附近友军士气下降15点
   - 超出范围事件上报

#### 第二梯队（战术选择丰富度）
4. **兵种协同与克制**
   - 步炮协同：步兵+炮兵相邻→攻击+20%
   - 装步协同：装甲+步兵相邻→攻击+25%
   - 兵种克制：步兵对装甲→攻击+30%
   - 每拍缓存相邻友军兵种，供战斗公式读取

5. **工程与工事系统**
   - 工事构筑需时间（默认3拍），工兵速度×2
   - 工事分3级，每级额外防御+20%
   - 待机/防御状态自动构筑工事
   - 工事升级事件上报

6. **天气影响增强**
   - 雨天→机动-20%，视野-20%
   - 雾天→视野-40%
   - 风暴→炮兵精度-30%，机动-40%
   - 想定支持天气时间表（开局晴→中期雨→后期晴）

#### 第三梯队（深度打磨）
7. **部队经验与训练**
   - 四级经验：新兵/正规/老兵/精锐
   - 交火累积经验，自动升级
   - 老兵战力+15%，精锐战力+30%
   - 经验对士气有保护作用
   - 升级事件上报

8. **指挥官特质**
   - 三种风格：谨慎/均衡/激进
   - 激进型指挥官→攻击+10%
   - 谨慎型指挥官→防御+10%
   - 指挥官能力值（leader_skill）

9. **接敌行军与展开**
   - 两种队形：行军队形/战斗队形
   - 行军队形→机动+30%，但遇敌战力-40%
   - 战斗队形→正常战力，机动正常
   - 展开需1拍，展开完成事件上报

### 前端显示更新
- 单位详情面板新增：弹药/燃料/经验/工事等级/队形/指挥状态/补给线状态
- 地图单位图标新增：指挥官金色星标/伪装虚线边框/补给线切断警告/超出指挥范围感叹号/经验等级标记/行军队形箭头
- 低弹药/低燃料红色警告，老兵绿色，精锐金色

### 场景初始化
- 师属炮兵营设为指挥官（红军激进/蓝军谨慎）
- 装甲团初始正规军经验，侦察连老兵+伪装
- 蓝军防御单位初始工事构筑进度+战斗队形
- 天气想定：0拍晴→30拍阴→50拍雨→80拍晴

### 验证
- 23个Python文件语法检查通过
- API返回所有新字段正确
- 浏览器实测：指挥官星标/伪装边框/详情面板全部正常显示
- 推演中战斗特效与新因素叠加正常
