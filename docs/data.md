# Data dictionary

## `experiments/principal_v0_4`

| File | Content |
|---|---|
| `p6_integrated_development_v0_4.py` | Runner with `check`, `prepare` and `run` commands. The plan records its SHA-256. |
| `plan.json` | Generation plan: model, endpoint, seeds, temperature, token limit, request budget, hashes of the job manifest and the runner. Canonical SHA-256 `0e8f1908…d74250`. |
| `jobs.json` | 192 jobs. Each holds the context, the initial proposal, the stream, the review messages and the revision task. |
| `references.json` | 48 assessments of the initial proposals, keyed by proposal identifier. |
| `request_ledger.json` | All 384 requests with payload hash, client duration, finish reason and the full response. |
| `units.json` | 192 scored workflow units keyed by unit name (`<proposal>__<stream>__<seed>`), with initial assessment, final artifact or paired patch paths, and final assessment. |
| `run_report.json` | Run status and scope flags. |

Verdicts are `supported`, `contradicted_contract` and `insufficient_evidence`. Pipeline states in `units.json` include `schema_failure` and `not_evaluated` for output that did not reach the evaluator.

## `results/principal_v0_4`

| File | Columns or content |
|---|---|
| `outcomes.csv` | One row per workflow path: `known_error_repairs_of_21`, `supported_retained_of_24`, `observed_harmful_changes`, `supported_outputs_of_48`, `unparseable_of_48`, `schema_failures_of_48`. |
| `resources.csv` | One row per stream: requests, prompt, completion and total tokens, summed client seconds, reviews that stopped at the length limit. |
| `summary.json` | Run totals, initial-state counts, the paired gate effect and the plan hash. |
| `failure_audit.json` | Audit of the five revisions that failed to parse or validate, with finish reasons and token counts. |
| `replay_check.json` | Record of the first replay: hashes of the source exports and the runner, and the checks passed. |

`results/principal_v0_4/sensitivity.json` holds the output of `analysis/sensitivity.py` (truncation strata, selection quality, paired contrasts, leave-one-family-out rates).

Client seconds are measured around each request on a shared machine and include queueing. They are not GPU time or wall-clock time.

## `experiments/extended_v0_5`

| File | Content |
|---|---|
| `p6_extended_v0_5.py` | `check`, `prepare` and `run`. Defines the 17 F07 contexts, the thinking switch, the F07 evidence gate and the fixed prefix-rule reviser. Imports the principal runner unchanged and verifies its hash. |
| `p6_extended_analyze.py` | Offline analysis of one arm. Writes `outcomes.csv` (one row per input and path, including the prefix-rule row) and `summary.json`. |
| `p6_scan_requests.py` | Counts finish reasons, completion tokens, reasoning fields and think tags in saved request logs. Prints no prompt or response text. |
| `run_extended.sh` | Launcher for the three arms. |

`outcomes.csv` columns: `unit`, `proposal_id`, `context_id`, `rule_id`, `family`, `archetype`, `seed`, `initial`, `status`, `path`, `final`, `pipeline`, `action`, `retained_fraction`. For F07 contexts `retained_fraction` is the share of the reference-valid features that appear in the final selection.

## `experiments/pilot_depression`

| Path | Content |
|---|---|
| `scripts/run_depression_agent_comparison_v1.py` | Pilot runner: three scenarios, five seeds, three workflows, 135 requests. |
| `scripts/analyze_depression_claims_sensitivity_v1.py` | Rescoring in which a scalar claims string that equals an allowed label becomes a one-element list. |
| `scripts/run_depression_reference_v1.py` | Fixed three-arm reference (primary, age and gender, intercept only) with grouped five-fold evaluation on NHANES 2017–2018. |
| `scripts/audit_depression_*` | Predictor and split audits that the refit regenerates. |
| `src/` | Preprocessing, baseline and secondary estimators, execution contract checks, proposal checks. |
| `configs/` | Versioned configurations; `nhanes_depression_dev_v7.json` is the one the archived report used. |
| `outputs/agent_comparison/<run>/` | Pilot configuration, provenance, 135 logged requests (`requests.jsonl`), 45 unit records, the post hoc rescoring and the changed-status sequences. |
| `outputs/reference_evaluation/<run>/run_report.json` | Cohort counts, fold sizes and six metric rows (AUROC, Brier score and log loss, weighted and unweighted). Aggregate only. |

The reference report contains no participant-level predictions and no fitted model. It records no confidence intervals, and its weighted point estimates are not a complex-survey analysis.

## `nhanes`

| Path | Content |
|---|---|
| `input_manifest.csv` | 90 file entries: cycle, suffix, split, file, download URL, codebook URL. |
| `data_use_policy.json` | Development and locked cycles and prohibited operations before freeze. |
| `acquire.py`, `extract_schema.py`, `build_harmonization.py` | Download with checksum logging, schema extraction, cross-cycle harmonization table. |
| `metadata/development_schema.csv` | 1,489 variable–file rows: cycle, split, file, variable, dtype. |
| `metadata/cross_cycle_harmonization.csv` | 571 variable names per component with the cycles they appear in. |
| `provenance/` | Acquisition log and inventory (54 files with byte counts and SHA-256) and the schema extraction report. |

Rebuilding the tables requires the raw XPT files, which are not stored here. From the repository root:

```
python nhanes/acquire.py --manifest nhanes/input_manifest.csv --split development --output data/raw/development --log nhanes/provenance/acquisition_log.jsonl --inventory nhanes/provenance/acquisition_inventory.csv
python nhanes/extract_schema.py --inventory nhanes/provenance/acquisition_inventory.csv --raw-dir data/raw/development --output nhanes/metadata/development_schema.csv --report nhanes/provenance/schema_extraction_report.csv
python nhanes/build_harmonization.py --schema nhanes/metadata/development_schema.csv --output nhanes/metadata/cross_cycle_harmonization.csv
```
