#!/usr/bin/env python3
"""self_test for bring-your-own-cloud-agent. Three classes (rule 97).
Run: python self_test.py
"""
import json
import os
import sys
import tempfile

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import byoc_agent as m  # noqa: E402

RESULTS = []


def check(name, cond, detail=""):
    RESULTS.append((name, bool(cond), detail))


def main() -> int:
    td = tempfile.mkdtemp()

    # ---------------- A. functional
    out = m.plan("free", expected_requests_per_day=5000,
                 expected_state_gb=0.01, expected_ai_calls_per_day=200)
    check("A1 plan returns budget+manifest",
          "budget_report" in out and "deployment_manifest" in out)
    check("A2 headroom computed", out["budget_report"]["headroom"]["requests"] == 20)
    check("A3 manifest binds DO+AI+memory",
          {b["type"].split("_")[0] for b in out["deployment_manifest"]["bindings"]}
          >= {"durable", "workers", "kv"})
    st = os.path.join(td, "state.json")
    s = m.AgentStateSim(st)
    check("A4 starts idle", s.state["state"] == "idle")
    r = s.op("remember", "deploy on own account")
    check("A5 remember persists memory", r["state_after"] == "idle"
          and len(s.state["memory"]) == 1)
    s.op("chat", "hello")
    s.op("task", "buy-milk")
    snap = s.snapshot()
    check("A6 snapshot counts open tasks", snap["tasks"] == 1
          and snap["open_tasks"] == 1)
    s2 = m.AgentStateSim(st)  # reload = persisted state
    check("A7 state file round-trips", s2.snapshot()["tasks"] == 1)
    check("A8 finish_task marks done", s2.finish_task(0)["done"] is True
          and s2.snapshot()["open_tasks"] == 0)

    # ---------------- B. error paths
    try:
        m.plan("gold-tier")
        check("B1 unknown tier raises", False)
    except m.PlanError:
        check("B1 unknown tier raises", True)
    try:
        m.AgentStateSim(st).op("bogus")
        check("B2 unknown op raises", False)
    except m.PlanError:
        check("B2 unknown op raises", True)
    try:
        m.AgentStateSim(st).op("remember", "   ")
        check("B3 empty memory rejected", False)
    except m.PlanError:
        check("B3 empty memory rejected", True)
    try:
        m.AgentStateSim(st).finish_task(99)
        check("B4 out-of-range task raises", False)
    except m.PlanError:
        check("B4 out-of-range task raises", True)
    corrupt = os.path.join(td, "corrupt.json")
    with open(corrupt, "w") as f:
        f.write("{broken")
    try:
        m.AgentStateSim(corrupt)
        check("B5 corrupted state file rejected", False)
    except m.PlanError:
        check("B5 corrupted state file rejected", True)

    # ---------------- C. extreme edges
    check("C1 huge request budget overflows flag",
          m.plan("free", expected_requests_per_day=10**9)["budget_report"]["within_free_tier"] is False)
    s3 = m.AgentStateSim(os.path.join(td, "empty_ops.json"))
    check("C2 zero ops snapshot is idle/empty",
          s3.snapshot() == {"state": "idle", "memories": 0, "tasks": 0, "open_tasks": 0})
    huge = "x" * 100_000
    s3.op("remember", huge)
    check("C3 100KB memory accepted and persisted",
          len(m.AgentStateSim(os.path.join(td, 'empty_ops.json')).state["memory"][0]) == 100_000)
    rc = m.main(["simulate", "--state", corrupt, "--ops", "chat:hi"])
    check("C4 CLI surfaces corrupted state as rc=2", rc == 2)
    check("C5 CLI plan runs", m.main(["plan", "--tier", "free"]) == 0)
    legal = m.ALLOWED["idle"]
    check("C6 transition table is conservative (idle→thinking/memory only)",
          legal == {"thinking", "storing_memory"})

    fails = [r for r in RESULTS if not r[1]]
    for name, ok, detail in RESULTS:
        print(f"[{'PASS' if ok else 'FAIL'}] {name}" + (f"  ({detail})" if detail else ""))
    print(f"\ntotal={len(RESULTS)} pass={len(RESULTS)-len(fails)} fail={len(fails)}")
    print("repro: python self_test.py")
    return 1 if fails else 0


if __name__ == "__main__":
    sys.exit(main())
