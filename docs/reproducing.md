# Reproducing the results

## Offline replay

```
python reproduce.py [--out DIR]
```

The command first verifies every file listed in `MANIFEST.json`. A missing or altered file stops the run. It then replays three archives.

Core contexts. The 384 request payloads are rebuilt from the plan, the jobs and the saved review text, and the saved responses are passed through the unchanged parser, the gates and the evaluator. All 192 scored units and 48 reference assessments must match the archived records exactly, and the rule reference is regenerated for the 24 contexts. Outputs: `principal_outcomes.csv`, `principal_requests.csv` and `posthoc_rule_reference.json`.

Preliminary study. The original scorer is applied to the 90 initial and final responses in the 135-request ledger, and the claims-label normalization is recomputed separately. Output: `pilot_replayed_scores.json`.

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

This recomputes four analyses of the core-context run from the archived records and writes `results/core_contexts/sensitivity.json`: outcomes by whether the review stopped at the output limit, selections compared with the rule reference, paired contrasts between paths (exact McNemar tests, context-level bootstrap with 5,000 resamples and a fixed seed), and rates with each constraint family left out in turn. The output is deterministic and corresponds to Supplementary Table S7.

## Extended and longer-limit runs

```
python analysis/extended_stats.py
python analysis/longlimit_stats.py
```

The first script recomputes, from `results/label_contexts/`, the outcomes of the 17 NHANES-label contexts, the context-level contrasts with the name-prefix baseline, the comparison of the two gates and the thinking-mode comparison, and writes `results/label_contexts/stats.json`. The second compares `results/review_limit_2048/` (review limit 2,048 tokens, revision limit 512) with the core-context run (`results/core_contexts/per_input_outcomes.csv`) and with the extended run: per-input exact McNemar tests, pooled repair with a context-level bootstrap (5,000 resamples, fixed seed), and request statistics. It writes `results/review_limit_2048/stats.json`. Both are deterministic and correspond to Table 7, Table 8 and Supplementary Tables S11 to S13 of the manuscript.

The three-arm extended run used the revision of `p6_extended_v0_5.py` that preceded the review-limit option; the two revisions differ only in the plan fields and the request payload for the review limit.

## Second model

```
python analysis/second_model_stats.py
```

`results/granite/` holds the responses of a second model (Granite 3.3 8B Instruct, served as `p6-granite-8b` with a context window of 8,192 tokens) for the core contexts and the NHANES-label contexts, run with the longer-limit protocol. The script regenerates each plan from the runner, rescores every revision twice with `analysis/normalized_rescore.py`, checks that the strict rescoring reproduces the outcomes of the original run, and writes `stats.json` and the rescored `outcomes.csv` and `summary.json` under `strict/` and `normalized/`. The strict mode parses a response as the runner does. The normalized mode applies five fixed rules before scoring: it removes a Markdown fence, parses the first JSON value and ignores text after it, unwraps a proposal nested under a single `proposal_schema` or `proposal` key, keeps only the keys named in the context's proposal schema when all are present, and adds the three envelope fields of a patch when they are absent. Evaluator and gates are unchanged. The normalized scores correspond to Table 9 and Supplementary Table S14 of the manuscript.

```
python analysis/prompt_variant_stats.py
```

`results/granite_clarified/` and `results/review_limit_2048_clarified/core24/` hold the responses of Granite (both arms) and of Qwen3-8B (core contexts) with a clarified revision instruction (`--prompt-variant clarified` in the runner, `P6_PROMPT_VARIANT=clarified` in `experiments/label_contexts/run_longlimit.sh`): the instruction states the exact top-level keys and forbids a wrapper key, a code fence and extra text for full proposals, and states the envelope values and the allowed field names for patches. The script rescores the responses of these runs, of the Granite run with the original instruction and of the Qwen3-8B longer-limit run (whose responses are in `results/review_limit_2048/*/requests.jsonl`), strictly and after normalization, and scores the reviews with `analysis/review_flags.py`. That module takes the contexts with a feature-selection proposal (families F01, F02 and F07) and a contradicted initial proposal, finds the variables that are contradicted when selected alone, and records whether the review names such a variable, whether an exclusion cue (a fixed list of words in the module) occurs within 160 characters of it, and whether the final selection leaves it out. Results are written to `results/prompt_variant_stats.json` and correspond to Supplementary Table S15.


## Refitting the fixed reference

The refit uses the public DEMO_J and DPQ_J files from the NHANES 2017–2018 cycle. It needs Python 3.11 and the packages pinned in `experiments/preliminary_study/requirements-reference.lock.txt`.

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

Core-context runner:

```
cd experiments/core_contexts
python p6_integrated_development_v0_4.py check
python p6_integrated_development_v0_4.py prepare --output-dir PLAN_DIR
python p6_integrated_development_v0_4.py run --plan-dir PLAN_DIR --output-dir RUN_DIR --approve-plan-hash HASH
```

The plan fixes the endpoint `http://127.0.0.1:8010/v1` and the model identifier `p6-qwen3-8b`. The archived plan in this directory has canonical hash `0e8f19089e1c30abd239e31980645f17a566369e37422b58228389a7f5d74250`, and the runner has SHA-256 `1649d94540600146e4f562c48525b68f82813b2fa6e360c8fa881bbdb8b7cb83`.

Extended package:

```
export P6_MODEL=<served model id>
export P6_BASE_URL=<endpoint>/v1
bash experiments/label_contexts/run_extended.sh
```

| Variable | Meaning |
|---|---|
| `P6_MODEL`, `P6_BASE_URL` | required model identifier and endpoint |
| `OPENAI_API_KEY` | bearer token, never printed |
| `P6_OUT` | output root, default `outputs/label_contexts` |
| `P6_WORKERS` | concurrent requests, default 8 |
| `P6_ORIGINAL_RUNS` | run directories to scan for reasoning output and truncation |
| `P6_CONFIRM=yes` | skip the interactive confirmation |
| `P6_MODEL2`, `P6_BASE_URL2` | add think-off arms for a second served model |

The three arms are `nhanes_default` (17 contexts, server-default thinking, seeds 42 and 43, 544 requests), `core24_think_off` (24 contexts, thinking off, seed 42, 384 requests) and `nhanes_think_off` (17 contexts, thinking off, seeds 42 and 43, 544 requests). Each arm writes a plan, request log, run records and, after analysis, `outcomes.csv` and `summary.json`. Name-prefix rule results for the 17 contexts are scored offline as a fixed comparison row.

Longer review limit:

```
bash experiments/label_contexts/run_longlimit.sh
```

It takes the same `P6_MODEL`, `P6_BASE_URL`, `OPENAI_API_KEY`, `P6_OUT`, `P6_WORKERS` and `P6_CONFIRM` variables, plus `P6_ARMS` (default `core24 nhanes`), `P6_REVIEW_MAX_TOKENS` (default 2,048) and `P6_REVISION_MAX_TOKENS` (default 512). The arms are `core24` (seed 42, 384 requests) and `nhanes` (seeds 42 and 43, 544 requests) at the server-default thinking mode.

The scripts in `experiments/label_contexts` import the core-context runner from `experiments/core_contexts`, so they run through `run_extended.sh`, or with that directory on `PYTHONPATH`.

## Tests

```
pip install -r requirements.txt
pytest
```

The suite covers the lineage rules, the offline replay and the schema audit, the extended pipeline against a mock server, and the numerical modules of the depression reference.

## Direct-revision comparator

`experiments/direct_revision` runs the reviser without a critic. Each input receives one revision request that contains the context and the initial proposal and no review, in the two formats of the critic–reviser workflows (a complete proposal and a JSON patch scored under both gates on one response). Settings follow the 2,048-token run: revision limit 512 tokens, temperature 0.2, revision seeds 1042 (core contexts) and 1042 and 1043 (label contexts), server-default thinking mode, original revision instruction. The run makes at most 232 requests and uses the same server configuration as the reference run.

```
export P6_MODEL=p6-qwen3-8b
export P6_BASE_URL=http://127.0.0.1:8010/v1
P6_CONFIRM=yes nohup bash experiments/direct_revision/run_direct_revision.sh > direct_revision.log 2>&1 &
```

The script runs an offline check, confirms that the endpoint serves the model, prepares and hashes both plans, runs them, and analyzes each run against `results/review_limit_2048/<set>/outcomes.csv`. Without `P6_CONFIRM=yes` it prints the plan hashes and waits for the confirmation `RUN`. The analysis reports repair, preservation, harmful edits, retention and permissions-family repair for each direct-revision path, and paired contrasts with the critic–reviser paths that share its revision format (exact McNemar test and a context-level bootstrap interval).
