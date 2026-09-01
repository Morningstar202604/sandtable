"""Web 控制台后端：REST 快照/控制 + SSE 实时事件流。

仿真推进循环放在事件循环里（LLM 模式单 tick 有网络等待，
用 to_thread 避免卡住 SSE）。SSE 按 seq 游标增量推送，
前端断线自动重连后从游标续传。
"""

from __future__ import annotations

import asyncio
import json
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI
from fastapi.responses import StreamingResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

from ..config import settings
from ..engine.world import DEFAULT_TUNING
from ..llm import llm_client
from ..scenarios import SCENARIOS
from ..scenarios.dynamic import make_dynamic_scenario
from ..sim import Simulation

try:
    from .. import battlelib
    _HAS_BATTLELIB = True
except Exception:  # noqa: BLE001
    _HAS_BATTLELIB = False

STATIC_DIR = Path(__file__).parent / "static"


class BattleBody(BaseModel):
    """战役定制：环境层 + 全局层 + 双方实力。apply=True 保存并重置推演生效。"""

    config: dict | None = None
    apply: bool = False


class ControlBody(BaseModel):
    """推演控制请求。注意必须定义在模块层：本项目开了 PEP 563 惰性注解，
    FastAPI 解析闭包内局部类的注解会失败并退化为 query 参数。"""

    action: str  # start / pause / step / reset / speed
    speed: float | None = None


class IntentBody(BaseModel):
    side: str
    text: str


class DirectorBody(BaseModel):
    """将台导演部情况注入：向指定参演方角色送一条电文。"""

    side: str            # 参演方 id（usa / uk / ger / red / blue …）
    recipient: str       # 目标角色职位 id，如 usa:army
    kind: str = "intent"  # intent/order/sitrep/intel/escalation/…
    subject: str = ""
    body: str = ""
    sender: str | None = None   # 默认该方上级司令部 {side}:hq
    priority: int = 0


class RoleConfig(BaseModel):
    pos: str
    config: dict


class RolesBody(BaseModel):
    updates: list[RoleConfig] = []
    reset: bool = False  # 一键恢复全部子智能体的想定原始性格/参数


class IntentsBody(BaseModel):
    intents: dict[str, str] | None = None


class SettingsBody(BaseModel):
    """推演设置：策略/种子/场景需重置生效；LLM 配置原地生效。"""

    policy_mode: str | None = None
    seed: int | None = None
    scenario: str | None = None
    weather_override: str | None = None
    llm_base_url: str | None = None
    llm_model: str | None = None
    llm_api_key: str | None = None
    llm_use_tools: bool | None = None
    llm_retry: int | None = None
    llm_timeout: float | None = None
    llm_top_p: float | None = None
    llm_frequency_penalty: float | None = None
    llm_presence_penalty: float | None = None
    fallback_enabled: bool | None = None


class LLMTestBody(BaseModel):
    """连接测试：携带候选端点（未保存时先测再存）；留空则测当前已保存配置。"""

    base_url: str | None = None
    model: str | None = None
    api_key: str | None = None


class FrictionBody(BaseModel):
    latency_scale: float | None = None
    loss_rate: float | None = None


class TuningBody(BaseModel):
    """实时调参：世界引擎与智能体策略直接读写共享字典，改完即生效。

    llm_* 三项路由到 LLM 客户端/预算配置，其余进 world.tuning。
    """

    combat_scale: float | None = None
    arty_scale: float | None = None
    entrench_bonus: float | None = None
    terrain_def_scale: float | None = None
    supply_regen: float | None = None
    supply_drain: float | None = None
    depot_radius: float | None = None
    recon_scale: float | None = None
    intel_error: int | None = None
    move_scale: float | None = None
    report_interval: int | None = None
    withdraw_threshold: float | None = None
    contact_fwd_interval: int | None = None
    air_scale: float | None = None
    air_dmg: float | None = None
    air_prob: float | None = None
    supply_combat_scale: float | None = None
    morale_scale: float | None = None
    low_strength_penalty: float | None = None
    flank_bonus: float | None = None
    overrun_scale: float | None = None
    road_bonus: float | None = None
    arty_range_scale: float | None = None
    terrain_cost_scale: float | None = None
    aggression_scale: float | None = None
    escalation_delay: int | None = None
    memory_size: int | None = None
    llm_temperature: float | None = None
    llm_max_tokens: int | None = None
    llm_budget: int | None = None
    # === 战役特征增强（v6）===
    daynight_enabled: float | None = None
    night_recon: float | None = None
    night_arty: float | None = None
    night_melee: float | None = None
    night_move: float | None = None
    fatigue_enabled: float | None = None
    fatigue_move: float | None = None
    fatigue_combat: float | None = None
    fatigue_rest: float | None = None
    fatigue_penalty: float | None = None
    morale_enabled: float | None = None
    morale_shock: float | None = None
    morale_break: float | None = None
    morale_recover: float | None = None
    reorg_strength: float | None = None
    suppression_enabled: float | None = None
    suppression_penalty: float | None = None
    suppression_ticks: float | None = None
    ew_jamming: float | None = None
    flank_dir_bonus: float | None = None
    tactical_withdraw_threshold: float | None = None
    tactical_report_interval: int | None = None


_TUNING_CLAMPS = {
    "combat_scale": (0.1, 5.0), "arty_scale": (0.1, 5.0),
    "entrench_bonus": (0.0, 1.0), "terrain_def_scale": (0.0, 2.0),
    "supply_regen": (0.0, 20.0), "supply_drain": (0.0, 15.0),
    "depot_radius": (2, 16), "recon_scale": (0.3, 4.0), "intel_error": (0, 3),
    "move_scale": (0.3, 4.0), "report_interval": (2, 48),
    "withdraw_threshold": (5, 90), "contact_fwd_interval": (1, 24),
    "air_scale": (0.0, 3.0), "air_dmg": (0.0, 12.0), "air_prob": (0.0, 0.6),
    "supply_combat_scale": (0.0, 1.0),
    "morale_scale": (0.0, 2.0), "low_strength_penalty": (0.0, 0.9),
    "flank_bonus": (0.0, 2.0), "overrun_scale": (0.0, 1.0),
    "road_bonus": (0.3, 3.0), "arty_range_scale": (0.5, 2.5),
    "terrain_cost_scale": (0.3, 3.0),
    "aggression_scale": (0.2, 3.0), "escalation_delay": (0, 20),
    "memory_size": (5, 200),
    # === 战役特征增强（v6）===
    "daynight_enabled": (0, 1), "night_recon": (0.1, 2.0),
    "night_arty": (0.1, 2.0), "night_melee": (0.1, 2.0), "night_move": (0.1, 2.0),
    "fatigue_enabled": (0, 1), "fatigue_move": (0, 3.0),
    "fatigue_combat": (0, 3.0), "fatigue_rest": (0, 1.5), "fatigue_penalty": (0, 0.01),
    "morale_enabled": (0, 1), "morale_shock": (0.05, 1.0),
    "morale_break": (0.05, 0.5), "morale_recover": (0, 0.2),
    "reorg_strength": (0.1, 0.8),
    "suppression_enabled": (0, 1), "suppression_penalty": (0, 0.8),
    "suppression_ticks": (1, 8), "ew_jamming": (0, 0.6),
    "flank_dir_bonus": (0, 0.8),
    "tactical_withdraw_threshold": (5, 80), "tactical_report_interval": (2, 24),
}


class DirectorScriptBody(BaseModel):
    script: list[dict] = []


class SimHost:
    """持有当前仿真实例与后台推进循环。

    friction 保存在 host 层而不是仿真层——重置推演后摩擦参数得以延续。
    role_overrides / intent_overrides 等"导演部配置"持久化到 runs/host_state.json，
    服务重启后恢复——将台想定与子智能体人格不因重启而丢失。
    """

    STATE_PATH = Path("runs") / "host_state.json"

    def __init__(self, policy: str = "auto", seed: int | None = None,
                 scenario: str | None = None) -> None:
        self.policy = policy
        self.seed = seed
        self.scenario = scenario
        self.running = False
        self.speed = 2.0
        self.epoch = 0  # 每次 reset 自增，前端据此重置游标与界面
        self.friction: dict = {"latency_scale": 1.0, "loss_rate": 0.0}
        self.tuning: dict = {}  # 重置后延续的调参（引擎侧有默认值兜底）
        self.intent_overrides: dict[str, str] = {}  # 导演部设定的各参演方开局意图
        self.role_overrides: dict[str, dict] = {}   # 导演部对子智能体的角色配置覆盖
        self.script: list[dict] = []                # 导演部导调剧本（按 tick 触发）
        self.weather_override: str = ""             # 全局天气覆盖（"" = 沿用想定天气）
        self.battle: dict = {}                      # 战役定制：环境/全局/双方实力
        self._load()
        self.sim = self._build()

    def _build(self) -> Simulation:
        sim = Simulation(policy_mode=self.policy, seed=self.seed,
                         scenario=self.scenario, tuning=self.tuning,
                         intent_overrides=self.intent_overrides,
                         role_overrides=self.role_overrides,
                         battle_config=self.battle)
        sim.friction.update(self.friction)
        if self.weather_override:
            sim.world.set_weather([(0, self.weather_override)])
        sim.set_director_script(self.script)
        return sim

    def _load(self) -> None:
        try:
            if not self.STATE_PATH.exists():
                return
            data = json.loads(self.STATE_PATH.read_text(encoding="utf-8"))
            if data.get("policy") in ("auto", "rule", "llm"):
                self.policy = data["policy"]
            if data.get("seed") is not None:
                self.seed = int(data["seed"])
            if data.get("scenario"):
                self.scenario = data["scenario"]
            self.friction.update({k: v for k, v in data.get("friction", {}).items()
                                  if isinstance(v, (int, float))})
            self.tuning = {k: v for k, v in data.get("tuning", {}).items()
                           if isinstance(v, (int, float))}
            self.intent_overrides = dict(data.get("intent_overrides", {}))
            self.role_overrides = dict(data.get("role_overrides", {}))
            self.script = [d for d in data.get("script", []) if isinstance(d, dict)]
            w = data.get("weather_override", "")
            self.weather_override = w if w in ("clear", "overcast", "rain", "storm") else ""
            b = data.get("battle", {})
            self.battle = b if isinstance(b, dict) else {}
        except Exception:  # noqa: BLE001  状态文件损坏不阻塞启动
            pass

    def save(self) -> None:
        try:
            self.STATE_PATH.parent.mkdir(parents=True, exist_ok=True)
            self.STATE_PATH.write_text(json.dumps({
                "policy": self.policy, "seed": self.seed, "scenario": self.scenario,
                "friction": self.friction, "tuning": self.tuning,
                "intent_overrides": self.intent_overrides,
                "role_overrides": self.role_overrides, "script": self.script,
                "weather_override": self.weather_override,
                "battle": self.battle,
            }, ensure_ascii=False), encoding="utf-8")
        except Exception:  # noqa: BLE001
            pass

    async def loop(self) -> None:
        # 推进循环绝不允许死：单拍异常只记日志并继续，
        # 否则一次 to_thread 异常会永久冻结推演（running=True 但 tick 不再前进）
        import logging
        logger = logging.getLogger("wargame.simhost")
        while True:
            try:
                if self.running:
                    await asyncio.to_thread(self.sim.run_tick)
                    await asyncio.sleep(1.0 / self.speed)
                else:
                    await asyncio.sleep(0.2)
            except asyncio.CancelledError:
                raise
            except Exception:  # noqa: BLE001
                logger.exception("run_tick 异常，跳过本拍继续")
                self.running = False  # 停下来让用户看到问题，而不是空转
                await asyncio.sleep(0.5)

    def reset(self, policy: str | None = None, seed: int | None = None) -> None:
        if policy:
            self.policy = policy
        if seed is not None:
            self.seed = seed
        self.epoch += 1
        self.running = False
        self.sim = self._build()


def create_app(policy: str = "auto", seed: int | None = None,
               scenario: str | None = None) -> FastAPI:
    host = SimHost(policy=policy, seed=seed, scenario=scenario)

    @asynccontextmanager
    async def lifespan(_: FastAPI):
        task = asyncio.create_task(host.loop())
        yield
        task.cancel()

    app = FastAPI(title="将台 WARGENERALS 指挥协同推演", lifespan=lifespan)

    def _scenario_info(key: str, mod) -> dict:
        fac = getattr(mod, "FACTIONS", None) or \
            [{"id": "red", "name": "红军"}, {"id": "blue", "name": "蓝军"}]
        return {
            "id": key,
            "name": getattr(mod, "SCENARIO_NAME", key),
            "codename": getattr(mod, "CODENAME", ""),
            "era": getattr(mod, "ERA", ""),
            "theater": getattr(mod, "THEATER", ""),
            "scale": getattr(mod, "SCALE", ""),
            "desc": getattr(mod, "SCENARIO_DESC", ""),
            "sides": [{"id": f["id"], "name": f.get("name", f["id"])} for f in fac],
        }

    @app.get("/api/scenarios")
    def list_scenarios():
        return [_scenario_info(k, m) for k, m in SCENARIOS.items()]

    @app.post("/api/scenarios/ai_import")
    def ai_import(body: IntentBody):
        """AI 场景导入：用户喂资料 → LLM 分类/意图识别 → 生成可推演场景。

        需要已配置 LLM；生成成功后注册进场景注册表，主界面立即可选。
        """
        if not llm_client.available:
            return {"ok": False, "error": "需要先在设置中配置 LLM 才能识别资料"}
        text = body.text.strip()
        if not text:
            return {"ok": False, "error": "请先粘贴战役资料"}
        system = (
            "你是军事推演场景编辑器。阅读用户提供的战役资料，提取为场景配置 JSON。"
            "严格输出 JSON，不要任何其他文字：\n"
            '{"name":"场景名","width":30,"height":22,\n'
            ' "factions":[{"id":"英文小写id","name":"阵营显示名",'
            '"intent":"该阵营开局作战意图（一两句）",'
            '"style":"统帅的指挥风格与性格（一两句）",'
            '"units":[{"name":"部队名","kind":"infantry|armor|artillery|recon",'
            '"x":横坐标,"y":纵坐标}]}],\n'
            ' "objectives":[{"name":"目标名","x":..,"y":..,"value":1到3}]}\n'
            "要求：提取 2~6 个阵营；每方 3~7 个单位；坐标必须在 width/height 内"
            "且不同阵营分区布置；value 代表目标战略重要性。 /no_think"
        )
        try:
            raw = llm_client.chat(system, text[:4000])
            spec = llm_client.extract_json(raw)
            ns = make_dynamic_scenario(spec)
        except Exception as e:  # noqa: BLE001
            return {"ok": False, "error": f"识别失败: {str(e)[:200]}"}
        sid = _safe_scenario_id(spec.get("name") or ns.SCENARIO_NAME, len(SCENARIOS))
        SCENARIOS[sid] = ns
        return {"ok": True, "id": sid, "name": ns.SCENARIO_NAME}

    def _safe_scenario_id(name: str, n: int) -> str:
        import re
        sid = re.sub(r"[^0-9a-zA-Z_]", "_", str(name)).strip("_").lower()[:32]
        base = sid or f"ai_scene_{n}"
        sid, i = base, 1
        while sid in SCENARIOS:
            i += 1
            sid = f"{base}_{i}"
        return sid

    @app.get("/api/battle/presets")
    def list_battle_presets():
        if not _HAS_BATTLELIB:
            return {"ok": False, "error": "战役库未加载"}
        return {"ok": True, "presets": battlelib.presets_meta()}

    @app.get("/api/battle/params")
    def get_battle_params():
        """战役定制的量化参数定义：前端据 global/side_dims/env/weather 生成滑块组。"""
        if not _HAS_BATTLELIB:
            return {"ok": False, "error": "战役库未加载"}
        return {"ok": True, **battlelib.params_meta()}

    @app.get("/api/battle")
    def get_battle():
        return {"ok": True, "config": host.battle,
                "factions": [{"id": s, "name": host.sim.camp_names.get(s, s)}
                             for s in host.sim.factions],
                "summary": getattr(host.sim, "battle_summary", {}),
                "side_mod": host.sim.world.side_mod,
                "presets": battlelib.presets_meta() if _HAS_BATTLELIB else []}

    @app.post("/api/battle")
    def post_battle(body: BattleBody):
        """保存一份战役定制配置；apply 为真则在下次重置推演时落到引擎并把结果回读。"""
        if not _HAS_BATTLELIB:
            return {"ok": False, "error": "战役库未加载"}
        cfg = body.config or {}
        # 清洗：只保留合法结构（env/global/sides），避免脏数据进入状态文件
        clean = {"env": dict(cfg.get("env") or {}),
                 "global": dict(cfg.get("global") or {}),
                 "sides": {str(k): dict(v) for k, v in (cfg.get("sides") or {}).items()}}
        if cfg.get("preset"):
            clean["preset"] = str(cfg["preset"])
        host.battle = clean
        host.save()
        if body.apply:
            host.reset()  # 重建仿真并把 battle 应用到世界引擎
        return {"ok": True, "config": host.battle,
                "summary": getattr(host.sim, "battle_summary", {}),
                "epoch": host.epoch}

    @app.get("/api/state")
    def get_state():
        snap = host.sim.snapshot()
        snap["running"] = host.running
        snap["speed"] = host.speed
        snap["epoch"] = host.epoch
        return snap

    @app.get("/api/events")
    def get_events(since: int = 0):
        return {"epoch": host.epoch, "seq": host.sim.seq,
                "events": host.sim.events_since(since)}

    @app.get("/api/metrics")
    def get_metrics():
        return host.sim.compute_metrics()

    @app.post("/api/control")
    def control(body: ControlBody):
        if body.action == "start":
            host.running = True
        elif body.action == "pause":
            host.running = False
        elif body.action == "step":
            host.sim.run_tick()
        elif body.action == "reset":
            host.reset()
        if body.speed:
            host.speed = max(0.5, min(8.0, body.speed))
        return {"ok": True, "running": host.running, "speed": host.speed,
                "epoch": host.epoch}

    @app.post("/api/intent")
    def intent(body: IntentBody):
        if body.side not in host.sim.camps or not body.text.strip():
            return {"ok": False, "error": "参数无效"}
        host.sim.inject_intent(body.side, body.text.strip()[:400])
        return {"ok": True}

    @app.post("/api/director")
    def director(body: DirectorBody):
        """导演部情况注入：任意参演方、任意角色、任意电文种类。"""
        body.body = body.body.strip()
        if not body.recipient or not body.body or body.side not in host.sim.camps:
            return {"ok": False, "error": "参数无效（需指定参演方/目标角色/情况内容）"}
        ok = host.sim.director_message(
            body.side, body.recipient.strip(), body.kind,
            body.subject.strip()[:60], body.body[:600],
            sender=body.sender, priority=body.priority)
        if not ok:
            return {"ok": False, "error": "注入失败：目标角色不在该参演方或发送失败"}
        return {"ok": True}

    @app.get("/api/roles")
    def get_roles():
        """子智能体角色清单：参演方 → 各职位的角色卡与当前配置（供将台作业室配置）。"""
        registry = host.sim.registry
        sides = {}
        for side in host.sim.factions:
            pos_list = []
            for p in registry.by_id.values():
                if p.side == side:
                    merged = dict(p.config or {})
                    merged.update(host.role_overrides.get(p.id, {}))
                    pos_list.append({
                        "id": p.id, "title": p.title, "archetype": p.archetype,
                        "parent": p.parent, "staff": p.staff, "virtual": p.virtual,
                        "units": p.units, "side": side, "side_name": p.side_name,
                        "config": merged,
                    })
            sides[side] = {"name": host.sim.camp_names.get(side, side),
                           "positions": pos_list}
        return {"sides": sides}

    @app.post("/api/roles")
    def post_roles(body: RolesBody):
        """导演部配置子智能体：性格/指挥风格/行为参数，实时与重置后均生效。"""
        registry = host.sim.registry
        if body.reset:
            # 一键恢复：清空全部覆盖并重建仿真，位置配置回到想定原始值
            host.role_overrides = {}
            host.save()
            host.reset()
            return {"ok": True, "reset": True}
        for u in body.updates:
            p = registry.get(u.pos)
            if not p:
                continue
            cfg = dict(u.config)
            host.role_overrides[u.pos] = dict(p.config or {}, **cfg)
            p.config.update(cfg)
        host.save()
        return {"ok": True}

    @app.get("/api/director/script")
    def get_script():
        return {"script": host.script}

    @app.post("/api/director/script")
    def post_script(body: DirectorScriptBody):
        """导演部保存导调剧本：一组按 tick 自动触发的情况注入。"""
        host.script = [s for s in body.script if isinstance(s, dict)]
        host.sim.set_director_script(host.script)
        host.save()
        return {"ok": True, "pending": len(host.sim.director_script)}

    @app.get("/api/intents")
    def get_intents():
        return {"intents": dict(host.intent_overrides),
                "names": dict(host.sim.camp_names),
                "factions": list(host.sim.factions),
                "defaults": dict(getattr(host.sim, "_intents", {}))}

    @app.post("/api/intents")
    def post_intents(body: IntentsBody):
        """导演部设置各参演方开局意图（下次重置推演时生效）。"""
        if body.intents is None:
            host.intent_overrides = {}
        else:
            for k, v in body.intents.items():
                if k in host.sim.camps:
                    host.intent_overrides[k] = v or ""
        host.save()
        return {"ok": True, "intents": dict(host.intent_overrides)}

    @app.get("/api/settings")
    def get_settings():
        return {
            "policy_mode": host.policy, "seed": host.seed, "speed": host.speed,
            "scenario": host.scenario,
            "weather_override": host.weather_override,
            "weather_options": [{"id": "auto", "name": "沿用想定"},
                                {"id": "clear", "name": "晴"},
                                {"id": "overcast", "name": "阴"},
                                {"id": "rain", "name": "雨"},
                                {"id": "storm", "name": "风暴"}],
            "scenarios": [{"id": k, "name": m.SCENARIO_NAME}
                          for k, m in SCENARIOS.items()],
            "friction": dict(host.sim.friction),
            # 合并引擎默认值：前端滑杆总能显示当前"有效值"，
            # 否则未调过的参数会停在滑杆中间值并误写回
            "tuning": {**DEFAULT_TUNING, **host.sim.tuning},
            "llm": {"available": llm_client.available, "model": llm_client.model,
                    "base_url": llm_client.base_url,
                    "temperature": llm_client.temperature,
                    "max_tokens": llm_client.max_tokens,
                    "budget": settings.max_llm_calls_per_tick,
                    "use_tools": settings.llm_use_tools,
                    "retry": settings.llm_retry,
                    "timeout": settings.llm_timeout,
                    "top_p": llm_client.top_p,
                    "frequency_penalty": llm_client.frequency_penalty,
                    "presence_penalty": llm_client.presence_penalty,
                    "fallback_enabled": settings.fallback_enabled},
        }

    @app.post("/api/settings")
    def post_settings(body: SettingsBody):
        if body.policy_mode in ("auto", "rule", "llm"):
            host.policy = body.policy_mode
        if body.seed is not None:
            host.seed = int(body.seed)
        if body.scenario and body.scenario in SCENARIOS:
            host.scenario = body.scenario
        if body.weather_override is not None:
            w = "auto" if body.weather_override == "" else body.weather_override
            if w in ("", "auto", "clear", "overcast", "rain", "storm"):
                host.weather_override = "" if w == "auto" else w
        # API Key 只写不读：前端不回显，留空表示保持不变
        if body.llm_base_url or body.llm_model or body.llm_api_key:
            llm_client.reconfigure(api_key=body.llm_api_key or None,
                                   base_url=body.llm_base_url or None,
                                   model=body.llm_model or None)
        # 智能体运行时/健壮性参数（原地生效，无需重置）
        if body.llm_use_tools is not None:
            settings.llm_use_tools = bool(body.llm_use_tools)
        if body.llm_retry is not None:
            settings.llm_retry = max(1, min(5, int(body.llm_retry)))
        if body.llm_timeout is not None:
            settings.llm_timeout = max(5, min(300, float(body.llm_timeout)))
        # 采样参数：原地生效，随请求下发（部分端点不支持则忽略）
        if body.llm_top_p is not None:
            llm_client.reconfigure(top_p=body.llm_top_p)
        if body.llm_frequency_penalty is not None:
            llm_client.reconfigure(frequency_penalty=body.llm_frequency_penalty)
        if body.llm_presence_penalty is not None:
            llm_client.reconfigure(presence_penalty=body.llm_presence_penalty)
        # LLM 失败容错开关（是否自动降级为规则策略）
        if body.fallback_enabled is not None:
            settings.fallback_enabled = bool(body.fallback_enabled)
        host.reset()
        host.save()
        return {"ok": True, "policy_mode": host.policy, "seed": host.seed,
                "scenario": host.scenario,
                "llm_available": llm_client.available}

    @app.post("/api/friction")
    def post_friction(body: FrictionBody):
        if body.latency_scale is not None:
            host.friction["latency_scale"] = max(0.5, min(4.0, body.latency_scale))
        if body.loss_rate is not None:
            host.friction["loss_rate"] = max(0.0, min(0.6, body.loss_rate))
        host.sim.friction.update(host.friction)
        host.save()
        return {"ok": True, "friction": dict(host.friction)}

    @app.post("/api/tuning")
    def post_tuning(body: TuningBody):
        data = body.model_dump(exclude_none=True)
        # LLM 运行参数路由到客户端/预算，其余进共享调参字典
        if "llm_temperature" in data:
            llm_client.reconfigure(temperature=data.pop("llm_temperature"))
        if "llm_max_tokens" in data:
            llm_client.reconfigure(max_tokens=data.pop("llm_max_tokens"))
        if "llm_budget" in data:
            settings.max_llm_calls_per_tick = max(1, min(200, int(data.pop("llm_budget"))))
        for k, v in data.items():
            lo, hi = _TUNING_CLAMPS.get(k, (0.0, 100.0))
            host.tuning[k] = max(lo, min(hi, v))
        host.sim.tuning.update(host.tuning)
        host.save()
        return {"ok": True, "tuning": dict(host.sim.tuning)}

    @app.post("/api/llm/test")
    def test_llm(body: LLMTestBody):
        """连接测试：携带候选端点先测后存；留空测已保存配置。测试不落库。"""
        import time
        saved = (llm_client.api_key, llm_client.base_url, llm_client.model)
        if body.api_key or body.base_url or body.model:
            llm_client.reconfigure(api_key=body.api_key or None,
                                   base_url=body.base_url or None,
                                   model=body.model or None)
        if not llm_client.available:
            llm_client.reconfigure(api_key=saved[0] or None, base_url=saved[1] or None,
                                   model=saved[2] or None)
            return {"ok": False, "model": llm_client.model,
                    "error": "未配置 API Key，无法测试连接"}
        t0 = time.perf_counter()
        raw, err = "", ""
        try:
            raw = llm_client.chat("你是连接测试助手。", "只回复两个字母：OK")
        except Exception as e:  # noqa: BLE001
            err = str(e)[:220]
        finally:
            ms = round((time.perf_counter() - t0) * 1000)
            llm_client.reconfigure(api_key=saved[0] or None, base_url=saved[1] or None,
                                   model=saved[2] or None)
            llm_client.reset_capture()
        if err:
            return {"ok": False, "model": body.model or saved[2],
                    "latency_ms": ms, "error": err}
        return {"ok": True, "model": body.model or saved[2],
                "latency_ms": ms, "reply": raw[:80]}

    @app.get("/api/debug/agents")
    def get_debug_agents(pos_id: str | None = None):
        """调试中心：各子智能体的实时内部状态快照（任务/记忆/信箱/局部状态）。"""
        return host.sim.agent_snapshot(pos_id)

    @app.get("/api/debug/tactical")
    def get_debug_tactical(side: str | None = None):
        """调试中心：一线战术Agent的实时状态与最近决策。
        每个作战Unit的局部感知、自主行动状态、上报记录均可观测。
        """
        sides = host.sim.factions if not side else [side]
        out = {}
        for s in sides:
            if s not in host.sim.camps:
                continue
            camp = host.sim.camps[s]
            out[s] = {
                "name": host.sim.camp_names.get(s, s),
                "agents": camp.tactical.snapshot(),
                "recent": camp.tactical.recent_decisions(limit=60),
            }
        return out

    @app.get("/api/debug/traces")
    def get_debug_traces(since: int = 0, limit: int = 100, pos: str | None = None):
        """调试中心：智能体决策轨迹。since=游标增量拉取，pos 可按职位过滤。"""
        traces = [t for t in host.sim.traces
                  if t["seq"] > since and (not pos or t["pos"] == pos)]
        return {"traces": traces[-limit:],
                "last_seq": host.sim._trace_seq,
                "total": len(host.sim.traces)}

    @app.get("/api/debug/export")
    def get_debug_export():
        """导出整场推演复盘 JSON：元信息 + 事件流 + 全部决策 trace + 智能体终态。

        供离线复盘/外部工具消费；也作为接外部可观测平台的中间数据格式。
        """
        return {
            "meta": {
                "scenario": host.sim.scenario_name,
                "policy": host.policy, "seed": host.seed,
                "ticks": host.sim.tick, "epoch": host.epoch,
                "factions": [{"id": s, "name": host.sim.camp_names.get(s, s)}
                             for s in host.sim.factions],
                "exported_at": __import__("datetime").datetime.now().isoformat(),
            },
            "tuning": dict(host.sim.tuning),
            "friction": dict(host.sim.friction),
            "events": host.sim.events,
            "traces": host.sim.traces,
            "agents": host.sim.agent_snapshot(),
        }

    @app.get("/api/stream")
    async def stream():
        async def gen():
            cursor = 0
            epoch_seen = host.epoch
            beats = 0
            while True:
                if host.epoch != epoch_seen:
                    epoch_seen = host.epoch
                    cursor = 0
                    yield ("data: " + json.dumps({"type": "reset", "epoch": host.epoch},
                                                 ensure_ascii=False) + "\n\n")
                for e in host.sim.events_since(cursor):
                    cursor = e["seq"]
                    yield "data: " + json.dumps(e, ensure_ascii=False) + "\n\n"
                beats += 1
                if beats % 60 == 0:
                    yield ": heartbeat\n\n"
                await asyncio.sleep(0.35)

        return StreamingResponse(gen(), media_type="text/event-stream",
                                 headers={"Cache-Control": "no-cache"})

    app.mount("/", StaticFiles(directory=str(STATIC_DIR), html=True), name="static")
    return app


# 支持 `uvicorn wargame.web.app:app` 直接启动
app = create_app()
