$ErrorActionPreference = "Stop"
$Root = Split-Path -Parent $MyInvocation.MyCommand.Path
Set-Location $Root
$Py = ".venv\Scripts\python.exe"
if (-not (Test-Path $Py)) { throw "Missing .venv. Create it with: py -3.11 -m venv .venv" }
& $Py -m pip install -r requirements.txt
New-Item -ItemType Directory -Force -Path "data\raw\development","data\metadata","results","logs" | Out-Null
& $Py src\acquire_nhanes.py --manifest protocol\nhanes_input_manifest_v2.csv --split development --output data\raw\development --log logs\acquisition.jsonl --inventory results\development_acquisition_inventory_v2.csv
& $Py src\extract_schema.py --inventory results\development_acquisition_inventory_v2.csv --raw-dir data\raw\development --output data\metadata\development_schema_v2.csv --report results\development_schema_report_v2.csv
& $Py src\build_harmonization.py --schema data\metadata\development_schema_v2.csv --output data\metadata\cross_cycle_harmonization_v2.csv
& $Py -m pytest -q
