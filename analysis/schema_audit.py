"""Audit of the name-prefix lineage rules against the NHANES development schema.

Compares the variables that the rules exclude with a reference set of variables, compiled from the
2015-2016 NHANES codebooks, that define, restate or are clinically tied to each task's outcome.
Reads nhanes/metadata and writes results/nhanes/schema_audit.json and schema_audit_reference.csv.
"""

import csv, re, json, sys, collections
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO))
from nhanes.lineage_validator import flagged as rule_flagged, RULES

S = list(csv.DictReader(open(REPO / "nhanes/metadata/development_schema.csv")))
H = list(csv.DictReader(open(REPO / "nhanes/metadata/cross_cycle_harmonization.csv")))
OUT = REPO / "results/nhanes"
OUT.mkdir(parents=True, exist_ok=True)
comp = lambda f: re.sub(r"_[GHI]$", "", f)
present = collections.defaultdict(set)  # variable -> set(components)
cyc = collections.defaultdict(set)
for r in S:
    present[r["variable"]].add(comp(r["file"]))
    cyc[(comp(r["file"]), r["variable"])].add(r["cycle"])
allvars = sorted(v for v in present if v != "SEQN")
RX = ["RXDDRUG", "RXDDRGID", "RXDRSC1", "RXDRSC2", "RXDRSC3", "RXDRSD1", "RXDRSD2", "RXDRSD3"]
LAB = {  # labels from the NHANES 2015-2016 codebooks (wwwn.cdc.gov)
    "LBXGH": "Glycohemoglobin (%)",
    "LBXGLU": "Fasting Glucose (mg/dL)",
    "LBDGLUSI": "Fasting Glucose (mmol/L)",
    "LBXGLT": "Two Hour Glucose (OGTT) (mg/dL)",
    "LBDGLTSI": "Two Hour Glucose (OGTT) (mmol/L)",
    "GTDCODE": "Incomplete OGTT Comment Code",
    "LBXSGL": "Glucose, refrigerated serum (mg/dL)",
    "LBDSGLSI": "Glucose, refrigerated serum (mmol/L)",
    "DID040": "Age when first told you had diabetes",
    "DIQ050": "Taking insulin now",
    "DID060": "How long taking insulin",
    "DIQ060U": "Unit of measure (month/year)",
    "DIQ070": "Take diabetic pills to lower blood sugar",
    "DIQ080": "Diabetes affected eyes/had retinopathy",
    "DIQ300S": "What was your recent SBP",
    "DIQ300D": "What was your recent DBP",
    "BPQ020": "Ever told you had high blood pressure",
    "BPQ030": "Told had high blood pressure - 2+ times",
    "BPD035": "Age told had hypertension",
    "BPQ040A": "Taking prescription for hypertension",
    "BPQ050A": "Now taking prescribed medicine for HBP",
    "LBXSCR": "Creatinine, refrigerated serum (mg/dL)",
    "LBDSCRSI": "Creatinine, refrigerated serum (umol/L)",
    "URXUMA": "Albumin, urine (ug/mL)",
    "URXUMS": "Albumin, urine (mg/L)",
    "URDUMALC": "Albumin, urine comment code",
    "URXUCR": "Creatinine, urine (mg/dL)",
    "URXCRS": "Creatinine, urine (umol/L)",
    "URDUCRLC": "Creatinine, urine comment code",
    "URDACT": "Albumin creatinine ratio (mg/g)",
    "RXDDRUG": "Generic drug name",
    "RXDDRGID": "Generic drug code",
    "RXDRSC1": "ICD-10-CM code 1",
    "RXDRSC2": "ICD-10-CM code 2",
    "RXDRSC3": "ICD-10-CM code 3",
    "RXDRSD1": "ICD-10-CM code 1 description",
    "RXDRSD2": "ICD-10-CM code 2 description",
    "RXDRSD3": "ICD-10-CM code 3 description",
}
for i in range(1, 5):
    LAB[f"BPXSY{i}"] = f"Systolic: Blood pres ({i}) mm Hg"
    LAB[f"BPXDI{i}"] = f"Diastolic: Blood pres ({i}) mm Hg"
for i in range(1, 10):
    LAB[f"DPQ0{i}0"] = f"PHQ-9 item {i}"
LAB["DPQ100"] = "Difficulty these problems have caused"
REF = {  # task -> {variable: category}  A defining measure/instrument; B same quantity re-expressed or held in another component; C diagnosis, treatment or indication
    "T1_diabetes_screening": {
        **{v: "A" for v in ["LBXGH", "LBXGLU", "LBXGLT"]},
        **{v: "B" for v in ["LBDGLUSI", "LBDGLTSI", "GTDCODE", "LBXSGL", "LBDSGLSI"]},
        **{v: "C" for v in ["DID040", "DIQ050", "DID060", "DIQ060U", "DIQ070", "DIQ080"] + RX},
    },
    "T2_hypertension_screening": {
        **{f"BPXSY{i}": "A" for i in range(1, 5)},
        **{f"BPXDI{i}": "A" for i in range(1, 5)},
        **{v: "B" for v in ["DIQ300S", "DIQ300D"]},
        **{v: "C" for v in ["BPQ020", "BPQ030", "BPD035", "BPQ040A", "BPQ050A"] + RX},
    },
    "T3_depressive_symptoms": {**{f"DPQ0{i}0": "A" for i in range(1, 10)}, "DPQ100": "A", **{v: "C" for v in RX}},
    "T4_ckd_screening": {
        **{v: "A" for v in ["LBXSCR", "URXUMA", "URXUCR", "URDACT"]},
        **{v: "B" for v in ["LBDSCRSI", "URXUMS", "URXCRS", "URDUMALC", "URDUCRLC"]},
        **{v: "C" for v in RX},
    },
}
out = {}
rows = []
for t, ref in REF.items():
    absent = [v for v in ref if v not in present]
    ref = {v: c for v, c in ref.items() if v in present}
    flagged = set(rule_flagged(t, allvars))
    hit = [v for v in ref if v in flagged]
    miss = [v for v in ref if v not in flagged]
    over = sorted(v for v in flagged if v not in ref and not re.match(r"^(SDMVSTRA|SDMVPSU|WTMEC|WTINT)", v))
    byc = {}
    for c in "ABC":
        r = [v for v in ref if ref[v] == c]
        byc[c] = {"n": len(r), "flagged": sum(v in flagged for v in r)}
    out[t] = {
        "reference_n": len(ref),
        "flagged_of_reference": len(hit),
        "missed": len(miss),
        "rule_flags_total": len(flagged),
        "flagged_not_in_reference": len(over),
        "by_category": byc,
        "ref_absent_from_schema": absent,
        "missed_vars": miss,
    }
    for v in ref:
        rows.append(
            [
                t,
                v,
                ref[v],
                ";".join(sorted(present[v])),
                LAB.get(v, "label not retrieved"),
                "flagged" if v in flagged else "MISSED",
            ]
        )
# rule patterns that match no variable in the acquired schema
pat = {}
for t, p in RULES.items():
    parts = [x for q in p for x in q.strip("^()").split("|")]
    pat[t] = [x for x in parts if not any(re.match("^" + x, v) for v in allvars)]
out["rule_prefixes_matching_no_schema_variable"] = pat
nc = collections.Counter(r["n_cycles"] for r in H)
out["harmonization"] = {"variables": len(H), "by_n_cycles": dict(nc)}
out["schema_variables_excluding_SEQN"] = len(allvars)
json.dump(out, open(OUT / "schema_audit.json", "w"), indent=1)
with open(OUT / "schema_audit_reference.csv", "w", newline="") as f:
    w = csv.writer(f)
    w.writerow(["task", "variable", "category", "components", "label_2015_2016", "repository_rule"])
    w.writerows(rows)
print(
    json.dumps(
        {
            k: (
                v
                if k.startswith("rule") or k in ("harmonization", "schema_variables_excluding_SEQN")
                else {x: y for x, y in v.items() if x != "missed_vars"}
            )
            for k, v in out.items()
        },
        indent=1,
    )
)
