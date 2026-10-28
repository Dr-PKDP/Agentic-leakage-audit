#!/usr/bin/env bash
# Prepares, confirms, runs and analyzes the three-arm extended experiment against a running
# OpenAI-compatible server. The script never starts or stops a model server.
#
# Required:  P6_MODEL      model identifier served by the endpoint
#            P6_BASE_URL   endpoint, e.g. http://127.0.0.1:8000/v1
# Optional:  OPENAI_API_KEY    bearer token if the endpoint requires one (never printed)
#            P6_OUT            output root (default: outputs/label_contexts under the current directory)
#            P6_WORKERS        concurrent requests (default 8)
#            P6_ORIGINAL_RUNS  space-separated run directories to scan for reasoning output
#            P6_CONFIRM=yes    skip the interactive confirmation
#            P6_MODEL2, P6_BASE_URL2  add the think-off arms for a second served model
set -uo pipefail
: "${P6_MODEL:?set P6_MODEL}"; : "${P6_BASE_URL:?set P6_BASE_URL}"
HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
export PYTHONPATH="$HERE/../core_contexts${PYTHONPATH:+:$PYTHONPATH}"
WORKERS="${P6_WORKERS:-8}"
TS="$(date -u +%Y%m%dT%H%M%SZ)"
OUT="${P6_OUT:-$PWD/outputs/label_contexts}/$TS"
mkdir -p "$OUT/plans" "$OUT/runs" "$OUT/analysis"

{ echo "== date"; date -u; echo "== host"; hostname; echo "== python"; python --version 2>&1
  echo "== gpus"; nvidia-smi --query-gpu=name,memory.used,memory.total --format=csv 2>&1 || echo "nvidia-smi unavailable"
} > "$OUT/env_report.txt"

( cd "$HERE" && python p6_extended_v0_5.py check > "$OUT/offline_check.json" ) || { echo "offline check failed; nothing was run"; exit 1; }
echo "offline check: pass"

AUTH=(); [ -n "${OPENAI_API_KEY:-}" ] && AUTH=(-H "Authorization: Bearer $OPENAI_API_KEY")
MJ="$(curl -sS --noproxy '*' -m 15 ${AUTH[@]+"${AUTH[@]}"} "$P6_BASE_URL/models" 2>&1)"
echo "$MJ" | python -c "import sys,json; ids=[x['id'] for x in json.load(sys.stdin)['data']]; print('served models:', ids); sys.exit(0 if '$P6_MODEL' in ids else 3)" \
  || { echo "model $P6_MODEL is not served at $P6_BASE_URL, or the endpoint rejected the request (is OPENAI_API_KEY set?)"; exit 2; }

if [ -n "${P6_ORIGINAL_RUNS:-}" ]; then
  # shellcheck disable=SC2086
  python "$HERE/p6_scan_requests.py" $P6_ORIGINAL_RUNS | tee "$OUT/original_run_scan.jsonl"
fi

declare -a ARMS=("nhanes_default nhanes default 42,43 $P6_MODEL $P6_BASE_URL"
                 "core24_think_off core24 off 42 $P6_MODEL $P6_BASE_URL"
                 "nhanes_think_off nhanes off 42,43 $P6_MODEL $P6_BASE_URL")
if [ -n "${P6_MODEL2:-}" ] && [ -n "${P6_BASE_URL2:-}" ]; then
  ARMS+=("core24_think_off_model2 core24 off 42 $P6_MODEL2 $P6_BASE_URL2"
         "nhanes_think_off_model2 nhanes off 42,43 $P6_MODEL2 $P6_BASE_URL2")
fi
declare -A HASH; TOTAL=0
for spec in "${ARMS[@]}"; do
  read -r arm set think seeds model base <<< "$spec"
  J="$( cd "$HERE" && python p6_extended_v0_5.py prepare --output-dir "$OUT/plans/$arm" --arm "$arm" --context-set "$set" --thinking "$think" --seeds "$seeds" --model "$model" --base-url "$base" --workers "$WORKERS" )" || { echo "prepare failed for $arm"; exit 1; }
  HASH[$arm]="$(echo "$J" | python -c "import sys,json; print(json.load(sys.stdin)['plan_sha256'])")"
  CALLS="$(echo "$J" | python -c "import sys,json; print(json.load(sys.stdin)['max_generation_calls'])")"
  TOTAL=$((TOTAL+CALLS))
  printf '%-26s set=%-7s thinking=%-7s seeds=%-6s model=%s  max_calls=%s  plan=%s\n' "$arm" "$set" "$think" "$seeds" "$model" "$CALLS" "${HASH[$arm]:0:16}"
done
echo "total maximum generation requests: $TOTAL"
if [ "${P6_CONFIRM:-ask}" != "yes" ]; then
  read -r -p "Type RUN to start all arms: " ANS
  [ "$ANS" = "RUN" ] || { echo "stopped before any generation; plans are in $OUT/plans"; exit 0; }
fi

for spec in "${ARMS[@]}"; do
  read -r arm set think seeds model base <<< "$spec"
  echo "=== run $arm $(date -u +%H:%M:%S)"
  ( cd "$HERE" && python p6_extended_v0_5.py run --plan-dir "$OUT/plans/$arm" --output-dir "$OUT/runs/$arm" --approve-plan-hash "${HASH[$arm]}" ) 2>&1 | tee "$OUT/runs_$arm.log" | tail -n 3
  ( cd "$HERE" && python p6_extended_analyze.py --plan-dir "$OUT/plans/$arm" --run-dir "$OUT/runs/$arm" --out-dir "$OUT/analysis/$arm" > "$OUT/analysis_$arm.txt" 2>&1 ) && echo "analyzed $arm" || echo "analysis failed for $arm (see $OUT/analysis_$arm.txt)"
done

RET="$OUT/summary_$TS"; mkdir -p "$RET"
cp "$OUT/env_report.txt" "$OUT/offline_check.json" "$OUT/original_run_scan.jsonl" "$RET"/ 2>/dev/null
for d in "$OUT"/analysis/*/; do n="$(basename "$d")"; mkdir -p "$RET/$n"; cp "$d/summary.json" "$d/outcomes.csv" "$RET/$n"/; cp "$OUT/runs/$n/run_report.json" "$RET/$n"/ 2>/dev/null; done
( cd "$OUT" && tar czf "summary_$TS.tar.gz" "summary_$TS" )
echo "done: $OUT"
