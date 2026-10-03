"use strict";

const byId = (id) => document.getElementById(id);
const state = {
  scenarios: [],
  selectedScenarioId: null,
  staticScenario: null,
  preview: null,
  liveEnabled: false,
  pending: null,
  working: false,
};
const STORAGE_KEY = "validation-demo.pending-request";
const ERROR_COPY = {
  demo_disabled: "实时服务尚未开放，当前展示的是固定离线示例。",
  feishu_auth_failed: "演示表暂时无法连接，请稍后重试。",
  feishu_lookup_failed: "暂时无法检查本次演示记录，请稍后重试。",
  feishu_create_failed: "暂时无法保存演示记录，请稍后重试。",
  feishu_update_failed: "分析结果暂时无法保存，请使用相同样例重试。",
  feishu_duplicate_request_id: "本次演示记录状态异常，请重新开始。",
  feishu_invalid_response: "演示记录服务暂时返回异常，请稍后重试。",
  pipeline_timeout: "处理时间超过本次演示上限，原请求可以安全重试。",
  dify_timeout: "AI 分析等待超时，原请求可以安全重试。",
  dify_quota_rejected: "AI 服务暂时达到调用上限，请稍后重试。",
  dify_invalid_output: "AI 返回内容未通过格式检查，原请求可以安全重试。",
  dify_upstream_failed: "AI 服务暂时不可用，原请求可以安全重试。",
  service_unavailable: "演示服务暂时不可用，请稍后重试。",
  unknown_scenario: "未找到该样例，请重新选择列表中的固定样例。",
};

function makeNode(tagName, className, text) {
  const node = document.createElement(tagName);
  if (className) node.className = className;
  if (text !== undefined) node.textContent = String(text);
  return node;
}

function setStatus(message, tone = "info") {
  const status = byId("status-message");
  status.textContent = message;
  status.dataset.tone = tone;
}

function setBadge(message, mode) {
  const badge = byId("mode-badge");
  badge.className = `mode-badge mode-${mode}`;
  badge.textContent = message;
}

function getSelectedScenario() {
  return state.scenarios.find((scenario) => scenario.id === state.selectedScenarioId) || null;
}

function renderScenarioList() {
  const list = byId("scenario-list");
  list.replaceChildren();
  byId("scenario-count").textContent = `${state.scenarios.length} 个固定样例`;

  state.scenarios.forEach((scenario, index) => {
    const button = makeNode("button", "scenario-card");
    button.type = "button";
    button.setAttribute("aria-pressed", String(scenario.id === state.selectedScenarioId));
    button.disabled = state.working || Boolean(state.pending);

    const number = makeNode("span", "scenario-index", String(index + 1).padStart(2, "0"));
    number.setAttribute("aria-hidden", "true");
    const copy = makeNode("span", "scenario-copy");
    copy.append(makeNode("strong", "", scenario.title));
    copy.append(makeNode("small", "", "固定资料 · 仅提交样例 ID"));
    const arrow = makeNode("span", "scenario-arrow", "↗");
    arrow.setAttribute("aria-hidden", "true");
    button.append(number, copy, arrow);
    button.addEventListener("click", () => selectScenario(scenario.id));
    list.append(button);
  });
}

function renderSelectedScenario() {
  const scenario = getSelectedScenario();
  if (!scenario) return;
  byId("selected-industry").textContent = "固定虚构资料";
  byId("selected-title").textContent = scenario.title;
  byId("selected-goal").textContent = "场景内容由服务端的固定样例目录提供。";
  byId("selected-metrics").textContent = "浏览器只提交样例 ID 与本次请求 ID。";
  byId("selected-budget").textContent = "不收集客户姓名、电话、邮箱或其他个人资料。";
  byId("result-eyebrow").textContent = "虚构经营样例 · 固定资料";
}

function selectScenario(scenarioId) {
  if (state.pending || state.working) return;
  state.selectedScenarioId = scenarioId;
  renderScenarioList();
  renderSelectedScenario();
  if (!state.liveEnabled && state.preview) {
    const staticTitle = state.staticScenario?.title || "固定静态示例";
    const note = scenarioId === state.staticScenario?.id
      ? "当前为离线静态预览，未执行实时 AI 分析。"
      : `当前选择为「${getSelectedScenario()?.title || "虚构样例"}」；下方固定静态结果对应「${staticTitle}」，未针对当前选择重新生成。`;
    renderStaticPreview(note);
  } else {
    showEmptyResult("此样例尚未运行实时分析。准备好后，可提交固定的虚构资料。", "运行实时分析");
  }
}

function renderObservationCards(observations) {
  const grid = makeNode("div", "observation-grid");
  const labels = ["证据", "推断", "缺失信息"];
  const grouped = groupObservations(observations);

  labels.forEach((label) => {
    const card = makeNode("article", "observation-card");
    card.dataset.kind = label;
    card.append(makeNode("span", "block-label", label));
    card.append(makeNode("p", "", grouped[label] || "暂无相关内容。"));
    grid.append(card);
  });
  return grid;
}

function renderAnalysis(analysis) {
  const content = byId("result-content");
  content.replaceChildren();

  const summary = makeNode("section", "summary-block");
  summary.append(makeNode("span", "block-label", "经营摘要 / EXECUTIVE SUMMARY"));
  summary.append(makeNode("p", "", analysis.executive_summary));
  content.append(summary);

  content.append(renderObservationCards(analysis.observations));

  const risks = makeNode("section", "risk-block");
  risks.append(makeNode("span", "block-label", "需要留意 / RISKS"));
  const riskList = makeNode("ul", "");
  for (const risk of analysis.risks || []) riskList.append(makeNode("li", "", risk));
  if (!riskList.childElementCount) riskList.append(makeNode("li", "", "暂无列出的风险。"));
  risks.append(riskList);
  content.append(risks);

  const heading = makeNode("div", "actions-heading");
  heading.append(makeNode("h3", "", "七天验证动作"));
  heading.append(makeNode("span", "", "记录指标，再做判断"));
  content.append(heading);

  const actionList = makeNode("div", "action-list");
  const actions = [...(analysis.seven_day_actions || [])].sort((left, right) => left.day - right.day);
  for (const action of actions) {
    const card = makeNode("article", "action-card");
    card.append(makeNode("span", "action-day", String(action.day).padStart(2, "0")));
    const copy = makeNode("div", "action-copy");
    copy.append(makeNode("strong", "", action.action));
    const metric = makeNode("p", "");
    metric.append(makeNode("b", "", "记录指标："), document.createTextNode(String(action.metric)));
    const rule = makeNode("p", "");
    rule.append(makeNode("b", "", "判断方式："), document.createTextNode(String(action.decision_rule)));
    copy.append(metric, rule);
    card.append(copy);
    actionList.append(card);
  }
  content.append(actionList);
}

function showEmptyResult(message, eyebrow) {
  setBadge("实时分析已就绪", "live");
  byId("result-title").textContent = "一周验证计划";
  byId("result-eyebrow").textContent = eyebrow || "经营问题 · 待开始";
  setStatus(message);
  byId("result-content").replaceChildren(
    makeNode("div", "result-empty", "提交后会生成经营摘要、证据与推断，以及逐日行动、记录指标和判断规则。")
  );
}

function renderStaticPreview(message) {
  if (!state.preview) return;
  setBadge("静态预览 · 未实时执行", "static");
  byId("result-title").textContent = state.staticScenario?.title || "固定静态示例";
  byId("result-eyebrow").textContent = "离线示例 · 非实时 AI 结果";
  setStatus(message, "info");
  renderAnalysis(state.preview);
}

function clearPending() {
  state.pending = null;
  try {
    sessionStorage.removeItem(STORAGE_KEY);
  } catch (_) {
    // Session storage is optional; the request remains available in memory.
  }
  renderScenarioList();
  byId("retry-button").hidden = true;
  byId("new-sample-button").hidden = true;
  byId("run-button").hidden = false;
  byId("run-button").disabled = !state.liveEnabled;
  byId("run-button").textContent = state.liveEnabled ? "运行实时分析 ↗" : "实时演示尚未启用";
}

function savePending() {
  try {
    sessionStorage.setItem(STORAGE_KEY, JSON.stringify(state.pending));
  } catch (_) {
    // Retrying still works until this page is closed.
  }
}

function restorePending() {
  try {
    const value = JSON.parse(sessionStorage.getItem(STORAGE_KEY) || "null");
    if (value && typeof value.requestId === "string" && state.scenarios.some((item) => item.id === value.scenarioId)) {
      state.pending = value;
      state.selectedScenarioId = value.scenarioId;
    }
  } catch (_) {
    state.pending = null;
  }
}

function showPendingControls() {
  byId("run-button").hidden = true;
  byId("run-button").disabled = true;
  byId("retry-button").hidden = false;
  byId("retry-button").disabled = state.working || !state.liveEnabled;
  byId("new-sample-button").hidden = false;
  byId("new-sample-button").disabled = state.working;
  renderScenarioList();
}

function newRequestId() {
  if (typeof crypto.randomUUID === "function") return crypto.randomUUID();
  const bytes = crypto.getRandomValues(new Uint8Array(16));
  bytes[6] = (bytes[6] & 0x0f) | 0x40;
  bytes[8] = (bytes[8] & 0x3f) | 0x80;
  const hex = Array.from(bytes, (byte) => byte.toString(16).padStart(2, "0")).join("");
  return `${hex.slice(0, 8)}-${hex.slice(8, 12)}-${hex.slice(12, 16)}-${hex.slice(16, 20)}-${hex.slice(20)}`;
}

async function postAnalysis(path) {
  const response = await fetch(path, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({
      scenario_id: state.pending.scenarioId,
      request_id: state.pending.requestId,
    }),
  });
  let payload = {};
  try {
    payload = await response.json();
  } catch (_) {
    payload = {};
  }
  if (!response.ok) {
    const code = payload.detail && typeof payload.detail.code === "string"
      ? payload.detail.code
      : "service_unavailable";
    throw Object.assign(new Error(ERROR_COPY[code] || ERROR_COPY.service_unavailable), {
      code,
      status: response.status,
    });
  }
  return payload;
}

function finishSuccess(result) {
  const scenario = state.scenarios.find((item) => item.id === state.pending.scenarioId);
  state.working = false;
  state.liveEnabled = true;
  state.selectedScenarioId = state.pending.scenarioId;
  state.pending = null;
  try {
    sessionStorage.removeItem(STORAGE_KEY);
  } catch (_) {
    // No persistent data is required after a completed run.
  }
  byId("run-button").hidden = false;
  byId("retry-button").hidden = true;
  byId("new-sample-button").hidden = true;
  byId("run-button").disabled = false;
  byId("run-button").textContent = "再分析一个样例 ↗";
  byId("result-title").textContent = scenario?.title || "分析完成";
  byId("result-eyebrow").textContent = "实时 AI 分析 · 已保存到 DEMO 表";
  setBadge("实时分析完成", "live");
  setStatus("分析已完成，结果已写入本次演示记录。", "success");
  renderAnalysis(result.analysis);
  renderScenarioList();
}

async function submitPending(path) {
  if (state.working || !state.pending) return;
  state.working = true;
  showPendingControls();
  setBadge("正在处理", "loading");
  setStatus("正在保存虚构样例并生成分析，请稍候…");
  byId("result-content").replaceChildren(
    makeNode("div", "result-empty", "正在执行：保存样例 → AI 分析 → 写回同一条演示记录。")
  );

  try {
    const result = await postAnalysis(path);
    if (result.status === "completed" && result.analysis) {
      finishSuccess(result);
      return;
    }
    state.working = false;
    if (result.status === "retryable_failed") {
      setBadge("需要重试", "error");
      setStatus(ERROR_COPY[result.error_code] || ERROR_COPY.service_unavailable, "error");
      showPendingControls();
      renderStaticIfAvailable();
      return;
    }
    throw Object.assign(new Error(ERROR_COPY.service_unavailable), { code: "service_unavailable" });
  } catch (error) {
    state.working = false;
    if (error.code === "demo_disabled") state.liveEnabled = false;
    setBadge("暂未完成", "error");
    setStatus(ERROR_COPY[error.code] || ERROR_COPY.service_unavailable, "error");
    renderStaticIfAvailable();
    showPendingControls();
  }
}

function renderStaticIfAvailable() {
  if (!state.preview) return;
  const message = byId("status-message").textContent;
  renderStaticPreview(`静态示例仅用于查看结果格式；${message}`);
  byId("mode-badge").className = "mode-badge mode-error";
  byId("mode-badge").textContent = "实时流程未完成";
  setStatus(message, "error");
}

function startNewAnalysis() {
  if (state.working) return;
  clearPending();
  state.selectedScenarioId = state.scenarios[0]?.id || null;
  renderScenarioList();
  renderSelectedScenario();
  if (state.liveEnabled) {
    showEmptyResult("选择样例后提交，即可生成只针对该样例的实时分析。", "经营问题 · 待开始");
  } else if (state.preview) {
    renderStaticPreview("实时服务未启用。下方结果是固定的早餐配送工作室静态示例。");
  }
}

async function initialize() {
  const [healthResult, scenariosResult, previewResult] = await Promise.allSettled([
    fetch("/api/health").then((response) => response.ok ? response.json() : Promise.reject(new Error("health"))),
    fetch("/api/scenarios").then((response) => response.ok ? response.json() : Promise.reject(new Error("scenarios"))),
    fetch("/api/preview").then((response) => response.ok ? response.json() : Promise.reject(new Error("preview"))),
  ]);

  if (scenariosResult.status === "fulfilled" && Array.isArray(scenariosResult.value)) {
    state.scenarios = scenariosResult.value.filter((item) =>
      item && typeof item.id === "string" && typeof item.title === "string"
    );
  }
  if (previewResult.status === "fulfilled") state.preview = previewResult.value;
  state.liveEnabled = healthResult.status === "fulfilled"
    && healthResult.value.live_demo_enabled === true;

  state.staticScenario = state.scenarios.find((item) => item.id === "breakfast-catering")
    || state.scenarios[0]
    || null;
  restorePending();
  if (!state.selectedScenarioId) state.selectedScenarioId = state.scenarios[0]?.id || null;
  renderScenarioList();
  renderSelectedScenario();

  const runButton = byId("run-button");
  runButton.disabled = !state.liveEnabled || state.scenarios.length === 0;
  runButton.textContent = state.liveEnabled ? "运行实时分析 ↗" : "实时演示尚未启用";
  runButton.addEventListener("click", () => {
    if (!state.liveEnabled || state.working) return;
    state.pending = { scenarioId: state.selectedScenarioId, requestId: newRequestId() };
    savePending();
    submitPending("/api/analyze");
  });

  byId("retry-button").addEventListener("click", () => submitPending("/api/retry"));
  byId("new-sample-button").addEventListener("click", startNewAnalysis);

  if (state.pending) {
    showPendingControls();
    if (state.liveEnabled) {
      setBadge("待恢复的请求", "loading");
      setStatus("发现尚未完成的同一请求。恢复检查会复用原请求 ID，不会新建演示记录。");
      showEmptyResult("点击下方恢复按钮；如果服务已完成，系统会直接返回已保存结果。", "原请求 · 可安全恢复");
      showPendingControls();
    } else if (state.preview) {
      renderStaticPreview("实时服务当前未启用；保留的请求可以在服务恢复后用原样例重试。");
      showPendingControls();
    }
    return;
  }

  if (state.liveEnabled) {
    showEmptyResult("实时服务已配置。选择一份虚构资料后开始分析。", "经营问题 · 待开始");
    return;
  }
  if (state.preview) {
    state.selectedScenarioId = state.staticScenario?.id || state.selectedScenarioId;
    renderScenarioList();
    renderSelectedScenario();
    renderStaticPreview(
      healthResult.status === "fulfilled"
        ? "实时服务尚未配置；当前展示早餐配送工作室的固定静态结果，未执行实时 AI 分析。"
        : "暂时无法确认实时服务状态；当前展示固定离线示例，未执行实时 AI 分析。"
    );
    return;
  }

  setBadge("暂时无法加载", "error");
  setStatus("样例和静态预览暂时无法加载，请刷新页面重试。", "error");
  byId("scenario-list").replaceChildren(makeNode("p", "scenario-loading", "样例服务暂时不可用。"));
}

initialize().catch(() => {
  setBadge("暂时无法加载", "error");
  setStatus("演示页面暂时无法初始化，请刷新页面重试。", "error");
});
