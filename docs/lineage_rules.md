# NHANES lineage rules and schema audit

## Rules

`nhanes/lineage_validator.py` holds one list of regular expressions per screening task. A variable whose upper-cased name matches a pattern is excluded from that task's predictor set. Survey design variables (`SDMVSTRA`, `SDMVPSU`, `WTMEC*`, `WTINT*`) are excluded for every task.

| Task | Name prefixes |
|---|---|
| T1 diabetes screening | LBXGH, LBDGH, LBXGLU, LBDGLU, LBXIN, LBDIN, DIQ |
| T2 hypertension screening | BPX, BPQ |
| T3 depressive symptoms | DPQ, FNQ |
| T4 chronic kidney disease screening | LBXSCR, LBDCRE, URXUMA, URXUCR, URDACT, URXUACR, KIQ, CKQ |

`flagged(task, features)` returns the excluded names, including design variables. `validate(task, features)` returns whether any feature matches an outcome prefix; design variables alone do not make it true.

Six prefixes match no variable in the acquired schema: LBDGH, FNQ, LBDCRE, URXUACR, KIQ and CKQ (the audit lists them per task).

## Audit

`analysis/schema_audit.py` applies the rules to the 551 variable names in the development schema (`nhanes/metadata/development_schema.csv`, 18 components, cycles 2011–2012, 2013–2014 and 2015–2016, respondent identifier excluded). For each task it compares the excluded names with a reference set compiled from the 2015–2016 NHANES codebooks under three criteria.

| Category | Criterion |
|---|---|
| A | The variable is part of the case definition or instrument |
| B | The variable restates a defining quantity in other units, as a comment code, or in another component |
| C | The variable records the diagnosis, treatment or indication for medication |

Prescription-medication fields (drug name and code, ICD-10-CM code and description) are in category C for every task, because the rules already exclude the questionnaire items on insulin and antihypertensive treatment and drug identity carries the same information. A variable enters a reference set only when its codebook label establishes the criterion, so the sets understate omissions. They were compiled without independent review. Labels were taken from the 2015–2016 codebooks; a variable that did not return a label is not in a set.

## Results

| Task | A defining | B restatement | C diagnosis, treatment, indication | All |
|---|---|---|---|---|
| Diabetes | 2/3 | 1/5 | 4/14 | 7/22 |
| Hypertension | 8/8 | 0/2 | 4/13 | 12/23 |
| Depressive symptoms | 10/10 | 0/0 | 0/8 | 10/18 |
| Chronic kidney disease | 4/4 | 0/5 | 0/8 | 4/17 |
| All | 24/25 | 1/12 | 8/43 | 33/80 |

Cells give reference variables flagged over reference variables. The rules flag nearly every variable that defines a case. They miss the two-hour glucose from the oral glucose tolerance test, and most variables that restate a defining quantity or record its treatment. The only restatement flagged is the SI-unit fasting glucose, which shares the `LBDGLU` prefix with the conventional-unit variable.

`results/nhanes/schema_audit_reference.csv` lists every reference pair with its category, the components that contain it, its 2015–2016 label and the rule outcome. `schema_audit.json` holds the counts per task, the names flagged outside the reference set, and the harmonization summary (571 variable names, of which 399 appear in all three cycles).

## Data-use policy

`nhanes/data_use_policy.json` separates the development cycles (2011–2012, 2013–2014, 2015–2016) from two locked temporal-test cycles (2017–2018 and 2021–2023) and lists the operations prohibited before a protocol freeze. The acquisition script refuses any split whose name begins with `locked`. The fixed depression reference in `experiments/pilot_depression` declares its own cycle role in its configuration (`development_only`, no final test set defined) and reads the 2017–2018 depression and demographics files under that declaration.
