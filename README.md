# bring-your-own-cloud-agent

A planner + local simulator for running a personal AI agent on **your own** cloud account — chat, memory, and tasks with zero subscription and no vendor-held state. If "agent as a service" feels wrong to you, plan it BYO-cloud here and test its state machine locally first.

**Confidence: High (≥80%)** for the architecture claim: a single-instance durable-object primitive is a natural fit for a single-user agent state machine (one writer, sequential ops, persisted state — reproduced locally by the simulator). **Confidence: Medium (60–79%)** that platform free tiers sustainably cover a personal agent — quota tables change; the planner reads *your* numbers, not ours.

## Problem

Hosted agent subscriptions bundle three things you may not want: a recurring bill, a vendor-operated copy of your conversation history, and a ceiling on customization. Self-hosting a full stack fixes ownership but adds an ops tax most individuals don't want to pay.

The overlooked angle: you don't need to *run* infrastructure to *own* it. Modern serverless platforms include a primitive — a single-instance, strongly-consistent durable object — that happens to match a single-user agent's needs exactly: one instance, one writer, sequential operations, persisted state. Deploy on your own account, bind the platform's included AI model, keep memory in your own storage: the agent runs at free-tier cost and every byte stays in your account. Nothing here substitutes for reading your provider's current quota table — all numbers in this repo are `[estimated defaults]`.

## How it works

Two offline tools:

1. **Planner** (`plan`): takes your expected daily load (requests, state GB, AI calls) and emits (a) a budget report with headroom against a tier table you can override, and (b) a deployment manifest — durable-object binding for state, workers-AI binding for the model, KV/DO storage for memory — as a spec you implement against your provider.
2. **Simulator** (`simulate`): a local single-writer state machine (`idle → thinking → replying → storing_memory → idle`) persisted to JSON. It reproduces the cloud primitive's discipline — sequential ops, explicit transitions, durable state — so conversation/memory/task flows can be tested before any deploy.

## Quickstart

Stage 1 — plan a deployment (~5 s):

```bash
python byoc_agent.py plan --tier free --requests 5000 --state-gb 0.01 --ai-calls 200
```

Stage 2 — simulate a day of agent ops locally (~5 s):

```bash
python byoc_agent.py simulate --state demo.json --ops chat:hi remember:deploy-on-own-account task:buy-milk finish_task:0
python byoc_agent.py snapshot --state demo.json
python self_test.py        # ~4 s, 21 checks
```

## Why not X

| Alternative | Why not | What we keep instead |
|---|---|---|
| Hosted agent SaaS | Subscription + vendor-held history + customization ceiling | Your account, your data, your model binding |
| Full self-host (VPS + DB + model server) | Ops tax: patching, backups, uptime — for one user | Serverless on your account; platform operates the boring parts |
| Pure client-side agent | No shared state across devices; secrets in the browser | Small server-side state in *your* DO, accessed by any client |

## Minimal Fallback

No cloud account yet? The simulator **is** the fallback: `simulate` + `snapshot` give you a working single-writer agent state machine on a JSON file, no deployment needed. Design against the manifest's endpoint shape (`POST /chat`, `GET /memory`, `POST /task`) and swap the local JSON for a DO later without changing callers.

## Design Trade-offs

Priority: **ownership > zero-recurring-cost > simplicity > scale**. Consequences:

- Single-user assumption is baked in (one DO instance, no multi-tenancy). Don't fight it; shard per user if you must.
- Manifest-first, not SDK-first: this repo won't deploy anything for you. It fixes *what* to deploy so you can't drift into vendor-coupled glue.
- Quota tables live as overridable defaults, explicitly `[estimated]` — correctness of your budget is your provider's table, not our constants.

## Limits & Second-order Effects

- Free tiers change; a config that fits today may bill tomorrow — the budget report marks its `quotas_as_of` date; re-check before relying on it.
- Second-order effect: "it's on my account" can breed over-trust — your cloud account becomes a single point of compromise for all agent history. Enable platform MFA and treat the state store as sensitive.
- Second-order effect: free-tier agents make throwaway agents too easy; abandoned DO state accumulates silently. Schedule exports/deletions.
- The simulator's transition table is stricter than real platforms; flows that pass locally may still need platform-specific review.

## FAQ

**Q: Does this deploy to the cloud for me?**
A: No. It plans and simulates. Deployment is ~50 lines against your provider once the manifest is fixed — deliberately outside this repo so it can't bit-rot with provider SDKs.

**Q: Which model does it use?**
A: Whatever your platform includes in its AI binding. The manifest specifies the binding, not the model, so the plan survives model churn.

**Q: When you should NOT use this tool?**
A: If you need multi-tenant agents, heavy GPU inference, or compliance regimes requiring dedicated infrastructure — single-instance serverless is the wrong shape. Also skip this if you'd rather pay a SaaS and never think about quotas; that's a legitimate trade.

## [Core Assumptions]

1. A single-user agent maps cleanly onto a single-instance sequential state machine.
2. Platform free tiers are adequate for personal-scale request/AI volumes (verify against current tables — `[estimated defaults, as of 2026-10-11]` here).
3. Memory belongs in user-owned storage, exportable and deletable on demand.
4. Manifest-first planning beats copy-paste deploy scripts for durability against provider changes.

---

Quota figures are `[estimated defaults]` for budget arithmetic only — always verify against your provider's current table. As of 2026-10-11. License: MIT (zhengming contributors).
