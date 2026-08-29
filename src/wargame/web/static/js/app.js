/* CommandSim 前端：指挥链路图 + 态势图 + 消息流（SSE 实时） */
"use strict";

// ---------- 全局状态 ----------
const S = {
  state: null,
  view: "director",   // director / red / blue
  camp: "red",        // 指挥链当前展示阵营
  filter: "",
  epoch: -1,
  titles: {},         // posId → 职位名
  shorts: {},         // posId → 短名（去阵营前缀，供指挥链节点）
  unitOwner: {},      // unitId → 指挥职位 posId
  unitNames: {},      // unitId → 部队名
  nodes: {},          // posId → DOM 节点（当前 tab）
  sideNames: { red: "红军", blue: "蓝军" },
  sideColors: {},
  factions: ["red", "blue"],
  factionsKey: "",
  metricsTab: false,
  cam: { scale: 1, panX: 0, panY: 0, drag: null, view: null },  // 态势图相机
  edges: [],          // 指挥链连线（含坐标，供消息动画）
};

const SVGNS = "http://www.w3.org/2000/svg";
const $ = (id) => document.getElementById(id);
const els = {};

const KIND_META = {
  intent: ["意图", "#e2a336"], order: ["命令", "#e5484d"], ack: ["确认", "#7c8a98"],
  sitrep: ["报告", "#46c98d"], request: ["请示", "#c58af9"], plan: ["方案", "#e2a336"],
  intel: ["情报", "#4c8dff"], escalation: ["告警", "#ff7a45"],
};

// 指挥链固定布局（与编制表对应）
const ORG_ROWS = [
  [{ k: "hq", w: 112, cls: "virtual" }],
  [{ k: "army", w: 96, cls: "main" }],
  [{ k: "cos", w: 86, cls: "staff" }, { k: "intel", w: 86, cls: "staff" }, { k: "log", w: 86, cls: "staff" }],
  [{ k: "div1", w: 112 }, { k: "div2", w: 112 }],
  [{ k: "div1-b1", w: 92 }, { k: "div1-b2", w: 92 }],
  [{ k: "div2-b3", w: 92 }, { k: "div2-b4", w: 92 }],
];
const NODE_LABELS = {
  "hq": "上级司令部", "army": "军长", "cos": "参谋长", "intel": "情报参谋", "log": "后勤处长",
  "div1": "第1摩步师", "div2": "第2装甲师",
  "div1-b1": "第1团", "div1-b2": "第2团", "div2-b3": "第3团", "div2-b4": "第4团",
};
const PARENT = {
  "army": "hq", "cos": "army", "intel": "army", "log": "army",
  "div1": "army", "div2": "army",
  "div1-b1": "div1", "div1-b2": "div1", "div2-b3": "div2", "div2-b4": "div2",
};

const TERR_COLOR = { ".": "#121920", "f": "#152219", "h": "#1b2114", "~": "#0e2033", "B": "#3a3123", "C": "#242b33", "m": "#14262a", "r": "#26200f" };
const WEATHER_CN = { clear: "晴", overcast: "阴", rain: "雨", storm: "风暴" };
const PALETTE = ["#e5484d", "#4c8dff", "#46c98d", "#e2a336", "#c58af9", "#ff7a45"];
const color = (side) => S.sideColors[side] || "#7c8a98";
const hexA = (hex, a) => {
  const n = parseInt(hex.slice(1), 16);
  return `rgba(${(n >> 16) & 255},${(n >> 8) & 255},${n & 255},${a})`;
};
const GLYPH = { infantry: "步", armor: "装", artillery: "炮", recon: "侦" };

function esc(s) {
  return String(s).replace(/[&<>"']/g, (c) =>
    ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]));
}

// ---------- 启动 ----------
function boot() {
  ["tick", "scenario", "run-pulse", "mode-badge", "org-wrap", "org-edges", "org-nodes",
   "intent-text", "intent-target", "btn-intent", "map", "feed", "feed-filter",
   "btn-start", "btn-pause", "btn-step", "btn-reset", "speed",
   "btn-settings", "settings-mask", "btn-close-settings",
   "btn-apply-friction", "btn-save-settings", "set-status",
   "zoom-in", "zoom-out", "zoom-reset", "zoom-label", "metrics",
   "tabs", "view-switch", "btn-home", "lobby", "lobby-cards",
   "ai-text", "btn-ai-import", "ai-status"].forEach((k) => (els[k] = $(k)));
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
  wireLobby();
  connectSSE();
  fetchState();
  setInterval(fetchState, 1200);
  wireSettings();
  showLobby();  // 开局先进主界面选场景
}

// ---------- 主界面大厅 ----------
function wireLobby() {
  els["btn-home"].onclick = () => { control({ action: "pause" }); showLobby(); };
  els["btn-ai-import"].onclick = aiImport;
}

async function showLobby() {
  els.lobby.classList.remove("hidden");
  try {
    const list = await (await fetch("/api/scenarios")).json();
    els["lobby-cards"].innerHTML = list.map((s) => `
      <button class="lcard" data-id="${s.id}">
        <span class="ltag">战役场景</span>
        ${esc(s.name)}
        <span class="lsub">点击进入推演 · 可在设置中调整引擎与参数</span>
      </button>`).join("");
    els["lobby-cards"].querySelectorAll(".lcard").forEach((c) =>
      c.addEventListener("click", () => enterScenario(c.dataset.id)));
  } catch (e) { /* ignore */ }
}

async function enterScenario(id) {
  await control({ action: "reset" });
  await fetch("/api/settings", {
    method: "POST", headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ scenario: id, policy_mode: "rule" }),
  });
  els.lobby.classList.add("hidden");
  els.feed.innerHTML = "";
  els.metrics.innerHTML = "";
  fetchState();
}

async function aiImport() {
  const text = els["ai-text"].value.trim();
  if (!text) return;
  els["ai-status"].textContent = "AI 正在识别资料并生成场景…";
  try {
    const r = await (await fetch("/api/scenarios/ai_import", {
      method: "POST", headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ side: "import", text }),
    })).json();
    if (r.ok) {
      els["ai-status"].textContent = `已生成场景「${r.name}」，点击上方卡片进入推演 ✓`;
      els["ai-text"].value = "";
      showLobby();
    } else {
      els["ai-status"].textContent = r.error || "识别失败";
    }
  } catch (e) {
    els["ai-status"].textContent = "请求失败，请重试";
  }
}

// ---------- 态势图相机：滚轮缩放（以光标为中心）+ 拖拽平移 + 复位 ----------
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
  window.addEventListener("mouseup", () => {
    S.cam.drag = null;
    cv.classList.remove("dragging");
  });
  els["zoom-in"].onclick = () => { const r = cv.getBoundingClientRect(); zoomAt(r.width / 2, r.height / 2, 1.3); };
  els["zoom-out"].onclick = () => { const r = cv.getBoundingClientRect(); zoomAt(r.width / 2, r.height / 2, 1 / 1.3); };
  els["zoom-reset"].onclick = () => { S.cam.scale = 1; S.cam.panX = 0; S.cam.panY = 0; drawMap(); };
}

function zoomAt(mx, my, factor) {
  const st = S.state;
  if (!st) return;
  const v = S.cam.view;
  if (!v) return;
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
// 实时参数分组（id 对应 modal 容器；friction 组走 /api/friction，其余走 /api/tuning）
const TUNING_GROUPS = {
  "set-battle": [
    { k: "combat_scale", label: "战斗强度", min: 0.2, max: 3, step: 0.1 },
    { k: "arty_scale", label: "炮兵威力", min: 0.2, max: 3, step: 0.1 },
    { k: "entrench_bonus", label: "工事加成", min: 0, max: 1, step: 0.05 },
    { k: "terrain_def_scale", label: "地形加成", min: 0, max: 2, step: 0.1 },
  ],
  "set-logi": [
    { k: "supply_regen", label: "补给回复/拍", min: 0, max: 15, step: 1 },
    { k: "supply_drain", label: "补给消耗/拍", min: 0, max: 10, step: 0.5 },
    { k: "depot_radius", label: "补给半径(格)", min: 3, max: 14, step: 1 },
    { k: "recon_scale", label: "侦察半径倍率", min: 0.5, max: 3, step: 0.1 },
    { k: "intel_error", label: "敌情误差(格)", min: 0, max: 3, step: 1 },
  ],
  "set-tempo": [
    { k: "move_scale", label: "移速倍率", min: 0.5, max: 3, step: 0.1 },
    { k: "report_interval", label: "报告间隔(拍)", min: 2, max: 24, step: 1 },
    { k: "withdraw_threshold", label: "告警兵力阈值%", min: 10, max: 80, step: 5 },
    { k: "contact_fwd_interval", label: "接触报告间隔", min: 1, max: 12, step: 1 },
  ],
  "set-friction": [
    { k: "latency_scale", label: "消息延迟倍率", min: 0.5, max: 4, step: 0.5 },
    { k: "loss_rate", label: "消息丢失率", min: 0, max: 0.4, step: 0.02, pct: true },
  ],
  "set-llmrun": [
    { k: "llm_temperature", label: "LLM 温度", min: 0, max: 1, step: 0.05 },
    { k: "llm_max_tokens", label: "单次Token上限", min: 200, max: 2000, step: 50 },
    { k: "llm_budget", label: "每拍调用预算", min: 5, max: 100, step: 5 },
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
      const show = () => {
        out.textContent = f.pct ? Math.round(inp.value * 100) + "%" : inp.value;
      };
      inp.addEventListener("input", show);
    }
  }
}

const tval = (k) => {
  const el = $("t-" + k);
  return el ? parseFloat(el.value) : 0;
};

function wireSettings() {
  els["btn-settings"].onclick = openSettings;
  els["btn-close-settings"].onclick = closeSettings;
  els["settings-mask"].addEventListener("click", (e) => {
    if (e.target === els["settings-mask"]) closeSettings();
  });
  $("set-speed").oninput = (e) => ($("set-speed-v").textContent = e.target.value);
  els["btn-apply-friction"].onclick = applyLive;
  els["btn-save-settings"].onclick = saveSettings;
}

async function openSettings() {
  els["settings-mask"].classList.remove("hidden");
  try {
    const s = await (await fetch("/api/settings")).json();
    const sel = $("set-scenario");
    sel.innerHTML = "";
    for (const sc of s.scenarios || []) {
      const opt = document.createElement("option");
      opt.value = sc.id; opt.textContent = sc.name;
      sel.appendChild(opt);
    }
    sel.value = s.scenario || (s.scenarios && s.scenarios[0] && s.scenarios[0].id) || "cross_river";
    $("set-policy").value = s.policy_mode;
    $("set-seed").value = s.seed ?? 7;
    $("set-speed").value = s.speed;
    $("set-speed-v").textContent = s.speed;
    for (const fields of Object.values(TUNING_GROUPS)) {
      for (const f of fields) {
        const inp = $("t-" + f.k);
        if (!inp) continue;
        let v;
        if (f.k === "latency_scale" || f.k === "loss_rate") v = (s.friction || {})[f.k];
        else if (f.k === "llm_temperature") v = s.llm.temperature;
        else if (f.k === "llm_max_tokens") v = s.llm.max_tokens;
        else if (f.k === "llm_budget") v = s.llm.budget;
        else v = (s.tuning || {})[f.k];
        if (v !== undefined && v !== null) {
          inp.value = v;
          inp.dispatchEvent(new Event("input"));
        }
      }
    }
    $("set-llm-url").value = s.llm.base_url || "";
    $("set-llm-model").value = s.llm.model || "";
    $("set-llm-key").value = "";
    els["set-status"].textContent = s.llm.available
      ? "当前：LLM 已接入 ✓" : "当前：规则模式（未配置 Key）";
  } catch (e) {
    els["set-status"].textContent = "读取设置失败";
  }
}

function closeSettings() {
  els["settings-mask"].classList.add("hidden");
}

async function applyLive() {
  const tuning = {};
  for (const fields of Object.values(TUNING_GROUPS)) {
    for (const f of fields) {
      if (f.k === "latency_scale" || f.k === "loss_rate") continue;
      tuning[f.k] = tval(f.k);
    }
  }
  try {
    await Promise.all([
      fetch("/api/friction", {
        method: "POST", headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          latency_scale: tval("latency_scale"),
          loss_rate: tval("loss_rate"),
        }),
      }),
      fetch("/api/tuning", {
        method: "POST", headers: { "Content-Type": "application/json" },
        body: JSON.stringify(tuning),
      }),
    ]);
    els["set-status"].textContent = "参数已实时应用 ✓";
  } catch (e) {
    els["set-status"].textContent = "应用失败";
  }
}

async function saveSettings() {
  const body = {
    policy_mode: $("set-policy").value,
    seed: parseInt($("set-seed").value || "7", 10),
    scenario: $("set-scenario").value,
  };
  const url = $("set-llm-url").value.trim();
  const model = $("set-llm-model").value.trim();
  const key = $("set-llm-key").value.trim();
  if (url) body.llm_base_url = url;
  if (model) body.llm_model = model;
  if (key) body.llm_api_key = key;
  try {
    await fetch("/api/control", {
      method: "POST", headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ action: "speed", speed: parseFloat($("set-speed").value) }),
    });
    await fetch("/api/settings", {
      method: "POST", headers: { "Content-Type": "application/json" },
      body: JSON.stringify(body),
    });
    closeSettings();
    els.feed.innerHTML = "";
    fetchState();
  } catch (e) { /* ignore */ }
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
    els.scenario.textContent = st.weather
      ? `${st.scenario} · ${WEATHER_CN[st.weather] || st.weather}` : st.scenario;
    els["run-pulse"].classList.toggle("on", st.running);
    const badge = els["mode-badge"];
    badge.textContent = st.llm.available ? `LLM · ${st.llm.model}` : `规则模式 · seed ${st.seed}`;
    badge.classList.toggle("llm", st.llm.available);
    renderOrg();
    drawMap();
  } catch (e) { /* 服务未就绪时静默重试 */ }
}

function buildLookup(st) {
  S.titles = {}; S.shorts = {}; S.unitOwner = {}; S.unitNames = {};
  for (const side of ["red", "blue"]) {
    const camp = st.camps[side];
    (function walk(n) {
      S.titles[n.id] = n.title;
      S.shorts[n.id] = n.short || n.title.replace(/^(红军|蓝军)/, "");
      for (const u of n.units) S.unitOwner[u] = n.id;
      n.children.forEach(walk);
    })(camp.org);
    for (const u of camp.units) S.unitNames[u.id] = u.name;
    for (const i of camp.intel) S.unitNames[i.unit_id] = i.name;
  }
}

// 阵营组合变化时重建页签/视角切换/配色（多方：任意数量的阵营）
function buildFactionUI() {
  const key = S.factions.join("|");
  if (key === S.factionsKey) return;
  S.factionsKey = key;
  S.sideColors = {};
  S.factions.forEach((f, i) => { S.sideColors[f] = PALETTE[i % PALETTE.length]; });
  if (!S.factions.includes(S.camp)) S.camp = S.factions[0];

  els.tabs.innerHTML = S.factions.map((f) =>
    `<button class="tab" data-side="${f}">${esc(S.sideNames[f] || f)}指挥链</button>`).join("");
  els.tabs.querySelectorAll(".tab").forEach((t) => t.addEventListener("click", () => {
    els.tabs.querySelectorAll(".tab").forEach((x) => x.classList.remove("active"));
    t.classList.add("active");
    S.camp = t.dataset.side;
    els["intent-target"].textContent = `→ ${S.sideNames[S.camp] || S.camp}主官`;
    renderOrg();
  }));
  els.tabs.querySelector(".tab").classList.add("active");

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

function titleOf(posId) {
  if (posId.startsWith("unit:")) return S.unitNames[posId.slice(5)] || posId.slice(5);
  return S.titles[posId] || posId;
}

// ---------- 指挥链路图 ----------
function renderOrg() {
  const wrap = els["org-wrap"];
  const nodesEl = els["org-nodes"];
  const svg = els["org-edges"];
  // 连线层放进节点容器，坐标系才一致；重绘前清空旧连线
  nodesEl.innerHTML = "";
  svg.innerHTML = "";
  nodesEl.appendChild(svg);
  S.nodes = {}; S.edges = [];

  const side = S.camp;
  const W = Math.max(240, wrap.clientWidth - 16);
  const GAP_Y = 16;
  let y = 10;
  for (const row of ORG_ROWS) {
    const isStaff = row.some((n) => n.cls === "staff");
    const h = isStaff ? 26 : 30;
    const totalW = row.reduce((s, n) => s + n.w, 0) + (row.length - 1) * 12;
    let x = Math.max(4, (W - totalW) / 2);
    for (const item of row) {
      const posId = `${side}:${item.k}`;
      const div = document.createElement("div");
      div.className = `node ${item.cls || ""}`;
      div.dataset.pos = posId;
      div.style.cssText = `left:${x}px; top:${y}px; width:${item.w}px; border-left:3px solid ${color(side)};`;
      div.innerHTML = `<span>${(S.shorts && S.shorts[posId]) || NODE_LABELS[item.k] || item.k}</span><span class="n-dot"></span>`;
      div.title = S.titles[posId] || posId;
      nodesEl.appendChild(div);
      S.nodes[posId] = div;
      x += item.w + 12;
    }
    y += h + GAP_Y;
  }
  nodesEl.style.height = (y + 12) + "px";
  svg.setAttribute("width", W);
  svg.setAttribute("height", y + 12);

  const stroke = hexA(color(side), .3);
  for (const [posId, el] of Object.entries(S.nodes)) {
    const key = posId.split(":")[1];
    const parentId = PARENT[key] ? `${side}:${PARENT[key]}` : null;
    const pel = parentId ? S.nodes[parentId] : null;
    if (!pel) continue;
    const x1 = pel.offsetLeft + pel.offsetWidth / 2, y1 = pel.offsetTop + pel.offsetHeight;
    const x2 = el.offsetLeft + el.offsetWidth / 2, y2 = el.offsetTop;
    const line = document.createElementNS(SVGNS, "line");
    line.setAttribute("x1", x1); line.setAttribute("y1", y1);
    line.setAttribute("x2", x2); line.setAttribute("y2", y2);
    line.setAttribute("stroke", stroke);
    line.setAttribute("stroke-width", "1");
    svg.appendChild(line);
    S.edges.push({ from: parentId, to: posId, x1, y1, x2, y2 });
  }
}

// 消息沿线动画：发件节点 → 收件节点
function animateMsg(e) {
  if (e.camp !== S.camp) return;
  const fromId = e.sender.startsWith("unit:") ? S.unitOwner[e.sender.slice(5)] : e.sender;
  const toId = e.recipient.startsWith("unit:") ? S.unitOwner[e.recipient.slice(5)] : e.recipient;
  if (!fromId || !toId) return;
  const edge = S.edges.find((x) =>
    (x.from === fromId && x.to === toId) || (x.from === toId && x.to === fromId));
  if (!edge) return;
  const svg = els["org-edges"];
  const color = (KIND_META[e.kind] || [, "#e2a336"])[1];
  const dot = document.createElementNS(SVGNS, "circle");
  dot.setAttribute("r", "3.2");
  dot.setAttribute("fill", color);
  svg.appendChild(dot);
  const fwd = edge.from === fromId;
  const t0 = performance.now(), DUR = 550;
  (function step(now) {
    const p = Math.min(1, (now - t0) / DUR);
    const x = fwd ? edge.x1 + (edge.x2 - edge.x1) * p : edge.x2 + (edge.x1 - edge.x2) * p;
    const yy = fwd ? edge.y1 + (edge.y2 - edge.y1) * p : edge.y2 + (edge.y1 - edge.y2) * p;
    dot.setAttribute("cx", x); dot.setAttribute("cy", yy);
    if (p < 1) requestAnimationFrame(step); else dot.remove();
  })(t0);
  const target = S.nodes[toId];
  if (target) {
    target.classList.add("flash");
    setTimeout(() => target.classList.remove("flash"), 900);
  }
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

  // 相机变换：有效格尺寸 = 适配格尺寸 × 缩放；平移在越界时钳制边缘
  const baseCs = Math.min(cw / st.w, ch / st.h);
  const zoom = S.cam.scale;
  const cs = baseCs * zoom;
  const cW = cs * st.w, cH = cs * st.h;
  let ox = (cw - cW) / 2 + S.cam.panX, oy = (ch - cH) / 2 + S.cam.panY;
  if (cW <= cw) ox = (cw - cW) / 2;
  else ox = Math.max(cw - cW, Math.min(0, ox));
  if (cH <= ch) oy = (ch - cH) / 2;
  else oy = Math.max(ch - cH, Math.min(0, oy));
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
  // 补给站（可被夺占，颜色=控制方）
  ctx.font = `${Math.max(10, Math.floor(cs * 0.4))}px sans-serif`;
  for (const d of (st.depots || [])) {
    ctx.fillStyle = d.owner === "red" ? "rgba(229,72,77,.65)"
      : d.owner === "blue" ? "rgba(76,141,255,.65)" : "rgba(255,255,255,.3)";
    ctx.fillText("◆", ox + d.x * cs + cs / 2, oy + d.y * cs + cs / 2);
  }

  // 单位（导演视角全知；阵营视角敌军只显示己方情报轮廓）
  let units = [];
  if (S.view === "director") {
    units = [...st.camps.red.units, ...st.camps.blue.units];
  } else {
    const camp = st.camps[S.view];
    units = camp.units.map((u) => ({ ...u }));
    const enemy = S.view === "red" ? "blue" : "red";
    for (const i of camp.intel) {
      units.push({ id: i.unit_id, side: enemy, kind: i.kind, x: i.x, y: i.y, ghost: true, age: st.tick - i.tick });
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
  if (S.filter && e.kind !== S.filter) return;
  const meta = KIND_META[e.kind] || ["消息", "#7c8a98"];
  const div = document.createElement("div");
  div.className = `fi k-${e.kind}`;
  div.dataset.kind = e.kind;
  div.innerHTML = `
    <div class="fi-head"><span class="ft">T${String(e.t).padStart(3, "0")}</span>
      <span class="fcamp" style="color:${color(e.camp)}">${esc((S.sideNames[e.camp] || e.camp).slice(0, 2))}</span>
      <span class="fk">${meta[0]}</span>
      <span class="fr">${esc(titleOf(e.sender))} → ${esc(titleOf(e.recipient))}</span></div>
    ${e.subject ? `<div class="fi-sub">${esc(e.subject)}</div>` : ""}
    ${e.body ? `<div class="fi-body">${esc(e.body)}</div>` : ""}`;
  prependFeed(div);
}

function addSysFeed(e) {
  if (S.filter) return;  // 系统事件只在"全部"下显示
  let sub = "", warn = false;
  if (e.type === "combat") sub = `⚔ ${e.name || e.unit} 损失 ${e.taken}（${(e.vs || []).join("、")}）`;
  else if (e.type === "fire") sub = `▲ ${e.name || e.unit} 炮击 ${e.target_name || ""}，损失 ${e.dmg}`;
  else if (e.type === "destroyed") { sub = `✝ ${e.name || e.unit} 全损`; warn = true; }
  else if (e.type === "intel") sub = `◎ 侦察发现 ${e.n} 个目标`;
  else if (e.type === "reached") sub = `➤ ${e.name || e.unit} 到达 (${e.x},${e.y})`;
  else if (e.type === "isolation_blocked") { sub = `⛔ 隔离拦截：${e.reason || e.detail || ""}`; warn = true; }
  else if (e.type === "msg_lost") { sub = `✉ 电文中断：${titleOf(e.sender)} → ${titleOf(e.recipient)}《${e.subject || ""}》`; warn = true; }
  else if (e.type === "weather") sub = `☁ 天气转为：${WEATHER_CN[e.weather] || e.weather}`;
  else if (e.type === "reinforce") sub = `＋ 增援入场：${e.name}（${e.camp === "red" ? (S.sideNames.red || "红") : (S.sideNames.blue || "蓝")}）`;
  else if (e.type === "depot") sub = `⚑ 补给站易手 (${e.x},${e.y})：${e.from} → ${e.side}`;
  else if (e.type === "objective") sub = `◈ 夺占目标：${e.name}（${e.camp === "red" ? "红" : "蓝"}方）`;
  else if (e.type === "air") sub = `✈ 空军遮断：${e.name || e.unit} 损失 ${e.dmg}`;
  else if (e.type === "llm_fallback") sub = `⚠ LLM 降级规则：${String(e.error || "").slice(0, 60)}`;
  else if (e.type === "action") sub = `→ ${e.unit} ${e.kind}${e.target ? " (" + e.target.join(",") + ")" : ""}`;
  if (!sub) return;
  const div = document.createElement("div");
  div.className = `fi sys${warn ? " warn" : ""}`;
  div.innerHTML = `<div class="fi-head"><span class="ft">T${String(e.t).padStart(3, "0")}</span>
    <span class="fcamp ${e.camp || ""}">${e.camp ? (e.camp === "red" ? "红" : "蓝") : ""}</span>
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

// ---------- 复盘指标 ----------
async function fetchMetrics() {
  try {
    const m = await (await fetch("/api/metrics")).json();
    renderMetrics(m);
  } catch (e) { /* ignore */ }
}

function renderMetrics(m) {
  const name = S.sideNames || {};
  const card = (side) => {
    const c = (m.camps || {})[side] || {};
    const pct = c.units_total ? Math.round((c.strength || 0) / (c.units_total * 100) * 100) : 0;
    const pctStr = (v) => (v == null ? "—" : Math.round(v * 100) + "%");
    return `
      <div class="mcard" style="border-top:3px solid ${color(side)}">
        <div class="mc-head">${name[side] || side}</div>
        <div class="mc-row big">剩余兵力<b>${c.strength ?? 0}</b>
          <span class="dim">/ ${c.units_total * 100 || "?"} · 存活 ${c.units_alive ?? 0}/${c.units_total ?? 0}</span></div>
        <div class="bar"><i style="width:${pct}%"></i></div>
        <div class="mc-grid">
          <div>命令下行<b>${c.orders ?? 0}</b></div>
          <div>确认率<b>${pctStr(c.ack_rate)}</b></div>
          <div>确认延迟<b>${c.ack_latency == null ? "—" : c.ack_latency + "拍"}</b></div>
          <div>态势报告<b>${c.sitreps ?? 0}</b></div>
          <div>请示<b>${c.requests ?? 0}</b></div>
          <div>告警<b>${c.escalations ?? 0}</b></div>
          <div>情报<b>${c.intel ?? 0}</b></div>
          <div>决策次数<b>${c.decisions ?? 0}</b></div>
          <div>电文中断<b>${c.msg_lost ?? 0}</b></div>
          <div>隔离拦截<b>${c.isolation_blocked ?? 0}</b></div>
          <div>LLM降级<b>${c.llm_fallback ?? 0}</b></div>
        </div>
      </div>`;
  };
  const score = m.score || { red: 0, blue: 0 };
  const objs = (m.objectives || []).map((o) => {
    const who = o.controller ? (S.sideNames[o.controller] || o.controller) : "无主";
    return `<span class="obj o-${o.controller || "none"}">${o.name}·${who}</span>`;
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
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(body),
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
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ side: S.camp, text }),
    });
    els["intent-text"].value = "";
  } catch (e) { /* ignore */ }
}

document.addEventListener("DOMContentLoaded", boot);
