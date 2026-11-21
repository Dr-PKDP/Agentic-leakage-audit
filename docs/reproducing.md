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

## Review replay, constrained decoding, gate operating characteristics and execution check

```
python analysis/replay_decoding_execution_stats.py
```

The script recomputes, from the archived outcome tables, the quantities reported for Experiments 6 to 9 and writes `results/replay_decoding_execution_stats.json`. It needs only the standard library. A final predictor set counts as inflated when its AUC is at least 0.02 above that of the reference set of its context; the archived table stores that difference rounded to four decimals and no record lies within 0.0005 of the threshold. The table records verdicts and AUCs but not the predictor names of each proposal, so agreement is reported over rows (2,989 of 3,030) and over contexts (disagreement in 3 of the 17 label contexts) and not over distinct predictor sets.

Experiment 6 (`results/review_replay/`). The reviews saved by the 2,048-token run of Experiment 3 are given to the reviser unchanged (`q_replay_full_*`) or cut to their first 1,024 tokens with the serving model's own tokenizer (`q_replay_t1024_*`); only the revision is generated. The replay of the complete reviews reproduces the repair counts of the source run exactly (71 of 84 pooled on the core contexts, 122 of 136 on the label contexts), so the two conditions differ only in the length of the critique.

Experiment 7 (`results/constrained_decoding/`). The revision request of the three full-proposal streams carries a JSON-schema response format built from the context's proposal schema (required keys, no additional keys, fixed value types), with the clarified instruction and a review limit of 2,048 tokens. Reviews are unconstrained. The schemas contain no `uniqueItems` keyword, which the serving stack rejects. Each model made 696 requests.

Experiment 10 (`results/model_scale/qwen3_27b/`). A larger model, Qwen3.8-27B, served as `qwen3.8-27b` with a 32,768-token context window, was run through the `model` stage: a clarified arm without constraint and a constrained arm on each context set, with the thinking mode requested off in every call, a review limit of 2,048 tokens and a revision limit of 512 tokens (seed 42 on the core contexts, seeds 42 and 43 on the label contexts; 384 requests per core arm and 544 per label arm). The patch stream is included in both arms and is not constrained. `analysis/replay_decoding_execution_stats.py` compares its constrained arms with those of the two 8B models under `model_scale` in `results/replay_decoding_execution_stats.json`.

Experiment 8 (`results/gate_operating_characteristics/`). The battery runs offline and without a model. For each of the 82 initial inputs it enumerates every single-field edit (a Boolean flip, an added or removed list element, a cleared list, or a string replaced by another value of the same field in the family), 474 edits in all, and passes each as a patch through both acceptance gates under four evidence-citation conditions: applicable identifiers, none, identifiers of another scope and nonexistent identifiers. The evaluator verdict on the edited proposal classifies the edit as harmful, repairing or neutral. `edits.csv` holds one row per edit and condition, `candidates.csv` one row per candidate artifact with the verdict of the evaluator and of the support check, and `summary.json` the totals.

```
bash experiments/constrained_and_replay/run_stages.sh gate
```

Experiment 9 (`results/execution_check/`). A fixed pipeline (median imputation with missingness indicators, standardization, one-hot coding of the four prescription fields, L2-penalized logistic regression, five-fold stratified cross-validated AUC with seed 20261119, no survey weights) is fitted to the public NHANES 2015–2016 files DEMO_I, BIOPRO_I, GHB_I, GLU_I, BPX_I, BPQ_I, DIQ_I, DPQ_I, ALB_CR_I and RXQ_RX_I for adults aged 20 years or older. The outcomes are diabetes (DIQ010 = 1, HbA1c of 6.5% or more, or fasting glucose of 126 mg/dL or more), hypertension (mean systolic pressure of 130 mmHg or more, mean diastolic pressure of 80 mmHg or more, or BPQ040A = 1, which records ever having been told to take prescribed medicine for high blood pressure and is therefore a prescription-history proxy rather than current use), depression (PHQ-9 of 10 or more with all nine items valid) and chronic kidney disease (eGFR below 60 mL/min/1.73 m² by CKD-EPI 2021, or urine albumin-to-creatinine ratio of 30 mg/g or more). A proposal is executed only as a list of predictors; names absent from the analytic file are ignored. A final predictor set counts as inflated when its AUC exceeds that of the reference set of its context by 0.02 or more. The model's text is never executed as code.

```
export P6_NHANES_DIR=data/nhanes_2015_2016   # the ten files above, downloaded by the fetch step if absent
export P6_RUNS_ROOT=<directory holding run outputs of the NHANES-label arms>
bash experiments/constrained_and_replay/run_stages.sh execute
```

The stage fetches the files (a download requires access to `wwwn.cdc.gov`), builds the analytic file, computes the reference AUCs, scores every NHANES-label run found under `P6_RUNS_ROOT`, and packages the tables. It needs `pandas`, `scikit-learn` and `pyreadstat`. `results/execution_check/` archives the output of the run reported in the manuscript, which scored the final proposals of 12 run directories of the NHANES-label contexts.

### Generating new responses

```
export P6_QWEN_URL=http://127.0.0.1:8010/v1 P6_GRANITE_URL=http://127.0.0.1:8011/v1
export P6_SRC=<longer-limit run directory holding plans/SET/jobs.json and runs/SET/requests.jsonl for core24 and nhanes>
bash experiments/constrained_and_replay/run_stages.sh check
bash experiments/constrained_and_replay/run_stages.sh replay
bash experiments/constrained_and_replay/run_stages.sh constrained q
bash experiments/constrained_and_replay/run_stages.sh constrained g
bash experiments/constrained_and_replay/run_stages.sh model TAG MODEL BASE_URL
```

Every stage prepares its plans, prints each plan hash and the maximum number of requests, and starts generation after the confirmation `RUN` (or with `P6_CONFIRM=yes`). It never retries, never resumes and never overwrites an output directory, and it does not start or stop a server. The runner `p6_v06.py` checks the SHA-256 of the core-context runner and of the copy of `p6_extended_v0_5.py` in this directory, which is the revision used for these runs; the revision in `experiments/label_contexts` adds only the clarified-instruction option. The `model` stage runs one further model through the clarified and constrained arms. The 32,768-token context window of a larger model leaves room for the 2,048-token review limit used here.

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

The script runs an offline check, finds the API key when the endpoint requires one (from `OPENAI_API_KEY`, else from this account's vLLM process, without printing it), confirms that the endpoint serves the model, prepares and hashes both plans, runs them, and analyzes each run against `results/review_limit_2048/<set>/outcomes.csv`. Without `P6_CONFIRM=yes` it prints the plan hashes and waits for the confirmation `RUN`. The analysis reports repair, preservation, harmful edits, retention and permissions-family repair for each direct-revision path, and paired contrasts with the critic–reviser paths that share its revision format (exact McNemar test and a context-level bootstrap interval). The archived run is in `results/direct_revision/` (`core24` and `nhanes`: outcomes, summary, plan and the logged requests and responses).

### Check-then-revise comparator

`experiments/direct_revision/p6_check_revision.py` gives the reviser one request that asks for a short written check of the proposal against the evidence and rule (the wording of the evidence-critic review request, at most 120 words, citing evidence identifiers) followed by a line `FINAL:` and the revision in the format of the original instruction. Only the text after the last `FINAL:` is parsed, strictly; a response without the marker is an interface failure. The revision limit is 1,024 tokens so that the check and the revision fit; the other settings are those of the direct-revision run. The runner imports the core and label runners unchanged and verifies their hashes.

```
P6_MODEL=p6-qwen3-8b P6_BASE_URL=http://127.0.0.1:8010/v1 \
P6_CONFIRM=yes nohup bash experiments/direct_revision/run_check_revision.sh > check_revision.log 2>&1 &
```

The script makes at most 232 requests and analyzes each run against the critic-reviser paths of the 2,048-token run and against the direct-revision run in `results/direct_revision/`.

## Acceptance-gate registry and the designated tests

```
python analysis/gate_pool.py
python analysis/designated_tests.py
```

`gate_pool.py` builds the registry of every condition in which the same generated patch passed through both acceptance gates, writing `results/gate_pool.json`. A condition is one generation run over one context set, so each generated patch is counted once; the normalized rescoring of the Granite and clarified-instruction runs rescores runs already in the registry and is listed separately rather than pooled. A pair enters the pool when the initial proposal was supported and both gate outcomes are assessable. The expected totals are 23 conditions, 633 paired supported inputs, 71 harmful edits under the interface-only gate and 3 under the evidence gate, with 29 further pairs excluded as unevaluable.

`designated_tests.py` computes the five designated hypothesis-level tests and writes `results/designated_tests.json`. Contexts are the unit of inference: each contrast is the mean over contexts of the within-context difference in the outcome rate, with a percentile interval from 10,000 bootstrap resamples of contexts (seed 2026) and a two-sided randomization test that flips the sign of each context's difference, enumerating every assignment for 20 contexts or fewer. The same rows are also fitted by a generalized estimating equation with an identity link, binomial variance and an exchangeable working correlation clustered on context, which needs `statsmodels`. The Holm procedure is applied across the five. The expected results are H1 +61.9 pp (p = 0.0004, Holm 0.0012), H2 +100 pp (0.125, 0.125), H3 +9.2 pp (0.0001, 0.0005), H4 +52.9 pp (0.00244, 0.00488) and H5 +25.7 pp (0.00018, 0.00072). The five tests were selected once the responses of the later experiments were available, so they are multiplicity-adjusted hypothesis-level tests and not a prespecified confirmatory family.

## Serving provenance and the traceability of the executed check

```
python analysis/serving_provenance.py
python analysis/predictor_sets.py
```

`serving_provenance.py` collects the model entry and server version that each run stored, and the server build the responses carry, into `results/serving_provenance.json`, and merges the weight revision, served dtype and quantization setting from `results/model_weights.json`. That file was recorded on the serving host on 2026-11-21: the commit hash stored in each model directory, the SHA-256 of every weight shard, and the dtype and quantization setting from the vLLM start-up logs (bfloat16, none, for all three models). The run records carry no timestamps, so the digests identify the weights in the directories on that date and do not independently establish the weights read at each run. The two 8B models were served by vLLM 0.32.0 and Qwen3.8-27B by vLLM 0.30.0.

`predictor_sets.py` quantifies two limits of `results/execution_check/executed_outcomes.csv`. The table records no predictor names, and its key of model, arm, context, input, path and seed is not unique, because an arm label covers repeated scoring views and sub-runs: 704 of the 2,730 keys carry more than one row, and the 3,638 rows describe 2,685 distinct units among those assessable. Collapsing each key to a single row gives agreement of 2,655 to 2,656 of 2,685 (98.9%) under three selection rules. The per-unit final artifacts survive for one arm, in `results/granite/nhanes/final_artifacts.csv` and `results/granite/core24/final_artifacts.csv`; restricted to the 30 whose executed row is unambiguous, the 14 distinct predictor sets agreed with the evaluator in 13 cases. That subset is a provenance check, not a result.

## Agreement of AI tools with the reference sets

`analysis/reference_agreement.py` compares the ratings of five general-purpose AI tools (ChatGPT, Perplexity, Gemini, Grok, Meta AI) with the NHANES reference exclusion sets. Each tool labeled every variable of the ten 2015–2016 files that hold the reference variables (162 candidates) as excluded or not for each of the four screening tasks, from the variable name, component and description, without seeing the reference. The script reports Cohen's kappa against the reference (pooled and per task), the share of reference pairs each tool flags, the flags outside the reference, the kappa between tools, and writes `disagreements.csv` with empty columns for a cross-check by the authors. The tools are a check on the reference, not independent human raters.

The ratings are in `results/reference_agreement/ratings/` and the task they were given is described in `results/reference_agreement/rating_task.md`. The authors adjudicated the 43 task–variable pairs on which at least one tool disagreed with the reference. Nine pairs were added, which gives the adjusted reference `results/nhanes/schema_audit_reference_adjusted.csv` (89 pairs, against 80). The primary analyses use the original reference.

```
python analysis/reference_agreement.py --ratings results/reference_agreement/ratings \
    --raters chatgpt perplexity gemini grok meta --out OUT
python analysis/reference_agreement.py --ratings results/reference_agreement/ratings \
    --raters chatgpt perplexity gemini grok meta \
    --reference results/nhanes/schema_audit_reference_adjusted.csv --out OUT_ADJ
```

The expected outputs are `against_original_reference.json` and `against_adjusted_reference.json` in the same folder. Mean kappa is 0.886 against the original reference and 0.896 against the adjusted one.
