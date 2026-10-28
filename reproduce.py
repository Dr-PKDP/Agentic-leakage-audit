"""Entry point for offline replay of the archived runs.

Default: verify the file manifest, then recompute every reported score from the archived
requests and responses. No network access, model server, GPU or participant data is used.

    python reproduce.py [--out DIR]

Optional refit of the fixed depression reference on the public NHANES 2017-2018 files:

    python reproduce.py --check-inputs --demo DEMO_J.xpt --dpq DPQ_J.xpt
    python reproduce.py --allow-fit --demo DEMO_J.xpt --dpq DPQ_J.xpt --out DIR

Maintainers: `python reproduce.py --write-manifest` regenerates MANIFEST.json after a deliberate change.
"""
import argparse
import hashlib
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT / "analysis"))
MANIFEST = ROOT / "MANIFEST.json"
SCOPE = ("experiments", "analysis", "nhanes", "results", "reproduce.py")


def scoped_files():
    for entry in SCOPE:
        path = ROOT / entry
        found = [path] if path.is_file() else sorted(path.rglob("*"))
        for f in found:
            if f.is_file() and "__pycache__" not in f.parts and f.suffix != ".pyc":
                yield f


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def write_manifest():
    files = [
        {"path": f.relative_to(ROOT).as_posix(), "bytes": f.stat().st_size, "sha256": digest(f)}
        for f in scoped_files()
        if f != ROOT / "reproduce.py"
    ]
    MANIFEST.write_text(json.dumps({"files": files}, indent=1) + "\n", encoding="utf-8")
    print(f"wrote {MANIFEST.name} with {len(files)} files")


def verify():
    listed = json.loads(MANIFEST.read_text(encoding="utf-8"))["files"]
    for entry in listed:
        path = ROOT / entry["path"]
        if not path.is_file() or digest(path) != entry["sha256"]:
            raise SystemExit(f"manifest check failed: {entry['path']}")
    return len(listed)


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--out", type=Path, default=ROOT / "_generated")
    ap.add_argument("--check-inputs", action="store_true")
    ap.add_argument("--allow-fit", action="store_true")
    ap.add_argument("--demo", type=Path)
    ap.add_argument("--dpq", type=Path)
    ap.add_argument("--write-manifest", action="store_true")
    a = ap.parse_args()

    if a.write_manifest:
        write_manifest()
        return
    verify()

    if a.allow_fit or a.check_inputs:
        if not (a.demo and a.dpq):
            ap.error("--demo and --dpq are required")
        import reference_portable

        if a.allow_fit:
            reference_portable.refit(ROOT, a.demo, a.dpq, a.out)
        else:
            print(json.dumps(reference_portable.check_inputs(ROOT, a.demo, a.dpq), indent=2))
        return

    import replay

    if a.out.exists():
        raise SystemExit(f"{a.out} exists; choose a new --out directory")
    a.out.mkdir(parents=True)
    result = {
        "principal": replay.principal(ROOT, a.out),
        "pilot": replay.pilot(ROOT, a.out),
        "reference": replay.reference_metadata(ROOT, a.out),
        "new_model_calls": 0,
        "new_participant_fits": 0,
    }
    replay.write(a.out / "summary.json", result)
    print(json.dumps(result, indent=2))


if __name__ == "__main__":
    main()
