# Rating task given to the five AI tools

This file records what each tool was asked to do, so that the ratings in `ratings/` can be read and
criticized. It is a description of the task, reconstructed from the task design and the column
structure of the rating files, and not a verbatim transcript of the prompts.

## Tools and settings

ChatGPT, Perplexity, Gemini, Grok and Meta AI, used through their public interfaces at their default
settings in November 2026. The underlying model versions are not pinned and are not recoverable, so
the ratings cannot be reproduced by re-running a fixed checkpoint. They are a check on the reference
exclusion sets, not an inter-rater reliability estimate, and no independent human rater took part.

## What each tool received

1. The three written criteria that define a reference exclusion, in this order and wording:
   - the variable defines the case or the instrument;
   - it expresses a defining quantity in other units, comment codes or another component;
   - it records diagnosis, treatment or medication indication.
2. The four screening task definitions:
   - T1 diabetes: a self-reported diagnosis, a glycated hemoglobin of 6.5% or more, or a fasting
     glucose of 126 mg/dL or more. The two-hour glucose of the oral glucose tolerance test was
     omitted from this line, although the exclusion policy treats it as case-defining; the omission
     is reported as a limitation.
   - T2 hypertension: a mean systolic pressure of 130 mmHg or more, a mean diastolic pressure of
     80 mmHg or more, or antihypertensive medication.
   - T3 depressive symptoms: a PHQ-9 total of 10 or more.
   - T4 chronic kidney disease: an eGFR below 60 mL/min/1.73 m² or an albumin-to-creatinine ratio
     of 30 mg/g or more.
3. The 162 candidate variables of the pool, each with its NHANES component and its 2015–2016
   codebook label. The reference exclusion sets were not shown.

## What each tool returned

One row per candidate variable for each of the four tasks, which is 648 judgments per tool and 3,240
in all, with the columns of `ratings/ratings_<tool>_T<task>.csv`:

- `variable`: the NHANES variable name;
- `exclude`: 1 if the variable should be excluded from the predictors of that task, else 0;
- `criterion`: which of the three criteria applies (A, B, C), or `none`;
- `reason`: a short free-text justification.

## Adjudication

`analysis/reference_agreement.py` compares each tool with the reference and writes
`disagreements.csv`. The authors adjudicated the 43 task–variable pairs on which at least one tool
differed from the original reference, against the written criteria and the codebook text, and added
nine pairs. That gives `results/nhanes/schema_audit_reference_adjusted.csv` with 89 pairs, against
80 in the original. The primary analyses use the original sets; the rule audit was repeated against
the adjusted sets.
