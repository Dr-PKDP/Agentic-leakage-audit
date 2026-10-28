#!/usr/bin/env bash
# Reruns the core and NHANES-label contexts with a longer review limit (default 2,048 tokens) and a
# revision limit of 512 tokens, against a running OpenAI-compatible server. The script never starts or
# stops a model server. The review prompt, the review text in the revision prompt and the output must fit
# in the context window of the server; with a 4,096-token window the review limit cannot exceed about 2,000.
#
# Required:  P6_MODEL      model identifier served by the endpoint
#            P6_BASE_URL   endpoint, e.g. http://127.0.0.1:8000/v1
# Optional:  OPENAI_API_KEY             bearer token if the endpoint requires one (never printed)
#            P6_OUT                     output root (default: outputs/longlimit under the current directory)
#            P6_ARMS                    arms to run (default "core24 nhanes")
#            P6_REVIEW_MAX_TOKENS       default 2048
#            P6_REVISION_MAX_TOKENS     default 512
#            P6_PROMPT_VARIANT          original (default) or clarified (explicit statement of the response form)
#            P6_WORKERS                 concurrent requests (default 8)
#            P6_CONFIRM=yes             skip the interactive confirmation
# Seeds: 42 for core24, 42 and 43 for nhanes. Thinking mode: server default.
set -uo pipefail
: "${P6_MODEL:?set P6_MODEL}"; : "${P6_BASE_URL:?set P6_BASE_URL}"
HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
export PYTHONPATH="$HERE/../principal_v0_4${PYTHONPATH:+:$PYTHONPATH}"
REV="${P6_REVIEW_MAX_TOKENS:-2048}"; RVS="${P6_REVISION_MAX_TOKENS:-512}"
ARMS="${P6_ARMS:-core24 nhanes}"; WORKERS="${P6_WORKERS:-8}"; VARIANT="${P6_PROMPT_VARIANT:-original}"
TS="$(date -u +%Y%m%dT%H%M%SZ)"
OUT="${P6_OUT:-$PWD/outputs/longlimit}/$TS"
mkdir -p "$OUT"

( cd "$HERE" && python p6_extended_v0_5.py check > "$OUT/offline_check.json" ) || { echo "offline check failed; nothing was run"; exit 1; }
AUTH=(); [ -n "${OPENAI_API_KEY:-}" ] && AUTH=(-H "Authorization: Bearer $OPENAI_API_KEY")
curl -sS --noproxy '*' -m 15 ${AUTH[@]+"${AUTH[@]}"} "$P6_BASE_URL/models" \
  | python -c "import sys,json; d=json.load(sys.stdin)['data']; ids=[x['id'] for x in d]; print('served:',ids,'max_model_len:',[x.get('max_model_len') for x in d]); sys.exit(0 if '$P6_MODEL' in ids else 3)" \
  || { echo "model $P6_MODEL is not served at $P6_BASE_URL, or the endpoint rejected the request (is OPENAI_API_KEY set?)"; exit 2; }

declare -A HASH; TOTAL=0
for set in $ARMS; do
  if [ "$set" = "nhanes" ]; then SEEDS="42,43"; else SEEDS="42"; fi
  J="$( cd "$HERE" && python p6_extended_v0_5.py prepare --output-dir "$OUT/plans/$set" --arm "${set}_review${REV}_${VARIANT}" --context-set "$set" --thinking default --seeds "$SEEDS" --model "$P6_MODEL" --base-url "$P6_BASE_URL" --workers "$WORKERS" --review-max-tokens "$REV" --revision-max-tokens "$RVS" --prompt-variant "$VARIANT" )" || { echo "prepare failed for $set"; exit 1; }
  HASH[$set]="$(echo "$J" | python -c "import sys,json; print(json.load(sys.stdin)['plan_sha256'])")"
  C="$(echo "$J" | python -c "import sys,json; print(json.load(sys.stdin)['max_generation_calls'])")"; TOTAL=$((TOTAL+C))
  echo "$set seeds=$SEEDS max_calls=$C plan=${HASH[$set]:0:16}"
done
echo "total maximum generation requests: $TOTAL (review limit $REV, revision limit $RVS, prompt variant $VARIANT)"
if [ "${P6_CONFIRM:-ask}" != "yes" ]; then
  read -r -p "Type RUN to start: " ANS
  [ "$ANS" = "RUN" ] || { echo "stopped before any generation; plans are in $OUT/plans"; exit 0; }
fi
for set in $ARMS; do
  echo "run $set $(date -u +%H:%M:%S)"
  ( cd "$HERE" && python p6_extended_v0_5.py run --plan-dir "$OUT/plans/$set" --output-dir "$OUT/runs/$set" --approve-plan-hash "${HASH[$set]}" ) 2>&1 | tee "$OUT/run_$set.log" | tail -n 3
  ( cd "$HERE" && python p6_extended_analyze.py --plan-dir "$OUT/plans/$set" --run-dir "$OUT/runs/$set" --out-dir "$OUT/analysis/$set" ) > "$OUT/analysis_$set.txt" 2>&1 \
    && echo "analyzed $set" || echo "analysis failed for $set; see $OUT/analysis_$set.txt"
done
echo "outputs: $OUT"
