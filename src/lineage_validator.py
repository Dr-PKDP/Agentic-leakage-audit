import re
RULES={"T1_diabetes_screening":[r"^(LBXGH|LBDGH|LBXGLU|LBDGLU|LBXIN|LBDIN|DIQ)"],"T2_hypertension_screening":[r"^(BPX|BPQ)"],"T3_depressive_symptoms":[r"^(DPQ|FNQ)"],"T4_ckd_screening":[r"^(LBXSCR|LBDCRE|URXUMA|URXUCR|URDACT|URXUACR|KIQ|CKQ)"]}
def validate(task,features): return any(re.match(p,f.upper()) for p in RULES.get(task,[]) for f in features)
