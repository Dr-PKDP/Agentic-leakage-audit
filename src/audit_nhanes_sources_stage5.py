from __future__ import annotations

import argparse
import csv
import hashlib
import json
import sys
import tempfile
import urllib.request
from datetime import datetime, timezone
from pathlib import Path

import pandas as pd

BASE = "https://wwwn.cdc.gov/Nchs/Data/Nhanes/Public"

CYCLES = {
    "G": "2011",
    "H": "2013",
    "I": "2015",
}

REQUIRED = {
    "DEMO": ["SEQN", "RIDAGEYR", "RIAGENDR", "RIDRETH3", "WTMEC2YR", "SDMVPSU", "SDMVSTRA"],
    "ALB_CR": ["SEQN", "URXUMA", "URXUCR", "URDACT"],
    "BIOPRO": ["SEQN", "LBXSCR", "LBDSCRSI"],
    "RXQ_RX": ["SEQN", "RXDUSE", "RXDDRUG", "RXDDRGID", "RXDCOUNT"],
    "GLU": ["SEQN", "WTSAF2YR", "LBXGLU", "LBDGLUSI"],
    "DIQ": ["SEQN", "DIQ010"],
    "BPX": ["SEQN", "BPXSY1", "BPXDI1", "BPXSY2", "BPXDI2", "BPXSY3", "BPXDI3"],
    "BPQ": ["SEQN", "BPQ020", "BPQ040A"],
    "DPQ": ["SEQN", "DPQ010", "DPQ020", "DPQ030", "DPQ040", "DPQ050", "DPQ060", "DPQ070", "DPQ080", "DPQ090"],
    "MCQ": ["SEQN", "MCQ160C", "MCQ160E", "MCQ160F"],
}

def build_registry():
    items = []

    for suffix, year in CYCLES.items():
        for stem, columns in REQUIRED.items():
            filename = f"{stem}_{suffix}.XPT"
            items.append(
                {
                    "id": filename[:-4],
                    "filename": filename,
                    "url": f"{BASE}/{year}/DataFiles/{filename}",
                    "required_columns": columns,
                    "require_unique_seqn": stem != "RXQ_RX",
                }
            )

    items.extend(
        [
            {
                "id": "FASTQX_G",
                "filename": "FASTQX_G.XPT",
                "url": f"{BASE}/2011/DataFiles/FASTQX_G.XPT",
                "required_columns": ["SEQN", "PHAFSTHR", "PHAFSTMN"],
                "require_unique_seqn": True,
            },
            {
                "id": "FASTQX_H",
                "filename": "FASTQX_H.XPT",
                "url": f"{BASE}/2013/DataFiles/FASTQX_H.XPT",
                "required_columns": ["SEQN", "PHAFSTHR", "PHAFSTMN"],
                "require_unique_seqn": True,
            },
            {
                "id": "FASTQX_I",
                "filename": "FASTQX_I.XPT",
                "url": f"{BASE}/2015/DataFiles/FASTQX_I.XPT",
                "required_columns": ["SEQN", "PHAFSTHR", "PHAFSTMN"],
                "require_unique_seqn": True,
            },
            {
                "id": "RXQ_DRUG",
                "filename": "RXQ_DRUG.XPT",
                "url": f"{BASE}/1988/DataFiles/RXQ_DRUG.XPT",
                "required_columns": [
                    "RXDDRGID",
                    "RXDDRUG",
                    "RXDINGFL",
                    "RXDDCI1A",
                    "RXDDCN1A",
                ],
                "require_unique_seqn": False,
            },
            {
                "id": "DEMO_L",
                "filename": "DEMO_L.XPT",
                "url": f"{BASE}/2021/DataFiles/DEMO_L.XPT",
                "required_columns": [
                    "SEQN",
                    "RIDAGEYR",
                    "RIAGENDR",
                    "WTMEC2YR",
                    "SDMVPSU",
                    "SDMVSTRA",
                ],
                "require_unique_seqn": True,
            },
            {
                "id": "BPXO_L",
                "filename": "BPXO_L.XPT",
                "url": f"{BASE}/2021/DataFiles/BPXO_L.XPT",
                "required_columns": [
                    "SEQN",
                    "BPXOSY1",
                    "BPXOSY2",
                    "BPXOSY3",
                    "BPXODI1",
                    "BPXODI2",
                    "BPXODI3",
                ],
                "require_unique_seqn": True,
            },
            {
                "id": "BPQ_L",
                "filename": "BPQ_L.XPT",
                "url": f"{BASE}/2021/DataFiles/BPQ_L.XPT",
                "required_columns": ["SEQN", "BPQ020", "BPQ150"],
                "require_unique_seqn": True,
            },
        ]
    )

    return items

def sha256(path):
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()

def download(url, destination):
    request = urllib.request.Request(url, headers={"User-Agent": "P6-NHANES-source-audit/1.0"})
    with urllib.request.urlopen(request, timeout=120) as response:
        payload = response.read()

    if len(payload) < 1024 or payload.lstrip().startswith(b"<"):
        raise ValueError("CDC response is unexpectedly small or looks like HTML, not an XPT file.")

    with tempfile.NamedTemporaryFile(delete=False, dir=destination.parent, suffix=".part") as handle:
        handle.write(payload)
        temporary = Path(handle.name)

    temporary.replace(destination)

def validate(item, raw_directory, download_missing):
    path = raw_directory / item["filename"]
    result = {
        "id": item["id"],
        "filename": item["filename"],
        "url": item["url"],
        "downloaded": False,
        "exists": path.exists(),
        "status": "FAIL",
        "rows": "",
        "columns": "",
        "missing_columns": "",
        "sha256": "",
        "error": "",
    }

    try:
        if not path.exists() and download_missing:
            print(f"Downloading {item['filename']}...")
            download(item["url"], path)
            result["downloaded"] = True
            result["exists"] = True

        if not path.exists():
            result["error"] = "Missing local file."
            return result

        data = pd.read_sas(path, format="xport")
        missing = [column for column in item["required_columns"] if column not in data.columns]

        result["rows"] = len(data)
        result["columns"] = len(data.columns)
        result["missing_columns"] = ";".join(missing)
        result["sha256"] = sha256(path)

        if missing:
            result["error"] = "Required columns absent."
            return result

        if item["require_unique_seqn"] and "SEQN" in data.columns and data["SEQN"].duplicated().any():
            result["error"] = "SEQN must be unique but duplicate identifiers were found."
            return result

        result["status"] = "PASS"
        return result

    except Exception as error:
        result["error"] = f"{type(error).__name__}: {error}"
        return result

def write_csv(path, rows):
    fields = list(rows[0].keys())
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields)
        writer.writeheader()
        writer.writerows(rows)

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--raw-dir", default="data/raw/nhanes")
    parser.add_argument("--manifest-dir", default="data/manifests")
    parser.add_argument("--output-dir", default="outputs/source_audits")
    parser.add_argument("--download-missing", action="store_true")
    arguments = parser.parse_args()

    raw_directory = Path(arguments.raw_dir)
    manifest_directory = Path(arguments.manifest_dir)
    output_directory = Path(arguments.output_dir)

    for directory in [raw_directory, manifest_directory, output_directory]:
        directory.mkdir(parents=True, exist_ok=True)

    records = [validate(item, raw_directory, arguments.download_missing) for item in build_registry()]
    passed = sum(record["status"] == "PASS" for record in records)
    failed = len(records) - passed

    summary = {
        "generated_utc": datetime.now(timezone.utc).isoformat(),
        "total": len(records),
        "passed": passed,
        "failed": failed,
        "download_missing": arguments.download_missing,
    }

    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    write_csv(manifest_directory / "P6_STAGE5_NHANES_SOURCE_MANIFEST_v1.csv", records)
    write_csv(output_directory / f"P6_STAGE5_NHANES_SOURCE_AUDIT_{stamp}.csv", records)

    payload = {"summary": summary, "files": records}
    (manifest_directory / "P6_STAGE5_NHANES_SOURCE_MANIFEST_v1.json").write_text(
        json.dumps(payload, indent=2), encoding="utf-8"
    )
    (output_directory / f"P6_STAGE5_NHANES_SOURCE_AUDIT_{stamp}.json").write_text(
        json.dumps(payload, indent=2), encoding="utf-8"
    )

    print(json.dumps(summary, indent=2))
    if failed:
        sys.exit(1)

if __name__ == "__main__":
    main()

