DASHBOARD_HTML = r"""<!doctype html>
<html lang="en">
<head>
  <meta charset="UTF-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1.0" />
  <title>pons copy · robinhood chain</title>
  <link rel="preconnect" href="https://fonts.googleapis.com" />
  <link rel="preconnect" href="https://fonts.gstatic.com" crossorigin />
  <link href="https://fonts.googleapis.com/css2?family=IBM+Plex+Mono:wght@400;500;600&family=IBM+Plex+Sans:wght@400;500;600&display=swap" rel="stylesheet" />
  <style>
    :root { --bg:#0b0c0e; --panel:#12141a; --line:#262a33; --ink:#ece7dc; --muted:#8d8678; --amber:#e2a54b; --buy:#3fbe7f; --sell:#e35d5d; --paper:#7ea0d6; }
    * { box-sizing:border-box; }
    html,body { margin:0; min-height:100%; background:var(--bg); color:var(--ink); font-family:"IBM Plex Sans",sans-serif; }
    a { color:var(--amber); text-decoration:none; } a:hover { text-decoration:underline; }
    .boot { min-height:100vh; display:grid; place-items:center; color:var(--muted); letter-spacing:.04em; }
    .shell { max-width:1280px; margin:0 auto; padding:22px 20px 48px; }
    .top { display:flex; justify-content:space-between; gap:16px; align-items:flex-end; border-bottom:1px solid var(--line); padding-bottom:16px; }
    .brand .mark { font-family:"IBM Plex Mono",monospace; font-size:28px; letter-spacing:-.04em; }
    .brand .sub { margin-left:10px; color:var(--muted); }
    .brand .chain { display:block; margin-top:4px; color:var(--muted); font-size:12px; letter-spacing:.08em; text-transform:uppercase; }
    .status-row { display:flex; flex-wrap:wrap; gap:10px; align-items:center; }
    .meta { color:var(--muted); font-family:"IBM Plex Mono",monospace; font-size:12px; }
    .banner { margin-top:14px; padding:10px 12px; border:1px solid #5a2e2e; color:#f0b4b4; background:#1a1010; }
    .stats { display:grid; grid-template-columns:repeat(6,1fr); gap:10px; margin:18px 0; }
    .stat { border:1px solid var(--line); background:var(--panel); padding:12px 14px; }
    .stat span { display:block; color:var(--muted); font-size:11px; letter-spacing:.08em; text-transform:uppercase; }
    .stat strong { display:block; margin-top:6px; font-family:"IBM Plex Mono",monospace; font-size:20px; }
    .grid { display:grid; grid-template-columns:1fr 1fr; gap:12px; }
    .panel { border:1px solid var(--line); background:var(--panel); padding:14px; min-height:220px; }
    .panel.wide { grid-column:1 / -1; }
    .panel h2 { margin:0 0 12px; font-size:12px; letter-spacing:.12em; text-transform:uppercase; color:var(--muted); font-weight:500; }
    .list,.tape { list-style:none; margin:0; padding:0; }
    .row,.add-row { display:flex; gap:10px; justify-content:space-between; align-items:center; padding:8px 0; border-bottom:1px solid #1c1f26; }
    .row a,.row strong { display:block; }
    .row-actions { display:flex; gap:6px; }
    .empty,.dim { color:var(--muted); }
    .add-row input,.settings input,.settings select { width:100%; background:#0b0c0e; border:1px solid var(--line); color:var(--ink); padding:8px 10px; font:inherit; }
    .btn { background:transparent; color:var(--ink); border:1px solid var(--line); padding:7px 12px; cursor:pointer; font:inherit; }
    .btn.accent { border-color:var(--amber); color:var(--amber); }
    .btn.ghost { color:var(--muted); }
    .pill { display:inline-block; border:1px solid var(--line); padding:2px 7px; font-size:11px; letter-spacing:.06em; text-transform:uppercase; font-family:"IBM Plex Mono",monospace; }
    .pill.live,.pill.filled { color:var(--buy); border-color:#245c40; }
    .pill.paper { color:var(--paper); border-color:#2d3d58; }
    .pill.hot { color:#f2c98a; border-color:#6a4a1e; }
    .pill.off,.pill.skipped { color:var(--muted); }
    .pill.failed { color:var(--sell); border-color:#5a2e2e; }
    table { width:100%; border-collapse:collapse; font-size:13px; }
    th { text-align:left; color:var(--muted); font-weight:500; font-size:11px; letter-spacing:.08em; text-transform:uppercase; padding:6px 8px 10px; }
    td { padding:8px; border-top:1px solid #1c1f26; vertical-align:top; }
    .num,.buy,.sell { font-family:"IBM Plex Mono",monospace; }
    .buy { color:var(--buy); } .sell { color:var(--sell); }
    .settings { display:grid; grid-template-columns:1fr 1fr; gap:10px; }
    .settings label span { display:block; margin-bottom:4px; color:var(--muted); font-size:11px; text-transform:uppercase; letter-spacing:.06em; }
    .tape li { padding:6px 0; border-bottom:1px solid #1c1f26; font-size:13px; }
    .tape time { color:var(--muted); font-family:"IBM Plex Mono",monospace; margin-right:8px; }
    .tape .error { color:#f0b4b4; } .tape .trade { color:var(--amber); }
    footer { margin-top:22px; color:var(--muted); font-size:12px; }
    @media (max-width:980px) { .stats,.grid,.settings { grid-template-columns:1fr; } .top { flex-direction:column; align-items:flex-start; } }
  </style>
</head>
<body>
  <div id="root" class="boot">connecting to robinhood chain…</div>
  <script>
    const EXPLORER = "https://robinhoodchain.blockscout.com";
    const PONS = "https://www.ponsfamily.com";
    const root = document.getElementById("root");
    let state = null;

    const short = (v) => !v ? "—" : `${v.slice(0,6)}…${v.slice(-4)}`;
    const fmtEth = (wei, digits=4) => {
      if (!wei) return "0";
      try {
        const n = Number(BigInt(wei)) / 1e18;
        if (n === 0) return "0";
        if (n < 0.0001) return n.toExponential(2);
        return n.toFixed(digits);
      } catch { return wei; }
    };
    async function api(path, init) {
      const res = await fetch(path, { ...init, headers: { "Content-Type": "application/json", ...(init?.headers||{}) } });
      if (!res.ok) throw new Error(await res.text());
      return res.json();
    }
    function pill(tone, text) { return `<span class="pill ${tone}">${text}</span>`; }

    function render() {
      if (!state) return;
      const s = state.settings;
      const filled = state.trades.filter(t => t.status === "filled" || t.status === "paper").length;
      const skipped = state.trades.filter(t => t.status === "skipped").length;
      const failed = state.trades.filter(t => t.status === "failed").length;
      root.className = "shell";
      root.innerHTML = `
        <header class="top">
          <div class="brand">
            <span class="mark">pons</span><span class="sub">copy trader</span>
            <span class="chain">robinhood · 4663 · python</span>
          </div>
          <div class="status-row">
            ${pill(s.running ? "live" : "off", s.running ? "live" : "paused")}
            ${pill(s.dryRun ? "paper" : "hot", s.dryRun ? "paper" : "live fills")}
            <span class="meta">blk ${state.lastBlock} / ${state.headBlock}</span>
            <span class="meta">wallet ${state.wallet.label ?? "watch-only"} · ${Number(state.wallet.eth).toFixed(4)} ETH</span>
            <button class="btn" id="toggle">${s.running ? "pause" : "resume"}</button>
          </div>
        </header>
        <section class="stats">
          ${[["copied", filled],["skipped", skipped],["failed", failed],["positions", state.positions.length],["spent today", Number(state.dailySpentEth).toFixed(4)+" ETH"],["targets", state.targets.filter(t=>t.enabled).length]].map(([l,v]) => `<div class="stat"><span>${l}</span><strong>${v}</strong></div>`).join("")}
        </section>
        <section class="grid">
          <section class="panel">
            <h2>leaders</h2>
            <form class="add-row" id="add-target">
              <input name="address" placeholder="0x leader wallet" required />
              <input name="label" placeholder="label" />
              <button class="btn accent" type="submit">follow</button>
            </form>
            <ul class="list">
              ${state.targets.length === 0 ? `<li class="empty">add a pons trader to copy</li>` : state.targets.map(t => `
                <li class="row">
                  <div><strong>${t.label}</strong><a href="${EXPLORER}/address/${t.address}" target="_blank">${short(t.address)}</a></div>
                  <div class="row-actions">
                    <button class="btn ghost" data-toggle="${t.address}" data-enabled="${t.enabled}">${t.enabled ? "on" : "off"}</button>
                    <button class="btn ghost" data-drop="${t.address}">drop</button>
                  </div>
                </li>`).join("")}
            </ul>
          </section>
          <section class="panel">
            <h2>risk</h2>
            <form class="settings" id="risk">
              <label><span>dry run</span><input type="checkbox" name="dryRun" ${s.dryRun ? "checked" : ""} /></label>
              <label><span>copy mode</span><select name="copyMode"><option value="percent" ${s.copyMode==="percent"?"selected":""}>percent of leader</option><option value="fixed" ${s.copyMode==="fixed"?"selected":""}>fixed ETH</option></select></label>
              <label><span>copy %</span><input type="number" step="0.1" name="copyPercent" value="${s.copyPercent}" /></label>
              <label><span>fixed buy ETH</span><input type="number" step="0.001" name="fixedBuyEth" value="${s.fixedBuyEth}" /></label>
              <label><span>sell mode</span><select name="sellMode"><option value="mirror" ${s.sellMode==="mirror"?"selected":""}>mirror size</option><option value="all" ${s.sellMode==="all"?"selected":""}>flatten bag</option></select></label>
              <label><span>slippage bps</span><input type="number" name="slippageBps" value="${s.slippageBps}" /></label>
              <label><span>max buy ETH</span><input type="number" step="0.001" name="maxBuyEth" value="${s.maxBuyEth}" /></label>
              <label><span>max daily ETH</span><input type="number" step="0.01" name="maxDailyEth" value="${s.maxDailyEth}" /></label>
              <label><span>min leader ETH</span><input type="number" step="0.001" name="minLeaderTradeEth" value="${s.minLeaderTradeEth}" /></label>
              <label><span>min liquidity ETH</span><input type="number" step="0.01" name="minLiquidityEth" value="${s.minLiquidityEth}" /></label>
              <label><span>skip launch protection</span><input type="checkbox" name="skipLaunchProtection" ${s.skipLaunchProtection ? "checked" : ""} /></label>
              <button class="btn accent" type="submit">save risk</button>
            </form>
          </section>
          <section class="panel wide">
            <h2>positions</h2>
            <table><thead><tr><th>token</th><th>amount</th><th>cost</th><th>venue</th></tr></thead>
            <tbody>
              ${state.positions.length === 0 ? `<tr><td colspan="4" class="empty">no open bags</td></tr>` : state.positions.map(p => `
                <tr>
                  <td><a href="${PONS}/token/${p.token}" target="_blank">${p.symbol}</a><span class="dim"> ${short(p.token)}</span></td>
                  <td class="num">${fmtEth(p.amount, 2)}</td>
                  <td class="num">${fmtEth(p.costWei)} ETH</td>
                  <td>${p.venue}</td>
                </tr>`).join("")}
            </tbody></table>
          </section>
          <section class="panel wide">
            <h2>copy tape</h2>
            <table><thead><tr><th>side</th><th>token</th><th>leader</th><th>size</th><th>status</th><th>tx</th></tr></thead>
            <tbody>
              ${state.trades.length === 0 ? `<tr><td colspan="6" class="empty">waiting for a followed wallet to trade on pons</td></tr>` : state.trades.map(t => `
                <tr>
                  <td class="${t.side}">${t.side}</td>
                  <td><a href="${PONS}/token/${t.token}" target="_blank">${t.symbol}</a></td>
                  <td><a href="${EXPLORER}/address/${t.sourceWallet}" target="_blank">${short(t.sourceWallet)}</a></td>
                  <td class="num">${fmtEth(t.quoteAmountWei)} ETH</td>
                  <td><span class="pill ${t.status}">${t.status}</span>${t.reason ? `<span class="dim"> ${t.reason}</span>` : ""}</td>
                  <td><a href="${EXPLORER}/tx/${t.sourceTx}" target="_blank">src</a>${t.ourTx ? ` · <a href="${EXPLORER}/tx/${t.ourTx}" target="_blank">copy</a>` : ""}</td>
                </tr>`).join("")}
            </tbody></table>
          </section>
          <section class="panel">
            <h2>activity</h2>
            <ul class="tape">
              ${(state.activity||[]).map(item => `<li class="${item.level}"><time>${(item.at||"").slice(11,19)}</time>${item.message}</li>`).join("")}
            </ul>
          </section>
          <section class="panel">
            <h2>recent launches</h2>
            <ul class="list">
              ${state.launches.length === 0 ? `<li class="empty">launches appear as the watcher sees them</li>` : state.launches.map(l => `
                <li class="row"><div><strong>${l.symbol ?? "token"}</strong><a href="${PONS}/token/${l.token}" target="_blank">${short(l.token)}</a></div><span class="dim">v${l.version}</span></li>`).join("")}
            </ul>
          </section>
        </section>
        <footer>copies on-chain pons fills on robinhood chain. not an official pons or robinhood product. tokens can go to zero.</footer>
      `;
      document.getElementById("toggle").onclick = () => api(`/api/control/${s.running ? "stop" : "start"}`, { method: "POST" });
      document.getElementById("add-target").onsubmit = (e) => {
        e.preventDefault();
        const fd = new FormData(e.target);
        api("/api/targets", { method: "POST", body: JSON.stringify({ address: fd.get("address"), label: fd.get("label"), enabled: true }) });
      };
      document.getElementById("risk").onsubmit = (e) => {
        e.preventDefault();
        const fd = new FormData(e.target);
        const body = {
          dryRun: fd.get("dryRun") === "on",
          copyMode: fd.get("copyMode"),
          copyPercent: Number(fd.get("copyPercent")),
          fixedBuyEth: Number(fd.get("fixedBuyEth")),
          sellMode: fd.get("sellMode"),
          slippageBps: Number(fd.get("slippageBps")),
          maxBuyEth: Number(fd.get("maxBuyEth")),
          maxDailyEth: Number(fd.get("maxDailyEth")),
          minLeaderTradeEth: Number(fd.get("minLeaderTradeEth")),
          minLiquidityEth: Number(fd.get("minLiquidityEth")),
          skipLaunchProtection: fd.get("skipLaunchProtection") === "on",
        };
        api("/api/settings", { method: "PATCH", body: JSON.stringify(body) });
      };
      root.querySelectorAll("[data-toggle]").forEach((btn) => {
        btn.onclick = () => {
          const addr = btn.getAttribute("data-toggle");
          const t = state.targets.find(x => x.address === addr);
          api("/api/targets", { method: "POST", body: JSON.stringify({ ...t, enabled: !(btn.getAttribute("data-enabled") === "true") }) });
        };
      });
      root.querySelectorAll("[data-drop]").forEach((btn) => {
        btn.onclick = () => api(`/api/targets/${btn.getAttribute("data-drop")}`, { method: "DELETE" });
      });
    }

    function apply(msg) {
      if (msg.type === "snapshot") state = msg.state;
      else if (!state) return;
      else if (msg.type === "trade") {
        const rest = state.trades.filter(t => t.id !== msg.trade.id);
        state = { ...state, trades: [msg.trade, ...rest].slice(0, 80) };
      } else if (msg.type === "settings") state = { ...state, settings: msg.settings };
      else if (msg.type === "targets") state = { ...state, targets: msg.targets };
      else if (msg.message && msg.id) state = { ...state, activity: [msg, ...state.activity].slice(0, 80) };
      render();
    }

    const proto = location.protocol === "https:" ? "wss" : "ws";
    const socket = new WebSocket(`${proto}://${location.host}/ws`);
    socket.onmessage = (e) => apply(JSON.parse(e.data));
    socket.onerror = () => { if (!state) root.textContent = "live socket disconnected — is the bot running?"; };
    api("/api/snapshot").then((snap) => { state = snap; render(); });
    setInterval(() => api("/api/snapshot").then((snap) => { state = snap; render(); }), 12000);
  </script>
</body>
</html>
"""
