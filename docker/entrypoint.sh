#!/bin/sh
set -eu

echo "▶ Running CS log pipeline…"

python src/blastlog/parse_faceit.py \
  && echo "✅ parse_faceit OK" \
  && python src/blastlog/parse_match_start_end_roster_accolade.py \
  && echo "✅ parse_match_start_end_roster_accolade OK" \
  && python src/blastlog/parse_round_events.py \
  && echo "✅ parse_round_events OK" \
  && python src/blastlog/extend_round_events.py \
  && echo "✅ extend_round_events OK" \
  || { echo "❌ FAILED (exit $?)"; exit 1; }

echo "▶ Starting API…"
exec python -m uvicorn src.fastapi.app.main:app --host 0.0.0.0 --port 8000