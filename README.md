# P6 Stage 2

Windows 10 / Python 3.11: resumable NHANES development-data acquisition, checksum logs, XPT schema extraction, harmonization table creation, and leakage-validator tests.

Run: `./run_stage2_windows.ps1`

## Source-verified development results - 27 October 2026

The synthetic run completed 192 units from 24 contexts and 48 inputs using 384 requests. Complete output and source/request exports have now been inspected. Approved hashes, prompts and payloads reconcile; offline replay reproduces all 192 unit records and 48 reference assessments. This is computational replay, not independent scientific validation.

- [Manuscript insert](docs/manuscript/development_evaluation_v0_4.md)
- [Structured summary](results/agent_development_v0_4_summary.json)
- [Original outcome table](results/agent_development_v0_4_outcomes.csv)
- [Earlier targeted failure audit](results/agent_development_v0_4_failure_audit.json)
- [Source/request replay provenance](results/agent_development_v0_4_replay.json)
- [Verified resource totals](results/agent_development_v0_4_resources.csv)

Both patch paths repaired 20/21 known errors; one harmful timing edit was prevented by evidence checking. Original scores are unchanged. New limitations: 93/192 reviews hit the output limit; structural findings were empty on every initial input; 40/48 identical review requests returned different text; the evidence critic twice returned empty feature sets counted as supported. Contract support is not task utility or safety.

Total usage was 543571 tokens and 3828.13 summed client-request seconds, not GPU time or full wall time. No participant records or generated-code execution were involved. Earlier unfavorable findings remain unchanged. Held-out evidence, independent adjudication and substantial novelty remain unestablished. This commit publishes derived documentation, not private prompts/responses, raw logs or a complete runtime release. No new generation, rescoring or runtime changes are included.
