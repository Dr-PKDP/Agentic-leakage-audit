# P6 BPQ cross-cycle verification v0.1

Status: DEVELOPMENT ONLY — NOT FROZEN

Verified development cycles:
- 2011–2012: BPQ_G; BPQ020=2 skips to BPQ057.
- 2013–2014: BPQ_H; BPQ020=2 skips to BPQ056.
- 2015–2016: BPQ_I; BPQ020=2 skips to BPQ080.

In all three cycles, BPQ020 codes are:
1=Yes; 2=No; 7=Refused; 9=Don't know; .=Missing.
All three negative-response routes bypass BPQ040A/BPQ050A.

Proposed primary eligibility remains BPQ020=2.
Do not require BPQ050A=2 or recode all missing medication values to No.
Do not assume identical skip destinations across cycles.

Sources:
https://wwwn.cdc.gov/Nchs/Data/Nhanes/Public/2011/DataFiles/BPQ_G.htm
https://wwwn.cdc.gov/Nchs/Data/Nhanes/Public/2013/DataFiles/BPQ_H.htm
https://wwwn.cdc.gov/Nchs/Data/Nhanes/Public/2015/DataFiles/BPQ_I.htm

Scope: questionnaire definitions only.
BP measurements, predictors, and survey design are not verified here.
