#!/usr/bin/env python3
"""bring-your-own-cloud-agent — BYOC personal agent planner + local state simulator.

Two jobs, zero network:
  1. PLAN      generate a deployment manifest (workers + DO + AI binding) for a
               personal agent on the user's OWN cloud account, plus a free-tier
               budget report (requests/day, DO storage, AI unit burn-down).
  2. SIMULATE  a local single-instance state machine that reproduces the key
               Durable-Object property worth borrowing for agent state: one
               instance, one writer, strictly sequential ops, persisted state
               (here: a JSON state file) — so you can test agent conversation
               + memory + task flows locally before touching any cloud.

All quota/pricing numbers are DEFAULTS the user can override; they are labeled
[estimated defaults, as of 2026-10-11] and exist for budget arithmetic only.
"""
from __future__ import annotations

import argparse
import json
import os
import sys

VERSION = "0.1.1"

# [estimated defaults, as of 2026-10-11] — override via CLI/tier files
FREE_TIERS = {
    "free": {
        "requests_per_day": 100_000,
        "durable_objects_storage_gb": 1.0,
        "ai_neurons_per_day": 10_000,
        "notes": "placeholder values; check your provider's current table",
    },
    "paid": {
        "requests_per_day": 10_000_000,
        "durable_objects_storage_gb": 50.0,
        "ai_neurons_per_day": 1_000_000,
        "notes": "placeholder values; check your provider's current table",
    },
}

STATES = ("idle", "thinking", "replying", "storing_memory", "running_task")
ALLOWED = {  # single-instance state machine transitions
    "idle":           {"thinking", "storing_memory"},
    "thinking":       {"replying", "running_task"},
    "replying":       {"storing_memory", "idle"},
    "storing_memory": {"idle"},
    "running_task":   {"replying", "idle"},
}


class PlanError(Exception):
    pass


# ---------------------------------------------------------------- plan

def plan(tier: str, expected_requests_per_day: int = 5000,
         expected_state_gb: float = 0.01,
         expected_ai_calls_per_day: int = 200) -> dict:
    if tier not in FREE_TIERS:
        raise PlanError(f"unknown tier {tier!r}; known: {list(FREE_TIERS)}")
    t = FREE_TIERS[tier]
    report = {
        "tier": tier,
        "headroom": {
            "requests": t["requests_per_day"] / max(expected_requests_per_day, 1),
            "do_storage": t["durable_objects_storage_gb"] / max(expected_state_gb, 1e-9),
            "ai_neurons": t["ai_neurons_per_day"] / max(expected_ai_calls_per_day * 50, 1),
        },
        "within_free_tier": (
            expected_requests_per_day <= t["requests_per_day"]
            and expected_state_gb <= t["durable_objects_storage_gb"]),
        "quotas_as_of": "2026-10-11",
        "quota_source": "[estimated defaults — replace with your provider's current table]",
    }
    manifest = {
        "manifest_version": VERSION,
        "bindings": [
            {"name": "AGENT_DO", "type": "durable_object",
             "rationale": "single-instance strong consistency fits a single-user agent state machine"},
            {"name": "AI", "type": "workers_ai_binding",
             "model_hint": "platform-included chat model"},
            {"name": "MEMORY", "type": "kv_or_do_storage",
             "rationale": "memory lives in YOUR account; exportable, deletable"},
        ],
        "endpoints": ["POST /chat", "GET /memory", "POST /task"],
        "ownership": "deployed under the user's own account; no vendor-operated state",
    }
    return {"budget_report": report, "deployment_manifest": manifest}


# ---------------------------------------------------------------- local simulate

class AgentStateSim:
    """Local single-instance agent state machine, persisted to JSON."""

    def __init__(self, state_path: str):
        self.state_path = state_path
        self.state = {"state": "idle", "history": [], "memory": [], "tasks": []}
        if os.path.exists(state_path):
            try:
                with open(state_path, encoding="utf-8") as f:
                    self.state = json.load(f)
            except (json.JSONDecodeError, OSError) as exc:
                raise PlanError(f"corrupted state file: {exc}") from exc

    def op(self, kind: str, payload: str = "") -> dict:
        if kind not in ("chat", "remember", "task"):
            raise PlanError(f"unknown op {kind!r}")
        cur = self.state["state"]
        nxt = {"chat": "thinking", "remember": "storing_memory",
               "task": "thinking"}[kind]
        if nxt not in ALLOWED[cur]:
            raise PlanError(f"illegal transition {cur} -> {nxt} (single-writer machine)")
        self.state["state"] = nxt
        if kind == "remember":
            if not payload.strip():
                raise PlanError("empty memory text")
            self.state["memory"].append(payload)
        elif kind == "task":
            self.state["tasks"].append({"desc": payload, "done": False})
        self.state["state"] = "replying" if kind != "remember" else "idle"
        self.state["history"].append({"op": kind, "payload": payload[:80]})
        if kind != "remember":
            self.state["state"] = "idle"
        self._persist()
        return {"op": kind, "state_after": self.state["state"]}

    def _persist(self):
        with open(self.state_path, "w", encoding="utf-8") as f:
            json.dump(self.state, f)

    def finish_task(self, index: int) -> dict:
        try:
            self.state["tasks"][index]["done"] = True
        except (IndexError, TypeError):
            raise PlanError(f"no task at index {index}") from None
        self._persist()
        return {"task": index, "done": True}

    def snapshot(self) -> dict:
        return {"state": self.state["state"], "memories": len(self.state["memory"]),
                "tasks": len(self.state["tasks"]),
                "open_tasks": sum(1 for t in self.state["tasks"] if not t.get("done"))}


# ---------------------------------------------------------------- CLI

def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(prog="bring-your-own-cloud-agent",
                                description="plan a BYO-cloud personal agent; simulate its state machine locally")
    sub = p.add_subparsers(dest="cmd", required=True)
    pl = sub.add_parser("plan", help="budget report + deployment manifest")
    pl.add_argument("--tier", default="free", choices=sorted(FREE_TIERS))
    pl.add_argument("--requests", type=int, default=5000)
    pl.add_argument("--state-gb", type=float, default=0.01)
    pl.add_argument("--ai-calls", type=int, default=200)
    sim = sub.add_parser("simulate", help="run ops against the local state machine")
    sim.add_argument("--ops", nargs="*",
                     help="ops like chat:hello remember:note task:buy-milk finish_task:0")
    sim.add_argument("--state", default="agent_state.json")
    sub.add_parser("snapshot", help="show sim state counts (needs --state)")
    p.add_argument("--state", default="agent_state.json", help=argparse.SUPPRESS)

    a = p.parse_args(argv)
    try:
        if a.cmd == "plan":
            print(json.dumps(plan(a.tier, a.requests, a.state_gb, a.ai_calls), indent=2))
        elif a.cmd == "simulate":
            s = AgentStateSim(a.state)
            for spec in a.ops or []:
                if ":" in spec:
                    kind, payload = spec.split(":", 1)
                else:
                    kind, payload = spec, ""
                if kind == "finish_task":
                    print(json.dumps(s.finish_task(int(payload))))
                else:
                    print(json.dumps(s.op(kind, payload)))
        elif a.cmd == "snapshot":
            print(json.dumps(AgentStateSim(a.state).snapshot(), indent=2))
        return 0
    except (PlanError, ValueError) as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    sys.exit(main())
