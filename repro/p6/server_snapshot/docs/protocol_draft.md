# P6 protocol draft

Status: DEVELOPMENT ONLY — NOT FROZEN

## Scope
Develop and evaluate a guarded proposal-generation workflow for
disease-prediction analyses using public population-survey data.

This project is separate from Arbiter. Do not reuse Arbiter data,
credentials, configurations, or experimental results.

## Completed development checks
- Local Qwen3-8B inference through vLLM.
- Schema-constrained JSON generation and parsing.
- One fictional planner–critic–revision example.
- Two observed contradictory critic approvals in that example.
- Deterministic consistency checks that blocked those approvals.
- Eight passing test methods against the reusable pilot_v2 gate.

These checks are software-development evidence, not benchmark results.

## Model-serving configuration observed in development
- Model repository: Qwen/Qwen3-8B
- Served name: p6-qwen3-8b
- vLLM version: 0.32.0
- Context limit: 1024 tokens
- Maximum concurrent sequences: 1
- GPU memory utilization setting: 0.12
- Eager execution enabled
- Thinking disabled
- Model revision identifier: NOT YET RECORDED

These settings are not automatically suitable for the final experiment.

## Decisions required before research runs
- Dataset and exact release/cycles.
- Disease task and outcome definition.
- Prediction time and intended use.
- Eligible population and exclusions.
- Predictor availability and prohibited variables.
- Development, validation, and final test assignments.
- Survey weights and design variables, where applicable.
- Metrics and uncertainty-estimation methods.
- Agent roles, prompts, schemas, and permitted actions.
- Baselines, seeds, run budgets, and stopping rules.
- Independent review criteria and evaluation labels.

## Guard boundaries
- JSON validity is not scientific validity.
- The consistency gate checks decision consistency only.
- Missing or malformed reviews must not authorize execution.
- Generated proposals must not automatically execute code.
- Preserve original requests, responses, reviews, and gate results.
- Record revisions separately.
- Keep development examples separate from final evaluation cases.

## Current authorization
No real-data modelling or autonomous code execution is authorized
by this draft.

## Next milestone
Select one dataset/task and specify its metadata before constructing
a real proposal-generation request.
