"""Pilot consistency gate; not scientific validation."""

def evaluate_gate(review):
    fields = {"decision", "issues", "required_changes"}

    valid = (
        isinstance(review, dict)
        and set(review) == fields
        and isinstance(review["decision"], str)
        and review["decision"] in {"approve", "revise", "reject"}
        and isinstance(review["issues"], list)
        and isinstance(review["required_changes"], list)
        and all(
            isinstance(item, str) and bool(item.strip())
            for item in review["issues"]
        )
        and all(
            isinstance(item, str) and bool(item.strip())
            for item in review["required_changes"]
        )
    )

    reasons = []
    if not valid:
        reasons.append("Invalid critic review structure.")
    else:
        if review["decision"] != "approve":
            reasons.append("Critic did not approve.")
        if review["issues"]:
            reasons.append("Critic reported unresolved issues.")
        if review["required_changes"]:
            reasons.append("Critic requested changes.")

    allowed = valid and not reasons
    return {
        "gate_version": "pilot_v2",
        "execution_allowed": allowed,
        "gate_decision": "allow" if allowed else "block",
        "reasons": reasons,
        "scope": "consistency_gate_only_not_scientific_validation"
    }
