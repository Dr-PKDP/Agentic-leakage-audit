# P6 task specification v0.1

Status: DEVELOPMENT ONLY — NOT FROZEN
No real-data modelling or autonomous model-generated execution authorized.
This document does not supersede protocol_draft.md.

## Purpose
Evaluate whether a guarded proposal-generation workflow produces
scientifically admissible population-survey prediction proposals.
Do not treat predictive accuracy alone as evidence of workflow benefit.

## Proposed dataset and temporal assignments
Dataset: public-use NHANES.
Development pool: 2011–2012, 2013–2014, and 2015–2016.
Reserved temporal evaluation: 2017–2018.
Internal tuning and calibration assignments: NOT YET SPECIFIED.
Verify cross-cycle variable definitions before freezing.
Do not inspect held-out outcome associations or predictive performance
to choose predictors, thresholds, or models.

## Intended use and prediction time
Research screening for elevated blood pressure among adults without
a reported previous hypertension diagnosis.
Prediction occurs before obtaining blood-pressure measurements.
This is not a clinical diagnosis or treatment recommendation.
Candidate measurement availability is a proposed screening scenario,
not a claim about actual NHANES examination ordering.

## Proposed eligibility
Age >=20 years.
Explicitly report no previous hypertension diagnosis.
Prior-diagnosis refused, don't-know, and unexplained missing values
are not equivalent to an explicit negative response.
Medication eligibility: pending verification of questionnaire routing.
Pregnancy handling: NOT YET SPECIFIED.
Require sufficient valid BP measurements under the rule below.
Missing predictors do not automatically imply exclusion.

## Proposed target
Screen-positive elevated BP:
mean systolic BP >=130 mmHg OR mean diastolic BP >=80 mmHg.
Screen-negative: both means below their thresholds.
Use conventional auscultatory BPX measurements consistently.
Do not substitute or pool BPXO measurements.
Exact reading selection, minimum count, zero-value handling,
measurement validity, and averaging rules: NOT YET SPECIFIED.
Missing or insufficient BP measurements are not negative outcomes.

## Candidate predictor domains
Age, sex, BMI, and smoking.
Exact variables, encodings, availability assumptions, and missing-data
procedures require codebook verification before freezing.
No additional predictor may be added merely because the model suggests it.

## Variable roles
Outcome only: BP measurements and derived target.
Eligibility only: prior-diagnosis and relevant medication information.
Survey design only: examination weight, stratum, and PSU.
Linkage only: participant identifier.
Partitioning only: survey cycle.
None of these fields may enter the predictor matrix.

## Survey design
Candidate design fields: WTMEC2YR, SDMVSTRA, SDMVPSU.
Confirm appropriate weights for the final component selection.
Specify pooled-cycle weight construction before analysis.
Preserve design information for design-aware evaluation and uncertainty.
Survey-design fields are not predictors.

## Proposed workflow comparison
Single-agent proposal versus planner–critic–revision proposal.
Use identical task metadata and evaluation criteria.
Record all requests, outputs, reviews, revisions, and gate results.
Measure proposal admissibility separately from JSON/schema validity.
Prompts, schemas, seeds, generation settings, run budgets,
review criteria, and stopping rules are NOT YET FROZEN.

## Unresolved decisions
- Verify all selected variables and questionnaire routing across cycles.
- Resolve medication eligibility and pregnancy handling.
- Specify BP measurement validity and aggregation.
- Specify preprocessing, internal validation, metrics, and uncertainty.
- Specify independent proposal-review labels and adjudication.
- Record model revision and final serving configuration.
- Review and freeze the task and experiment before evaluated generation.
