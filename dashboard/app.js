const fallbackPath = "./data/sample.json";
const dailyPath = "./data/daily.json";
const refreshStatusPath = "./data/refresh-status.json";
const autoRefreshIntervalMs = 60 * 1000;
const scheduledSnapshotText = "云端约 11:30/15:30/21:00 更新";

let dashboardData = null;
let refreshStatusData = null;
let activeLimitFilter = "all";
let activeReportId = "";
let activeSheet = "overview";
let autoRefreshTimer = null;
let lastDataStamp = "";

const money = new Intl.NumberFormat("zh-CN", {
  maximumFractionDigits: 1,
});

document.addEventListener("DOMContentLoaded", () => {
  bindEvents();
  updateRuntimeMode();
  loadDashboard().then(startAutoRefresh);
});

function bindEvents() {
  document.getElementById("refreshBtn").addEventListener("click", () => refreshMarketData("manual"));
  document.getElementById("scoreForm")?.addEventListener("submit", handleScoreSubmit);
  document.getElementById("sheetTabs")?.addEventListener("click", (event) => {
    const button = event.target.closest("[data-sheet-target]");
    if (!button) return;
    setActiveSheet(button.dataset.sheetTarget);
  });
  document.querySelectorAll("[data-limit-filter]").forEach((button) => {
    button.addEventListener("click", () => {
      activeLimitFilter = button.dataset.limitFilter;
      document
        .querySelectorAll("[data-limit-filter]")
        .forEach((item) => item.classList.toggle("active", item === button));
      renderLimitUps();
    });
  });
  document.getElementById("reportTabs")?.addEventListener("click", (event) => {
    const button = event.target.closest("[data-report-id]");
    if (!button) return;
    activeReportId = button.dataset.reportId;
    renderReports();
  });
  setActiveSheet(activeSheet);
}

function setActiveSheet(sheet) {
  activeSheet = sheet || "overview";
  document.querySelectorAll("[data-sheet-target]").forEach((button) => {
    button.classList.toggle("active", button.dataset.sheetTarget === activeSheet);
  });
  document.querySelectorAll("[data-sheet]").forEach((section) => {
    section.hidden = section.dataset.sheet !== activeSheet;
  });
}

async function handleScoreSubmit(event) {
  event.preventDefault();
  const form = event.currentTarget;
  const code = document.getElementById("scoreCode").value.trim();
  const mode = document.getElementById("scoreMode").value;
  const target = document.getElementById("scoreResult");
  const button = form.querySelector("button");
  if (!code) {
    target.innerHTML = `<div class="risk-item">请先输入 6 位股票代码。</div>`;
    return;
  }

  button.disabled = true;
  button.textContent = "计算中";
  target.innerHTML = `<div class="risk-item">正在读取行情和 K 线，请稍等。</div>`;
  try {
    const useLocalApi = isLocalRuntime() && !new URLSearchParams(window.location.search).has("publicScore");
    const result = useLocalApi
      ? await fetchJson(`/api/score?code=${encodeURIComponent(code)}&mode=${encodeURIComponent(mode)}`)
      : await window.PublicStockCalculator.score(code, mode);
    if (!result.ok) {
      throw new Error(result.error || result.stderr || "计算失败");
    }
    renderScoreResult(result);
  } catch (error) {
    target.innerHTML = `
      <div class="risk-item">
        实时计算不可用：${escapeHtml(error.message || "未知错误")}。请稍后重试，或改用 6 位股票代码查询。
      </div>
    `;
  } finally {
    button.disabled = false;
    button.textContent = "计算";
  }
}

async function loadDashboard(options = {}) {
  const previousStamp = dataStamp(dashboardData);
  if (!options.silent) {
    updateRefreshStatus("更新中");
  }
  try {
    dashboardData = await fetchJson(dailyPath);
    if (!isUsableData(dashboardData)) {
      throw new Error("daily.json has no market data");
    }
  } catch {
    dashboardData = await fetchJson(fallbackPath);
  }
  refreshStatusData = await loadRefreshStatus();
  renderDashboard();
  const nextStamp = dataStamp(dashboardData);
  lastDataStamp = nextStamp;
  updateRefreshStatus(previousStamp && previousStamp !== nextStamp ? "已更新" : "已同步");
}

async function refreshMarketData(reason = "manual") {
  const button = document.getElementById("refreshBtn");
  button.disabled = true;
  button.textContent = isLocalRuntime() ? "抓取中" : "同步中";
  try {
    if (isLocalRuntime()) {
      await fetchJson("/api/refresh");
    }
    await loadDashboard({ reason });
  } catch {
    updateRefreshStatus("刷新失败");
  } finally {
    button.disabled = false;
    button.textContent = "刷新";
  }
}

function updateRuntimeMode() {
  const local = isLocalRuntime();
  const hint = document.getElementById("scoreModeHint");
  const notice = document.getElementById("runtimeNotice");
  const form = document.getElementById("scoreForm");
  if (hint) {
    hint.textContent = local ? "本地服务实时计算" : "公网浏览器实时计算";
  }
  if (notice) {
    notice.textContent = local
      ? "本地服务版支持实时刷新和个股打分；公网发布版展示最近一次自动生成快照。"
      : "公网版展示自动复盘快照，并可在浏览器中使用实时个股打分。";
  }
}

function isLocalRuntime() {
  return ["localhost", "127.0.0.1", "::1"].includes(window.location.hostname);
}

function startAutoRefresh() {
  if (autoRefreshTimer) return;
  autoRefreshTimer = window.setInterval(() => {
    loadDashboard({ silent: true, reason: "auto" }).catch(() => updateRefreshStatus("刷新失败"));
  }, autoRefreshIntervalMs);
  document.addEventListener("visibilitychange", () => {
    if (!document.hidden) {
      loadDashboard({ silent: true, reason: "visible" }).catch(() => updateRefreshStatus("刷新失败"));
    }
  });
}

function dataStamp(data) {
  return [data?.meta?.tradeDate, data?.meta?.phase, data?.meta?.generatedAt].filter(Boolean).join("|");
}

function updateRefreshStatus(state) {
  const target = document.getElementById("refreshStatus");
  if (!target) return;
  const nextCheck = new Date(Date.now() + autoRefreshIntervalMs).toLocaleTimeString("zh-CN", {
    hour12: false,
  });
  const cloudStatus = formatCloudStatus();
  target.textContent = `${state} · 页面检查 ${nextCheck} · ${cloudStatus}`;
}

async function loadRefreshStatus() {
  try {
    return await fetchJson(refreshStatusPath);
  } catch {
    return null;
  }
}

function formatCloudStatus() {
  if (!refreshStatusData?.lastAttemptAt) {
    return scheduledSnapshotText;
  }
  const result = refreshStatusData.success === false ? "失败" : "成功";
  return `云端尝试 ${refreshStatusData.lastAttemptAt} ${result}`;
}

function isUsableData(data) {
  return Boolean(
    data?.indices?.length ||
      data?.limitUps?.length ||
      data?.flows?.industries?.length ||
      data?.flows?.concepts?.length,
  );
}

async function fetchJson(path) {
  return new Promise((resolve, reject) => {
    const request = new XMLHttpRequest();
    request.open("GET", `${path}?t=${Date.now()}`, true);
    request.onreadystatechange = () => {
      if (request.readyState !== 4) return;
      if (request.status < 200 || request.status >= 300) {
        reject(new Error(`Cannot load ${path}`));
        return;
      }
      try {
        resolve(JSON.parse(request.responseText));
      } catch (error) {
        reject(error);
      }
    };
    request.send();
  });
}

function renderDashboard() {
  document.getElementById("tradeDate").textContent = dashboardData.meta.tradeDate;
  document.getElementById("marketPhase").textContent = dashboardData.meta.phase;
  document.getElementById("generatedAt").textContent = dashboardData.meta.generatedAt
    ? `生成 ${dashboardData.meta.generatedAt}`
    : "静态数据";
  renderIndices();
  renderReports();
  renderExecutionPlan();
  renderNewsBrief();
  renderCandidatePools();
  renderEmotion();
  renderTemperature();
  renderDiscipline();
  renderLimitUps();
  renderLadder();
  renderFlow("industryFlow", dashboardData.flows.industries);
  renderFlow("conceptFlow", dashboardData.flows.concepts);
  renderAgainstMarket();
  renderFocusBoards();
  renderTrendCharts();
  renderRisks();
  renderLimitDowns();
  renderWatchPlan();
}

function renderExecutionPlan() {
  const target = document.getElementById("executionPlan");
  if (!target) return;
  const plan = dashboardData.executionPlan;
  if (!plan?.items?.length) {
    target.innerHTML = `<div class="risk-item">暂无明日执行表，等待候选池和技术评分生成。</div>`;
    return;
  }
  target.innerHTML = `
    <div class="execution-summary">
      <div>
        <strong>${escapeHtml(plan.stance || "--")}</strong>
        <span>市场温度 ${escapeHtml(plan.marketLevel || "--")} · 情绪分 ${plan.emotionScore ?? "--"} · 总仓 ${escapeHtml(plan.totalPosition || "--")} · 单票 ${escapeHtml(plan.singlePosition || "--")}</span>
      </div>
      <div class="tag-row">${renderTags((plan.focusThemes || []).filter(Boolean))}</div>
    </div>
    <div class="execution-grid">
      <article class="execution-rules">
        <strong>禁止交易条件</strong>
        <ul>${(plan.bans || []).map((item) => `<li>${escapeHtml(item)}</li>`).join("")}</ul>
      </article>
      <article class="execution-rules">
        <strong>执行纪律</strong>
        <ul>${(plan.rules || []).map((item) => `<li><b>${escapeHtml(item.title)}</b>：${escapeHtml(item.rule)}</li>`).join("")}</ul>
      </article>
    </div>
    <div class="execution-items">
      ${(plan.items || []).map(renderExecutionItem).join("")}
    </div>
  `;
}

function renderExecutionItem(item) {
  const vetoHtml = item.vetoes?.length ? `<div class="execution-veto">${item.vetoes.map((veto) => `<span>${escapeHtml(veto)}</span>`).join("")}</div>` : "";
  return `
    <article class="execution-item">
      <div class="execution-item-head">
        <div>
          <strong>${item.rank}. ${escapeHtml(item.name)}</strong>
          <span>${escapeHtml(item.code)} · ${escapeHtml(item.pool)} · ${escapeHtml(item.theme)}</span>
        </div>
        <b>${escapeHtml(item.watchLevel || "--")}</b>
      </div>
      <div class="execution-meta">
        <span>综合 ${item.score ?? "--"}</span>
        <span>技术 ${item.technicalScore ?? "--"}</span>
        <span>仓位 ${escapeHtml(item.position || "--")}</span>
        <span>${escapeHtml(item.timeWindow || "--")}</span>
      </div>
      <p><b>动作：</b>${escapeHtml(item.action || "--")}</p>
      <p><b>触发：</b>${escapeHtml(item.entry || "--")}</p>
      <p><b>止损：</b>${escapeHtml(item.stop || "--")}</p>
      <ul>${(item.conditions || []).map((condition) => `<li>${escapeHtml(condition)}</li>`).join("")}</ul>
      ${vetoHtml}
    </article>
  `;
}

function renderNewsBrief() {
  const target = document.getElementById("newsBrief");
  if (!target) return;
  const brief = dashboardData.newsBrief;
  if (!brief?.items?.length) {
    target.innerHTML = `<div class="risk-item">暂无可用新闻数据，本次看板仅基于行情和资金生成。</div>`;
    return;
  }
  target.innerHTML = `
    <div class="news-summary">
      <div>
        <strong>${escapeHtml(brief.summary || "--")}</strong>
        <span>${escapeHtml(brief.generatedAt || "--")} · ${escapeHtml(brief.source || "--")}</span>
      </div>
      <div class="tag-row">${renderTags((brief.themes || []).slice(0, 6).map((item) => item.name))}</div>
    </div>
    ${brief.errors?.length ? `<div class="risk-item">部分新闻源失败：${brief.errors.map(escapeHtml).join("；")}</div>` : ""}
    <div class="news-grid">
      ${(brief.items || []).map(renderNewsItem).join("")}
    </div>
  `;
}

function renderNewsItem(item) {
  const url = item.url ? `<a href="${escapeHtml(item.url)}" target="_blank" rel="noreferrer">来源</a>` : "";
  return `
    <article class="news-item">
      <div class="news-head">
        <strong>${escapeHtml(item.title || "--")}</strong>
        <span class="${item.impact === "风险" ? "down" : item.impact === "催化" ? "up" : "flat"}">${escapeHtml(item.impact || "--")}</span>
      </div>
      <p>${escapeHtml(item.summary || "--")}</p>
      <div class="news-meta">
        <span>${escapeHtml(item.source || "--")}</span>
        <span>${escapeHtml(item.publishedAt || "--")}</span>
        <span>${escapeHtml(item.credibility || "--")}</span>
        ${url}
      </div>
      <div class="tag-row">${renderTags(item.themes || [])}</div>
    </article>
  `;
}

function renderCandidatePools() {
  const target = document.getElementById("candidatePools");
  if (!target) return;
  const candidatePools = dashboardData.candidatePools;
  const pools = candidatePools?.pools || [];
  if (!pools.length) {
    target.innerHTML = `<div class="risk-item">暂无候选股票池，等待盘后数据生成。</div>`;
    return;
  }
  const coverage = candidatePools.technicalCoverage || {};
  target.innerHTML = `
    <div class="candidate-coverage">
      <span>股票池 ${coverage.universe ?? "--"}</span>
      <span>成功评分 ${coverage.scored ?? "--"}</span>
      <span>大于60分 ${coverage.qualified ?? "--"}</span>
      <span>失败 ${coverage.failed ?? "--"}</span>
      <span>${escapeHtml(candidatePools.generatedAt || "--")}</span>
    </div>
    <div class="candidate-pool-grid">
      ${pools
    .map(
      (pool) => `
        <article class="candidate-pool">
          <div class="candidate-pool-head">
            <div>
              <strong>${pool.title}</strong>
              <span>${pool.description}</span>
            </div>
            <b>${pool.items?.length || 0}</b>
          </div>
          <div class="candidate-list">
            ${(pool.items || []).map(renderCandidateItem).join("") || `<div class="risk-item">暂无入池标的</div>`}
          </div>
        </article>
      `,
    )
    .join("")}
    </div>
  `;
}

function renderCandidateItem(item) {
  const technical = item.technical || {};
  return `
    <div class="candidate-item">
      <div class="candidate-main">
        <div>
          <strong>${escapeHtml(item.name)}</strong>
          <span>${escapeHtml(item.code)} · ${escapeHtml(item.theme)} · ${escapeHtml(item.setup)}</span>
        </div>
        <b>${item.score}</b>
      </div>
      <div class="tag-row">${renderTags(item.labels || [])}</div>
      <div class="candidate-meta">
        <span>${item.boards ? `${item.boards}板` : "弹性观察"}</span>
        <span>成交 ${escapeHtml(item.amount || "--")}</span>
        <span>炸板 ${item.failCount ?? 0}</span>
        <span>仓位 ${escapeHtml(item.position || "--")}</span>
      </div>
      ${renderCandidateTechnical(technical)}
      <p><b>买点：</b>${escapeHtml(item.buyPoint || "--")}</p>
      <p><b>风险：</b>${escapeHtml(item.risk || "--")}</p>
    </div>
  `;
}

function renderCandidateTechnical(technical) {
  if (!technical.status) return "";
  if (technical.status === "error") {
    return `<div class="candidate-tech muted">技术评分失败：${escapeHtml(technical.message || "--")}</div>`;
  }
  if (technical.status === "not_scored") {
    return `<div class="candidate-tech muted">${escapeHtml(technical.message || "本次未技术评分")}</div>`;
  }
  const veto = technical.vetoes?.length ? ` · 否决 ${technical.vetoes.length}` : "";
  return `
    <div class="candidate-tech">
      <span>技术 ${technical.total ?? "--"}${veto}</span>
      <span>MA20 ${formatMaybe(technical.ma20)}</span>
      <span>ATR ${formatMaybe(technical.atrPct)}%</span>
      <span>量比 ${formatMaybe(technical.volumeRatio)}</span>
    </div>
  `;
}

function renderReports() {
  const reports = dashboardData.reports;
  const tabs = document.getElementById("reportTabs");
  const content = document.getElementById("reportContent");
  if (!tabs || !content) return;
  if (!reports?.items?.length) {
    tabs.innerHTML = "";
    content.innerHTML = `<div class="risk-item">暂无自动复盘报告，等待下一次数据生成。</div>`;
    return;
  }

  if (!activeReportId || !reports.items.some((item) => item.id === activeReportId)) {
    activeReportId = reports.active || reports.items[0].id;
  }
  const active = reports.items.find((item) => item.id === activeReportId) || reports.items[0];
  tabs.innerHTML = reports.items
    .map(
      (item) => `
        <button class="${item.id === active.id ? "active" : ""}" data-report-id="${item.id}" type="button">${item.stage}</button>
      `,
    )
    .join("");

  const positionRule = reports.positionRule || {};
  content.innerHTML = `
    <div class="report-head">
      <div>
        <strong>${active.title}</strong>
        <span>${active.generatedAt || dashboardData.meta.generatedAt || "--"}</span>
      </div>
      <div class="report-badges">
        <span class="tag">温度 ${reports.marketLevel || "--"}</span>
        <span class="tag">周期 ${reports.emotionCycle || "--"}</span>
        <span class="tag">总仓 ${positionRule.total || "--"}</span>
      </div>
    </div>
    <p class="report-summary">${active.summary}</p>
    <div class="report-grid">
      ${(active.sections || []).map(renderReportSection).join("")}
      ${renderReportPlan(active.plan || [])}
    </div>
    <p class="disclaimer">${reports.disclaimer || ""}</p>
  `;
}

function renderReportSection(section) {
  return `
    <article class="report-card">
      <strong>${section.title}</strong>
      <ul>
        ${(section.items || []).map((item) => `<li>${item}</li>`).join("")}
      </ul>
    </article>
  `;
}

function renderReportPlan(plan) {
  if (!plan.length) return "";
  return `
    <article class="report-card">
      <strong>执行计划</strong>
      <ul>
        ${plan.map((item) => `<li><b>${item.title}</b>：${item.rule}</li>`).join("")}
      </ul>
    </article>
  `;
}

function renderScoreResult(result) {
  const q = result.quote || {};
  const score = result.score || {};
  const tech = result.technical || {};
  const labels = result.labels || {};
  const plan = result.plan || {};
  const vetoes = result.vetoes || [];
  const target = document.getElementById("scoreResult");
  const total = score.total ?? "--";
  target.innerHTML = `
    <div class="score-card">
      <div class="score-head">
        <div>
          <strong>${escapeHtml(q.name || `${q.market || ""}${q.code || ""}`)}</strong>
          <span>${escapeHtml(q.market || "")}${escapeHtml(q.code || "")} · ${escapeHtml(q.source || "--")} ${escapeHtml(q.time || "--")}</span>
        </div>
        <b>${total}</b>
      </div>
      <div class="score-meta">
        <span>动作：${escapeHtml(result.action || "--")}</span>
        <span>置信度：${escapeHtml(result.confidence || "--")}</span>
        <span>仓位：${escapeHtml(result.suggested_position || "--")}</span>
        <span>模式：${escapeHtml(labels.mode || "--")}</span>
      </div>
      <div class="score-grid">
        ${renderScoreMetric("趋势", score.trend)}
        ${renderScoreMetric("量价", score.volume_price)}
        ${renderScoreMetric("买点", score.buy_point_fit)}
        ${renderScoreMetric("风险", score.risk)}
        ${renderScoreMetric("波动", score.volatility)}
        ${renderScoreMetric("位置", score.position)}
      </div>
      <div class="score-plan">
        <p><b>买入：</b>${escapeHtml(plan.buy || "--")}</p>
        <p><b>止损：</b>${escapeHtml(plan.stop || "--")}</p>
        <p><b>止盈：</b>${escapeHtml(plan.take_profit || "--")}</p>
        <p><b>关键位：</b>${escapeHtml(plan.levels || "--")}</p>
      </div>
      <div class="score-meta">
        <span>MA20 ${formatMaybe(tech.ma20)}</span>
        <span>ATR ${formatMaybe(tech.atr)} (${formatMaybe(tech.atr_pct)}%)</span>
        <span>60日位置 ${formatMaybe(tech.position_60_pct)}%</span>
        <span>量比 ${formatMaybe(tech.volume_ratio)}</span>
      </div>
      ${vetoes.length ? `<div class="score-veto">${vetoes.map((item) => `<span>${escapeHtml(item)}</span>`).join("")}</div>` : ""}
      <p class="disclaimer">${escapeHtml(result.caveat || "自动分数需要结合市场情绪和主线地位确认。")}</p>
    </div>
  `;
}

function renderScoreMetric(label, value) {
  return `
    <div class="score-metric">
      <span>${label}</span>
      <strong>${value ?? "--"}</strong>
    </div>
  `;
}

function renderIndices() {
  const html = dashboardData.indices
    .map((item) => {
      const trendClass = item.changePct > 0 ? "up" : item.changePct < 0 ? "down" : "flat";
      return `
        <article class="ticker-card">
          <small>${item.name}</small>
          <strong>${item.price}</strong>
          <span class="${trendClass}">${formatSigned(item.changePct)}%</span>
        </article>
      `;
    })
    .join("");
  document.getElementById("indexStrip").innerHTML = html;
}

function renderEmotion() {
  const emotion = dashboardData.emotion;
  document.getElementById("emotionScore").textContent = emotion.score;
  document.getElementById("emotionTitle").textContent = emotion.title;
  document.getElementById("emotionBrief").textContent = emotion.brief;
  document.getElementById("emotionTag").textContent = emotion.tag;

  document.getElementById("heatBars").innerHTML = emotion.factors
    .map(
      (factor) => `
        <div class="heat-item">
          <span>${factor.label}</span>
          <strong class="${factor.valueClass || ""}">${factor.value}</strong>
        </div>
      `,
    )
    .join("");
}

function renderTemperature() {
  const stats = dashboardData.temperature;
  document.getElementById("temperatureStats").innerHTML = [
    ["涨停", stats.limitUp, "up"],
    ["跌停", stats.limitDown, "down"],
    ["炸板率", `${stats.failRate}%`, stats.failRate > 35 ? "down" : "flat"],
    ["最高连板", `${stats.maxLadder}板`, stats.maxLadder >= 5 ? "up" : "flat"],
  ]
    .map(
      ([label, value, trend]) => `
        <div class="stat">
          <span>${label}</span>
          <strong class="${trend}">${value}</strong>
        </div>
      `,
    )
    .join("");
}

function renderDiscipline() {
  document.getElementById("disciplineList").innerHTML = dashboardData.discipline
    .map((item) => `<li>${item}</li>`)
    .join("");
}

function renderLimitUps() {
  const rows = dashboardData.limitUps.filter((item) => {
    if (activeLimitFilter === "multi") return item.boards >= 2;
    if (activeLimitFilter === "first") return item.boards === 1;
    return true;
  });

  document.getElementById("limitUpTable").innerHTML = rows
    .map(
      (item) => `
        <tr>
          <td>
            <span class="stock-name">${item.name}</span>
            <span class="stock-code">${item.code}</span>
          </td>
          <td><strong class="up">${item.boards}板</strong></td>
          <td><div class="tag-row">${renderTags(item.tags)}</div></td>
          <td>
            <span>${item.sealAmount}</span>
            <div class="muted">${item.turnover}</div>
          </td>
          <td>${item.reason}</td>
        </tr>
      `,
    )
    .join("");
}

function renderLadder() {
  const groups = dashboardData.ladder;
  document.getElementById("ladderList").innerHTML = groups
    .map(
      (group) => `
        <div class="ladder-item">
          <div class="ladder-head">
            <strong>${group.level}板</strong>
            <span class="muted">${group.stocks.length}只</span>
          </div>
          <div class="tag-row">${renderTags(group.stocks)}</div>
        </div>
      `,
    )
    .join("");
}

function renderFlow(targetId, items) {
  if (!items?.length) {
    document.getElementById(targetId).innerHTML = `<div class="risk-item">暂无数据</div>`;
    return;
  }
  const maxAbs = Math.max(...items.map((item) => Math.abs(item.netInflow)), 1);
  document.getElementById(targetId).innerHTML = items
    .map((item) => {
      const isOut = item.netInflow < 0;
      const width = Math.max(10, Math.round((Math.abs(item.netInflow) / maxAbs) * 100));
      return `
        <div class="flow-item">
          <div class="flow-head">
            <strong>${item.name}</strong>
            <span class="${isOut ? "down" : "up"}">${formatMoney(item.netInflow)}</span>
          </div>
          <div class="flow-track">
            <span class="flow-fill ${isOut ? "out" : ""}" style="--w:${width}%"></span>
          </div>
          <span class="muted">${item.note}</span>
        </div>
      `;
    })
    .join("");
}

function renderAgainstMarket() {
  const against = dashboardData.againstMarket || { up: [], down: [], benchmark: null };
  renderPerformanceList("againstUp", against.up, "up");
  renderPerformanceList("againstDown", against.down, "down");

  const benchmark = against.benchmark;
  const text = benchmark
    ? `
      <div class="watch-card">
        <strong>${benchmark.name}</strong>
        <p>大盘基准 ${formatSigned(benchmark.changePct)}%。强于大盘看超额收益，弱于大盘看风险扩散。</p>
      </div>
    `
    : `<div class="watch-card"><strong>暂无基准</strong><p>指数数据缺失时无法计算强弱板块。</p></div>`;
  document.getElementById("marketBenchmark").innerHTML = text;
}

function renderFocusBoards() {
  const focus = dashboardData.focusBoards || { items: [], summary: [] };
  const items = focus.items || [];
  if (!items.length) {
    document.getElementById("focusBoards").innerHTML = `<div class="risk-item">暂无后续关注板块</div>`;
  } else {
    document.getElementById("focusBoards").innerHTML = items
      .map(
        (item) => `
          <div class="focus-card">
            <div class="focus-head">
              <div>
                <strong>${item.name}</strong>
                <span>${item.type}</span>
              </div>
              <b>${item.score}</b>
            </div>
            <div class="tag-row">${renderTags(item.labels)}</div>
            <div class="focus-metrics">
              <span>涨跌 ${formatSigned(item.changePct)}%</span>
              <span>超额 ${formatSigned(item.excessPct)}%</span>
              <span>资金 ${formatMoney(item.netInflow)}</span>
            </div>
            <p>${item.reason}</p>
          </div>
        `,
      )
      .join("");
  }

  document.getElementById("focusSummary").innerHTML = (focus.summary || [])
    .map(
      (item) => `
        <div class="watch-card">
          <strong>${item.title}</strong>
          <p>${item.rule}</p>
        </div>
      `,
    )
    .join("");
}

function renderTrendCharts() {
  const charts = dashboardData.trendCharts || [];
  const target = document.getElementById("trendCharts");
  if (!charts.length) {
    target.innerHTML = `<div class="risk-item">暂无走势数据，历史行情接口可能暂时不可用。</div>`;
    return;
  }
  target.innerHTML = charts
    .map(
      (chart) => `
        <div class="trend-card">
          <div class="trend-head">
            <div>
              <strong>${chart.name}</strong>
              <span>${chart.type} · ${chart.trend}</span>
            </div>
            <b class="${chart.ret5 >= 0 ? "up" : "down"}">${formatSigned(chart.ret5)}%</b>
          </div>
          ${chart.chartType === "snapshot" ? renderSnapshotBars(chart.bars) : renderSparkline(chart.points)}
          <div class="trend-stats">
            <span>${chart.chartType === "snapshot" ? "当日" : "5日"} ${formatSigned(chart.ret5)}%</span>
            <span>${chart.chartType === "snapshot" ? "超额" : "20日"} ${formatSigned(chart.ret20)}%</span>
            <span>${chart.chartType === "snapshot" ? "评分" : "回撤"} ${chart.chartType === "snapshot" ? chart.position : formatSigned(chart.drawdown) + "%"}</span>
            <span>${chart.chartType === "snapshot" ? "图形 强弱" : "位置 " + chart.position + "%"}</span>
          </div>
          <div class="tag-row">${renderTags(chart.labels || [])}</div>
        </div>
      `,
    )
    .join("");
}

function renderSnapshotBars(bars) {
  return `
    <div class="snapshot-bars">
      ${(bars || [])
        .map((bar) => {
          const width = Math.max(2, Math.min(100, (Math.abs(bar.value) / Math.max(bar.max, 1)) * 100));
          const trend = bar.value >= 0 ? "up" : "down";
          return `
            <div class="snapshot-row">
              <span>${bar.label}</span>
              <div class="snapshot-track"><b class="${trend}" style="--w:${width}%"></b></div>
              <em class="${trend}">${formatSigned(bar.value)}</em>
            </div>
          `;
        })
        .join("")}
    </div>
  `;
}

function renderSparkline(points) {
  if (!points?.length) return `<div class="spark-empty">暂无走势</div>`;
  const width = 320;
  const height = 120;
  const pad = 10;
  const closes = points.map((point) => point.close);
  const min = Math.min(...closes);
  const max = Math.max(...closes);
  const span = Math.max(max - min, 0.0001);
  const step = (width - pad * 2) / Math.max(points.length - 1, 1);
  const coords = points.map((point, index) => {
    const x = pad + index * step;
    const y = height - pad - ((point.close - min) / span) * (height - pad * 2);
    return `${x.toFixed(1)},${y.toFixed(1)}`;
  });
  const first = closes[0];
  const last = closes[closes.length - 1];
  const lineClass = last >= first ? "spark-up" : "spark-down";
  const area = `${pad},${height - pad} ${coords.join(" ")} ${width - pad},${height - pad}`;
  return `
    <svg class="sparkline" viewBox="0 0 ${width} ${height}" role="img" aria-label="走势线">
      <polyline class="spark-grid" points="${pad},${pad} ${width - pad},${pad}" />
      <polyline class="spark-grid" points="${pad},${height / 2} ${width - pad},${height / 2}" />
      <polyline class="spark-grid" points="${pad},${height - pad} ${width - pad},${height - pad}" />
      <polygon class="spark-area ${lineClass}" points="${area}" />
      <polyline class="spark-line ${lineClass}" points="${coords.join(" ")}" />
      <circle class="spark-dot ${lineClass}" cx="${coords[coords.length - 1].split(",")[0]}" cy="${coords[coords.length - 1].split(",")[1]}" r="3.5" />
    </svg>
  `;
}

function renderPerformanceList(targetId, items, trendClass) {
  if (!items?.length) {
    document.getElementById(targetId).innerHTML = `<div class="risk-item">暂无符合条件的板块</div>`;
    return;
  }
  document.getElementById(targetId).innerHTML = items
    .map(
      (item) => `
        <div class="flow-item">
          <div class="flow-head">
            <strong>${item.name}</strong>
            <span class="${trendClass}">${formatSigned(item.changePct)}%</span>
          </div>
          <div class="tag-row">
            <span class="tag">${item.type}</span>
            <span class="tag">超额 ${formatSigned(item.excessPct)}%</span>
          </div>
          <span class="muted">${item.note}</span>
        </div>
      `,
    )
    .join("");
}

function renderRisks() {
  document.getElementById("riskRadar").innerHTML = dashboardData.risks
    .map((item) => `<div class="risk-item">${item}</div>`)
    .join("");
}

function renderLimitDowns() {
  document.getElementById("limitDownTable").innerHTML = dashboardData.limitDowns
    .map(
      (item) => `
        <tr>
          <td>
            <span class="stock-name">${item.name}</span>
            <span class="stock-code">${item.code}</span>
          </td>
          <td><strong class="down">${item.changePct}%</strong></td>
          <td><div class="tag-row">${renderTags(item.tags)}</div></td>
          <td>${item.reason}</td>
        </tr>
      `,
    )
    .join("");
}

function renderWatchPlan() {
  document.getElementById("watchPlan").innerHTML = dashboardData.watchPlan
    .map(
      (item) => `
        <div class="watch-card">
          <strong>${item.title}</strong>
          <p>${item.rule}</p>
        </div>
      `,
    )
    .join("");
}

function renderTags(tags) {
  return tags.map((tag) => `<span class="tag">${tag}</span>`).join("");
}

function formatSigned(value) {
  return value > 0 ? `+${value.toFixed(2)}` : value.toFixed(2);
}

function formatMoney(value) {
  const unit = Math.abs(value) >= 10000 ? "亿" : "万";
  const normalized = unit === "亿" ? value / 10000 : value;
  return `${value > 0 ? "+" : ""}${money.format(normalized)}${unit}`;
}

function formatMaybe(value) {
  if (value === null || value === undefined || value === "") return "--";
  if (typeof value === "number") return value.toFixed(2);
  return String(value);
}

function escapeHtml(value) {
  return String(value ?? "").replace(/[&<>"']/g, (char) => {
    const entities = {
      "&": "&amp;",
      "<": "&lt;",
      ">": "&gt;",
      '"': "&quot;",
      "'": "&#39;",
    };
    return entities[char];
  });
}
