from __future__ import annotations

import argparse
import json
from datetime import datetime, timezone
from pathlib import Path

from src.stage9_proposal_validator import validate_proposal


REPO_ROOT = Path(__file__).resolve().parents[1]
RUN_DIR = REPO_ROOT / "outputs" / "stage9_runs"


def load_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def save_json(data: dict, path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, indent=2), encoding="utf-8")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--run-id", required=True)
    parser.add_argument("--proposal-file", required=True)
    args = parser.parse_args()

    manifest_path = RUN_DIR / f"{args.run_id}_manifest.json"
    proposal_path = Path(args.proposal_file)

    if not manifest_path.exists():
        raise FileNotFoundError(f"Missing manifest: {manifest_path}")

    if not proposal_path.exists():
        raise FileNotFoundError(f"Missing proposal: {proposal_path}")

    manifest = load_json(manifest_path)
    proposal = load_json(proposal_path)

    required_match_fields = ["run_id", "agent_name", "seed"]
    mismatches = {
        field: {
            "manifest": manifest.get(field),
            "proposal": proposal.get(field),
        }
        for field in required_match_fields
        if manifest.get(field) != proposal.get(field)
    }

    if mismatches:
        validation = {
            "status": "fail",
            "details": (
                "Proposal identity does not match its pre-registered "
                f"manifest: {mismatches}"
            ),
        }
    else:
        validation = validate_proposal(proposal)

    record = {
        "run_id": args.run_id,
        "captured_utc": datetime.now(timezone.utc).isoformat(),
        "proposal_file_source": str(proposal_path),
        "proposal": proposal,
        "validation": validation,
    }

    output_path = RUN_DIR / f"{args.run_id}_proposal_record.json"
    save_json(record, output_path)

    print(output_path)
    print(json.dumps(validation, indent=2))


if __name__ == "__main__":
    main()