#!/usr/bin/env bash
# Direct-revision comparator for the core and NHANES-label contexts: one revision request per input and seed,
# with no review, in two formats (full proposal and JSON patch). Settings match the 2,048-token run: revision limit
# 512 tokens, temperature 0.2, revision seeds 1042 (core) and 1042, 1043 (labels), server-default thinking mode.
# The script never starts or stops a model server. Run it against the same server configuration as the reference run.
#
# Required:  P6_MODEL      model identifier served by the endpoint (p6-qwen3-8b for the reference run)
#            P6_BASE_URL   endpoint, e.g. http://127.0.0.1:8010/v1
# Optional:  OPENAI_API_KEY   bearer token if the endpoint requires one (never printed)
#            P6_OUT           output root (default: outputs/direct_revision under the current directory)
#            P6_WORKERS       concurrent requests (default 8)
#            P6_CONFIRM=yes   skip the interactive confirmation (needed for nohup)
set -uo pipefail
: "${P6_MODEL:?set P6_MODEL}"; : "${P6_BASE_URL:?set P6_BASE_URL}"
HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO="$(cd "$HERE/../.." && pwd)"
WORKERS="${P6_WORKERS:-8}"
TS="$(date -u +%Y%m%dT%H%M%SZ)"
OUT="${P6_OUT:-$PWD/outputs/direct_revision}/$TS"
mkdir -p "$OUT"

( cd "$HERE" && python p6_direct_revision.py check > "$OUT/offline_check.json" ) || { echo "offline check failed; nothing was run"; exit 1; }
AUTH=(); [ -n "${OPENAI_API_KEY:-}" ] && AUTH=(-H "Authorization: Bearer $OPENAI_API_KEY")
curl -sS --noproxy '*' -m 15 ${AUTH[@]+"${AUTH[@]}"} "$P6_BASE_URL/models" \
  | python -c "import sys,json; d=json.load(sys.stdin)['data']; ids=[x['id'] for x in d]; print('served:',ids,'max_model_len:',[x.get('max_model_len') for x in d]); sys.exit(0 if '$P6_MODEL' in ids else 3)" \
  || { echo "model $P6_MODEL is not served at $P6_BASE_URL, or the endpoint rejected the request (is OPENAI_API_KEY set?)"; exit 2; }

declare -A HASH; TOTAL=0
for set in core24 nhanes; do
  if [ "$set" = "nhanes" ]; then SEEDS="42,43"; else SEEDS="42"; fi
  J="$( cd "$HERE" && python p6_direct_revision.py prepare --output-dir "$OUT/plans/$set" --context-set "$set" --seeds "$SEEDS" --model "$P6_MODEL" --base-url "$P6_BASE_URL" --workers "$WORKERS" )" || { echo "prepare failed for $set"; exit 1; }
  HASH[$set]="$(echo "$J" | python -c "import sys,json; print(json.load(sys.stdin)['plan_sha256'])")"
  C="$(echo "$J" | python -c "import sys,json; print(json.load(sys.stdin)['max_generation_calls'])")"; TOTAL=$((TOTAL+C))
  echo "$set seeds=$SEEDS max_calls=$C plan=${HASH[$set]:0:16}"
done
echo "total maximum generation requests: $TOTAL"
if [ "${P6_CONFIRM:-ask}" != "yes" ]; then
  read -r -p "Type RUN to start: " ANS
  [ "$ANS" = "RUN" ] || { echo "stopped before any generation; plans are in $OUT/plans"; exit 0; }
fi
for set in core24 nhanes; do
  echo "run $set $(date -u +%H:%M:%S)"
  ( cd "$HERE" && python p6_direct_revision.py run --plan-dir "$OUT/plans/$set" --output-dir "$OUT/runs/$set" --approve-plan-hash "${HASH[$set]}" ) 2>&1 | tee "$OUT/run_$set.log" | tail -n 3
  ( cd "$HERE" && python analyze_direct_revision.py --plan-dir "$OUT/plans/$set" --run-dir "$OUT/runs/$set" --out-dir "$OUT/analysis/$set" --reference "$REPO/results/review_limit_2048/$set/outcomes.csv" ) > "$OUT/analysis_$set.txt" 2>&1 \
    && echo "analyzed $set" || echo "analysis failed for $set; see $OUT/analysis_$set.txt"
done
echo "outputs: $OUT"
