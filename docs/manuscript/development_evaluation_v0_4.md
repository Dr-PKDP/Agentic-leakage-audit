# Synthetic development evaluation: manuscript insert

## Methods and analysis
We evaluated 24 authored synthetic contexts across six constraint families using 48 initial proposals: 24 supported, 21 contradicted and three unresolved. Four streams used p6-qwen3-8b, review seed 42, revision seed 1042, temperature 0.2 and a 1024-token ceiling per request. Each unit used review and revision, giving 192 units and 384 requests. The same generated patch was processed by interface-only and evidence-guarded acceptance. No participant records or generated-code execution were involved.

Artifact assessment did not consume acceptance decisions. Guard and evaluator shared authored contract semantics, not independent scientific ground truth. Repair used all 21 contradicted inputs; preservation used all 24 supported inputs; supported-output counts used all 48 attempts. Schema failures and unparseable outputs were not treated as valid uncertainty decisions. Contexts were development-exposed, dependence was unresolved and no confirmatory inference was performed. Request ceilings were matched, not realized cost.

Both uploaded exports were inspected. Approved source/job hashes and request identities were checked; all 384 payloads were reconstructed. Offline replay of the unchanged parser and pure evaluation/acceptance functions reproduced all 192 saved units and 48 references exactly. No model was rerun or primary score changed. This is computational reproducibility of the supplied implementation, not independent adjudication.

## Results
| Path | Repairs / 21 | Supported retained / 24 | Observed harmful edits | Supported outputs / 48 |
|---|---:|---:|---:|---:|
| Self-review | 16 | 24 | 0 | 42 |
| Structure feedback | 17 | 23 | 1 | 42 |
| Evidence critic | 16 | 23 | 1 | 41 |
| Patch: interface-only | 20 | 22 | 1 | 45 |
| Patch: evidence-guarded | 20 | 23 | 0 | 46 |

Among 47 assessable patch inputs, both paths produced support in 45, guarded alone produced support in one, and both produced contradiction in one. The remaining input had one shared unparseable patch. Exactly one retained artifact differed: interface-only added DERIVED with dependency readiness 12 beyond cutoff 10; guarded rejected it and retained SAFE. Both paths repaired the same 20 known-error proposal IDs.

Both paths also rejected a stale-contract correction addressed to proposal.requested_action rather than requested_action and retained the incorrect fit request. Execution authorization remained false. Two strict parsing failures contained fenced JSON; two schema failures contained empty population_domain or requested_action strings. The five targeted revisions ended with stop and used 9-288 tokens. Fence-only parsing was diagnostic, not rescoring.

The evidence critic returned selected=[] twice: one counted repair of a contradicted input and one supported-to-supported transition. The contract permitted empty selection, but neither established useful task completion. No other path returned an empty selection. Original scores remain unchanged.

### Resources and generation diagnostics
The 384 completed requests used 346336 prompt tokens and 197235 completion tokens, totaling 543571. Summed client request duration was 3828.13 seconds, not independently measured wall time, GPU time or monetary cost. Patch acceptance paths share generation. Per-stream totals are in results/agent_development_v0_4_resources.csv.

Ninety-three of 192 reviews (48.4%) ended at the 1024-token limit: 21 self-review, 12 structure-feedback, 30 evidence-critic and 30 patch-critic. All 192 revisions ended with stop. The revision stage consumed returned review text without a truncation-specific fallback. The earlier five-revision audit must not be generalized to all review stages.

All 48 initial proposals were schema-valid; structural feedback therefore appended Structural findings: [] in every case. This was a structural-check prompt condition, not active initial-schema repair. Evidence-critic and patch-critic review payloads were identical for all 48 pairs, but returned text matched in eight and differed in 40. The logged seed did not guarantee identical observed responses; the cause is unestablished.

## Discussion
The supported guard effect is one prevented harmful edit, not an increased repair count. Self-review also showed no observed harmful edit. The guarded zero-harm observation covers 23 evaluated supported inputs plus one unevaluated input. Rejection retaining an incorrect proposal is unsuccessful repair. Contract support, preservation of useful content, task completion and execution safety are distinct outcomes.

Review cap hits, unequal realized resources, different output interfaces and nonidentical review text constrain cross-stream attribution. The acceptance-stage comparison remains paired on one actual generated patch. Prior pilot findings remain separate and unchanged: exact passes were 1/15 self-review, 7/15 structure-feedback and 4/15 guarded critic. They must not be pooled with the later artifact endpoints.

Independent adjudication, held-out generalization, exact base-weight revision and substantial methodological novelty remain unestablished. Runtime enforcement and provenance-aware auditing already exist; this work does not claim to originate those principles. The supplied artifacts are now inspected and computationally replayed, but they are not yet a public runtime release. No selective retries, normalization rescoring or runtime changes were made.

## Provenance
Run: integrated_v0_4_20261027T040459122453Z. Evidence: complete saved-output and source/request text exports, not summaries alone. The new inspection supersedes earlier uninspected-source statements while retaining their historical audit records. This is a manuscript insert; a consolidated Word development draft is supplied separately. No new bibliography entries are introduced here.
