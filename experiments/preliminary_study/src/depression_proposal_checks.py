PENDING = {"predictor_codebook_and_availability_review", "income_missingness_handling", "survey_weight_approval", "evaluation_design"}
FIELDS = {"predictors", "excluded", "survey_plan", "validation_plan", "unresolved_decisions"}

def check_proposal(proposal):
    reasons = []
    if not isinstance(proposal, dict) or set(proposal) != FIELDS:
        reasons.append("Expected exactly the five proposal fields.")
    else:
        for field in ("predictors", "excluded", "unresolved_decisions"):
            values = proposal[field]
            valid = isinstance(values, list) and all(isinstance(x, str) and bool(x.strip()) for x in values)
            if not valid:
                reasons.append(field + " must be a list of nonblank strings.")
            elif len(values) != len(set(values)):
                reasons.append(field + " contains duplicates.")
        for field in ("survey_plan", "validation_plan"):
            value = proposal[field]
            if not isinstance(value, str) or not value.strip():
                reasons.append(field + " must be a nonblank string.")
        pending = proposal["unresolved_decisions"]
        if isinstance(pending, list) and all(isinstance(x, str) for x in pending):
            if set(pending) != PENDING:
                reasons.append("Pending-decision identifiers do not match the required set.")
    return {"checker_version": "depression_structure_v1", "structure_valid": not reasons, "reasons": reasons, "scientific_validity": "not_assessed", "execution_authorized": False}
