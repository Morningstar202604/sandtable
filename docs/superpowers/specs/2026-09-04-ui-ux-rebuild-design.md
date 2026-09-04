# Phase 3 重构 Spec：UI/UX 全面升级 + 美术精致化

**日期**: 2026-09-04
**目标**: 基于已有代码结构，对沙盒推演系统进行全量重构，包括后端 API、前端简报屏、战役状态栏、战报流渲染、CSS 美术升级。

---

## 一、现状与问题（来自 Phase 1-2 诊断）

### 数据链路断裂（最关键）
| 问题 | 位置 | 影响 |
|------|------|------|
| `BattlePreset.meta()` 不返回 `briefing` 字段 | `battlelib.py:147-151` | 所有预设的战役背景对前端完全不可见 |
| 无 `/api/briefing` 接口 | `app.py` | 前端无法获取单战役简报详情 |
| `_scenario_info()` 不拼入战役背景 | `app.py` | 想定列表 API 缺背景信息 |
| `KIND_META` 无 `briefing_pulse` 映射 | `app.js:40-44` | 战报事件完全无法被前端识别 |
| 无简报屏/战役状态栏组件 | `index.html` | 用户直接跳入空白的推演界面 |

### 业务流程断层
- 选择场景后直接进入 canvas map，无任何战役上下文说明
- 没有 "简报 → 确认 → 开始推演" 的流程
- 推演中用户不知道当前目标进度、天气趋势、敌情动态

### 美术精致度不足
- 卡片缺乏深度感（只有简单 border）
- 按钮无 press 反馈（点击后无视觉变化）
- 动画/过渡太生硬（缺少 ease-in-out）
- 地图单位形状未区分兵种类型
- 关键事件无颜色高亮

---

## 二、重构范围

### 后端（3 文件）
1. `src/wargame/battlelib.py` — `meta()` 加入 briefing
2. `src/wargame/web/app.py` — 新增 `/api/briefing`，更新 `_scenario_info()`
3. `src/wargame/sim.py` — 无需改动（`get_briefing()` + `_emit_briefing_pulse()` 已完成）

### 前端（3 文件）
1. `src/wargame/web/static/index.html` — 新增简报屏 + 战役状态栏
2. `src/wargame/web/static/js/app.js` — 简报逻辑 + 战报渲染 + KIND_META 补全
3. `src/wargame/web/static/css/app.css` — 卡片深度、按钮质感、动画过渡、单位形状

---

## 三、详细任务清单

### Step 1: 后端 API 修复（独立验证）

#### 任务 1.1: `BattlePreset.meta()` 加入 briefing
**文件**: `src/wargame/battlelib.py:147-151`

```python
def meta(self) -> dict:
    result = {
        "id": self.pid, "name": self.name, "codename": self.codename,
        "era": self.era, "theater": self.theater, "category": self.category,
        "desc": self.desc, "env": self.env, "params": self.params,
        "sides": self.sides,
    }
    if self.briefing:
        result["briefing"] = self.briefing
    return result
```

#### 任务 1.2: 新增 `/api/briefing` GET 接口
**文件**: `src/wargame/web/app.py`

在 `/api/battle/presets` 路由附近添加：
```python
@app.get("/api/briefing")
def get_briefing(pid: str | None = None):
    """获取战役简报详情。"""
    if not _HAS_BATTLELIB:
        return {"ok": False, "error": "战役库未加载"}
    preset = next((p for p in battlelib.BATTLE_PRESETS if p.pid == pid), None)
    if not preset:
        return {"ok": False, "error": f"未找到战役: {pid}"}
    return {"ok": True, "briefing": preset.briefing, "meta": preset.meta()}
```

#### 任务 1.3: `_scenario_info()` 拼入战役背景
**文件**: `src/wargame/web/app.py`

在现有 `_scenario_info()` 返回 dict 中追加 `briefing` 字段（若存在对应 preset）。

### Step 2: 前端简报屏（HTML + JS）

#### 任务 2.1: `index.html` 新增简报屏结构
在 `<div id="app">` 顶部、`<div class="studio-view">` 之前插入：
```html
<div id="briefing-screen" class="briefing-screen hidden">
  <div class="briefing-card">
    <div class="briefing-header">
      <span class="briefing-eyebrow">CINEMATIC BRIEFING</span>
      <h1 class="briefing-title" id="briefing-title"></h1>
      <span class="briefing-codename" id="briefing-codename"></span>
    </div>
    <div class="briefing-body">
      <div class="briefing-section">
        <h3>战役背景</h3>
        <p id="briefing-narrative"></p>
      </div>
      <div class="briefing-section">
        <h3>兵力对比</h3>
        <div id="briefing-force-comparison"></div>
      </div>
      <div class="briefing-section">
        <h3>地形特点</h3>
        <p id="briefing-terrain"></p>
      </div>
      <div class="briefing-section">
        <h3>天气趋势</h3>
        <p id="briefing-weather"></p>
      </div>
    </div>
    <div class="briefing-footer">
      <button id="briefing-back-btn" class="btn-secondary">← 返回</button>
      <button id="briefing-confirm-btn" class="btn-primary">确认，开始推演</button>
    </div>
  </div>
</div>
```

#### 任务 2.2: `app.js` 新增简报逻辑
- 在 `S` state 对象中添加 `briefing: null`
- 修改 `launchExercise()` 流程：先获取简报 → 显示简报屏 → 用户确认后 → 调用 `/api/control start`
- 新增 `showBriefingScreen(preset)` 函数：填充标题/背景/兵力/地形/天气
- 新增 `hideBriefingScreen()` 函数
- `briefing-confirm-btn` 点击 → 调用原有启动逻辑

#### 任务 2.3: `app.js` KIND_META 补全
```javascript
const KIND_META = {
  ...
  briefing_pulse: { label: '指挥摘要', icon: '📡', color: '#dfb26a' },
  ...
};
```

### Step 3: 战役状态栏（campaign-bar）

#### 任务 3.1: `index.html` 新增 campaign-bar
在 deck 视图的 topbar 下方添加：
```html
<div id="campaign-bar" class="campaign-bar hidden">
  <div class="campaign-stat">
    <span class="campaign-label">T-</span><span class="campaign-tick" id="cb-tick">0</span>
  </div>
  <div class="campaign-stat">
    <span class="campaign-label">天气:</span>
    <span class="campaign-weather" id="cb-weather">晴</span>
  </div>
  <div class="campaign-objectives" id="cb-objectives">
    <!-- 动态填充 -->
  </div>
  <div class="campaign-factions">
    <div class="faction-stat red-faction" id="cb-red">
      <span class="faction-dot red-dot"></span>
      <span class="campaign-unit-count" id="cb-red-count">0</span> 单位
    </div>
    <div class="faction-stat blue-faction" id="cb-blue">
      <span class="faction-dot blue-dot"></span>
      <span class="campaign-unit-count" id="cb-blue-count">0</span> 单位
    </div>
  </div>
</div>
```

#### 任务 3.2: `app.js` 更新 campaign-bar
- 在 `handleEvent()` 中捕获 `briefing_pulse` 事件，更新 campaign-bar 各字段
- tick 更新：从 `S.tick` 同步
- 天气：从 event.payload.weather_name
- 目标控制：从 event.payload.objectives 渲染为圆点行
- 单位数：从 event.payload.unit_counts

### Step 4: feed 流战役事件渲染

#### 任务 4.1: `app.js` 新增 `briefing_pulse` 处理
在 `handleEvent()` 函数的 switch/if 块中加入：
```javascript
case 'briefing_pulse':
  renderBriefingPulse(event);
  break;
```

新增 `renderBriefingPulse(event)` 函数，生成金色主题卡片：
- 图标: 📡
- 标题: "指挥摘要 — T-{tick}"
- 内容: 天气 + 目标控制状态 + 兵力概览
- CSS class: `feed-card briefing-pulse`（金色边框）

### Step 5: CSS 精致化

#### 任务 5.1: 卡片深度感
```css
.info-card, .feed-card, .briefing-card {
  box-shadow: 0 1px 3px rgba(0,0,0,0.4), 0 4px 12px rgba(0,0,0,0.3);
  border: 1px solid rgba(223,178,106,0.15);
  transition: box-shadow 0.2s ease, transform 0.15s ease;
}
.info-card:hover, .feed-card:hover {
  box-shadow: 0 2px 6px rgba(0,0,0,0.5), 0 8px 20px rgba(0,0,0,0.35);
  transform: translateY(-1px);
}
```

#### 任务 5.2: 按钮质感
```css
.btn-primary, .btn-secondary {
  transition: all 0.15s ease-in-out;
  box-shadow: 0 2px 4px rgba(0,0,0,0.3), inset 0 1px 0 rgba(255,255,255,0.05);
}
.btn-primary:hover {
  transform: translateY(-1px);
  box-shadow: 0 4px 8px rgba(0,0,0,0.4), inset 0 1px 0 rgba(255,255,255,0.08);
}
.btn-primary:active {
  transform: translateY(0);
  box-shadow: 0 1px 2px rgba(0,0,0,0.4);
}
```

#### 任务 5.3: 简报屏样式
```css
.briefing-screen {
  position: fixed; inset: 0; z-index: 1000;
  background: rgba(6,11,9,0.95);
  display: flex; align-items: center; justify-content: center;
}
.briefing-card {
  max-width: 680px; width: 90%;
  background: linear-gradient(135deg, #0a1510 0%, #0d1f17 100%);
  border: 1px solid rgba(223,178,106,0.3);
  box-shadow: 0 0 40px rgba(223,178,106,0.1);
}
.briefing-eyebrow {
  letter-spacing: 0.3em; font-size: 0.65rem; color: #dfb26a;
  text-transform: uppercase;
}
.briefing-title { font-size: 1.6rem; color: #e8dcc8; margin: 0.3rem 0; }
.briefing-section h3 { color: #dfb26a; font-size: 0.8rem; letter-spacing: 0.15em; margin-top: 1.2rem; }
```

#### 任务 5.4: 战役状态栏样式
```css
.campaign-bar {
  display: flex; align-items: center; gap: 1.5rem;
  padding: 0.4rem 1rem;
  background: rgba(10,21,16,0.95);
  border-bottom: 1px solid rgba(223,178,106,0.2);
  font-size: 0.75rem;
}
.campaign-label { color: #7a9a7a; margin-right: 0.3rem; }
.campaign-tick { color: #dfb26a; font-weight: bold; }
.campaign-weather { color: #6ba3ff; }
.faction-dot {
  display: inline-block; width: 8px; height: 8px;
  border-radius: 50%; margin-right: 4px; vertical-align: middle;
}
.red-dot { background: #ff5b6a; box-shadow: 0 0 4px #ff5b6a; }
.blue-dot { background: #6ba3ff; box-shadow: 0 0 4px #6ba3ff; }
```

#### 任务 5.5: 战报卡片金色主题
```css
.feed-card.briefing-pulse {
  border-left: 3px solid #dfb26a;
  background: linear-gradient(90deg, rgba(223,178,106,0.08) 0%, transparent 100%);
}
.feed-card.briefing-pulse .feed-card-icon { color: #dfb26a; }
```

### Step 6: 地图 Canvas 精致化

#### 任务 6.1: 单位形状按兵种区分
在地图渲染循环中，根据 `unit.type` 绘制不同形状：
- `infantry` → 圆形
- `armor` → 正方形
- `artillery` → 三角形
- `air` → 菱形
- `navy` → 五边形

#### 任务 6.2: 目标控制点发光效果
对受控目标绘制带光晕的外圈（根据控制方颜色 glow）：
```javascript
// 在 drawUnit 函数中
if (unit.is_target) {
  ctx.beginPath();
  ctx.arc(x, y, radius + 4, 0, Math.PI * 2);
  ctx.strokeStyle = controlledBy === 'red' ? 'rgba(255,91,106,0.6)' : 'rgba(107,163,255,0.6)';
  ctx.lineWidth = 2;
  ctx.stroke();
}
```

---

## 四、验收标准

### 后端
- [ ] `pytest -q` 全部通过（含 Phase 1 & 2 测试）
- [ ] `/api/briefing?pid=normandy_1944` 返回包含 briefing 文本的 JSON
- [ ] `/api/battle/presets` 返回的每个 preset 都包含 `briefing` 字段（如有）

### 前端
- [ ] 选择场景后先显示简报屏，再进入推演界面
- [ ] 简报屏可正常展示标题/背景/兵力/地形/天气
- [ ] 点击"确认，开始推演"后进入指挥台视图
- [ ] 点击"← 返回"回到场景选择
- [ ] 推演运行中 campaign-bar 显示 T-xx、天气、各单位数
- [ ] 每 5 tick 出现金色边框的战报卡片在 feed 流中
- [ ] 战报卡片有 📡 图标、指挥摘要标题、天气/目标/兵力内容

### 美术
- [ ] 卡片有 hover 阴影加深效果
- [ ] 按钮有 press 下沉效果
- [ ] 简报屏有渐变背景和发光边框
- [ ] 地图单位按兵种显示不同形状
- [ ] 目标控制点有颜色光晕

---

## 五、实施顺序

```
Step 1 (后端 API) → Step 2 (简报屏 HTML+JS) → Step 3 (campaign-bar)
                                              → Step 4 (feed 战报)
                                              → Step 5 (CSS 精致化)
                                              → Step 6 (地图 Canvas)
                                              → Step 7 (全量测试)
```

每一步完成后独立验证，最后统一跑全部测试。
