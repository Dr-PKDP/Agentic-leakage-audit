# P6: Population-Valid Agentic Clinical Prediction

Stage 1 reproducibility scaffold for the NHANES clinical-agent benchmark. Raw NHANES files are deliberately not included.

## Setup

```bash
python -m pip install -r requirements.txt
python src/acquire_manifest.py --manifest protocol/nhanes_input_manifest_v1.csv --split development --output data/raw/development
pytest -q
```
