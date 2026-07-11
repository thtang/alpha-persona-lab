#!/usr/bin/env python3
"""Build a self-contained Lagradar + ThemeMiner diffusion graph HTML."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

from scan_laggards import THEME_TO_CONCEPTS


def read_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def read_optional_json(path: Path, default: Any) -> Any:
    if not path.exists():
        return default
    return read_json(path)


def read_jsonl(path: Path) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    rows: list[dict[str, Any]] = []
    with path.open(encoding="utf-8") as handle:
        for line in handle:
            if line.strip():
                rows.append(json.loads(line))
    return rows


def to_script_json(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, separators=(",", ":")).replace("</", "<\\/")


def build_html(payload: dict[str, Any]) -> str:
    data = to_script_json(payload)
    return f"""<!doctype html>
<html lang="zh-Hant">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>Lagradar Theme Diffusion Graph</title>
  <style>
    :root {{
      color-scheme: light;
      --bg: #f5f7fa;
      --panel: #ffffff;
      --ink: #172033;
      --muted: #687386;
      --line: #d8dde6;
      --soft: #eef2f7;
      --blue: #2563eb;
      --green: #059669;
      --amber: #d97706;
      --red: #dc2626;
      --purple: #7c3aed;
      --cyan: #0891b2;
      --shadow: 0 10px 28px rgba(23, 32, 51, .08);
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

    button, input, select {{ font: inherit; }}

    header {{
      background: var(--panel);
      border-bottom: 1px solid var(--line);
      padding: 17px 22px 13px;
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
      font-weight: 760;
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
      min-width: 102px;
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
      grid-template-columns: minmax(210px, 1fr) minmax(180px, .7fr) minmax(150px, .55fr) minmax(150px, .55fr) minmax(150px, .55fr);
      gap: 10px;
      padding: 12px 22px;
      background: #fbfcfe;
      border-bottom: 1px solid var(--line);
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

    main {{
      display: grid;
      grid-template-columns: 360px minmax(0, 1fr);
      gap: 14px;
      padding: 14px 22px 22px;
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
      justify-content: space-between;
      gap: 10px;
      align-items: center;
    }}

    .theme-name {{
      font-size: 16px;
      font-weight: 740;
      line-height: 1.25;
    }}

    .score {{
      color: var(--blue);
      font-weight: 760;
      font-variant-numeric: tabular-nums;
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

    .stage-0_latent_or_cold {{ color: var(--muted); }}
    .stage-1_overseas_validated {{ color: var(--blue); }}
    .stage-2_local_initial_move {{ color: var(--cyan); }}
    .stage-3_diffusion_confirmation {{ color: var(--green); }}
    .stage-4_retail_climax_or_overheat {{ color: var(--red); }}
    .stage-5_late_catchup_or_fade {{ color: var(--amber); }}

    .workspace {{
      display: grid;
      grid-template-rows: auto minmax(430px, 52vh) auto;
      gap: 14px;
      min-width: 0;
    }}

    .cards {{
      display: grid;
      grid-template-columns: repeat(6, minmax(112px, 1fr));
      gap: 8px;
    }}

    .metric-card {{
      border: 1px solid var(--line);
      border-radius: 7px;
      background: var(--panel);
      padding: 9px 10px;
      min-width: 0;
    }}

    .metric-card b {{
      display: block;
      font-size: 18px;
      line-height: 1.15;
      font-variant-numeric: tabular-nums;
    }}

    .metric-card span {{
      display: block;
      margin-top: 3px;
      font-size: 11px;
      color: var(--muted);
    }}

    .graph-panel, .detail-panel {{
      border: 1px solid var(--line);
      border-radius: 8px;
      background: var(--panel);
      box-shadow: var(--shadow);
      overflow: hidden;
      min-width: 0;
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
      color: var(--muted);
      font-size: 11px;
    }}

    .legend span {{
      display: inline-flex;
      align-items: center;
      gap: 5px;
    }}

    .dot {{
      width: 9px;
      height: 9px;
      border-radius: 50%;
      display: inline-block;
      background: var(--muted);
    }}

    .graph-wrap {{
      height: calc(100% - 50px);
      min-height: 380px;
    }}

    svg {{
      display: block;
      width: 100%;
      height: 100%;
    }}

    .edge {{
      fill: none;
      stroke: #a7b0bf;
      stroke-width: 1.05;
      opacity: .45;
    }}

    .edge.candidate {{
      stroke: #d97706;
      opacity: .75;
      stroke-width: 1.8;
    }}

    .edge.leader {{
      stroke: #2563eb;
      opacity: .62;
      stroke-width: 1.5;
    }}

    .node circle {{
      stroke: #fff;
      stroke-width: 2;
      filter: drop-shadow(0 2px 5px rgba(23,32,51,.18));
    }}

    .node {{
      cursor: grab;
    }}

    .node.dragging {{
      cursor: grabbing;
    }}

    .node.dragging circle {{
      stroke: #38bdf8;
      stroke-width: 5;
    }}

    .node text {{
      font-size: 12px;
      fill: var(--ink);
      paint-order: stroke;
      stroke: rgba(255,255,255,.88);
      stroke-width: 4px;
      stroke-linejoin: round;
      user-select: none;
    }}

    .node.concept text {{
      font-size: 13px;
      font-weight: 740;
    }}

    .node.candidate circle {{
      stroke: var(--amber);
      stroke-width: 4;
    }}

    .node.leader circle {{
      stroke: var(--blue);
      stroke-width: 3;
    }}

    .detail-panel {{
      padding: 14px;
    }}

    .detail-grid {{
      display: grid;
      grid-template-columns: minmax(260px, .8fr) minmax(420px, 1.35fr);
      gap: 14px;
      min-width: 0;
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
      grid-template-columns: 96px 1fr;
      gap: 7px;
      font-size: 13px;
      padding: 5px 0;
      border-bottom: 1px solid #edf0f5;
    }}

    .kv:last-child {{
      border-bottom: 0;
    }}

    .kv span:first-child {{
      color: var(--muted);
    }}

    .chips {{
      display: flex;
      gap: 6px;
      flex-wrap: wrap;
      margin-top: 8px;
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
      min-width: 1380px;
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

    .pos {{ color: var(--green); }}
    .neg {{ color: var(--red); }}
    .empty {{ padding: 28px; text-align: center; color: var(--muted); }}

    @media (max-width: 1180px) {{
      .toolbar {{ grid-template-columns: 1fr 1fr; }}
      main {{ grid-template-columns: 1fr; }}
      .theme-list {{ max-height: 320px; }}
      .cards {{ grid-template-columns: repeat(3, 1fr); }}
      .detail-grid {{ grid-template-columns: 1fr; }}
    }}

    @media (max-width: 680px) {{
      header, .toolbar, main {{ padding-left: 12px; padding-right: 12px; }}
      .toolbar {{ grid-template-columns: 1fr; }}
      .cards {{ grid-template-columns: 1fr 1fr; }}
    }}
  </style>
</head>
<body>
  <header>
    <div class="header-row">
      <div>
        <h1>Lagradar Theme Diffusion Graph</h1>
        <div class="subtitle" id="subtitle">Loading...</div>
      </div>
      <div class="stats" id="stats"></div>
    </div>
  </header>

  <section class="toolbar" aria-label="Filters">
    <div class="control">
      <label for="search">Search</label>
      <input id="search" type="search" placeholder="題材 / 股票 / ticker / stage">
    </div>
    <div class="control">
      <label for="themeSelect">Theme</label>
      <select id="themeSelect"></select>
    </div>
    <div class="control">
      <label for="status">Candidate Status</label>
      <select id="status"></select>
    </div>
    <div class="control">
      <label for="market">Market</label>
      <select id="market"></select>
    </div>
    <div class="control">
      <label for="topN">Theme List</label>
      <select id="topN">
        <option value="8">Top 8</option>
        <option value="15" selected>Top 15</option>
        <option value="999">All</option>
      </select>
    </div>
  </section>

  <main>
    <aside>
      <div class="theme-list" id="themeList"></div>
    </aside>

    <section class="workspace">
      <div class="cards" id="metricCards"></div>

      <div class="graph-panel">
        <div class="panel-head">
          <h2 id="graphTitle">Diffusion Graph</h2>
          <div class="legend" id="legend"></div>
        </div>
        <div class="graph-wrap">
          <svg id="graphSvg" role="img" aria-label="ThemeMiner graph with Lagradar diffusion scores"></svg>
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
                    <th>Status</th>
                    <th>Market</th>
                    <th>Symbol</th>
                    <th>Name</th>
                    <th>Score</th>
                    <th>Gap20</th>
                    <th>Turn</th>
                    <th>Overheat</th>
                    <th>R5</th>
                    <th>R20</th>
                    <th>Vol</th>
                    <th>Trigger</th>
                    <th>Invalidation</th>
                    <th>Business</th>
                  </tr>
                </thead>
                <tbody id="candidateRows"></tbody>
              </table>
            </div>
          </div>
        </div>
      </div>
    </section>
  </main>

  <script>
    const DATA = {data};
    const themeScores = (DATA.theme_scores || []).slice().sort((a, b) => (b.theme_heat || 0) - (a.theme_heat || 0));
    const candidates = DATA.candidates || [];
    const seedThemes = DATA.seed?.themes || [];
    const themeToConcepts = DATA.theme_to_concepts || {{}};
    const graph = DATA.thememiner?.graph || {{nodes: [], edges: []}};
    const tmManifest = DATA.thememiner?.manifest || {{}};
    const lagManifest = DATA.lagradar_manifest || {{}};

    const MARKET_COLORS = {{US:"#2563eb",TW:"#dc2626",JP:"#7c3aed",CN:"#059669",HK:"#d97706",KR:"#0891b2",OTHER:"#687386"}};
    const MARKET_ORDER = ["US","JP","KR","TW","CN","HK","OTHER"];
    const STATUS_COLORS = {{improving_laggard:"#059669",early_turn_laggard:"#0891b2",sleeping_laggard:"#687386",weak_not_laggard:"#dc2626",overheated_catchup:"#d97706",already_caught_up:"#7c3aed",neutral:"#687386"}};
    const nodeById = new Map((graph.nodes || []).map(node => [node.id, node]));
    const stockBySymbol = new Map((graph.nodes || []).filter(node => node.type === "stock").map(node => [node.symbol, node]));
    const conceptEdges = (graph.edges || []).filter(edge => edge.type === "concept_stock");
    const seedByTheme = new Map(seedThemes.map(theme => [theme.theme_id, theme]));
    const candidatesByTheme = new Map();
    for (const row of candidates) {{
      if (!candidatesByTheme.has(row.theme_id)) candidatesByTheme.set(row.theme_id, []);
      candidatesByTheme.get(row.theme_id).push(row);
    }}

    const state = {{search:"", status:"ALL", market:"ALL", topN:15, selected:themeScores[0]?.theme_id || ""}};
    const dragState = {{active:null, group:null, pointerId:null, offsetX:0, offsetY:0}};
    const $ = selector => document.querySelector(selector);
    const svgNS = "http://www.w3.org/2000/svg";

    function fmt(value, digits = 1, suffix = "") {{
      if (value === null || value === undefined || Number.isNaN(Number(value))) return "-";
      return `${{Number(value).toFixed(digits)}}${{suffix}}`;
    }}

    function esc(value) {{
      return String(value ?? "").replace(/[&<>"']/g, ch => ({{"&":"&amp;","<":"&lt;",">":"&gt;",'"':"&quot;","'":"&#39;"}}[ch]));
    }}

    function cssIdent(value) {{
      return String(value || "").replace(/[^a-zA-Z0-9_-]/g, "_");
    }}

    function signedClass(value) {{
      const num = Number(value || 0);
      return num >= 0 ? "pos" : "neg";
    }}

    function marketColor(market) {{
      return MARKET_COLORS[market] || MARKET_COLORS.OTHER;
    }}

    function themeCandidates(themeId) {{
      let rows = (candidatesByTheme.get(themeId) || []).slice();
      if (state.status !== "ALL") rows = rows.filter(row => row.status === state.status);
      if (state.market !== "ALL") rows = rows.filter(row => row.market === state.market);
      return rows.sort((a, b) => (b.candidate_score || 0) - (a.candidate_score || 0));
    }}

    function themeMatches(theme) {{
      const key = state.search.trim().toLowerCase();
      if (!key) return true;
      const seed = seedByTheme.get(theme.theme_id) || {{}};
      const candText = (candidatesByTheme.get(theme.theme_id) || [])
        .slice(0, 30)
        .map(row => `${{row.symbol}} ${{row.name}} ${{row.status}}`)
        .join(" ");
      const text = [
        theme.theme_id,
        theme.label,
        theme.lifecycle_stage,
        seed.hypothesis,
        ...(seed.catalysts || []),
        candText
      ].join(" ").toLowerCase();
      return text.includes(key);
    }}

    function filteredThemes() {{
      return themeScores.filter(themeMatches).slice(0, state.topN);
    }}

    function selectedTheme() {{
      return themeScores.find(row => row.theme_id === state.selected) || filteredThemes()[0] || themeScores[0];
    }}

    function stockBusiness(symbol, fallback = "") {{
      const stock = stockBySymbol.get(symbol);
      return stock?.primary_business || fallback || "-";
    }}

    function seedNodes(themeId) {{
      return (seedByTheme.get(themeId)?.nodes || []).slice();
    }}

    function leaderRows(theme) {{
      return (theme.leaders || []).slice().sort((a, b) => (b.r20 || 0) - (a.r20 || 0));
    }}

    function relevantStockSymbols(theme) {{
      const symbols = new Set();
      for (const node of seedNodes(theme.theme_id)) symbols.add(node.symbol);
      for (const row of leaderRows(theme)) symbols.add(row.symbol);
      for (const row of (candidatesByTheme.get(theme.theme_id) || []).slice(0, 40)) symbols.add(row.symbol);
      const concepts = new Set(themeToConcepts[theme.theme_id] || [theme.theme_id]);
      const conceptStockScores = [];
      for (const edge of conceptEdges) {{
        const conceptId = String(edge.source || "").replace("concept:", "");
        if (!concepts.has(conceptId)) continue;
        const stock = nodeById.get(edge.target);
        if (!stock?.symbol) continue;
        conceptStockScores.push({{symbol: stock.symbol, r20: Number(stock.r20 || 0), weight: Number(edge.weight || 0)}});
      }}
      conceptStockScores
        .sort((a, b) => (b.weight - a.weight) || (b.r20 - a.r20))
        .slice(0, 70)
        .forEach(row => symbols.add(row.symbol));
      return Array.from(symbols).filter(symbol => stockBySymbol.has(symbol));
    }}

    function renderStats() {{
      $("#subtitle").textContent = `Lagradar ${{lagManifest.built_at || "-"}} · ThemeMiner ${{tmManifest.built_at || "-"}}`;
      const stats = [
        ["Lagradar Themes", themeScores.length],
        ["Candidates", candidates.length],
        ["TM Stocks", tmManifest.watchlist_symbol_count || (graph.nodes || []).filter(n => n.type === "stock").length],
        ["TM Edges", tmManifest.graph_edge_count || (graph.edges || []).length],
        ["Corr", tmManifest.correlation_edge_count || 0],
        ["Stage", selectedTheme()?.lifecycle_stage || "-"]
      ];
      $("#stats").innerHTML = stats.map(([label, value]) => `<div class="stat"><b>${{esc(value)}}</b><span>${{label}}</span></div>`).join("");
    }}

    function renderControls() {{
      $("#themeSelect").innerHTML = themeScores.map(theme => `<option value="${{esc(theme.theme_id)}}">${{esc(theme.label)}} · heat ${{fmt(theme.theme_heat,1)}}</option>`).join("");
      $("#themeSelect").value = state.selected;
      const statuses = Array.from(new Set(candidates.map(row => row.status).filter(Boolean))).sort();
      $("#status").innerHTML = [`<option value="ALL">All statuses</option>`, ...statuses.map(s => `<option value="${{esc(s)}}">${{esc(s)}}</option>`)].join("");
      $("#status").value = state.status;
      const markets = Array.from(new Set(candidates.map(row => row.market).filter(Boolean))).sort();
      $("#market").innerHTML = [`<option value="ALL">All markets</option>`, ...markets.map(m => `<option value="${{esc(m)}}">${{esc(m)}}</option>`)].join("");
      $("#market").value = state.market;
      $("#topN").value = String(state.topN);
    }}

    function renderThemeList() {{
      const root = $("#themeList");
      const rows = filteredThemes();
      if (!rows.length) {{
        root.innerHTML = `<div class="empty">No matching themes</div>`;
        return;
      }}
      root.innerHTML = "";
      for (const theme of rows) {{
        const count = (candidatesByTheme.get(theme.theme_id) || []).length;
        const clean = (candidatesByTheme.get(theme.theme_id) || []).filter(row => row.status === "improving_laggard" || row.status === "early_turn_laggard").length;
        const button = document.createElement("button");
        button.className = `theme-card ${{theme.theme_id === state.selected ? "active" : ""}}`;
        button.type = "button";
        button.innerHTML = `
          <div class="theme-topline">
            <div class="theme-name">${{esc(theme.label)}}</div>
            <div class="score">${{fmt(theme.theme_heat,1)}}</div>
          </div>
          <div class="meta">
            <span class="pill stage-${{cssIdent(theme.lifecycle_stage)}}">${{esc(theme.lifecycle_stage || "-")}}</span>
            <span class="pill">diff ${{fmt(theme.diffusion_score,1)}}</span>
            <span class="pill">gap list ${{clean}}/${{count}}</span>
            <span class="pill">overheat ${{fmt((theme.overheat_ratio || 0) * 100,0,"%")}}</span>
          </div>
        `;
        button.addEventListener("click", () => {{
          state.selected = theme.theme_id;
          render();
        }});
        root.appendChild(button);
      }}
    }}

    function renderMetricCards(theme) {{
      const rows = [
        ["Heat", fmt(theme.theme_heat, 1), "leader basket strength"],
        ["Diffusion", fmt(theme.diffusion_score, 1), "follower breadth"],
        ["Leader 20D", fmt(theme.leader_20d_median, 1, "%"), "median"],
        ["Leader 60D", fmt(theme.leader_60d_median, 1, "%"), "median"],
        ["Follower +5D", fmt((theme.follower_positive_5d_ratio || 0) * 100, 0, "%"), "breadth"],
        ["Overheat", fmt((theme.overheat_ratio || 0) * 100, 0, "%"), "late-stage risk"]
      ];
      $("#metricCards").innerHTML = rows.map(([label, value, sub]) => `<div class="metric-card"><b>${{esc(value)}}</b><span>${{esc(label)}} · ${{esc(sub)}}</span></div>`).join("");
    }}

    function makeSVG(name, attrs = {{}}, text = "") {{
      const element = document.createElementNS(svgNS, name);
      for (const [key, value] of Object.entries(attrs)) element.setAttribute(key, value);
      if (text) element.textContent = text;
      return element;
    }}

    function svgPoint(svg, event) {{
      const point = svg.createSVGPoint();
      point.x = event.clientX;
      point.y = event.clientY;
      const matrix = svg.getScreenCTM();
      return matrix ? point.matrixTransform(matrix.inverse()) : {{x: event.offsetX, y: event.offsetY}};
    }}

    function clampNode(node, width, height) {{
      const radius = node.r || 12;
      node.x = Math.max(radius + 8, Math.min(width - radius - 8, node.x));
      node.y = Math.max(radius + 8, Math.min(height - radius - 8, node.y));
    }}

    function renderLegend(theme) {{
      const statuses = Array.from(new Set(themeCandidates(theme.theme_id).map(row => row.status))).slice(0, 5);
      $("#legend").innerHTML = [
        `<span><i class="dot" style="background:#2563eb"></i>leader</span>`,
        `<span><i class="dot" style="background:#d97706"></i>candidate</span>`,
        ...statuses.map(s => `<span><i class="dot" style="background:${{STATUS_COLORS[s] || "#687386"}}"></i>${{esc(s)}}</span>`)
      ].join("");
    }}

    function renderGraph(theme) {{
      renderLegend(theme);
      $("#graphTitle").textContent = `${{theme.label}} · ThemeMiner graph + Lagradar diffusion`;
      const svg = $("#graphSvg");
      svg.innerHTML = "";
      dragState.active = null;
      dragState.group = null;
      dragState.pointerId = null;
      const box = svg.getBoundingClientRect();
      const width = Math.max(900, box.width || 1100);
      const height = Math.max(430, box.height || 540);
      svg.setAttribute("viewBox", `0 0 ${{width}} ${{height}}`);
      const concepts = (themeToConcepts[theme.theme_id] || []).map(id => nodeById.get(`concept:${{id}}`)).filter(Boolean);
      const symbols = relevantStockSymbols(theme).slice(0, 95);
      const selectedStocks = symbols.map(symbol => stockBySymbol.get(symbol)).filter(Boolean);
      const candMap = new Map((candidatesByTheme.get(theme.theme_id) || []).map(row => [row.symbol, row]));
      const leaderSet = new Set(leaderRows(theme).map(row => row.symbol));

      const conceptLayout = new Map();
      const conceptX = width * 0.25;
      const conceptTop = 58;
      const conceptBottom = height - 46;
      const conceptGap = concepts.length > 1 ? (conceptBottom - conceptTop) / (concepts.length - 1) : 0;
      concepts.forEach((concept, index) => {{
        conceptLayout.set(concept.id, {{...concept, x: conceptX, y: concepts.length === 1 ? height * .5 : conceptTop + conceptGap * index, r: 12 + Math.min(16, Number(concept.score || 0) / 8)}});
      }});
      for (const concept of conceptLayout.values()) clampNode(concept, width, height);

      const markets = Array.from(new Set(selectedStocks.map(stock => stock.market || "OTHER"))).sort((a, b) => MARKET_ORDER.indexOf(a) - MARKET_ORDER.indexOf(b));
      const stockLayout = new Map();
      const colStart = width * 0.52;
      const colGap = markets.length > 1 ? (width * 0.42) / (markets.length - 1) : 0;
      markets.forEach((market, marketIndex) => {{
        const group = selectedStocks
          .filter(stock => (stock.market || "OTHER") === market)
          .sort((a, b) => (candMap.has(b.symbol) - candMap.has(a.symbol)) || (leaderSet.has(b.symbol) - leaderSet.has(a.symbol)) || (Number(b.r20 || 0) - Number(a.r20 || 0)))
          .slice(0, 28);
        const x = markets.length === 1 ? width * 0.73 : colStart + colGap * marketIndex;
        const top = 58;
        const bottom = height - 46;
        const gap = group.length > 1 ? (bottom - top) / (group.length - 1) : 0;
        group.forEach((stock, index) => {{
          const candidate = candMap.get(stock.symbol);
          const isLeader = leaderSet.has(stock.symbol);
          stockLayout.set(stock.id, {{
            ...stock,
            x,
            y: group.length === 1 ? height * .5 : top + gap * index,
            r: candidate ? 13 : isLeader ? 12 : 8 + Math.min(8, Math.abs(Number(stock.r20 || 0)) / 10),
            candidate,
            isLeader
          }});
        }});
      }});
      for (const stock of stockLayout.values()) clampNode(stock, width, height);

      function path(a, b) {{
        const mx = (a.x + b.x) / 2;
        return `M ${{a.x + (a.r || 12)}} ${{a.y}} C ${{mx}} ${{a.y}}, ${{mx}} ${{b.y}}, ${{b.x - (b.r || 9)}} ${{b.y}}`;
      }}

      const edgeRefs = [];
      const groupByNodeId = new Map();

      function updatePositions() {{
        for (const item of edgeRefs) {{
          item.path.setAttribute("d", path(item.a, item.b));
        }}
        for (const concept of conceptLayout.values()) {{
          const group = groupByNodeId.get(concept.id);
          if (group) group.setAttribute("transform", `translate(${{concept.x}} ${{concept.y}})`);
        }}
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
        updatePositions();
      }};
      svg.onpointerup = stopDrag;
      svg.onpointercancel = stopDrag;
      svg.onpointerleave = event => {{
        if (dragState.active && dragState.pointerId === event.pointerId) stopDrag();
      }};

      for (const edge of conceptEdges) {{
        const c = conceptLayout.get(edge.source);
        const s = stockLayout.get(edge.target);
        if (!c || !s) continue;
        const cls = s.candidate ? "edge candidate" : s.isLeader ? "edge leader" : "edge";
        const p = makeSVG("path", {{class: cls, d: path(c, s)}});
        edgeRefs.push({{path:p, a:c, b:s}});
        svg.appendChild(p);
      }}

      for (const concept of conceptLayout.values()) {{
        const g = makeSVG("g", {{class:"node concept", transform:`translate(${{concept.x}} ${{concept.y}})`, "data-node-id": concept.id}});
        g.appendChild(makeSVG("circle", {{cx:0, cy:0, r:concept.r, fill:"#172033"}}));
        g.appendChild(makeSVG("text", {{x:concept.r + 7, y:4}}, concept.label || concept.concept_id || concept.id.replace("concept:","")));
        g.addEventListener("pointerdown", event => startDrag(g, concept, event));
        groupByNodeId.set(concept.id, g);
        svg.appendChild(g);
      }}

      for (const stock of stockLayout.values()) {{
        const cls = `node stock ${{stock.candidate ? "candidate" : ""}} ${{stock.isLeader ? "leader" : ""}}`;
        const g = makeSVG("g", {{class:cls, transform:`translate(${{stock.x}} ${{stock.y}})`, "data-node-id": stock.id}});
        const fill = stock.candidate ? (STATUS_COLORS[stock.candidate.status] || "#d97706") : marketColor(stock.market || "OTHER");
        g.appendChild(makeSVG("circle", {{cx:0, cy:0, r:stock.r, fill}}));
        g.appendChild(makeSVG("text", {{x:stock.r + 7, y:-4}}, stock.symbol || stock.id.replace("stock:","")));
        g.appendChild(makeSVG("text", {{x:stock.r + 7, y:12, fill:"#687386"}}, `${{stock.market || "-"}} · R20 ${{fmt(stock.r20,1,"%")}}`));
        g.appendChild(makeSVG("title", {{}}, `${{stock.symbol}} ${{stock.name || ""}}\\n${{stock.candidate ? `${{stock.candidate.status}} score=${{fmt(stock.candidate.candidate_score,1)}} gap20=${{fmt(stock.candidate.lag_gap_20d,1,"%")}}` : stock.isLeader ? "leader" : "ThemeMiner peer"}}\\nThesis: ${{stock.candidate?.thesis_label || "-"}}\\nChain: ${{stock.candidate?.ai_chain_position || "-"}}\\nBusiness: ${{stock.candidate?.primary_business || stock.primary_business || "-"}}`));
        g.addEventListener("pointerdown", event => startDrag(g, stock, event));
        groupByNodeId.set(stock.id, g);
        svg.appendChild(g);
      }}
    }}

    function trigger(row) {{
      if (row.status === "overheated_catchup") return "等回測/rebase，不追伸";
      if (row.breakout_20d) return "守住20D breakout，高量續強";
      if (row.above_ma5 && row.above_ma10) return "MA5/10續強，突破前高";
      if (row.status === "sleeping_laggard") return "先等放量站回MA10/MA20";
      return "短均轉強 + leader basket不翻弱";
    }}

    function invalidation(row) {{
      if (row.status === "sleeping_laggard") return "跌破近期低點或leader轉弱";
      if ((row.overheat_score || 0) > 2) return "爆量長黑或跌回突破區";
      return "失守MA10/MA20，或leader basket rollover";
    }}

    function renderSummary(theme) {{
      const seed = seedByTheme.get(theme.theme_id) || {{}};
      const leaders = leaderRows(theme).slice(0, 6);
      const concepts = themeToConcepts[theme.theme_id] || [];
      $("#summary").innerHTML = `
        <h3>${{esc(theme.label)}}</h3>
        <div class="kv"><span>Theme ID</span><strong>${{esc(theme.theme_id)}}</strong></div>
        <div class="kv"><span>Lifecycle</span><strong class="stage-${{cssIdent(theme.lifecycle_stage)}}">${{esc(theme.lifecycle_stage || "-")}}</strong></div>
        <div class="kv"><span>Shock</span><strong>${{esc((seed.catalysts || []).slice(0, 4).join(" / ") || "-")}}</strong></div>
        <div class="kv"><span>Relation</span><strong>${{esc(concepts.slice(0, 8).join(" / ") || "-")}}</strong></div>
        <div class="kv"><span>Breadth</span><strong>+5D ${{fmt((theme.follower_positive_5d_ratio || 0) * 100,0,"%")}} · breakout ${{fmt((theme.follower_breakout_ratio || 0) * 100,0,"%")}}</strong></div>
        <div class="kv"><span>Leaders</span><strong>${{esc(leaders.map(row => `${{row.symbol}} ${{fmt(row.r20,1,"%")}}`).join(" / ") || "-")}}</strong></div>
        <div class="chips">${{concepts.slice(0, 12).map(id => `<span class="pill">${{esc(id)}}</span>`).join("")}}</div>
      `;
    }}

    function renderCandidateTable(theme) {{
      const rows = themeCandidates(theme.theme_id);
      const tbody = $("#candidateRows");
      if (!rows.length) {{
        tbody.innerHTML = `<tr><td colspan="14" class="empty">No candidates after filters</td></tr>`;
        return;
      }}
      tbody.innerHTML = rows.map(row => {{
        const stock = stockBySymbol.get(row.symbol);
        const thesis = row.thesis_label ? `${{row.thesis_label}} · ` : "";
        const business = `${{thesis}}${{stockBusiness(row.symbol, row.primary_business)}}`;
        const statusColor = STATUS_COLORS[row.status] || "#687386";
        return `
          <tr>
            <td><span class="pill" style="border-color:${{statusColor}}55;color:${{statusColor}}">${{esc(row.status || "-")}}</span></td>
            <td><span class="pill" style="border-color:${{marketColor(row.market || "OTHER")}}33;color:${{marketColor(row.market || "OTHER")}}">${{esc(row.market || "-")}}</span></td>
            <td><strong>${{esc(row.symbol)}}</strong></td>
            <td>${{esc(row.name || "-")}}</td>
            <td class="num">${{fmt(row.candidate_score,1)}}</td>
            <td class="num">${{fmt(row.lag_gap_20d,1,"%")}}</td>
            <td class="num">${{fmt(row.turning_score,2)}}</td>
            <td class="num">${{fmt(row.overheat_score,2)}}</td>
            <td class="num ${{signedClass(row.r5)}}">${{fmt(row.r5,1,"%")}}</td>
            <td class="num ${{signedClass(row.r20)}}">${{fmt(row.r20,1,"%")}}</td>
            <td class="num">${{fmt(row.volume_ratio_20d,2,"x")}}</td>
            <td>${{esc(trigger(row))}}</td>
            <td>${{esc(invalidation(row))}}</td>
            <td title="${{esc([row.ai_chain_position, row.non_ai_chain_position, ...(row.thesis_risks || [])].filter(Boolean).join(" / "))}}">${{esc(business)}}</td>
          </tr>
        `;
      }}).join("");
    }}

    function render() {{
      if (!selectedTheme()) return;
      if (!themeMatches(selectedTheme())) {{
        state.selected = filteredThemes()[0]?.theme_id || themeScores[0]?.theme_id || "";
      }}
      const theme = selectedTheme();
      renderStats();
      renderControls();
      renderThemeList();
      renderMetricCards(theme);
      renderGraph(theme);
      renderSummary(theme);
      renderCandidateTable(theme);
      $("#themeSelect").value = theme.theme_id;
    }}

    function bindEvents() {{
      $("#search").addEventListener("input", event => {{
        state.search = event.target.value;
        render();
      }});
      $("#themeSelect").addEventListener("change", event => {{
        state.selected = event.target.value;
        render();
      }});
      $("#status").addEventListener("change", event => {{
        state.status = event.target.value;
        render();
      }});
      $("#market").addEventListener("change", event => {{
        state.market = event.target.value;
        render();
      }});
      $("#topN").addEventListener("change", event => {{
        state.topN = Number(event.target.value);
        render();
      }});
      window.addEventListener("resize", () => renderGraph(selectedTheme()));
    }}

    bindEvents();
    render();
  </script>
</body>
</html>
"""


def main() -> int:
    parser = argparse.ArgumentParser(description="Build self-contained Lagradar HTML graph")
    parser.add_argument("--lagradar-output", default="lagradar/output")
    parser.add_argument("--thememiner-output", default="thememiner/output")
    parser.add_argument("--seed", default=None)
    parser.add_argument("--html", default="lagradar/output/lagradar_theme_graph.html")
    args = parser.parse_args()

    lagradar_dir = Path(args.lagradar_output)
    thememiner_dir = Path(args.thememiner_output)
    seed_path = Path(args.seed) if args.seed else lagradar_dir / "synced_theme_seed.json"
    if not seed_path.exists():
        seed_path = Path("lagradar/data/cross_market_theme_seed.json")
    seed = read_json(seed_path)
    dynamic_theme_to_concepts = {theme["theme_id"]: [theme["theme_id"]] for theme in seed.get("themes", []) if theme.get("theme_id")}
    dynamic_theme_to_concepts.update({key: sorted(value) for key, value in THEME_TO_CONCEPTS.items()})
    payload = {
        "theme_scores": read_json(lagradar_dir / "theme_scores.json"),
        "candidates": read_json(lagradar_dir / "laggard_candidates.json"),
        "lagradar_manifest": read_json(lagradar_dir / "build_manifest.json"),
        "seed": seed,
        "theme_to_concepts": dynamic_theme_to_concepts,
        "thememiner": {
            "graph": read_json(thememiner_dir / "cross_market_stock_graph.json"),
            "manifest": read_json(thememiner_dir / "update_manifest.json"),
        },
    }
    html = build_html(payload)
    target = Path(args.html)
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(html, encoding="utf-8")
    print(f"Wrote {target}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
