const state = {
  sessionId: localStorage.getItem("clone_session_id") || "",
  files: [],
  tts: false,
  sending: false,
  webMode: localStorage.getItem("clone_web_mode") || "auto",
};

const $ = (id) => document.getElementById(id);
const TRACE_STEPS = [
  ["connect", "认知轨迹正在建立连接"],
  ["sense", "感知需求"],
  ["attach", "解析附件"],
  ["memory", "召回记忆"],
  ["context", "整理上下文"],
  ["search", "搜索证据"],
  ["select", "选择能力"],
  ["generate", "生成回答"],
  ["review", "结构自检"],
];

const api = async (url, options = {}) => {
  const res = await fetch(url, options);
  const text = await res.text();
  const data = text ? JSON.parse(text) : {};
  if (!res.ok) throw new Error(data.detail || data.error || `HTTP ${res.status}`);
  return data;
};

function escapeHtml(text = "") {
  return String(text).replace(/[&<>"']/g, (m) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#039;" }[m]));
}

function toast(text) {
  const el = document.createElement("div");
  el.className = "toast";
  el.textContent = text;
  $("toasts").appendChild(el);
  setTimeout(() => el.remove(), 2600);
}

function renderMarkdownLite(text) {
  let html = escapeHtml(text);
  html = html.replace(/```([\s\S]*?)```/g, (_, code) => `<pre><code>${code.trim()}</code></pre>`);
  html = html.replace(/\*\*(.*?)\*\*/g, "<strong>$1</strong>");
  html = html.replace(/`([^`]+)`/g, "<code>$1</code>");
  return html;
}

function messageEl(role, content = "") {
  const el = document.createElement("article");
  el.className = `message ${role}`;
  const trace = role === "assistant" && !content ? renderCognitiveTrace() : "";
  el.innerHTML = `<span class="meta">${role === "user" ? "你" : "耦合生命"}</span>${trace}<div class="content">${renderMarkdownLite(content)}</div>`;
  return el;
}

function renderCognitiveTrace() {
  const rows = TRACE_STEPS.slice(1).map(([key, label]) => `
    <div class="trace-row" data-trace-step="${key}">
      <span class="trace-node"></span>
      <span class="trace-label">${label}</span>
      <span class="trace-state">等待信号</span>
      <span class="trace-time">--</span>
    </div>
  `).join("");
  return `
    <section class="cognitive-trace" data-cognitive-trace role="status" aria-live="polite">
      <div class="trace-head">
        <span class="trace-node trace-node-main"></span>
        <strong data-trace-title>认知轨迹正在建立连接</strong>
        <button type="button" class="trace-toggle" data-trace-toggle>展开中</button>
      </div>
      <div class="trace-steps">${rows}</div>
    </section>
    <div class="thinking-core" data-thinking-core>
      <span class="thinking-orb" aria-hidden="true"><i></i><i></i><i></i><i></i></span>
      <span>耦合生命思考中...</span>
    </div>
  `;
}

function clearWelcome() {
  const welcome = document.querySelector(".welcome");
  if (welcome) welcome.remove();
}

function scrollBottom() {
  $("messages").scrollTop = $("messages").scrollHeight;
}

function setConversationStatus(kind, text) {
  const status = $("statusText");
  if (!status) return;
  status.className = `status-text ${kind}`;
  status.textContent = text;
}

function setStreamStatus(assistant, text, hidden = false) {
  const title = assistant?.querySelector("[data-trace-title]");
  if (!title) return;
  title.textContent = text.replace(/^[^\u4e00-\u9fa5A-Za-z0-9]+/, "");
  const trace = assistant.querySelector("[data-cognitive-trace]");
  if (trace) trace.hidden = hidden;
}

function updateCognitiveTrace(assistant, targetKey, title = "") {
  const trace = assistant?.querySelector("[data-cognitive-trace]");
  if (!trace) return;
  if (title) setStreamStatus(assistant, title);
  const index = Math.max(0, TRACE_STEPS.findIndex(([key]) => key === targetKey) - 1);
  const rows = [...trace.querySelectorAll("[data-trace-step]")];
  rows.forEach((row, rowIndex) => {
    row.classList.toggle("is-done", rowIndex < index);
    row.classList.toggle("is-active", rowIndex === index);
    row.classList.toggle("is-pending", rowIndex > index);
    row.querySelector(".trace-state").textContent = rowIndex < index ? "已完成" : rowIndex === index ? "建立中" : "等待信号";
    row.querySelector(".trace-time").textContent = rowIndex < index ? `${Math.max(1, rowIndex + 1)}ms` : rowIndex === index ? "..." : "--";
  });
}

function setTraceRow(assistant, key, mode, detail, timeText = "") {
  const row = assistant?.querySelector(`[data-trace-step="${key}"]`);
  if (!row) return;
  row.classList.remove("is-done", "is-active", "is-pending", "is-error", "is-skipped");
  row.classList.add(`is-${mode}`);
  row.querySelector(".trace-state").textContent = detail;
  row.querySelector(".trace-time").textContent = timeText || (mode === "active" ? "..." : "--");
}

function traceMs(assistant, offset = 0) {
  const start = assistant?._traceStartedAt || performance.now();
  return `${Math.max(1, Math.round(performance.now() - start + offset))}ms`;
}

function applyTracePlan(assistant, plan) {
  if (!assistant) return;
  setStreamStatus(assistant, "生成回答 · 正在组织回答");
  setTraceRow(assistant, "sense", "done", "需求信号已接收", traceMs(assistant));
  setTraceRow(
    assistant,
    "attach",
    plan.attachments > 0 ? "done" : "skipped",
    plan.attachments > 0 ? `已解析 ${plan.attachments} 个附件` : "本次未使用附件",
    traceMs(assistant, 4),
  );
  setTraceRow(
    assistant,
    "memory",
    plan.memory_enabled && plan.memories > 0 ? "done" : "skipped",
    !plan.memory_enabled ? "长期记忆已关闭" : plan.memories > 0 ? `已参考 ${plan.memories} 条相关记忆` : "未命中相关记忆",
    traceMs(assistant, 8),
  );
  setTraceRow(
    assistant,
    "context",
    plan.context_enabled && plan.history > 1 ? "done" : "skipped",
    !plan.context_enabled ? "智能上下文优化已关闭" : plan.history > 1 ? "已整理最近上下文" : "暂无可整理上下文",
    traceMs(assistant, 12),
  );
  setTraceRow(
    assistant,
    "search",
    plan.web_results > 0 ? "done" : "skipped",
    plan.web_results > 0 ? `已找到 ${plan.web_results} 条证据` : (plan.web_mode === "off" ? "联网搜索已关闭" : "自动判断本次无需联网"),
    traceMs(assistant, 16),
  );
  const routeLabel = plan.route === "web_research" ? "联网研究" : "文本推理";
  setTraceRow(assistant, "select", "done", `已选择${routeLabel}`, traceMs(assistant, 20));
  setTraceRow(assistant, "generate", "active", "正在组织回答", traceMs(assistant, 20));
  setTraceRow(assistant, "review", "pending", "等待信号");
}

function startCognitiveTrace(assistant) {
  stopCognitiveTrace(assistant);
  assistant._traceStartedAt = performance.now();
  const planned = ["sense", "memory", "context", "select"];
  let index = 0;
  updateCognitiveTrace(assistant, planned[index], "认知轨迹正在建立连接");
  assistant._traceTimer = window.setInterval(() => {
    index = Math.min(index + 1, planned.length - 1);
    updateCognitiveTrace(assistant, planned[index], "认知轨迹正在建立连接");
  }, 520);
}

function stopCognitiveTrace(assistant) {
  if (assistant?._traceTimer) {
    window.clearInterval(assistant._traceTimer);
    assistant._traceTimer = null;
  }
}

function finishCognitiveTrace(assistant, errored = false) {
  stopCognitiveTrace(assistant);
  const trace = assistant?.querySelector("[data-cognitive-trace]");
  if (!trace) return;
  if (errored) {
    setTraceRow(assistant, "review", "error", "连接波动", "!");
    setStreamStatus(assistant, "认知轨迹连接波动");
    return;
  }
  setTraceRow(assistant, "generate", "done", "回答已生成", traceMs(assistant));
  setTraceRow(assistant, "review", "done", "结构检查完成", traceMs(assistant, 3));
  const doneCount = trace.querySelectorAll(".trace-row.is-done").length;
  const seconds = Math.max(0.1, (performance.now() - (assistant._traceStartedAt || performance.now())) / 1000).toFixed(1);
  trace.classList.add("is-collapsed");
  trace.querySelector("[data-trace-title]").textContent = `已完成 ${doneCount} 项能力 · 用时 ${seconds}s`;
  const toggle = trace.querySelector("[data-trace-toggle]");
  if (toggle) toggle.textContent = "查看神经图";
  const core = assistant.querySelector("[data-thinking-core]");
  if (core) core.hidden = true;
}

async function loadHistory() {
  const q = $("historySearch").value.trim();
  const data = await api(`/api/history?q=${encodeURIComponent(q)}`);
  const list = $("historyList");
  list.innerHTML = "";
  if (!data.items.length) list.innerHTML = `<div class="muted">暂无对话</div>`;
  data.items.forEach((item) => {
    const row = document.createElement("div");
    row.className = "list-item";
    row.innerHTML = `
      <strong>${escapeHtml(item.title)}</strong>
      <small>${escapeHtml(item.preview || "点击继续这个会话")}</small>
      <div class="item-actions">
        <button data-open="${item.id}">打开</button>
        <button data-rename="${item.id}">重命名</button>
        <button class="danger" data-delete="${item.id}">删除</button>
      </div>`;
    list.appendChild(row);
  });
}

async function loadTrash() {
  const data = await api("/api/trash");
  const list = $("trashList");
  list.innerHTML = data.items.length ? "" : `<div class="muted">回收站为空</div>`;
  data.items.forEach((item) => {
    const row = document.createElement("div");
    row.className = "list-item";
    row.innerHTML = `
      <strong>${escapeHtml(item.title)}</strong>
      <small>${escapeHtml(item.updated_at)}</small>
      <div class="item-actions">
        <button data-restore="${item.id}">恢复</button>
        <button class="danger" data-hard-delete="${item.id}">彻底删除</button>
      </div>`;
    list.appendChild(row);
  });
}

async function openConversation(id) {
  const data = await api(`/api/history/${id}`);
  state.sessionId = id;
  localStorage.setItem("clone_session_id", id);
  $("conversationTitle").textContent = data.conversation.title;
  $("messages").innerHTML = "";
  data.messages.forEach((m) => $("messages").appendChild(messageEl(m.role, m.content)));
  scrollBottom();
}

async function sendMessage() {
  if (state.sending) return;
  const input = $("chatInput");
  const text = input.value.trim();
  if (!text && !state.files.length) return;
  clearWelcome();
  input.value = "";
  const user = messageEl("user", text || "[附件]");
  $("messages").appendChild(user);
  const assistant = messageEl("assistant", "");
  $("messages").appendChild(assistant);
  const content = assistant.querySelector(".content");
  state.sending = true;
  setSendButtonGenerating(true);
  setConversationStatus("thinking", "耦合思考中");
  startCognitiveTrace(assistant);

  const fd = new FormData();
  fd.append("message", text);
  fd.append("session_id", state.sessionId);
  fd.append("web_search_mode", state.webMode);
  state.files.forEach((file) => fd.append("files", file));

  try {
    const res = await fetch("/api/chat/stream", { method: "POST", body: fd });
    if (!res.ok || !res.body) throw new Error(`HTTP ${res.status}`);
    const reader = res.body.getReader();
    const decoder = new TextDecoder();
    let buffer = "";
    let full = "";
    while (true) {
      const { value, done } = await reader.read();
      if (done) break;
      buffer += decoder.decode(value, { stream: true });
      const parts = buffer.split("\n\n");
      buffer = parts.pop() || "";
      for (const part of parts) {
        if (!part.startsWith("data:")) continue;
        const payload = JSON.parse(part.slice(5));
        if (payload.type === "trace") {
          stopCognitiveTrace(assistant);
          applyTracePlan(assistant, payload);
        }
        if (payload.type === "status") {
          if (payload.phase === "thinking") {
            setConversationStatus("thinking", "耦合思考中");
          } else if (payload.phase === "streaming") {
            setConversationStatus("streaming", "生命流生成中");
            setTraceRow(assistant, "generate", "active", "正在组织回答", traceMs(assistant));
          } else if (payload.phase === "complete") {
            setConversationStatus("complete", "回答已形成");
            finishCognitiveTrace(assistant);
          } else if (payload.phase === "error") {
            setConversationStatus("error", "连接波动");
            finishCognitiveTrace(assistant, true);
          }
        }
        if (payload.type === "delta") {
          if (!full) {
            setTraceRow(assistant, "generate", "active", "正在组织回答", traceMs(assistant));
            setConversationStatus("streaming", "生命流生成中");
          }
          full += payload.content;
          content.innerHTML = renderMarkdownLite(full);
          scrollBottom();
        }
        if (payload.type === "done") {
          state.sessionId = payload.session_id;
          localStorage.setItem("clone_session_id", state.sessionId);
        }
      }
    }
    if (state.tts && full && "speechSynthesis" in window) {
      speechSynthesis.speak(new SpeechSynthesisUtterance(full.slice(0, 500)));
    }
    state.files = [];
    renderPendingFiles();
    await loadHistory();
  } catch (err) {
    content.innerHTML = `<span class="danger-text">${escapeHtml(err.message)}</span>`;
    finishCognitiveTrace(assistant, true);
    setConversationStatus("error", "连接波动");
  } finally {
    stopCognitiveTrace(assistant);
    state.sending = false;
    setSendButtonGenerating(false);
    if (!$("statusText").classList.contains("error")) {
      setConversationStatus("complete", "回答已形成");
      window.setTimeout(() => {
        if (!state.sending) setConversationStatus("idle", "在线 · 本地可部署");
      }, 900);
    }
  }
}

function setSendButtonGenerating(active) {
  const btn = $("sendBtn");
  btn.classList.toggle("is-generating", active);
  btn.title = active ? "停止生成" : "发送消息 (Enter)";
  btn.setAttribute("aria-label", active ? "停止生成" : "发送消息");
}

function setWebSearchMode(mode) {
  state.webMode = mode;
  localStorage.setItem("clone_web_mode", mode);
  const label = mode === "off" ? "联网 · 关闭" : mode === "manual" ? "联网 · 手动" : "联网 · 自动";
  $("webSearchModeLabel").textContent = label;
  document.querySelectorAll("[data-search-mode]").forEach((button) => {
    button.setAttribute("aria-checked", button.dataset.searchMode === mode ? "true" : "false");
  });
  $("webSearchModeMenu").classList.remove("open");
  $("webSearchBtn").setAttribute("aria-expanded", "false");
}

function renderPendingFiles() {
  const badge = $("fileBadge");
  const list = $("fileList");
  if (!state.files.length) {
    badge.textContent = "";
    list.innerHTML = "";
    $("fileBtn").classList.remove("has-file");
    return;
  }
  badge.textContent = `${state.files.length} 个文件`;
  $("fileBtn").classList.add("has-file");
  list.innerHTML = state.files.map((file, index) => `
    <div class="file-chip-clone">
      <span>${escapeHtml(file.name)}</span>
      <button type="button" data-remove-file="${index}" title="移除附件">×</button>
    </div>
  `).join("");
}

async function loadSettings() {
  const [profile, memory, knowledge, context] = await Promise.all([
    api("/auth/profile"),
    api("/api/memory/settings"),
    api("/api/knowledge/settings"),
    api("/api/context/settings"),
  ]);
  $("profileName").value = profile.name || "";
  $("profileIdentity").value = profile.identity || "user";
  $("profileCompany").value = profile.company || "";
  $("profileDepartment").value = profile.department || "";
  $("memorySetting").checked = memory.enabled;
  $("knowledgeSetting").checked = knowledge.enabled;
  $("contextSetting").checked = context.enabled;
  $("profileState").textContent = "个人资料已读取";
  setSettingState("memorySettingState", memory.enabled ? "已开启 · 将在后续对话中使用长期记忆" : "已关闭 · 已有记忆仍会保留", memory.enabled);
  setSettingState("knowledgeSettingState", knowledge.enabled ? "已开启 · 回答可引用耦合知识库" : "已关闭 · 资料仍保留，可手动搜索", knowledge.enabled);
  setSettingState("contextSettingState", context.enabled ? "已开启 · 长对话会自动整理旧内容" : "已关闭 · 保留完整上下文", context.enabled);
  await loadMemories();
}

async function loadMemories() {
  const params = new URLSearchParams();
  if ($("memoryManagerQuery") && $("memoryManagerQuery").value.trim()) params.set("q", $("memoryManagerQuery").value.trim());
  if ($("memoryManagerStatus") && $("memoryManagerStatus").value) params.set("status", $("memoryManagerStatus").value);
  if ($("memoryManagerKind") && $("memoryManagerKind").value) params.set("kind", $("memoryManagerKind").value);
  const data = await api(`/api/memories?${params.toString()}`);
  const list = $("memoryList");
  if ($("memoryManagerState")) $("memoryManagerState").textContent = `共 ${data.memories.length} 条记忆`;
  list.innerHTML = data.memories.length ? "" : `<div class="muted">暂无长期记忆</div>`;
  data.memories.forEach((m) => {
    const row = document.createElement("div");
    row.className = "memory-manager-row";
    row.innerHTML = `
      <div class="memory-manager-copy"><strong>${escapeHtml(m.content)}</strong><span>${escapeHtml(m.kind)} · ${escapeHtml(m.status)} · ${escapeHtml(m.updated_at || "")}</span></div>
      <div class="memory-manager-actions">
        <button data-memory-edit="${m.id}">编辑</button>
        <button data-memory-archive="${m.id}">归档</button>
        <button class="danger" data-memory-delete="${m.id}">删除</button>
      </div>`;
    list.appendChild(row);
  });
}

function setSettingState(id, text, enabled) {
  const el = $(id);
  if (!el) return;
  el.textContent = text;
  el.dataset.state = enabled ? "on" : "off";
}

const kbState = { nodes: [], edges: [], selectedId: "", zoom: 1 };

async function loadKnowledge() {
  const data = await api("/api/knowledge/graph");
  kbState.nodes = data.nodes || [];
  kbState.edges = data.edges || [];
  renderKnowledgeGraph();
  renderKnowledgeSources();
}

function kbNodePosition(index, total) {
  if (total <= 1) return { x: 600, y: 380 };
  const angle = (Math.PI * 2 * index) / total - Math.PI / 2;
  const radius = Math.min(260, 120 + total * 12);
  return { x: 600 + Math.cos(angle) * radius, y: 380 + Math.sin(angle) * radius };
}

function renderKnowledgeGraph() {
  const edgeLayer = $("kbEdgeLayer");
  const nodeLayer = $("kbNodeLayer");
  if (!edgeLayer || !nodeLayer) return;
  edgeLayer.innerHTML = "";
  nodeLayer.innerHTML = "";
  const positions = new Map();
  kbState.nodes.forEach((node, index) => positions.set(node.id, kbNodePosition(index, kbState.nodes.length)));
  kbState.edges.forEach((edge) => {
    const a = positions.get(edge.source_id);
    const b = positions.get(edge.target_id);
    if (!a || !b) return;
    const line = document.createElementNS("http://www.w3.org/2000/svg", "line");
    line.setAttribute("class", "kb-edge-line");
    line.setAttribute("x1", a.x);
    line.setAttribute("y1", a.y);
    line.setAttribute("x2", b.x);
    line.setAttribute("y2", b.y);
    edgeLayer.appendChild(line);
  });
  kbState.nodes.forEach((node, index) => {
    const pos = positions.get(node.id);
    const group = document.createElementNS("http://www.w3.org/2000/svg", "g");
    group.setAttribute("class", `kb-node-clone${kbState.selectedId === node.id ? " selected" : ""}`);
    group.setAttribute("transform", `translate(${pos.x} ${pos.y}) scale(${kbState.zoom})`);
    group.dataset.id = node.id;
    const circle = document.createElementNS("http://www.w3.org/2000/svg", "circle");
    circle.setAttribute("r", "34");
    const label = document.createElementNS("http://www.w3.org/2000/svg", "text");
    label.setAttribute("y", "5");
    label.textContent = (node.title || "知识").slice(0, 8);
    const bg = document.createElementNS("http://www.w3.org/2000/svg", "rect");
    bg.setAttribute("class", "kb-label-bg-clone");
    bg.setAttribute("x", "-58");
    bg.setAttribute("y", "45");
    bg.setAttribute("width", "116");
    bg.setAttribute("height", "28");
    bg.setAttribute("rx", "9");
    const caption = document.createElementNS("http://www.w3.org/2000/svg", "text");
    caption.setAttribute("y", "64");
    caption.setAttribute("font-size", "11");
    caption.textContent = (node.title || "知识节点").slice(0, 10);
    group.append(circle, label, bg, caption);
    group.addEventListener("click", () => openKnowledge(node.id));
    nodeLayer.appendChild(group);
  });
  $("kbEmpty").hidden = kbState.nodes.length > 0;
  $("kbStatus").textContent = `节点 ${kbState.nodes.length} · 关系 ${kbState.edges.length}`;
}

function renderKnowledgeSources() {
  const list = $("knowledgeList");
  if (!list) return;
  list.innerHTML = kbState.nodes.length ? "" : `<div class="kb-source-row-clone"><span>还没有投喂资料</span></div>`;
  kbState.nodes.forEach((node) => {
    const row = document.createElement("div");
    row.className = "kb-source-row-clone";
    row.innerHTML = `
      <strong>${escapeHtml(node.title || "知识节点")}</strong>
      <span>${escapeHtml(node.kind || "手工知识")} · ${escapeHtml(node.status || "ready")}</span>
      <div class="item-actions">
        <button data-kb-open="${node.id}">打开知识节点</button>
        <button class="danger" data-kb-archive="${node.id}">归档</button>
      </div>`;
    list.appendChild(row);
  });
}

async function addKnowledge() {
  const title = $("kbTitle").value.trim();
  const text = $("kbText").value.trim();
  if (!title || !text) return toast("请填写知识标题和内容");
  await api("/api/knowledge/sources/text", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ title, text }),
  });
  $("kbTitle").value = "";
  $("kbText").value = "";
  toast("知识已添加");
  $("kbImportDrawer").classList.remove("open");
  await loadKnowledge();
}

async function uploadKnowledgeFiles(files) {
  if (!files || !files.length) return;
  const fd = new FormData();
  [...files].forEach((file) => fd.append("files", file));
  await fetch("/api/knowledge/sources", { method: "POST", body: fd });
  toast("资料已导入知识库");
  await loadKnowledge();
}

async function openKnowledge(id) {
  const note = await api(`/api/knowledge/notes/${id}`);
  kbState.selectedId = id;
  $("kbImportDrawer").classList.remove("open");
  $("kbNodeKind").textContent = note.kind === "file" ? "文件知识" : "可用知识";
  $("kbNodeTitle").textContent = note.title || "知识节点";
  $("kbReaderState").textContent = note.status === "ready" ? "已确认知识" : note.status || "知识条目";
  $("kbReaderContent").innerHTML = renderMarkdownLite(note.content || "暂无内容");
  $("kbReaderSources").textContent = note.source_file ? `原始文件：${note.source_file}` : "手工知识";
  $("kbEditTitle").value = note.title || "";
  $("kbEditContent").value = note.content || "";
  $("kbNodeMeta").textContent = `稳定编号：${note.id}\n来源：${note.source_file || "手工知识"}\n最近更新：${note.updated_at || "—"}`;
  $("kbReader").hidden = false;
  $("kbEditor").hidden = true;
  renderKnowledgeRelations(id);
  $("kbInspector").classList.add("open");
  renderKnowledgeGraph();
}

function renderKnowledgeRelations(id) {
  const select = $("kbRelationTarget");
  const chips = $("kbRelationList");
  const reader = $("kbReaderRelations");
  select.innerHTML = `<option value="">选择已有节点</option>`;
  chips.innerHTML = "";
  reader.innerHTML = "";
  kbState.nodes.filter((node) => node.id !== id).forEach((node) => {
    const option = document.createElement("option");
    option.value = node.id;
    option.textContent = node.title || "知识节点";
    select.appendChild(option);
  });
  const related = kbState.edges.filter((edge) => edge.source_id === id || edge.target_id === id);
  related.forEach((edge) => {
    const otherId = edge.source_id === id ? edge.target_id : edge.source_id;
    const other = kbState.nodes.find((node) => node.id === otherId);
    if (!other) return;
    const chip = document.createElement("span");
    chip.className = "kb-chip-clone";
    chip.textContent = other.title || "关联知识";
    chips.appendChild(chip);
    const link = document.createElement("button");
    link.type = "button";
    link.className = "kb-reader-relation-clone";
    link.textContent = other.title || "关联知识";
    link.onclick = () => openKnowledge(other.id);
    reader.appendChild(link);
  });
  if (!reader.childElementCount) reader.textContent = "暂无关联知识。";
}

async function saveKnowledgeNote() {
  if (!kbState.selectedId) return;
  await api(`/api/knowledge/notes/${kbState.selectedId}`, {
    method: "PATCH",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ title: $("kbEditTitle").value, content: $("kbEditContent").value }),
  });
  toast("知识已保存，可立即用于检索");
  await loadKnowledge();
  await openKnowledge(kbState.selectedId);
}

async function archiveKnowledgeNote(id = kbState.selectedId) {
  if (!id) return;
  await api(`/api/knowledge/notes/${id}`, { method: "DELETE" });
  toast("知识已归档");
  $("kbInspector").classList.remove("open");
  kbState.selectedId = "";
  await loadKnowledge();
}

async function createKnowledgeRelation(targetId) {
  if (!kbState.selectedId || !targetId) return;
  await api("/api/knowledge/relations", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ source_id: kbState.selectedId, target_id: targetId, type: "相关" }),
  });
  toast("已建立知识关系");
  await loadKnowledge();
  await openKnowledge(kbState.selectedId);
}

function openInspector(html) {
  $("inspectorContent").innerHTML = html;
  $("inspector").classList.add("open");
}

function closeInspector() {
  $("inspector").classList.remove("open");
  setTimeout(() => {
    if (!$("inspector").classList.contains("open")) $("inspectorContent").innerHTML = "";
  }, 240);
}

function openModal(html) {
  $("modalContent").innerHTML = html;
  $("modal").hidden = false;
}

function closeModal() {
  $("modal").hidden = true;
  $("modalContent").innerHTML = "";
}

async function openAnnouncements() {
  const data = await api("/api/announcements?filter=all");
  openModal(`<h2>公告中心</h2>${data.items.map((a) => `<article class="list-item"><strong>${escapeHtml(a.title)}</strong><small>${escapeHtml(a.content)}</small></article>`).join("")}<button id="readAll">全部标为已读</button>`);
  $("readAll").onclick = async () => {
    await api("/api/announcements/read-all", { method: "POST" });
    toast("已标记");
    closeModal();
  };
}

async function openMemos() {
  const data = await api("/api/memos");
  openModal(`
    <h2>备忘录</h2>
    <div class="memory-create"><input id="memoTitle" placeholder="新的备忘"><button id="memoAdd">添加</button></div>
    <div class="list">${data.memos.map((m) => `<div class="list-item"><strong>${escapeHtml(m.title)}</strong><small>${escapeHtml(m.status)}</small><div class="item-actions"><button data-memo-complete="${m.id}">完成</button><button class="danger" data-memo-delete="${m.id}">删除</button></div></div>`).join("") || "<div class='muted'>暂无备忘录</div>"}</div>
  `);
  $("memoAdd").onclick = async () => {
    await api("/api/memos", { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ title: $("memoTitle").value }) });
    closeModal();
    openMemos();
  };
}

async function openApiKey() {
  const status = await api("/auth/api-key-status");
  openModal(`
    <h2>API 密钥</h2>
    <p class="muted">${status.has_key ? `已有密钥：${escapeHtml(status.masked)}` : "还没有申请本地 API 密钥。"}</p>
    <button id="applyKey">申请/重置密钥</button>
    <button id="viewKey">查看密钥</button>
    <pre id="keyBox"></pre>
  `);
  $("applyKey").onclick = async () => {
    const data = await api("/auth/apply-api-key", { method: "POST" });
    $("keyBox").textContent = data.api_key;
  };
  $("viewKey").onclick = async () => {
    try {
      const data = await api("/auth/view-api-key");
      $("keyBox").textContent = data.api_key;
    } catch (err) {
      toast(err.message);
    }
  };
}

async function makePpt() {
  const message = $("chatInput").value.trim() || "产品汇报";
  const outline = await api("/api/ppt/outline", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ message }),
  });
  const slides = await api("/api/ppt/slides", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ outline: outline.outline, template: outline.template }),
  });
  openModal(`
    <h2>PPT 工作台</h2>
    <pre>${escapeHtml(outline.outline)}</pre>
    <div class="list">${slides.slides.map((s, i) => `<article class="list-item"><strong>${i + 1}. ${escapeHtml(s.title)}</strong><small>${escapeHtml(s.body)}</small></article>`).join("")}</div>
    <button id="downloadSlides">下载 JSON 方案</button>
  `);
  $("downloadSlides").onclick = () => {
    const blob = new Blob([JSON.stringify(slides, null, 2)], { type: "application/json" });
    const a = document.createElement("a");
    a.href = URL.createObjectURL(blob);
    a.download = "slides.json";
    a.click();
  };
}

async function showSummary() {
  if (!state.sessionId) return toast("当前还没有会话");
  const data = await api(`/api/context/summary/${state.sessionId}`);
  openModal(`<h2>上下文摘要</h2><pre>${escapeHtml(data.summary)}</pre><button id="copySummary">复制摘要</button>`);
  $("copySummary").onclick = () => navigator.clipboard.writeText(data.summary).then(() => toast("已复制"));
}

function drawLife() {
  const canvas = $("lifeCanvas");
  const ctx = canvas.getContext("2d");
  let t = 0;
  function frame() {
    t += 0.018;
    ctx.clearRect(0, 0, canvas.width, canvas.height);
    ctx.save();
    ctx.translate(130, 130);
    for (let i = 0; i < 54; i++) {
      const a = i * 0.72 + t;
      const r = 34 + Math.sin(t * 2 + i) * 12 + i * 1.35;
      ctx.beginPath();
      ctx.arc(Math.cos(a) * r, Math.sin(a * 0.91) * r, 2.2 + Math.sin(i + t) * 1.3, 0, Math.PI * 2);
      ctx.fillStyle = i % 3 ? "rgba(47,157,97,.55)" : "rgba(211,123,72,.58)";
      ctx.fill();
    }
    ctx.restore();
    requestAnimationFrame(frame);
  }
  frame();
}

function applyUi() {
  const theme = localStorage.getItem("clone_theme") || "aurora";
  const scale = localStorage.getItem("clone_font_scale") || "100";
  const width = localStorage.getItem("clone_content_width") || "standard";
  const reduceMotion = localStorage.getItem("clone_reduce_motion") === "true";
  document.documentElement.dataset.theme = theme;
  document.documentElement.dataset.contentWidth = width;
  document.documentElement.dataset.reduceMotion = reduceMotion ? "true" : "false";
  document.documentElement.style.setProperty("--font-scale", Number(scale) / 100);
  document.documentElement.style.setProperty("--content-width", width === "compact" ? "740px" : width === "wide" ? "1120px" : "920px");
  if ($("fontScale")) $("fontScale").value = scale;
  if ($("fontScaleValue")) $("fontScaleValue").textContent = `${scale}%`;
  if ($("motionSetting")) $("motionSetting").checked = reduceMotion;
  document.querySelectorAll("[data-theme-value]").forEach((button) => button.classList.toggle("active", button.dataset.themeValue === theme));
  document.querySelectorAll("[data-width-value]").forEach((button) => button.classList.toggle("active", button.dataset.widthValue === width));
}

function bindEvents() {
  $("sendBtn").onclick = sendMessage;
  $("chatInput").addEventListener("keydown", (event) => {
    if (event.key === "Enter" && !event.shiftKey) {
      event.preventDefault();
      sendMessage();
    }
  });
  document.querySelectorAll("[data-prompt]").forEach((button) => {
    button.onclick = () => {
      $("chatInput").value = button.dataset.prompt;
      $("chatInput").focus();
    };
  });
  $("newChat").onclick = () => {
    state.sessionId = "";
    localStorage.removeItem("clone_session_id");
    $("conversationTitle").textContent = "新对话";
    $("messages").innerHTML = document.querySelector(".messages").innerHTML;
    location.reload();
  };
  $("historySearch").oninput = () => loadHistory();
  $("messages").addEventListener("click", (event) => {
    const toggle = event.target.closest("[data-trace-toggle]");
    if (!toggle) return;
    const trace = toggle.closest("[data-cognitive-trace]");
    if (!trace) return;
    const collapsed = trace.classList.toggle("is-collapsed");
    toggle.textContent = collapsed ? "查看神经图" : "收起";
  });
  $("fileInput").onchange = (e) => {
    state.files = [...e.target.files];
    renderPendingFiles();
  };
  $("cameraInput").onchange = (e) => {
    state.files = [...e.target.files];
    renderPendingFiles();
  };
  $("webSearchBtn").onclick = (event) => {
    event.stopPropagation();
    const menu = $("webSearchModeMenu");
    const willOpen = !menu.classList.contains("open");
    menu.classList.toggle("open", willOpen);
    $("webSearchBtn").setAttribute("aria-expanded", willOpen ? "true" : "false");
  };
  document.querySelectorAll("[data-search-mode]").forEach((button) => {
    button.onclick = (event) => {
      event.stopPropagation();
      setWebSearchMode(button.dataset.searchMode);
    };
  });
  setWebSearchMode(state.webMode);
  $("ttsToggle").onclick = () => {
    state.tts = !state.tts;
    $("ttsToggle").classList.toggle("active", state.tts);
    toast(state.tts ? "已开启语音播报" : "已关闭语音播报");
  };
  $("voiceBtn").onclick = async () => {
    const data = await api("/api/stt", { method: "POST" });
    $("chatInput").value = data.text;
    toast("语音入口已跑通");
  };
  $("pptBtn").onclick = makePpt;
  $("summaryBtn").onclick = showSummary;
  $("announcementBtn").onclick = openAnnouncements;
  $("loginHelpTop").onclick = () => openModal(`<h2>联系管理员</h2><p class="muted">本地复刻版默认免登录。正式部署时可以在这里接入管理员二维码、企业微信或登录帮助。</p>`);
  $("settingsTop").onclick = () => {
    document.querySelector('[data-tab="settings"]').click();
    $("sidebar").classList.add("open");
  };
  $("userMenuTop").onclick = (event) => {
    event.stopPropagation();
    $("userMenuPop").classList.toggle("open");
    $("userMenuTop").setAttribute("aria-expanded", $("userMenuPop").classList.contains("open") ? "true" : "false");
  };
  $("memoBtn").onclick = openMemos;
  $("apiKeyBtn").onclick = openApiKey;
  $("profileMenuBtn").onclick = () => {
    $("userMenuPop").classList.remove("open");
    document.querySelector('[data-tab="settings"]').click();
    $("sidebar").classList.add("open");
  };
  $("modalClose").onclick = closeModal;
  $("closeInspector").onclick = closeInspector;
  $("modal").addEventListener("click", (event) => {
    if (event.target === $("modal")) closeModal();
  });
  document.addEventListener("keydown", (event) => {
    if (event.key === "Escape") {
      closeModal();
      closeInspector();
      $("sidebar").classList.remove("open");
    }
  });
  $("toggleSidebar").onclick = () => $("sidebar").classList.toggle("open");
  $("saveProfile").onclick = async () => {
    await api("/auth/profile", {
      method: "PUT",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ name: $("profileName").value, identity: $("profileIdentity").value, company: $("profileCompany").value, department: $("profileDepartment").value }),
    });
    toast("资料已保存");
  };
  $("memorySetting").onchange = async (e) => {
    setSettingState("memorySettingState", "正在保存…", e.target.checked);
    const data = await api("/api/memory/settings", { method: "PUT", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ enabled: e.target.checked }) });
    setSettingState("memorySettingState", data.enabled ? "已开启 · 将在后续对话中使用长期记忆" : "已关闭 · 已有记忆仍会保留", data.enabled);
  };
  $("knowledgeSetting").onchange = async (e) => {
    setSettingState("knowledgeSettingState", "正在保存…", e.target.checked);
    const data = await api("/api/knowledge/settings", { method: "PUT", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ enabled: e.target.checked }) });
    setSettingState("knowledgeSettingState", data.enabled ? "已开启 · 回答可引用耦合知识库" : "已关闭 · 资料仍保留，可手动搜索", data.enabled);
  };
  $("contextSetting").onchange = async (e) => {
    setSettingState("contextSettingState", "正在保存…", e.target.checked);
    const data = await api("/api/context/settings", { method: "PUT", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ enabled: e.target.checked }) });
    setSettingState("contextSettingState", data.enabled ? "已开启 · 长对话会自动整理旧内容" : "已关闭 · 保留完整上下文", data.enabled);
  };
  $("addMemory").onclick = async () => {
    if (!$("memoryText").value.trim()) return;
    await api("/api/memories", { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ content: $("memoryText").value, kind: "fact" }) });
    $("memoryText").value = "";
    await loadMemories();
  };
  $("refreshMemory").onclick = () => loadMemories();
  $("memoryManagerQuery").oninput = () => loadMemories();
  $("memoryManagerStatus").onchange = () => loadMemories();
  $("memoryManagerKind").onchange = () => loadMemories();
  $("addKnowledge").onclick = addKnowledge;
  $("kbFiles").onchange = (e) => uploadKnowledgeFiles(e.target.files);
  $("kbDropzone").onclick = () => $("kbFiles").click();
  $("kbDropzone").addEventListener("dragover", (event) => event.preventDefault());
  $("kbDropzone").addEventListener("drop", (event) => {
    event.preventDefault();
    uploadKnowledgeFiles(event.dataTransfer.files);
  });
  $("kbImportOpen").onclick = () => {
    $("kbInspector").classList.remove("open");
    $("kbImportDrawer").classList.add("open");
  };
  $("kbImportClose").onclick = () => $("kbImportDrawer").classList.remove("open");
  $("kbInspectorClose").onclick = () => $("kbInspector").classList.remove("open");
  $("kbEditNote").onclick = () => {
    $("kbReader").hidden = true;
    $("kbEditor").hidden = false;
    $("kbEditTitle").focus();
  };
  $("kbCancelEdit").onclick = () => {
    $("kbEditor").hidden = true;
    $("kbReader").hidden = false;
  };
  $("kbSaveNote").onclick = saveKnowledgeNote;
  $("kbArchiveNote").onclick = () => archiveKnowledgeNote();
  $("kbRelationTarget").onchange = (event) => {
    const value = event.target.value;
    event.target.value = "";
    createKnowledgeRelation(value);
  };
  $("kbSearch").addEventListener("keydown", async (event) => {
    if (event.key !== "Enter" || !event.currentTarget.value.trim()) return;
    const data = await api(`/api/knowledge/search?q=${encodeURIComponent(event.currentTarget.value.trim())}`);
    if (data.items && data.items[0]) openKnowledge(data.items[0].note_id);
    else toast("没有找到已确认知识");
  });
  $("kbZoomOut").onclick = () => {
    kbState.zoom = Math.max(0.65, kbState.zoom - 0.15);
    renderKnowledgeGraph();
  };
  $("kbZoomIn").onclick = () => {
    kbState.zoom = Math.min(1.55, kbState.zoom + 0.15);
    renderKnowledgeGraph();
  };
  $("kbZoomFit").onclick = () => {
    kbState.zoom = 1;
    renderKnowledgeGraph();
  };
  $("kbLayoutReset").onclick = () => {
    kbState.zoom = 1;
    renderKnowledgeGraph();
    toast("布局已重置");
  };
  $("exportWiki").onclick = () => window.open("/api/evolution/wiki/export", "_blank");
  document.querySelectorAll("[data-theme-value]").forEach((button) => {
    button.onclick = () => {
      localStorage.setItem("clone_theme", button.dataset.themeValue);
      applyUi();
      toast(`主题已切换为：${button.textContent.trim()}`);
    };
  });
  document.querySelectorAll("[data-width-value]").forEach((button) => {
    button.onclick = () => {
      localStorage.setItem("clone_content_width", button.dataset.widthValue);
      applyUi();
    };
  });
  $("fontScale").oninput = (e) => {
    localStorage.setItem("clone_font_scale", e.target.value);
    applyUi();
  };
  $("motionSetting").onchange = (e) => {
    localStorage.setItem("clone_reduce_motion", e.target.checked ? "true" : "false");
    applyUi();
  };
  $("resetUi").onclick = () => {
    localStorage.removeItem("clone_theme");
    localStorage.removeItem("clone_font_scale");
    localStorage.removeItem("clone_content_width");
    localStorage.removeItem("clone_reduce_motion");
    applyUi();
  };
  document.querySelectorAll(".tab").forEach((tab) => {
    tab.onclick = () => {
      document.querySelectorAll(".tab").forEach((x) => x.classList.remove("active"));
      document.querySelectorAll(".side-panel").forEach((x) => x.classList.remove("active"));
      tab.classList.add("active");
      $(`panel-${tab.dataset.tab}`).classList.add("active");
      if (tab.dataset.tab === "trash") loadTrash();
      $("sidebar").classList.toggle("knowledge-expanded", tab.dataset.tab === "knowledge");
      if (tab.dataset.tab === "knowledge") loadKnowledge();
      if (tab.dataset.tab === "settings") loadSettings();
    };
  });
  document.body.addEventListener("click", async (event) => {
    if (!event.target.closest("#webSearchModeWrap")) {
      $("webSearchModeMenu").classList.remove("open");
      $("webSearchBtn").setAttribute("aria-expanded", "false");
    }
    if (!event.target.closest(".user-menu-lite")) {
      const pop = $("userMenuPop");
      if (pop) pop.classList.remove("open");
      if ($("userMenuTop")) $("userMenuTop").setAttribute("aria-expanded", "false");
    }
    const target = event.target.closest("button");
    if (!target) return;
    if (target.id === "modalClose") {
      closeModal();
      return;
    }
    if (target.id === "closeInspector") {
      closeInspector();
      return;
    }
    if (target.dataset.removeFile) {
      state.files.splice(Number(target.dataset.removeFile), 1);
      renderPendingFiles();
      return;
    }
    if (target.dataset.open) openConversation(target.dataset.open);
    if (target.dataset.rename) {
      const title = prompt("新的会话标题");
      if (title) {
        await api(`/api/history/${target.dataset.rename}`, { method: "PATCH", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ title }) });
        loadHistory();
      }
    }
    if (target.dataset.delete) {
      await api(`/api/history/${target.dataset.delete}`, { method: "DELETE" });
      loadHistory();
      toast("已移入回收站");
    }
    if (target.dataset.restore) {
      await api(`/api/history/${target.dataset.restore}/restore`, { method: "POST" });
      loadTrash();
      loadHistory();
    }
    if (target.dataset.hardDelete) {
      await api(`/api/history/${target.dataset.hardDelete}?hard=1`, { method: "DELETE" });
      loadTrash();
    }
    if (target.dataset.kbOpen) openKnowledge(target.dataset.kbOpen);
    if (target.dataset.kbArchive) {
      await archiveKnowledgeNote(target.dataset.kbArchive);
    }
    if (target.dataset.memoryArchive) {
      await api(`/api/memories/${target.dataset.memoryArchive}/archive`, { method: "POST" });
      loadMemories();
    }
    if (target.dataset.memoryDelete) {
      await api(`/api/memories/${target.dataset.memoryDelete}`, { method: "DELETE" });
      loadMemories();
    }
    if (target.dataset.memoryEdit) {
      const text = prompt("编辑记忆内容");
      if (text) {
        await api(`/api/memories/${target.dataset.memoryEdit}`, { method: "PATCH", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ content: text }) });
        loadMemories();
      }
    }
    if (target.dataset.memoComplete) {
      await api(`/api/memos/${target.dataset.memoComplete}/complete`, { method: "POST" });
      openMemos();
    }
    if (target.dataset.memoDelete) {
      await api(`/api/memos/${target.dataset.memoDelete}`, { method: "DELETE" });
      openMemos();
    }
  });
}

async function boot() {
  applyUi();
  bindEvents();
  drawLife();
  await Promise.all([loadHistory(), loadSettings(), loadKnowledge()]);
  if (state.sessionId) {
    try { await openConversation(state.sessionId); } catch { state.sessionId = ""; }
  }
}

boot().catch((err) => toast(err.message));
