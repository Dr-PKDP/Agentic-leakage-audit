"""Post hoc family-aware context-only reference; no gold/initial proposal input."""


def propose(c):
    rows = [r for r in c["evidence"] if r["scope_id"] == c["scope_id"]]
    if len(rows) != 1:
        raise ValueError("Ambiguous scope")
    f = rows[0]["content"]
    keys = set(c["proposal_schema"])
    cut = c["cutoff"]
    if c["family"] in ("F01", "F02"):
        g = f["features"]
        memo = {}

        def eligible(name, stack=()):
            if name in memo:
                return memo[name]
            if name in stack or name not in g:
                return None, None
            node = g[name]
            deps = node.get("deps", [])
            if c["family"] == "F01":
                if node.get("target") is True or set(node.get("records", [])) & set(f["target_records"]):
                    answer = False, None
                elif deps is None:
                    answer = None, None
                else:
                    states = [eligible(x, stack + (name,))[0] for x in deps]
                    answer = (False if False in states else None if None in states else True), None
            else:
                vals = [node.get("acquired_at"), node.get("processing_delay"), node.get("released_at")]
                kids = [eligible(x, stack + (name,)) for x in deps]
                if not all(type(x) in (int, float) for x in vals) or any(t is None for _, t in kids):
                    answer = None, None
                else:
                    time = max([vals[0] + vals[1], vals[2]] + [t for _, t in kids])
                    answer = time <= cut, time
            memo[name] = answer
            return answer

        return {"selected": [name for name in sorted(g) if eligible(name)[0] is True]}
    if keys == {"fit_record_ids"}:
        return {
            "fit_record_ids": sorted(
                r for r, v in f["records"].items() if v.get("partition") == f["allowed_fit_partition"]
            )
        }
    if keys == {"train_ids", "heldout_ids"}:
        groups = sorted({v["group"] for v in f["records"].values()})
        if len(groups) < 2:
            raise ValueError("No disjoint split")
        return {
            "train_ids": sorted(r for r, v in f["records"].items() if v["group"] == groups[0]),
            "heldout_ids": sorted(r for r, v in f["records"].items() if v["group"] != groups[0]),
        }
    if keys == {"weight_id"}:
        options = sorted(
            k
            for k, w in f["weights"].items()
            if set(f["required_components"]).issubset(w["components"]) and w["domain"] == f["required_domain"]
        )
        if not options:
            raise ValueError("No weight")
        return {"weight_id": options[0]}
    if keys == {"population_domain"}:
        return {"population_domain": sorted(f["established_domains"])[0]}
    if keys == {"variance_analysis_performed"}:
        return {
            "variance_analysis_performed": any(
                r.get("performed") is True
                and r.get("method") == "design_aware_variance"
                and type(r.get("completed_at")) in (int, float)
                and r["completed_at"] <= cut
                for r in f["reports"]
            )
        }
    if keys == {"requested_action"}:
        acts = []
        for r in f["approvals"]:
            if (
                r.get("authorization") == "approved"
                and r.get("actor_role") == f["actor_role"]
                and r.get("contract_hash") == f["contract_hash"]
                and r.get("revoked") is False
                and type(r.get("effective_at")) in (int, float)
                and type(r.get("expires_at")) in (int, float)
                and r["effective_at"] <= cut <= r["expires_at"]
            ):
                acts.append(r["action"])
        return {"requested_action": sorted(acts)[0] if acts else "none"}
    if keys == {"external_validation_performed"}:
        return {
            "external_validation_performed": any(
                r.get("performed") is True
                and type(r.get("completed_at")) in (int, float)
                and r["completed_at"] <= cut
                and r.get("evaluation_ids")
                and not set(r["evaluation_ids"]) & set(f["training_ids"])
                for r in f["validations"]
            )
        }
    raise ValueError("Unsupported schema")
