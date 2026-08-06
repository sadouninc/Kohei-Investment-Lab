(() => {
  "use strict";
  const dataNode = document.getElementById("trade-analysis-data");
  if (!dataNode) return;
  const payload = JSON.parse(dataNode.textContent);
  const allTrades = payload.trades || [];
  let groupMode = "month";
  let sort = { key: "close_date", direction: -1 };
  const yen = new Intl.NumberFormat("ja-JP", {
    style: "currency", currency: "JPY", maximumFractionDigits: 0
  });
  const number = new Intl.NumberFormat("ja-JP", { maximumFractionDigits: 2 });
  const pct = value => value == null ? "―" : `${(value * 100).toFixed(1)}%`;
  const money = value => value == null ? "―" : yen.format(value);
  const escapeHtml = value => String(value ?? "").replace(/[&<>"']/g, c => ({
    "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;"
  }[c]));

  const controls = {
    year: document.getElementById("ta-year"),
    month: document.getElementById("ta-month"),
    symbol: document.getElementById("ta-symbol"),
    theme: document.getElementById("ta-theme"),
    account: document.getElementById("ta-account"),
    side: document.getElementById("ta-side"),
    result: document.getElementById("ta-result"),
    holding: document.getElementById("ta-holding")
  };
  const unique = (key, formatter = value => value) =>
    [...new Set(allTrades.map(formatter).filter(Boolean))].sort((a, b) =>
      String(a).localeCompare(String(b), "ja", { numeric: true }));
  const addOptions = (select, values) => values.forEach(value => {
    const option = document.createElement("option");
    option.value = value;
    option.textContent = value;
    select.append(option);
  });
  addOptions(controls.year, unique("close_date", t => t.close_date?.slice(0, 4)));
  addOptions(controls.month, unique("close_date", t => t.close_date?.slice(0, 7)));
  addOptions(controls.symbol, unique("security_code",
    t => `${t.security_code} ${t.security_name}`));
  addOptions(controls.theme, unique("primary_theme", t => t.primary_theme));
  addOptions(controls.account, unique("account_type", t => t.account_type));
  addOptions(controls.side, unique("position_side", t => t.position_side));

  function holdingMatch(days, bucket) {
    if (!bucket) return true;
    if (bucket === "0") return days === 0;
    if (bucket === "1-5") return days >= 1 && days <= 5;
    if (bucket === "6-20") return days >= 6 && days <= 20;
    if (bucket === "21-60") return days >= 21 && days <= 60;
    return days >= 61;
  }
  function filteredTrades() {
    return allTrades.filter(t => {
      const result = t.net_pnl > 0 ? "win" : t.net_pnl < 0 ? "loss" : "flat";
      return (!controls.year.value || t.close_date?.startsWith(controls.year.value))
        && (!controls.month.value || t.close_date?.startsWith(controls.month.value))
        && (!controls.symbol.value ||
            `${t.security_code} ${t.security_name}` === controls.symbol.value)
        && (!controls.theme.value || t.primary_theme === controls.theme.value)
        && (!controls.account.value || t.account_type === controls.account.value)
        && (!controls.side.value || t.position_side === controls.side.value)
        && (!controls.result.value || result === controls.result.value)
        && holdingMatch(Number(t.holding_days), controls.holding.value);
    });
  }
  function metrics(rows) {
    const wins = rows.filter(t => t.net_pnl > 0);
    const losses = rows.filter(t => t.net_pnl < 0);
    const total = rows.reduce((sum, t) => sum + Number(t.net_pnl || 0), 0);
    const grossProfit = wins.reduce((sum, t) => sum + t.net_pnl, 0);
    const grossLoss = -losses.reduce((sum, t) => sum + t.net_pnl, 0);
    const avgWin = wins.length ? grossProfit / wins.length : 0;
    const avgLoss = losses.length ? grossLoss / losses.length : 0;
    return {
      trade_count: rows.length, net_pnl: total, gross_profit: grossProfit,
      gross_loss: grossLoss, win_rate: rows.length ? wins.length / rows.length : 0,
      profit_factor: grossLoss ? grossProfit / grossLoss : null,
      payoff_ratio: avgLoss ? avgWin / avgLoss : null,
      average_holding_days: rows.length
        ? rows.reduce((sum, t) => sum + Number(t.holding_days || 0), 0) / rows.length : 0,
      max_win: wins.length ? Math.max(...wins.map(t => t.net_pnl)) : 0,
      max_loss: losses.length ? Math.min(...losses.map(t => t.net_pnl)) : 0
    };
  }
  function renderSummary(rows) {
    const m = metrics(rows);
    const cards = [
      ["取引件数", `${number.format(m.trade_count)}件`],
      ["実現損益", money(m.net_pnl)],
      ["総利益", money(m.gross_profit)],
      ["総損失", money(m.gross_loss)],
      ["勝率", pct(m.win_rate)],
      ["PF", m.profit_factor == null ? "―" : m.profit_factor.toFixed(2)],
      ["ペイオフレシオ", m.payoff_ratio == null ? "―" : m.payoff_ratio.toFixed(2)],
      ["平均保有期間", `${m.average_holding_days.toFixed(1)}日`],
      ["最大利益", money(m.max_win)],
      ["最大損失", money(m.max_loss)]
    ];
    document.getElementById("ta-summary").innerHTML = cards.map(([label, value]) =>
      `<div class="metric-card"><span>${label}</span><strong>${value}</strong></div>`
    ).join("");
    document.getElementById("ta-filter-summary").textContent =
      `${payload.period.start} ～ ${payload.period.end} / ${number.format(rows.length)}件を表示`;
  }
  function renderEquity(rows) {
    const ordered = [...rows].sort((a, b) =>
      a.close_date.localeCompare(b.close_date) || a.id - b.id);
    let cumulative = 0;
    const points = ordered.map(t => ({ date: t.close_date,
      value: cumulative += Number(t.net_pnl || 0) }));
    const node = document.getElementById("ta-equity");
    if (!points.length) { node.textContent = "該当する取引はありません。"; return; }
    const w = 900, h = 280, p = 28;
    const values = points.map(x => x.value);
    const low = Math.min(0, ...values), high = Math.max(0, ...values);
    const span = high - low || 1;
    const coords = points.map((x, i) => {
      const px = p + i / Math.max(points.length - 1, 1) * (w - p * 2);
      const py = p + (high - x.value) / span * (h - p * 2);
      return `${px.toFixed(1)},${py.toFixed(1)}`;
    }).join(" ");
    node.innerHTML = `<svg viewBox="0 0 ${w} ${h}" aria-hidden="true">
      <polyline points="${coords}"></polyline></svg>
      <div><span>${escapeHtml(points[0].date)}</span>
      <strong>${money(points.at(-1).value)}</strong>
      <span>${escapeHtml(points.at(-1).date)}</span></div>`;
  }
  function groupLabel(t) {
    if (groupMode === "month") return t.close_date.slice(0, 7);
    if (groupMode === "security") return `${t.security_code} ${t.security_name}`;
    if (groupMode === "account") return t.account_type;
    if (groupMode === "side") return t.position_side;
    if (groupMode === "theme") return t.primary_theme;
    if (groupMode === "weekday")
      return ["日", "月", "火", "水", "木", "金", "土"][new Date(`${t.open_date}T00:00:00`).getDay()];
    const d = Number(t.holding_days);
    return d === 0 ? "当日" : d === 1 ? "1日" : d <= 5 ? "2～5日"
      : d <= 10 ? "6～10日" : d <= 20 ? "11～20日"
      : d <= 60 ? "21～60日" : d <= 120 ? "61～120日" : "121日以上";
  }
  function renderGroups(rows) {
    const groups = new Map();
    rows.forEach(t => {
      const label = groupLabel(t);
      if (!groups.has(label)) groups.set(label, []);
      groups.get(label).push(t);
    });
    let entries = [...groups].map(([label, trades]) => ({ label, ...metrics(trades) }));
    if (groupMode === "weekday") {
      const order = ["月", "火", "水", "木", "金", "土", "日"];
      entries.sort((a, b) => order.indexOf(a.label) - order.indexOf(b.label));
    } else entries.sort((a, b) => b.net_pnl - a.net_pnl);
    document.getElementById("ta-group-table").innerHTML =
      `<table class="sortable-table"><thead><tr><th>区分</th><th>件数</th>
      <th>実現損益</th><th>勝率</th><th>PF</th><th>平均保有</th></tr></thead><tbody>`
      + entries.map(x => `<tr><td>${escapeHtml(x.label)}</td><td>${number.format(x.trade_count)}</td>
      <td class="${x.net_pnl < 0 ? "loss" : "gain"}">${money(x.net_pnl)}</td>
      <td>${pct(x.win_rate)}</td><td>${x.profit_factor == null ? "―" : x.profit_factor.toFixed(2)}</td>
      <td>${x.average_holding_days.toFixed(1)}日</td></tr>`).join("") + "</tbody></table>";
  }
  function renderTrades(rows) {
    const ordered = [...rows].sort((a, b) => {
      const av = a[sort.key], bv = b[sort.key];
      return (typeof av === "number" ? av - bv :
        String(av ?? "").localeCompare(String(bv ?? ""), "ja", { numeric: true })) * sort.direction;
    });
    const columns = [
      ["close_date", "決済日"], ["security_code", "コード"], ["security_name", "銘柄"],
      ["account_type", "区分"], ["position_side", "方向"], ["quantity", "数量"],
      ["average_open_price", "取得価格"], ["average_close_price", "決済価格"],
      ["net_pnl", "実現損益"], ["return_rate", "利益率"], ["holding_days", "保有日数"]
    ];
    document.getElementById("ta-trades").innerHTML =
      `<table class="sortable-table"><thead><tr>${columns.map(([key, label]) =>
        `<th><button type="button" data-sort="${key}">${label}</button></th>`).join("")}</tr></thead><tbody>`
      + ordered.map(t => `<tr><td>${t.close_date}</td><td>${escapeHtml(t.security_code)}</td>
      <td>${escapeHtml(t.security_name)}</td><td>${escapeHtml(t.account_type)}</td>
      <td>${escapeHtml(t.position_side)}</td><td>${number.format(t.quantity)}</td>
      <td>${money(t.average_open_price)}</td><td>${money(t.average_close_price)}</td>
      <td class="${t.net_pnl < 0 ? "loss" : "gain"}">${money(t.net_pnl)}</td>
      <td>${pct(t.return_rate)}</td><td>${number.format(t.holding_days)}日</td></tr>`).join("")
      + "</tbody></table>";
    document.querySelectorAll("[data-sort]").forEach(button =>
      button.addEventListener("click", () => {
        const key = button.dataset.sort;
        sort = { key, direction: sort.key === key ? -sort.direction : -1 };
        renderTrades(filteredTrades());
      }));
  }
  function renderQuality() {
    const q = payload.data_quality || {};
    document.getElementById("ta-quality").innerHTML = `<dl class="quality-grid">
      <div><dt>対象期間</dt><dd>${payload.period.start} ～ ${payload.period.end}</dd></div>
      <div><dt>最終更新</dt><dd>${payload.updated_date}</dd></div>
      <div><dt>元レコード</dt><dd>${number.format(q.source_record_count ?? 0)}件</dd></div>
      <div><dt>決済済み</dt><dd>${number.format(q.closed_episode_count ?? 0)}件</dd></div>
      <div><dt>未決済</dt><dd>${number.format(q.open_episode_count ?? 0)}件</dd></div>
      <div><dt>対応不能</dt><dd>${number.format(q.unmatched_execution_count ?? 0)}件</dd></div>
      <div><dt>対応付け</dt><dd>${escapeHtml(q.matching_method)}</dd></div>
      <div><dt>1取引の定義</dt><dd>${escapeHtml(q.trade_unit)}</dd></div></dl>`;
  }
  function render() {
    const rows = filteredTrades();
    renderSummary(rows); renderEquity(rows); renderGroups(rows); renderTrades(rows);
  }
  Object.values(controls).forEach(control => control.addEventListener("change", render));
  document.getElementById("ta-reset").addEventListener("click", () => {
    Object.values(controls).forEach(control => { control.value = ""; }); render();
  });
  document.querySelectorAll("[data-group]").forEach(button =>
    button.addEventListener("click", () => {
      groupMode = button.dataset.group;
      document.querySelectorAll("[data-group]").forEach(x =>
        x.classList.toggle("active", x === button));
      renderGroups(filteredTrades());
    }));
  renderQuality();
  render();
})();
