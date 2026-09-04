/* 军旗演练前端：导演部导控台（主界面）+ 演练指挥台（实时）+ 导演部导调。
   定位：模拟各种大型战役与各种情况——把 AI 拆成一条条子智能体去扮演
   各参演方角色，由它们推动战役，成为一场军旗演练。 */
"use strict";

// ---------- 全局状态 ----------
const S = {
  state: null,
  view: "director",           // director / side（导演视角 / 参演方视角）
  camp: "",
  filter: "",
  epoch: -1,
  titles: {}, shorts: {}, unitOwner: {}, unitNames: {},
  nodes: {}, sideNames: {}, sideColors: {},
  factions: [], factionsKey: "",
  metricsTab: false,
  cam: { scale: 1, panX: 0, panY: 0, drag: null, view: null, anim: null },
  directOpen: false,
  // 作业区状态（路口式入口 + 独立工作台）
  studioView: "home",         // home / scenario / roster / director
  scenarios: [], roles: {}, scenSelected: null,
  roleEdits: {}, intentEdits: {}, collapsed: {},   // 兵力编成：职位 -> 是否折叠（true=折叠）
  script: [],                 // 导演部导调剧本（本地队列）
  llm: { available: false, model: "" },
  // 战斗特效系统
  effects: [],          // {type, x, y, start, duration, color, size, fromX, fromY}
  unitPrevPos: {},      // unit_id -> {x, y, tick} 用于移动平滑插值
  unitRenderPos: {},    // unit_id -> {px, py} 当前渲染的像素位置（平滑插值用）
  viewFlash: null,      // 视角切换扫描线过渡 {start}
  // 音效系统
  audio: { ctx: null, enabled: true, volume: 0.3, lastPlay: {} },
  selectedUnit: null,   // 选中的单位ID
  decisionBubbles: [],  // 战术Agent决策气泡 {unit_id, text, x, y, start, duration}
  briefing: null,       // 当前选中的战役简报
  _pendingLaunch: null, // 待启动的 launchExercise 参数
};

const SVGNS = "http://www.w3.org/2000/svg";
const $ = (id) => document.getElementById(id);
const els = {};

const KIND_META = {
  intent: ["意图", "#e2a336"], order: ["命令", "#e5484d"], ack: ["确认", "#7c8a98"],
  sitrep: ["报告", "#46c98d"], request: ["请示", "#c58af9"], plan: ["方案", "#e2a336"],
  intel: ["情报", "#4c8dff"], escalation: ["告警", "#ff7a45"],
  briefing_pulse: ["指挥摘要", "#dfb26a"],
};

const TERR_COLOR = { ".": "#121920", "f": "#152219", "h": "#1b2114", "~": "#0e2033", "B": "#3a3123", "C": "#242b33", "m": "#14262a", "r": "#26200f" };
const WEATHER_CN = { clear: "晴", overcast: "阴", rain: "雨", storm: "暴风雪", snowstorm: "暴风雪" };
const PALETTE = ["#e5484d", "#4c8dff", "#46c98d", "#e2a336", "#c58af9", "#ff7a45"];
const ARCTYPE_CN = {
  army_cmd: "军事主官", cos: "参谋·方案", intel: "参谋·情报", log: "参谋·后勤",
  div_cmd: "师级主官", reg_cmd: "团级主官", hq: "上级", front: "侦察哨",
};
const GLYPH = { infantry: "步", armor: "装", artillery: "炮", recon: "侦" };

const color = (side) => S.sideColors[side] || "#7c8a98";
const hexA = (hex, a) => {
  const n = parseInt(hex.slice(1), 16);
  return `rgba(${(n >> 16) & 255},${(n >> 8) & 255},${n & 255},${a})`;
};
const esc = (s) => String(s).replace(/[&<>"']/g, (c) =>
  ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]));
const shade = (hex, amt) => {
  const n = parseInt(hex.slice(1), 16);
  const c = (v) => Math.max(0, Math.min(255, v + amt));
  return `rgb(${c((n >> 16) & 255)},${c((n >> 8) & 255)},${c(n & 255)})`;
};
const shortName = (id) => { const s = S.titles[id] || id; return S.shorts[id] || s.replace(/^(红军|蓝军|美军|英加军|德军)/, ""); };

// ---------- 启动 ----------
function boot() {
  ["tick", "scenario", "deck-scenario", "run-pulse", "mode-badge", "org-tree",
   "intent-text", "intent-target", "btn-intent", "map", "feed", "feed-filter",
   "btn-start", "btn-pause", "btn-step", "btn-reset", "speed",
   "btn-settings", "settings-mask", "btn-close-settings",
   "btn-apply-friction", "btn-save-settings", "set-status",
   "engine-mask", "btn-close-engine", "btn-save-engine", "engine-status",
   "btn-llm-test", "conn-dot", "conn-state", "conn-meta", "conn-result",
   "engine-policy", "eng-llm-url", "eng-llm-model", "eng-llm-key",
   "eng-llm-retry", "eng-llm-timeout", "eng-use-tools",
   "zoom-in", "zoom-out", "zoom-reset", "zoom-label", "metrics",
   "tabs", "view-switch", "legend-sides", "map-hint",
   // 作业区（路口 + 独立工作台）
   "studio", "deck",
   "h-llm-badge", "h-go-settings",
   "h-scenario", "h-policy", "h-seed", "h-llm-line", "h-home-note",
   "btn-home-launch", "btn-home-scenario", "btn-home-battle", "btn-home-roster", "btn-home-director",
   "btn-home-settings",
   // 战役定制中心
   "btn-battle", "battle-mask", "btn-close-battle",
   "bt-presets", "bt-preset-count", "bt-weather", "bt-weather-desc", "bt-env",
   "bt-global", "bt-sides", "bt-status",
   "btn-battle-clear", "btn-battle-apply-launch",
   "bt-reset-env", "bt-reset-global", "bt-reset-sides",
   "st-scenarios", "sc-count", "st-ai", "btn-ai-import", "st-ai-status",
   "ai-import-toggle", "ai-import-chev", "ai-import-body",
   "st-tabs", "st-roster", "st-roster-hint", "btn-reset-roster",
   "btn-collapse-roster", "btn-expand-roster",
   "st-intents", "script-overview-count", "script-overview",
   "script-overview-toggle", "script-overview-chev", "script-overview-body",
   "btn-studio",
   // 导演部
   "btn-director", "director-mask", "director-close", "director-send",
   "dir-side", "dir-recipient", "dir-kind", "dir-subject", "dir-body", "dir-status",
   "dir-mode", "dir-tick-wrap", "dir-after", "dir-cur-tick",
   "script-list", "script-count", "dir-save-script",
   // 智能体调试中心
   "debug-search", "debug-side", "debug-count", "agent-list-items",
   "dbg-empty", "dbg-detail", "dbg-title", "dbg-meta", "dbg-live",
   "dbg-tabs", "dbg-content", "debug-export", "report-export",
   // v7 增强：一线分队战术面板 + 昼夜/天气指示
   "tactical", "deck-period", "deck-weather",
  ].forEach((k) => (els[k] = $(k)));
  document.querySelectorAll(".vs").forEach((b) => b.addEventListener("click", () => {
    document.querySelectorAll(".vs").forEach((x) => x.classList.remove("active"));
    b.classList.add("active");
    S.view = b.dataset.view;
    scheduleDraw();
  }));
  els["feed-filter"].addEventListener("change", (e) => { S.filter = e.target.value; applyFeedFilter(); });
  document.querySelectorAll(".rtab").forEach((t) => t.addEventListener("click", () => {
    document.querySelectorAll(".rtab").forEach((x) => x.classList.remove("active"));
    t.classList.add("active");
    const tab = t.dataset.rtab;
    S.metricsTab = tab === "metrics";
    els.feed.classList.toggle("hidden", tab !== "feed");
    els.tactical.classList.toggle("hidden", tab !== "tactical");
    els.metrics.classList.toggle("hidden", tab !== "metrics");
    if (tab === "metrics") fetchMetrics();
    if (tab === "tactical") renderTacticalPanel();
  }));
  setInterval(() => { if (S.metricsTab) fetchMetrics(); }, 3000);

  els["btn-start"].onclick = () => control({ action: "start" });
  els["btn-pause"].onclick = () => control({ action: "pause" });
  els["btn-step"].onclick = () => control({ action: "step" });
  els["btn-reset"].onclick = () => control({ action: "reset" }, true);
  // 音效开关
  const soundBtn = document.getElementById("sound-toggle");
  if (soundBtn) {
    soundBtn.addEventListener("click", () => {
      S.audio.enabled = !S.audio.enabled;
      soundBtn.textContent = S.audio.enabled ? "🔊" : "🔇";
      soundBtn.style.opacity = S.audio.enabled ? "1" : "0.4";
      if (S.audio.enabled) { initAudio(); playSound("message"); }
    });
  }
  els["speed"].onchange = (e) => control({ action: "speed", speed: parseFloat(e.target.value) });
  els["btn-intent"].onclick = sendIntent;
  els["intent-text"].addEventListener("keydown", (e) => {
    if (e.key === "Enter" && (e.ctrlKey || e.metaKey)) sendIntent();
  });

  new ResizeObserver(scheduleDraw).observe(els["map"].parentElement);
  wireCamera();
  buildTuningUI();
  wireStudio();
  wireDirector();
  wireSettings();
  wireBattle();
  connectSSE();
  fetchState();
  setInterval(fetchState, 1200);

  // 启动即进入作业桌（导演部导控台主界面）
  initStudio();
  // 按钮点击涟漪效果
  document.addEventListener("click", (e) => {
    const btn = e.target.closest(".btn");
    if (btn) {
      const r = btn.getBoundingClientRect();
      btn.style.setProperty("--ripple-x", (e.clientX - r.left) + "px");
      btn.style.setProperty("--ripple-y", (e.clientY - r.top) + "px");
    }
  });

  // 键盘快捷键：按1-9选中对应单位，Esc取消选中
  document.addEventListener("keydown", (e) => {
    if (e.key >= "1" && e.key <= "9") {
      const idx = parseInt(e.key) - 1;
      const st = S.state;
      if (!st) return;
      let units = [];
      if (S.view === "director") {
        units = S.factions.flatMap((f) => (st.camps[f] || {}).units || []);
      } else {
        units = (st.camps[S.view] || {}).units || [];
      }
      if (units[idx]) {
        S.selectedUnit = units[idx].id;
        renderUnitDetail(units[idx]);
        scheduleDraw();
      }
    }
    if (e.key === "Escape") {
      S.selectedUnit = null;
      document.getElementById("unit-detail")?.classList.add("hidden");
      scheduleDraw();
    }
  });
}

// ============================================================
// 一、作业区（主界面 = 路口式入口 + 独立工作台）
//    参考 Dify / Coze / AutoGen Studio：主界面只做入口与导航，
//    想定库 / 兵力编成 / 导演部设定 各自独立成视图，
//    引擎与连接类技术参数收进「设置」弹窗。
// ============================================================

function fitTextarea(ta) {
  if (!ta) return;
  ta.style.height = "auto";
  ta.style.height = Math.max(ta.scrollHeight, 44) + "px";
}

// 折叠式区块：标题按钮 + 箭头 + 内容体（用于想定库 AI 生成区、剧本概览等）
function toggleFold(toggleBtn, chev, body) {
  const collapsed = body.classList.toggle("hidden");
  chev.textContent = collapsed ? "▸" : "▾";
  toggleBtn.setAttribute("aria-expanded", String(!collapsed));
}

function wireStudio() {
  els["btn-studio"].onclick = () => { control({ action: "pause" }); enterStudio(); };
  els["btn-ai-import"].onclick = aiImport;
  els["btn-reset-roster"].onclick = resetRoster;
  els["btn-collapse-roster"].onclick = collapseAllRoster;
  els["btn-expand-roster"].onclick = expandAllRoster;

  // 左侧导航：视图切换
  document.querySelectorAll(".nav-item").forEach((item) =>
    item.addEventListener("click", () => switchStudioView(item.dataset.view)));

  // 首页快捷入口（只做跳转，不承载配置）
  els["btn-home-scenario"].onclick = () => switchStudioView("scenario");
  els["btn-home-roster"].onclick = () => switchStudioView("roster");
  els["btn-home-director"].onclick = () => switchStudioView("director");
  els["btn-home-launch"].onclick = launchExercise;

  // 首页流程条：1-3 步跳转对应工作台，第 4 步直接启动
  document.querySelectorAll(".hf").forEach((b) =>
    b.addEventListener("click", () => {
      const go = b.dataset.go;
      if (go === "launch") launchExercise();
      else switchStudioView(go);
    }));

  // 折叠式区块（想定库 AI 生成区 / 导演部剧本概览）
  els["ai-import-toggle"].onclick = () => toggleFold(
    els["ai-import-toggle"], els["ai-import-chev"], els["ai-import-body"]);
  els["script-overview-toggle"].onclick = () => toggleFold(
    els["script-overview-toggle"], els["script-overview-chev"], els["script-overview-body"]);

  // 自动增高文本框：直接输入 + 随内容长高（框不挤、不重叠）
  document.querySelectorAll("textarea.grow").forEach(fitTextarea);
  document.addEventListener("input", (e) => {
    if (e.target && e.target.matches && e.target.matches("textarea.grow")) fitTextarea(e.target);
  });

  // 智能体调试中心：搜索/筛选/选项卡
  els["debug-search"].addEventListener("input", debounce(loadDebugData, 300));
  els["debug-side"].addEventListener("change", loadDebugData);
  els["debug-export"].addEventListener("click", exportDebugJson);
  els["report-export"].addEventListener("click", exportReport);
  els["dbg-tabs"].addEventListener("click", (e) => {
    const tab = e.target.closest(".dbg-tab");
    if (!tab) return;
    document.querySelectorAll(".dbg-tab").forEach((t) => t.classList.remove("active"));
    tab.classList.add("active");
    renderDebugTab(S.dbgAgent, tab.dataset.tab);
  });
}

async function exportDebugJson() {
  try {
    const data = await (await fetch("/api/debug/export")).json();
    const blob = new Blob([JSON.stringify(data, null, 2)],
                          { type: "application/json;charset=utf-8" });
    const a = document.createElement("a");
    const ts = new Date().toISOString().replace(/[:.]/g, "-").slice(0, 19);
    a.href = URL.createObjectURL(blob);
    a.download = `复盘_${data.meta.scenario || "沙盘"}_T${data.meta.ticks}_${ts}.json`;
    document.body.appendChild(a);
    a.click();
    setTimeout(() => { URL.revokeObjectURL(a.href); a.remove(); }, 300);
  } catch (e) {
    console.error("导出失败:", e);
  }
}

function switchStudioView(name) {
  S.studioView = name;
  document.querySelectorAll(".nav-item").forEach((b) =>
    b.classList.toggle("active", b.dataset.view === name));
  document.querySelectorAll(".view").forEach((v) =>
    v.classList.toggle("active", v.id === "view-" + name));
  if (name === "scenario") populateScenarios();
  else if (name === "roster") populateRoles();
  else if (name === "director") { populateIntents(); loadScriptOverview(); }
  else if (name === "home") updateHomeStatus();
  else if (name === "debug") initDebugView();
  if (els.studio) els.studio.scrollTop = 0;
}

function enterStudio() {
  els.deck.classList.add("hidden");
  els.studio.classList.remove("hidden");
  initStudio(true);
}

async function initStudio(refresh = false) {
  try {
    await populateScenarios();
    await populateRoles();
    await populateIntents();
    await loadScriptOverview();
    updateHomeStatus();
  } catch (e) { /* 服务未就绪时静默 */ }
}

async function populateScenarios() {
  let list = [];
  try { list = await (await fetch("/api/scenarios")).json(); } catch (e) { return; }
  S.scenarios = list;
  if (S.scenSelected && !list.some((s) => s.id === S.scenSelected)) S.scenSelected = null;
  els["sc-count"].textContent = `共 ${list.length} 个预设想定`;
  // 给各参演方分配稳定色（跨想定一致）
  let idx = 0;
  const seen = {};
  for (const s of list) for (const x of s.sides)
    if (!seen[x.id]) { seen[x.id] = PALETTE[idx++ % PALETTE.length]; }
  Object.assign(S.sideColors, seen);
  els["st-scenarios"].innerHTML = list.map((s) => `
    <button class="sc-card${S.scenSelected === s.id ? " active" : ""}" data-id="${s.id}">
      <div class="sc-top"><span class="sc-tag">想定</span><span class="sc-cname">${esc(s.codename || s.name)}</span></div>
      <div class="sc-meta">
        <span>${esc(s.era || "")}</span><span>${s.sides.length} 方</span>
        <span>${esc((s.scale || "").split("·")[0] || "")}</span>
      </div>
      <div class="sc-desc">${esc(s.desc || "")}</div>
      <div class="sc-foot">
        ${s.sides.map((x) => `<span class="sc-side" style="color:${color(x.id)}">● ${esc(x.name)}</span>`).join("")}
        <span class="sc-enter">选用 →</span>
      </div>
    </button>`).join("");
  els["st-scenarios"].querySelectorAll(".sc-card").forEach((c) =>
    c.addEventListener("click", () => selectScenario(c.dataset.id)));
}

async function selectScenario(id) {
  S.scenSelected = id;
  els["st-scenarios"].querySelectorAll(".sc-card").forEach((c) =>
    c.classList.toggle("active", c.dataset.id === id));
  try {
    await fetch("/api/settings", {
      method: "POST", headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ scenario: id }),
    });
  } catch (e) { /* ignore */ }
  await populateRoles();
  updateHomeStatus();
}

async function populateRoles() {
  let r;
  try { r = await (await fetch("/api/roles")).json(); } catch (e) { return; }
  S.roles = r.sides || {};
  renderStudioTabs();
}

function renderStudioTabs() {
  const sides = Object.keys(S.roles);
  if (!sides.length) { els["st-tabs"].innerHTML = ""; els["st-roster"].innerHTML = ""; return; }
  const key = sides.join("|");
  if (key !== S.factionsKey) {
    S.sideColors = {};
    sides.forEach((f, i) => (S.sideColors[f] = PALETTE[i % PALETTE.length]));
    S.factionsKey = key;
  }
  if (!S.roles[S.camp]) S.camp = sides[0];
  els["st-tabs"].innerHTML = sides.map((s) => `
    <button class="st-tab${s === S.camp ? " active" : ""}" data-side="${s}"
      style="--c:${color(s)}">${esc((S.roles[s].name || s))}</button>`).join("");
  els["st-tabs"].querySelectorAll(".st-tab").forEach((t) => t.addEventListener("click", () => {
    els["st-tabs"].querySelectorAll(".st-tab").forEach((x) => x.classList.remove("active"));
    t.classList.add("active");
    S.camp = t.dataset.side;
    renderRoster();
  }));
  renderRoster();
}

// 指挥链上的子智能体角色卡（数据驱动：任意编制/任意多方都成立）
// 折叠策略：根节点默认展开，子节点默认折叠；点职位卡头部箭头切换；全部展开/折叠可一键控制。
function renderRoster() {
  const side = S.camp;
  const posList = (S.roles[side] || {}).positions || [];
  const agents = posList.filter((p) => !p.virtual);
  if (!posList.length) {
    els["st-roster"].innerHTML = `<div class="st-hint">该参演方暂无职位。</div>`;
    els["st-roster-hint"].innerHTML = "";
    return;
  }
  els["st-roster-hint"].innerHTML =
    `<div class="st-hint">该方共 <b>${agents.length}</b> 条 AI 子智能体。点职位卡头部可展开/折叠其性格与行为参数；改写文字即覆盖其历史性格，拖动滑杆即调行为参数——越激进（如告警阈值低）越敢硬打，改动在启动推演时提交生效。</div>`;

  const childrenOf = (id) => posList.filter((p) => String(p.parent || "") === id);
  const roots = posList.filter((p) => !p.parent);

  const gval = (merged, k, def) => (merged[k] != null && merged[k] !== "" ? merged[k] : def);
  const colState = (p) => (S.collapsed[p.id] != null ? S.collapsed[p.id] : Boolean(p.parent));

  function cardHTML(p) {
    const merged = Object.assign({}, p.config || {}, S.roleEdits[p.id] || {});
    const style = merged.style || "";
    const thr = gval(merged, "withdraw_threshold", 40);
    const rep = gval(merged, "report_interval", 8);
    const cf = gval(merged, "contact_fwd_interval", 4);
    const kids = childrenOf(p.id);
    const col = colState(p);
    const inner = p.virtual
      ? `<div class="rc-static">联络/上级席位（只收不发）</div>`
      : `<div class="rc-fold">
          <div class="rc-field">
            <div class="rc-label">指挥风格 / 性格（AI 子智能体角色卡）</div>
            <textarea rows="2" class="rc-style grow" data-pos="${p.id}" placeholder="例：蒙哥马利式谨慎缜密；或：狂热激进，崇尚立即反击…">${esc(style)}</textarea></div>
          <div class="rc-behavior">
            <label title="兵力低于此值触发告警并转入据守"><span class="b-label">告警兵力阈值</span>
              <input type="range" class="rc-slider" data-key="withdraw_threshold" min="5" max="90" step="5" value="${thr}">
              <b class="rc-th-v">${thr}</b></label>
            <label title="无新电文时周期性上报战况的间隔（拍）"><span class="b-label">战况报告间隔</span>
              <input type="range" class="rc-slider" data-key="report_interval" min="2" max="24" step="1" value="${rep}">
              <b class="rc-th-v">${rep}拍</b></label>
            <label title="接触敌军后上报接触报告的间隔（拍）"><span class="b-label">接触报告间隔</span>
              <input type="range" class="rc-slider" data-key="contact_fwd_interval" min="1" max="12" step="1" value="${cf}">
              <b class="rc-th-v">${cf}拍</b></label>
          </div>
        </div>`;
    return `<div class="role-card${p.virtual ? " virt" : ""}${col ? " collapsed" : ""}" data-pos="${p.id}" data-parent="${p.parent || ""}" style="--c:${color(side)}">
      <div class="rc-head">
        <button class="rc-toggle${col ? " off" : ""}" data-pos="${p.id}" title="${col ? "展开详细配置" : "折叠详细配置"}" aria-label="${col ? "展开" : "折叠"}">${col ? "▸" : "▾"}</button>
        <span class="rc-chip" style="background:${hexA(color(side), .15)};color:${shade(color(side), 60)}">${esc((S.roles[side].name || side).slice(0, 2))}</span>
        <span class="rc-title">${esc(p.title)}</span>
        <span class="rc-archetype">${esc(ARCTYPE_CN[p.archetype] || p.archetype || "")}</span>
        ${kids.length ? `<span class="rc-kids-count">${kids.length} 下级</span>` : ""}
        <span class="rc-units">直辖 ${p.units.length} 部</span>
      </div>
      ${col ? "" : inner}
      ${!col && kids.length ? `<div class="rc-kids">${kids.map(cardHTML).join("")}</div>` : ""}
    </div>`;
  }
  els["st-roster"].innerHTML = roots.map(cardHTML).join("");
  els["st-roster"].querySelectorAll(".rc-toggle").forEach((b) => {
    b.addEventListener("click", () => {
      const card = b.closest(".role-card");
      const pos = card.dataset.pos;
      const parent = card.dataset.parent || "";
      const def = Boolean(parent);
      const cur = S.collapsed[pos] != null ? S.collapsed[pos] : def;
      S.collapsed[pos] = !cur;
      renderRoster();
    });
  });
  els["st-roster"].querySelectorAll(".rc-style").forEach((ta) => {
    const pos = ta.dataset.pos;
    fitTextarea(ta);
    ta.addEventListener("input", () => { fitTextarea(ta); applyRosterEdit(pos); });
  });
  els["st-roster"].querySelectorAll(".rc-slider").forEach((r) => {
    const pos = r.closest(".role-card").dataset.pos;
    const v = r.closest("label").querySelector(".rc-th-v");
    r.addEventListener("input", () => {
      v.textContent = r.value + (r.dataset.key === "withdraw_threshold" ? "" : "拍");
      applyRosterEdit(pos);
    });
  });
}

function collapseAllRoster() {
  const posList = (S.roles[S.camp] || {}).positions || [];
  posList.forEach((p) => (S.collapsed[p.id] = true));
  renderRoster();
}

function expandAllRoster() {
  const posList = (S.roles[S.camp] || {}).positions || [];
  posList.forEach((p) => (S.collapsed[p.id] = false));
  renderRoster();
}

function applyRosterEdit(pos) {
  const card = els["st-roster"].querySelector(`.role-card[data-pos="${pos}"]`);
  if (!card) return;
  const cfg = {};
  const st = (card.querySelector(".rc-style") || {}).value || "";
  if (st.trim()) cfg.style = st.trim();
  card.querySelectorAll(".rc-slider").forEach((r) => { cfg[r.dataset.key] = parseFloat(r.value); });
  if (!Object.keys(cfg).length) delete S.roleEdits[pos];
  else S.roleEdits[pos] = cfg;
}

async function resetRoster() {
  S.roleEdits = {};
  try {
    await fetch("/api/roles", {
      method: "POST", headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ reset: true }),
    });
  } catch (e) { /* ignore */ }
  await populateRoles();
}

async function populateIntents() {
  try {
    const r = await (await fetch("/api/intents")).json();
    const names = r.names || {};
    const defaults = r.defaults || {};
    const saved = r.intents || {};
    const factions = r.factions || Object.keys(defaults);
    els["st-intents"].innerHTML = factions.map((f) => `
      <div class="intent-card" data-side="${f}" style="--c:${color(f)}">
        <div class="ic-head"><span class="rc-chip" style="background:${hexA(color(f), .15)};color:${shade(color(f), 60)}">${esc((names[f] || f).slice(0, 2))}</span>
          <b>${esc(names[f] || f)}</b> 开局作战意图</div>
        <textarea rows="2" class="ic-text grow" placeholder="给该参演方主官的第一份上级任务…">${esc(saved[f] || defaults[f] || "")}</textarea>
      </div>`).join("");
    els["st-intents"].querySelectorAll(".ic-text").forEach((ta) => {
      const f = ta.closest(".intent-card").dataset.side;
      fitTextarea(ta);
      S.intentEdits[f] = ta.value.trim();
      ta.addEventListener("input", () => { fitTextarea(ta); S.intentEdits[f] = ta.value.trim(); });
    });
  } catch (e) { /* ignore */ }
}

// 首页状态卡：反映当前引擎配置（入口只读，改动去对应工作台/设置）
async function updateHomeStatus() {
  try {
    const s = await (await fetch("/api/settings")).json();
    S.llm = s.llm || S.llm;
    els["h-llm-badge"].textContent = S.llm.available
      ? `LLM · ${S.llm.model}` : "规则模式 · 未配置 Key";
    els["h-llm-badge"].classList.toggle("llm", S.llm.available);
    const sc = (s.scenarios || []).find((x) => x.id === (S.scenSelected || s.scenario));
    els["h-scenario"].textContent = sc ? sc.name : (S.scenSelected || s.scenario || "未选定想定");
    els["h-policy"].textContent = {
      auto: "自动", rule: "规则策略", llm: "LLM 智能决策",
    }[s.policy_mode] || s.policy_mode;
    els["h-seed"].textContent = s.seed ?? "7";
    const line = els["h-llm-line"];
    line.classList.remove("ok", "warn");
    if (S.llm.available) {
      line.textContent = `已连接决策引擎 ${S.llm.model}：全部 AI 子智能体由 LLM 驱动。`;
      line.classList.add("ok");
    } else {
      line.textContent = "规则模式 · 离线确定性 · 可在「引擎与连接」中配置 LLM Key 升级决策。";
      line.classList.add("warn");
    }
    els["h-home-note"].textContent = S.scenSelected
      ? `已选用想定「${sc ? sc.name : S.scenSelected}」，随时可以开始推演。`
      : "尚未选定想定：先到「想定库」选用，或直接粘贴资料让 AI 生成。";
  } catch (e) { /* ignore */ }
}

// 从路口启动：使用当前已保存的引擎配置，进入简报屏后再启动
async function launchExercise() {
  try {
    const s = await (await fetch("/api/settings")).json();
    const scenario = S.scenSelected || s.scenario;
    if (!scenario) {
      els["h-home-note"].textContent = "请先到「想定库」选定一个想定，或让 AI 生成。";
      return;
    }
    els["btn-home-launch"].disabled = true;
    // Fetch briefing for the selected scenario
    const presets = await (await fetch("/api/battle/presets")).json();
    const preset = (presets.presets || []).find((p) => p.id === scenario);
    S.briefing = preset || null;
    showBriefingScreen(preset);
  } catch (e) {
    els["h-home-note"].textContent = "启动失败，请重试：" + String(e);
  } finally {
    els["btn-home-launch"].disabled = false;
  }
}

// 显示战役简报屏
function showBriefingScreen(preset) {
  if (!preset) {
    // 无简报，直接启动
    doLaunchExercise();
    return;
  }
  els["briefing-title"].textContent = preset.name || "";
  els["briefing-codename"].textContent = preset.codename || "";
  // Parse briefing text into sections
  const b = preset.briefing || "";
  const sections = b.split(/【(.+?)】/).filter(Boolean);
  const sectionMap = {};
  for (let i = 0; i < sections.length - 1; i += 2) {
    sectionMap[sections[i]] = sections[i + 1];
  }
  els["briefing-narrative"].textContent = sectionMap["战役背景"] || sectionMap["背景"] || (preset.desc || "");
  els["briefing-force-comparison"].textContent = sectionMap["兵力对比"] || "—";
  els["briefing-terrain"].textContent = sectionMap["地形特点"] || sectionMap["地形"] || "—";
  els["briefing-weather"].textContent = sectionMap["天气趋势"] || sectionMap["天气"] || "—";
  els["briefing-screen"].classList.remove("hidden");
}

function hideBriefingScreen() {
  els["briefing-screen"].classList.add("hidden");
}

// 实际启动逻辑（从简报屏确认后调用）
async function doLaunchExercise() {
  try {
    const s = await (await fetch("/api/settings")).json();
    const scenario = S.scenSelected || s.scenario;
    els["btn-home-launch"].disabled = true;
    const updates = Object.entries(S.roleEdits)
      .filter(([, c]) => Object.keys(c).length)
      .map(([pos, config]) => ({ pos, config }));
    if (updates.length) await fetch("/api/roles", {
      method: "POST", headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ updates }),
    });
    const intents = {};
    for (const [f, v] of Object.entries(S.intentEdits)) if (v) intents[f] = v;
    if (Object.keys(intents).length) await fetch("/api/intents", {
      method: "POST", headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ intents }),
    });
    await fetch("/api/settings", {
      method: "POST", headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ scenario }),
    });
    await control({ action: "start" });
    hideBriefingScreen();
    els.studio.classList.add("hidden");
    els.deck.classList.remove("hidden");
    els["campaign-bar"].classList.remove("hidden");
    els.feed.innerHTML = "";
    fetchState();
  } catch (e) {
    hideBriefingScreen();
  } finally {
    els["btn-home-launch"].disabled = false;
  }
}

async function aiImport() {
  const text = els["st-ai"].value.trim();
  if (!text) return;
  els["st-ai-status"].textContent = "AI 正在识别资料并生成想定…";
  try {
    const r = await (await fetch("/api/scenarios/ai_import", {
      method: "POST", headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ side: "import", text }),
    })).json();
    if (r.ok) {
      els["st-ai-status"].textContent = `已生成「${r.name}」，点上面卡片选用 ✓`;
      els["st-ai"].value = "";
      fitTextarea(els["st-ai"]);
      await populateScenarios();
      selectScenario(r.id);
    } else {
      els["st-ai-status"].textContent = r.error || "识别失败";
    }
  } catch (e) { els["st-ai-status"].textContent = "请求失败，请重试"; }
}

// 导演部设定页：导调剧本概览（完整编排在指挥台导调面板）
async function loadScriptOverview() {
  try {
    const r = await (await fetch("/api/director/script")).json();
    S.script = r.script || [];
  } catch (e) { /* ignore */ }
  renderScriptOverview();
}

function renderScriptOverview() {
  els["script-overview-count"].textContent = S.script.length ? `共 ${S.script.length} 条` : "(空)";
  if (!S.script.length) {
    els["script-overview"].innerHTML =
      `<div class="sc-item empty">暂无导调剧本 —— 进入指挥台「导演部导调」面板编排，到指定拍自动触发。</div>`;
    return;
  }
  els["script-overview"].innerHTML = S.script.slice(0, 3).map((s) => {
    const who = (S.roles[s.side] || {}).name || s.side;
    return `<div class="sc-item">
      <span class="sc-i-t">T${String(s.tick).padStart(3, "0")}</span>
      <span class="sc-i-meta">${esc(who)} → ${esc(titleOf(s.recipient))}</span>
      <span class="sc-i-sub">${esc(s.subject || s.body.slice(0, 20))}</span>
    </div>`;
  }).join("");
  if (S.script.length > 3) {
    els["script-overview"].innerHTML +=
      `<div class="sc-more">… 还有 ${S.script.length - 3} 条，详见指挥台「导演部导调」</div>`;
  }
}

// ============================================================
// 二、导演部导调（单条注入 + 导调剧本）
// ============================================================
function wireDirector() {
  els["btn-director"].onclick = openDirector;
  els["director-close"].onclick = closeDirector;
  els["director-mask"].addEventListener("click", (e) => {
    if (e.target === els["director-mask"]) closeDirector();
  });
  els["dir-side"].addEventListener("change", () => renderDirRecipients());
  els["dir-mode"].addEventListener("change", () => {
    els["dir-tick-wrap"].classList.toggle("hidden", els["dir-mode"].value !== "script");
  });
  els["dir-save-script"].onclick = saveScript;
  els["director-send"].onclick = directorSend;
}

async function openDirector() {
  els["director-mask"].classList.remove("hidden");
  els["dir-status"].textContent = "";
  els["dir-subject"].value = "";
  els["dir-body"].value = "";
  els["dir-mode"].value = S.directOpen ? "script" : "now";
  els["dir-tick-wrap"].classList.toggle("hidden", els["dir-mode"].value !== "script");
  try {
    let roles = S.roles;
    if (!Object.keys(roles).length) roles = (await (await fetch("/api/roles")).json()).sides;
    const sides = Object.keys(roles);
    els["dir-side"].innerHTML = sides.map((s) =>
      `<option value="${s}">${esc(roles[s].name || s)}</option>`).join("");
    if (sides[0]) renderDirRecipients();
    await loadScript();
  } catch (e) { els["dir-status"].textContent = "读取角色失败"; }
}

function renderDirRecipients() {
  const side = els["dir-side"].value;
  const pos = ((S.roles[side] || {}).positions || []).filter((p) => !p.virtual);
  els["dir-recipient"].innerHTML = pos.map((p) =>
    `<option value="${p.id}">${esc(p.title)}</option>`).join("");
}

function closeDirector() { els["director-mask"].classList.add("hidden"); }

async function directorSend() {
  const payload = {
    side: els["dir-side"].value,
    recipient: els["dir-recipient"].value,
    kind: els["dir-kind"].value,
    subject: els["dir-subject"].value.trim(),
    body: els["dir-body"].value.trim(),
  };
  if (!payload.body) { els["dir-status"].textContent = "请填写情况内容"; return; }
  if (els["dir-mode"].value === "script") {
    const tick = (S.state ? S.state.tick : 0) + Math.max(1, parseInt(els["dir-after"].value || "3", 10));
    S.script.push({ ...payload, tick });
    els["dir-body"].value = ""; els["dir-subject"].value = "";
    renderScriptList();
    els["dir-status"].textContent = `已入剧（T${tick} 触发）。点「保存剧本」生效 ✓`;
    return;
  }
  els["director-send"].disabled = true;
  try {
    const r = await (await fetch("/api/director", {
      method: "POST", headers: { "Content-Type": "application/json" },
      body: JSON.stringify(payload),
    })).json();
    els["dir-status"].textContent = r.ok ? "已注入该子智能体信箱 ✓" : (r.error || "注入失败");
    if (r.ok) { els["dir-body"].value = ""; els["dir-subject"].value = ""; }
  } catch (e) { els["dir-status"].textContent = "请求失败"; }
  finally { els["director-send"].disabled = false; }
}

async function loadScript() {
  try {
    const r = await (await fetch("/api/director/script")).json();
    S.script = r.script || [];
  } catch (e) { /* ignore */ }
  renderScriptList();
}

function renderScriptList() {
  els["script-count"].textContent = S.script.length ? `共 ${S.script.length} 条` : "(空)";
  if (!S.script.length) {
    els["script-list"].innerHTML = "";
    return;
  }
  els["script-list"].innerHTML = S.script.map((s, i) => {
    const who = (S.roles[s.side] || {}).name || s.side;
    const role = titleOf(s.recipient);
    return `<div class="sc-item">
      <span class="sc-i-t">T${String(s.tick).padStart(3, "0")}</span>
      <span class="sc-i-meta">${esc(who)} → ${esc(role)} · ${esc(KIND_META[s.kind] ? KIND_META[s.kind][0] : s.kind)}</span>
      <span class="sc-i-sub">${esc(s.subject || s.body.slice(0, 18))}</span>
      <button class="btn icon" data-i="${i}" title="移除">✕</button>
    </div>`;
  }).join("");
  els["script-list"].querySelectorAll("button").forEach((b) => b.addEventListener("click", () => {
    S.script.splice(parseInt(b.dataset.i, 10), 1);
    renderScriptList();
  }));
}

async function saveScript() {
  els["dir-status"].textContent = "保存中…";
  try {
    const r = await (await fetch("/api/director/script", {
      method: "POST", headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ script: S.script }),
    })).json();
    els["dir-status"].textContent = r.ok ? `剧本已保存，${r.pending} 条待触发 ✓` : "保存失败";
  } catch (e) { els["dir-status"].textContent = "保存失败"; }
}

// ============================================================
// 三、态势图相机
// ============================================================
function wireCamera() {
  const cv = els["map"];
  S.mapCanvas = cv;
  const tooltip = document.getElementById("map-tooltip");

  cv.addEventListener("wheel", (e) => {
    e.preventDefault();
    const r = cv.getBoundingClientRect();
    zoomAt(e.clientX - r.left, e.clientY - r.top, e.deltaY < 0 ? 1.15 : 1 / 1.15);
  }, { passive: false });

  cv.addEventListener("mousedown", (e) => {
    S.cam.dragStart = { x: e.clientX, y: e.clientY };
    if (tooltip) tooltip.classList.add("hidden");
  });

  // 双击重置视角
  cv.addEventListener("dblclick", (e) => {
    e.preventDefault();
    S.cam.anim = {
      startScale: S.cam.scale, targetScale: 1,
      startPanX: S.cam.panX, startPanY: S.cam.panY,
      targetPanX: 0, targetPanY: 0,
      startTime: performance.now(), duration: 400,
    };
    startAnimLoop();
  });

  window.addEventListener("mousemove", (e) => {
    // 拖拽处理
    if (S.cam.dragStart && !S.cam.drag) {
      const dx = Math.abs(e.clientX - S.cam.dragStart.x);
      const dy = Math.abs(e.clientY - S.cam.dragStart.y);
      if (dx > 5 || dy > 5) {
        if (S.cam.scale > 1) {
          S.cam.drag = { x: e.clientX, y: e.clientY, px: S.cam.panX, py: S.cam.panY };
          cv.classList.add("dragging");
        }
      }
    }
    if (S.cam.drag) {
      // 边界限制：防止拖出地图
      const st = S.state;
      if (st && S.cam.view) {
        const v = S.cam.view;
        const cs = v.base * S.cam.scale;
        const mapW = cs * st.w, mapH = cs * st.h;
        const maxPanX = Math.max(0, mapW - v.cw);
        const maxPanY = Math.max(0, mapH - v.ch);
        S.cam.panX = Math.max(-maxPanX, Math.min(0, S.cam.drag.px + (e.clientX - S.cam.drag.x)));
        S.cam.panY = Math.max(-maxPanY, Math.min(0, S.cam.drag.py + (e.clientY - S.cam.drag.y)));
      } else {
        S.cam.panX = S.cam.drag.px + (e.clientX - S.cam.drag.x);
        S.cam.panY = S.cam.drag.py + (e.clientY - S.cam.drag.y);
      }
      scheduleDraw();
      return;
    }

    // hover检测：显示单位tooltip
    if (!S.cam.dragStart && tooltip && S.state && S.cam.view) {
      const r = cv.getBoundingClientRect();
      const mx = e.clientX - r.left, my = e.clientY - r.top;
      if (mx >= 0 && mx <= r.width && my >= 0 && my <= r.height) {
        const hovered = _findUnitAt(mx, my);
        if (hovered) {
          cv.style.cursor = "pointer";
          const sideColor = color(hovered.side);
          const kindMap = { infantry: "步兵", armor: "装甲", artillery: "炮兵", recon: "侦察" };
          const stateMap = { advancing: "推进", engaging: "接战", defending: "防御", withdrawing: "后撤", holding: "待命", resting: "休整", reorganizing: "重组", destroyed: "全损" };
          const str = hovered.strength ?? hovered.str ?? 0;
          const maxStr = hovered.max_strength ?? 100;
          const strPct = Math.round((str / maxStr) * 100);
          const strColor = strPct > 60 ? "#57d99b" : strPct > 30 ? "#e0b06a" : "#ff5f5f";
          tooltip.innerHTML = `
            <div class="tt-name" style="color:${sideColor}">${hovered.name || hovered.id}</div>
            <div class="tt-row"><span>${kindMap[hovered.kind] || hovered.kind}</span><span style="color:${strColor}">兵力 ${strPct}%</span></div>
            <div class="tt-row"><span>坐标 (${hovered.x},${hovered.y})</span><span>${stateMap[hovered.state] || hovered.state || ""}</span></div>
          `;
          tooltip.style.left = (e.clientX - r.left + 14) + "px";
          tooltip.style.top = (e.clientY - r.top + 14) + "px";
          tooltip.classList.remove("hidden");
        } else {
          cv.style.cursor = S.cam.scale > 1 ? "grab" : "zoom-in";
          tooltip.classList.add("hidden");
        }
      } else {
        tooltip.classList.add("hidden");
      }
    }
  });

  window.addEventListener("mouseup", () => {
    S.cam.drag = null; cv.classList.remove("dragging");
    S.cam.dragStart = null;
  });

  cv.addEventListener("mouseleave", () => {
    if (tooltip) tooltip.classList.add("hidden");
  });

  els["zoom-in"].onclick = () => { const r = cv.getBoundingClientRect(); zoomAt(r.width / 2, r.height / 2, 1.3); };
  els["zoom-out"].onclick = () => { const r = cv.getBoundingClientRect(); zoomAt(r.width / 2, r.height / 2, 1 / 1.3); };
  els["zoom-reset"].onclick = () => {
    S.cam.anim = {
      startScale: S.cam.scale, targetScale: 1,
      startPanX: S.cam.panX, startPanY: S.cam.panY,
      targetPanX: 0, targetPanY: 0,
      startTime: performance.now(), duration: 350,
    };
    startAnimLoop();
  };
}

// 查找指定坐标下的单位（用于hover检测）
function _findUnitAt(mx, my) {
  const st = S.state;
  if (!st || !S.cam.view) return null;
  const v = S.cam.view;
  let units = [];
  if (S.view === "director") {
    units = S.factions.flatMap((f) => (st.camps[f] || {}).units || []);
  } else {
    units = (st.camps[S.view] || {}).units || [];
  }
  let hit = null, hitDist = Infinity;
  for (const u of units) {
    const rp = S.unitRenderPos[u.id];
    const px = rp ? rp.px : (v.ox + u.x * v.cs);
    const py = rp ? rp.py : (v.oy + u.y * v.cs);
    const cx = px + v.cs / 2, cy = py + v.cs / 2;
    const dist = Math.sqrt((mx - cx) ** 2 + (my - cy) ** 2);
    if (dist < v.cs * 0.6 && dist < hitDist) {
      hit = u; hitDist = dist;
    }
  }
  return hit;
}

// 聚焦到指定单位（平滑动画）
function focusOnUnit(u) {
  if (!u || !S.cam.view) return;
  const v = S.cam.view;
  const targetScale = Math.max(1.5, Math.min(3, S.cam.scale));
  const cs = v.base * targetScale;
  const targetPanX = v.cw / 2 - (u.x * cs + cs / 2);
  const targetPanY = v.ch / 2 - (u.y * cs + cs / 2);
  S.cam.anim = {
    startScale: S.cam.scale, targetScale,
    startPanX: S.cam.panX, startPanY: S.cam.panY,
    targetPanX, targetPanY,
    startTime: performance.now(), duration: 500,
  };
  startAnimLoop();
}

function _trySelectUnit(clientX, clientY) {
  const st = S.state;
  if (!st) return;
  const cv = S.mapCanvas;
  if (!cv) return;
  const r = cv.getBoundingClientRect();
  const mx = clientX - r.left, my = clientY - r.top;
  const v = S.cam.view;
  if (!v) return;
  let units = [];
  if (S.view === "director") {
    units = S.factions.flatMap((f) => (st.camps[f] || {}).units || []);
  } else {
    const camp = st.camps[S.view] || {};
    units = (camp.units || []).slice();
    for (const i of (camp.intel || [])) {
      const owner = S.factions.find((f) => f !== S.view);
      units.push({ id: i.unit_id, side: owner, kind: i.kind, x: i.x, y: i.y, ghost: true });
    }
  }
  let hit = null, hitDist = Infinity;
  for (const u of units) {
    const rp = S.unitRenderPos[u.id];
    const px = rp ? rp.px : (v.ox + u.x * v.cs);
    const py = rp ? rp.py : (v.oy + u.y * v.cs);
    const cx = px + v.cs / 2, cy = py + v.cs / 2;
    const dist = Math.sqrt((mx - cx) ** 2 + (my - cy) ** 2);
    if (dist < v.cs * 0.6 && dist < hitDist) {
      hit = u; hitDist = dist;
    }
  }
  S.selectedUnit = hit ? hit.id : null;
  if (hit) {
    playSound("message");
    renderUnitDetail(hit);
    focusOnUnit(hit);
  }
  scheduleDraw();
}

function renderUnitDetail(u) {
  const panel = document.getElementById("unit-detail");
  if (!panel || !u) return;
  panel.classList.remove("hidden");
  const sideColor = color(u.side);
  document.getElementById("ud-name").textContent = u.name || u.id;
  document.getElementById("ud-name").style.color = sideColor;
  document.getElementById("ud-side").textContent = u.side === "red" ? "红军" : u.side === "blue" ? "蓝军" : u.side;
  document.getElementById("ud-side").style.color = sideColor;
  const kindMap = { infantry: "步兵", armor: "装甲", artillery: "炮兵", recon: "侦察" };
  document.getElementById("ud-kind").textContent = kindMap[u.kind] || u.kind || "--";
  document.getElementById("ud-pos").textContent = `(${u.x}, ${u.y})`;
  document.getElementById("ud-str").textContent = `${u.strength ?? u.str ?? "--"} / ${u.max_strength ?? 100}`;
  document.getElementById("ud-sup").textContent = `${u.supply ?? "--"}`;
  document.getElementById("ud-fat").textContent = `${((u.fatigue ?? 0) * 100).toFixed(0)}%`;
  const moraleMap = { steady: "稳定", shaken: "动摇", breaking: "崩溃", reorg: "重组" };
  const moraleVal = u.morale ?? 1;
  const moralePct = moraleVal > 1 ? moraleVal.toFixed(0) : (moraleVal * 100).toFixed(0);
  document.getElementById("ud-mor").textContent = `${moraleMap[u.morale_state] || u.morale_state || "--"} (${moralePct}%)`;
  const stateMap = { advancing: "推进", engaging: "接战", defending: "防御", withdrawing: "后撤", holding: "待命", resting: "休整", reorganizing: "重组", destroyed: "全损" };
  document.getElementById("ud-state").textContent = stateMap[u.state] || u.state || "--";
  // 查找战术Agent状态
  let tacState = "--";
  if (S.state && S.state.camps) {
    for (const f of S.factions) {
      const camp = S.state.camps[f] || {};
      const t = (camp.tactical || []).find((x) => x.unit_id === u.id);
      if (t) { tacState = stateMap[t.state] || t.state; break; }
    }
  }
  document.getElementById("ud-tac").textContent = tacState;
  // v0.9.7 新因素显示
  const ammoEl = document.getElementById("ud-ammo");
  if (ammoEl) {
    const ammo = u.ammo ?? 100;
    ammoEl.textContent = ammo + "%";
    ammoEl.style.color = ammo < 20 ? "#ff5f5f" : ammo < 50 ? "#e0b06a" : "inherit";
  }
  const fuelEl = document.getElementById("ud-fuel");
  if (fuelEl) {
    const fuel = u.fuel ?? 100;
    fuelEl.textContent = fuel + "%";
    fuelEl.style.color = fuel < 20 ? "#ff5f5f" : "inherit";
  }
  const expEl = document.getElementById("ud-exp");
  if (expEl) {
    const expMap = { green: "新兵", regular: "正规", veteran: "老兵", elite: "精锐" };
    expEl.textContent = `${expMap[u.exp_level] || u.exp_level || "--"} (${u.experience ?? 0})`;
    expEl.style.color = u.exp_level === "elite" ? "#ffd700" : u.exp_level === "veteran" ? "#57d99b" : "inherit";
  }
  const entEl = document.getElementById("ud-ent");
  if (entEl) {
    if (u.entrenched) {
      entEl.textContent = `Lv.${u.entrench_level || 1}`;
      entEl.style.color = "#7dd3fc";
    } else {
      entEl.textContent = "无";
    }
  }
  const formEl = document.getElementById("ud-form");
  if (formEl) {
    formEl.textContent = u.formation === "combat" ? "战斗队形" : "行军队形";
    formEl.style.color = u.formation === "march" ? "#e0b06a" : "inherit";
  }
  const cmdEl = document.getElementById("ud-cmd");
  if (cmdEl) {
    if (u.is_commander) {
      cmdEl.textContent = "指挥官";
      cmdEl.style.color = "#ffd700";
    } else if (u.in_command === false) {
      cmdEl.textContent = "超出范围";
      cmdEl.style.color = "#ff5f5f";
    } else {
      cmdEl.textContent = "正常";
    }
  }
  const slineEl = document.getElementById("ud-sline");
  if (slineEl) {
    if (u.supply_line_cut) {
      slineEl.textContent = "已切断";
      slineEl.style.color = "#ff5f5f";
    } else {
      slineEl.textContent = "畅通";
      slineEl.style.color = "#57d99b";
    }
  }
}

function easeOutBack(t) {
  const c1 = 1.70158, c3 = c1 + 1;
  return 1 + c3 * Math.pow(t - 1, 3) + c1 * Math.pow(t - 1, 2);
}

// 全局点击监听：点击地图canvas时选中单位
document.addEventListener("click", (e) => {
  const cv = document.getElementById("map");
  if (!cv) return;
  const r = cv.getBoundingClientRect();
  if (e.clientX < r.left || e.clientX > r.right || e.clientY < r.top || e.clientY > r.bottom) return;
  _trySelectUnit(e.clientX, e.clientY);
});

function zoomAt(mx, my, factor) {
  const st = S.state, v = S.cam.view;
  if (!st || !v) return;
  const wx = (mx - v.ox) / v.cs, wy = (my - v.oy) / v.cs;
  const targetScale = Math.max(1, Math.min(6, S.cam.scale * factor));
  const cw = v.cw, ch = v.ch;
  const cs2 = v.base * targetScale;
  const cW = cs2 * st.w, cH = cs2 * st.h;
  let ox = mx - wx * cs2, oy = my - wy * cs2;
  ox = (cW <= cw) ? (cw - cW) / 2 : Math.max(cw - cW, Math.min(0, ox));
  oy = (cH <= ch) ? (ch - cH) / 2 : Math.max(ch - cH, Math.min(0, oy));
  const targetPanX = ox - (cw - cW) / 2;
  const targetPanY = oy - (ch - cH) / 2;
  // 启动弹性缩放动画
  S.cam.anim = {
    startScale: S.cam.scale, targetScale,
    startPanX: S.cam.panX, startPanY: S.cam.panY,
    targetPanX, targetPanY,
    startTime: performance.now(), duration: 350,
  };
  startAnimLoop();
}

function _updateZoomAnim() {
  if (!S.cam.anim) return false;
  const a = S.cam.anim;
  const t = Math.min(1, (performance.now() - a.startTime) / a.duration);
  const e = easeOutBack(t);
  S.cam.scale = a.startScale + (a.targetScale - a.startScale) * e;
  S.cam.panX = a.startPanX + (a.targetPanX - a.startPanX) * e;
  S.cam.panY = a.startPanY + (a.targetPanY - a.startPanY) * e;
  if (t >= 1) {
    S.cam.scale = a.targetScale;
    S.cam.panX = a.targetPanX;
    S.cam.panY = a.targetPanY;
    S.cam.anim = null;
    return false;
  }
  return true;
}

// ---------- 设置面板 ----------
const TUNING_GROUPS = {
  // 智能体行为：子智能体的上报节奏、告警阈值、进攻倾向与通信摩擦（把"机动与节奏""组织摩擦"并入此处）
  "set-agent": [
    { k: "report_interval", label: "例行报告间隔(拍)", min: 2, max: 48, step: 1 },
    { k: "contact_fwd_interval", label: "接触报告间隔(拍)", min: 1, max: 24, step: 1 },
    { k: "withdraw_threshold", label: "告警兵力阈值%", min: 5, max: 90, step: 5 },
    { k: "aggression_scale", label: "进攻倾向", min: 0.2, max: 3, step: 0.1 },
    { k: "escalation_delay", label: "告警延迟(拍)", min: 0, max: 20, step: 1 },
    { k: "memory_size", label: "记忆容量(条)", min: 5, max: 200, step: 5 },
    { k: "latency_scale", label: "消息延迟倍率", min: 0.5, max: 4, step: 0.5 },
    { k: "loss_rate", label: "消息丢失率", min: 0, max: 0.4, step: 0.02, pct: true },
  ],
  "set-battle": [
    { k: "combat_scale", label: "战斗强度", min: 0.2, max: 3, step: 0.1 },
    { k: "arty_scale", label: "炮兵威力", min: 0.2, max: 3, step: 0.1 },
    { k: "entrench_bonus", label: "工事加成", min: 0, max: 1, step: 0.05 },
    { k: "terrain_def_scale", label: "地形加成", min: 0, max: 2, step: 0.1 },
  ],
  "set-morale": [
    { k: "morale_scale", label: "士气影响强度", min: 0, max: 2, step: 0.05 },
    { k: "low_strength_penalty", label: "残兵战力折扣", min: 0, max: 0.9, step: 0.05, pct: true },
    { k: "flank_bonus", label: "侧翼夹击加成", min: 0, max: 2, step: 0.1 },
    { k: "overrun_scale", label: "追击加成", min: 0, max: 1, step: 0.05 },
  ],
  "set-move": [
    { k: "move_scale", label: "部队移速倍率", min: 0.3, max: 4, step: 0.1 },
    { k: "road_bonus", label: "道路机动效率", min: 0.3, max: 3, step: 0.1 },
    { k: "arty_range_scale", label: "炮兵射程倍率", min: 0.5, max: 2.5, step: 0.1 },
    { k: "terrain_cost_scale", label: "越野通行惩罚", min: 0.3, max: 3, step: 0.1 },
  ],
  "set-air": [
    { k: "air_scale", label: "空军遮断强度", min: 0, max: 2, step: 0.1 },
    { k: "air_prob", label: "遮断命中概率", min: 0, max: 0.5, step: 0.01, pct: true },
    { k: "air_dmg", label: "单次打击伤害", min: 0, max: 10, step: 0.5 },
  ],
  "set-logi": [
    { k: "supply_regen", label: "补给回复/拍", min: 0, max: 15, step: 1 },
    { k: "supply_drain", label: "补给消耗/拍", min: 0, max: 10, step: 0.5 },
    { k: "depot_radius", label: "补给半径(格)", min: 3, max: 14, step: 1 },
    { k: "supply_combat_scale", label: "补给影响战力", min: 0, max: 1, step: 0.05, pct: true },
  ],
  "set-recon": [
    { k: "recon_scale", label: "侦察半径倍率", min: 0.5, max: 3, step: 0.1 },
    { k: "intel_error", label: "敌情误差(格)", min: 0, max: 3, step: 1 },
  ],
  // 引擎弹窗内的智能体运行时（决策成本与健壮性）
  "set-llmrun": [
    { k: "llm_temperature", label: "决策温度", min: 0, max: 1, step: 0.05 },
    { k: "llm_max_tokens", label: "单次Token上限", min: 200, max: 4000, step: 50 },
    { k: "llm_budget", label: "每拍调用预算", min: 5, max: 200, step: 5 },
  ],
};

function buildTuningUI() {
  for (const [gid, fields] of Object.entries(TUNING_GROUPS)) {
    const box = $(gid);
    if (!box) continue;
    box.innerHTML = "";
    for (const f of fields) {
      const lab = document.createElement("label");
      lab.innerHTML = `${f.label} <span class="sv" id="v-${f.k}"></span>` +
        `<input type="range" id="t-${f.k}" min="${f.min}" max="${f.max}" step="${f.step}">`;
      box.appendChild(lab);
      const inp = lab.querySelector("input"), out = lab.querySelector(".sv");
      const show = () => { out.textContent = f.pct ? Math.round(inp.value * 100) + "%" : inp.value; };
      inp.addEventListener("input", show);
    }
  }
}

const tval = (k) => { const el = $("t-" + k); return el ? parseFloat(el.value) : 0; };

function wireSettings() {
  // 推演设置（参数）
  els["btn-settings"].onclick = openSettings;
  els["btn-home-settings"].onclick = openSettings;
  els["btn-close-settings"].onclick = closeSettings;
  els["settings-mask"].addEventListener("click", (e) => {
    if (e.target === els["settings-mask"]) closeSettings();
  });
  $("set-speed").oninput = (e) => ($("set-speed-v").textContent = e.target.value);
  els["btn-apply-friction"].onclick = applyLive;
  els["btn-save-settings"].onclick = saveSettings;
  // 引擎与连接
  els["h-go-settings"].onclick = openEngine;
  els["mode-badge"].onclick = openEngine;
  els["btn-close-engine"].onclick = closeEngine;
  els["engine-mask"].addEventListener("click", (e) => {
    if (e.target === els["engine-mask"]) closeEngine();
  });
  els["btn-llm-test"].onclick = testConnection;
  els["btn-save-engine"].onclick = saveEngine;
}

// 填充指定参数组（agent/battle/air/logi 在设置弹窗；llmrun 在引擎弹窗）
function populateTuning(s, gids) {
  for (const gid of gids) {
    for (const f of (TUNING_GROUPS[gid] || [])) {
      const inp = $("t-" + f.k);
      if (!inp) continue;
      let v;
      if (f.k === "latency_scale" || f.k === "loss_rate") v = (s.friction || {})[f.k];
      else if (f.k === "llm_temperature") v = s.llm.temperature;
      else if (f.k === "llm_max_tokens") v = s.llm.max_tokens;
      else if (f.k === "llm_budget") v = s.llm.budget;
      else v = (s.tuning || {})[f.k];
      if (v !== undefined && v !== null) { inp.value = v; inp.dispatchEvent(new Event("input")); }
    }
  }
}

async function openSettings() {
  els["settings-mask"].classList.remove("hidden");
  try {
    const s = await (await fetch("/api/settings")).json();
    const sel = $("set-scenario");
    sel.innerHTML = "";
    const list = s.scenarios || [];
    for (const sc of list) {
      const opt = document.createElement("option");
      opt.value = sc.id; opt.textContent = sc.name;
      sel.appendChild(opt);
    }
    sel.value = s.scenario || (list[0] && list[0].id) || "cross_river";
    $("set-seed").value = s.seed ?? 7;
    $("set-speed").value = s.speed;
    $("set-speed-v").textContent = s.speed;
    const wsel = $("set-weather");
    if (wsel) {
      wsel.innerHTML = (s.weather_options || []).map((o) =>
        `<option value="${o.id}">${o.name}</option>`).join("");
      wsel.value = s.weather_override || "auto";
    }
    populateTuning(s, ["set-agent", "set-battle", "set-morale", "set-move",
                       "set-air", "set-logi", "set-recon"]);
    els["set-status"].textContent = s.llm.available ? "当前：LLM 已接入 ✓" : "当前：规则模式（未配置 Key）";
  } catch (e) { els["set-status"].textContent = "读取设置失败"; }
}

function closeSettings() { els["settings-mask"].classList.add("hidden"); }

// ============================================================
// 三·五、战役定制中心
//    参照十余场经典战役，把"一场战役像什么样"拆成通用量化参数
//    （环境层天气/地形 → 全局层烈度/机动/后勤/士气/空军 → 双方实力），
//    傻瓜式：点一场预置 → 拖几下滑杆 → 「应用并启动推演」。
// ============================================================
const BT = {
  meta: null, presets: [], factions: [],
  cfg: { env: {}, global: {}, sides: {}, preset: "" },
};

function wireBattle() {
  const open = () => { control({ action: "pause" }); openBattle(); };
  els["btn-battle"].onclick = open;
  els["btn-home-battle"].onclick = open;
  els["btn-close-battle"].onclick = closeBattle;
  els["battle-mask"].addEventListener("click", (e) => {
    if (e.target === els["battle-mask"]) closeBattle();
  });
  els["btn-battle-clear"].onclick = clearBattleCfg;
  els["btn-battle-apply-launch"].onclick = applyLaunchBattle;
  els["bt-reset-env"].onclick = () => { BT.cfg.env = {}; BT.cfg.preset = ""; renderBattleForm(); };
  els["bt-reset-global"].onclick = () => { BT.cfg.global = {}; BT.cfg.preset = ""; renderBattleForm(); };
  els["bt-reset-sides"].onclick = () => { BT.cfg.sides = {}; BT.cfg.preset = ""; renderBattleForm(); };
}

async function openBattle() {
  BT.cfg = { env: {}, global: {}, sides: {}, preset: "" };
  els["battle-mask"].classList.remove("hidden");
  els["bt-status"].textContent = "正在加载十余场经典战役参数…";
  try {
    const [params, st] = await Promise.all([
      (await fetch("/api/battle/params")).json(),
      (await fetch("/api/battle")).json(),
    ]);
    BT.meta = params;
    BT.presets = st.presets || [];
    BT.factions = st.factions || [];
    if (st.config && Object.keys(st.config).length) {
      BT.cfg = {
        env: st.config.env || {}, global: st.config.global || {},
        sides: st.config.sides || {}, preset: st.config.preset || "",
      };
    }
    renderBattleForm();
    const hasCfg = Object.keys(BT.cfg.global).length || Object.keys(BT.cfg.sides).length || Object.keys(BT.cfg.env).length;
    els["bt-status"].textContent = hasCfg
      ? `当前已套用${BT.cfg.preset ? "「" + (BT.presets.find(p => p.id === BT.cfg.preset) || {}).name + "」" : ""}——改动「应用并启动」即生效`
      : "当前为想定原始设置 —— 挑一场预置或随手调几项即可";
  } catch (e) { els["bt-status"].textContent = "加载失败：" + String(e); }
}

function closeBattle() { els["battle-mask"].classList.add("hidden"); }

function renderBattleForm() { renderPresets(); renderEnv(); renderGlobal(); renderSides(); }

// —— ① 参考战役（预置）——
function renderPresets() {
  const box = els["bt-presets"], list = BT.presets || [];
  els["bt-preset-count"].textContent = `共 ${list.length} 场`;
  box.innerHTML = list.map(p => `
    <div class="bt-preset${BT.cfg.preset === p.id ? " active" : ""}" data-id="${p.id}">
      <span class="bt-pre-tag">${esc(p.category)}</span>
      <span class="bt-pre-name">${esc(p.name)}</span>
      <span class="bt-pre-sub">${esc(p.codename)} · ${esc(p.era)} · ${esc(p.theater)}</span>
      <span class="bt-pre-desc">${esc(p.desc)}</span>
    </div>`).join("");
  box.querySelectorAll(".bt-preset").forEach(el =>
    el.addEventListener("click", () => applyPreset(el.dataset.id)));
}

function applyPreset(id) {
  const p = BT.presets.find(x => x.id === id); if (!p) return;
  BT.cfg.preset = id;
  BT.cfg.env = Object.assign({}, p.env || {});
  BT.cfg.global = Object.assign({}, p.params || {});
  BT.cfg.sides = {};
  (BT.factions || []).forEach((f, i) => {
    BT.cfg.sides[f.id] = Object.assign({}, BT.meta.side_default, (p.sides || [])[i] || {});
  });
  renderBattleForm();
  els["bt-status"].textContent = `已套用「${p.name}」—— 可再逐项精调，然后「应用并启动推演」`;
}

// —— ② 环境层：天气 + 地形 ——
function renderEnv() {
  const host = els["bt-env"];
  const old = host.querySelector(".env-terrain"); if (old) old.remove();
  const wsel = els["bt-weather"], wdesc = els["bt-weather-desc"];
  const cur = BT.cfg.env.weather || "auto";
  wsel.innerHTML = (BT.meta.weather || []).map(w =>
    `<option value="${w.id}">${esc(w.label)}</option>`).join("");
  wsel.value = cur;
  const wmeta = (BT.meta.weather || []).find(w => w.id === cur);
  wdesc.textContent = wmeta ? wmeta.desc : "";
  wsel.onchange = () => {
    const v = wsel.value;
    if (v === "auto") delete BT.cfg.env.weather; else BT.cfg.env.weather = v;
    const m = (BT.meta.weather || []).find(w => w.id === v);
    wdesc.textContent = m ? m.desc : "";
  };
  const rows = (BT.meta.env || []).map(k => {
    const val = BT.cfg.env[k.id] ?? k.default;
    return rowHTML("env", k.id, k.label, k.hint, k.unit, val, k.min, k.max, k.step, k.default);
  }).join("");
  wsel.closest(".bt-env-weather").insertAdjacentHTML("afterend",
    `<div class="bt-grid env-terrain">${rows}</div>`);
  bindRanges(host, ".env-terrain input[type=range]", (k, v) => { BT.cfg.env[k] = v; });
}

// —— ③ 全局层：烈度 / 地形机动 / 后勤 / 士气认知 / 空军 ——
function renderGlobal() {
  const box = els["bt-global"];
  const knobs = (BT.meta.global || []), groups = {};
  for (const g of knobs) (groups[g.group] = groups[g.group] || []).push(g);
  box.innerHTML = "";
  for (const [name, list] of Object.entries(groups)) {
    const rows = list.map(g => {
      const val = BT.cfg.global[g.id] ?? g.default;
      return rowHTML("global", g.id, g.label, g.hint, g.unit, val, g.min, g.max, g.step, g.default);
    }).join("");
    box.insertAdjacentHTML("beforeend",
      `<div class="bt-group"><div class="bt-group-title">${esc(name)}</div><div class="bt-grid">${rows}</div></div>`);
  }
  bindRanges(box, "input[type=range]", (k, v) => { BT.cfg.global[k] = v; });
}

// —— ④ 双方实力：每一方独立 · 兵员/火力/装甲/机动/后勤/士气/制空 ——
function renderSides() {
  const box = els["bt-sides"], dims = BT.meta.side_dims || [];
  box.innerHTML = "";
  if (!(BT.factions || []).length) {
    box.innerHTML = `<div class="bt-dimmer">当前想定暂无参演方 —— 先在「想定库」选用或新建一个想定。</div>`;
    return;
  }
  for (const f of BT.factions) {
    if (!BT.cfg.sides[f.id]) BT.cfg.sides[f.id] = Object.assign({}, BT.meta.side_default);
    const sCfg = BT.cfg.sides[f.id];
    const card = document.createElement("div");
    card.className = "bt-side";
    card.dataset.fid = f.id;
    card.innerHTML = `
      <div class="bt-side-head">
        <span class="bt-side-dot" style="color:${color(f.id)}"></span>
        <span>${esc(f.name)}</span>
        <span class="bt-side-score"></span>
      </div>
      <div class="bt-side-body"><div class="bt-grid">${dims.map(d => {
        const val = sCfg[d.key] ?? d.default;
        return rowHTML("side", d.key, d.label, d.hint, d.unit, val, d.min, d.max, d.step, d.default);
      }).join("")}</div></div>`;
    box.appendChild(card);
    bindRanges(card, "input[type=range]",
      (k, v) => { BT.cfg.sides[f.id][k] = v; updateSideScore(card, f.id); });
    updateSideScore(card, f.id);
  }
  box.querySelectorAll(".bt-row").forEach(r =>
    r.title = (r.title || "") + "（拖动即塑造这支军队的性格；停在左侧=更弱，右侧=更强）");
}

function updateSideScore(card, fid) {
  const c = BT.cfg.sides[fid];
  // 简明加权战力指数（1.00 = 平衡）：兵员/火力/装甲/机动 取几何，机动特指的士气与后勤、制空折算
  const geomean = Math.pow(Math.max(0.05, c.hp) * Math.max(0.05, c.atk) * Math.max(0.05, c.def) * Math.max(0.05, c.speed), 0.25);
  const soft = (c.spirit * 0.55 + c.supply * 0.45);
  const air = 1 + Math.max(0, c.air || 0) * 0.4;
  const score = geomean * soft * air;
  const tag = card.querySelector(".bt-side-score");
  const cls = score > 1.05 ? "bt-strong" : (score < 0.95 ? "bt-weak" : "");
  tag.className = "bt-side-score " + cls;
  tag.textContent = `综合战力 ×${score.toFixed(2)}`;
}

// —— 通用滑杆与绑定 ——
function rowHTML(kind, k, label, hint, unit, val, min, max, step, normAt = 1.0) {
  const n = Math.abs(val - normAt) < 1e-6;
  const unitStr = unit ? " " + unit : "";
  return `<div class="bt-row" data-kind="${kind}" data-k="${k}" title="${esc(hint || "")}">
    <span class="bt-k">${esc(label)}</span>
    <input type="range" data-kind="${kind}" data-k="${k}" data-norm="${normAt}" data-unit="${esc(unit || "")}"
      min="${min}" max="${max}" step="${step}" value="${val}">
    <span class="bt-v ${n ? "norm" : ""}">${val}${unitStr}</span>
  </div>`;
}

function bindRanges(root, sel, setter) {
  root.querySelectorAll(sel).forEach(inp => {
    inp.oninput = () => {
      const v = parseFloat(inp.value);
      setter(inp.dataset.k, v);
      const tag = inp.closest(".bt-row").querySelector(".bt-v");
      const norm = Math.abs(v - parseFloat(inp.dataset.norm)) < 1e-6;
      tag.textContent = v + (inp.dataset.unit ? " " + inp.dataset.unit : "");
      tag.classList.toggle("norm", norm);
    };
  });
}

async function clearBattleCfg() {
  els["bt-status"].textContent = "还原想定中…";
  try {
    await fetch("/api/battle", {
      method: "POST", headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ config: {}, apply: true }),
    });
    BT.cfg = { env: {}, global: {}, sides: {}, preset: "" };
    renderBattleForm();
    closeBattle();
    els.feed.innerHTML = "";
    fetchState();
    els["bt-status"].textContent = "";
  } catch (e) { els["bt-status"].textContent = "还原失败：" + String(e); }
}

async function applyLaunchBattle() {
  const btn = els["btn-battle-apply-launch"];
  btn.disabled = true; els["bt-status"].textContent = "正在应用并启动推演…";
  // 清洗：空值不发送，避免覆盖设置面板里同键的实时参数
  const cfg = { env: {}, global: {}, sides: {} };
  if (BT.cfg.preset) cfg.preset = BT.cfg.preset;
  for (const k of Object.keys(BT.cfg.env)) if (k !== "auto") cfg.env[k] = BT.cfg.env[k];
  for (const [k, v] of Object.entries(BT.cfg.global)) if (v != null) cfg.global[k] = v;
  for (const [fid, m] of Object.entries(BT.cfg.sides)) cfg.sides[fid] = Object.assign({}, m);
  try {
    const r = await (await fetch("/api/battle", {
      method: "POST", headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ config: cfg, apply: true }),
    })).json();
    if (r.ok === false) { els["bt-status"].textContent = "应用失败：" + (r.error || ""); btn.disabled = false; return; }
    // 服务端已按战役配置重建推演，切回指挥台并启动
    closeBattle();
    els.studio.classList.add("hidden");
    els.deck.classList.remove("hidden");
    els.feed.innerHTML = "";
    await control({ action: "start" });
    fetchState();
  } catch (e) {
    els["bt-status"].textContent = "应用失败：" + String(e);
  } finally { btn.disabled = false; }
}

function renderConnStatus(llm) {
  const dot = els["conn-dot"], state = els["conn-state"], meta = els["conn-meta"];
  if (llm.available) {
    dot.className = "conn-dot ok";
    state.className = "conn-state ok";
    state.textContent = "LLM 已接入";
    meta.textContent = `${llm.model || "?"} · ${llm.base_url || "OpenAI 兼容端点"}`;
  } else {
    dot.className = "conn-dot off";
    state.className = "conn-state";
    state.textContent = "规则模式（未配置 Key）";
    meta.textContent = "离线确定性推演；填好端点后点「测试连接」即可升级智能决策。";
  }
}

async function openEngine() {
  els["engine-mask"].classList.remove("hidden");
  els["conn-result"].classList.add("hidden");
  try {
    const s = await (await fetch("/api/settings")).json();
    S.llm = s.llm || S.llm;
    $("engine-policy").value = s.policy_mode;
    $("eng-llm-url").value = s.llm.base_url || "";
    $("eng-llm-model").value = s.llm.model || "";
    $("eng-llm-key").value = "";
    $("eng-llm-retry").value = s.llm.retry ?? 2;
    $("eng-llm-timeout").value = s.llm.timeout ?? 90;
    $("eng-use-tools").checked = !!s.llm.use_tools;
    $("eng-top-p").value = s.llm.top_p ?? 1;
    $("eng-freq").value = s.llm.frequency_penalty ?? 0;
    $("eng-presence").value = s.llm.presence_penalty ?? 0;
    $("eng-fallback").checked = s.llm.fallback_enabled !== false;
    matchProvider();
    populateTuning(s, ["set-llmrun"]);
    renderConnStatus(s.llm);
    els["engine-status"].textContent = "";
  } catch (e) { els["engine-status"].textContent = "读取引擎配置失败"; }
}

function closeEngine() { els["engine-mask"].classList.add("hidden"); }

// ---------- LLM 提供商预设 ----------
const PROVIDERS = {
  "openai":    { url: "https://api.openai.com/v1",        model: "gpt-4o-mini" },
  "deepseek":  { url: "https://api.deepseek.com/v1",      model: "deepseek-chat" },
  "qwen":      { url: "https://dashscope.aliyuncs.com/compatible-mode/v1", model: "qwen-plus" },
  "zhipu":     { url: "https://open.bigmodel.cn/api/paas/v4", model: "glm-4-flash" },
  "moonshot":  { url: "https://api.moonshot.cn/v1",       model: "moonshot-v1-8k" },
  "ollama":    { url: "http://localhost:11434/v1",        model: "qwen2.5:7b" },
};
function matchProvider() {
  // 打开弹窗时按当前 URL 反推预设，命中则亮起对应项
  const sel = $("eng-provider"), url = ($("eng-llm-url").value || "").toLowerCase();
  let hit = "";
  for (const [k, v] of Object.entries(PROVIDERS)) {
    if (url.includes(new URL(v.url).hostname)) { hit = k; break; }
  }
  sel.value = hit;
}
function clamp(v, lo, hi, dft) {
  if (Number.isNaN(v)) return dft;
  return Math.max(lo, Math.min(hi, v));
}
$("eng-provider").addEventListener("change", function () {
  const p = PROVIDERS[this.value];
  if (!p) return;
  $("eng-llm-url").value = p.url;
  $("eng-llm-model").value = p.model;
  // 本地端点没有保密 Key，顺手清掉占位更直观
  if (this.value === "ollama") $("eng-llm-key").value = "";
});

async function testConnection() {
  const btn = els["btn-llm-test"], res = els["conn-result"];
  btn.disabled = true;
  res.classList.remove("hidden");
  res.className = "conn-result testing";
  res.textContent = "正在测试连接…";
  try {
    const r = await (await fetch("/api/llm/test", {
      method: "POST", headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        base_url: $("eng-llm-url").value.trim() || null,
        model: $("eng-llm-model").value.trim() || null,
        api_key: $("eng-llm-key").value.trim() || null,
      }),
    })).json();
    if (r.ok) {
      res.className = "conn-result ok";
      res.textContent = `✓ 连接成功 · ${r.model} · ${r.latency_ms}ms` + (r.reply ? ` · 回复「${r.reply.trim()}」` : "");
    } else {
      res.className = "conn-result err";
      res.textContent = "✗ 连接失败：" + (r.error || "未知错误");
    }
  } catch (e) {
    res.className = "conn-result err";
    res.textContent = "✗ 测试失败：" + String(e);
  } finally { btn.disabled = false; }
}

async function applyLive() {
  const tuning = {};
  // 只推设置弹窗里的实时参数；引擎弹窗的 LLM 运行时走独立保存，避免默认值误覆盖
  for (const gid of ["set-agent", "set-battle", "set-morale", "set-move",
                     "set-air", "set-logi", "set-recon"]) {
    for (const f of (TUNING_GROUPS[gid] || [])) {
      if (f.k === "latency_scale" || f.k === "loss_rate") continue;
      tuning[f.k] = tval(f.k);
    }
  }
  try {
    await Promise.all([
      fetch("/api/friction", {
        method: "POST", headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ latency_scale: tval("latency_scale"), loss_rate: tval("loss_rate") }),
      }),
      fetch("/api/tuning", {
        method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify(tuning),
      }),
    ]);
    els["set-status"].textContent = "参数已实时应用 ✓";
  } catch (e) { els["set-status"].textContent = "应用失败"; }
}

async function saveSettings() {
  const wsel = $("set-weather");
  const body = {
    seed: parseInt($("set-seed").value || "7", 10),
    scenario: $("set-scenario").value,
    weather_override: wsel ? wsel.value : "auto",
  };
  try {
    await fetch("/api/control", {
      method: "POST", headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ action: "speed", speed: parseFloat($("set-speed").value) }),
    });
    await applyLive();
    await fetch("/api/settings", {
      method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify(body),
    });
    closeSettings();
    els.feed.innerHTML = "";
    fetchState();
    updateHomeStatus();
  } catch (e) { /* ignore */ }
}

async function saveEngine() {
  const body = {
    policy_mode: $("engine-policy").value,
    llm_use_tools: $("eng-use-tools").checked,
    llm_retry: parseInt($("eng-llm-retry").value || "2", 10),
    llm_timeout: parseFloat($("eng-llm-timeout").value || "90"),
    llm_top_p: clamp(parseFloat($("eng-top-p").value), 0, 1, 1),
    llm_frequency_penalty: clamp(parseFloat($("eng-freq").value), -2, 2, 0),
    llm_presence_penalty: clamp(parseFloat($("eng-presence").value), -2, 2, 0),
    fallback_enabled: $("eng-fallback").checked,
  };
  const url = $("eng-llm-url").value.trim();
  const model = $("eng-llm-model").value.trim();
  const key = $("eng-llm-key").value.trim();
  if (url) body.llm_base_url = url;
  if (model) body.llm_model = model;
  if (key) body.llm_api_key = key;
  const tuning = {};
  for (const f of (TUNING_GROUPS["set-llmrun"] || [])) tuning[f.k] = tval(f.k);
  try {
    await fetch("/api/settings", {
      method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify(body),
    });
    await fetch("/api/tuning", {
      method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify(tuning),
    });
    closeEngine();
    els.feed.innerHTML = "";
    fetchState();
    updateHomeStatus();
  } catch (e) { els["engine-status"].textContent = "保存失败：" + String(e); }
}

// ---------- 数据 ----------
async function fetchState() {
  try {
    const r = await fetch("/api/state");
    const st = await r.json();
    if (st.epoch !== S.epoch) { S.epoch = st.epoch; els.feed.innerHTML = ""; }
    S.state = st;
    S.sideNames = st.side_names || {};
    startAnimLoop(); // 状态更新后启动动画循环（单位移动/特效）
    S.factions = Object.keys(st.camps || {});
    buildFactionUI();
    buildLookup(st);
    els.tick.textContent = String(st.tick).padStart(3, "0");
    els.scenario.textContent = goodsWeather(st);
    els["deck-scenario"].textContent = st.scenario || "";
    els["run-pulse"].classList.toggle("on", st.running);
    // 昼夜时段与天气指示
    const prd = els["deck-period"];
    if (prd) {
      const pn = st.period === "night" ? "夜" : st.period === "dusk" ? "昏" : "昼";
      prd.textContent = pn;
      prd.className = "period period-" + (st.period || "day");
    }
    // 昼夜进度条
    const dayFill = document.getElementById("day-bar-fill");
    const dayIcon = document.getElementById("day-bar-icon");
    if (dayFill && dayIcon) {
      const dayProgress = ((st.tick % 24) / 24) * 100;
      dayFill.style.width = dayProgress + "%";
      dayIcon.style.left = dayProgress + "%";
      // 根据时段切换图标
      if (st.period === "night") {
        dayIcon.textContent = "☾";
        dayIcon.style.filter = "drop-shadow(0 0 3px rgba(157,184,255,0.8))";
      } else if (st.period === "dusk") {
        dayIcon.textContent = "◐";
        dayIcon.style.filter = "drop-shadow(0 0 3px rgba(255,157,69,0.8))";
      } else {
        dayIcon.textContent = "☀";
        dayIcon.style.filter = "drop-shadow(0 0 3px rgba(255,217,138,0.8))";
      }
    }
    // 双方兵力对比
    const forceRed = document.getElementById("force-red");
    const forceBlue = document.getElementById("force-blue");
    const forceLabel = document.getElementById("force-label");
    if (forceRed && forceBlue && forceLabel) {
      let redStr = 0, blueStr = 0;
      for (const f of S.factions) {
        const camp = st.camps[f] || {};
        const total = (camp.units || []).reduce((s, u) => s + (u.strength || 0), 0);
        if (f === "red") redStr = total;
        else blueStr += total;
      }
      const total = redStr + blueStr || 1;
      const redPct = (redStr / total) * 100;
      const bluePct = (blueStr / total) * 100;
      forceRed.style.width = redPct + "%";
      forceBlue.style.width = bluePct + "%";
      forceLabel.textContent = `${Math.round(redStr)} : ${Math.round(blueStr)}`;
    }
    const wtx = els["deck-weather"];
    if (wtx) { wtx.textContent = goodsWeather(st).replace(/^.*?/, ""); wtx.textContent = st.weather_name || st.weather || ""; }
    const badge = els["mode-badge"];
    badge.textContent = st.llm.available ? `LLM · ${st.llm.model}` : `规则模式 · seed ${st.seed}`;
    badge.classList.toggle("llm", st.llm.available);
    renderOrg();
    renderLegend();
    scheduleDraw();
    // 刷新一线分队面板（若当前可见）
    if (!els.tactical.classList.contains("hidden")) renderTacticalPanelThrottled();
  } catch (e) { /* 服务未就绪时静默重试 */ }
}

function goodsWeather(st) {
  return st.weather ? WEATHER_CN[st.weather] || st.weather : "";
}

/* 一线分队面板：实时展示每个战术Agent（作战单元）的自主状态。 */
const TACT_STATE_CN = {
  advancing: "推进", engaging: "接战", defending: "防御",
  withdrawing: "后撤", holding: "待命", resting: "休整",
  reorganizing: "重组", destroyed: "全损",
};
// 战术面板节流（性能优化：fetchState每1.2秒调用，节流到2秒一次）
let _tactLastRender = 0;
function renderTacticalPanelThrottled() {
  const now = Date.now();
  if (now - _tactLastRender < 2000) return;
  _tactLastRender = now;
  renderTacticalPanel();
}
function renderTacticalPanel() {
  const box = els.tactical;
  if (!box) return;
  const st = S.state;
  if (!st || !st.camps) return;
  const frag = document.createDocumentFragment();
  const title = document.createElement("div");
  title.className = "tact-summary";
  title.textContent = "一线分队自主态势 · 每个作战单位绑定一个战术Agent";
  frag.appendChild(title);
  for (const side of S.factions) {
    const camp = st.camps[side] || {};
    const tacts = camp.tactical || [];
    const units = {};
    for (const u of (camp.units || [])) units[u.id] = u;
    const sideColor = color(side);
    const sec = document.createElement("div");
    sec.className = "tact-side";
    const hd = document.createElement("div");
    hd.className = "tact-side-head";
    hd.innerHTML = `<i style="background:${sideColor}"></i><b>${esc(S.sideNames[side] || side)}</b>
      <span>${tacts.filter(t => t.state !== "destroyed").length} 个分队</span>`;
    sec.appendChild(hd);
    if (!tacts.length) {
      const none = document.createElement("div");
      none.className = "tact-none";
      none.textContent = "暂无战术分队";
      sec.appendChild(none);
    }
    const sorted = [...tacts].sort((a, b) =>
      (a.state === "destroyed") - (b.state === "destroyed"));
    for (const t of sorted) {
      const u = units[t.unit_id];
      const card = document.createElement("div");
      card.className = "tact-card st-" + t.state;
      const cn = TACT_STATE_CN[t.state] || t.state_name || t.state;
      const str = u ? Math.round(u.strength) : "—";
      const mor = u && u.morale !== undefined ? Math.round(u.morale) : "—";
      const fat = u && u.fatigue !== undefined ? Math.round(u.fatigue) : "—";
      const sup = u && u.suppressed ? " · 压制" : "";
      const pos = u ? `(${u.x},${u.y})` : "";
      const dec = t.last_decision ? `<div class="tact-dec">${esc(t.last_decision)}</div>` : "";
      card.innerHTML = `
        <div class="tact-card-top">
          <span class="tact-name">${esc(t.unit_id)}</span>
          <span class="tact-st">${cn}${sup}</span>
        </div>
        <div class="tact-bar"><i style="width:${Math.max(0, Math.min(100, str))}%"></i></div>
        <div class="tact-meta">兵力 ${str} · 士气 ${mor} · 疲劳 ${fat} · ${pos}</div>
        ${dec}`;
      sec.appendChild(card);
    }
    frag.appendChild(sec);
  }
  box.innerHTML = "";
  box.appendChild(frag);
}

function buildLookup(st) {
  S.titles = {}; S.shorts = {}; S.unitOwner = {}; S.unitNames = {};
  for (const side of S.factions) {
    const camp = st.camps[side];
    (function walk(n) {
      S.titles[n.id] = n.title;
      S.shorts[n.id] = n.short || n.title;
      for (const u of n.units) S.unitOwner[u] = n.id;
      (n.children || []).forEach(walk);
    })(camp.org);
    for (const u of camp.units) S.unitNames[u.id] = u.name;
    for (const i of camp.intel) S.unitNames[i.unit_id] = i.name;
  }
}

function buildFactionUI() {
  const key = S.factions.join("|");
  const changed = key !== S.factionsKey;
  if (changed) {
    S.factionsKey = key;
    S.sideColors = {};
    S.factions.forEach((f, i) => (S.sideColors[f] = PALETTE[i % PALETTE.length]));
    if (!S.factions.includes(S.camp)) S.camp = S.factions[0];
  }

  els.tabs.innerHTML = S.factions.map((f) =>
    `<button class="tab${f === S.camp ? " active" : ""}" data-side="${f}" style="--c:${color(f)}">${esc(S.sideNames[f] || f)}指挥链</button>`).join("");
  els.tabs.querySelectorAll(".tab").forEach((t) => t.addEventListener("click", () => {
    els.tabs.querySelectorAll(".tab").forEach((x) => x.classList.remove("active"));
    t.classList.add("active");
    S.camp = t.dataset.side;
    els["intent-target"].textContent = `→ ${S.sideNames[S.camp] || S.camp}主官`;
    renderOrg();
  }));

  els["view-switch"].innerHTML =
    `<button class="vs active" data-view="director">导演视角</button>` +
    S.factions.map((f) =>
      `<button class="vs" data-view="${f}">${esc(S.sideNames[f] || f)}视角</button>`).join("");
  els["view-switch"].querySelectorAll(".vs").forEach((b) => b.addEventListener("click", () => {
    if (S.view === b.dataset.view) return;
    els["view-switch"].querySelectorAll(".vs").forEach((x) => x.classList.remove("active"));
    b.classList.add("active");
    S.view = b.dataset.view;
    S.viewFlash = { start: performance.now() };
    // 切换视角时重置单位渲染位置，避免跨视角单位错位
    S.unitRenderPos = {};
    startAnimLoop();
    scheduleDraw();
  }));
  els["intent-target"].textContent = `→ ${S.sideNames[S.camp] || S.camp}主官`;
  renderOrg();
}

function renderLegend() {
  els["legend-sides"].innerHTML = S.factions.map((f) =>
    `<span><i class="sw" style="background:${color(f)}"></i>${esc(S.sideNames[f] || f)}</span>`).join("");
}

function titleOf(posId) {
  if (posId.startsWith("unit:")) return S.unitNames[posId.slice(5)] || posId.slice(5);
  return S.titles[posId] || posId;
}

// ---------- 指挥链（数据驱动 · 任意编制/任意多方） ----------
function renderOrg() {
  const wrap = els["org-tree"];
  const side = S.camp;
  const camp = (S.state.camps || {})[side];
  if (!camp || !camp.org) { wrap.innerHTML = ""; S.nodes = {}; return; }
  S.nodes = {};

  function nodeHTML(n) {
    S.nodes[n.id] = true;
    const cls = ["onode"];
    if (n.virtual) cls.push("virtual");
    else if (n.staff) cls.push("staff");
    const units = (n.units || []).length;
    const agent = n.virtual ? "" : `<span class="oc-live" title="AI 子智能体"></span>`;
    return `<li class="${cls.join(" ")}" data-pos="${n.id}">
      <div class="ocard" title="${esc(n.title || n.id)}">
        <div class="oc-t">${agent}${esc(shortName(n.id))}</div>
        ${units ? `<span class="oc-u">${units} 部</span>` : ""}
        ${n.staff ? `<span class="oc-badge">参谋</span>` : ""}
      </div>
      ${n.children && n.children.length ? `<ul>${n.children.map(nodeHTML).join("")}</ul>` : ""}
    </li>`;
  }
  wrap.innerHTML = `<ul class="otree">${nodeHTML(camp.org)}</ul>`;
  // 指挥链节点点击：高亮下辖单位并聚焦
  wrap.querySelectorAll(".ocard").forEach((card) => {
    card.style.cursor = "pointer";
    card.addEventListener("click", () => {
      const node = card.closest(".onode");
      if (!node) return;
      const posId = node.dataset.pos;
      // 收集该节点下辖的所有单位
      const unitIds = new Set();
      function collect(n) {
        (n.units || []).forEach((u) => unitIds.add(u.id || u));
        (n.children || []).forEach(collect);
      }
      function findNode(n, id) {
        if (n.id === id) return n;
        for (const c of (n.children || [])) {
          const r = findNode(c, id);
          if (r) return r;
        }
        return null;
      }
      const target = findNode(camp.org, posId);
      if (target) collect(target);
      // 高亮第一个单位
      if (unitIds.size > 0 && S.state) {
        const firstId = Array.from(unitIds)[0];
        for (const f of S.factions) {
          const c = S.state.camps[f] || {};
          const u = (c.units || []).find((x) => x.id === firstId);
          if (u) {
            S.selectedUnit = u.id;
            renderUnitDetail(u);
            focusOnUnit(u);
            scheduleDraw();
            break;
          }
        }
      }
      // 节点闪烁反馈
      card.classList.add("flash");
      setTimeout(() => card.classList.remove("flash"), 600);
    });
  });
}

function animateMsg(e) {
  if (e.camp !== S.camp) return;
  const toId = e.recipient.startsWith("unit:") ? S.unitOwner[e.recipient.slice(5)] : e.recipient;
  const el = els["org-tree"].querySelector(`.onode[data-pos="${toId}"] .ocard`);
  if (el) { el.classList.add("flash"); setTimeout(() => el.classList.remove("flash"), 900); }
}

// ---------- 态势图 ----------
// ===== 地形层缓存（离屏canvas，性能优化）=====
const _terrainCache = { canvas: null, key: "", w: 0, h: 0, cs: 0 };

function _terrainKey(st, cs) {
  // 地形缓存键：map序列化 + 格子尺寸 + 宽高
  let h = st.w + "x" + st.h + "_" + Math.round(cs * 100) + "_";
  for (let y = 0; y < st.h; y++) h += st.map[y];
  return h;
}

function _drawTerrainTexture(ctx, st, cs) {
  // 程序化地形纹理：河流光泽、森林点阵、丘陵等高线、城镇建筑、桥梁、道路
  const W = st.w * cs, H = st.h * cs;
  // 基础底色
  ctx.fillStyle = "#1a2418";
  ctx.fillRect(0, 0, W, H);

  for (let y = 0; y < st.h; y++) {
    for (let x = 0; x < st.w; x++) {
      const t = st.map[y][x];
      const px = x * cs, py = y * cs;
      if (t === "~") {
        // 河流：深蓝渐变 + 光泽波纹
        const g = ctx.createLinearGradient(px, py, px + cs, py + cs);
        g.addColorStop(0, "#1a3a5c");
        g.addColorStop(0.5, "#2a5a8c");
        g.addColorStop(1, "#1a3a5c");
        ctx.fillStyle = g;
        ctx.fillRect(px, py, cs, cs);
        // 波纹高光
        ctx.strokeStyle = "rgba(140,200,255,0.15)";
        ctx.lineWidth = 0.8;
        ctx.beginPath();
        ctx.moveTo(px + cs * 0.1, py + cs * 0.3 + (x + y) % 3);
        ctx.quadraticCurveTo(px + cs * 0.5, py + cs * 0.2, px + cs * 0.9, py + cs * 0.35);
        ctx.stroke();
      } else if (t === "f" || t === "F") {
        // 森林：深绿底 + 树点纹理
        ctx.fillStyle = "#1e3a1e";
        ctx.fillRect(px, py, cs, cs);
        ctx.fillStyle = "rgba(60,120,60,0.5)";
        const seed = (x * 31 + y * 17) % 7;
        for (let i = 0; i < 4; i++) {
          const tx = px + ((i * 7 + seed) % 10) / 10 * cs;
          const ty = py + ((i * 11 + seed * 3) % 10) / 10 * cs;
          ctx.beginPath();
          ctx.arc(tx, ty, cs * 0.12, 0, Math.PI * 2);
          ctx.fill();
        }
      } else if (t === "h" || t === "H") {
        // 丘陵：土黄底 + 等高线弧线
        ctx.fillStyle = "#3a3520";
        ctx.fillRect(px, py, cs, cs);
        ctx.strokeStyle = "rgba(180,160,100,0.25)";
        ctx.lineWidth = 0.8;
        ctx.beginPath();
        ctx.arc(px + cs / 2, py + cs / 2, cs * 0.3, 0, Math.PI * 2);
        ctx.stroke();
        ctx.beginPath();
        ctx.arc(px + cs / 2, py + cs / 2, cs * 0.15, 0, Math.PI * 2);
        ctx.stroke();
      } else if (t === "T" || t === "C") {
        // 城镇：灰底 + 建筑块
        ctx.fillStyle = "#2a2a30";
        ctx.fillRect(px, py, cs, cs);
        ctx.fillStyle = "rgba(140,140,150,0.4)";
        const seed = (x * 13 + y * 29) % 5;
        for (let i = 0; i < 3; i++) {
          const bx = px + ((i * 5 + seed) % 8) / 10 * cs + cs * 0.05;
          const by = py + ((i * 7 + seed * 2) % 8) / 10 * cs + cs * 0.05;
          ctx.fillRect(bx, by, cs * 0.2, cs * 0.2);
        }
      } else if (t === "B") {
        // 桥梁：木色桥面跨河
        ctx.fillStyle = "#5a4a30";
        ctx.fillRect(px, py, cs, cs);
        ctx.strokeStyle = "rgba(200,170,100,0.5)";
        ctx.lineWidth = 1;
        ctx.beginPath();
        ctx.moveTo(px, py + cs * 0.3);
        ctx.lineTo(px + cs, py + cs * 0.3);
        ctx.moveTo(px, py + cs * 0.7);
        ctx.lineTo(px + cs, py + cs * 0.7);
        ctx.stroke();
      } else if (t === "R") {
        // 道路：暗色路径
        ctx.fillStyle = "#2a2820";
        ctx.fillRect(px, py, cs, cs);
        ctx.strokeStyle = "rgba(100,90,70,0.3)";
        ctx.lineWidth = 0.5;
        ctx.setLineDash([2, 3]);
        ctx.beginPath();
        ctx.moveTo(px, py + cs / 2);
        ctx.lineTo(px + cs, py + cs / 2);
        ctx.stroke();
        ctx.setLineDash([]);
      } else {
        // 平原：基础草地
        ctx.fillStyle = "#1f2a1c";
        ctx.fillRect(px, py, cs, cs);
        // 微纹理
        if ((x + y) % 3 === 0) {
          ctx.fillStyle = "rgba(50,80,45,0.3)";
          ctx.fillRect(px + cs * 0.2, py + cs * 0.3, cs * 0.15, cs * 0.15);
        }
      }
    }
  }
}

function _getTerrainLayer(st, cs) {
  const key = _terrainKey(st, cs);
  if (_terrainCache.canvas && _terrainCache.key === key) {
    return _terrainCache.canvas;
  }
  const W = Math.ceil(st.w * cs), H = Math.ceil(st.h * cs);
  const off = document.createElement("canvas");
  off.width = W; off.height = H;
  const octx = off.getContext("2d");
  _drawTerrainTexture(octx, st, cs);
  _terrainCache.canvas = off;
  _terrainCache.key = key;
  _terrainCache.w = W; _terrainCache.h = H;
  return off;
}

// ===== 精致单位图标绘制（NATO军事符号风格）=====
function _drawUnitIcon(ctx, u, px, py, cs, st, tacticalMap) {
  const sideColor = color(u.side);
  const cx = px + cs / 2, cy = py + cs / 2;
  const size = cs * 0.38;

  // 状态光环（接战脉冲/防御/后撤/推进）
  const tstate = tacticalMap[u.id];
  if (tstate && tstate !== "holding" && tstate !== "destroyed") {
    const TACT_COLOR = {
      engaging: "#ff4d4f", defending: "#4c8dff", withdrawing: "#e2a336",
      advancing: "#46c98d",
    };
    const tc = TACT_COLOR[tstate] || "#7c8a98";
    const pulse = tstate === "engaging" ? (Math.sin(st.tick * 1.2) * 0.3 + 0.7) : 0.5;
    const glow = ctx.createRadialGradient(cx, cy, size * 0.5, cx, cy, size * 1.8);
    glow.addColorStop(0, hexA(tc, 0.35 * pulse));
    glow.addColorStop(1, hexA(tc, 0));
    ctx.fillStyle = glow;
    ctx.beginPath();
    ctx.arc(cx, cy, size * 1.8, 0, Math.PI * 2);
    ctx.fill();
  }

  // 单位主体：NATO风格符号
  ctx.save();
  ctx.translate(cx, cy);

  // 阴影
  ctx.shadowColor = "rgba(0,0,0,0.6)";
  ctx.shadowBlur = 4;
  ctx.shadowOffsetY = 1;

  // 填充
  const fillGrad = ctx.createLinearGradient(0, -size, 0, size);
  fillGrad.addColorStop(0, hexA(sideColor, 0.85));
  fillGrad.addColorStop(1, hexA(sideColor, 0.55));
  ctx.fillStyle = fillGrad;

  // 按兵种绘制形状
  ctx.beginPath();
  if (u.kind === "infantry") {
    // 步兵：菱形
    ctx.moveTo(0, -size);
    ctx.lineTo(size * 0.85, 0);
    ctx.lineTo(0, size);
    ctx.lineTo(-size * 0.85, 0);
  } else if (u.kind === "armor") {
    // 装甲：方形（圆角）
    const r = size * 0.2;
    ctx.moveTo(-size * 0.8 + r, -size * 0.7);
    ctx.lineTo(size * 0.8 - r, -size * 0.7);
    ctx.quadraticCurveTo(size * 0.8, -size * 0.7, size * 0.8, -size * 0.7 + r);
    ctx.lineTo(size * 0.8, size * 0.7 - r);
    ctx.quadraticCurveTo(size * 0.8, size * 0.7, size * 0.8 - r, size * 0.7);
    ctx.lineTo(-size * 0.8 + r, size * 0.7);
    ctx.quadraticCurveTo(-size * 0.8, size * 0.7, -size * 0.8, size * 0.7 - r);
    ctx.lineTo(-size * 0.8, -size * 0.7 + r);
    ctx.quadraticCurveTo(-size * 0.8, -size * 0.7, -size * 0.8 + r, -size * 0.7);
  } else if (u.kind === "artillery") {
    // 炮兵：圆形
    ctx.arc(0, 0, size * 0.8, 0, Math.PI * 2);
  } else if (u.kind === "recon") {
    // 侦察：三角形
    ctx.moveTo(0, -size * 0.9);
    ctx.lineTo(size * 0.85, size * 0.7);
    ctx.lineTo(-size * 0.85, size * 0.7);
  } else {
    // 默认：六边形
    for (let i = 0; i < 6; i++) {
      const a = Math.PI / 3 * i - Math.PI / 6;
      const x = Math.cos(a) * size * 0.8, y = Math.sin(a) * size * 0.8;
      if (i === 0) ctx.moveTo(x, y); else ctx.lineTo(x, y);
    }
  }
  ctx.closePath();
  ctx.fill();
  ctx.shadowColor = "transparent";

  // 白色边框
  ctx.strokeStyle = "rgba(255,255,255,0.85)";
  ctx.lineWidth = 1.3;
  ctx.stroke();

  // 内部兵种符号（白色细线）
  ctx.strokeStyle = "rgba(255,255,255,0.9)";
  ctx.fillStyle = "rgba(255,255,255,0.9)";
  ctx.lineWidth = 1.2;
  if (u.kind === "infantry") {
    // 步兵：X交叉
    ctx.beginPath();
    ctx.moveTo(-size * 0.3, -size * 0.3);
    ctx.lineTo(size * 0.3, size * 0.3);
    ctx.moveTo(size * 0.3, -size * 0.3);
    ctx.lineTo(-size * 0.3, size * 0.3);
    ctx.stroke();
  } else if (u.kind === "armor") {
    // 装甲：椭圆（履带感）
    ctx.beginPath();
    ctx.ellipse(0, 0, size * 0.4, size * 0.2, 0, 0, Math.PI * 2);
    ctx.stroke();
  } else if (u.kind === "artillery") {
    // 炮兵：圆点
    ctx.beginPath();
    ctx.arc(0, 0, size * 0.2, 0, Math.PI * 2);
    ctx.fill();
  } else if (u.kind === "recon") {
    // 侦察：眼睛点
    ctx.beginPath();
    ctx.arc(0, size * 0.1, size * 0.18, 0, Math.PI * 2);
    ctx.fill();
  }
  ctx.restore();

  // 兵力条（精致渐变）
  const s = Math.max(0, Math.min(100, u.strength || 0));
  const barW = cs * 0.7, barH = 3;
  const bx = cx - barW / 2, by = cy + cs * 0.42;
  // 背景
  ctx.fillStyle = "rgba(0,0,0,0.5)";
  ctx.fillRect(bx - 0.5, by - 0.5, barW + 1, barH + 1);
  // 渐变兵力
  const barColor = s > 60 ? "#46c98d" : s > 30 ? "#e2a336" : "#e5484d";
  const barGrad = ctx.createLinearGradient(bx, by, bx + barW, by);
  barGrad.addColorStop(0, hexA(barColor, 0.9));
  barGrad.addColorStop(1, barColor);
  ctx.fillStyle = barGrad;
  ctx.fillRect(bx, by, barW * s / 100, barH);

  // 被压制：红色脉冲外框
  if (u.suppressed > 0) {
    const pulse = Math.sin(st.tick * 2) * 0.3 + 0.7;
    ctx.strokeStyle = hexA("#ff5d5d", pulse);
    ctx.lineWidth = 1.5;
    ctx.setLineDash([3, 2]);
    ctx.strokeRect(cx - size * 1.1, cy - size * 1.1, size * 2.2, size * 2.2);
    ctx.setLineDash([]);
  }

  // 士气濒崩：暗红罩
  if (u.morale !== undefined && u.morale < 25 && u.morale_state !== "steady") {
    ctx.fillStyle = "rgba(229,72,77,0.25)";
    ctx.beginPath();
    ctx.arc(cx, cy, size * 1.1, 0, Math.PI * 2);
    ctx.fill();
  }

  // 疲劳警示：顶部三角
  if (u.fatigue !== undefined && u.fatigue > 60) {
    ctx.fillStyle = "rgba(226,163,54,0.9)";
    ctx.beginPath();
    ctx.moveTo(cx + size * 0.7, cy - size * 1.1);
    ctx.lineTo(cx + size * 0.95, cy - size * 1.1);
    ctx.lineTo(cx + size * 0.82, cy - size * 0.85);
    ctx.closePath();
    ctx.fill();
  }

  // 筑垒标记
  if (u.entrenched) {
    ctx.strokeStyle = "rgba(255,255,255,0.6)";
    ctx.lineWidth = 1;
    ctx.beginPath();
    ctx.moveTo(cx - size * 0.5, cy - size * 1.05);
    ctx.lineTo(cx + size * 0.5, cy - size * 1.05);
    ctx.stroke();
  }

  // 朝向指示箭头（facing = 最近移动/接战方向）
  if (u.facing && (u.facing[0] !== 0 || u.facing[1] !== 0)) {
    const fx = u.facing[0], fy = u.facing[1];
    const flen = Math.sqrt(fx * fx + fy * fy) || 1;
    const nx = fx / flen, ny = fy / flen;
    const arrowLen = size * 0.7;
    const ex = cx + nx * arrowLen, ey = cy + ny * arrowLen;
    const isEngaging = tacticalMap && tacticalMap[u.id] === "engaging";
    const arrowColor = isEngaging ? "rgba(255,90,90,0.85)" : `${sideColor}cc`;
    ctx.strokeStyle = arrowColor;
    ctx.lineWidth = isEngaging ? 2 : 1.5;
    ctx.lineCap = "round";
    ctx.beginPath();
    ctx.moveTo(cx + nx * size * 0.35, cy + ny * size * 0.35);
    ctx.lineTo(ex, ey);
    ctx.stroke();
    // 箭头头部
    const headLen = size * 0.2;
    const ang = Math.atan2(ny, nx);
    ctx.fillStyle = arrowColor;
    ctx.beginPath();
    ctx.moveTo(ex, ey);
    ctx.lineTo(ex - Math.cos(ang - 0.5) * headLen, ey - Math.sin(ang - 0.5) * headLen);
    ctx.lineTo(ex - Math.cos(ang + 0.5) * headLen, ey - Math.sin(ang + 0.5) * headLen);
    ctx.closePath();
    ctx.fill();
  }

  // === v0.9.7 新因素状态指示 ===
  // 指挥官标记：金色星标
  if (u.is_commander) {
    ctx.fillStyle = "#ffd700";
    ctx.shadowColor = "rgba(255,215,0,0.8)";
    ctx.shadowBlur = 6;
    ctx.beginPath();
    const sx = cx - size * 0.9, sy = cy - size * 0.9;
    for (let i = 0; i < 5; i++) {
      const a = (Math.PI * 2 / 5) * i - Math.PI / 2;
      const r = i % 2 === 0 ? size * 0.25 : size * 0.12;
      const px = sx + Math.cos(a) * r;
      const py = sy + Math.sin(a) * r;
      if (i === 0) ctx.moveTo(px, py); else ctx.lineTo(px, py);
    }
    ctx.closePath();
    ctx.fill();
    ctx.shadowBlur = 0;
  }

  // 伪装状态：虚线边框+半透明
  if (u.camouflaged) {
    ctx.strokeStyle = "rgba(150,200,150,0.7)";
    ctx.lineWidth = 1;
    ctx.setLineDash([2, 2]);
    ctx.beginPath();
    ctx.arc(cx, cy, size * 1.05, 0, Math.PI * 2);
    ctx.stroke();
    ctx.setLineDash([]);
  }

  // 补给线切断：红色警告
  if (u.supply_line_cut) {
    const pulse = Math.sin(st.tick * 3) * 0.3 + 0.7;
    ctx.fillStyle = `rgba(255,80,80,${pulse})`;
    ctx.font = `bold ${Math.max(8, size * 0.5)}px sans-serif`;
    ctx.textAlign = "center";
    ctx.fillText("⚠", cx + size * 0.9, cy - size * 0.9);
  }

  // 超出指挥范围：橙色感叹号
  if (u.in_command === false && !u.is_commander) {
    ctx.fillStyle = "rgba(255,170,50,0.9)";
    ctx.font = `bold ${Math.max(8, size * 0.45)}px sans-serif`;
    ctx.textAlign = "center";
    ctx.fillText("!", cx - size * 0.9, cy - size * 0.9);
  }

  // 经验等级：右下角小标记
  if (u.exp_level && u.exp_level !== "green") {
    const expColor = u.exp_level === "elite" ? "#ffd700" : u.exp_level === "veteran" ? "#57d99b" : "#7dd3fc";
    ctx.fillStyle = expColor;
    ctx.beginPath();
    ctx.arc(cx + size * 0.7, cy + size * 0.7, size * 0.15, 0, Math.PI * 2);
    ctx.fill();
  }

  // 行军队形：移动箭头指示
  if (u.formation === "march" && u.order) {
    ctx.fillStyle = "rgba(255,200,100,0.8)";
    ctx.font = `${Math.max(7, size * 0.4)}px sans-serif`;
    ctx.textAlign = "center";
    ctx.fillText("→", cx, cy - size * 1.2);
  }
}

// ===== 战斗特效系统 =====
function spawnEffect(type, x, y, opts = {}) {
  S.effects.push({
    type, x, y,
    start: performance.now(),
    duration: opts.duration || 800,
    color: opts.color || "#ff7a45",
    size: opts.size || 1,
    fromX: opts.fromX, fromY: opts.fromY,
  });
  // 限制特效数量，避免内存膨胀
  if (S.effects.length > 60) S.effects.shift();
}

// ===== 战斗音效系统（Web Audio API 程序化生成，无需外部文件）=====
function initAudio() {
  if (S.audio.ctx) return;
  try {
    S.audio.ctx = new (window.AudioContext || window.webkitAudioContext)();
  } catch (e) { S.audio.enabled = false; }
}

function playSound(type) {
  if (!S.audio.enabled) return;
  initAudio();
  if (!S.audio.ctx) return;
  const ctx = S.audio.ctx;
  if (ctx.state === "suspended") ctx.resume();
  const now = ctx.currentTime;
  // 节流：同类音效最小间隔
  const minInterval = { explosion: 120, artillery: 200, gunfire: 60, message: 80, destroyed: 300 }[type] || 100;
  const last = S.audio.lastPlay[type] || 0;
  if (performance.now() - last < minInterval) return;
  S.audio.lastPlay[type] = performance.now();
  const vol = S.audio.volume;

  if (type === "explosion" || type === "artillery") {
    // 爆炸：白噪声 burst + 低频轰鸣
    const dur = type === "artillery" ? 0.6 : 0.4;
    // 噪声
    const bufSize = ctx.sampleRate * dur;
    const buf = ctx.createBuffer(1, bufSize, ctx.sampleRate);
    const data = buf.getChannelData(0);
    for (let i = 0; i < bufSize; i++) {
      data[i] = (Math.random() * 2 - 1) * Math.pow(1 - i / bufSize, 2);
    }
    const noise = ctx.createBufferSource();
    noise.buffer = buf;
    const nf = ctx.createBiquadFilter();
    nf.type = "lowpass";
    nf.frequency.setValueAtTime(type === "artillery" ? 800 : 1200, now);
    nf.frequency.exponentialRampToValueAtTime(100, now + dur);
    const ng = ctx.createGain();
    ng.gain.setValueAtTime(vol * 0.5, now);
    ng.gain.exponentialRampToValueAtTime(0.001, now + dur);
    noise.connect(nf); nf.connect(ng); ng.connect(ctx.destination);
    noise.start(now); noise.stop(now + dur);
    // 低频轰鸣
    const osc = ctx.createOscillator();
    osc.type = "sine";
    osc.frequency.setValueAtTime(type === "artillery" ? 80 : 120, now);
    osc.frequency.exponentialRampToValueAtTime(30, now + dur * 0.8);
    const og = ctx.createGain();
    og.gain.setValueAtTime(vol * 0.4, now);
    og.gain.exponentialRampToValueAtTime(0.001, now + dur);
    osc.connect(og); og.connect(ctx.destination);
    osc.start(now); osc.stop(now + dur);
  } else if (type === "gunfire") {
    // 枪声：短促高频脉冲
    const dur = 0.08;
    const osc = ctx.createOscillator();
    osc.type = "square";
    osc.frequency.setValueAtTime(800 + Math.random() * 400, now);
    osc.frequency.exponentialRampToValueAtTime(200, now + dur);
    const g = ctx.createGain();
    g.gain.setValueAtTime(vol * 0.15, now);
    g.gain.exponentialRampToValueAtTime(0.001, now + dur);
    osc.connect(g); g.connect(ctx.destination);
    osc.start(now); osc.stop(now + dur);
  } else if (type === "message") {
    // 消息提示：短促"嘀"
    const osc = ctx.createOscillator();
    osc.type = "sine";
    osc.frequency.setValueAtTime(1200, now);
    const g = ctx.createGain();
    g.gain.setValueAtTime(vol * 0.1, now);
    g.gain.exponentialRampToValueAtTime(0.001, now + 0.08);
    osc.connect(g); g.connect(ctx.destination);
    osc.start(now); osc.stop(now + 0.08);
  } else if (type === "destroyed") {
    // 单位全损：低沉下行
    const dur = 0.5;
    const osc = ctx.createOscillator();
    osc.type = "sawtooth";
    osc.frequency.setValueAtTime(200, now);
    osc.frequency.exponentialRampToValueAtTime(50, now + dur);
    const g = ctx.createGain();
    g.gain.setValueAtTime(vol * 0.25, now);
    g.gain.exponentialRampToValueAtTime(0.001, now + dur);
    osc.connect(g); g.connect(ctx.destination);
    osc.start(now); osc.stop(now + dur);
  }
}

function _renderEffects(ctx, ox, oy, cs, st) {
  const now = performance.now();
  const alive = [];
  for (const ef of S.effects) {
    const age = now - ef.start;
    if (age > ef.duration) continue;
    alive.push(ef);
    const t = age / ef.duration; // 0~1
    const px = ox + ef.x * cs + cs / 2;
    const py = oy + ef.y * cs + cs / 2;

    if (ef.type === "explosion") {
      // 爆炸：径向渐变闪光 + 扩散圈
      const r = cs * (0.3 + t * 1.2) * ef.size;
      const alpha = (1 - t) * 0.8;
      // 闪光
      const g = ctx.createRadialGradient(px, py, 0, px, py, r);
      g.addColorStop(0, `rgba(255,240,180,${alpha})`);
      g.addColorStop(0.3, `rgba(255,140,50,${alpha * 0.8})`);
      g.addColorStop(0.7, `rgba(200,60,30,${alpha * 0.4})`);
      g.addColorStop(1, "rgba(100,20,10,0)");
      ctx.fillStyle = g;
      ctx.beginPath(); ctx.arc(px, py, r, 0, Math.PI * 2); ctx.fill();
      // 扩散圈
      ctx.strokeStyle = `rgba(255,180,80,${(1 - t) * 0.6})`;
      ctx.lineWidth = 2 * (1 - t);
      ctx.beginPath(); ctx.arc(px, py, r * 0.8, 0, Math.PI * 2); ctx.stroke();
    } else if (ef.type === "bigExplosion") {
      // 大爆炸（单位全损）：更大更亮 + 烟雾
      const r = cs * (0.5 + t * 2) * ef.size;
      const alpha = (1 - t) * 0.9;
      const g = ctx.createRadialGradient(px, py, 0, px, py, r);
      g.addColorStop(0, `rgba(255,255,220,${alpha})`);
      g.addColorStop(0.2, `rgba(255,180,60,${alpha * 0.9})`);
      g.addColorStop(0.5, `rgba(220,80,30,${alpha * 0.6})`);
      g.addColorStop(0.8, `rgba(80,30,20,${alpha * 0.3})`);
      g.addColorStop(1, "rgba(30,10,5,0)");
      ctx.fillStyle = g;
      ctx.beginPath(); ctx.arc(px, py, r, 0, Math.PI * 2); ctx.fill();
      // 碎片
      for (let i = 0; i < 6; i++) {
        const ang = (i / 6) * Math.PI * 2 + ef.start * 0.001;
        const dist = r * 0.7 * (0.5 + t * 0.5);
        ctx.fillStyle = `rgba(255,200,100,${(1 - t) * 0.7})`;
        ctx.beginPath();
        ctx.arc(px + Math.cos(ang) * dist, py + Math.sin(ang) * dist, cs * 0.06 * (1 - t), 0, Math.PI * 2);
        ctx.fill();
      }
    } else if (ef.type === "fireline") {
      // 火力线：从from到目标的虚线
      if (ef.fromX === undefined) continue;
      const fx = ox + ef.fromX * cs + cs / 2;
      const fy = oy + ef.fromY * cs + cs / 2;
      const alpha = (1 - t) * 0.7;
      ctx.strokeStyle = `rgba(255,200,80,${alpha})`;
      ctx.lineWidth = 1.5;
      ctx.setLineDash([4, 3]);
      ctx.beginPath();
      ctx.moveTo(fx, fy);
      ctx.lineTo(px, py);
      ctx.stroke();
      ctx.setLineDash([]);
      // 命中点闪光
      ctx.fillStyle = `rgba(255,220,120,${alpha})`;
      ctx.beginPath(); ctx.arc(px, py, cs * 0.12 * (1 - t * 0.5), 0, Math.PI * 2); ctx.fill();
    } else if (ef.type === "artillery") {
      // 炮击弹道：抛物线 + 弹丸 + 落点爆炸
      if (ef.fromX === undefined) continue;
      const fx = ox + ef.fromX * cs + cs / 2;
      const fy = oy + ef.fromY * cs + cs / 2;
      const dist = Math.sqrt((px - fx) ** 2 + (py - fy) ** 2);
      const arcH = Math.min(cs * 2.5, dist * 0.5); // 弹道高度
      // 弹道轨迹（虚线，渐隐）
      ctx.strokeStyle = `rgba(255,180,80,${(1 - t) * 0.35})`;
      ctx.lineWidth = 1;
      ctx.setLineDash([3, 4]);
      ctx.beginPath();
      for (let i = 0; i <= 20; i++) {
        const lt = i / 20;
        const lx = fx + (px - fx) * lt;
        const ly = fy + (py - fy) * lt - 4 * arcH * lt * (1 - lt);
        if (i === 0) ctx.moveTo(lx, ly); else ctx.lineTo(lx, ly);
      }
      ctx.stroke();
      ctx.setLineDash([]);
      // 弹丸位置（前70%时间飞行，后30%爆炸）
      if (t < 0.7) {
        const ft = t / 0.7;
        const bx = fx + (px - fx) * ft;
        const by = fy + (py - fy) * ft - 4 * arcH * ft * (1 - ft);
        // 弹丸发光
        const bg = ctx.createRadialGradient(bx, by, 0, bx, by, cs * 0.15);
        bg.addColorStop(0, "rgba(255,240,180,0.95)");
        bg.addColorStop(0.5, "rgba(255,160,60,0.6)");
        bg.addColorStop(1, "rgba(255,100,30,0)");
        ctx.fillStyle = bg;
        ctx.beginPath(); ctx.arc(bx, by, cs * 0.15, 0, Math.PI * 2); ctx.fill();
        // 弹丸尾迹
        ctx.strokeStyle = "rgba(255,180,80,0.4)";
        ctx.lineWidth = 1.5;
        ctx.beginPath();
        const tx2 = fx + (px - fx) * Math.max(0, ft - 0.15);
        const ty2 = fy + (py - fy) * Math.max(0, ft - 0.15) - 4 * arcH * Math.max(0, ft - 0.15) * (1 - Math.max(0, ft - 0.15));
        ctx.moveTo(tx2, ty2); ctx.lineTo(bx, by);
        ctx.stroke();
      } else {
        // 落点爆炸
        const et = (t - 0.7) / 0.3;
        const r = cs * (0.3 + et * 1.5) * (ef.size || 1);
        const alpha = (1 - et) * 0.9;
        const g = ctx.createRadialGradient(px, py, 0, px, py, r);
        g.addColorStop(0, `rgba(255,250,200,${alpha})`);
        g.addColorStop(0.3, `rgba(255,160,60,${alpha * 0.85})`);
        g.addColorStop(0.7, `rgba(200,70,30,${alpha * 0.5})`);
        g.addColorStop(1, "rgba(80,20,10,0)");
        ctx.fillStyle = g;
        ctx.beginPath(); ctx.arc(px, py, r, 0, Math.PI * 2); ctx.fill();
        // 扩散圈
        ctx.strokeStyle = `rgba(255,180,80,${(1 - et) * 0.7})`;
        ctx.lineWidth = 2 * (1 - et);
        ctx.beginPath(); ctx.arc(px, py, r * 0.7, 0, Math.PI * 2); ctx.stroke();
      }
    }
  }
  S.effects = alive;
}

// 战术Agent决策气泡渲染
function _renderDecisionBubbles(ctx, ox, oy, cs) {
  const now = performance.now();
  const alive = [];
  for (const b of S.decisionBubbles) {
    const age = now - b.start;
    if (age > b.duration) continue;
    alive.push(b);
    const t = age / b.duration;
    const rp = S.unitRenderPos[b.unit_id];
    const bx = rp ? rp.px : (ox + b.x * cs);
    const by = rp ? rp.py : (oy + b.y * cs);
    const cx = bx + cs / 2;
    // 气泡向上浮动
    const floatY = by - cs * 0.5 - t * cs * 0.4;
    const alpha = t < 0.15 ? t / 0.15 : (t > 0.7 ? (1 - t) / 0.3 : 1);
    const bColor = color(b.side);
    // 气泡背景
    ctx.font = "600 10px 'JetBrains Mono', monospace";
    const tw = ctx.measureText(b.text).width;
    const bw = tw + 14, bh = 20;
    const bxp = cx - bw / 2, byp = floatY - bh;
    ctx.fillStyle = `rgba(8,16,12,${0.88 * alpha})`;
    roundRect(ctx, bxp, byp, bw, bh, 4);
    ctx.fill();
    ctx.strokeStyle = hexA(bColor, 0.7 * alpha);
    ctx.lineWidth = 1;
    roundRect(ctx, bxp, byp, bw, bh, 4);
    ctx.stroke();
    // 气泡小三角
    ctx.fillStyle = `rgba(8,16,12,${0.88 * alpha})`;
    ctx.beginPath();
    ctx.moveTo(cx - 4, byp + bh);
    ctx.lineTo(cx + 4, byp + bh);
    ctx.lineTo(cx, byp + bh + 5);
    ctx.closePath();
    ctx.fill();
    // 文字
    ctx.fillStyle = hexA(bColor, alpha);
    ctx.fillText(b.text, bxp + 7, byp + 14);
  }
  S.decisionBubbles = alive;
}

function _drawGhostUnit(ctx, u, px, py, cs) {
  // 情报幽灵单位：虚线框 + ?
  const cx = px + cs / 2, cy = py + cs / 2;
  const size = cs * 0.35;
  ctx.globalAlpha = u.age > 8 ? 0.3 : 0.6;
  ctx.setLineDash([3, 3]);
  ctx.strokeStyle = color(u.side);
  ctx.lineWidth = 1.2;
  ctx.strokeRect(cx - size, cy - size * 0.7, size * 2, size * 1.4);
  ctx.setLineDash([]);
  ctx.fillStyle = color(u.side);
  ctx.font = `${Math.max(9, Math.floor(cs * 0.3))}px sans-serif`;
  ctx.textAlign = "center"; ctx.textBaseline = "middle";
  ctx.fillText("?", cx, cy);
  ctx.globalAlpha = 1;
}

// drawMap 的 requestAnimationFrame 节流（性能优化：合并频繁调用）
let _drawRaf = null;
function scheduleDraw() {
  if (_drawRaf) return;
  _drawRaf = requestAnimationFrame(() => {
    _drawRaf = null;
    _drawMapImmediate();
  });
}

// 智能动画循环：有单位移动或特效时持续重绘，否则停止（性能优化）
let _animLoop = null;
function _hasAnimation() {
  if (S.effects.length > 0) return true;
  if (S.cam.anim) return true;
  if (S.decisionBubbles.length > 0) return true;
  const st = S.state;
  if (!st) return false;
  // 检查是否有单位渲染位置≠目标位置
  for (const key in S.unitRenderPos) {
    const rp = S.unitRenderPos[key];
    // 简单检查：渲染位置是否在变化（通过上一帧记录）
    if (rp._lastPx !== undefined && Math.abs(rp.px - rp._lastPx) > 0.1) return true;
  }
  return false;
}
function startAnimLoop() {
  if (_animLoop) return;
  const tick = () => {
    _drawMapImmediate();
    // 记录上一帧位置用于判断是否在移动
    for (const key in S.unitRenderPos) {
      const rp = S.unitRenderPos[key];
      rp._lastPx = rp.px;
      rp._lastPy = rp.py;
    }
    if (_hasAnimation()) {
      _animLoop = requestAnimationFrame(tick);
    } else {
      _animLoop = null;
    }
  };
  _animLoop = requestAnimationFrame(tick);
}
function _drawMapImmediate() {
  _updateZoomAnim();
  const st = S.state;
  if (!st) return;
  const c = els["map"], wrap = c.parentElement;
  const dpr = window.devicePixelRatio || 1;
  const cw = wrap.clientWidth, ch = wrap.clientHeight;
  if (cw < 40 || ch < 40) return;
  if (c.width !== Math.round(cw * dpr) || c.height !== Math.round(ch * dpr)) {
    c.width = Math.round(cw * dpr); c.height = Math.round(ch * dpr);
  }
  const ctx = c.getContext("2d");
  ctx.setTransform(dpr, 0, 0, dpr, 0, 0);

  const baseCs = Math.min(cw / st.w, ch / st.h);
  const zoom = S.cam.scale;
  const cs = baseCs * zoom;
  const cW = cs * st.w, cH = cs * st.h;
  let ox = (cw - cW) / 2 + S.cam.panX, oy = (ch - cH) / 2 + S.cam.panY;
  if (cW <= cw) ox = (cw - cW) / 2; else ox = Math.max(cw - cW, Math.min(0, ox));
  if (cH <= ch) oy = (ch - cH) / 2; else oy = Math.max(ch - cH, Math.min(0, oy));
  S.cam.view = { cs, ox, oy, base: baseCs, cw, ch };
  els["zoom-label"].textContent = Math.round(zoom * 100) + "%";

  // 清空
  ctx.fillStyle = "#0d1117";
  ctx.fillRect(0, 0, cw, ch);

  // 地形层（离屏缓存，性能优化核心）
  const terrain = _getTerrainLayer(st, cs);
  ctx.imageSmoothingEnabled = true;
  ctx.imageSmoothingQuality = "high";
  ctx.drawImage(terrain, ox, oy, cW, cH);

  // 战术网格（仅缩放>1.2时显示，减少绘制）
  if (zoom > 1.2) {
    ctx.strokeStyle = "rgba(100,140,100,0.08)";
    ctx.lineWidth = 0.5;
    ctx.beginPath();
    for (let x = 0; x <= st.w; x++) {
      ctx.moveTo(ox + x * cs, oy);
      ctx.lineTo(ox + x * cs, oy + st.h * cs);
    }
    for (let y = 0; y <= st.h; y++) {
      ctx.moveTo(ox, oy + y * cs);
      ctx.lineTo(ox + st.w * cs, oy + y * cs);
    }
    ctx.stroke();
  }

  // 补给站/目标点（精致标记）
  ctx.textAlign = "center"; ctx.textBaseline = "middle";
  for (const d of (st.depots || [])) {
    const dx = ox + d.x * cs + cs / 2, dy = oy + d.y * cs + cs / 2;
    const dc = (S.factions.includes(d.owner) && color(d.owner)) ? color(d.owner) : "#ffffff";
    // 光环
    const dg = ctx.createRadialGradient(dx, dy, 0, dx, dy, cs * 0.5);
    dg.addColorStop(0, hexA(dc, 0.4));
    dg.addColorStop(1, hexA(dc, 0));
    ctx.fillStyle = dg;
    ctx.beginPath(); ctx.arc(dx, dy, cs * 0.5, 0, Math.PI * 2); ctx.fill();
    // 菱形标记
    ctx.fillStyle = dc;
    ctx.beginPath();
    ctx.moveTo(dx, dy - cs * 0.18);
    ctx.lineTo(dx + cs * 0.15, dy);
    ctx.lineTo(dx, dy + cs * 0.18);
    ctx.lineTo(dx - cs * 0.15, dy);
    ctx.closePath(); ctx.fill();
    ctx.strokeStyle = "rgba(255,255,255,0.7)"; ctx.lineWidth = 1; ctx.stroke();
  }

  // 战术Agent状态映射
  const tacticalMap = {};
  for (const f of S.factions) {
    for (const t of ((st.camps[f] || {}).tactical || [])) {
      tacticalMap[t.unit_id] = t.state;
    }
  }

  // 收集单位
  let units = [];
  if (S.view === "director") {
    units = S.factions.flatMap((f) => (st.camps[f] || {}).units || []);
  } else {
    const camp = st.camps[S.view] || {};
    units = (camp.units || []).map((u) => ({ ...u }));
    for (const i of (camp.intel || [])) {
      const owner = S.factions.find((f) => f !== S.view);
      units.push({ id: i.unit_id, side: owner, kind: i.kind, x: i.x, y: i.y, ghost: true, age: st.tick - i.tick });
    }
  }

  // 绘制单位（按y排序，模拟深度 + 移动平滑插值）
  units.sort((a, b) => a.y - b.y);
  const lerp = (a, b, t) => a + (b - a) * t;
  for (const u of units) {
    const targetPx = ox + u.x * cs, targetPy = oy + u.y * cs;
    const key = u.id || ("ghost_" + u.x + "_" + u.y);
    let rp = S.unitRenderPos[key];
    if (!rp) {
      rp = { px: targetPx, py: targetPy };
      S.unitRenderPos[key] = rp;
    }
    // 平滑插值：每帧移动15%的距离，快速响应但流畅
    const smooth = 0.18;
    rp.px = lerp(rp.px, targetPx, smooth);
    rp.py = lerp(rp.py, targetPy, smooth);
    // 距离过远时直接对齐（避免重置后缓慢漂移）
    if (Math.abs(rp.px - targetPx) > cs * 3 || Math.abs(rp.py - targetPy) > cs * 3) {
      rp.px = targetPx; rp.py = targetPy;
    }
    if (u.ghost) {
      _drawGhostUnit(ctx, u, rp.px, rp.py, cs);
    } else {
      _drawUnitIcon(ctx, u, rp.px, rp.py, cs, st, tacticalMap);
    }
  }

  // 战斗特效（在单位之上，夜间覆盖层之下）
  _renderEffects(ctx, ox, oy, cs, st);

  // 选中单位高亮框（脉冲+四角装饰）
  if (S.selectedUnit) {
    for (const u of units) {
      if (u.id !== S.selectedUnit) continue;
      const rp = S.unitRenderPos[u.id];
      const spx = rp ? rp.px : (ox + u.x * cs);
      const spy = rp ? rp.py : (oy + u.y * cs);
      const scx = spx + cs / 2, scy = spy + cs / 2;
      const pulse = Math.sin(performance.now() * 0.005) * 0.3 + 0.7;
      const selColor = color(u.side);
      const boxSize = cs * 0.55;
      // 外发光
      const glow = ctx.createRadialGradient(scx, scy, 0, scx, scy, cs * 0.9);
      glow.addColorStop(0, hexA(selColor, 0.25 * pulse));
      glow.addColorStop(1, hexA(selColor, 0));
      ctx.fillStyle = glow;
      ctx.beginPath(); ctx.arc(scx, scy, cs * 0.9, 0, Math.PI * 2); ctx.fill();
      // 矩形框
      ctx.strokeStyle = hexA(selColor, 0.8 + 0.2 * pulse);
      ctx.lineWidth = 2;
      ctx.setLineDash([4, 3]);
      ctx.strokeRect(scx - boxSize, scy - boxSize, boxSize * 2, boxSize * 2);
      ctx.setLineDash([]);
      // 四角装饰
      const cLen = cs * 0.18;
      ctx.strokeStyle = selColor;
      ctx.lineWidth = 2.5;
      const corners = [
        [scx - boxSize, scy - boxSize, 1, 1],
        [scx + boxSize, scy - boxSize, -1, 1],
        [scx - boxSize, scy + boxSize, 1, -1],
        [scx + boxSize, scy + boxSize, -1, -1],
      ];
      for (const [cx, cy, dx, dy] of corners) {
        ctx.beginPath();
        ctx.moveTo(cx + dx * cLen, cy);
        ctx.lineTo(cx, cy);
        ctx.lineTo(cx, cy + dy * cLen);
        ctx.stroke();
      }
      // 单位名称标签
      const label = u.name || u.id;
      ctx.font = "600 11px 'JetBrains Mono', monospace";
      const tw = ctx.measureText(label).width;
      const lx = scx - tw / 2 - 6, ly = scy - boxSize - 22;
      ctx.fillStyle = "rgba(10,18,14,0.9)";
      ctx.fillRect(lx, ly, tw + 12, 18);
      ctx.strokeStyle = hexA(selColor, 0.6);
      ctx.lineWidth = 1;
      ctx.strokeRect(lx, ly, tw + 12, 18);
      ctx.fillStyle = selColor;
      ctx.fillText(label, lx + 6, ly + 13);
      break;
    }
  }

  // 战术Agent决策气泡
  _renderDecisionBubbles(ctx, ox, oy, cs);

  // 视角切换扫描线过渡（军事风格）
  if (S.viewFlash) {
    const vfAge = performance.now() - S.viewFlash.start;
    const vfDur = 600;
    if (vfAge < vfDur) {
      const vft = vfAge / vfDur;
      const scanY = vft * ch;
      // 扫描线发光
      const sg = ctx.createLinearGradient(0, scanY - 30, 0, scanY + 30);
      sg.addColorStop(0, "rgba(80,200,255,0)");
      sg.addColorStop(0.5, "rgba(100,220,255,0.25)");
      sg.addColorStop(1, "rgba(80,200,255,0)");
      ctx.fillStyle = sg;
      ctx.fillRect(0, scanY - 30, cw, 60);
      // 扫描线亮边
      ctx.strokeStyle = `rgba(140,230,255,${0.6 * (1 - vft)})`;
      ctx.lineWidth = 1.5;
      ctx.beginPath(); ctx.moveTo(0, scanY); ctx.lineTo(cw, scanY); ctx.stroke();
      // 整体淡入（前30%暗，之后渐亮）
      if (vft < 0.3) {
        ctx.fillStyle = `rgba(0,10,20,${0.5 * (1 - vft / 0.3)})`;
        ctx.fillRect(0, 0, cw, ch);
      }
    } else {
      S.viewFlash = null;
    }
  }

  // 夜间覆盖层：整体暗化 + 单位微光 + 扫描线
  if (st.period === "night") {
    ctx.fillStyle = "rgba(5,10,25,0.45)";
    ctx.fillRect(0, 0, cw, ch);
    // 单位微光（在暗化层之上重新绘制发光）
    for (const u of units) {
      if (u.ghost) continue;
      const cx = ox + u.x * cs + cs / 2, cy = oy + u.y * cs + cs / 2;
      const ug = ctx.createRadialGradient(cx, cy, 0, cx, cy, cs * 0.6);
      ug.addColorStop(0, hexA(color(u.side), 0.15));
      ug.addColorStop(1, hexA(color(u.side), 0));
      ctx.fillStyle = ug;
      ctx.beginPath(); ctx.arc(cx, cy, cs * 0.6, 0, Math.PI * 2); ctx.fill();
    }
    // 扫描线
    ctx.fillStyle = "rgba(0,0,0,0.08)";
    for (let y = 0; y < ch; y += 3) {
      ctx.fillRect(0, y, cw, 1);
    }
  } else if (st.period === "dusk") {
    // 黄昏：暖色滤镜
    ctx.fillStyle = "rgba(60,35,15,0.18)";
    ctx.fillRect(0, 0, cw, ch);
  }

  // 暗角（Vignette）增强沉浸感
  const vg = ctx.createRadialGradient(cw / 2, ch / 2, Math.min(cw, ch) * 0.3, cw / 2, ch / 2, Math.max(cw, ch) * 0.75);
  vg.addColorStop(0, "rgba(0,0,0,0)");
  vg.addColorStop(1, "rgba(0,0,0,0.35)");
  ctx.fillStyle = vg;
  ctx.fillRect(0, 0, cw, ch);
}

function roundRect(ctx, x, y, w, h, r) {
  ctx.beginPath();
  ctx.moveTo(x + r, y);
  ctx.arcTo(x + w, y, x + w, y + h, r);
  ctx.arcTo(x + w, y + h, x, y + h, r);
  ctx.arcTo(x, y + h, x, y, r);
  ctx.arcTo(x, y, x + w, y, r);
  ctx.closePath();
}

// ---------- 消息流 ----------
function addFeed(e) {
  if (S.filter && (e.kind || e.type) !== S.filter) return;
  if (e.kind === "order" || e.kind === "escalation") playSound("message");
  const meta = KIND_META[e.kind] || ["消息", "#7c8a98"];
  const src = e.director ? "导演部" : (S.sideNames[e.camp] || e.camp || "");
  const div = document.createElement("div");
  div.className = `fi k-${e.kind}${e.director ? " dir" : ""}`;
  div.dataset.kind = e.kind;
  const hasBody = !!(e.body || e.subject);
  // 消息类型图标
  const MSG_ICONS = { intent: "▶", order: "▼", ack: "✓", sitrep: "◈", request: "?", plan: "◇", intel: "◎", escalation: "!", briefing_pulse: "📡" };
  const mIcon = MSG_ICONS[e.kind] || "·";
  const mIconColor = meta[1] || "#7c8a98";
  div.innerHTML = `
    <div class="fi-head"><span class="ft">T${String(e.t).padStart(3, "0")}</span>
      <span class="fi-icon" style="color:${mIconColor}">${mIcon}</span>
      <span class="fcamp dir-src" ${e.camp ? `style="color:${color(e.camp)}"` : ""}>${esc(src.slice(0, 3))}</span>
      <span class="fk">${meta[0]}${e.director ? "·注入" : ""}</span>
      <span class="fr">${esc(titleOf(e.sender))} → ${esc(titleOf(e.recipient))}</span>
      ${hasBody ? '<span class="fi-toggle">▾</span>' : ""}</div>
    ${e.subject ? `<div class="fi-sub">${esc(e.subject)}</div>` : ""}
    ${e.body ? `<div class="fi-body">${esc(e.body)}</div>` : ""}`;
  // 点击展开/收起详情
  if (hasBody) {
    div.style.cursor = "pointer";
    div.addEventListener("click", () => {
      div.classList.toggle("expanded");
      const toggle = div.querySelector(".fi-toggle");
      if (toggle) toggle.textContent = div.classList.contains("expanded") ? "▴" : "▾";
    });
  }
  prependFeed(div);
}

function addSysFeed(e) {
  if (S.filter) return;
  // 触发战斗特效
  const _findUnit = (uid) => {
    if (!S.state) return null;
    const camps = S.state.camps || {};
    for (const f in camps) {
      const hit = (camps[f].units || []).find((x) => x.id === uid);
      if (hit) return hit;
    }
    return null;
  };
  if (e.type === "combat") {
    const hit = _findUnit(e.unit);
    if (hit) spawnEffect("explosion", hit.x, hit.y, { color: "#ff7a45", size: 1.2 });
    playSound("gunfire");
  } else if (e.type === "destroyed") {
    spawnEffect("bigExplosion", e.x, e.y, { color: "#ff5d5d", size: 1.5, duration: 1200 });
    playSound("destroyed");
  } else if (e.type === "fire") {
    // 炮击：从炮兵位置到目标画抛物线弹道 + 落点爆炸
    const arty = _findUnit(e.unit);
    const tx = e.x !== undefined ? e.x : (e.target_pos ? e.target_pos[0] : 0);
    const ty = e.y !== undefined ? e.y : (e.target_pos ? e.target_pos[1] : 0);
    if (arty) {
      spawnEffect("artillery", tx, ty, {
        fromX: arty.x, fromY: arty.y, color: "#ffb347", duration: 900, size: 1.3,
      });
    } else {
      spawnEffect("explosion", tx, ty, { color: "#ffb347", size: 1.3 });
    }
    playSound("artillery");
  } else if (e.type === "tactical") {
    // 战术Agent决策气泡
    const u = _findUnit(e.unit);
    if (u) {
      const stateCN = { engaging: "接战", defending: "防御", withdrawing: "后撤",
        advancing: "推进", holding: "待命", resting: "休整", reorganizing: "重组" }[e.state] || e.state;
      const kindCN = { attack: "攻击", move: "机动", hold: "固守", retreat: "撤退" }[e.kind] || e.kind;
      S.decisionBubbles.push({
        unit_id: e.unit, x: u.x, y: u.y,
        text: `自主${kindCN}·${stateCN}`,
        start: performance.now(), duration: 2500,
        side: e.camp,
      });
      if (S.decisionBubbles.length > 20) S.decisionBubbles.shift();
    }
    if (e.kind === "attack" && e.target) {
      const atk = _findUnit(e.unit);
      if (atk) {
        spawnEffect("fireline", e.target[0], e.target[1], {
          fromX: atk.x, fromY: atk.y, color: "#ffc864", duration: 500,
        });
      } else {
        spawnEffect("explosion", e.target[0], e.target[1], { color: "#ffc864", size: 0.8 });
      }
    }
  }
  let sub = "", warn = false;
  if (e.type === "combat") sub = `⚔ ${e.name || e.unit} 损失 ${e.taken}（${(e.vs || []).join("、")}）`;
  else if (e.type === "fire") sub = `▲ ${e.name || e.unit} 炮击 ${e.target_name || ""}，损失 ${e.dmg}`;
  else if (e.type === "destroyed") { sub = `✝ ${e.name || e.unit} 全损`; warn = true; }
  else if (e.type === "intel") sub = `◎ 侦察发现 ${e.n} 个目标`;
  else if (e.type === "reached") sub = `➤ ${e.name || e.unit} 到达 (${e.x},${e.y})`;
  else if (e.type === "isolation_blocked") { sub = `⛔ 隔离拦截：${e.reason || e.detail || ""}`; warn = true; }
  else if (e.type === "msg_lost") { sub = `✉ 电文中断：${titleOf(e.sender)} → ${titleOf(e.recipient)}《${e.subject || ""}》`; warn = true; }
  else if (e.type === "weather") sub = `☁ 天气转为：${WEATHER_CN[e.weather] || e.weather}`;
  else if (e.type === "reinforce") sub = `＋ 增援入场：${e.name}（${e.camp ? (S.sideNames[e.camp] || e.camp) : ""}）`;
  else if (e.type === "depot") sub = `⚑ 补给站易手 (${e.x},${e.y})：${e.from} → ${e.side}`;
  else if (e.type === "objective") sub = `◈ 夺占目标：${e.name}（${e.camp ? (S.sideNames[e.camp] || e.camp) : ""}方）`;
  else if (e.type === "air") sub = `✈ 空军遮断：${e.name || e.unit} 损失 ${e.dmg}`;
  else if (e.type === "llm_fallback") sub = `⚠ LLM 降级规则：${String(e.error || "").slice(0, 60)}`;
  else if (e.type === "action") sub = `→ ${e.unit} ${e.kind}${e.target ? " (" + e.target.join(",") + ")" : ""}`;
  else if (e.type === "tactical") {
    const sn = { engaging: "接战", defending: "防御", withdrawing: "后撤", advancing: "推进", holding: "待命" }[e.state] || e.state;
    sub = `◆ ${e.name || e.unit} 自主${e.kind}${e.target ? " (" + e.target.join(",") + ")" : ""} [${sn}]`;
  }
  else if (e.type === "tactical_rejected") sub = `◆ ${e.unit} 自主行动被拒 ${e.kind}`;
  else if (e.type === "dirscript") sub = `◈ 导演剧本触发：${(S.sideNames[e.camp] || e.camp)} → ${titleOf(e.recipient)}《${e.subject || ""}》`;
  else if (e.type === "dirscript_failed") { sub = `⚠ 剧本注入失败：${(S.sideNames[e.camp] || e.camp)} → ${titleOf(e.recipient)}`; warn = true; }
  if (!sub) return;
  const isTactical = e.type === "tactical" || e.type === "tactical_rejected";
  const div = document.createElement("div");
  div.className = `fi sys${warn ? " warn" : e.type === "dirscript" ? " dir" : ""}${isTactical ? " tactical" : ""}`;
  // 图标映射
  const ICONS = { combat: "⚔", fire: "▲", destroyed: "✝", intel: "◎", reached: "➤",
    isolation_blocked: "⛔", msg_lost: "✉", weather: "☁", reinforce: "＋", depot: "⚑",
    objective: "◈", air: "✈", llm_fallback: "⚠", action: "→", tactical: "◆", tactical_rejected: "◇",
    dirscript: "◉", dirscript_failed: "⚠" };
  const ic = ICONS[e.type] || "·";
  const icColor = { combat: "#e5484d", fire: "#ff9a3c", destroyed: "#ff5d5d", intel: "#4c8dff",
    weather: "#7c8a98", reinforce: "#46c98d", depot: "#dfb26a", objective: "#dfb26a",
    air: "#c58af9", llm_fallback: "#ff7a45", tactical: "#46c98d", tactical_rejected: "#ff7a45",
    dirscript: "#dfb26a", dirscript_failed: "#ff7a45", isolation_blocked: "#ff7a45",
    msg_lost: "#7c8a98", reached: "#7c8a98", action: "#7c8a98" }[e.type] || "#7c8a98";
  div.innerHTML = `<div class="fi-head"><span class="ft">T${String(e.t).padStart(3, "0")}</span>
    <span class="fi-icon" style="color:${icColor}">${ic}</span>
    <span class="fcamp">${e.camp ? esc((S.sideNames[e.camp] || e.camp).slice(0, 2)) : ""}</span>
    <span class="fr mono">${esc(sub)}</span></div>`;
  prependFeed(div);
}

function addBriefingPulse(e) {
  const payload = e.payload || {};
  const div = document.createElement("div");
  div.className = "fi k-briefing_pulse briefing-pulse";
  div.dataset.kind = "briefing_pulse";
  const lines = [];
  if (payload.weather_name) lines.push(`天气：<span class="weather-val">${esc(payload.weather_name)}</span>`);
  if (payload.objectives && payload.objectives.length) {
    const objs = payload.objectives.map((o) => {
      const c = o.controller === "red" ? "red" : o.controller === "blue" ? "blue" : "neutral";
      return `<span class="obj-dot obj-${c}" title="${esc(o.name)}">${esc(o.name.slice(0, 6))}</span>`;
    }).join("");
    lines.push(`目标：${objs}`);
  }
  if (payload.unit_counts) {
    const counts = Object.entries(payload.unit_counts).map(([k, v]) => `${esc(k)}: ${v}`).join(" · ");
    lines.push(`兵力：${counts}`);
  }
  div.innerHTML = `<div class="fi-head"><span class="ft">T${String(e.t).padStart(3, "0")}</span><span class="fk">📡 指挥摘要</span></div><div class="fi-body briefing-pulse-body">${lines.join("<br>")}</div>`;
  prependFeed(div);
}

function updateCampaignBar(e) {
  const payload = e.payload || {};
  const tickEl = els["cb-tick"];
  if (tickEl) tickEl.textContent = String(e.t).padStart(3, "0");
  const weatherEl = els["cb-weather"];
  if (weatherEl && payload.weather_name) weatherEl.textContent = payload.weather_name;
  const redCount = els["cb-red-count"];
  const blueCount = els["cb-blue-count"];
  if (payload.unit_counts) {
    if (redCount) redCount.textContent = payload.unit_counts.red || 0;
    if (blueCount) blueCount.textContent = payload.unit_counts.blue || 0;
  }
}

function prependFeed(div) {
  els.feed.prepend(div);
  while (els.feed.children.length > 300) els.feed.lastChild.remove();
}

function applyFeedFilter() {
  for (const el of els.feed.children) {
    const k = el.dataset.kind;
    el.style.display = (!S.filter || k === S.filter) ? "" : "none";
  }
}

// ---------- 导演部讲评（复盘指标 + 曲线） ----------
async function fetchMetrics() {
  try {
    const [m, h] = await Promise.all([
      fetch("/api/metrics").then((r) => r.json()),
      fetch("/api/metrics/history").then((r) => r.json()),
    ]);
    renderMetrics(m, h);
  } catch (e) { /* ignore */ }
}

function renderMetrics(m, h) {
  const name = S.sideNames || {};
  const card = (side) => {
    const c = (m.camps || {})[side] || {};
    const pct = c.units_total ? Math.round((c.strength || 0) / (c.units_total * 100) * 100) : 0;
    const pctStr = (v) => (v == null ? "—" : Math.round(v * 100) + "%");
    const show = (v, suff = "") => (v == null ? "—" : v + suff);
    return `
      <div class="mcard" style="--mc:${color(side)}">
        <div class="mc-head">${name[side] || side}</div>
        <div class="mc-row big">剩余兵力<b>${c.strength ?? 0}</b>
          <span class="dim">/ ${c.units_total * 100 || "?"} · 存活 ${c.units_alive ?? 0}/${c.units_total ?? 0}</span></div>
        <div class="bar"><i style="width:${pct}%"></i></div>
        <div class="mc-grid">
          <div>命令下行<b>${show(c.orders, "")}</b></div>
          <div>确认率<b>${pctStr(c.ack_rate)}</b></div>
          <div>确认延迟<b>${show(c.ack_latency, "拍")}</b></div>
          <div>态势报告<b>${show(c.sitreps)}</b></div>
          <div>请示<b>${show(c.requests)}</b></div>
          <div>告警<b>${show(c.escalations)}</b></div>
          <div>情报<b>${show(c.intel)}</b></div>
          <div>决策次数<b>${show(c.decisions)}</b></div>
          <div>电文中断<b>${show(c.msg_lost)}</b></div>
          <div>隔离拦截<b>${show(c.isolation_blocked)}</b></div>
          <div>LLM降级<b>${show(c.llm_fallback)}</b></div>
        </div>
      </div>`;
  };
  const score = m.score || {};
  const objs = (m.objectives || []).map((o) => {
    const who = o.controller ? (S.sideNames[o.controller] || o.controller) : "无主";
    return `<span class="obj" style="color:${o.controller ? color(o.controller) : "var(--dim)"};border-color:${o.controller ? hexA(color(o.controller), .5) : "var(--border-hi)"}">${o.name}·${who}</span>`;
  }).join("");
  els.metrics.innerHTML =
    `<div class="mnote">T${String(m.tick).padStart(3, "0")} · ${esc(m.scenario || "")} · 每 3 秒刷新</div>` +
    `<div class="objs">${objs}</div>` +
    Object.keys(m.camps || {}).map(card).join("") +
    `<div class="mcharts">
       ${chartCanvas("mc-strength", "战力曲线（存活单位强度）")}
       ${chartCanvas("mc-score", "得分曲线（目标控制）")}
       ${chartCanvas("mc-objectives", "目标控制时序")}
     </div>`;
  renderCharts(h);
}

// ---- 讲评曲线（Canvas 绘制） ----
function chartCanvas(id, label) {
  return `<div class="mchart"><div class="mc-title">${label}</div><canvas id="${id}" class="mcanvas"></canvas></div>`;
}

function sizeCanvas(cv) {
  const dpr = window.devicePixelRatio || 1;
  const w = cv.clientWidth || 320;
  const h = cv.clientHeight || 108;
  cv.width = Math.max(1, Math.round(w * dpr));
  cv.height = Math.max(1, Math.round(h * dpr));
  const ctx = cv.getContext("2d");
  ctx.setTransform(dpr, 0, 0, dpr, 0, 0);
  return { ctx, w, h };
}

function chartBase(cv, maxY) {
  const { ctx, w, h } = sizeCanvas(cv);
  ctx.clearRect(0, 0, w, h);
  ctx.strokeStyle = "rgba(148,178,210,.10)";
  ctx.lineWidth = 1;
  const rows = 3;
  for (let i = 0; i <= rows; i++) {
    const y = 6 + (h - 16) * (i / rows);
    ctx.beginPath(); ctx.moveTo(30, y); ctx.lineTo(w - 4, y); ctx.stroke();
  }
  ctx.font = "9px ui-monospace, SFMono-Regular, Consolas, monospace";
  ctx.fillStyle = "rgba(148,178,210,.5)";
  for (let i = 0; i <= rows; i++) {
    const y = 6 + (h - 16) * (i / rows);
    const v = Math.round(maxY * (1 - i / rows));
    ctx.textAlign = "left";
    ctx.fillText(String(v), 2, y + 3);
  }
  return { ctx, w, h };
}

function drawMetricLines(cv, samples, getY, sides, label) {
  const maxY = Math.max(4, ...samples.flatMap((s) => sides.map((k) => getY(s, k) || 0)));
  const { ctx, w, h } = chartBase(cv, maxY);
  const n = samples.length;
  const X = (i) => 30 + (w - 36) * (n > 1 ? i / (n - 1) : 0.5);
  const Y = (v) => 6 + (h - 16) * (1 - (v || 0) / maxY);
  ctx.font = "10px 'Noto Sans SC', 'PingFang SC', sans-serif";
  ctx.fillStyle = "rgba(210,190,140,.8)";
  ctx.textAlign = "left";
  ctx.fillText(label, 30, 5);
  sides.forEach((k, idx) => {
    const col = color(k);
    const pts = samples.map((s, i) => [X(i), Y(getY(s, k) || 0)]);
    ctx.strokeStyle = col;
    ctx.lineWidth = 1.7;
    ctx.beginPath();
    pts.forEach((p, i) => (i ? ctx.lineTo(p[0], p[1]) : ctx.moveTo(p[0], p[1])));
    ctx.stroke();
    ctx.globalAlpha = 0.10;
    ctx.fillStyle = col;
    ctx.beginPath();
    ctx.moveTo(pts[0][0], h - 10);
    pts.forEach((p) => ctx.lineTo(p[0], p[1]));
    ctx.lineTo(pts[n - 1][0], h - 10);
    ctx.closePath();
    ctx.fill();
    ctx.globalAlpha = 1;
    const lx = w - 6, ly = 6 + idx * 12;
    ctx.fillStyle = col;
    ctx.beginPath(); ctx.arc(lx - 38, ly + 1, 2.5, 0, Math.PI * 2); ctx.fill();
    ctx.font = "9px 'Noto Sans SC', sans-serif";
    ctx.textAlign = "right";
    ctx.fillStyle = "rgba(210,215,220,.7)";
    ctx.fillText(S.sideNames[k] || k, lx, ly + 4);
    ctx.textAlign = "left";
  });
  ctx.fillStyle = "rgba(148,178,210,.5)";
  ctx.font = "9px ui-monospace, Consolas, monospace";
  const step = Math.max(1, Math.floor(n / 4));
  for (let i = 0; i < n; i += step) {
    ctx.textAlign = "center";
    ctx.fillText("T" + samples[i].tick, X(i), h - 1);
  }
}

function drawObjectiveBands(cv, samples) {
  const names = [];
  samples.forEach((s) => (s.objectives || []).forEach((o) => {
    if (o && o.name && !names.includes(o.name)) names.push(o.name);
  }));
  if (!names.length) return;
  const { ctx, w, h } = sizeCanvas(cv);
  ctx.clearRect(0, 0, w, h);
  const n = samples.length;
  const rowH = Math.max(14, Math.min(20, (h - 8) / names.length));
  const x0 = 88;
  ctx.font = "9px 'Noto Sans SC', sans-serif";
  names.forEach((nm, ri) => {
    const y = 4 + ri * rowH;
    ctx.fillStyle = "rgba(210,190,140,.7)";
    ctx.textAlign = "left";
    ctx.fillText(nm.length > 7 ? nm.slice(0, 7) + "…" : nm, 2, y + rowH - 6);
    const segs = [];
    let lastCtrl = null, start = 0;
    samples.forEach((s, i) => {
      const o = (s.objectives || []).find((x) => x && x.name === nm);
      const ctrl = o ? o.controller : null;
      if (i === 0) { lastCtrl = ctrl; return; }
      if (ctrl !== lastCtrl) { segs.push([start, i, lastCtrl]); lastCtrl = ctrl; start = i; }
    });
    segs.push([start, n, lastCtrl]);
    segs.forEach(([a, b, ctrl]) => {
      const x1 = x0 + (w - x0 - 4) * (a / n);
      const x2 = x0 + (w - x0 - 4) * (b / n);
      ctx.fillStyle = ctrl ? hexA(color(ctrl), .5) : "rgba(120,130,140,.14)";
      ctx.fillRect(x1, y + 2, Math.max(1, x2 - x1), rowH - 8);
      ctx.strokeStyle = "rgba(0,0,0,.25)";
      ctx.lineWidth = .5;
      ctx.strokeRect(x1, y + 2, Math.max(1, x2 - x1), rowH - 8);
    });
  });
}

function renderCharts(h) {
  if (!h || !h.series || !h.series.length) return;
  const samples = h.series;
  const sides = Object.keys(samples[0].strength || {});
  const cv1 = document.getElementById("mc-strength");
  if (cv1) drawMetricLines(cv1, samples, (s, k) => s.strength[k], sides, "存活单位强度");
  const cv2 = document.getElementById("mc-score");
  if (cv2) drawMetricLines(cv2, samples, (s, k) => s.score[k], sides, "目标控制得分");
  const cv3 = document.getElementById("mc-objectives");
  if (cv3) drawObjectiveBands(cv3, samples);
}

async function exportReport() {
  try {
    const r = await (await fetch("/api/debug/report")).json();
    if (!r.ok) return;
    const blob = new Blob([r.markdown || ""], { type: "text/markdown;charset=utf-8" });
    const a = document.createElement("a");
    a.href = URL.createObjectURL(blob);
    a.download = r.filename || "复盘报告.md";
    document.body.appendChild(a);
    a.click();
    setTimeout(() => { URL.revokeObjectURL(a.href); a.remove(); }, 300);
  } catch (e) {
    console.error("导出报告失败:", e);
  }
}

// ---------- SSE 与控制 ----------
function connectSSE() {
  const es = new EventSource("/api/stream");
  es.onmessage = (ev) => {
    let e;
    try { e = JSON.parse(ev.data); } catch { return; }
    if (e.type === "reset") { els.feed.innerHTML = ""; S.epoch = e.epoch; fetchState(); return; }
    if (e.type === "msg") { addFeed(e); animateMsg(e); }
    else if (e.type === "briefing_pulse") { addBriefingPulse(e); updateCampaignBar(e); }
    else addSysFeed(e);
    els.tick.textContent = String(e.t).padStart(3, "0");
  };
}

async function control(body, resetUi = false) {
  try {
    await fetch("/api/control", {
      method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify(body),
    });
  } catch (e) { /* ignore */ }
  if (resetUi) els.feed.innerHTML = "";
  fetchState();
}

async function sendIntent() {
  const text = els["intent-text"].value.trim();
  if (!text) return;
  try {
    await fetch("/api/intent", {
      method: "POST", headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ side: S.camp, text }),
    });
    els["intent-text"].value = "";
  } catch (e) { /* ignore */ }
}

document.addEventListener("DOMContentLoaded", boot);

// ============================================================
// 智能体调试中心
// ============================================================
function debounce(fn, ms) {
  let t = null;
  return (...a) => { clearTimeout(t); t = setTimeout(() => fn(...a), ms); };
}

function initDebugView() {
  if (!S.dbgSides) loadDebugSides();
  loadDebugData();
  // 推演中每 2 秒静默刷新（保持实时），离开视图时自然停摆
  clearInterval(S.dbgTimer);
  S.dbgTimer = setInterval(() => { if (S.studioView === "debug") loadDebugData(true); }, 2000);
}

async function loadDebugSides() {
  S.dbgSides = {};
  try {
    const r = await (await fetch("/api/roles")).json();
    for (const [id, v] of Object.entries(r.sides || {})) S.dbgSides[id] = v.name || id;
  } catch (e) { /* ignore */ }
  els["debug-side"].innerHTML =
    `<option value="">全部阵营</option>` +
    Object.entries(S.dbgSides).map(([k, n]) =>
      `<option value="${esc(k)}">${esc(n)}</option>`).join("");
}

async function loadDebugData(silent = false) {
  let agents = {};
  try { agents = await (await fetch("/api/debug/agents")).json(); }
  catch (e) { if (!silent) els["agent-list-items"].innerHTML = `<div class="dbg-note">服务未就绪</div>`; return; }
  const q = (els["debug-search"].value || "").toLowerCase();
  const side = els["debug-side"].value;
  const list = Object.values(agents).filter((a) =>
    (!side || a.side === side) &&
    (q === "" || (a.title || "").toLowerCase().includes(q) ||
     (a.pos || "").toLowerCase().includes(q) ||
     (a.archetype || "").toLowerCase().includes(q)));
  els["debug-count"].textContent = `共 ${Object.keys(agents).length} 条子智能体`;
  els["agent-list-items"].innerHTML = list.map((a) => {
    const on = a.wake;
    const cls = `agent-list-item${S.dbgAgent === a.pos ? " sel" : ""}${on ? " on" : ""}`;
    return `<button class="${cls}" data-pos="${esc(a.pos)}">
      <span class="ali-dot" style="background:${color(a.side)}"></span>
      <span class="ali-main">
        <span class="ali-title">${esc(a.title)}</span>
        <span class="ali-sub">${esc(ARCTYPE_CN[a.archetype] || a.archetype)} · ${esc(S.dbgSides[a.side] || a.side)}</span>
      </span>
      <span class="ali-state">${on ? "活跃" : "待机"}</span>
    </button>`;
  }).join("");
  document.querySelectorAll(".agent-list-item").forEach((b) =>
    b.addEventListener("click", () => selectDebugAgent(b.dataset.pos)));
  // 若当前选中项被筛选掉，自动选中列表第一项，保证列表与详情始终一致
  const visible = Object.values(agents).filter((a) =>
    (!side || a.side === side) &&
    (q === "" || (a.title || "").toLowerCase().includes(q) ||
     (a.pos || "").toLowerCase().includes(q) ||
     (a.archetype || "").toLowerCase().includes(q)));
  const stillVisible = S.dbgAgent && visible.some((a) => a.pos === S.dbgAgent);
  if (!stillVisible) {
    if (visible.length) {
      S.dbgAgent = visible[0].pos;
      refreshDebugDetail(visible[0]);
    } else if (S.dbgAgent) {
      // 列表被筛空：收起详情，回到空态
      S.dbgAgent = null;
      els["dbg-detail"].classList.add("hidden");
      els["dbg-empty"].classList.remove("hidden");
      els["dbg-empty"].textContent = "没有匹配的子智能体";
    }
  } else if (S.dbgAgent && agents[S.dbgAgent]) {
    refreshDebugDetail(agents[S.dbgAgent]);
  }
}

function selectDebugAgent(pos) {
  S.dbgAgent = pos;
  loadDebugData(true);
}

async function refreshDebugDetail(a) {
  els["dbg-empty"].classList.add("hidden");
  els["dbg-detail"].classList.remove("hidden");
  els["dbg-title"].textContent = a.title;
  els["dbg-meta"].innerHTML = `
    <span>ID: ${esc(a.pos)}</span>
    <span>阵营: ${esc(S.dbgSides[a.side] || a.side)}</span>
    <span>类型: ${esc(ARCTYPE_CN[a.archetype] || a.archetype)}</span>
    <span>策略: ${a.policy === "llm" ? "LLM" : "规则"}</span>
    <span>最近活跃: T${a.last_active ?? "—"}</span>`;
  els["dbg-live"].classList.toggle("cold", !a.wake);
  els["dbg-live"].textContent = a.wake ? "● 活跃" : "○ 待机";
  const activeTab = document.querySelector(".dbg-tab.active");
  renderDebugTab(a.pos, activeTab ? activeTab.dataset.tab : "state");
}

async function renderDebugTab(pos, tab) {
  if (!pos) return;
  const content = els["dbg-content"];
  content.innerHTML = `<div class="dbg-loading">加载中…</div>`;
  let agents = {};
  try { agents = await (await fetch(`/api/debug/agents?pos_id=${encodeURIComponent(pos)}`)).json(); }
  catch (e) { content.innerHTML = `<div class="dbg-note">加载失败</div>`; return; }
  const a = agents[pos];
  if (!a) { content.innerHTML = `<div class="dbg-note">无数据</div>`; return; }

  if (tab === "state") {
    content.innerHTML = `
      <div class="dbg-grid">
        <div class="dbg-cell"><div class="dc-k">信箱未读</div><div class="dc-v">${a.inbox.length}</div></div>
        <div class="dbg-cell"><div class="dc-k">进行中任务</div><div class="dc-v">${(a.tasks || []).filter((t) => t.status !== "done").length}</div></div>
        <div class="dbg-cell"><div class="dc-k">记忆条目</div><div class="dc-v">${(a.memory || []).length}</div></div>
        <div class="dbg-cell"><div class="dc-k">局部状态</div><div class="dc-v">${Object.keys(a.state || {}).length}</div></div>
      </div>
      <div class="dbg-sec">最后思考</div>
      <pre class="dbg-pre">${esc(a.last_thought || "（尚无决策输出）")}</pre>
      <div class="dbg-sec">局部状态</div>
      <pre class="dbg-pre">${esc(JSON.stringify(a.state || {}, null, 2))}</pre>`;
  } else if (tab === "inbox") {
    content.innerHTML = (a.inbox && a.inbox.length)
      ? a.inbox.map((m) => `
        <div class="dbg-msg">
          <div class="dm-head"><span class="dm-kind">${esc(KIND_META[m.kind] ? KIND_META[m.kind][0] : m.kind)}</span>
            <span class="dm-from">来自 ${esc(m.sender)}</span></div>
          <div class="dm-subject">${esc(m.subject || "")}</div>
          <div class="dm-body">${esc(m.body || "")}</div>
        </div>`).join("")
      : `<div class="dbg-empty2">信箱为空</div>`;
  } else if (tab === "tasks") {
    content.innerHTML = (a.tasks && a.tasks.length)
      ? a.tasks.map((t) => `
        <div class="dbg-task ${t.status === "done" ? "done" : ""}">
          <span class="dt-status">${t.status === "done" ? "✓ 完成" : "… 进行"}</span>
          <span class="dt-desc">${esc(t.desc)}</span>
          <span class="dt-created">T${t.created}</span>
        </div>`).join("")
      : `<div class="dbg-empty2">暂无任务</div>`;
  } else if (tab === "memory") {
    content.innerHTML = (a.memory && a.memory.length)
      ? `<ul class="dbg-mem">${a.memory.map((m) => `<li>${esc(m)}</li>`).join("")}</ul>`
      : `<div class="dbg-empty2">记忆为空（LLM 模式可在设置中开启记忆）</div>`;
  } else if (tab === "decisions") {
    try {
      const r = await (await fetch(`/api/debug/traces?pos=${encodeURIComponent(pos)}&limit=60`)).json();
      const tr = (r.traces || []).slice().reverse();
      content.innerHTML = tr.length
        ? tr.map((t) => `
          <div class="dbg-decision${t.fallback ? " fb" : ""}${t.error ? " err" : ""}">
            <div class="dd-head">
              <span class="dd-tick">T${t.tick}</span>
              <span class="dd-policy">${t.fallback ? "规则降级" : (t.policy === "llm" ? "LLM" : "规则")}</span>
              ${t.structured ? `<span class="dd-policy str">结构化输出</span>` : ""}
              <span class="dd-view">视野: ${t.view.own_units}单位 · ${t.view.intel}情报 · 子节点${t.view.children}</span>
            </div>
            <div class="dd-thought">${esc(t.thoughts || "")}</div>
            ${t.error ? `<div class="dd-err">⚠ ${esc(t.error)}</div>` : ""}
            ${t.actions.length ? `<div class="dd-actions">动作: ${t.actions.map((x) => `${x.kind}→${esc(x.unit)}${x.target ? "(" + x.target.join(",") + ")" : ""}`).join(" · ")}</div>` : ""}
            ${t.messages.length ? `<div class="dd-actions">发信: ${t.messages.map((m) => `${esc(m.kind)}→${esc(m.to)}`).join(" · ")}</div>` : ""}
          </div>`).join("")
        : `<div class="dbg-empty2">尚无决策记录（启动推演后出现）</div>`;
    } catch (e) { content.innerHTML = `<div class="dbg-note">加载失败</div>`; }
  } else if (tab === "llm") {
    try {
      const r = await (await fetch(`/api/debug/traces?pos=${encodeURIComponent(pos)}&limit=30`)).json();
      const tr = (r.traces || []).filter((t) => t.llm && t.llm.length).slice(0, 5).reverse();
      content.innerHTML = tr.length
        ? tr.map((t) => `
          <div class="dbg-llm">
            <div class="llm-head">T${t.tick} · ${t.llm.length} 次调用 · 预算 ${t.budget.used}/${t.budget.max}</div>
            ${t.llm.map((c, i) => `
              <div class="llm-ex">
                <div class="le-role sys">系统</div><div class="le-body">${esc((c.system || "").slice(0, 400))}</div>
                <div class="le-role user">用户</div><div class="le-body">${esc((c.user || "").slice(0, 400))}</div>
                <div class="le-role ${c.ok ? "resp" : "err"}">${c.ok ? `响应 ${c.latency_ms}ms` : "失败"}</div>
                <div class="le-body">${esc((c.ok ? c.response : ("错误: " + (c.error || ""))).slice(0, 800))}</div>
              </div>`).join("")}
          </div>`).join("")
        : `<div class="dbg-empty2">当前策略为规则模式，无 LLM 调用记录（在设置中配置 LLM 并选「智能决策」后出现）</div>`;
    } catch (e) { content.innerHTML = `<div class="dbg-note">加载失败</div>`; }
  }
}
// 全局错误捕获（调试用）
window.addEventListener("error", (e) => {
  document.title = "ERR: " + e.message.slice(0, 80);
  console.error("GLOBAL ERROR:", e.message, e.filename, e.lineno);
});
// 启动
boot();
// URL参数 ?deck=1 自动进入指挥台（用于调试/直接链接）
if (new URLSearchParams(location.search).get("deck") === "1") {
  setTimeout(() => {
    const studio = document.getElementById("studio");
    const deck = document.getElementById("deck");
    if (studio && deck) { studio.classList.add("hidden"); deck.classList.remove("hidden"); }
  }, 500);
}
