# Population-valid agentic clinical prediction

Code, archived runs and reference tables for a study of critic–reviser workflows that review analysis proposals for leakage-prone clinical prediction tasks. A language model proposes or revises an analysis decision (which features to use, which records to fit on, which survey weight applies, which action to request, which validation to claim), and deterministic gates check the result against scoped evidence. The study counts repaired errors, preserved decisions and harmful edits separately, and compares the workflows with fixed rules.

## Reproducing the reported results

The archived requests and responses can be re-scored offline. The replay needs Python 3.10 or later and the standard library only. It does not call a model, use a GPU or read participant data.

```
python reproduce.py
```

The command checks `MANIFEST.json`, recomputes every score from the saved responses and writes tables to `_generated/`. Run it with `--out DIR` to write elsewhere; it never overwrites an existing directory. The expected totals are listed below.

| Run | Replayed quantity | Expected value |
|---|---|---|
| Principal run | Workflow units, requests, total tokens | 192, 384, 543,571 |
| Principal run | Reviews that stopped at the 1,024-token limit | 93 |
| Principal run | Contexts supported by the deterministic rule reference | 24 of 24 |
| Pilot | Exact contract passes: self-review, structure feedback, evidence critic | 1, 7, 4 of 15 |
| Pilot | Passes after the claims-label normalization | 3, 7, 4 of 15 |
| Fixed reference | Complete-outcome participants in the recorded report | 5,068 |

## Layout

```
reproduce.py            offline replay, manifest check, optional reference refit
MANIFEST.json           SHA-256 of every file the replay depends on
analysis/               replay, deterministic rule reference, NHANES schema audit, sensitivity analyses
experiments/
  principal_v0_4/       24-context run: runner, plan, jobs, requests, responses, scored units
  extended_v0_5/        NHANES-label contexts, thinking-mode switch, multiple seeds
  pilot_depression/     earlier three-scenario pilot and the fixed depression reference
nhanes/                 name-prefix lineage rules, acquisition scripts, schema and harmonization tables
results/                scored tables and the schema audit
tests/                  unit, replay and pipeline tests
docs/                   design, reproduction, data dictionary and lineage-rule notes
```

## Components

The principal run (`experiments/principal_v0_4`) used 24 synthetic contexts in six constraint families. Each context had two initial proposals, 48 inputs in all, and each input was processed by four critic streams. One stream produced JSON patches, and each patch was passed through two acceptance gates, so the gates share a single generation. The design and scoring rules are described in [docs/design.md](docs/design.md).

The extended package (`experiments/extended_v0_5`) adds a seventh family of 17 contexts whose candidate variables carry NHANES codebook labels. It also adds a switch for the model's thinking mode, several seeds per input and concurrent requests. It needs a running OpenAI-compatible endpoint, which the replay does not.

The pilot (`experiments/pilot_depression`) evaluated three developer-written scenarios under three workflows. The same directory holds the fixed depression reference, a logistic baseline on NHANES 2017–2018 with grouped five-fold evaluation, whose aggregate report is archived.

`nhanes/lineage_validator.py` holds the name-prefix rules that exclude outcome-defining variables for four screening tasks. `analysis/schema_audit.py` compares them with a codebook-derived reference set ([docs/lineage_rules.md](docs/lineage_rules.md)).

## Running the extended experiment

```
export P6_MODEL=<served model id>
export P6_BASE_URL=http://127.0.0.1:8000/v1
export OPENAI_API_KEY=<token, if the endpoint requires one>
bash experiments/extended_v0_5/run_extended.sh
```

The script runs an offline check, confirms that the endpoint serves the model, prepares three arms, prints the plan hash and the maximum number of requests, and starts generation only after the confirmation `RUN`. It does not start or stop a model server. Further options are in [docs/reproducing.md](docs/reproducing.md).

## Tests

```
pip install -r requirements.txt
pytest
```

The suite uses Python 3.11 and the pinned packages in `experiments/pilot_depression/requirements-reference.lock.txt`. Pipeline tests run against a local mock server.

## Data

The repository contains no participant records. NHANES files are public and are obtained from the CDC data pages; their sizes and SHA-256 values are recorded in `nhanes/provenance/`. Model responses in the archives are recorded generations on synthetic contexts.

## Scope

The contexts, rules and scorer were written by the study authors, and the evaluator shares its encoded semantics with the gates and the rule reference. A replay therefore checks computational reproducibility, not independent validity, held-out performance or clinical utility. Details are in [docs/design.md](docs/design.md).
