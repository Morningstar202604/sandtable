"""命令行入口：headless 推演 / Web 控制台。"""

from __future__ import annotations

import argparse
import sys


def _setup_stdio() -> None:
    # Windows 控制台默认 GBK，中文输出会炸，强制 UTF-8
    try:
        sys.stdout.reconfigure(encoding="utf-8")
        sys.stderr.reconfigure(encoding="utf-8")
    except Exception:  # noqa: BLE001  非 tty 场景可能无此方法
        pass


def cmd_run(args: argparse.Namespace) -> None:
    from .sim import Simulation

    sim = Simulation(policy_mode=args.policy, seed=args.seed,
                     default_intents=not args.no_intents, scenario=args.scenario)
    print(f"场景：{sim.scenario_name} | 策略：{sim.policy_mode} | 种子：{sim.seed}")
    cursor = 0
    for _ in range(args.ticks):
        sim.run_tick()
        for e in sim.events_since(cursor):
            cursor = e["seq"]
            t, et = e["t"], e["type"]
            if et == "msg":
                print(f"T{t:03d} [{e['camp']}] {sim.registry.title(e['sender'])}"
                      f" → {sim.registry.title(e['recipient'])}"
                      f" 〈{e['kind']}〉{e['subject']}")
            elif et == "combat":
                print(f"T{t:03d} [{e['camp']}] ⚔ {e.get('name', e['unit'])}"
                      f" 损失{e['taken']}（对{'、'.join(e['vs'])}）")
            elif et == "fire":
                print(f"T{t:03d} [{e['camp']}] ▲ {e.get('name', e['unit'])}"
                      f" 炮击 {e.get('target_name', e['target'])} 损失{e['dmg']}")
            elif et == "destroyed":
                print(f"T{t:03d} [{e['camp']}] ✝ {e['name']} 全损")
            elif et == "intel":
                print(f"T{t:03d} [{e['camp']}] ◎ 侦察发现 {e['n']} 个目标")
            elif et == "isolation_blocked":
                print(f"T{t:03d} [{e['camp']}] ⛔ 隔离拦截：{e.get('reason') or e.get('detail')}")
            elif et == "action":
                print(f"T{t:03d} [{e['camp']}] → {e['unit']} {e['kind']} {e['target'] or ''}")
            elif et == "tactical":
                state_name = {"engaging": "接战", "defending": "防御",
                              "withdrawing": "后撤", "advancing": "推进",
                              "holding": "待命"}.get(e.get("state", ""), e.get("state", ""))
                print(f"T{t:03d} [{e['camp']}] ◆ {e.get('name', e['unit'])} "
                      f"自主{e['kind']} {e.get('target') or ''} [{state_name}]")
            elif et == "tactical_rejected":
                print(f"T{t:03d} [{e['camp']}] ◆ {e['unit']} 自主行动被拒 {e['kind']}")
    print(f"完成：{sim.tick} ticks，事件 {sim.seq} 条。日志：{sim.run_dir / 'events.jsonl'}")


def cmd_serve(args: argparse.Namespace) -> None:
    import uvicorn

    from .web.app import create_app

    uvicorn.run(create_app(policy=args.policy, seed=args.seed, scenario=args.scenario),
                host=args.host, port=args.port, log_level="warning")


def main() -> None:
    _setup_stdio()
    parser = argparse.ArgumentParser(prog="wargame", description="指挥协同推演系统")
    sub = parser.add_subparsers(dest="cmd", required=True)

    p_run = sub.add_parser("run", help="headless 跑推演")
    p_run.add_argument("--ticks", type=int, default=40)
    p_run.add_argument("--policy", choices=["auto", "rule", "llm"], default="auto")
    p_run.add_argument("--seed", type=int, default=None)
    p_run.add_argument("--scenario", default=None, help="场景 id（cross_river / normandy）")
    p_run.add_argument("--no-intents", action="store_true", help="不注入默认意图")
    p_run.set_defaults(fn=cmd_run)

    p_srv = sub.add_parser("serve", help="启动 Web 控制台")
    p_srv.add_argument("--host", default="127.0.0.1")
    p_srv.add_argument("--port", type=int, default=8300)
    p_srv.add_argument("--policy", choices=["auto", "rule", "llm"], default="auto")
    p_srv.add_argument("--seed", type=int, default=None)
    p_srv.add_argument("--scenario", default=None, help="场景 id（cross_river / normandy）")
    p_srv.set_defaults(fn=cmd_serve)

    args = parser.parse_args()
    args.fn(args)


if __name__ == "__main__":
    main()
