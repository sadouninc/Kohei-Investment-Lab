(() => {
  const source = document.getElementById("phase-data");
  if (!source) return;
  const data = JSON.parse(source.textContent);
  const symbols = Object.fromEntries(data.symbols.map(item => [item.code, item]));
  const colors = ["#2563eb", "#dc2626", "#16a34a", "#9333ea", "#ea580c", "#0891b2",
    "#be123c", "#4f46e5", "#65a30d", "#c026d3"];
  const esc = value => String(value).replace(/[&<>"']/g, char =>
    ({"&":"&amp;","<":"&lt;",">":"&gt;",'"':"&quot;","'":"&#39;"}[char]));
  const table = (rows, columns) =>
    `<div class="table-scroll"><table><thead><tr>${columns.map(c => `<th>${c[0]}</th>`).join("")}</tr></thead>` +
    `<tbody>${rows.map(row => `<tr>${columns.map(c => `<td>${esc(c[1](row))}</td>`).join("")}</tr>`).join("")}</tbody></table></div>`;

  function renderChart() {
    const svg = document.getElementById("phase-chart");
    const period = Number(document.getElementById("phase-period").value);
    const group = document.getElementById("phase-group").value;
    const selected = data.symbols.filter(item => group === "all" || item.group === group);
    const series = selected.map(item => {
      const points = Object.entries(data.normalized[item.code]).slice(-period);
      if (!points.length) return null;
      const base = points[0][1];
      return {item, points: points.map(([day, value]) => [day, value / base * 100])};
    }).filter(Boolean);
    const values = series.flatMap(row => row.points.map(point => point[1]));
    const min = Math.min(...values, 90), max = Math.max(...values, 110);
    const x = (index, length) => 45 + index / Math.max(1, length - 1) * 920;
    const y = value => 425 - (value - min) / Math.max(1, max - min) * 380;
    let content = `<line x1="45" y1="${y(100)}" x2="965" y2="${y(100)}" class="chart-baseline"/>`;
    series.forEach((row, index) => {
      const points = row.points.map((point, i) => `${x(i, row.points.length)},${y(point[1])}`).join(" ");
      content += `<polyline points="${points}" fill="none" stroke="${colors[index % colors.length]}" stroke-width="2" opacity="${series.length > 20 ? .45 : .8}"><title>${esc(row.item.name)}</title></polyline>`;
    });
    content += `<text x="8" y="${y(max) + 5}">${max.toFixed(0)}</text><text x="8" y="${y(min) + 5}">${min.toFixed(0)}</text>`;
    svg.innerHTML = content;
    document.getElementById("phase-legend").innerHTML = series.map((row, index) =>
      `<span><i style="background:${colors[index % colors.length]}"></i>${esc(row.item.code)} ${esc(row.item.name)}</span>`).join("");
  }

  function renderHeatmap() {
    const codes = data.symbols.map(item => item.code);
    let html = `<table><thead><tr><th></th>${codes.map(code => `<th title="${esc(symbols[code].name)}">${code}</th>`).join("")}</tr></thead><tbody>`;
    codes.forEach(left => {
      html += `<tr><th>${left}</th>`;
      codes.forEach(right => {
        const value = data.correlation.pearson[left][right];
        const hue = value == null ? 0 : value >= 0 ? 210 : 4;
        const alpha = value == null ? .05 : .12 + Math.abs(value) * .72;
        html += `<td style="background:hsla(${hue},75%,50%,${alpha})" title="${left} × ${right}: ${value == null ? "—" : value.toFixed(2)}">${value == null ? "—" : value.toFixed(1)}</td>`;
      });
      html += "</tr>";
    });
    document.getElementById("phase-heatmap").innerHTML = html + "</tbody></table>";
  }

  const grouped = {};
  data.symbols.forEach(item => (grouped[item.cluster] ||= []).push(item));
  document.getElementById("phase-clusters").innerHTML = Object.entries(grouped).map(([id, items]) =>
    `<section><h3>Cluster ${id}</h3><ul>${items.map(item => `<li>${item.code} ${esc(item.name)}<small>${esc(item.group)}</small></li>`).join("")}</ul></section>`).join("");
  document.getElementById("phase-cluster-periods").innerHTML = table(data.symbols, [
    ["コード", row => row.code], ["銘柄", row => row.name],
    ["3か月", row => `Cluster ${data.clusters_by_period["3m"][row.code]}`],
    ["6か月", row => `Cluster ${data.clusters_by_period["6m"][row.code]}`],
    ["1年", row => `Cluster ${data.clusters_by_period["1y"][row.code]}`],
  ]);
  const pairColumns = [["銘柄ペア", row => `${row.left} × ${row.right}`], ["相関", row => row.correlation.toFixed(3)]];
  document.getElementById("phase-positive").innerHTML = table(data.top_positive_pairs, pairColumns);
  document.getElementById("phase-negative").innerHTML = table(data.top_negative_pairs, pairColumns);
  document.getElementById("phase-lead-lag").innerHTML = table(data.lead_lag.slice(0, 20), [
    ["先行候補", row => row.leader || "同日"], ["追随候補", row => row.follower || "同日"],
    ["ラグ", row => `${row.lag}日`], ["相関", row => row.correlation.toFixed(3)],
    ["共通標本", row => row.samples],
  ]);
  document.getElementById("phase-period").addEventListener("change", renderChart);
  document.getElementById("phase-group").addEventListener("change", renderChart);
  renderChart();
  renderHeatmap();
})();
