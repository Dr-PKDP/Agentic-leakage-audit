# P6 Stage 2

Windows 10 / Python 3.11: resumable NHANES development-data acquisition, checksum logs, XPT schema extraction, harmonization table creation, and leakage-validator tests.

Run: `./run_stage2_windows.ps1`

## Development results — 27 October 2026

The synthetic development run completed 192 workflow units from 24 authored contexts and 48 inputs using 384 generation requests. Two outputs were unparseable. Both patch-acceptance paths repaired 20 of 21 contradicted inputs. Matched inspection confirmed that evidence checking prevented one harmful timing edit; a separate structural rejection retained an incorrect permission request in both paths.

- [Manuscript insert](docs/manuscript/development_evaluation_v0_4.md)
- [Structured summary](results/agent_development_v0_4_summary.json)
- [Outcome table](results/agent_development_v0_4_outcomes.csv)

These are user-reported development results, not held-out evaluation or independent scientific validation. Earlier pilot findings remain unchanged. The raw archive has not been independently inspected or uploaded; this documentation update is not a complete runtime release. No participant data or generated-code execution was involved in this run. Remaining offline audits and limitations are recorded in the manuscript insert. Do not retry or overwrite the completed run retrospectively.
