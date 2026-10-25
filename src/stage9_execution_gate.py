from __future__ import annotations


def check_execution_gate(
    manifest: dict,
    proposal_record: dict | None,
) -> dict[str, str]:
    if proposal_record is None:
        return {
            "status": "fail",
            "details": "Missing captured proposal record.",
        }

    if proposal_record.get("run_id") != manifest.get("run_id"):
        return {
            "status": "fail",
            "details": "Proposal record run_id does not match manifest.",
        }

    validation = proposal_record.get("validation", {})
    if validation.get("status") != "pass":
        return {
            "status": "fail",
            "details": "Captured proposal did not pass validation.",
        }

    if manifest.get("test_labels_accessed"):
        return {
            "status": "fail",
            "details": "Locked test labels were already accessed by this run.",
        }

    return {
        "status": "pass",
        "details": (
            "Captured proposal passed validation and may proceed to "
            "pre-test model fitting."
        ),
    }