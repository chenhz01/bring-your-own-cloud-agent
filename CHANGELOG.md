# Changelog

## v0.1.1 (2026-10-11) — self-review revision (iteration 2)

- **Correctness (+~30%, the iteration's focus)**: honesty pass on quota numbers — all tier constants demoted to `[estimated defaults]` with explicit `quotas_as_of` and `quota_source` fields in the budget report; README no longer implies "free tier fits" as a fact, only as a Medium-confidence claim to verify.
- **Completeness**: added Minimal Fallback (the simulator itself as a deploy-free agent state machine) and second-order effects (account-compromise concentration; abandoned DO state).
- **Correctness (code)**: self_test gained C1 (budget overflow → within_free_tier False) and C4 (corrupted state via CLI → rc=2).

## v0.1.0 (2026-10-11) — initial draft

- `plan` subcommand: tier budget report + deployment manifest (DO + workers-AI + memory bindings).
- `simulate`/`snapshot`: local single-writer agent state machine persisted to JSON.
- self_test with functional / error-path / edge classes (21 checks).
