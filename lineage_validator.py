import re
RULES={
"T1_diabetes_screening":r"^(LBXGH|LBDGH|LBXGLU|LBDGLU|LBXIN|LBDIN|DIQ)",
"T2_hypertension_screening":r"^(BPX|BPQ)",
"T3_depressive_symptoms":r"^(DPQ|FNQ)",
"T4_ckd_screening":r"^(LBXSCR|LBDCRE|URXUMA|URXUCR|URDACT|URXUACR|KIQ|CKQ)"
}
def validate(task, features):
    return [str(x).upper() for x in features if re.match(RULES[task],str(x).upper()) or re.match(r"^(SDMVSTRA|SDMVPSU|WTMEC|WTINT)",str(x).upper())]
