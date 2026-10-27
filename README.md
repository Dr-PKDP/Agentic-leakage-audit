# P6: reproducible analysis-workflow study

This branch preserves the exact supplied programs, synthetic contexts, prompts, model responses, source hashes and aggregate reference report used in the study. The default command performs **offline replay only**: it does not train a participant-data model, contact an API, use a GPU, or require SSH.

## 1. Checkout and reproduce the saved results

```text
git clone --branch publication/stage9-recovery --single-branch https://github.com/Dr-PKDP/P6-Population-Valid-Agentic-Clinical-Prediction.git
cd P6-Population-Valid-Agentic-Clinical-Prediction
python reproduce.py
```

Use an existing Python 3.10+ interpreter; the offline release was tested with Python 3.12. In Windows PowerShell, `py -3` can replace `python`. The default replay uses only Python's standard library. Do **not** install the legacy root requirements.txt to run it. No API key or participant dataset is needed.

Default output: `repro/p6/_generated/`. It contains `summary.json`, principal outcome/request CSVs, replayed earlier-pilot scores and the recorded reference-metric CSV. If that directory exists, the command stops instead of overwriting it:

```text
python reproduce.py --out repro/p6/_generated_second
```

The release manifest is checked before replay. A changed/missing file is an error, not a reason to edit expected hashes until a check passes.

## 2. What the command actually reproduces

| Component | Offline operation | Expected result |
|---|---|---|
| Principal synthetic v0.4 run | Reconstruct 384 request payloads; reapply frozen strict parser, scorer and two acceptance paths to saved responses | 192 exact unit records; 48 exact references; 543571 tokens; 93 review-length stops |
| Post hoc rule-only reference | Regenerate one context-only proposal for each of 24 contexts; score afterward | 24/24 supported; outputs reused for two initial variants; no model requests |
| Earlier synthetic pilot | Reapply original scorer to all 90 initial/final proposal responses in the 135-request ledger | 45 units; strict final passes 1/15 self-review, 7/15 structure feedback, 4/15 guarded critic |
| Earlier post hoc claims sensitivity | Recompute the declared scalar-to-singleton-list transformation separately | Normalized final passes 3/15, 7/15, 4/15; original strict scores unchanged |
| Fixed depression reference | Verify config/runner/numerical-module hashes and export recorded aggregate metrics | Six metric rows, 5068 complete-outcome participants; **no numerical refit** in default replay |

All model responses in the synthetic archives are recorded data, not participant observations. Replaying the same authored scorer is computational reproducibility, not independent scientific adjudication, held-out validation, clinical utility or proof of novelty. The two v0.4 patch paths share one generated patch per input. Their rows are not independent generations.

## 3. Release layout

```text
reproduce.py                         # documented entry point
RELEASE_MANIFEST.json                 # exact release paths, byte counts, SHA-256
repro/p6/analysis.py                   # portable offline replay and report verification
repro/p6/reference_portable.py         # optional, explicit new clinical refit adapter
repro/p6/rule_reference.py             # post hoc deterministic comparator
repro/p6/v0_4/                        # exact runner, plan, jobs, ledger, unit/reference outputs
repro/p6/server_snapshot/             # 105 collected original server files
  configs/                           # versioned decisions and recorded analysis environment
  scripts/                           # original pilot, reference, audit and sensitivity runners
  src/                               # original numerical, preprocessing and gate modules
  tests/                             # supplied development tests and records
  outputs/                           # archived synthetic run and aggregate reference artifacts
repro/p6/REPRODUCIBILITY_NOTES.md       # scope, corrections and exclusions
```

The snapshot is isolated so it does not overwrite the repository's older hypertension modules. The only added package marker is an empty `src/__init__.py` for portable imports; original numerical module bytes are unchanged. Existing top-level acquisition/hypertension programs are legacy work, not the v0.4 replay entry point.

## 4. Optional fresh participant-data reference reproduction

This is separate from offline replay and starts a **new local fit**. It needs the two original public XPT files, Python 3.11 and the recorded reference dependencies. Raw files, participant-level predictions and fitted models are not included in the repository. Obtain DEMO_J and DPQ_J from the CDC documentation pages:

- https://wwwn.cdc.gov/Nchs/Data/Nhanes/Public/2017/DataFiles/DEMO_J.htm
- https://wwwn.cdc.gov/Nchs/Data/Nhanes/Public/2017/DataFiles/DPQ_J.htm

Expected SHA-256:

```text
DEMO_J.xpt c0b46e0345ea19404928656277c8b0d10b0cca348a9b2fe4fc3c67e8b7ee73ec
DPQ_J.xpt  1c075f332e79736bd2360b41b0c10ed526883417e0b5996c407b1c564b01ca24
```

The original run recorded Python 3.11.16, NumPy 2.3.5, pandas 3.1.0, scikit-learn 1.9.1 and pyreadstat 1.3.7. The full recorded analysis package list is preserved, not claimed to describe the original model-serving environment.

Example setup, if you choose to perform a new fit:

```text
python3.11 -m venv .venv-reference
```

Activate that environment using your operating system's usual procedure, then:

```text
python -m pip install -r repro/p6/server_snapshot/requirements-reference.lock.txt
python reproduce.py --check-inputs --demo /path/to/DEMO_J.xpt --dpq /path/to/DPQ_J.xpt
python reproduce.py --allow-fit --demo /path/to/DEMO_J.xpt --dpq /path/to/DPQ_J.xpt --out repro/p6/_generated_reference
```

In PowerShell, quote real Windows paths containing spaces and use `py -3.11 -m venv .venv-reference` if appropriate. Replace `/path/to/...` with actual local files; these are not download URLs. Installing packages is only for the optional refit, not offline replay.

The adapter verifies the public-input hashes, regenerates a genuine predictor/fold audit from those inputs, and adapts only the original runner's ROOT and prior-audit path assignments in memory. Cohort, estimator, preprocessing, fold and metric code remain unchanged. It retains the original source files, records the path adaptation and compares six aggregate metrics with tolerance 1e-10. It is not a byte-identical reproduction of timestamps or the original prior-audit hash. This optional path was source/syntax checked but was **not numerically rerun** while preparing the release because the raw inputs are not supplied here. No institutional or new data-use authorization is inferred from `--allow-fit`.

## 5. New language-model generations are not replay

The original generation programs are archived for inspection. They require a model server, credentials entered locally, an explicit model identity and separate authorization. Do not run them merely to reproduce the published tables. Exact base-weight revision and complete original serving environment are not established. Forty of 48 identical logged review requests returned different text despite the same seed; bitwise repeat generation is not promised. Existing 384/135-request budgets are historical, not permission for additional calls. No credentials or model weights are bundled.

## 6. Known results and limits

Both principal patch paths repair the same 20/21 known errors. Evidence checking prevents one harmful timing edit. Empty evidence-critic selections, fenced JSON, schema failures and unsuccessful fallback remain in original scores. Ninety-three reviews reached their output ceiling, every initial input was schema-valid, and resource totals differ across streams. Contract support is not useful completion, national inference, clinical safety or a novel enforcement principle.

The newly recovered source includes the **completed** earlier post hoc claims sensitivity. Earlier draft language saying it was only proposed is superseded by the archived report and replay. Normalized results are secondary; original strict pilot results remain primary.

## 7. Testing, provenance and release boundaries

`reproduce.py` checks every file listed in RELEASE_MANIFEST.json. The offline command was actually executed in an isolated local release directory. It does not install packages or execute networking/model code. Test results and exact scope are recorded in `repro/p6/VERIFICATION.json`.

The optional numerical refit and the original full development-test suite require the recorded numerical environment; they are not claimed to have been rerun in the release environment. The repository's earlier hypertension/temporal work is retained but not certified as a completed temporal experiment. No independent adjudication, substantial novelty or third-party replication is inferred from internal replay.

No API secrets, private keys, raw XPTs, participant-level prediction arrays, fitted models or virtual environments are part of this release. Pattern checks are not a comprehensive security certificate. Licensing terms are not changed by this update. A repository being readable does not itself establish a new reuse licence.
