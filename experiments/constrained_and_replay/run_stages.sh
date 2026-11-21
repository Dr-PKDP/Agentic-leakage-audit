#!/usr/bin/env bash
# Stages of the constrained-decoding, review-replay, gate-operating-characteristic and execution experiments.
# Usage: bash run_stages.sh STAGE [args]
#   check                      offline checks and endpoint listing; no generation
#   gate                       gate operating characteristics (offline, no model calls)
#   replay                     saved-review replay on the Qwen3-8B endpoint (needs P6_SRC)
#   constrained q|g            JSON-schema constrained revision for the Qwen3-8B (q) or Granite (g) endpoint
#   model TAG MODEL BASE_URL   one further model served under MODEL at BASE_URL: clarified and constrained arms
#   execute                    NHANES 2015-2016 execution check: fetch, build, reference AUCs, scoring of every NHANES-label run under P6_RUNS_ROOT
# Uses running OpenAI-compatible endpoints; never starts or restarts a model server.
#
# Environment: P6_QWEN_URL (default http://127.0.0.1:8010/v1), P6_QWEN (p6-qwen3-8b), P6_GRANITE_URL (http://127.0.0.1:8011/v1),
#   P6_GRANITE (p6-granite-8b), OPENAI_API_KEY (bearer token, never printed), P6_OUT (default ./outputs/stages), P6_WORKERS (8),
#   P6_CONFIRM=yes (skip the interactive confirmation), P6_SRC (replay source), P6_STREAMS (comma-separated subset of streams),
#   P6_NHANES_DIR (default ./data/nhanes_2015_2016), P6_RUNS_ROOT (default ./outputs, searched for NHANES-label runs).
set -uo pipefail
STAGE="${1:-}"; shift || true
QURL="${P6_QWEN_URL:-http://127.0.0.1:8010/v1}"; QMOD="${P6_QWEN:-p6-qwen3-8b}"
GURL="${P6_GRANITE_URL:-http://127.0.0.1:8011/v1}"; GMOD="${P6_GRANITE:-p6-granite-8b}"
WORKERS="${P6_WORKERS:-8}"
HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
export PYTHONPATH="$HERE/../core_contexts${PYTHONPATH:+:$PYTHONPATH}"
TS="$(date -u +%Y%m%dT%H%M%SZ)"
OUT="${P6_OUT:-$PWD/outputs/stages}/${STAGE}_$TS"
[ -n "$STAGE" ] || { sed -n 2,9p "$0"; exit 1; }

if [ -z "${OPENAI_API_KEY:-}" ]; then
  K="$(ps -u "$(id -un)" -o args= 2>/dev/null | grep -i vllm | grep -- '--api-key' | grep -v grep | head -1 | sed -E 's/.*--api-key[ =]([^ ]+).*/\1/')"
  [ -n "$K" ] && export OPENAI_API_KEY="$K"; unset K
fi
AUTH=(); [ -n "${OPENAI_API_KEY:-}" ] && AUTH=(-H "Authorization: Bearer $OPENAI_API_KEY")

served() {  # URL MODEL
  curl -sS --noproxy '*' -m 15 ${AUTH[@]+"${AUTH[@]}"} "$1/models" | python -c "import sys,json; d=json.load(sys.stdin)['data']; ids=[x['id'] for x in d]; print('  $1 serves',ids,'max_model_len',[x.get('max_model_len') for x in d]); sys.exit(0 if '$2' in ids else 3)"
}
busy() { pgrep -u "$(id -un)" -f "p6_(v06|extended_v0_5)\.py run" >/dev/null && { echo "A P6 run is still active. Wait for it to finish."; exit 3; }; }

declare -a A_NAME A_SET A_SEEDS A_MODEL A_URL A_EXTRA
add() { A_NAME+=("$1"); A_SET+=("$2"); A_SEEDS+=("$3"); A_MODEL+=("$4"); A_URL+=("$5"); A_EXTRA+=("$6"); }
seeds_for() { [ "$1" = "nhanes" ] && echo "42,43" || echo "42"; }

run_arms() {
  mkdir -p "$OUT"; ( cd "$HERE" && python p6_v06.py check > "$OUT/offline_check.json" ) || { echo "Offline check failed."; exit 1; }
  declare -A HASH; local TOTAL=0 i J C
  for i in "${!A_NAME[@]}"; do
    J="$( cd "$HERE" && python p6_v06.py prepare --output-dir "$OUT/plans/${A_NAME[$i]}" --arm "${A_NAME[$i]}" --context-set "${A_SET[$i]}" --seeds "${A_SEEDS[$i]}" --model "${A_MODEL[$i]}" --base-url "${A_URL[$i]}" --workers "$WORKERS" ${A_EXTRA[$i]} )" || { echo "prepare failed for ${A_NAME[$i]}"; exit 1; }
    HASH[${A_NAME[$i]}]="$(echo "$J" | python -c "import sys,json; print(json.load(sys.stdin)['plan_sha256'])")"
    C="$(echo "$J" | python -c "import sys,json; print(json.load(sys.stdin)['max_generation_calls'])")"; TOTAL=$((TOTAL+C))
    printf '%-28s set=%-7s model=%-16s max_calls=%-5s plan=%s\n' "${A_NAME[$i]}" "${A_SET[$i]}" "${A_MODEL[$i]}" "$C" "${HASH[${A_NAME[$i]}]:0:16}"
  done
  echo "TOTAL at most $TOTAL generation requests (synthetic contexts only, no participant data, no execution of model code, no server restart)."
  if [ "${P6_CONFIRM:-ask}" != "yes" ]; then read -r -p "Type RUN to start all arms, anything else to stop: " ANS; [ "$ANS" = "RUN" ] || { echo "Stopped before any generation. Plans are in $OUT/plans"; exit 0; }; fi
  for i in "${!A_NAME[@]}"; do
    n="${A_NAME[$i]}"; echo "=== RUN $n $(date -u +%H:%M:%S)"
    ( cd "$HERE" && python p6_v06.py run --plan-dir "$OUT/plans/$n" --output-dir "$OUT/runs/$n" --approve-plan-hash "${HASH[$n]}" ) 2>&1 | tee "$OUT/run_$n.log" | tail -n 2
    ( cd "$HERE" && python p6_extended_analyze.py --plan-dir "$OUT/plans/$n" --run-dir "$OUT/runs/$n" --out-dir "$OUT/analysis/$n" > "$OUT/analysis_$n.txt" 2>&1 ) && echo "analyzed $n" || echo "analysis failed for $n (see $OUT/analysis_$n.txt)"
  done
  package
}

package() {
  local RET="$OUT/P6_${STAGE}_return_$TS"; mkdir -p "$RET"; cp "$OUT/offline_check.json" "$RET"/ 2>/dev/null
  for d in "$OUT"/analysis/*/; do [ -d "$d" ] || continue; n="$(basename "$d")"; mkdir -p "$RET/$n"; cp "$d/summary.json" "$d/outcomes.csv" "$RET/$n"/; cp "$OUT/runs/$n/run_report.json" "$OUT/plans/$n/plan.json" "$RET/$n"/ 2>/dev/null; done
  [ -d "$OUT/execution" ] && cp -r "$OUT/execution" "$RET"/
  ( cd "$OUT" && tar czf "P6_${STAGE}_return_$TS.tar.gz" "P6_${STAGE}_return_$TS" && base64 -w 76 "P6_${STAGE}_return_$TS.tar.gz" > "P6_${STAGE}_return_$TS.b64.txt" )
  echo; echo "DONE. Results directory: $OUT"
  echo "Return package: $OUT/P6_${STAGE}_return_$TS.tar.gz  ($(du -h "$OUT/P6_${STAGE}_return_$TS.tar.gz" | cut -f1))"
}

case "$STAGE" in
check)
  ( cd "$HERE" && python p6_v06.py check && python p6_extended_v0_5.py check | python -c "import sys,json; d=json.load(sys.stdin); print('extended runner offline check', d['status'])" )
  served "$QURL" "$QMOD"; served "$GURL" "$GMOD"
  python - <<'PY'
import importlib
for m in ("pandas", "sklearn", "pyreadstat", "numpy"):
    try: print(m, importlib.import_module(m).__version__)
    except Exception as e: print(m, "not importable in this environment:", type(e).__name__)
PY
  ;;
gate)
  mkdir -p "$OUT"; ( cd "$HERE" && python p6_v06_gate_battery.py --out-dir "$OUT/gate_battery" ) | tee "$OUT/console.txt"; echo "Results: $OUT/gate_battery" ;;
replay)
  busy; served "$QURL" "$QMOD" || exit 2
  SRC="${P6_SRC:?set P6_SRC to a longer-limit run directory that holds plans/SET/jobs.json and runs/SET/requests.jsonl for core24 and nhanes}"
  for s in core24 nhanes; do
    [ -f "$SRC/plans/$s/jobs.json" ] && [ -f "$SRC/runs/$s/requests.jsonl" ] || { echo "P6_SRC is missing plans/$s/jobs.json or runs/$s/requests.jsonl"; exit 4; }
  done
  for s in core24 nhanes; do
    sd="$(seeds_for $s)"
    add "q_replay_full_$s"   "$s" "$sd" "$QMOD" "$QURL" "--replay-source $SRC --truncate-review-tokens 0 --revision-max-tokens 512"
    add "q_replay_t1024_$s"  "$s" "$sd" "$QMOD" "$QURL" "--replay-source $SRC --truncate-review-tokens 1024 --revision-max-tokens 512"
  done
  run_arms ;;
constrained)
  W="${1:?usage: run_stages.sh constrained q|g}"; busy
  if [ "$W" = q ]; then served "$QURL" "$QMOD" || exit 2; else served "$GURL" "$GMOD" || exit 2; fi
  STREAMS="${P6_STREAMS:-self_review,structure_feedback,evidence_critic}"
  for s in core24 nhanes; do
    sd="$(seeds_for $s)"
    [ "$W" = q ] && add "q_con_$s" "$s" "$sd" "$QMOD" "$QURL" "--constrained --prompt-variant clarified --review-max-tokens 2048 --revision-max-tokens 512 --streams $STREAMS"
    [ "$W" = g ] && add "g_con_$s" "$s" "$sd" "$GMOD" "$GURL" "--constrained --prompt-variant clarified --review-max-tokens 2048 --revision-max-tokens 512 --streams $STREAMS"
  done
  run_arms ;;
model)
  TAG="${1:?tag}"; MOD="${2:?served model name}"; URL="${3:?base url}"
  busy; served "$URL" "$MOD" || exit 2
  STREAMS="${P6_STREAMS:-self_review,structure_feedback,evidence_critic}"
  for s in core24 nhanes; do
    sd="$(seeds_for $s)"
    add "${TAG}_clar_$s" "$s" "$sd" "$MOD" "$URL" "--prompt-variant clarified --review-max-tokens 2048 --revision-max-tokens 512"
    add "${TAG}_con_$s"  "$s" "$sd" "$MOD" "$URL" "--constrained --prompt-variant clarified --review-max-tokens 2048 --revision-max-tokens 512 --streams $STREAMS"
  done
  run_arms ;;
execute)
  DATA="${P6_NHANES_DIR:-$PWD/data/nhanes_2015_2016}"; ROOT="${P6_RUNS_ROOT:-$PWD/outputs}"; mkdir -p "$OUT/execution"
  python -c "import pandas, sklearn, pyreadstat" 2>/dev/null || { echo "pandas, scikit-learn and pyreadstat are required (pip install pandas scikit-learn pyreadstat)."; exit 5; }
  cd "$HERE"
  python p6_v06_exec.py fetch "$DATA" || { echo "Download failed. Place the ten *_I.xpt files listed in p6_v06_exec.py (FILES) in $DATA and rerun."; exit 6; }
  python p6_v06_exec.py build "$DATA" | tee "$OUT/execution/build.txt"
  python p6_v06_exec.py reference "$DATA" "$OUT/execution" | tee "$OUT/execution/reference.txt"
  PAIRS=( $(python - "$ROOT" <<'PY'
import json, sys
from pathlib import Path
root = Path(sys.argv[1])
for plan in sorted(root.glob("**/plans/*/plan.json")):
    try: p = json.loads(plan.read_text())
    except Exception: continue
    run = plan.parent.parent.parent / "runs" / plan.parent.name
    if p.get("context_set") == "nhanes" and str(p.get("version", "")).startswith(("p6_extended", "p6_v06")) and list(run.glob("*__*.json")):
        print(f"{plan.parent}:{run}")
PY
) )
  echo "NHANES-label runs found: ${#PAIRS[@]}"; printf '  %s\n' "${PAIRS[@]}"
  [ "${#PAIRS[@]}" -gt 0 ] && python p6_v06_exec.py score "$DATA" "$OUT/execution" "${PAIRS[@]}" > "$OUT/execution/score_console.txt" && tail -n 40 "$OUT/execution/score_console.txt"
  package ;;
*) echo "Unknown stage: $STAGE"; exit 1 ;;
esac
