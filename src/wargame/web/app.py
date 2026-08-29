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

STATIC_DIR = Path(__file__).parent / "static"


class ControlBody(BaseModel):
    """推演控制请求。注意必须定义在模块层：本项目开了 PEP 563 惰性注解，
    FastAPI 解析闭包内局部类的注解会失败并退化为 query 参数。"""

    action: str  # start / pause / step / reset / speed
    speed: float | None = None


class IntentBody(BaseModel):
    side: str
    text: str


class SettingsBody(BaseModel):
    """推演设置：策略/种子/场景需重置生效；LLM 配置原地生效。"""

    policy_mode: str | None = None
    seed: int | None = None
    scenario: str | None = None
    llm_base_url: str | None = None
    llm_model: str | None = None
    llm_api_key: str | None = None


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
    llm_temperature: float | None = None
    llm_max_tokens: int | None = None
    llm_budget: int | None = None


_TUNING_CLAMPS = {
    "combat_scale": (0.1, 5.0), "arty_scale": (0.1, 5.0),
    "entrench_bonus": (0.0, 1.0), "terrain_def_scale": (0.0, 2.0),
    "supply_regen": (0.0, 20.0), "supply_drain": (0.0, 15.0),
    "depot_radius": (2, 16), "recon_scale": (0.3, 4.0), "intel_error": (0, 3),
    "move_scale": (0.3, 4.0), "report_interval": (2, 48),
    "withdraw_threshold": (5, 90), "contact_fwd_interval": (1, 24),
}


class SimHost:
    """持有当前仿真实例与后台推进循环。

    friction 保存在 host 层而不是仿真层——重置推演后摩擦参数得以延续。
    """

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
        self.sim = self._build()

    def _build(self) -> Simulation:
        sim = Simulation(policy_mode=self.policy, seed=self.seed,
                         scenario=self.scenario, tuning=self.tuning)
        sim.friction.update(self.friction)
        return sim

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

    app = FastAPI(title="Sandtable 指挥协同推演", lifespan=lifespan)

    @app.get("/api/scenarios")
    def list_scenarios():
        return [{"id": k, "name": m.SCENARIO_NAME} for k, m in SCENARIOS.items()]

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

    @app.get("/api/settings")
    def get_settings():
        return {
            "policy_mode": host.policy, "seed": host.seed, "speed": host.speed,
            "scenario": host.scenario,
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
                    "budget": settings.max_llm_calls_per_tick},
        }

    @app.post("/api/settings")
    def post_settings(body: SettingsBody):
        if body.policy_mode in ("auto", "rule", "llm"):
            host.policy = body.policy_mode
        if body.seed is not None:
            host.seed = int(body.seed)
        if body.scenario and body.scenario in SCENARIOS:
            host.scenario = body.scenario
        # API Key 只写不读：前端不回显，留空表示保持不变
        if body.llm_base_url or body.llm_model or body.llm_api_key:
            llm_client.reconfigure(api_key=body.llm_api_key or None,
                                   base_url=body.llm_base_url or None,
                                   model=body.llm_model or None)
        host.reset()
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
        return {"ok": True, "tuning": dict(host.sim.tuning)}

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
