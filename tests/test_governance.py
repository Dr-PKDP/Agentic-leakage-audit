import json,sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).parents[1]/"src"))
from governance import classify,evaluate_proposal,load_ontology
O=Path(__file__).parents[1]/"protocol"/"feature_governance_v1.json"
def test_diabetes_outcome_blocked():
 o=load_ontology(O);assert classify("T1_diabetes_screening","LBXGH",o)[0]=="blocked"
def test_survey_analysis_only():
 o=load_ontology(O);assert classify("T1_diabetes_screening","WTMEC2YR",o)[0]=="analysis_only"
def test_allowed_requires_review():
 o=load_ontology(O);assert classify("T1_diabetes_screening","RIDAGEYR",o)[0]=="allowed"
def test_bp_blocked():
 o=load_ontology(O);assert classify("T2_hypertension_screening","BPXSY1",o)[0]=="blocked"
def test_locked_partition_rejected():
 try:evaluate_proposal("T1_diabetes_screening",["RIDAGEYR"],O,partition="2017-2018")
 except ValueError:return
 assert False
