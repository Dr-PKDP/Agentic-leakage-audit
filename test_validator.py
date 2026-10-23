from src.lineage_validator import validate
def test_diabetes():
    assert validate("T1_diabetes_screening",["LBXGH"])==["LBXGH"]
def test_bp():
    assert validate("T2_hypertension_screening",["BPXSY1"])==["BPXSY1"]
def test_phq():
    assert validate("T3_depressive_symptoms",["DPQ010"])==["DPQ010"]
def test_ckd():
    assert validate("T4_ckd_screening",["LBXSCR"])==["LBXSCR"]
