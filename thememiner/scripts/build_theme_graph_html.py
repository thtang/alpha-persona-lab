#!/usr/bin/env python3
"""Build a self-contained ThemeMiner graph HTML report."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any


def read_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def to_script_json(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, separators=(",", ":")).replace("</", "<\\/")


def build_html(payload: dict[str, Any]) -> str:
    data = to_script_json(payload)
    return f"""<!doctype html>
<html lang="zh-Hant">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>ThemeMiner Cross-Market Graph</title>
  <style>
    :root {{
      color-scheme: light;
      --bg: #f6f7f9;
      --panel: #ffffff;
      --ink: #172033;
      --muted: #687386;
      --line: #d8dde6;
      --soft: #eef2f6;
      --blue: #2563eb;
      --red: #dc2626;
      --green: #059669;
      --amber: #d97706;
      --purple: #7c3aed;
      --cyan: #0891b2;
      --shadow: 0 10px 30px rgba(23, 32, 51, .08);
    }}

    * {{ box-sizing: border-box; }}

    body {{
      margin: 0;
      min-height: 100vh;
      background: var(--bg);
      color: var(--ink);
      font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", "Noto Sans TC", "PingFang TC", Arial, sans-serif;
      letter-spacing: 0;
    }}

    button, input, select {{
      font: inherit;
    }}

    .app {{
      display: grid;
      grid-template-rows: auto auto 1fr;
      min-height: 100vh;
    }}

    header {{
      background: var(--panel);
      border-bottom: 1px solid var(--line);
      padding: 18px 22px 14px;
    }}

    .header-row {{
      display: flex;
      align-items: flex-end;
      justify-content: space-between;
      gap: 16px;
      flex-wrap: wrap;
    }}

    h1 {{
      margin: 0;
      font-size: 24px;
      line-height: 1.15;
      font-weight: 750;
    }}

    .subtitle {{
      margin-top: 6px;
      color: var(--muted);
      font-size: 13px;
    }}

    .stats {{
      display: flex;
      gap: 8px;
      flex-wrap: wrap;
      justify-content: flex-end;
    }}

    .stat {{
      min-width: 98px;
      padding: 8px 10px;
      border: 1px solid var(--line);
      border-radius: 6px;
      background: #fbfcfe;
    }}

    .stat b {{
      display: block;
      font-size: 17px;
      line-height: 1.15;
    }}

    .stat span {{
      display: block;
      color: var(--muted);
      font-size: 11px;
      margin-top: 2px;
    }}

    .toolbar {{
      display: grid;
      grid-template-columns: minmax(190px, .9fr) minmax(240px, 1.1fr) minmax(220px, 1fr) repeat(3, minmax(110px, 150px));
      gap: 10px;
      padding: 12px 22px;
      background: #fbfcfe;
      border-bottom: 1px solid var(--line);
    }}

    .control {{
      min-width: 0;
    }}

    .control label {{
      display: block;
      color: var(--muted);
      font-size: 11px;
      margin-bottom: 4px;
    }}

    input, select {{
      width: 100%;
      height: 38px;
      border: 1px solid var(--line);
      border-radius: 6px;
      background: #fff;
      color: var(--ink);
      padding: 0 10px;
      outline: none;
    }}

    input:focus, select:focus {{
      border-color: var(--blue);
      box-shadow: 0 0 0 3px rgba(37, 99, 235, .12);
    }}

    .suggest-control {{
      position: relative;
    }}

    .suggestions {{
      position: absolute;
      z-index: 20;
      top: calc(100% + 5px);
      left: 0;
      right: 0;
      display: none;
      max-height: 310px;
      overflow: auto;
      border: 1px solid var(--line);
      border-radius: 7px;
      background: var(--panel);
      box-shadow: var(--shadow);
    }}

    .suggestions.open {{
      display: block;
    }}

    .suggestion {{
      width: 100%;
      min-height: 44px;
      display: grid;
      grid-template-columns: 64px 1fr auto;
      align-items: center;
      gap: 8px;
      border: 0;
      border-bottom: 1px solid #edf0f5;
      border-radius: 0;
      background: #fff;
      padding: 8px 10px;
      text-align: left;
      cursor: pointer;
    }}

    .suggestion:last-child {{
      border-bottom: 0;
    }}

    .suggestion:hover, .suggestion.active {{
      background: #f4f7fb;
    }}

    .suggestion-symbol {{
      font-weight: 740;
      font-variant-numeric: tabular-nums;
    }}

    .suggestion-name {{
      min-width: 0;
      overflow: hidden;
      text-overflow: ellipsis;
      white-space: nowrap;
    }}

    .suggestion-market {{
      color: var(--muted);
      font-size: 11px;
    }}

    main {{
      display: grid;
      grid-template-columns: 350px minmax(0, 1fr);
      gap: 14px;
      padding: 14px 22px 22px;
      min-height: 0;
    }}

    aside, .workspace {{
      min-height: 0;
    }}

    .theme-list {{
      display: flex;
      flex-direction: column;
      gap: 8px;
      max-height: calc(100vh - 160px);
      overflow: auto;
      padding-right: 4px;
    }}

    .theme-card {{
      width: 100%;
      text-align: left;
      border: 1px solid var(--line);
      border-radius: 7px;
      background: var(--panel);
      padding: 11px 12px;
      cursor: pointer;
    }}

    .theme-card:hover {{
      border-color: #aeb7c5;
      box-shadow: var(--shadow);
    }}

    .theme-card.active {{
      border-color: var(--blue);
      box-shadow: 0 0 0 3px rgba(37, 99, 235, .12);
    }}

    .theme-topline {{
      display: flex;
      align-items: center;
      justify-content: space-between;
      gap: 8px;
    }}

    .theme-name {{
      font-size: 16px;
      font-weight: 720;
      line-height: 1.25;
    }}

    .score {{
      font-variant-numeric: tabular-nums;
      font-weight: 720;
      color: var(--blue);
    }}

    .meta {{
      margin-top: 7px;
      display: flex;
      gap: 6px;
      flex-wrap: wrap;
      color: var(--muted);
      font-size: 12px;
    }}

    .pill {{
      display: inline-flex;
      align-items: center;
      height: 22px;
      padding: 0 7px;
      border: 1px solid var(--line);
      border-radius: 999px;
      background: #fbfcfe;
      white-space: nowrap;
      max-width: 100%;
    }}

    .stage-active_cross_market {{ border-color: rgba(5, 150, 105, .35); color: var(--green); }}
    .stage-price_active {{ border-color: rgba(37, 99, 235, .35); color: var(--blue); }}
    .stage-news_active {{ border-color: rgba(217, 119, 6, .35); color: var(--amber); }}

    .workspace {{
      display: grid;
      grid-template-rows: minmax(420px, 58vh) auto;
      gap: 14px;
    }}

    .graph-panel, .detail-panel {{
      border: 1px solid var(--line);
      border-radius: 8px;
      background: var(--panel);
      box-shadow: var(--shadow);
      overflow: hidden;
    }}

    .panel-head {{
      display: flex;
      justify-content: space-between;
      align-items: center;
      gap: 12px;
      padding: 12px 14px;
      border-bottom: 1px solid var(--line);
      background: #fbfcfe;
    }}

    .panel-head h2 {{
      margin: 0;
      font-size: 16px;
      line-height: 1.2;
    }}

    .legend {{
      display: flex;
      gap: 7px;
      flex-wrap: wrap;
      justify-content: flex-end;
    }}

    .legend span {{
      display: inline-flex;
      align-items: center;
      gap: 5px;
      font-size: 11px;
      color: var(--muted);
    }}

    .dot {{
      width: 9px;
      height: 9px;
      border-radius: 50%;
      background: var(--muted);
      display: inline-block;
    }}

    .graph-wrap {{
      height: calc(100% - 50px);
      min-height: 360px;
      position: relative;
    }}

    svg {{
      display: block;
      width: 100%;
      height: 100%;
    }}

    .edge {{
      fill: none;
      stroke: #a7b0bf;
      stroke-width: 1.1;
      opacity: .5;
    }}

    .edge.peer {{
      stroke: #c4cbd6;
      stroke-dasharray: 4 4;
      opacity: .35;
    }}

    .edge.correlation {{
      stroke: #d97706;
      opacity: .62;
    }}

    .node circle {{
      stroke: #fff;
      stroke-width: 2;
      filter: drop-shadow(0 2px 5px rgba(23,32,51,.18));
    }}

    .node.selected circle {{
      stroke: #111827;
      stroke-width: 4;
    }}

    .node text {{
      font-size: 12px;
      fill: var(--ink);
      paint-order: stroke;
      stroke: rgba(255,255,255,.86);
      stroke-width: 4px;
      stroke-linejoin: round;
      pointer-events: auto;
      user-select: none;
    }}

    .node {{
      cursor: grab;
      touch-action: none;
    }}

    .node.dragging {{
      cursor: grabbing;
    }}

    .node.concept text {{
      font-size: 15px;
      font-weight: 760;
    }}

    .detail-panel {{
      padding: 14px;
    }}

    .detail-grid {{
      display: grid;
      grid-template-columns: minmax(260px, .9fr) minmax(360px, 1.3fr);
      gap: 14px;
    }}

    .summary {{
      border: 1px solid var(--line);
      border-radius: 7px;
      padding: 12px;
      background: #fbfcfe;
    }}

    .summary h3 {{
      margin: 0 0 8px;
      font-size: 18px;
    }}

    .kv {{
      display: grid;
      grid-template-columns: 92px 1fr;
      gap: 7px;
      font-size: 13px;
      padding: 4px 0;
      border-bottom: 1px solid #edf0f5;
    }}

    .kv:last-child {{
      border-bottom: 0;
    }}

    .kv span:first-child {{
      color: var(--muted);
    }}

    .headline-list {{
      margin: 10px 0 0;
      padding: 0;
      list-style: none;
      display: grid;
      gap: 8px;
    }}

    .headline-list a {{
      color: var(--ink);
      text-decoration: none;
      line-height: 1.35;
    }}

    .headline-list a:hover {{
      color: var(--blue);
      text-decoration: underline;
    }}

    .table-wrap {{
      overflow: auto;
      border: 1px solid var(--line);
      border-radius: 7px;
      background: #fff;
    }}

    table {{
      width: 100%;
      border-collapse: collapse;
      font-size: 13px;
      min-width: 1180px;
    }}

    th, td {{
      padding: 8px 9px;
      border-bottom: 1px solid #edf0f5;
      text-align: left;
      white-space: nowrap;
    }}

    th {{
      color: var(--muted);
      font-size: 11px;
      font-weight: 680;
      background: #fbfcfe;
      position: sticky;
      top: 0;
      z-index: 1;
    }}

    td.num {{
      text-align: right;
      font-variant-numeric: tabular-nums;
    }}

    tr.selected-stock {{
      background: #fff7ed;
    }}

    tr.selected-stock td {{
      border-bottom-color: #fed7aa;
    }}

    .pos {{ color: var(--green); }}
    .neg {{ color: var(--red); }}

    .empty {{
      padding: 30px;
      text-align: center;
      color: var(--muted);
    }}

    @media (max-width: 1100px) {{
      .toolbar {{
        grid-template-columns: 1fr 1fr;
      }}

      main {{
        grid-template-columns: 1fr;
      }}

      .theme-list {{
        max-height: 280px;
      }}

      .detail-grid {{
        grid-template-columns: 1fr;
      }}
    }}

    @media (max-width: 680px) {{
      header, .toolbar, main {{
        padding-left: 12px;
        padding-right: 12px;
      }}

      .toolbar {{
        grid-template-columns: 1fr;
      }}

      .workspace {{
        grid-template-rows: 480px auto;
      }}
    }}
  </style>
</head>
<body>
  <div class="app">
    <header>
      <div class="header-row">
        <div>
          <h1>ThemeMiner Cross-Market Graph</h1>
          <div class="subtitle" id="subtitle">Loading...</div>
        </div>
        <div class="stats" id="stats"></div>
      </div>
    </header>

    <section class="toolbar" aria-label="Filters">
      <div class="control">
        <label for="search">Search</label>
        <input id="search" type="search" placeholder="題材 / concept id / category">
      </div>
      <div class="control suggest-control">
        <label for="stockSearch">Stock</label>
        <input id="stockSearch" type="search" autocomplete="off" placeholder="Ticker / 名稱，例如 8046 / 南電 / FORM">
        <div class="suggestions" id="stockSuggestions" role="listbox" aria-label="Stock suggestions"></div>
      </div>
      <div class="control">
        <label for="themeSelect">Theme</label>
        <select id="themeSelect"></select>
      </div>
      <div class="control">
        <label for="market">Market</label>
        <select id="market"></select>
      </div>
      <div class="control">
        <label for="stage">Stage</label>
        <select id="stage"></select>
      </div>
      <div class="control">
        <label for="topN">List Size</label>
        <select id="topN">
          <option value="15">Top 15</option>
          <option value="30" selected>Top 30</option>
          <option value="60">Top 60</option>
          <option value="999">All</option>
        </select>
      </div>
    </section>

    <main>
      <aside>
        <div class="theme-list" id="themeList"></div>
      </aside>

      <section class="workspace">
        <div class="graph-panel">
          <div class="panel-head">
            <h2 id="graphTitle">Theme Graph</h2>
            <div class="legend" id="legend"></div>
          </div>
          <div class="graph-wrap">
            <svg id="graphSvg" role="img" aria-label="Cross-market concept stock relation graph"></svg>
          </div>
        </div>

        <div class="detail-panel">
          <div class="detail-grid">
            <div class="summary" id="summary"></div>
            <div>
              <div class="table-wrap">
                <table>
                  <thead>
                    <tr>
                      <th>Market</th>
                      <th>Symbol</th>
                      <th>Name</th>
                      <th>Products</th>
                      <th>Supply Chain</th>
                      <th>Bottleneck</th>
                      <th>Corr</th>
                      <th>Path</th>
                      <th>R5</th>
                      <th>R20</th>
                      <th>Near 20D High</th>
                      <th>Business</th>
                    </tr>
                  </thead>
                  <tbody id="stockRows"></tbody>
                </table>
              </div>
            </div>
          </div>
        </div>
      </section>
    </main>
  </div>

  <script>
    const DATA = {data};

    const MARKET_COLORS = {{
      US: "#2563eb",
      TW: "#dc2626",
      JP: "#7c3aed",
      CN: "#059669",
      HK: "#d97706",
      KR: "#0891b2",
      OTHER: "#687386"
    }};
    const MARKET_ORDER = ["US", "JP", "KR", "TW", "CN", "HK", "OTHER"];

    const graph = DATA.graph || {{nodes: [], edges: []}};
    const library = DATA.library || {{themes: []}};
    const manifest = DATA.manifest || {{}};
    const themes = (library.themes || []).slice().sort((a, b) => (b.score || 0) - (a.score || 0));
    const nodeById = new Map((graph.nodes || []).map(node => [node.id, node]));
    const conceptEdges = (graph.edges || []).filter(edge => edge.type === "concept_stock");
    const peerEdges = (graph.edges || []).filter(edge => edge.type === "same_concept_cross_market");
    const correlationEdges = (graph.edges || []).filter(edge => edge.type === "price_correlation");
    const stockNodes = (graph.nodes || []).filter(node => node.type === "stock").sort((a, b) => String(a.symbol || "").localeCompare(String(b.symbol || "")));
    const stockConceptIds = new Map();
    for (const edge of conceptEdges) {{
      const conceptId = String(edge.source || "").replace("concept:", "");
      if (!stockConceptIds.has(edge.target)) stockConceptIds.set(edge.target, []);
      stockConceptIds.get(edge.target).push(conceptId);
    }}
    const customPositions = new Map();
    const dragState = {{active: null, offsetX: 0, offsetY: 0, pointerId: null, group: null}};

    const state = {{
      search: "",
      stockSearch: "",
      focusStockId: "",
      market: "ALL",
      stage: "ALL",
      topN: 30,
      selected: themes[0]?.concept_id || ""
    }};

    const $ = selector => document.querySelector(selector);
    const svgNS = "http://www.w3.org/2000/svg";

    function fmt(value, digits = 1, suffix = "") {{
      if (value === null || value === undefined || Number.isNaN(Number(value))) return "-";
      return `${{Number(value).toFixed(digits)}}${{suffix}}`;
    }}

    function esc(value) {{
      return String(value ?? "").replace(/[&<>"']/g, ch => ({{
        "&": "&amp;",
        "<": "&lt;",
        ">": "&gt;",
        '"': "&quot;",
        "'": "&#39;"
      }}[ch]));
    }}

    function cssIdent(value) {{
      return String(value || "").replace(/[^a-zA-Z0-9_-]/g, "_");
    }}

    function marketColor(market) {{
      return MARKET_COLORS[market] || MARKET_COLORS.OTHER;
    }}

    function signedClass(value) {{
      const num = Number(value || 0);
      return num >= 0 ? "pos" : "neg";
    }}

    function positionKey(themeId, nodeId) {{
      return `${{themeId}}::${{nodeId}}`;
    }}

    function applySavedPosition(themeId, node) {{
      const saved = customPositions.get(positionKey(themeId, node.id));
      if (!saved) return node;
      node.x = saved.x;
      node.y = saved.y;
      return node;
    }}

    function clampNode(node, width, height) {{
      const radius = node.radius || 12;
      node.x = Math.max(radius + 12, Math.min(width - 120, node.x));
      node.y = Math.max(radius + 12, Math.min(height - radius - 12, node.y));
      return node;
    }}

    function svgPoint(svg, event) {{
      const point = svg.createSVGPoint();
      point.x = event.clientX;
      point.y = event.clientY;
      const matrix = svg.getScreenCTM();
      return matrix ? point.matrixTransform(matrix.inverse()) : {{x: event.offsetX, y: event.offsetY}};
    }}

    function themeMatches(theme) {{
      const key = state.search.trim().toLowerCase();
      if (key) {{
        const text = [theme.label, theme.concept_id, theme.category_label, theme.stage]
          .join(" ")
          .toLowerCase();
        if (!text.includes(key)) return false;
      }}
      if (state.market !== "ALL" && !(theme.markets || []).includes(state.market)) return false;
      if (state.stage !== "ALL" && theme.stage !== state.stage) return false;
      return true;
    }}

    function filteredThemes() {{
      return themes.filter(themeMatches).slice(0, state.topN);
    }}

    function selectedTheme() {{
      return themes.find(theme => theme.concept_id === state.selected) || filteredThemes()[0] || themes[0];
    }}

    function stockSearchText(stock) {{
      return [
        stock.symbol,
        stock.name,
        stock.market,
        stock.sector,
        ...(stock.specializations || []),
        ...(stock.products || [])
      ].join(" ").toLowerCase();
    }}

    function scoreStockSuggestion(stock, key) {{
      if (!key) {{
        const isCurrentTheme = stockConceptIds.get(stock.id)?.includes(state.selected);
        return (isCurrentTheme ? 1000 : 0) + Math.max(0, Number(stock.r20 || 0));
      }}
      const symbol = String(stock.symbol || "").toLowerCase();
      const name = String(stock.name || "").toLowerCase();
      const text = stockSearchText(stock);
      if (symbol === key) return 1000;
      if (symbol.startsWith(key)) return 900;
      if (name.startsWith(key)) return 820;
      if (symbol.includes(key)) return 760;
      if (name.includes(key)) return 720;
      if (text.includes(key)) return 560;
      return -1;
    }}

    function stockSuggestions() {{
      const key = state.stockSearch.trim().toLowerCase();
      return stockNodes
        .map(stock => ({{stock, score: scoreStockSuggestion(stock, key)}}))
        .filter(item => item.score >= 0)
        .sort((a, b) => b.score - a.score || String(a.stock.symbol || "").localeCompare(String(b.stock.symbol || "")))
        .slice(0, 14)
        .map(item => item.stock);
    }}

    function closeStockSuggestions() {{
      $("#stockSuggestions").classList.remove("open");
    }}

    function renderStockSuggestions(open = false) {{
      const root = $("#stockSuggestions");
      const rows = stockSuggestions();
      if (!rows.length) {{
        root.innerHTML = `<div class="empty">No matching stocks</div>`;
      }} else {{
        root.innerHTML = rows.map(stock => `
          <button class="suggestion" type="button" data-stock-id="${{esc(stock.id)}}">
            <span class="suggestion-symbol">${{esc(stock.symbol || stock.id.replace("stock:", ""))}}</span>
            <span class="suggestion-name">${{esc(stock.name || "-")}}</span>
            <span class="suggestion-market">${{esc(stock.market || "-")}}</span>
          </button>
        `).join("");
        root.querySelectorAll(".suggestion").forEach(button => {{
          button.addEventListener("mousedown", event => event.preventDefault());
          button.addEventListener("click", () => {{
            const stock = nodeById.get(button.dataset.stockId);
            if (stock) chooseStock(stock);
          }});
        }});
      }}
      root.classList.toggle("open", open);
    }}

    function chooseStock(stock) {{
      state.focusStockId = stock.id;
      state.stockSearch = `${{stock.symbol || ""}} ${{stock.name || ""}}`.trim();
      const concepts = (stockConceptIds.get(stock.id) || [])
        .map(conceptId => themes.find(theme => theme.concept_id === conceptId))
        .filter(Boolean)
        .sort((a, b) => (b.score || 0) - (a.score || 0));
      if (concepts.length) {{
        state.selected = concepts[0].concept_id;
        state.search = "";
        $("#search").value = "";
      }}
      $("#stockSearch").value = state.stockSearch;
      closeStockSuggestions();
      renderControls();
      render();
    }}

    function stockNodesFor(conceptId) {{
      const bestCorr = bestCorrelationByStock(conceptId);
      const rows = conceptEdges
        .filter(edge => edge.source === `concept:${{conceptId}}`)
        .map(edge => {{
          const node = nodeById.get(edge.target) || {{}};
          return {{
            ...node,
            edgeWeight: edge.weight || 0,
            edgeRole: edge.role || node.role || "",
            bestCorrelation: bestCorr.get(edge.target),
            relationPath: edge.relation_path || "",
            edgeMarket: edge.market || node.market || "OTHER"
          }};
        }});
      return rows.sort((a, b) => {{
        if (a.id === state.focusStockId) return -1;
        if (b.id === state.focusStockId) return 1;
        const ma = MARKET_ORDER.indexOf(a.market || "OTHER");
        const mb = MARKET_ORDER.indexOf(b.market || "OTHER");
        if (ma !== mb) return ma - mb;
        return (b.r20 || 0) - (a.r20 || 0);
      }});
    }}

    function bestCorrelationByStock(conceptId) {{
      const best = new Map();
      for (const edge of correlationEdges.filter(item => item.concept_id === conceptId)) {{
        for (const id of [edge.source, edge.target]) {{
          const other = id === edge.source ? edge.target : edge.source;
          const current = best.get(id);
          if (!current || Math.abs(edge.correlation || 0) > Math.abs(current.correlation || 0)) {{
            best.set(id, {{
              other,
              otherSymbol: (nodeById.get(other) || {{}}).symbol || other.replace("stock:", ""),
              correlation: edge.correlation,
              lag_days: edge.lag_days,
              lag_direction: edge.lag_direction,
              sample_size: edge.sample_size
            }});
          }}
        }}
      }}
      return best;
    }}

    function renderStats() {{
      $("#subtitle").textContent = `Built at ${{library.built_at || graph.built_at || manifest.built_at || "-"}}`;
      const stats = [
        ["Themes", manifest.concept_count ?? themes.length],
        ["Stocks", manifest.watchlist_symbol_count ?? graph.nodes.filter(n => n.type === "stock").length],
        ["Nodes", manifest.graph_node_count ?? graph.nodes.length],
        ["Edges", manifest.graph_edge_count ?? graph.edges.length],
        ["Corr", manifest.correlation_edge_count ?? correlationEdges.length],
        ["Supply", manifest.supply_chain_edge_count ?? graph.edges.filter(edge => edge.type === "upstream_concept_stock" || edge.type === "stock_downstream_concept").length]
      ];
      $("#stats").innerHTML = stats.map(([label, value]) => `<div class="stat"><b>${{value}}</b><span>${{label}}</span></div>`).join("");
    }}

    function renderControls() {{
      const groups = new Map();
      for (const theme of themes) {{
        const label = theme.category_label || "Other";
        if (!groups.has(label)) groups.set(label, []);
        groups.get(label).push(theme);
      }}
      const themeSelect = $("#themeSelect");
      themeSelect.innerHTML = "";
      for (const [category, rows] of groups.entries()) {{
        const group = document.createElement("optgroup");
        group.label = category;
        for (const theme of rows) {{
          const option = document.createElement("option");
          option.value = theme.concept_id;
          option.textContent = `${{theme.label}} · ${{theme.concept_id}} · ${{fmt(theme.score, 1)}}`;
          group.appendChild(option);
        }}
        themeSelect.appendChild(group);
      }}
      themeSelect.value = state.selected;

      const markets = Array.from(new Set(themes.flatMap(theme => theme.markets || []))).sort();
      $("#market").innerHTML = [`<option value="ALL">All markets</option>`, ...markets.map(m => `<option value="${{m}}">${{m}}</option>`)].join("");
      const stages = Array.from(new Set(themes.map(theme => theme.stage).filter(Boolean))).sort();
      $("#stage").innerHTML = [`<option value="ALL">All stages</option>`, ...stages.map(s => `<option value="${{s}}">${{s}}</option>`)].join("");
      $("#market").value = state.market;
      $("#stage").value = state.stage;
      $("#topN").value = String(state.topN);
      $("#stockSearch").value = state.stockSearch;
    }}

    function renderThemeList() {{
      const list = filteredThemes();
      const root = $("#themeList");
      if (!list.length) {{
        root.innerHTML = `<div class="empty">No matching themes</div>`;
        return;
      }}
      root.innerHTML = "";
      for (const theme of list) {{
        const button = document.createElement("button");
        button.className = `theme-card ${{theme.concept_id === state.selected ? "active" : ""}}`;
        button.type = "button";
        button.dataset.conceptId = theme.concept_id;
        button.innerHTML = `
          <div class="theme-topline">
            <div class="theme-name"></div>
            <div class="score">${{fmt(theme.score, 1)}}</div>
          </div>
          <div class="meta">
            <span class="pill">${{theme.category_label || "-"}}</span>
            <span class="pill stage-${{cssIdent(theme.stage)}}">${{theme.stage || "-"}}</span>
            <span class="pill">${{(theme.markets || []).join(",") || "-"}}</span>
            <span class="pill">R5 ${{fmt(theme.r5_median, 1, "%")}}</span>
            <span class="pill">R20 ${{fmt(theme.r20_median, 1, "%")}}</span>
          </div>
        `;
        button.querySelector(".theme-name").textContent = theme.label || theme.concept_id;
        button.addEventListener("click", () => {{
          state.selected = theme.concept_id;
          render();
        }});
        root.appendChild(button);
      }}
    }}

    function renderLegend(stocks) {{
      const markets = Array.from(new Set(stocks.map(stock => stock.market || "OTHER"))).sort((a, b) => MARKET_ORDER.indexOf(a) - MARKET_ORDER.indexOf(b));
      $("#legend").innerHTML = markets.map(m => `<span><i class="dot" style="background:${{marketColor(m)}}"></i>${{m}}</span>`).join("");
    }}

    function makeSVG(name, attrs = {{}}, text = "") {{
      const element = document.createElementNS(svgNS, name);
      for (const [key, value] of Object.entries(attrs)) element.setAttribute(key, value);
      if (text) element.textContent = text;
      return element;
    }}

    function renderGraph() {{
      const theme = selectedTheme();
      if (!theme) return;
      const stocks = stockNodesFor(theme.concept_id);
      renderLegend(stocks);
      $("#graphTitle").textContent = `${{theme.label}} relation graph`;
      const svg = $("#graphSvg");
      svg.innerHTML = "";
      dragState.active = null;
      dragState.group = null;
      dragState.pointerId = null;
      const box = svg.getBoundingClientRect();
      const width = Math.max(760, box.width || 900);
      const height = Math.max(420, box.height || 520);
      svg.setAttribute("viewBox", `0 0 ${{width}} ${{height}}`);

      const concept = {{
        id: `concept:${{theme.concept_id}}`,
        label: theme.label,
        x: Math.max(150, width * 0.28),
        y: height * 0.5,
        radius: 30 + Math.min(22, (theme.score || 0) / 5)
      }};
      applySavedPosition(theme.concept_id, concept);
      clampNode(concept, width, height);

      const markets = Array.from(new Set(stocks.map(stock => stock.market || "OTHER"))).sort((a, b) => MARKET_ORDER.indexOf(a) - MARKET_ORDER.indexOf(b));
      const colStart = width * 0.52;
      const colGap = markets.length > 1 ? (width * 0.42) / (markets.length - 1) : 0;
      const stockLayout = new Map();
      markets.forEach((market, marketIndex) => {{
        const group = stocks.filter(stock => (stock.market || "OTHER") === market);
        const x = markets.length === 1 ? width * 0.72 : colStart + marketIndex * colGap;
        const laneTop = 72;
        const laneBottom = height - 56;
        const gap = group.length > 1 ? (laneBottom - laneTop) / (group.length - 1) : 0;
        group.forEach((stock, index) => {{
          const positioned = {{
            ...stock,
            x,
            y: group.length === 1 ? height * 0.5 : laneTop + index * gap,
            radius: 9 + Math.min(10, Math.max(0, Math.abs(stock.r20 || 0)) / 8)
          }};
          applySavedPosition(theme.concept_id, positioned);
          clampNode(positioned, width, height);
          stockLayout.set(stock.id, positioned);
        }});
      }});

      const defs = makeSVG("defs");
      const arrow = makeSVG("marker", {{
        id: "arrow",
        markerWidth: 8,
        markerHeight: 8,
        refX: 7,
        refY: 3,
        orient: "auto",
        markerUnits: "strokeWidth"
      }});
      arrow.appendChild(makeSVG("path", {{d: "M0,0 L0,6 L7,3 z", fill: "#a7b0bf"}}));
      defs.appendChild(arrow);
      svg.appendChild(defs);

      const selectedIds = new Set([concept.id, ...Array.from(stockLayout.keys())]);
      const relationRefs = [];
      const peerRefs = [];
      const correlationRefs = [];
      const groupByNodeId = new Map();

      function relationPath(stock) {{
        const midX = (concept.x + stock.x) / 2;
        return `M ${{concept.x + concept.radius}} ${{concept.y}} C ${{midX}} ${{concept.y}}, ${{midX}} ${{stock.y}}, ${{stock.x - stock.radius}} ${{stock.y}}`;
      }}

      function peerPath(a, b) {{
        return `M ${{a.x}} ${{a.y}} C ${{(a.x + b.x) / 2}} ${{a.y - 28}}, ${{(a.x + b.x) / 2}} ${{b.y + 28}}, ${{b.x}} ${{b.y}}`;
      }}

      function updatePositions() {{
        for (const item of relationRefs) {{
          item.path.setAttribute("d", relationPath(item.stock));
        }}
        for (const item of peerRefs) {{
          item.path.setAttribute("d", peerPath(item.a, item.b));
        }}
        for (const item of correlationRefs) {{
          item.path.setAttribute("d", peerPath(item.a, item.b));
        }}
        const conceptGroup = groupByNodeId.get(concept.id);
        if (conceptGroup) conceptGroup.setAttribute("transform", `translate(${{concept.x}} ${{concept.y}})`);
        for (const stock of stockLayout.values()) {{
          const group = groupByNodeId.get(stock.id);
          if (group) group.setAttribute("transform", `translate(${{stock.x}} ${{stock.y}})`);
        }}
      }}

      function startDrag(group, node, event) {{
        event.preventDefault();
        const point = svgPoint(svg, event);
        dragState.active = node;
        dragState.offsetX = point.x - node.x;
        dragState.offsetY = point.y - node.y;
        dragState.pointerId = event.pointerId;
        dragState.group = group;
        group.classList.add("dragging");
        svg.setPointerCapture?.(event.pointerId);
      }}

      function stopDrag() {{
        if (dragState.group) dragState.group.classList.remove("dragging");
        dragState.active = null;
        dragState.group = null;
        dragState.pointerId = null;
      }}

      svg.onpointermove = event => {{
        if (!dragState.active) return;
        const point = svgPoint(svg, event);
        dragState.active.x = point.x - dragState.offsetX;
        dragState.active.y = point.y - dragState.offsetY;
        clampNode(dragState.active, width, height);
        customPositions.set(positionKey(theme.concept_id, dragState.active.id), {{
          x: dragState.active.x,
          y: dragState.active.y
        }});
        updatePositions();
      }};
      svg.onpointerup = stopDrag;
      svg.onpointercancel = stopDrag;
      svg.onpointerleave = event => {{
        if (dragState.active && dragState.pointerId === event.pointerId) stopDrag();
      }};

      for (const edge of peerEdges.filter(edge => edge.concept_id === theme.concept_id && selectedIds.has(edge.source) && selectedIds.has(edge.target)).slice(0, 80)) {{
        const a = stockLayout.get(edge.source);
        const b = stockLayout.get(edge.target);
        if (!a || !b) continue;
        const path = makeSVG("path", {{
          class: "edge peer",
          d: peerPath(a, b)
        }});
        peerRefs.push({{path, a, b}});
        svg.appendChild(path);
      }}

      for (const edge of correlationEdges.filter(edge => edge.concept_id === theme.concept_id && selectedIds.has(edge.source) && selectedIds.has(edge.target)).slice(0, 70)) {{
        const a = stockLayout.get(edge.source);
        const b = stockLayout.get(edge.target);
        if (!a || !b) continue;
        const path = makeSVG("path", {{
          class: "edge correlation",
          d: peerPath(a, b),
          "stroke-width": 1.1 + Math.min(3.2, Math.abs(edge.correlation || 0) * 3.2)
        }});
        const title = makeSVG("title", {{}}, `corr ${{fmt(edge.correlation, 2)}} · ${{edge.lag_direction || "sync"}} · n=${{edge.sample_size || "-"}}`);
        path.appendChild(title);
        correlationRefs.push({{path, a, b}});
        svg.appendChild(path);
      }}

      for (const stock of stockLayout.values()) {{
        const path = makeSVG("path", {{
          class: "edge",
          d: relationPath(stock),
          "marker-end": "url(#arrow)"
        }});
        relationRefs.push({{path, stock}});
        svg.appendChild(path);
      }}

      const conceptGroup = makeSVG("g", {{class: "node concept", transform: `translate(${{concept.x}} ${{concept.y}})`, "data-node-id": concept.id}});
      conceptGroup.appendChild(makeSVG("circle", {{cx: 0, cy: 0, r: concept.radius, fill: "#172033"}}));
      conceptGroup.appendChild(makeSVG("text", {{x: 0, y: 5, "text-anchor": "middle"}}, concept.label));
      conceptGroup.addEventListener("pointerdown", event => startDrag(conceptGroup, concept, event));
      groupByNodeId.set(concept.id, conceptGroup);
      svg.appendChild(conceptGroup);

      for (const stock of stockLayout.values()) {{
        const group = makeSVG("g", {{class: `node stock ${{stock.id === state.focusStockId ? "selected" : ""}}`, transform: `translate(${{stock.x}} ${{stock.y}})`, "data-node-id": stock.id}});
        const fill = marketColor(stock.market || "OTHER");
        const supply = stock.supply_chain_profile || {{}};
        const products = (stock.products || supply.products || []).slice(0, 5).join(", ");
        const upstream = (supply.upstream_concepts || []).slice(0, 6).join(", ");
        const downstream = (supply.downstream_concepts || []).slice(0, 6).join(", ");
        group.appendChild(makeSVG("circle", {{cx: 0, cy: 0, r: stock.radius, fill}}));
        const name = stock.symbol || stock.label || stock.id.replace("stock:", "");
        const labelX = stock.radius + 7;
        group.appendChild(makeSVG("text", {{x: labelX, y: -4}}, name));
        group.appendChild(makeSVG("text", {{x: labelX, y: 12, fill: "#687386"}}, `${{stock.market || "-"}} · R20 ${{fmt(stock.r20, 1, "%")}}`));
        const title = makeSVG(
          "title",
          {{}},
          `${{stock.symbol || ""}} ${{stock.name || ""}}\\nMarket: ${{stock.market || "-"}}\\nBusiness: ${{stock.primary_business || "-"}}\\nProducts: ${{products || "-"}}\\nUpstream: ${{upstream || "-"}}\\nDownstream: ${{downstream || "-"}}\\nSpecialization: ${{(stock.specializations || []).slice(0, 3).join(", ") || "-"}}\\nPath: ${{stock.relationPath || "-"}}\\nR5: ${{fmt(stock.r5, 2, "%")}}\\nR20: ${{fmt(stock.r20, 2, "%")}}`
        );
        group.appendChild(title);
        group.addEventListener("pointerdown", event => startDrag(group, stock, event));
        groupByNodeId.set(stock.id, group);
        svg.appendChild(group);
      }}
    }}

    function renderDetail() {{
      const theme = selectedTheme();
      if (!theme) return;
      const stocks = stockNodesFor(theme.concept_id);
      const summary = $("#summary");
      const headlines = (theme.top_headlines || []).filter(item => !item.error).slice(0, 5);
      summary.innerHTML = `
        <h3></h3>
        <div class="kv"><span>Concept</span><strong>${{theme.concept_id}}</strong></div>
        <div class="kv"><span>Category</span><strong>${{theme.category_label || "-"}}</strong></div>
        <div class="kv"><span>Stage</span><strong>${{theme.stage || "-"}}</strong></div>
        <div class="kv"><span>Markets</span><strong>${{(theme.markets || []).join(", ") || "-"}}</strong></div>
        <div class="kv"><span>Score</span><strong>${{fmt(theme.score, 2)}}</strong></div>
        <div class="kv"><span>Momentum</span><strong>R5 ${{fmt(theme.r5_median, 1, "%")}} · R20 ${{fmt(theme.r20_median, 1, "%")}}</strong></div>
        <div class="kv"><span>Breadth</span><strong>${{stocks.length}} stocks · breakout ${{fmt((theme.breakout_ratio || 0) * 100, 1, "%")}}</strong></div>
        <ul class="headline-list"></ul>
      `;
      summary.querySelector("h3").textContent = theme.label || theme.concept_id;
      const ul = summary.querySelector(".headline-list");
      if (headlines.length) {{
        for (const item of headlines) {{
          const li = document.createElement("li");
          const a = document.createElement("a");
          a.href = item.url || "#";
          a.target = "_blank";
          a.rel = "noreferrer";
          a.textContent = item.title || item.source || "headline";
          li.appendChild(a);
          ul.appendChild(li);
        }}
      }} else {{
        const li = document.createElement("li");
        li.textContent = "No headline evidence in this snapshot.";
        ul.appendChild(li);
      }}

      const tbody = $("#stockRows");
      tbody.innerHTML = "";
      for (const stock of stocks) {{
        const tr = document.createElement("tr");
        if (stock.id === state.focusStockId) tr.className = "selected-stock";
        const near = stock.near_20d_high ? "yes" : "no";
        const bottleneck = stock.bottleneck_profile || {{}};
        const supply = stock.supply_chain_profile || {{}};
        const productsText = (stock.products || supply.products || []).slice(0, 6).join(", ");
        const supplyText = [
          (supply.layers || []).slice(0, 3).join(", "),
          (supply.upstream_concepts || []).length ? `up=${{(supply.upstream_concepts || []).slice(0, 5).join(",")}}` : "",
          (supply.downstream_concepts || []).length ? `down=${{(supply.downstream_concepts || []).slice(0, 5).join(",")}}` : ""
        ].filter(Boolean).join(" | ");
        const bottleneckText = [
          bottleneck.layer || "",
          bottleneck.scarcity ? `scarcity=${{bottleneck.scarcity}}` : "",
          bottleneck.substitutability ? `sub=${{bottleneck.substitutability}}` : "",
          bottleneck.discovery_state ? `discovery=${{bottleneck.discovery_state}}` : ""
        ].filter(Boolean).join(" | ");
        const corr = stock.bestCorrelation;
        const corrText = corr ? `${{corr.otherSymbol}} ${{fmt(corr.correlation, 2)}}` : "-";
        const corrTitle = corr ? `${{corr.lag_direction || "sync"}} · n=${{corr.sample_size || "-"}}` : "";
        tr.innerHTML = `
          <td><span class="pill" style="border-color:${{marketColor(stock.market || "OTHER")}}33;color:${{marketColor(stock.market || "OTHER")}}">${{stock.market || "-"}}</span></td>
          <td><strong>${{esc(stock.symbol || stock.id.replace("stock:", ""))}}</strong></td>
          <td>${{esc(stock.name || "-")}}</td>
          <td title="${{esc(productsText)}}">${{esc(productsText || "-")}}</td>
          <td title="${{esc(supplyText)}}">${{esc(supplyText || "-")}}</td>
          <td title="${{esc(bottleneck.reason || bottleneckText || "")}}">${{esc(bottleneckText || "-")}}</td>
          <td title="${{esc(corrTitle)}}">${{esc(corrText)}}</td>
          <td title="${{esc(stock.relationPath || "")}}">${{esc(stock.relationPath || "-")}}</td>
          <td class="num ${{signedClass(stock.r5)}}">${{fmt(stock.r5, 1, "%")}}</td>
          <td class="num ${{signedClass(stock.r20)}}">${{fmt(stock.r20, 1, "%")}}</td>
          <td>${{near}}</td>
          <td title="${{esc((stock.specializations || []).join(", "))}}">${{esc(stock.primary_business || "-")}}</td>
        `;
        tbody.appendChild(tr);
      }}
    }}

    function render() {{
      if (!themeMatches(selectedTheme() || {{}})) {{
        state.selected = filteredThemes()[0]?.concept_id || themes[0]?.concept_id || "";
      }}
      renderStats();
      renderThemeList();
      $("#themeSelect").value = state.selected;
      renderDetail();
      renderGraph();
    }}

    function bindEvents() {{
      $("#themeSelect").addEventListener("change", event => {{
        state.selected = event.target.value || themes[0]?.concept_id || "";
        state.search = "";
        state.stockSearch = "";
        state.focusStockId = "";
        state.market = "ALL";
        state.stage = "ALL";
        $("#search").value = "";
        $("#stockSearch").value = "";
        closeStockSuggestions();
        renderControls();
        render();
      }});
      $("#search").addEventListener("input", event => {{
        state.search = event.target.value;
        render();
      }});
      $("#stockSearch").addEventListener("focus", event => {{
        state.stockSearch = event.target.value;
        renderStockSuggestions(true);
      }});
      $("#stockSearch").addEventListener("input", event => {{
        state.stockSearch = event.target.value;
        if (!state.stockSearch.trim()) state.focusStockId = "";
        renderStockSuggestions(true);
        render();
      }});
      $("#stockSearch").addEventListener("keydown", event => {{
        if (event.key === "Enter") {{
          event.preventDefault();
          const stock = stockSuggestions()[0];
          if (stock) chooseStock(stock);
        }} else if (event.key === "Escape") {{
          closeStockSuggestions();
        }}
      }});
      $("#stockSearch").addEventListener("blur", () => {{
        window.setTimeout(closeStockSuggestions, 120);
      }});
      $("#market").addEventListener("change", event => {{
        state.market = event.target.value;
        render();
      }});
      $("#stage").addEventListener("change", event => {{
        state.stage = event.target.value;
        render();
      }});
      $("#topN").addEventListener("change", event => {{
        state.topN = Number(event.target.value);
        render();
      }});
      window.addEventListener("resize", () => renderGraph());
    }}

    renderControls();
    bindEvents();
    render();
  </script>
</body>
</html>
"""


def main() -> int:
    parser = argparse.ArgumentParser(description="Build self-contained ThemeMiner HTML graph")
    parser.add_argument("--output-dir", default="thememiner/output")
    parser.add_argument("--html", default="thememiner/output/theme_graph.html")
    args = parser.parse_args()

    output_dir = Path(args.output_dir)
    payload = {
        "library": read_json(output_dir / "theme_library.json"),
        "graph": read_json(output_dir / "cross_market_stock_graph.json"),
        "manifest": read_json(output_dir / "update_manifest.json"),
    }
    html = build_html(payload)
    target = Path(args.html)
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(html, encoding="utf-8")
    print(f"Wrote {target}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
