# P6 codebook verification v0.1

Status: DEVELOPMENT ONLY — NOT FROZEN
Scope: 2017–2018 only. Earlier cycles remain unverified.
No modelling or evaluated generation authorized.

## Sources
https://wwwn.cdc.gov/Nchs/Data/Nhanes/Public/2017/DataFiles/BPX_J.htm
https://wwwn.cdc.gov/Nchs/Data/Nhanes/Public/2017/DataFiles/BPQ_J.htm

## Questionnaire findings
BPQ020: 1=Yes, 2=No, 7=Refused, 9=Don't know.
BPQ020=2 skips to BPQ080, bypassing hypertension medication questions.
Do not require BPQ050A=2 for that route.
Do not globally recode missing medication responses to No.

## Proposed eligibility
Require BPQ020=2 for the primary population.
Describe this as without self-reported prior diagnosis.
Do not claim independently verified absence of medication use.
Flag unexpected questionnaire contradictions for review.

## BP findings
BPX includes three consecutive readings and a possible fourth attempt.
Systolic fields: BPXSY1 through BPXSY4.
Diastolic fields: BPXDI1 through BPXDI4.
Zero diastolic BP is permitted; it is not a missing-value code.
Reading selection and averaging remain undecided.
Use examination weights; pooled-cycle construction remains undecided.

## Pending
Verify earlier cycles, measurement rules, pregnancy handling,
predictors, validation, weighting, metrics, and uncertainty.
