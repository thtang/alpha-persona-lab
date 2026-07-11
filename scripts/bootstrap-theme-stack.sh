#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
PYTHON="${PYTHON:-python3}"
FRESH=false
DISCOVER=false
BACKTEST=false
REBUILD_GRAPH=false
FULL=false
AGENT_MODE="auto"
AGENT_PROVIDER="auto"
AGENT_WORKERS=2
AGENT_BATCH_SIZE=24
SEMANTIC_BACKEND="auto"
EMBEDDING_ENDPOINT=""
EMBEDDING_MODEL=""
DISCOVER_MAX_SYMBOLS=0
MAX_DISCOVERED=800
PRICE_SYMBOL_LIMIT=""

usage() {
  cat <<'EOF'
Rebuild the ThemeMiner + Lagradar research stack after clone or git pull.

Usage:
  scripts/bootstrap-theme-stack.sh [options]

Options:
  --fresh                    Refresh prices/news/history where supported
  --rebuild-graph            Recompute ThemeMiner graph from seed/profile data
  --full                     Full graph rebuild; include every discovered stock
  --discover                 Re-scan broad US/TW/TPEX universes before graph build
  --discover-max-symbols N   Cap mapped discovery symbols; 0 means no cap
  --max-discovered N         Cap discovered symbols in graph; 0 means no cap
  --price-symbol-limit N     Cap graph price refresh symbols; 0 means no cap
  --agent-mode MODE          auto, on, or off. Default: auto
  --agent-provider PROVIDER  auto, openai, or codex. Default: auto
  --agent-workers N          Parallel semantic judges. Default: 2
  --agent-batch-size N       Companies/stocks per agent call. Default: 24
  --semantic-backend MODE    auto, lexical, mlx, mlx-local, or mlx-http. Default: auto
  --embedding-endpoint URL   OpenAI-compatible /v1/embeddings endpoint
  --embedding-model MODEL    Embedding model name sent to the endpoint
  --backtest                 Fetch/build 20-year lead-lag backtest outputs
  --help                     Show this help text

Default mode is intentionally light: it rebuilds HTML and laggard outputs from
committed graph/profile snapshots. Use --rebuild-graph when you want to
recompute ThemeMiner, --fresh for live market/news refresh, --discover for a
broad universe scan, --full for uncapped graph size, and --backtest for
historical research artifacts.
EOF
}

while [[ $# -gt 0 ]]; do
  case "$1" in
    --fresh)
      FRESH=true
      REBUILD_GRAPH=true
      shift
      ;;
    --rebuild-graph)
      REBUILD_GRAPH=true
      shift
      ;;
    --full)
      FULL=true
      REBUILD_GRAPH=true
      shift
      ;;
    --discover)
      DISCOVER=true
      REBUILD_GRAPH=true
      shift
      ;;
    --discover-max-symbols)
      DISCOVER_MAX_SYMBOLS="$2"
      shift 2
      ;;
    --max-discovered)
      MAX_DISCOVERED="$2"
      shift 2
      ;;
    --price-symbol-limit)
      PRICE_SYMBOL_LIMIT="$2"
      shift 2
      ;;
    --agent-mode)
      AGENT_MODE="$2"
      shift 2
      ;;
    --agent-provider)
      AGENT_PROVIDER="$2"
      shift 2
      ;;
    --agent-workers)
      AGENT_WORKERS="$2"
      shift 2
      ;;
    --agent-batch-size)
      AGENT_BATCH_SIZE="$2"
      shift 2
      ;;
    --semantic-backend)
      SEMANTIC_BACKEND="$2"
      shift 2
      ;;
    --embedding-endpoint)
      EMBEDDING_ENDPOINT="$2"
      shift 2
      ;;
    --embedding-model)
      EMBEDDING_MODEL="$2"
      shift 2
      ;;
    --backtest)
      BACKTEST=true
      shift
      ;;
    --help|-h)
      usage
      exit 0
      ;;
    *)
      echo "Unknown argument: $1" >&2
      usage >&2
      exit 2
      ;;
  esac
done

cd "$ROOT_DIR"

if [[ "$FULL" == true ]]; then
  MAX_DISCOVERED=0
  DISCOVER_MAX_SYMBOLS=0
  if [[ -z "$PRICE_SYMBOL_LIMIT" ]]; then
    PRICE_SYMBOL_LIMIT=0
  fi
fi

run() {
  echo
  printf '>>>'
  printf ' %q' "$@"
  echo
  "$@"
}

if [[ "$DISCOVER" == true ]]; then
  run "$PYTHON" thememiner/scripts/discover_market_universe.py \
    --markets US,TW,TWO \
    --max-symbols "$DISCOVER_MAX_SYMBOLS" \
    --agent-mode "$AGENT_MODE" \
    --agent-provider "$AGENT_PROVIDER" \
    --agent-workers "$AGENT_WORKERS" \
    --agent-batch-size "$AGENT_BATCH_SIZE"
fi

if [[ "$REBUILD_GRAPH" == true || ! -f thememiner/output/cross_market_stock_graph.json ]]; then
  GRAPH_ARGS=("$PYTHON" thememiner/scripts/update_theme_graph.py --max-discovered "$MAX_DISCOVERED")
  if [[ "$FRESH" == true ]]; then
    GRAPH_ARGS+=(--refresh-prices --refresh-news)
  fi
  if [[ -n "$PRICE_SYMBOL_LIMIT" ]]; then
    GRAPH_ARGS+=(--price-symbol-limit "$PRICE_SYMBOL_LIMIT")
  fi
  if [[ -f thememiner/data/company_profiles_official_autofill.json ]]; then
    GRAPH_ARGS+=(--auto-profiles thememiner/data/company_profiles_official_autofill.json)
  elif [[ -f thememiner/data/company_profiles_autofill.json ]]; then
    GRAPH_ARGS+=(--auto-profiles thememiner/data/company_profiles_autofill.json)
  fi
  run "${GRAPH_ARGS[@]}"

  run "$PYTHON" thememiner/scripts/build_company_thesis_cards.py \
    --agent-mode "$AGENT_MODE" \
    --agent-provider "$AGENT_PROVIDER" \
    --agent-workers "$AGENT_WORKERS" \
    --agent-batch-size "$AGENT_BATCH_SIZE"
else
  echo "Using committed ThemeMiner graph snapshot. Add --rebuild-graph to recompute."
fi

SEMANTIC_ARGS=("$PYTHON" thememiner/scripts/build_semantic_relation_index.py --backend "$SEMANTIC_BACKEND")
if [[ -n "$EMBEDDING_ENDPOINT" ]]; then
  SEMANTIC_ARGS+=(--embedding-endpoint "$EMBEDDING_ENDPOINT")
fi
if [[ -n "$EMBEDDING_MODEL" ]]; then
  SEMANTIC_ARGS+=(--embedding-model "$EMBEDDING_MODEL")
fi
run "${SEMANTIC_ARGS[@]}"

run "$PYTHON" thememiner/scripts/build_theme_graph_html.py

LAGRADAR_ARGS=("$PYTHON" lagradar/scripts/scan_laggards.py)
if [[ "$FRESH" == true ]]; then
  LAGRADAR_ARGS+=(--refresh-history)
fi
run "${LAGRADAR_ARGS[@]}"

run "$PYTHON" lagradar/scripts/build_lagradar_html.py

if [[ "$BACKTEST" == true ]]; then
  FETCH_ARGS=("$PYTHON" lagradar/scripts/fetch_backtest_history.py --years 20)
  if [[ "$FRESH" == true ]]; then
    FETCH_ARGS+=(--refresh)
  fi
  run "${FETCH_ARGS[@]}"
  run "$PYTHON" lagradar/scripts/backtest_theme_diffusion.py
fi

echo
echo "ThemeMiner HTML: $ROOT_DIR/thememiner/output/theme_graph.html"
echo "Lagradar HTML:   $ROOT_DIR/lagradar/output/lagradar_theme_graph.html"
echo "Bootstrap complete."
