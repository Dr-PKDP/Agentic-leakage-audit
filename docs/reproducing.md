# Reproducing the results

## Offline replay

```
python reproduce.py [--out DIR]
```

The command first verifies every file listed in `MANIFEST.json`. A missing or altered file stops the run. It then replays three archives.

Principal run. The 384 request payloads are rebuilt from the plan, the jobs and the saved review text, and the saved responses are passed through the unchanged parser, the gates and the evaluator. All 192 scored units and 48 reference assessments must match the archived records exactly, and the rule reference is regenerated for the 24 contexts. Outputs: `principal_outcomes.csv`, `principal_requests.csv` and `posthoc_rule_reference.json`.

Pilot. The original scorer is applied to the 90 initial and final responses in the 135-request ledger, and the claims-label normalization is recomputed separately. Output: `pilot_replayed_scores.json`.

Fixed reference. The configuration, runner and four numerical modules are checked against the hashes in the archived report, and the six recorded metric rows are exported. The replay does not refit the model. Output: `recorded_reference_metrics.csv`.

`summary.json` collects the totals. After a deliberate change to a tracked file, `python reproduce.py --write-manifest` regenerates the manifest.

## Re-scoring the schema audit

```
python analysis/schema_audit.py
```

This reads `nhanes/metadata/` and rewrites `results/nhanes/schema_audit.json` and `schema_audit_reference.csv`. The expected totals are 33 of 80 reference pairs flagged.

## Sensitivity analyses

```
python analysis/sensitivity.py
```

This recomputes four analyses of the principal run from the archived records and writes `results/principal_v0_4/sensitivity.json`: outcomes by whether the review stopped at the output limit, selections compared with the rule reference, paired contrasts between paths (exact McNemar tests, context-level bootstrap with 5,000 resamples and a fixed seed), and rates with each constraint family left out in turn. The output is deterministic and corresponds to Supplementary Table S7.

## Refitting the fixed reference

The refit uses the public DEMO_J and DPQ_J files from the NHANES 2017–2018 cycle. It needs Python 3.11 and the packages pinned in `experiments/pilot_depression/requirements-reference.lock.txt`.

| File | SHA-256 |
|---|---|
| DEMO_J.xpt | c0b46e0345ea19404928656277c8b0d10b0cca348a9b2fe4fc3c67e8b7ee73ec |
| DPQ_J.xpt | 1c075f332e79736bd2360b41b0c10ed526883417e0b5996c407b1c564b01ca24 |

```
python reproduce.py --check-inputs --demo DEMO_J.xpt --dpq DPQ_J.xpt
python reproduce.py --allow-fit --demo DEMO_J.xpt --dpq DPQ_J.xpt --out DIR
```

The first command only compares file hashes. The second regenerates the predictor and fold audit from the files, adapts the two path assignments in the original runner in memory, runs it, and compares the six aggregate metrics with the archived report at a tolerance of 1e-10. Cohort, preprocessing, folds, estimator and metric code are not changed. Timestamps and the hash of the original prior-audit file are not reproduced. This path is not covered by the test suite because the raw files are not part of the repository. Running it is a new local fit and requires whatever data-use authorization applies to the files.

## Generating new model responses

The replay never contacts a model. Generation programs need a served model, an explicit model identifier and, where the endpoint requires one, a token in `OPENAI_API_KEY`. Every generation command takes the plan hash as an explicit argument, makes no retries, never resumes and never overwrites an output directory.

Principal runner:

```
cd experiments/principal_v0_4
python p6_integrated_development_v0_4.py check
python p6_integrated_development_v0_4.py prepare --output-dir PLAN_DIR
python p6_integrated_development_v0_4.py run --plan-dir PLAN_DIR --output-dir RUN_DIR --approve-plan-hash HASH
```

The plan fixes the endpoint `http://127.0.0.1:8010/v1` and the model identifier `p6-qwen3-8b`. The archived plan in this directory has canonical hash `0e8f19089e1c30abd239e31980645f17a566369e37422b58228389a7f5d74250`, and the runner has SHA-256 `1649d94540600146e4f562c48525b68f82813b2fa6e360c8fa881bbdb8b7cb83`.

Extended package:

```
export P6_MODEL=<served model id>
export P6_BASE_URL=<endpoint>/v1
bash experiments/extended_v0_5/run_extended.sh
```

| Variable | Meaning |
|---|---|
| `P6_MODEL`, `P6_BASE_URL` | required model identifier and endpoint |
| `OPENAI_API_KEY` | bearer token, never printed |
| `P6_OUT` | output root, default `outputs/extended_v0_5` |
| `P6_WORKERS` | concurrent requests, default 8 |
| `P6_ORIGINAL_RUNS` | run directories to scan for reasoning output and truncation |
| `P6_CONFIRM=yes` | skip the interactive confirmation |
| `P6_MODEL2`, `P6_BASE_URL2` | add think-off arms for a second served model |

The three arms are `nhanes_default` (17 contexts, server-default thinking, seeds 42 and 43, 544 requests), `core24_think_off` (24 contexts, thinking off, seed 42, 384 requests) and `nhanes_think_off` (17 contexts, thinking off, seeds 42 and 43, 544 requests). Each arm writes a plan, request log, run records and, after analysis, `outcomes.csv` and `summary.json`. Name-prefix rule results for the 17 contexts are scored offline as a fixed comparison row.

The scripts in `experiments/extended_v0_5` import the principal runner from `experiments/principal_v0_4`, so they run through `run_extended.sh`, or with that directory on `PYTHONPATH`.

## Tests

```
pip install -r requirements.txt
pytest
```

The suite covers the lineage rules, the offline replay and the schema audit, the extended pipeline against a mock server, and the numerical modules of the depression reference.
