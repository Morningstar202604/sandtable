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
  cam: { scale: 1, panX: 0, panY: 0, drag: null, view: null },
  directOpen: false,
  // 作业区状态（路口式入口 + 独立工作台）
  studioView: "home",         // home / scenario / roster / director
  scenarios: [], roles: {}, scenSelected: null,
  roleEdits: {}, intentEdits: {}, collapsed: {},   // 兵力编成：职位 -> 是否折叠（true=折叠）
  script: [],                 // 导演部导调剧本（本地队列）
  llm: { available: false, model: "" },
};

const SVGNS = "http://www.w3.org/2000/svg";
const $ = (id) => document.getElementById(id);
const els = {};

const KIND_META = {
  intent: ["意图", "#e2a336"], order: ["命令", "#e5484d"], ack: ["确认", "#7c8a98"],
  sitrep: ["报告", "#46c98d"], request: ["请示", "#c58af9"], plan: ["方案", "#e2a336"],
  intel: ["情报", "#4c8dff"], escalation: ["告警", "#ff7a45"],
};

const TERR_COLOR = { ".": "#121920", "f": "#152219", "h": "#1b2114", "~": "#0e2033", "B": "#3a3123", "C": "#242b33", "m": "#14262a", "r": "#26200f" };
const WEATHER_CN = { clear: "晴", overcast: "阴", rain: "雨", storm: "风暴" };
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
   "dbg-tabs", "dbg-content", "debug-export",
  ].forEach((k) => (els[k] = $(k)));
  document.querySelectorAll(".vs").forEach((b) => b.addEventListener("click", () => {
    document.querySelectorAll(".vs").forEach((x) => x.classList.remove("active"));
    b.classList.add("active");
    S.view = b.dataset.view;
    drawMap();
  }));
  els["feed-filter"].addEventListener("change", (e) => { S.filter = e.target.value; applyFeedFilter(); });
  document.querySelectorAll(".rtab").forEach((t) => t.addEventListener("click", () => {
    document.querySelectorAll(".rtab").forEach((x) => x.classList.remove("active"));
    t.classList.add("active");
    S.metricsTab = t.dataset.rtab === "metrics";
    els.feed.classList.toggle("hidden", S.metricsTab);
    els.metrics.classList.toggle("hidden", !S.metricsTab);
    if (S.metricsTab) fetchMetrics();
  }));
  setInterval(() => { if (S.metricsTab) fetchMetrics(); }, 3000);

  els["btn-start"].onclick = () => control({ action: "start" });
  els["btn-pause"].onclick = () => control({ action: "pause" });
  els["btn-step"].onclick = () => control({ action: "step" });
  els["btn-reset"].onclick = () => control({ action: "reset" }, true);
  els["speed"].onchange = (e) => control({ action: "speed", speed: parseFloat(e.target.value) });
  els["btn-intent"].onclick = sendIntent;
  els["intent-text"].addEventListener("keydown", (e) => {
    if (e.key === "Enter" && (e.ctrlKey || e.metaKey)) sendIntent();
  });

  new ResizeObserver(drawMap).observe(els["map"].parentElement);
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

// 从路口启动：使用当前已保存的引擎配置，直接进入指挥台
async function launchExercise() {
  try {
    const s = await (await fetch("/api/settings")).json();
    const scenario = S.scenSelected || s.scenario;
    if (!scenario) {
      els["h-home-note"].textContent = "请先到「想定库」选定一个想定，或让 AI 生成。";
      return;
    }
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
    els.studio.classList.add("hidden");
    els.deck.classList.remove("hidden");
    els.feed.innerHTML = "";
    fetchState();
  } catch (e) {
    els["h-home-note"].textContent = "启动失败，请重试：" + String(e);
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
  cv.addEventListener("wheel", (e) => {
    e.preventDefault();
    const r = cv.getBoundingClientRect();
    zoomAt(e.clientX - r.left, e.clientY - r.top, e.deltaY < 0 ? 1.15 : 1 / 1.15);
  }, { passive: false });
  cv.addEventListener("mousedown", (e) => {
    if (S.cam.scale <= 1) return;
    S.cam.drag = { x: e.clientX, y: e.clientY, px: S.cam.panX, py: S.cam.panY };
    cv.classList.add("dragging");
  });
  window.addEventListener("mousemove", (e) => {
    if (!S.cam.drag) return;
    S.cam.panX = S.cam.drag.px + (e.clientX - S.cam.drag.x);
    S.cam.panY = S.cam.drag.py + (e.clientY - S.cam.drag.y);
    drawMap();
  });
  window.addEventListener("mouseup", () => { S.cam.drag = null; cv.classList.remove("dragging"); });
  els["zoom-in"].onclick = () => { const r = cv.getBoundingClientRect(); zoomAt(r.width / 2, r.height / 2, 1.3); };
  els["zoom-out"].onclick = () => { const r = cv.getBoundingClientRect(); zoomAt(r.width / 2, r.height / 2, 1 / 1.3); };
  els["zoom-reset"].onclick = () => { S.cam.scale = 1; S.cam.panX = 0; S.cam.panY = 0; drawMap(); };
}

function zoomAt(mx, my, factor) {
  const st = S.state, v = S.cam.view;
  if (!st || !v) return;
  const wx = (mx - v.ox) / v.cs, wy = (my - v.oy) / v.cs;
  S.cam.scale = Math.max(1, Math.min(6, S.cam.scale * factor));
  const cw = v.cw, ch = v.ch;
  const cs2 = v.base * S.cam.scale;
  const cW = cs2 * st.w, cH = cs2 * st.h;
  let ox = mx - wx * cs2, oy = my - wy * cs2;
  ox = (cW <= cw) ? (cw - cW) / 2 : Math.max(cw - cW, Math.min(0, ox));
  oy = (cH <= ch) ? (ch - cH) / 2 : Math.max(ch - cH, Math.min(0, oy));
  S.cam.panX = ox - (cw - cW) / 2;
  S.cam.panY = oy - (ch - cH) / 2;
  drawMap();
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
    S.factions = Object.keys(st.camps || {});
    buildFactionUI();
    buildLookup(st);
    els.tick.textContent = String(st.tick).padStart(3, "0");
    els.scenario.textContent = goodsWeather(st);
    els["deck-scenario"].textContent = st.scenario || "";
    els["run-pulse"].classList.toggle("on", st.running);
    const badge = els["mode-badge"];
    badge.textContent = st.llm.available ? `LLM · ${st.llm.model}` : `规则模式 · seed ${st.seed}`;
    badge.classList.toggle("llm", st.llm.available);
    renderOrg();
    renderLegend();
    drawMap();
  } catch (e) { /* 服务未就绪时静默重试 */ }
}

function goodsWeather(st) {
  return st.weather ? WEATHER_CN[st.weather] || st.weather : "";
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
    els["view-switch"].querySelectorAll(".vs").forEach((x) => x.classList.remove("active"));
    b.classList.add("active");
    S.view = b.dataset.view;
    drawMap();
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
}

function animateMsg(e) {
  if (e.camp !== S.camp) return;
  const toId = e.recipient.startsWith("unit:") ? S.unitOwner[e.recipient.slice(5)] : e.recipient;
  const el = els["org-tree"].querySelector(`.onode[data-pos="${toId}"] .ocard`);
  if (el) { el.classList.add("flash"); setTimeout(() => el.classList.remove("flash"), 900); }
}

// ---------- 态势图 ----------
function drawMap() {
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
  ctx.clearRect(0, 0, cw, ch);

  const baseCs = Math.min(cw / st.w, ch / st.h);
  const zoom = S.cam.scale;
  const cs = baseCs * zoom;
  const cW = cs * st.w, cH = cs * st.h;
  let ox = (cw - cW) / 2 + S.cam.panX, oy = (ch - cH) / 2 + S.cam.panY;
  if (cW <= cw) ox = (cw - cW) / 2; else ox = Math.max(cw - cW, Math.min(0, ox));
  if (cH <= ch) oy = (ch - cH) / 2; else oy = Math.max(ch - cH, Math.min(0, oy));
  S.cam.view = { cs, ox, oy, base: baseCs, cw, ch };
  els["zoom-label"].textContent = Math.round(zoom * 100) + "%";

  for (let y = 0; y < st.h; y++) {
    for (let x = 0; x < st.w; x++) {
      ctx.fillStyle = TERR_COLOR[st.map[y][x]] || TERR_COLOR["."];
      ctx.fillRect(ox + x * cs, oy + y * cs, cs + 0.5, cs + 0.5);
    }
  }
  ctx.strokeStyle = "rgba(255,255,255,0.03)";
  ctx.lineWidth = 1;
  for (let x = 0; x <= st.w; x++) {
    ctx.beginPath(); ctx.moveTo(ox + x * cs, oy); ctx.lineTo(ox + x * cs, oy + st.h * cs); ctx.stroke();
  }
  for (let y = 0; y <= st.h; y++) {
    ctx.beginPath(); ctx.moveTo(ox, oy + y * cs); ctx.lineTo(ox + st.w * cs, oy + y * cs); ctx.stroke();
  }

  ctx.textAlign = "center"; ctx.textBaseline = "middle";
  ctx.font = `${Math.max(10, Math.floor(cs * 0.4))}px sans-serif`;
  for (const d of (st.depots || [])) {
    ctx.fillStyle = (S.factions.includes(d.owner) && color(d.owner))
      ? hexA(color(d.owner), .7) : "rgba(255,255,255,.3)";
    ctx.fillText("◆", ox + d.x * cs + cs / 2, oy + d.y * cs + cs / 2);
  }

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
  for (const u of units) {
    const px = ox + u.x * cs, py = oy + u.y * cs;
    const bw = cs * 0.74, bh = cs * 0.56;
    const bx = px + (cs - bw) / 2, by = py + (cs - bh) / 2 - cs * 0.04;
    ctx.font = `${Math.max(9, Math.floor(cs * 0.38))}px sans-serif`;
    if (u.ghost) {
      ctx.globalAlpha = u.age > 8 ? 0.35 : 0.7;
      ctx.setLineDash([3, 3]);
      ctx.strokeStyle = color(u.side); ctx.lineWidth = 1.2;
      ctx.strokeRect(bx, by, bw, bh);
      ctx.setLineDash([]);
      ctx.fillStyle = color(u.side);
      ctx.fillText("?", px + cs / 2, py + cs / 2 - cs * 0.02);
      ctx.globalAlpha = 1;
    } else {
      ctx.fillStyle = "rgba(10,14,19,0.85)";
      roundRect(ctx, bx, by, bw, bh, 3); ctx.fill();
      ctx.strokeStyle = color(u.side); ctx.lineWidth = 1.4;
      roundRect(ctx, bx, by, bw, bh, 3); ctx.stroke();
      ctx.fillStyle = color(u.side);
      ctx.fillText(GLYPH[u.kind] || "?", px + cs / 2, py + cs / 2 - cs * 0.04);
      const s = Math.max(0, Math.min(100, u.strength));
      ctx.fillStyle = s > 60 ? "#46c98d" : s > 30 ? "#e2a336" : "#e5484d";
      ctx.fillRect(bx + 1, by + bh + 2, (bw - 2) * s / 100, 2.5);
      if (u.entrenched) {
        ctx.fillStyle = "rgba(255,255,255,0.55)";
        ctx.fillRect(px + cs / 2 - 1.5, by - 4, 3, 3);
      }
    }
  }
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
  const meta = KIND_META[e.kind] || ["消息", "#7c8a98"];
  const src = e.director ? "导演部" : (S.sideNames[e.camp] || e.camp || "");
  const div = document.createElement("div");
  div.className = `fi k-${e.kind}${e.director ? " dir" : ""}`;
  div.dataset.kind = e.kind;
  div.innerHTML = `
    <div class="fi-head"><span class="ft">T${String(e.t).padStart(3, "0")}</span>
      <span class="fcamp dir-src" ${e.camp ? `style="color:${color(e.camp)}"` : ""}>${esc(src.slice(0, 3))}</span>
      <span class="fk">${meta[0]}${e.director ? "·注入" : ""}</span>
      <span class="fr">${esc(titleOf(e.sender))} → ${esc(titleOf(e.recipient))}</span></div>
    ${e.subject ? `<div class="fi-sub">${esc(e.subject)}</div>` : ""}
    ${e.body ? `<div class="fi-body">${esc(e.body)}</div>` : ""}`;
  prependFeed(div);
}

function addSysFeed(e) {
  if (S.filter) return;
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
  else if (e.type === "dirscript") sub = `◈ 导演剧本触发：${(S.sideNames[e.camp] || e.camp)} → ${titleOf(e.recipient)}《${e.subject || ""}》`;
  else if (e.type === "dirscript_failed") { sub = `⚠ 剧本注入失败：${(S.sideNames[e.camp] || e.camp)} → ${titleOf(e.recipient)}`; warn = true; }
  if (!sub) return;
  const div = document.createElement("div");
  div.className = `fi sys${warn ? " warn" : e.type === "dirscript" ? " dir" : ""}`;
  div.innerHTML = `<div class="fi-head"><span class="ft">T${String(e.t).padStart(3, "0")}</span>
    <span class="fcamp">${e.camp ? esc((S.sideNames[e.camp] || e.camp).slice(0, 2)) : ""}</span>
    <span class="fr mono">${esc(sub)}</span></div>`;
  prependFeed(div);
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

// ---------- 导演部讲评（复盘指标） ----------
async function fetchMetrics() {
  try { renderMetrics(await (await fetch("/api/metrics")).json()); } catch (e) { /* ignore */ }
}

function renderMetrics(m) {
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
    Object.keys(m.camps || {}).map(card).join("");
}

// ---------- SSE 与控制 ----------
function connectSSE() {
  const es = new EventSource("/api/stream");
  es.onmessage = (ev) => {
    let e;
    try { e = JSON.parse(ev.data); } catch { return; }
    if (e.type === "reset") { els.feed.innerHTML = ""; S.epoch = e.epoch; fetchState(); return; }
    if (e.type === "msg") { addFeed(e); animateMsg(e); }
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