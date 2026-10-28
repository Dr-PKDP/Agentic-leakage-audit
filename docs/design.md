# Study design

## Constraint families

The principal run encodes six families of constraints that correspond to documented leakage and reporting failures in clinical prediction. Each family has four synthetic contexts.

| Family | Rule checked | Schema field proposed |
|---|---|---|
| F01 target dependency | Selected features must not derive from the target or from target-observation records | list of selected features |
| F02 availability | Selected features must be ready by the prediction cutoff | list of selected features |
| F03 fitting boundaries | Fitting, selection and calibration use permitted records, and groups stay apart | record identifiers for fitting, or train and held-out identifiers |
| F04 survey scope | Weight, population domain and variance claims match the survey design | weight identifier, population domain, or a Boolean variance claim |
| F05 permissions | A requested action has a current approval for that action, role, time and protocol version | requested action |
| F06 empirical claims | A validation claim requires completed, applicable evidence | Boolean claim of external validation |

The extended package adds F07, 17 contexts in which candidate variables carry NHANES 2015–2016 codebook labels. The evaluator scores F07 against author-written reference sets, and the evidence gate uses the name-prefix rules in `nhanes/lineage_validator.py`.

Each context holds scoped evidence records, an explicit rule, a cutoff and a proposal schema. Two initial proposals per context give 48 inputs in the principal run: 24 supported by the evidence, 21 contradicted and 3 with insufficient evidence.

## Workflows

Four critic streams review each input.

- `self_review`: the critic reviews the proposal.
- `structure_feedback`: the critic request also carries deterministic schema findings for the initial proposal.
- `evidence_critic`: the critic is instructed to check scope, dependencies, timestamps, partition roles, approvals and empirical support, and to cite evidence identifiers.
- `patch_critic`: same instructions as the evidence critic; the reviser returns a JSON patch instead of a full proposal.

A reviser request then receives the context, the initial proposal and the full review text. Reviews that reach the output limit are passed on unchanged. Self-review, structure feedback and the evidence critic return complete proposals. The patch stream returns an envelope with the context and proposal hashes and a list of operations. Each operation names one existing field, its exact current value, a new value, evidence identifiers and a rationale. An empty list means no change.

## Acceptance gates

Both gates consume the same generated patch.

Gate A (interface only) applies the patch when it is interface-valid and otherwise keeps the initial proposal. Interface validity requires matching hashes, a well-formed operation list, operations on existing top-level fields without duplicates, exact agreement of each stated old value, string rationales, list-valued evidence identifiers and a schema-valid result.

Gate B (evidence-guarded) applies the patch only when it is interface-valid and either makes no change or cites applicable evidence for every changed field and passes a support check of the resulting proposal against the evidence and the rule.

A response that is not valid JSON is recorded as not evaluated under both gates. No gate authorizes execution of an action.

## Scoring

A rule-based evaluator assigns each proposal one of three verdicts: `supported`, `contradicted_contract` or `insufficient_evidence`. Schema violations are recorded separately from evidential insufficiency.

- Repair: a contradicted initial proposal that becomes supported.
- Preservation: a supported initial proposal that stays supported.
- Harmful edit: a supported initial proposal that becomes contradicted.
- Final support: supported outputs over all inputs, with unparseable output counted as unsupported.

Unresolved initial proposals are analysed separately.

## Deterministic reference

`analysis/rule_reference.py` generates one proposal per context from the scoped facts and the proposal schema alone. It does not read the initial proposal, any model output or the expected verdict. For feature selection it computes each feature's readiness as the latest of its acquisition time plus processing delay, its release time and the readiness of its inputs. For the other schemas it selects permitted records, separates groups, matches weights to required components and domains, accepts only current approvals and asserts analyses or validations only when a completed record exists. It was written after the principal run.

## Model and generation settings

The principal run used Qwen3-8B served through an OpenAI-compatible endpoint under the identifier `p6-qwen3-8b`, temperature 0.2, a 1,024-token output limit, seed 42 for reviews and 1042 for revisions, no constrained decoding and no retries. The extended package uses the same limits with seeds s and s + 1000, and it can switch the thinking mode off through `chat_template_kwargs`.

The recorded model identifier is a serving label and does not fix the weight revision. Identical review requests did not always return identical text, so a fixed seed does not guarantee repeatable generation on the serving stack used.

## Limits

The contexts, the rules and the scorer were written by the study authors and were not adjudicated externally. The evaluator, the gates and the rule reference share the same encoded semantics, so agreement among them says nothing about whether those semantics are correct. The two patch gates share one generation per input and are not independent samples. Ninety-three of the 192 reviews stopped at the output limit, and resource use differs across streams. The inputs are repeated within contexts, so interval estimates that treat inputs as independent are optimistic; the cluster bootstrap in the paper resamples contexts. Nothing in the archive establishes performance on held-out contexts, clinical safety or national inference.
