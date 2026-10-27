# Synthetic development evaluation: manuscript insert

## Methods
We evaluated 24 authored synthetic contexts in six constraint families using 48 initial proposals: 24 supported, 21 contradicted and three unresolved. Four generation streams used p6-qwen3-8b with review seed 42, revision seed 1042, temperature 0.2 and a 1024-token output ceiling. Each input-stream combination used two requests, giving 192 workflow units and 384 requests. The same generated patch was processed by interface-only and evidence-guarded acceptance; these were paired paths, not independent generations. No participant data or generated-code execution was involved.

An artifact evaluator assessed scoped evidence without consuming guard acceptance. Guard and evaluator were separate authored implementations sharing contract semantics, not independent scientific adjudication. All input denominators retained unsuccessful units. These development-exposed contexts were not a held-out test set, and context independence was not established.

A targeted offline audit examined the saved revisions for two unparseable outputs, two schema failures and one rejected stale-contract patch. It inspected response content, termination reasons and token usage. Parsing after removal of a single enclosing Markdown fence was diagnostic only; original scores and artifacts were not changed.

## Results
| Path | Repairs / 21 | Supported retained / 24 | Observed harmful changes | Supported outputs / 48 |
|---|---:|---:|---:|---:|
| Self-review | 16 | 24 | 0 | 42 |
| Structure feedback | 17 | 23 | 1 | 42 |
| Evidence critic | 16 | 23 | 1 | 41 |
| Patch: interface-only | 20 | 22 | 1 | 45 |
| Patch: evidence-guarded | 20 | 23 | 0 | 46 |

Two outputs were unparseable under the strict parser: one self-review input initially contradicted and one patch input initially supported. The latter affected both patch paths. Structure feedback and the evidence critic each produced one schema failure. Initially unresolved inputs became supported in two of three cases under each non-patch stream and all three under both patch paths; conservative withholding can satisfy these contracts without recovering missing evidence.

Matched inspection confirmed a harmful edit in F02/latest_dependency. A patch added a derived feature whose dependency became ready at time 12, beyond cutoff 10. Interface-only acceptance applied the edit; evidence-guarded acceptance rejected it and retained the supported input. In F05/stale_binding, both paths rejected a patch and retained a contradicted permission request. Execution authorization stayed false.

### Targeted failure audit
All five audited revisions ended with finish_reason=stop; completion lengths ranged from 9 to 288 tokens, below the 1024-token ceiling. The two strict parsing failures contained valid JSON enclosed in Markdown fences. Fence-only diagnostic parsing succeeded in both cases, but no artifact was rescored. The two schema failures were valid JSON with empty population_domain or requested_action strings, violating nonempty-field requirements rather than establishing substantive evidence uncertainty.

The stale-contract patch proposed changing fit to none, consistent with the approval mismatch, but addressed proposal.requested_action instead of the permitted top-level requested_action field. Its single operation established an unknown-field failure, not a duplicate-field failure. The model expressed an evidence-consistent intended correction that neither acceptance path could apply through the declared interface. The original unsuccessful-repair outcome remains unchanged.

## Discussion
Evidence checking prevented one harmful edit without reducing the 20 observed repairs, yielding one additional supported output out of 48. It did not cause the patch stream's higher repair count: both acceptance paths repaired the same inputs. Self-review also produced no observed harmful change. The guarded path had zero observed harmful edits among 23 evaluated supported inputs, with one further input unevaluated. Rejection retaining an incorrect input was unsuccessful repair, not safety success.

The audit distinguished response-format, schema and patch-addressing failures from scientific decision errors. It motivates prospectively specifying fence handling, nonempty decision values and permitted patch fields. Diagnostic parsing does not establish full contract validity. Any normalization analysis or interface revision must be reported separately rather than replacing strict-format outcomes.

Results are descriptive development evidence, not general superiority, clinical safety or population inference. The 192 units came from 24 contexts, not 192 independent contexts. Prior pilot findings remain unchanged and must not be pooled across different endpoints. The five-case targeted failure audit is complete on the supplied extracts; it is not an exhaustive audit of every output. No retrospective retries, score changes or additional generations were included.

## Provenance
Run: integrated_v0_4_20261027T040459122453Z. Evidence consists of user-supplied terminal summaries, two matched fallback records and five targeted revision extracts. The assistant has not downloaded or independently verified the raw archive. This is a manuscript insert, not a replacement full manuscript. A matching Word insert is delivered separately. No new bibliography entries are introduced.
