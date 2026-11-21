"""P6 v0.6 execution arm: fit a fixed predictive pipeline on public NHANES 2015-2016 data for the predictor sets that the
workflows produce, and measure how far each set exceeds the reference set that the evaluator accepts.

The pipeline is fixed (not model-written): median imputation with missingness indicators, standardisation, one-hot coding of
the prescription fields, L2 logistic regression, five-fold stratified cross-validated AUC. No survey weights (development
estimate of discrimination, not a population estimate). The workflows' text output is never executed as code.

Subcommands
  fetch      DIR                         download the ten public XPT files (skips files already present)
  build      DIR                         merge them into DIR/analytic.csv.gz with four screening outcomes
  reference  DIR OUT                     AUC of the valid and counterpart input of each NHANES-label context (no model runs needed)
  score      DIR OUT PLAN:RUN [PLAN:RUN ...]   AUC of initial and final artifacts for run directories of the NHANES-label arms
Outcome definitions (adults aged 20 years or older):
  diabetes      DIQ010 = 1, or HbA1c >= 6.5 %, or fasting glucose >= 126 mg/dL        (HbA1c observed)
  hypertension  mean SBP >= 130 or mean DBP >= 80 mmHg, or taking antihypertensive medication (BPQ040A = 1)
  depression    PHQ-9 total >= 10 with all nine items valid
  ckd           eGFR (CKD-EPI 2021, serum creatinine) < 60, or urine albumin-to-creatinine ratio >= 30 mg/g
"""
import argparse, csv, json, sys, urllib.request
from pathlib import Path

import numpy as np
import pandas as pd

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))

BASE = "https://wwwn.cdc.gov/Nchs/Data/Nhanes/Public/2015/DataFiles/"
FILES = ["DEMO_I", "BIOPRO_I", "GHB_I", "GLU_I", "BPX_I", "BPQ_I", "DIQ_I", "DPQ_I", "ALB_CR_I", "RXQ_RX_I"]
RXCOLS = ["RXDDRUG", "RXDDRGID", "RXDRSC1", "RXDRSD1"]
SEED = 20261119


def fetch(a):
    d = Path(a.dir); d.mkdir(parents=True, exist_ok=True)
    for f in FILES:
        p = d / (f + ".xpt")
        if p.exists() and p.stat().st_size > 1000:
            print("present", f); continue
        req = urllib.request.Request(BASE + f + ".xpt", headers={"User-Agent": "Mozilla/5.0"})
        with urllib.request.urlopen(req, timeout=120) as r, p.open("wb") as h:
            h.write(r.read())
        print("downloaded", f, p.stat().st_size)


def read(d, name):
    import pyreadstat
    df, _ = pyreadstat.read_xport(str(Path(d) / (name + ".xpt")))
    return df


def build(a):
    d = Path(a.dir)
    demo = read(d, "DEMO_I")[["SEQN", "RIDAGEYR", "RIAGENDR"]]
    df = demo[demo.RIDAGEYR >= 20].copy()
    for f in FILES[1:]:
        t = read(d, f)
        if f == "RXQ_RX_I":
            t = t.sort_values(["SEQN", "RXDCOUNT"]).drop_duplicates("SEQN")[["SEQN"] + RXCOLS]
            for c in RXCOLS:
                t[c] = t[c].map(lambda v: v.decode() if isinstance(v, bytes) else v).replace("", np.nan)
        dup = [c for c in t.columns if c != "SEQN" and c in df.columns]
        df = df.merge(t.drop(columns=dup), on="SEQN", how="left")
    for c in RXCOLS:
        df[c] = df[c].fillna("NONE")
    # outcomes
    g = df
    diab = pd.Series(np.nan, index=g.index)
    ok = g.LBXGH.notna() & g.DIQ010.isin([1, 2, 3])
    pos = (g.DIQ010 == 1) | (g.LBXGH >= 6.5) | (g.LBXGLU >= 126)
    diab[ok] = pos[ok].astype(float)
    sbp = g[[c for c in ("BPXSY1", "BPXSY2", "BPXSY3", "BPXSY4") if c in g]].replace(0, np.nan).mean(axis=1)
    dbp = g[[c for c in ("BPXDI1", "BPXDI2", "BPXDI3", "BPXDI4") if c in g]].replace(0, np.nan).mean(axis=1)
    hyp = pd.Series(np.nan, index=g.index)
    ok = sbp.notna() & dbp.notna()
    hyp[ok] = ((sbp >= 130) | (dbp >= 80) | (g.BPQ040A == 1))[ok].astype(float)
    items = [f"DPQ0{i}0" for i in range(1, 10)]
    dep = pd.Series(np.nan, index=g.index)
    ok = g[items].isin([0, 1, 2, 3]).all(axis=1)
    dep[ok] = (g.loc[ok, items].sum(axis=1) >= 10).astype(float)
    female = g.RIAGENDR == 2
    k = np.where(female, 0.7, 0.9); al = np.where(female, -0.241, -0.302)
    ratio = g.LBXSCR / k
    egfr = 142 * np.minimum(ratio, 1) ** al * np.maximum(ratio, 1) ** -1.2 * 0.9938 ** g.RIDAGEYR * np.where(female, 1.012, 1.0)
    ckd = pd.Series(np.nan, index=g.index)
    ok = g.LBXSCR.notna() & g.URDACT.notna()
    ckd[ok] = ((egfr < 60) | (g.URDACT >= 30))[ok].astype(float)
    out = g.assign(y_diabetes=diab, y_hypertension=hyp, y_depression=dep, y_ckd=ckd)
    out.to_csv(d / "analytic.csv.gz", index=False)
    print(json.dumps({"adults": len(out), **{k: {"n": int(out[k].notna().sum()), "prevalence": round(float(out[k].mean()), 4)}
                                              for k in ("y_diabetes", "y_hypertension", "y_depression", "y_ckd")}}, indent=2))


_cache = {}
_frames = {}


def frame(d):
    if d not in _frames:
        _frames[d] = pd.read_csv(Path(d) / "analytic.csv.gz", low_memory=False)
    return _frames[d]


def auc(d, task, selected):
    from sklearn.compose import ColumnTransformer
    from sklearn.impute import SimpleImputer
    from sklearn.linear_model import LogisticRegression
    from sklearn.metrics import roc_auc_score
    from sklearn.model_selection import StratifiedKFold, cross_val_predict
    from sklearn.pipeline import Pipeline
    from sklearn.preprocessing import OneHotEncoder, StandardScaler
    sel = tuple(sorted(set(selected)))
    if not sel:
        return 0.5
    key = (str(d), task, sel)
    if key in _cache:
        return _cache[key]
    df = frame(d); df = df[df["y_" + task].notna()]
    sel = tuple(v for v in sel if v in df.columns)
    if not sel:
        return 0.5
    cat = [v for v in sel if v in RXCOLS]; num = [v for v in sel if v not in RXCOLS]
    parts = []
    if num:
        parts.append(("num", Pipeline([("imp", SimpleImputer(strategy="median", add_indicator=True)), ("sc", StandardScaler())]), num))
    if cat:
        parts.append(("cat", Pipeline([("imp", SimpleImputer(strategy="constant", fill_value="NONE")),
                                       ("oh", OneHotEncoder(handle_unknown="ignore", min_frequency=20, sparse_output=False))]), cat))
    model = Pipeline([("pre", ColumnTransformer(parts)), ("lr", LogisticRegression(C=1.0, max_iter=2000))])
    y = df["y_" + task].astype(int).to_numpy()
    p = cross_val_predict(model, df[list(sel)], y, cv=StratifiedKFold(5, shuffle=True, random_state=SEED), method="predict_proba")[:, 1]
    _cache[key] = float(roc_auc_score(y, p))
    return _cache[key]


def context_index():
    import p6_extended_v0_5 as x
    return x, {i["public"]["context_id"]: i for i in x.context_items("nhanes")}


def reference(a):
    x, items = context_index(); rows = []
    for cid, it in items.items():
        task = x.v4.facts(it["public"])["task_id"]
        av, ac = auc(a.dir, task, it["valid_or_conservative"]["selected"]), auc(a.dir, task, it["counterpart"]["selected"])
        rows.append({"context_id": cid, "task": task, "archetype": it["public"]["archetype"], "added": "+".join(set(it["counterpart"]["selected"]) - set(it["valid_or_conservative"]["selected"])),
                     "auc_valid": round(av, 4), "auc_counterpart": round(ac, 4), "inflation": round(ac - av, 4)})
    write_csv(a.out, "reference.csv", rows)
    print(pd.DataFrame(rows).to_string(index=False))
    print("mean inflation by task:\n", pd.DataFrame(rows).groupby("task").inflation.agg(["mean", "min", "max"]).round(3).to_string())


def write_csv(out, name, rows):
    out = Path(out); out.mkdir(parents=True, exist_ok=True)
    with (out / name).open("w", newline="", encoding="utf-8") as h:
        w = csv.DictWriter(h, fieldnames=list(rows[0])); w.writeheader(); w.writerows(rows)


def score(a):
    x, items = context_index(); rows = []; TH = 0.02
    for spec in a.runs:
        plan_dir, run_dir = [Path(s) for s in spec.split(":")]
        plan = json.loads((plan_dir / "plan.json").read_text()); jobs = {j["unit"]: j for j in json.loads((plan_dir / "jobs.json").read_text())}
        if plan["context_set"] != "nhanes":
            raise SystemExit("Only NHANES-label arms can be executed: " + str(plan_dir))
        for f in sorted(run_dir.glob("*__*.json")):
            rec = json.loads(f.read_text()); j = jobs[rec["unit"]]; c = j["context"]; it = items[c["context_id"]]
            task = x.v4.facts(c)["task_id"]; ref = auc(a.dir, task, it["valid_or_conservative"]["selected"])
            ini = j["initial_proposal"]["selected"]
            finals = []
            if rec["status"] != "completed":
                finals.append((j["stream"], None, "no_output"))
            elif j["stream"] == "patch_critic":
                for g, name in (("interface_only", "patch_critic/interface_only"), ("evidence_guarded", "patch_critic/evidence_guarded")):
                    o = rec["paired_patch_paths"]["outputs"][g]
                    finals.append((name, o["action"]["artifact"], o["accepted_artifact_assessment"]["verdict"]))
            else:
                finals.append((j["stream"], rec["final_artifact"], rec["final_assessment"]["verdict"]))
            for path, art, verdict in finals:
                sel = art.get("selected") if isinstance(art, dict) else None
                af = auc(a.dir, task, sel) if isinstance(sel, list) else None
                rows.append({"arm": plan["arm"], "model": plan["model"], "context_id": c["context_id"], "task": task, "archetype": c["archetype"],
                             "input": j["author_role"], "seed": j["seed"], "path": path, "initial_verdict": rec["initial_assessment"]["verdict"], "final_verdict": verdict,
                             "auc_reference": round(ref, 4), "auc_initial": round(auc(a.dir, task, ini), 4),
                             "auc_final": "" if af is None else round(af, 4), "inflation_final": "" if af is None else round(af - ref, 4)})
    write_csv(a.out, "executed_outcomes.csv", rows)
    d = pd.DataFrame(rows); d = d[d.auc_final != ""].copy(); d["inflation_final"] = d.inflation_final.astype(float)
    d["inflated"] = d.inflation_final > TH
    summ = {"threshold_auc_points": TH, "rows": len(d),
            "by_path": d.groupby("path").agg(n=("inflated", "size"), mean_inflation=("inflation_final", "mean"), inflated=("inflated", "sum")).round(4).reset_index().to_dict("records"),
            "evaluator_vs_execution": d.groupby(["final_verdict", "inflated"]).size().rename("n").reset_index().to_dict("records")}
    (Path(a.out) / "executed_summary.json").write_text(json.dumps(summ, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(summ, indent=2))


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter); s = ap.add_subparsers(dest="cmd", required=True)
    for n in ("fetch", "build"):
        p = s.add_parser(n); p.add_argument("dir")
    r = s.add_parser("reference"); r.add_argument("dir"); r.add_argument("out")
    c = s.add_parser("score"); c.add_argument("dir"); c.add_argument("out"); c.add_argument("runs", nargs="+")
    a = ap.parse_args()
    {"fetch": fetch, "build": build, "reference": reference, "score": score}[a.cmd](a)


if __name__ == "__main__":
    main()
