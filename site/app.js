/* Forecast Duel — static page. Reads data.json, renders one of three layouts. */
(function () {
  "use strict";
  const MODELS = ["kronos", "timestral", "naive"];
  const NAMES = { kronos: "Kronos", timestral: "Timestral", naive: "Naive guess" };
  const COLOR = { kronos: "var(--kronos)", timestral: "var(--timestral)", naive: "var(--naive)" };
  const $ = (s, r = document) => r.querySelector(s);
  const esc = (s) => String(s).replace(/[&<>"]/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;" }[c]));

  const store = {
    get(k) { try { return localStorage.getItem(k); } catch (e) { return null; } },
    set(k, v) { try { localStorage.setItem(k, v); } catch (e) {} },
  };

  let D = null;
  const S = {
    mode: null,
    variant: new URLSearchParams(location.search).get("v") || store.get("fd-variant") || "board",
    showPast: store.get("fd-past") !== "0",
    pick: store.get("fd-pick") || null,
    open: null,
  };

  /* ---------- formatting ---------- */
  function cur(a) { return a.kind === "crypto" ? "$" : "€"; }
  function px(v, a) {
    if (v == null || isNaN(v)) return "—";
    const d = Math.abs(v) >= 1000 ? 0 : Math.abs(v) >= 10 ? 2 : 3;
    return cur(a) + Number(v).toLocaleString("en-GB", { minimumFractionDigits: d, maximumFractionDigits: d });
  }
  function pct(v, d = 1) { return v == null || isNaN(v) ? "—" : Number(v).toFixed(d) + "%"; }
  function signed(v, a) {
    const s = v >= 0 ? "+" : "−";
    return s + px(Math.abs(v), a);
  }
  const MON = ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"];
  function day(d) { const [y, m, dd] = d.split("-"); return +dd + " " + MON[+m - 1]; }
  function dayLong(d) {
    const dt = new Date(d + "T12:00:00Z");
    return dt.toLocaleDateString("en-GB", { weekday: "short", day: "numeric", month: "short", timeZone: "UTC" });
  }

  /* ---------- data helpers ---------- */
  function hasData(mode) { return MODELS.some((m) => (D.leaderboard[mode][m] || {}).n > 0); }
  function firstLiveScoreDate() {
    let best = null;
    D.assets.forEach((a) => { const last = a.latest && a.latest.dates && a.latest.dates[4]; if (last && (!best || last < best)) best = last; });
    return best;
  }
  function leaderInAsset(a, mode) {
    const sc = a.scores[mode] || {};
    let best = null;
    MODELS.forEach((m) => { const s = sc[m]; if (s && s.n > 0 && s.mape_pct != null && (!best || s.mape_pct < sc[best].mape_pct)) best = m; });
    return best;
  }

  /* ---------- header + scoreboard ---------- */
  function renderStamp() {
    const g = new Date(D.generated_at);
    const ageH = (Date.now() - g.getTime()) / 36e5;
    const when = g.toLocaleString("en-GB", { day: "numeric", month: "short", year: "numeric", hour: "2-digit", minute: "2-digit", timeZone: "UTC" }) + " UTC";
    let s = "Last updated " + when + ". Next update tonight at 00:30 UTC.";
    if (ageH > 36) s = '<span class="stale">Last updated ' + when + ", " + Math.round(ageH / 24) + " days ago. The nightly job may be paused.</span>";
    $("#stamp").innerHTML = s;
  }

  function renderBoard() {
    document.querySelectorAll(".seg button").forEach((b) => b.setAttribute("aria-selected", String(b.dataset.mode === S.mode)));
    const lb = D.leaderboard[S.mode];
    const note = $("#board-note");
    if (S.mode === "live" && !hasData("live")) {
      const f = firstLiveScoreDate();
      note.textContent = "No live forecast has finished its 5 days yet. The first live scores arrive after the close of " + (f ? dayLong(f) : "the fifth trading day") + ". Until then, the warm-up shows how scoring will look.";
    } else if (S.mode === "warmup") {
      note.textContent = "Warm-up replays the 20 trading days before launch. The models may have seen these days in training, so treat it as a preview.";
    } else {
      note.textContent = "Forecasts made from launch night on, each one scored after its 5 days have passed.";
    }
    const maxMiss = Math.max(0.5, ...MODELS.map((m) => (lb[m] && lb[m].mape_pct) || 0));
    $("#board").innerHTML = MODELS.map((m) => {
      const s = lb[m] || {};
      const info = D.model_info[m] || {};
      const n = s.n || 0;
      const missW = s.mape_pct != null ? (s.mape_pct / maxMiss) * 100 : 0;
      const dir = m === "naive"
        ? '<div class="metric"><span class="k">Direction called right</span><span class="na">Never calls one</span></div>'
        : metric("Direction called right", s.direction_hit_pct, pct(s.direction_hit_pct, 0), s.direction_hit_pct, m, 50, "coin flip");
      const beat = m === "naive"
        ? '<div class="metric"><span class="k">Beat the naive guess</span><span class="na">This is the bar</span></div>'
        : metric("Beat the naive guess", s.beats_naive_pct, pct(s.beats_naive_pct, 0), s.beats_naive_pct, m, 50, "half the time");
      return '<article class="player">' +
        '<div class="who"><span class="sw" style="background:' + COLOR[m] + '"></span><span class="name">' + esc(NAMES[m]) + "</span></div>" +
        '<div class="meta">' + (m === "naive" ? "Says tomorrow equals today" : esc(info.label || "") + " · " + esc(info.by || "")) + " · " + n + " scored</div>" +
        metric("Average miss over 5 days", s.mape_pct, pct(s.mape_pct, 2), missW, m, null, null, "lower is better") +
        dir + beat + "</article>";
    }).join("");
    renderHeadline(lb);
  }
  function metric(label, raw, shown, width, m, ref, refLabel, hint) {
    const w = raw == null ? 0 : Math.max(0, Math.min(100, width));
    return '<div class="metric"><span class="k">' + label + (hint ? ' <span class="dim">· ' + hint + "</span>" : "") + '</span><span class="v">' + shown + "</span>" +
      '<div class="bar"><i style="width:' + w + "%;background:" + COLOR[m] + '"></i>' +
      (ref != null ? '<span class="ref" style="left:' + ref + '%" title="' + refLabel + '"></span>' : "") + "</div></div>";
  }
  function renderHeadline(lb) {
    let h = $("#headline");
    if (!h) { h = document.createElement("p"); h.id = "headline"; h.className = "headline"; $(".board-sec").appendChild(h); }
    const k = lb.kronos || {}, t = lb.timestral || {}, n = lb.naive || {};
    if (!(k.n && t.n && n.n)) { h.textContent = ""; return; }
    const rows = MODELS.map((m) => [m, lb[m].mape_pct]).sort((a, b) => a[1] - b[1]);
    const lead = rows[0][0];
    const where = S.mode === "warmup" ? "In the warm-up" : "So far";
    let s = where + ", " + NAMES[lead] + (lead === "naive" ? " is ahead" : " leads") + ": it misses by " + pct(rows[0][1], 2) + " on average, against " +
      pct(rows[1][1], 2) + " for " + NAMES[rows[1][0]] + " and " + pct(rows[2][1], 2) + " for " + NAMES[rows[2][0]] + ".";
    if (lead === "naive") s += " Doing nothing is still the forecast to beat.";
    h.textContent = s;
  }

  /* ---------- chart ---------- */
  // Returns {svg, bind(el)} for one asset.
  function chart(a, o) {
    const W = o.w, H = o.h, P = { l: 8, r: o.labels ? 92 : 14, t: 14, b: 26 };
    const hist = a.history.slice(-o.days);
    const histMap = new Map(a.history.map((r) => [r[0], r[1]]));
    const fut = (a.latest && a.latest.dates) || [];
    const dates = Array.from(new Set(hist.map((r) => r[0]).concat(fut))).sort();
    const ix = new Map(dates.map((d, i) => [d, i]));
    const first = dates[0];
    const past = S.showPast ? (a.past || []).filter((p) => p.made_on >= first && p.made_on !== (a.latest && a.latest.made_on)) : [];

    let vals = hist.map((r) => r[1]);
    MODELS.forEach((m) => { if (a.latest && a.latest[m]) vals = vals.concat(a.latest[m]); });
    if (a.latest && a.latest.timestral_q10) vals = vals.concat(a.latest.timestral_q10, a.latest.timestral_q90);
    past.forEach((p) => ["kronos", "timestral"].forEach((m) => p[m] && p[m].forEach((v, i) => { if (ix.has(p.dates[i])) vals.push(v); })));
    vals = vals.filter((v) => v != null && isFinite(v));
    let lo = Math.min(...vals), hi = Math.max(...vals);
    const pad = (hi - lo) * 0.08 || hi * 0.01;
    lo -= pad; hi += pad;
    const X = (i) => P.l + (i / Math.max(1, dates.length - 1)) * (W - P.l - P.r);
    const Y = (v) => P.t + (1 - (v - lo) / (hi - lo)) * (H - P.t - P.b);
    const pts = (arr) => arr.map((p) => X(p[0]).toFixed(1) + "," + Y(p[1]).toFixed(1)).join(" ");

    const made = a.latest && a.latest.made_on;
    const madeIx = ix.has(made) ? ix.get(made) : hist.length - 1;
    const lastClose = histMap.get(made) != null ? histMap.get(made) : a.last_close;
    let g = "";

    // grid: 3 recessive lines with price labels
    const ticks = niceTicks(lo, hi, 3);
    ticks.forEach((t) => {
      g += '<line x1="' + P.l + '" x2="' + (W - P.r) + '" y1="' + Y(t).toFixed(1) + '" y2="' + Y(t).toFixed(1) + '" stroke="var(--grid)" stroke-width="1"/>';
      g += '<text x="' + (P.l + 2) + '" y="' + (Y(t) - 5).toFixed(1) + '">' + esc(px(t, a)) + "</text>";
    });
    // forecast zone
    const zx = X(madeIx);
    g += '<rect x="' + zx.toFixed(1) + '" y="' + P.t + '" width="' + (W - P.r - zx).toFixed(1) + '" height="' + (H - P.t - P.b) + '" fill="var(--surface-2)" opacity=".55"/>';
    g += '<line x1="' + zx.toFixed(1) + '" x2="' + zx.toFixed(1) + '" y1="' + P.t + '" y2="' + (H - P.b) + '" stroke="var(--line)" stroke-dasharray="3 3"/>';
    // x labels
    g += '<text x="' + P.l + '" y="' + (H - 6) + '">' + day(first) + "</text>";
    g += '<text x="' + (zx - 6).toFixed(1) + '" y="' + (H - 6) + '" text-anchor="end">' + day(made) + "</text>";
    if (fut.length) g += '<text x="' + (zx + 6).toFixed(1) + '" y="' + (H - 6) + '" text-anchor="start">→ ' + day(fut[fut.length - 1]) + "</text>";

    // past forecasts, faint
    past.forEach((p) => {
      const start = histMap.get(p.made_on);
      ["kronos", "timestral"].forEach((m) => {
        if (!p[m] || start == null || !ix.has(p.made_on)) return;
        const arr = [[ix.get(p.made_on), start]];
        p[m].forEach((v, i) => { if (ix.has(p.dates[i])) arr.push([ix.get(p.dates[i]), v]); });
        g += '<polyline points="' + pts(arr) + '" fill="none" stroke="' + COLOR[m] + '" stroke-width="1" opacity="' + (p.live ? 0.45 : 0.28) + '"/>';
      });
    });

    // timestral band
    if (a.latest && a.latest.timestral_q10 && a.latest.timestral_q90) {
      const up = [[madeIx, lastClose]].concat(fut.map((d, i) => [ix.get(d), a.latest.timestral_q90[i]]));
      const dn = fut.map((d, i) => [ix.get(d), a.latest.timestral_q10[i]]).reverse();
      g += '<polygon points="' + pts(up.concat(dn)) + '" fill="var(--timestral)" opacity=".16"/>';
    }
    // real price
    g += '<polyline points="' + pts(hist.map((r) => [ix.get(r[0]), r[1]])) + '" fill="none" stroke="var(--ink)" stroke-width="2" stroke-linejoin="round"/>';
    // latest forecasts
    const ends = [];
    MODELS.slice().reverse().forEach((m) => {
      const v = a.latest && a.latest[m];
      if (!v) return;
      const arr = [[madeIx, lastClose]].concat(fut.map((d, i) => [ix.get(d), v[i]]));
      g += '<polyline points="' + pts(arr) + '" fill="none" stroke="' + COLOR[m] + '" stroke-width="2" stroke-linejoin="round"' + (m === "naive" ? ' stroke-dasharray="5 4"' : "") + "/>";
      ends.push({ m, y: Y(v[v.length - 1]), v: v[v.length - 1] });
    });
    g += '<circle cx="' + zx.toFixed(1) + '" cy="' + Y(lastClose).toFixed(1) + '" r="4" fill="var(--ink)" stroke="var(--surface)" stroke-width="2"/>';

    // direct labels, de-collided
    if (o.labels && fut.length) {
      ends.sort((p, q) => p.y - q.y);
      for (let i = 1; i < ends.length; i++) if (ends[i].y - ends[i - 1].y < 16) ends[i].y = ends[i - 1].y + 16;
      const ex = X(dates.length - 1) + 8;
      ends.forEach((e) => { g += '<text class="dl" x="' + ex.toFixed(1) + '" y="' + (e.y + 4).toFixed(1) + '" style="fill:' + COLOR[e.m] + '">' + (e.m === "naive" ? "Naive" : NAMES[e.m]) + "</text>"; });
    }
    // hover layer
    g += '<line class="xh" x1="0" x2="0" y1="' + P.t + '" y2="' + (H - P.b) + '" stroke="var(--ink-3)" stroke-width="1" visibility="hidden"/>';
    g += '<rect class="hit" x="' + P.l + '" y="0" width="' + (W - P.l - P.r) + '" height="' + H + '" fill="transparent"/>';

    const svg = '<svg class="chart" viewBox="0 0 ' + W + " " + H + '" role="img" aria-label="' + esc(a.name) + ': price for the last ' + hist.length + ' sessions and the 5-day forecasts">' + g + "</svg>";

    function bind(el) {
      const s = el.querySelector("svg"), hit = s.querySelector(".hit"), xh = s.querySelector(".xh"), tip = $("#tip");
      function move(ev) {
        const r = s.getBoundingClientRect();
        const x = ((ev.clientX - r.left) / r.width) * W;
        const i = Math.round(((x - P.l) / (W - P.l - P.r)) * (dates.length - 1));
        const ci = Math.max(0, Math.min(dates.length - 1, i));
        const d = dates[ci];
        xh.setAttribute("x1", X(ci)); xh.setAttribute("x2", X(ci)); xh.setAttribute("visibility", "visible");
        let rows = "";
        if (histMap.has(d) && d <= (hist[hist.length - 1] || [])[0]) rows += row("var(--ink)", "Real price", px(histMap.get(d), a));
        const fi = fut.indexOf(d);
        if (fi >= 0) MODELS.forEach((m) => { if (a.latest[m]) rows += row(COLOR[m], NAMES[m], px(a.latest[m][fi], a)); });
        if (fi >= 0 && a.latest.timestral_q10) rows += '<div class="r"><span>Timestral 80% range</span><span>' + px(a.latest.timestral_q10[fi], a) + "–" + px(a.latest.timestral_q90[fi], a) + "</span></div>";
        tip.innerHTML = '<div class="d">' + dayLong(d) + (fi >= 0 ? " · forecast" : "") + "</div>" + rows;
        tip.hidden = false;
        const tx = Math.min(window.innerWidth - tip.offsetWidth - 12, ev.clientX + 14);
        tip.style.left = tx + "px"; tip.style.top = (ev.clientY + 14) + "px";
      }
      function row(c, k, v) { return '<div class="r"><span><i style="background:' + c + '"></i>' + k + "</span><span>" + v + "</span></div>"; }
      hit.addEventListener("pointermove", move);
      hit.addEventListener("pointerleave", () => { xh.setAttribute("visibility", "hidden"); tip.hidden = true; });
    }
    return { svg, bind };
  }
  function niceTicks(lo, hi, n) {
    const span = hi - lo, step0 = span / n, mag = Math.pow(10, Math.floor(Math.log10(step0)));
    const step = [1, 2, 2.5, 5, 10].map((k) => k * mag).find((s) => s >= step0) || step0;
    const out = [];
    for (let v = Math.ceil(lo / step) * step; v <= hi; v += step) out.push(+v.toFixed(8));
    return out;
  }

  /* ---------- per-asset bits ---------- */
  function missLine(a) {
    const sc = a.scores[S.mode] || {};
    const lead = leaderInAsset(a, S.mode);
    if (!MODELS.some((m) => sc[m] && sc[m].n)) return '<div class="miss">No ' + (S.mode === "live" ? "live" : "warm-up") + " forecast scored yet for this asset.</div>";
    return '<div class="miss">' + MODELS.map((m) => {
      const s = sc[m] || {};
      return "<span><i class=\"sw\" style=\"background:" + COLOR[m] + '"></i>' + (m === "naive" ? "Naive" : NAMES[m]) + " misses <b>" + pct(s.mape_pct, 2) + "</b>" + (m === lead ? " · closest" : "") + "</span>";
    }).join("") + "</div>";
  }
  function callText(a, m) {
    const v = a.latest[m]; if (!v) return "";
    const last = a.last_close, end = v[v.length - 1], ch = ((end / last) - 1) * 100;
    if (m === "naive") return "No change";
    return (ch >= 0 ? "Up " : "Down ") + Math.abs(ch).toFixed(1) + "% by " + day(a.latest.dates[4]);
  }

  /* ---------- layouts ---------- */
  function renderBoardLayout(root) {
    root.innerHTML = '<div class="grid">' + D.assets.map((a, i) =>
      '<article class="card"><div class="card-head"><div><span class="t">' + esc(a.name) + '</span><span class="tk">' + esc(a.ticker) + "</span></div>" +
      '<span class="px">' + px(a.last_close, a) + ' <span class="dim">' + day(a.last_date) + "</span></span></div>" +
      '<div class="cw" data-i="' + i + '"></div>' + missLine(a) + "</article>").join("") + "</div>";
    root.querySelectorAll(".cw").forEach((el) => {
      const a = D.assets[+el.dataset.i]; const c = chart(a, { w: 560, h: 230, days: 45, labels: true });
      el.innerHTML = c.svg; c.bind(el);
    });
  }

  function renderStageLayout(root) {
    let a = D.assets.find((x) => x.ticker === S.pick) || D.assets[0];
    root.innerHTML = '<div class="stage"><ul class="picker">' + D.assets.map((x) => {
      const lead = leaderInAsset(x, S.mode);
      return '<li><button data-t="' + esc(x.ticker) + '" aria-pressed="' + (x === a) + '"><span class="pn">' + esc(x.name) + '</span><span class="pp">' + px(x.last_close, x) + "</span>" +
        '<span class="pw">' + (lead ? NAMES[lead] + " closest so far" : "Not scored yet") + "</span></button></li>";
    }).join("") + '</ul><div class="focus"></div></div>';
    root.querySelectorAll(".picker button").forEach((b) => b.addEventListener("click", () => { S.pick = b.dataset.t; store.set("fd-pick", S.pick); renderAssets(); }));
    const f = root.querySelector(".focus");
    f.innerHTML = '<div class="t">' + esc(a.name) + '</div><div class="sub">' + esc(a.ticker) + " · closed at " + px(a.last_close, a) + " on " + dayLong(a.last_date) + "</div>" +
      '<div class="calls">' + MODELS.map((m) => '<div class="call" style="border-color:' + COLOR[m] + '"><div class="k">' + NAMES[m] + " says</div>" +
        '<div class="v">' + px(a.latest[m] && a.latest[m][4], a) + '</div><div class="c">' + callText(a, m) + "</div></div>").join("") + "</div>" +
      '<div class="cw"></div>' + missLine(a);
    const c = chart(a, { w: 820, h: 340, days: 70, labels: true });
    const cw = f.querySelector(".cw"); cw.innerHTML = c.svg; c.bind(cw);
  }

  function renderLedgerLayout(root) {
    const rows = D.assets.map((a, i) => {
      const sc = a.scores[S.mode] || {}, lead = leaderInAsset(a, S.mode);
      const maxM = Math.max(0.01, ...MODELS.map((m) => (sc[m] && sc[m].mape_pct) || 0));
      const cells = MODELS.map((m) => {
        const s = sc[m] || {};
        const w = s.mape_pct != null ? Math.round((s.mape_pct / maxM) * 48) : 0;
        return '<td class="r' + (m === lead ? " best" : "") + '">' + pct(s.mape_pct, 2) + '<span class="missbar" style="width:' + w + "px;background:" + COLOR[m] + '"></span></td>';
      }).join("");
      const open = S.open === a.ticker;
      return '<tr class="row' + (open ? " open" : "") + '" data-t="' + esc(a.ticker) + '" tabindex="0" aria-expanded="' + open + '"><td><span class="nm">' + esc(a.name) + '</span><span class="tk">' + esc(a.ticker) + "</span></td>" +
        '<td class="r hide-s">' + px(a.last_close, a) + "</td>" +
        '<td class="spark" data-i="' + i + '"></td>' + cells +
        '<td class="hide-s">' + (lead ? NAMES[lead] : '<span class="dim">—</span>') + "</td></tr>" +
        (open ? '<tr class="detail"><td colspan="7"><div class="cw" data-i="' + i + '"></div></td></tr>' : "");
    }).join("");
    root.innerHTML = '<div class="tablewrap"><table class="ledger"><thead><tr><th>Asset</th><th class="r hide-s">Last close</th><th class="spark">Last 30 sessions + forecasts</th>' +
      MODELS.map((m) => '<th class="r">' + (m === "naive" ? "Naive" : NAMES[m]) + " miss</th>").join("") + '<th class="hide-s">Closest</th></tr></thead><tbody>' + rows + "</tbody></table></div>" +
      '<p class="dim small">Select a row to open its chart. Miss = average distance from the real close over the 5 days.</p>';
    root.querySelectorAll("td.spark[data-i]").forEach((el) => {
      const a = D.assets[+el.dataset.i]; const save = S.showPast; S.showPast = false;
      el.innerHTML = chart(a, { w: 180, h: 48, days: 30, labels: false }).svg.replace(/<text[^>]*>[^<]*<\/text>/g, "").replace(/<line class="xh"[^>]*\/>|<rect class="hit"[^>]*\/>/g, "");
      S.showPast = save;
    });
    root.querySelectorAll(".detail .cw").forEach((el) => {
      const a = D.assets[+el.dataset.i]; const c = chart(a, { w: 980, h: 300, days: 60, labels: true }); el.innerHTML = c.svg; c.bind(el);
    });
    root.querySelectorAll("tr.row").forEach((tr) => {
      const go = () => { S.open = S.open === tr.dataset.t ? null : tr.dataset.t; renderAssets(); };
      tr.addEventListener("click", go);
      tr.addEventListener("keydown", (e) => { if (e.key === "Enter" || e.key === " ") { e.preventDefault(); go(); } });
    });
  }

  function renderAssets() {
    const root = $("#assets");
    document.querySelectorAll(".review button").forEach((b) => b.setAttribute("aria-pressed", String(b.dataset.v === S.variant)));
    if (S.variant === "stage") renderStageLayout(root);
    else if (S.variant === "ledger") renderLedgerLayout(root);
    else renderBoardLayout(root);
  }

  function renderPlayers() {
    $("#players").innerHTML =
      "<dt>Kronos-base</dt><dd>102M parameters, by Tsinghua University (NeoQuasar). Trained only on market candles: over 12 billion of them from 45 exchanges. Sees open, high, low, close and volume.</dd>" +
      "<dt>Timestral-209M</dt><dd>209M parameters, by Mistral AI, released October 2026. A generalist trained on many kinds of time series. Sees the closing prices and gives a range as well as a number.</dd>" +
      "<dt>Naive guess</dt><dd>No model. Says every one of the next 5 closes equals the last one.</dd>";
  }

  function renderAll() { renderStamp(); renderBoard(); renderAssets(); }

  /* ---------- wire up ---------- */
  document.querySelectorAll(".seg button").forEach((b) => b.addEventListener("click", () => { S.mode = b.dataset.mode; renderBoard(); renderAssets(); }));
  document.querySelectorAll(".review button").forEach((b) => b.addEventListener("click", () => {
    S.variant = b.dataset.v; store.set("fd-variant", S.variant);
    const u = new URL(location.href); u.searchParams.set("v", S.variant); history.replaceState(null, "", u);
    renderAssets();
  }));
  const pastBox = $("#show-past");
  pastBox.checked = S.showPast;
  pastBox.addEventListener("change", () => { S.showPast = pastBox.checked; store.set("fd-past", S.showPast ? "1" : "0"); renderAssets(); });
  let rt; window.addEventListener("resize", () => { clearTimeout(rt); rt = setTimeout(renderAssets, 150); });

  fetch("data.json", { cache: "no-store" }).then((r) => r.json()).then((d) => {
    D = d;
    S.mode = hasData("live") ? "live" : (hasData("warmup") ? "warmup" : "live");
    renderPlayers();
    renderAll();
  }).catch((e) => {
    $("#stamp").textContent = "Could not load the forecast data (" + e.message + ").";
  });
})();
