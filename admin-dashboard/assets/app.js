const API_ROOT = "/v1/admin";
const TOKEN_STORAGE_KEY = "northstar.admin.token";
const PAGE_LIMIT = 20;
const COURSES = ["CMA", "CPA", "CFA", "ACCA", "CS", "EA"];
const DOCUMENT_TYPES = ["lesson", "notes", "faq", "quiz", "job_hunt", "policy", "other"];
const DOCUMENT_STATUSES = ["draft", "queued", "indexing", "indexed", "failed", "deleting"];
const FEEDBACK_STATUSES = ["open", "reviewing", "resolved", "dismissed"];
const FEEDBACK_CATEGORIES = ["change", "error", "other"];

const ROUTES = {
  overview: { title: "Overview", eyebrow: "Workspace" },
  knowledge: { title: "Knowledge", eyebrow: "Content library" },
  training: { title: "Training", eyebrow: "RAG operations" },
  feedback: { title: "Feedback", eyebrow: "Student voice" },
  conversations: { title: "Conversations", eyebrow: "WhatsApp inbox" },
  enrollments: { title: "Enrollments", eyebrow: "WhatsApp access" },
  analytics: { title: "Analytics", eyebrow: "Student usage" },
  activity: { title: "Activity", eyebrow: "Audit trail" },
  configuration: { title: "Configuration", eyebrow: "System behavior" },
};

const ICONS = {
  alert: '<path d="M12 3 2.8 20h18.4L12 3Z"/><path d="M12 9v4M12 17h.01"/>',
  arrow: '<path d="m9 18 6-6-6-6"/>',
  book: '<path d="M4 4.5A2.5 2.5 0 0 1 6.5 2H20v17H6.5A2.5 2.5 0 0 0 4 21.5v-17Z"/><path d="M4 21.5A2.5 2.5 0 0 1 6.5 19H20"/>',
  check: '<path d="m5 12 4 4L19 6"/>',
  close: '<path d="m6 6 12 12M18 6 6 18"/>',
  download: '<path d="M12 3v12m0 0 4-4m-4 4-4-4M5 21h14"/>',
  edit: '<path d="M13.5 6.5 17.5 10.5M4 20l4.2-1 10.3-10.3a2.8 2.8 0 0 0-4-4L4.2 15 4 20Z"/>',
  file: '<path d="M6 2h8l4 4v16H6z"/><path d="M14 2v5h5M9 12h6M9 16h6"/>',
  filter: '<path d="M4 5h16l-6.5 7.2V19l-3 1v-7.8L4 5Z"/>',
  image: '<rect x="3" y="4" width="18" height="16" rx="2"/><circle cx="9" cy="10" r="2"/><path d="m4 17 5-4 3 3 2-2 6 5"/>',
  info: '<circle cx="12" cy="12" r="9"/><path d="M12 11v5M12 8h.01"/>',
  message: '<path d="M21 15a3 3 0 0 1-3 3H9l-6 4V6a3 3 0 0 1 3-3h12a3 3 0 0 1 3 3v9Z"/>',
  phone: '<path d="M7 3H4.5A1.5 1.5 0 0 0 3 4.5C3 13.6 10.4 21 19.5 21a1.5 1.5 0 0 0 1.5-1.5V17l-4-1-1.2 2a15 15 0 0 1-9.8-9.8L8 7 7 3Z"/>',
  plus: '<path d="M12 5v14M5 12h14"/>',
  refresh: '<path d="M20 6v5h-5M4 18v-5h5"/><path d="M18.5 9A7 7 0 0 0 6 6.5L4 9m2 6a7 7 0 0 0 12 2.5L20 15"/>',
  search: '<circle cx="11" cy="11" r="7"/><path d="m20 20-4-4"/>',
  settings: '<circle cx="12" cy="12" r="3"/><path d="M19 12h3M2 12h3M12 2v3M12 19v3M17 7l2-2M5 19l2-2M17 17l2 2M5 5l2 2"/>',
  spark: '<path d="m12 3 1.7 5.3L19 10l-5.3 1.7L12 17l-1.7-5.3L5 10l5.3-1.7L12 3Z"/><path d="m19 16 .8 2.2L22 19l-2.2.8L19 22l-.8-2.2L16 19l2.2-.8L19 16Z"/>',
  trash: '<path d="M4 7h16M9 3h6l1 4H8l1-4ZM7 7l1 14h8l1-14M10 11v6M14 11v6"/>',
  upload: '<path d="M12 16V4m0 0L8 8m4-4 4 4M4 16v4h16v-4"/>',
  users: '<circle cx="9" cy="8" r="4"/><path d="M2.5 21v-2a5.5 5.5 0 0 1 5.5-5.5h2a5.5 5.5 0 0 1 5.5 5.5v2M17 8h5M19.5 5.5v5"/>',
};

const elements = {
  loginView: document.querySelector("#login-view"),
  loginForm: document.querySelector("#login-form"),
  loginToken: document.querySelector("#admin-token"),
  loginError: document.querySelector("#login-error"),
  loginSubmit: document.querySelector("#login-submit"),
  toggleToken: document.querySelector("#toggle-token"),
  app: document.querySelector("#dashboard-app"),
  sidebar: document.querySelector("#sidebar"),
  sidebarBackdrop: document.querySelector("#sidebar-backdrop"),
  menuButton: document.querySelector("#menu-button"),
  logoutButton: document.querySelector("#logout-button"),
  refreshButton: document.querySelector("#refresh-button"),
  pageTitle: document.querySelector("#page-title"),
  pageEyebrow: document.querySelector("#page-eyebrow"),
  lastUpdated: document.querySelector("#last-updated"),
  connectionLabel: document.querySelector("#connection-label"),
  feedbackNavCount: document.querySelector("#feedback-nav-count"),
  viewRoot: document.querySelector("#view-root"),
  progress: document.querySelector("#route-progress"),
  dialog: document.querySelector("#app-dialog"),
  dialogTitle: document.querySelector("#dialog-title"),
  dialogEyebrow: document.querySelector("#dialog-eyebrow"),
  dialogBody: document.querySelector("#dialog-body"),
  dialogClose: document.querySelector("#dialog-close"),
  toastRegion: document.querySelector("#toast-region"),
};

const state = {
  authenticated: false,
  route: "overview",
  sequence: 0,
  overview: null,
  documents: [],
  jobs: [],
  approvedAnswers: [],
  feedback: [],
  conversations: [],
  configuration: null,
  enrollment: null,
  enrollmentRoster: [],
  enrollmentSource: "",
  whatsappStatus: null,
  analytics: null,
  auditEvents: [],
  enrollmentPhone: "",
  selectedDocumentIds: new Set(),
  knowledgeFilters: { search: "", course: "", status: "" },
  feedbackFilters: { search: "", category: "", status: "" },
  conversationFilters: { search: "" },
  activityFilters: { search: "" },
  pages: {
    knowledge: { limit: PAGE_LIMIT, offset: 0, total: 0, count: 0 },
    trainingDocuments: { limit: PAGE_LIMIT, offset: 0, total: 0, count: 0 },
    trainingJobs: { limit: PAGE_LIMIT, offset: 0, total: 0, count: 0 },
    approvedAnswers: { limit: PAGE_LIMIT, offset: 0, total: 0, count: 0 },
    feedback: { limit: PAGE_LIMIT, offset: 0, total: 0, count: 0 },
    conversations: { limit: PAGE_LIMIT, offset: 0, total: 0, count: 0 },
    activity: { limit: PAGE_LIMIT, offset: 0, total: 0, count: 0 },
  },
  trainingPoll: null,
  conversationPoll: null,
  conversationsRenderedSignature: "",
  conversationFocusTarget: null,
  activeConversationId: null,
  activeConversationSignature: "",
};

class ApiError extends Error {
  constructor(message, status, details = null) {
    super(message);
    this.name = "ApiError";
    this.status = status;
    this.details = details;
  }
}

function icon(name, className = "icon") {
  return `<svg class="${className}" viewBox="0 0 24 24" aria-hidden="true">${ICONS[name] || ICONS.info}</svg>`;
}

function escapeHtml(value) {
  return String(value ?? "")
    .replaceAll("&", "&amp;")
    .replaceAll("<", "&lt;")
    .replaceAll(">", "&gt;")
    .replaceAll('"', "&quot;")
    .replaceAll("'", "&#039;");
}

function humanize(value) {
  return String(value ?? "")
    .replaceAll("_", " ")
    .replaceAll("-", " ")
    .replace(/\b\w/g, (letter) => letter.toUpperCase());
}

function statusClass(value) {
  return String(value || "plain").toLowerCase().replaceAll("_", "-").replace(/[^a-z0-9-]/g, "");
}

function badge(value, plain = false) {
  const label = humanize(value || "Unknown");
  return `<span class="badge badge--${statusClass(value)}${plain ? " badge--plain" : ""}">${escapeHtml(label)}</span>`;
}

function formatNumber(value) {
  const number = Number(value);
  return Number.isFinite(number) ? new Intl.NumberFormat().format(number) : String(value || "—");
}

function formatDate(value, includeTime = true) {
  if (!value) return "—";
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return String(value);
  return new Intl.DateTimeFormat(undefined, {
    dateStyle: "medium",
    ...(includeTime ? { timeStyle: "short" } : {}),
  }).format(date);
}

function formatBytes(value) {
  const bytes = Number(value);
  if (!Number.isFinite(bytes) || bytes < 0) return "—";
  if (bytes < 1024) return `${bytes} B`;
  const units = ["KB", "MB", "GB"];
  let size = bytes / 1024;
  let unit = units[0];
  for (let index = 1; index < units.length && size >= 1024; index += 1) {
    size /= 1024;
    unit = units[index];
  }
  return `${size >= 10 ? size.toFixed(0) : size.toFixed(1)} ${unit}`;
}

function resetPage(pageKey) {
  state.pages[pageKey].offset = 0;
}

function applyPageResult(pageKey, total, count) {
  const page = state.pages[pageKey];
  page.total = Math.max(0, Number(total) || 0);
  page.count = Math.max(0, Number(count) || 0);
  if (page.total > 0 && page.count === 0 && page.offset >= page.total) {
    page.offset = Math.floor((page.total - 1) / page.limit) * page.limit;
    return false;
  }
  return true;
}

function paginationMarkup(pageKey, itemLabel) {
  const page = state.pages[pageKey];
  const first = page.count ? page.offset + 1 : 0;
  const last = page.count ? page.offset + page.count : 0;
  const currentPage = page.total ? Math.floor(page.offset / page.limit) + 1 : 1;
  const pageCount = Math.max(1, Math.ceil(page.total / page.limit));
  return `
    <nav class="pagination" aria-label="${escapeHtml(itemLabel)} pagination">
      <p class="pagination__range" role="status">Showing ${formatNumber(first)}–${formatNumber(last)} of ${formatNumber(page.total)} ${escapeHtml(itemLabel.toLowerCase())}<span> · Page ${formatNumber(currentPage)} of ${formatNumber(pageCount)}</span></p>
      <div class="pagination__controls">
        <button class="button button--secondary button--small" type="button" data-page-key="${escapeHtml(pageKey)}" data-page-direction="previous" aria-label="Previous page of ${escapeHtml(itemLabel.toLowerCase())}"${page.offset <= 0 ? " disabled" : ""}>Previous</button>
        <button class="button button--secondary button--small" type="button" data-page-key="${escapeHtml(pageKey)}" data-page-direction="next" aria-label="Next page of ${escapeHtml(itemLabel.toLowerCase())}"${page.offset + page.count >= page.total ? " disabled" : ""}>Next</button>
      </div>
    </nav>`;
}

function bindPagination(root = document) {
  root.querySelectorAll("[data-page-key]").forEach((button) => button.addEventListener("click", () => {
    const pageKey = button.dataset.pageKey;
    const page = state.pages[pageKey];
    if (!page) return;
    const delta = button.dataset.pageDirection === "next" ? page.limit : -page.limit;
    page.offset = Math.max(0, page.offset + delta);
    if (pageKey === "conversations") {
      state.conversationFocusTarget = { type: "page", direction: button.dataset.pageDirection };
    }
    loadRoute();
  }));
}

function truncate(value, maximum = 90) {
  const text = String(value ?? "").trim();
  return text.length > maximum ? `${text.slice(0, maximum - 1)}…` : text;
}

function options(values, selected = "", labels = {}) {
  return values.map((value) => (
    `<option value="${escapeHtml(value)}"${String(selected) === String(value) ? " selected" : ""}>${escapeHtml(labels[value] || humanize(value))}</option>`
  )).join("");
}

function debounce(callback, wait = 300) {
  let timer;
  return (...args) => {
    window.clearTimeout(timer);
    timer = window.setTimeout(() => callback(...args), wait);
  };
}

function setButtonBusy(button, busy) {
  if (!button) return;
  button.disabled = busy;
  button.classList.toggle("is-loading", busy);
  button.setAttribute("aria-busy", String(busy));
}

function setProgress(active) {
  elements.progress.classList.toggle("is-loading", active);
}

function showToast(title, message = "", type = "success") {
  const toast = document.createElement("div");
  toast.className = `toast toast--${type}`;
  const toastIcon = document.createElementNS("http://www.w3.org/2000/svg", "svg");
  toastIcon.setAttribute("class", "toast__icon icon");
  toastIcon.setAttribute("viewBox", "0 0 24 24");
  toastIcon.setAttribute("aria-hidden", "true");
  toastIcon.innerHTML = type === "error" ? ICONS.alert : ICONS.check;
  const copy = document.createElement("span");
  const strong = document.createElement("strong");
  strong.textContent = title;
  copy.append(strong);
  if (message) {
    const small = document.createElement("small");
    small.textContent = message;
    copy.append(small);
  }
  toast.append(toastIcon, copy);
  elements.toastRegion.append(toast);
  window.setTimeout(() => {
    toast.classList.add("is-leaving");
    window.setTimeout(() => toast.remove(), 190);
  }, 4800);
}

function errorMessage(payload, fallback) {
  const detail = payload?.detail;
  if (typeof detail === "string") return detail;
  if (Array.isArray(detail)) {
    return detail.map((item) => item?.msg || String(item)).join("; ");
  }
  if (typeof payload?.message === "string") return payload.message;
  return fallback;
}

async function apiRequest(path, { method = "GET", body, headers = {}, responseType = "json" } = {}) {
  const token = sessionStorage.getItem(TOKEN_STORAGE_KEY);
  const requestHeaders = new Headers(headers);
  if (token) requestHeaders.set("X-Admin-Token", token);
  let requestBody = body;
  if (body !== undefined && body !== null && !(body instanceof FormData) && !(body instanceof Blob)) {
    requestHeaders.set("Content-Type", "application/json");
    requestBody = JSON.stringify(body);
  }

  let response;
  try {
    response = await fetch(`${API_ROOT}${path}`, {
      method,
      headers: requestHeaders,
      body: requestBody,
      credentials: "same-origin",
      cache: "no-store",
    });
  } catch (error) {
    throw new ApiError("The admin API could not be reached. Check the service and try again.", 0, error);
  }

  if (!response.ok) {
    let payload = null;
    try { payload = await response.json(); } catch { /* Response may have no JSON body. */ }
    throw new ApiError(errorMessage(payload, `Request failed (${response.status})`), response.status, payload);
  }

  if (response.status === 204) return null;
  if (responseType === "blob") return response.blob();
  if (responseType === "text") return response.text();
  return response.json();
}

function openDialog({ title, eyebrow = "", content, onOpen }) {
  elements.dialogTitle.textContent = title;
  elements.dialogEyebrow.textContent = eyebrow;
  elements.dialogEyebrow.hidden = !eyebrow;
  elements.dialogBody.innerHTML = content;
  if (!elements.dialog.open) elements.dialog.showModal();
  onOpen?.(elements.dialogBody);
}

function closeDialog() {
  if (elements.dialog.open) elements.dialog.close();
  elements.dialogBody.innerHTML = "";
  elements.dialog.classList.remove("dialog--conversation");
  state.activeConversationId = null;
  state.activeConversationSignature = "";
}

function confirmAction({ title, message, confirmLabel = "Confirm", danger = false }) {
  return new Promise((resolve) => {
    let settled = false;
    const settle = (value, close = true) => {
      if (settled) return;
      settled = true;
      elements.dialog.removeEventListener("close", handleDialogClose);
      if (close) closeDialog();
      resolve(value);
    };
    const handleDialogClose = () => settle(false, false);

    openDialog({
      title,
      eyebrow: danger ? "Please confirm" : "Confirmation",
      content: `
        <p class="confirm-copy">${message}</p>
        <div class="confirm-actions">
          <button class="button button--secondary" type="button" data-confirm="cancel">Cancel</button>
          <button class="button ${danger ? "button--danger-solid" : "button--primary"}" type="button" data-confirm="yes">${escapeHtml(confirmLabel)}</button>
        </div>`,
      onOpen: (root) => {
        root.querySelector('[data-confirm="cancel"]').addEventListener("click", () => {
          settle(false);
        });
        root.querySelector('[data-confirm="yes"]').addEventListener("click", () => {
          settle(true);
        });
      },
    });
    elements.dialog.addEventListener("close", handleDialogClose, { once: true });
  });
}

function loadingMarkup() {
  return `<div class="skeleton-grid" aria-label="Loading dashboard"><div class="skeleton"></div><div class="skeleton"></div><div class="skeleton"></div><div class="skeleton"></div></div>`;
}

function emptyMarkup(title, message, action = "") {
  return `
    <div class="empty-state">
      <div class="state-content">
        <span class="state-icon">${icon("book")}</span>
        <h2>${escapeHtml(title)}</h2>
        <p>${escapeHtml(message)}</p>
        ${action}
      </div>
    </div>`;
}

function errorMarkup(error) {
  return `
    <div class="panel error-state" role="alert">
      <div class="state-content">
        <span class="state-icon">${icon("alert")}</span>
        <h2>We couldn’t load this view</h2>
        <p>${escapeHtml(error.message || "An unexpected error occurred.")}</p>
        <button class="button button--secondary" type="button" data-action="retry">${icon("refresh")}<span>Try again</span></button>
      </div>
    </div>`;
}

function renderRouteError(error) {
  if (error.status === 401) {
    signOut("Your admin session is no longer valid. Sign in again.");
    return;
  }
  elements.connectionLabel.textContent = error.status === 0 ? "Unavailable" : "Request error";
  elements.viewRoot.innerHTML = errorMarkup(error);
  elements.viewRoot.querySelector('[data-action="retry"]')?.addEventListener("click", () => loadRoute(true));
}

function setActiveNavigation(route) {
  document.querySelectorAll("[data-route]").forEach((button) => {
    const active = button.dataset.route === route;
    button.classList.toggle("is-active", active);
    if (active) button.setAttribute("aria-current", "page");
    else button.removeAttribute("aria-current");
  });
  const meta = ROUTES[route];
  elements.pageTitle.textContent = meta.title;
  elements.pageEyebrow.textContent = meta.eyebrow;
  document.title = `${meta.title} · NorthStar Control Center`;
}

function closeMobileNavigation() {
  elements.sidebar.classList.remove("is-open");
  elements.sidebarBackdrop.hidden = true;
  elements.menuButton.setAttribute("aria-expanded", "false");
  document.body.style.overflow = "";
}

function openMobileNavigation() {
  elements.sidebar.classList.add("is-open");
  elements.sidebarBackdrop.hidden = false;
  elements.menuButton.setAttribute("aria-expanded", "true");
  document.body.style.overflow = "hidden";
}

function navigate(route) {
  const safeRoute = ROUTES[route] ? route : "overview";
  if (location.hash.slice(1) === safeRoute) loadRoute();
  else location.hash = safeRoute;
  closeMobileNavigation();
}

function updateTimestamp() {
  elements.lastUpdated.textContent = `Updated ${new Intl.DateTimeFormat(undefined, { hour: "numeric", minute: "2-digit" }).format(new Date())}`;
  elements.connectionLabel.textContent = "Connected";
}

function retrievalEnabled() {
  return state.overview?.retrieval_enabled === true;
}

function retrievalWarningMarkup() {
  if (retrievalEnabled()) return "";
  return `
    <div class="notice notice--warning notice--blocking" role="alert">
      ${icon("alert")}
      <span class="notice__content"><strong>Knowledge retrieval is disabled.</strong> RAG indexing is blocked until Course retrieval is enabled in Configuration.</span>
      <button class="button button--secondary button--small notice__action" type="button" data-enable-retrieval>${icon("settings")}<span>Open configuration</span></button>
    </div>`;
}

function bindRetrievalWarning(root = document) {
  root.querySelectorAll("[data-enable-retrieval]").forEach((button) => button.addEventListener("click", () => navigate("configuration")));
}

function stopTrainingPoll() {
  window.clearTimeout(state.trainingPoll);
  state.trainingPoll = null;
}

function stopConversationPoll() {
  window.clearTimeout(state.conversationPoll);
  state.conversationPoll = null;
}

function conversationPollAllowed() {
  return state.authenticated && state.route === "conversations" && document.visibilityState === "visible";
}

function scheduleConversationPoll() {
  stopConversationPoll();
  if (!conversationPollAllowed()) return;
  state.conversationPoll = window.setTimeout(pollConversationInbox, 10000);
}

async function loadRoute(force = false) {
  if (!state.authenticated) return;
  const requested = location.hash.slice(1);
  const route = ROUTES[requested] ? requested : "overview";
  if (requested !== route) {
    history.replaceState(null, "", `#${route}`);
  }
  state.route = route;
  if (route !== "conversations") state.conversationFocusTarget = null;
  if (force && route !== "overview") state.overview = null;
  state.sequence += 1;
  const sequence = state.sequence;
  stopTrainingPoll();
  stopConversationPoll();
  if (route !== "conversations" && state.activeConversationId) closeDialog();
  setActiveNavigation(route);
  elements.viewRoot.innerHTML = loadingMarkup();
  setProgress(true);
  let routeConnectionHealthy = true;

  try {
    if (route === "overview") await loadOverview(sequence, force);
    if (route === "knowledge") await loadKnowledge(sequence);
    if (route === "training") await loadTraining(sequence);
    if (route === "feedback") await loadFeedback(sequence);
    if (route === "conversations") {
      await loadConversations(sequence);
      if (state.activeConversationId && elements.dialog.open) {
        routeConnectionHealthy = await refreshConversationThread(state.activeConversationId, { silent: true });
      }
      scheduleConversationPoll();
    }
    if (route === "enrollments") {
      const [roster, whatsappStatus] = await Promise.all([
        apiRequest("/whatsapp/enrollments?limit=200&offset=0"),
        apiRequest("/whatsapp/status"),
      ]);
      state.enrollmentRoster = Array.isArray(roster.items) ? roster.items : [];
      state.enrollmentSource = roster.source || "";
      state.whatsappStatus = whatsappStatus;
      if (force && state.enrollmentPhone) {
        state.enrollment = await apiRequest(`/whatsapp/enrollments/${encodeURIComponent(state.enrollmentPhone)}`);
      }
      renderEnrollments();
    }
    if (route === "analytics") await loadAnalytics(sequence);
    if (route === "activity") await loadActivity(sequence);
    if (route === "configuration") await loadConfiguration(sequence);
    if (sequence === state.sequence && routeConnectionHealthy) updateTimestamp();
  } catch (error) {
    if (sequence === state.sequence) renderRouteError(error);
  } finally {
    if (sequence === state.sequence) setProgress(false);
  }
}

function statCard(label, value, meta, iconName, tone = "") {
  return `
    <article class="stat-card${tone ? ` stat-card--${tone}` : ""}">
      <div class="stat-card__top"><span class="stat-card__icon">${icon(iconName)}</span></div>
      <p class="stat-card__label">${escapeHtml(label)}</p>
      <p class="stat-card__value">${escapeHtml(formatNumber(value))}</p>
      <p class="stat-card__meta">${escapeHtml(meta)}</p>
    </article>`;
}

function jobRows(jobs, compact = false) {
  return jobs.map((job) => {
    const total = Number(job.total_documents) || 0;
    const completed = Number(job.completed_documents) || 0;
    const failed = Number(job.failed_documents) || 0;
    const percent = total ? Math.min(100, Math.round(((completed + failed) / total) * 100)) : 0;
    const retryable = !compact && ["failed", "partial"].includes(job.status);
    return `
      <tr>
        <td><span class="table-primary">Job ${escapeHtml(String(job.id || "").slice(0, 8))}</span><span class="table-secondary">${escapeHtml(formatDate(job.created_at))}</span></td>
        <td>${badge(job.status)}${job.error_message ? `<span class="table-secondary text-danger" title="${escapeHtml(job.error_message)}">${escapeHtml(truncate(job.error_message, 84))}</span>` : ""}${retryable ? `<button class="button button--ghost button--small job-retry" type="button" data-job-retry="${escapeHtml(job.id)}">Retry</button>` : ""}</td>
        <td>${formatNumber(total)}</td>
        ${compact ? "" : `<td><div class="progress-track" title="${percent}% complete"><span style="--progress:${percent}%"></span></div><span class="table-secondary">${completed} complete · ${failed} failed</span></td>`}
        <td>${formatNumber(job.total_chunks || 0)}</td>
      </tr>`;
  }).join("");
}

async function loadOverview(sequence, force) {
  const data = state.overview && !force ? state.overview : await apiRequest("/overview");
  if (sequence !== state.sequence) return;
  state.overview = data;
  const openFeedback = Number(data.open_feedback) || 0;
  elements.feedbackNavCount.hidden = openFeedback === 0;
  elements.feedbackNavCount.textContent = openFeedback > 99 ? "99+" : String(openFeedback);

  const latestJobs = Array.isArray(data.latest_jobs) ? data.latest_jobs : [];
  elements.viewRoot.innerHTML = `
    <header class="section-heading">
      <div><span class="eyebrow">At a glance</span><h2>Mentor operations</h2><p>Monitor the content and feedback workflows that shape the student experience.</p></div>
      <div class="section-heading__actions"><button class="button button--primary" type="button" data-action="overview-upload">${icon("upload")}<span>Add knowledge</span></button></div>
    </header>
    <section class="stat-grid" aria-label="Key metrics">
      ${statCard("Knowledge documents", data.documents, "Editable source documents", "book")}
      ${statCard("Indexed documents", data.indexed_documents, "Available to RAG retrieval", "spark", "blue")}
      ${statCard("Open feedback", data.open_feedback, "Needs review or resolution", "message", "coral")}
      ${statCard("Active training jobs", data.active_jobs, "Queued or currently indexing", "refresh", "warm")}
    </section>
    <div class="overview-grid">
      <section class="panel">
        <div class="panel__header"><div><h2>Recent training activity</h2><p>Latest knowledge indexing jobs</p></div><button class="button button--ghost button--small" type="button" data-route-link="training">View all ${icon("arrow")}</button></div>
        <div class="panel__body panel__body--flush">
          ${latestJobs.length ? `<div class="data-table-wrap"><table class="data-table"><thead><tr><th>Job</th><th>Status</th><th>Documents</th><th>Chunks</th></tr></thead><tbody>${jobRows(latestJobs, true)}</tbody></table></div>` : emptyMarkup("No training jobs yet", "Upload a document, then index it when it is ready.")}
        </div>
      </section>
      <div>
        <section class="panel">
          <div class="panel__header"><div><h2>Quick actions</h2><p>Common operational tasks</p></div></div>
          <div class="quick-actions">
            <button class="quick-action" type="button" data-route-link="knowledge"><span class="quick-action__icon">${icon("book")}</span><span><strong>Manage knowledge</strong><small>Upload and edit mentor sources</small></span></button>
            <button class="quick-action" type="button" data-route-link="training"><span class="quick-action__icon">${icon("spark")}</span><span><strong>Start indexing</strong><small>Train retrieval on selected sources</small></span></button>
            <button class="quick-action" type="button" data-route-link="feedback"><span class="quick-action__icon">${icon("message")}</span><span><strong>Review feedback</strong><small>Resolve student-reported issues</small></span></button>
            <button class="quick-action" type="button" data-route-link="configuration"><span class="quick-action__icon">${icon("settings")}</span><span><strong>Tune behavior</strong><small>Edit safe runtime settings</small></span></button>
          </div>
        </section>
        <section class="panel">
          <div class="panel__header"><div><h2>System snapshot</h2><p>Non-sensitive runtime information</p></div></div>
          <ul class="health-list">
            <li><span class="health-list__name">Environment</span>${badge(data.environment || "unknown", true)}</li>
            <li><span class="health-list__name">Retrieval</span>${badge(data.retrieval_enabled ? "active" : "disabled")}</li>
            <li><span class="health-list__name">Embedding</span><strong>${escapeHtml(humanize(data.embedding_provider || "unknown"))}</strong></li>
            <li><span class="health-list__name">Feedback number</span>${badge(data.feedback_number_configured ? "configured" : "not configured", true)}</li>
          </ul>
        </section>
      </div>
    </div>`;

  elements.viewRoot.querySelector('[data-action="overview-upload"]')?.addEventListener("click", openUploadDialog);
  elements.viewRoot.querySelectorAll("[data-route-link]").forEach((button) => button.addEventListener("click", () => navigate(button.dataset.routeLink)));
}

function documentRows(items) {
  return items.map((document) => {
    const id = String(document.id || "");
    const checked = state.selectedDocumentIds.has(id);
    const active = ["queued", "indexing"].includes(document.status);
    return `
      <tr>
        <td><input class="checkbox" type="checkbox" value="${escapeHtml(id)}" data-document-select aria-label="Select ${escapeHtml(document.title || document.filename)}"${checked ? " checked" : ""}${active ? " disabled" : ""}></td>
        <td><div class="data-table__title"><span class="file-icon">${icon("file")}</span><span><span class="table-primary" title="${escapeHtml(document.title || "Untitled")}">${escapeHtml(document.title || "Untitled")}</span><span class="table-secondary">${escapeHtml(document.filename || "Source document")}</span></span></div></td>
        <td>${badge(document.course, true)}</td>
        <td>${escapeHtml(humanize(document.doc_type))}</td>
        <td>${badge(document.status)}${document.error_message ? `<span class="table-secondary text-danger" title="${escapeHtml(document.error_message)}">${escapeHtml(truncate(document.error_message, 84))}</span>` : ""}</td>
        <td><span class="table-primary">${formatNumber(document.chunk_count || 0)}</span><span class="table-secondary">${formatNumber(document.character_count || 0)} characters</span></td>
        <td><span class="table-primary">${escapeHtml(formatDate(document.updated_at, false))}</span><span class="table-secondary">v${formatNumber(document.version || 1)}</span></td>
        <td><div class="table-actions"><button class="icon-button" type="button" data-document-edit="${escapeHtml(id)}" aria-label="Edit ${escapeHtml(document.title || "document")}">${icon("edit")}</button><button class="icon-button text-danger" type="button" data-document-delete="${escapeHtml(id)}" aria-label="Delete ${escapeHtml(document.title || "document")}"${active ? " disabled title=\"Training is active\"" : ""}>${icon("trash")}</button></div></td>
      </tr>`;
  }).join("");
}

function knowledgeQuery() {
  const page = state.pages.knowledge;
  const query = new URLSearchParams({ limit: String(page.limit), offset: String(page.offset) });
  Object.entries(state.knowledgeFilters).forEach(([key, value]) => { if (value) query.set(key, value); });
  return query.toString();
}

async function loadKnowledge(sequence = state.sequence) {
  const [payload, overview] = await Promise.all([
    apiRequest(`/knowledge/documents?${knowledgeQuery()}`),
    apiRequest("/overview"),
  ]);
  if (sequence !== state.sequence) return;
  state.overview = overview;
  state.documents = Array.isArray(payload.items) ? payload.items : [];
  if (!applyPageResult("knowledge", payload.total ?? state.documents.length, state.documents.length)) {
    await loadKnowledge(sequence);
    return;
  }
  renderKnowledge(state.pages.knowledge.total);
}

function renderKnowledge(total) {
  const filters = state.knowledgeFilters;
  const hasFilters = Boolean(filters.search || filters.course || filters.status);
  elements.viewRoot.innerHTML = `
    <header class="section-heading">
      <div><span class="eyebrow">Source of truth</span><h2>Knowledge library</h2><p>Upload, inspect, and edit the source material used by the mentor’s retrieval layer.</p></div>
      <div class="section-heading__actions">
        <button id="train-selected" class="button button--secondary" type="button"${state.selectedDocumentIds.size && retrievalEnabled() ? "" : " disabled"}${retrievalEnabled() ? "" : ' title="Enable course retrieval before indexing"'}>${icon("spark")}<span>Train selected${state.selectedDocumentIds.size ? ` (${state.selectedDocumentIds.size})` : ""}</span></button>
        <button id="upload-documents" class="button button--primary" type="button">${icon("upload")}<span>Upload documents</span></button>
      </div>
    </header>
    ${retrievalWarningMarkup()}
    <section class="panel">
      <div class="toolbar">
        <label class="toolbar__search"><span class="sr-only">Search documents</span>${icon("search")}<input id="knowledge-search" type="search" value="${escapeHtml(filters.search)}" placeholder="Search title or filename…"></label>
        <select id="knowledge-course" class="select" aria-label="Filter by course"><option value="">All courses</option>${options(COURSES, filters.course)}</select>
        <select id="knowledge-status" class="select" aria-label="Filter by status"><option value="">All statuses</option>${options(DOCUMENT_STATUSES, filters.status)}</select>
        <span class="toolbar__count">${formatNumber(total)} document${Number(total) === 1 ? "" : "s"}</span>
      </div>
      <div class="panel__body panel__body--flush">
        ${state.documents.length ? `<div class="data-table-wrap"><table class="data-table"><thead><tr><th><input id="select-all-documents" class="checkbox" type="checkbox" aria-label="Select all available documents on this page"></th><th>Document</th><th>Course</th><th>Type</th><th>Status</th><th>Indexed content</th><th>Updated</th><th><span class="sr-only">Actions</span></th></tr></thead><tbody>${documentRows(state.documents)}</tbody></table></div>` : emptyMarkup(hasFilters ? "No matching documents" : "Your knowledge library is empty", hasFilters ? "Try a broader search or clear one of the filters." : "Upload TXT, Markdown, PDF, or DOCX material to begin building the library.", hasFilters ? '<button class="button button--secondary" type="button" data-action="clear-knowledge-filters">Clear filters</button>' : '<button class="button button--primary" type="button" data-action="empty-upload">Upload documents</button>')}
      </div>
      ${paginationMarkup("knowledge", "Knowledge documents")}
    </section>`;
  bindKnowledgeEvents();
}

function updateKnowledgeSelectionControls() {
  const button = document.querySelector("#train-selected");
  if (!button) return;
  button.disabled = state.selectedDocumentIds.size === 0 || !retrievalEnabled();
  const label = button.querySelector("span");
  if (label) label.textContent = `Train selected${state.selectedDocumentIds.size ? ` (${state.selectedDocumentIds.size})` : ""}`;
  const checkboxes = [...document.querySelectorAll("[data-document-select]:not(:disabled)")];
  const selectAll = document.querySelector("#select-all-documents");
  if (selectAll) {
    const selected = checkboxes.filter((checkbox) => checkbox.checked).length;
    selectAll.checked = checkboxes.length > 0 && selected === checkboxes.length;
    selectAll.indeterminate = selected > 0 && selected < checkboxes.length;
  }
}

function bindKnowledgeEvents() {
  document.querySelector("#upload-documents")?.addEventListener("click", openUploadDialog);
  document.querySelector('[data-action="empty-upload"]')?.addEventListener("click", openUploadDialog);
  document.querySelector('[data-action="clear-knowledge-filters"]')?.addEventListener("click", () => {
    state.knowledgeFilters = { search: "", course: "", status: "" };
    resetPage("knowledge");
    loadRoute();
  });
  document.querySelector("#train-selected")?.addEventListener("click", async () => {
    const ids = [...state.selectedDocumentIds];
    if (!ids.length) return;
    await createTrainingJob(ids);
  });

  const runSearch = debounce((value) => {
    state.knowledgeFilters.search = value.trim();
    resetPage("knowledge");
    loadRoute();
  }, 350);
  document.querySelector("#knowledge-search")?.addEventListener("input", (event) => runSearch(event.target.value));
  document.querySelector("#knowledge-course")?.addEventListener("change", (event) => {
    state.knowledgeFilters.course = event.target.value;
    resetPage("knowledge");
    loadRoute();
  });
  document.querySelector("#knowledge-status")?.addEventListener("change", (event) => {
    state.knowledgeFilters.status = event.target.value;
    resetPage("knowledge");
    loadRoute();
  });
  document.querySelectorAll("[data-document-select]").forEach((checkbox) => checkbox.addEventListener("change", () => {
    if (checkbox.checked) state.selectedDocumentIds.add(checkbox.value);
    else state.selectedDocumentIds.delete(checkbox.value);
    updateKnowledgeSelectionControls();
  }));
  document.querySelector("#select-all-documents")?.addEventListener("change", (event) => {
    document.querySelectorAll("[data-document-select]:not(:disabled)").forEach((checkbox) => {
      checkbox.checked = event.target.checked;
      if (checkbox.checked) state.selectedDocumentIds.add(checkbox.value);
      else state.selectedDocumentIds.delete(checkbox.value);
    });
    updateKnowledgeSelectionControls();
  });
  document.querySelectorAll("[data-document-edit]").forEach((button) => button.addEventListener("click", () => openDocumentEditor(button.dataset.documentEdit)));
  document.querySelectorAll("[data-document-delete]").forEach((button) => button.addEventListener("click", () => deleteDocument(button.dataset.documentDelete)));
  bindRetrievalWarning(elements.viewRoot);
  bindPagination(elements.viewRoot);
  updateKnowledgeSelectionControls();
}

function openUploadDialog() {
  openDialog({
    title: "Upload knowledge",
    eyebrow: "New source documents",
    content: `
      <form id="upload-form" novalidate>
        <label id="upload-zone" class="upload-zone" for="knowledge-files">
          <span><span class="upload-zone__icon">${icon("upload")}</span><strong>Drop files here or choose from your device</strong><small>TXT, Markdown, PDF, or DOCX · up to the configured upload limit</small></span>
          <input id="knowledge-files" name="files" type="file" accept=".txt,.md,.pdf,.docx,text/plain,text/markdown,application/pdf,application/vnd.openxmlformats-officedocument.wordprocessingml.document" multiple required>
        </label>
        <ul id="selected-files" class="selected-files" hidden></ul>
        <div class="form-grid" style="margin-top:18px">
          <div class="field"><label for="upload-course">Course</label><select id="upload-course" name="course" required>${options(COURSES, "CMA")}</select></div>
          <div class="field"><label for="upload-type">Document type</label><select id="upload-type" name="doc_type" required>${options(DOCUMENT_TYPES, "lesson")}</select></div>
        </div>
        <p id="upload-error" class="form-error" role="alert" hidden></p>
        <div class="form-actions"><button class="button button--secondary" type="button" data-action="cancel-upload">Cancel</button><button id="upload-submit" class="button button--primary" type="submit"><span>Upload to library</span>${icon("upload")}</button></div>
      </form>`,
    onOpen: bindUploadDialog,
  });
}

function bindUploadDialog(root) {
  const form = root.querySelector("#upload-form");
  const input = root.querySelector("#knowledge-files");
  const list = root.querySelector("#selected-files");
  const zone = root.querySelector("#upload-zone");
  let selectedFiles = [];

  const renderFiles = () => {
    list.hidden = selectedFiles.length === 0;
    list.innerHTML = selectedFiles.map((file) => `<li>${icon("file")}<span class="truncate">${escapeHtml(file.name)}</span><span>${escapeHtml(formatBytes(file.size))}</span></li>`).join("");
  };
  input.addEventListener("change", () => {
    selectedFiles = [...input.files];
    renderFiles();
  });
  ["dragenter", "dragover"].forEach((name) => zone.addEventListener(name, (event) => {
    event.preventDefault();
    zone.classList.add("is-dragging");
  }));
  ["dragleave", "drop"].forEach((name) => zone.addEventListener(name, (event) => {
    event.preventDefault();
    zone.classList.remove("is-dragging");
  }));
  zone.addEventListener("drop", (event) => {
    selectedFiles = [...event.dataTransfer.files];
    renderFiles();
  });
  root.querySelector('[data-action="cancel-upload"]').addEventListener("click", closeDialog);
  form.addEventListener("submit", async (event) => {
    event.preventDefault();
    const error = root.querySelector("#upload-error");
    error.hidden = true;
    if (!selectedFiles.length) {
      error.textContent = "Choose at least one supported document.";
      error.hidden = false;
      return;
    }
    const submit = root.querySelector("#upload-submit");
    setButtonBusy(submit, true);
    const body = new FormData();
    selectedFiles.forEach((file) => body.append("files", file, file.name));
    body.append("course", root.querySelector("#upload-course").value);
    body.append("doc_type", root.querySelector("#upload-type").value);
    try {
      const result = await apiRequest("/knowledge/documents", { method: "POST", body });
      closeDialog();
      showToast("Documents uploaded", `${formatNumber(result.total || selectedFiles.length)} source document(s) are ready to review.`);
      state.overview = null;
      resetPage("knowledge");
      if (state.route === "knowledge") loadRoute(true);
      else navigate("knowledge");
    } catch (requestError) {
      error.textContent = requestError.message;
      error.hidden = false;
      setButtonBusy(submit, false);
    }
  });
}

async function openDocumentEditor(documentId) {
  openDialog({ title: "Loading document…", eyebrow: "Knowledge source", content: '<div class="loading-state"><div><div class="spinner"></div><p class="muted">Loading source text…</p></div></div>' });
  try {
    const document = await apiRequest(`/knowledge/documents/${encodeURIComponent(documentId)}`);
    elements.dialogTitle.textContent = "Edit document";
    elements.dialogBody.innerHTML = `
      <form id="document-edit-form" novalidate>
        <div class="form-grid">
          <div class="field field--full"><label for="document-title">Title</label><input id="document-title" name="title" maxlength="300" required value="${escapeHtml(document.title)}"></div>
          <div class="field"><label for="document-course">Course</label><select id="document-course" name="course" required>${options(COURSES, document.course)}</select></div>
          <div class="field"><label for="document-type">Document type</label><select id="document-type" name="doc_type" required>${options(DOCUMENT_TYPES, document.doc_type)}</select></div>
          <div class="field field--full"><label for="document-content">Source text</label><textarea id="document-content" name="content" rows="15" maxlength="2000000" required>${escapeHtml(document.content)}</textarea><p class="field-help">Saving a change marks this source as a draft. Run knowledge training to publish the updated retrieval index.</p></div>
        </div>
        <p id="document-edit-error" class="form-error" role="alert" hidden></p>
        <div class="form-actions"><button class="button button--secondary" type="button" data-action="cancel-edit">Cancel</button><button id="document-save" class="button button--primary" type="submit"><span>Save changes</span>${icon("check")}</button></div>
      </form>`;
    const root = elements.dialogBody;
    root.querySelector('[data-action="cancel-edit"]').addEventListener("click", closeDialog);
    root.querySelector("#document-edit-form").addEventListener("submit", async (event) => {
      event.preventDefault();
      const submit = root.querySelector("#document-save");
      const error = root.querySelector("#document-edit-error");
      error.hidden = true;
      const payload = {
        title: root.querySelector("#document-title").value.trim(),
        course: root.querySelector("#document-course").value,
        doc_type: root.querySelector("#document-type").value,
        content: root.querySelector("#document-content").value.trim(),
        version: Number(document.version),
      };
      if (!payload.title || !payload.content) {
        error.textContent = "Title and source text are required.";
        error.hidden = false;
        return;
      }
      setButtonBusy(submit, true);
      try {
        await apiRequest(`/knowledge/documents/${encodeURIComponent(documentId)}`, { method: "PUT", body: payload });
        closeDialog();
        showToast("Document updated", "Run knowledge training when the revised source is ready to publish.");
        state.overview = null;
        loadRoute(true);
      } catch (requestError) {
        error.textContent = requestError.status === 409 ? `${requestError.message}. Close and reopen this document to get the latest version.` : requestError.message;
        error.hidden = false;
        setButtonBusy(submit, false);
      }
    });
  } catch (error) {
    closeDialog();
    showToast("Could not open document", error.message, "error");
  }
}

async function deleteDocument(documentId) {
  const document = state.documents.find((item) => String(item.id) === String(documentId));
  const confirmed = await confirmAction({
    title: "Delete knowledge document?",
    message: `This permanently removes <strong>${escapeHtml(document?.title || "this document")}</strong> and its retrieval index. This action cannot be undone.`,
    confirmLabel: "Delete document",
    danger: true,
  });
  if (!confirmed) return;
  setProgress(true);
  try {
    await apiRequest(`/knowledge/documents/${encodeURIComponent(documentId)}`, { method: "DELETE" });
    state.selectedDocumentIds.delete(String(documentId));
    state.overview = null;
    showToast("Document deleted", "The source was removed from the knowledge library.");
    await loadRoute(true);
  } catch (error) {
    showToast("Delete failed", error.message, "error");
  } finally {
    setProgress(false);
  }
}

async function createTrainingJob(documentIds) {
  const uniqueIds = [...new Set(documentIds.filter(Boolean))];
  if (!uniqueIds.length) {
    showToast("No documents selected", "Choose at least one document to index.", "error");
    return;
  }
  setProgress(true);
  try {
    state.overview = await apiRequest("/overview");
    if (!retrievalEnabled()) {
      showToast("RAG indexing is disabled", "Enable Course retrieval in Configuration before starting a training job.", "error");
      if (["knowledge", "training"].includes(state.route)) await loadRoute(true);
      return null;
    }
    const job = await apiRequest("/training/jobs", { method: "POST", body: { document_ids: uniqueIds } });
    state.selectedDocumentIds.clear();
    state.overview = null;
    resetPage("trainingJobs");
    showToast("Training job queued", `${uniqueIds.length} document${uniqueIds.length === 1 ? " is" : "s are"} ready for RAG indexing.`);
    if (state.route === "training") await loadRoute(true);
    else navigate("training");
    return job;
  } catch (error) {
    showToast("Could not start training", error.message, "error");
    return null;
  } finally {
    setProgress(false);
  }
}

async function retryTrainingJob(jobId, button) {
  setButtonBusy(button, true);
  setProgress(true);
  try {
    const job = await apiRequest(`/training/jobs/${encodeURIComponent(jobId)}/retry`, { method: "POST" });
    state.overview = null;
    resetPage("trainingJobs");
    showToast("Training job requeued", `Retry job ${String(job.id || "").slice(0, 8)} is ready for indexing.`);
    await loadRoute(true);
  } catch (error) {
    showToast("Retry failed", error.message, "error");
    setButtonBusy(button, false);
  } finally {
    setProgress(false);
  }
}

async function loadTraining(sequence = state.sequence, quiet = false) {
  const documentPage = state.pages.trainingDocuments;
  const jobPage = state.pages.trainingJobs;
  const approvedPage = state.pages.approvedAnswers;
  const [documentsPayload, jobsPayload, overview, approvedPayload] = await Promise.all([
    apiRequest(`/knowledge/documents?limit=${documentPage.limit}&offset=${documentPage.offset}`),
    apiRequest(`/training/jobs?limit=${jobPage.limit}&offset=${jobPage.offset}`),
    apiRequest("/overview"),
    apiRequest(`/approved-answers?limit=${approvedPage.limit}&offset=${approvedPage.offset}`),
  ]);
  if (sequence !== state.sequence || state.route !== "training") return;
  state.overview = overview;
  state.documents = Array.isArray(documentsPayload.items) ? documentsPayload.items : [];
  state.jobs = Array.isArray(jobsPayload.items) ? jobsPayload.items : [];
  state.approvedAnswers = Array.isArray(approvedPayload.items) ? approvedPayload.items : [];
  const documentsInRange = applyPageResult("trainingDocuments", documentsPayload.total ?? state.documents.length, state.documents.length);
  const jobsInRange = applyPageResult("trainingJobs", jobsPayload.total ?? state.jobs.length, state.jobs.length);
  const approvedInRange = applyPageResult("approvedAnswers", approvedPayload.total ?? state.approvedAnswers.length, state.approvedAnswers.length);
  if (!documentsInRange || !jobsInRange || !approvedInRange) {
    await loadTraining(sequence, quiet);
    return;
  }
  renderTraining(state.pages.trainingJobs.total);
  if (!quiet) updateTimestamp();
  const hasActiveJobs = Number(state.overview?.active_jobs || 0) > 0
    || state.jobs.some((job) => ["queued", "running"].includes(job.status));
  if (hasActiveJobs) {
    state.trainingPoll = window.setTimeout(async () => {
      try {
        await loadTraining(state.sequence, true);
      } catch {
        state.trainingPoll = window.setTimeout(() => loadTraining(state.sequence, true), 7000);
      }
    }, 5000);
  }
}

function renderTraining(totalJobs) {
  const availableDocuments = state.documents.filter((document) => !["queued", "indexing"].includes(document.status));
  const choiceMarkup = state.documents.map((document) => {
    const id = String(document.id);
    const active = ["queued", "indexing"].includes(document.status);
    return `
      <label class="document-choice">
        <input class="checkbox" type="checkbox" value="${escapeHtml(id)}" data-training-document${state.selectedDocumentIds.has(id) ? " checked" : ""}${active ? ' disabled title="This document already has an active job"' : ""}>
        <span class="file-icon">${icon("file")}</span>
        <span class="document-choice__copy"><strong>${escapeHtml(document.title || document.filename)}</strong><small>${escapeHtml(document.course)} · ${escapeHtml(humanize(document.doc_type))} · ${escapeHtml(humanize(document.status))}</small>${document.error_message ? `<small class="text-danger" title="${escapeHtml(document.error_message)}">${escapeHtml(truncate(document.error_message, 96))}</small>` : ""}</span>
      </label>`;
  }).join("");
  const approvedMarkup = state.approvedAnswers.map((item) => `
    <article class="approved-answer-card" data-approved-card="${escapeHtml(item.id)}">
      <div class="approved-answer-card__heading"><div><span>${badge(item.status)}</span><strong>${escapeHtml(item.course)}</strong></div><small>v${escapeHtml(item.version)}</small></div>
      <h3>${escapeHtml(item.question)}</h3>
      <p>${escapeHtml(item.answer)}</p>
      <div class="approved-answer-card__actions">
        <button class="button button--ghost button--small" type="button" data-approved-edit="${escapeHtml(item.id)}">${icon("edit")} Edit</button>
        ${item.status === "published" ? "" : `<button class="button button--secondary button--small" type="button" data-approved-publish="${escapeHtml(item.id)}">${icon("check")} Publish</button>`}
        <button class="icon-button text-danger" type="button" data-approved-delete="${escapeHtml(item.id)}" aria-label="Delete approved answer">${icon("trash")}</button>
      </div>
    </article>`).join("");

  elements.viewRoot.innerHTML = `
    <header class="section-heading">
      <div><span class="eyebrow">Retrieval operations</span><h2>Knowledge training (RAG indexing)</h2><p>Convert selected source documents into searchable embeddings for course-aware mentor answers.</p></div>
    </header>
    ${retrievalWarningMarkup()}
    <div class="notice">${icon("info")}<span><strong>This does not fine-tune the base language model.</strong> It chunks and indexes your approved content in the retrieval store. Interrupted jobs use durable leases and are automatically requeued after a restart.</span></div>
    <section class="panel model-health-panel">
      <div class="panel__header"><div><h2>AI model health</h2><p>${escapeHtml(humanize(state.overview?.mentor_provider || "nvidia"))} · ${escapeHtml(state.overview?.mentor_model || "Configured model")}</p></div><button id="test-model" class="button button--secondary" type="button">${icon("spark")}<span>Test model</span></button></div>
      <div id="model-test-result" class="panel__body"><p class="muted">Run a short live completion to verify credentials, model availability, response quality, and latency. Private reasoning is never displayed.</p></div>
    </section>
    <div class="mentor-contract-layout">
      <section class="panel">
        <div class="panel__header"><div><h2>WhatsApp answer preview</h2><p>Test the complete mentor path: course policy, published answers, retrieval, model, and WhatsApp formatting.</p></div></div>
        <form id="whatsapp-preview-form" class="panel__body form-grid">
          <div class="field"><label for="preview-course">Course</label><select id="preview-course" name="course">${options(COURSES, "CMA")}</select></div>
          <div class="field"><label for="preview-mode">Learning mode</label><select id="preview-mode" name="mode">${options(["doubt_solving", "teach", "quiz", "revise", "job_hunt"], "doubt_solving")}</select></div>
          <div class="field field--full"><label for="preview-question">Student question</label><textarea id="preview-question" name="question" rows="4" maxlength="6000" required placeholder="Enter the exact question the student will send on WhatsApp"></textarea></div>
          <div class="field--full form-actions"><button class="button button--primary" type="submit">${icon("message")} Preview WhatsApp reply</button></div>
        </form>
        <div id="whatsapp-preview-result" class="panel__body preview-result" aria-live="polite"><p class="muted">A published exact match is returned word-for-word. Other questions are answered from the indexed knowledge and model.</p></div>
      </section>
      <section class="panel">
        <div class="panel__header"><div><h2>Approved WhatsApp answers</h2><p>Publish exact answers for questions that must always receive identical wording.</p></div></div>
        <form id="approved-answer-form" class="panel__body form-grid">
          <input id="approved-answer-id" type="hidden"><input id="approved-answer-version" type="hidden">
          <div class="field"><label for="approved-course">Course</label><select id="approved-course" name="course">${options(COURSES, "CMA")}</select></div>
          <div class="field field--full"><label for="approved-question">Exact student question</label><textarea id="approved-question" name="question" rows="3" maxlength="6000" required></textarea></div>
          <div class="field field--full"><label for="approved-answer">Approved answer</label><textarea id="approved-answer" name="answer" rows="7" maxlength="20000" required></textarea><p class="field-help">Saving creates a draft. Publish it before WhatsApp begins using it.</p></div>
          <div class="field--full form-actions"><button id="approved-cancel" class="button button--ghost" type="button" hidden>Cancel edit</button><button class="button button--primary" type="submit">${icon("check")} Save draft</button></div>
        </form>
        <div class="panel__body approved-answer-list">${approvedMarkup || emptyMarkup("No approved answers", "Create an exact question and answer, then publish it for WhatsApp.")}</div>
        ${paginationMarkup("approvedAnswers", "Approved answers")}
      </section>
    </div>
    <div class="training-layout">
      <section class="panel">
        <div class="panel__header"><div><h2>Select source documents</h2><p>${formatNumber(state.pages.trainingDocuments.total)} sources · selections persist across pages</p></div><button id="training-select-all" class="button button--ghost button--small" type="button"${availableDocuments.length ? "" : " disabled"}>Select page</button></div>
        <div class="panel__body panel__body--flush">
          <div class="document-selector">${choiceMarkup || emptyMarkup("No documents available", "Upload a knowledge document or wait for the active job to finish.")}</div>
        </div>
        ${paginationMarkup("trainingDocuments", "Source documents")}
        <div class="panel__footer"><span id="training-selection-summary" class="selection-summary">${state.selectedDocumentIds.size} selected</span><button id="start-training" class="button button--primary" type="button"${state.selectedDocumentIds.size && retrievalEnabled() ? "" : " disabled"}${retrievalEnabled() ? "" : ' title="Enable course retrieval before indexing"'}>${icon("spark")}<span>Start RAG indexing</span></button></div>
      </section>
      <section class="panel">
        <div class="panel__header"><div><h2>Training jobs</h2><p>${formatNumber(totalJobs)} recorded job${Number(totalJobs) === 1 ? "" : "s"}; active jobs refresh automatically</p></div></div>
        <div class="panel__body panel__body--flush">
          ${state.jobs.length ? `<div class="data-table-wrap"><table class="data-table"><thead><tr><th>Job</th><th>Status</th><th>Documents</th><th>Progress</th><th>Chunks</th></tr></thead><tbody>${jobRows(state.jobs)}</tbody></table></div>` : emptyMarkup("No training jobs yet", "Select one or more source documents to create the first RAG indexing job.")}
        </div>
        ${paginationMarkup("trainingJobs", "Training jobs")}
      </section>
    </div>`;

  const updateSelection = () => {
    const count = state.selectedDocumentIds.size;
    const summary = document.querySelector("#training-selection-summary");
    const start = document.querySelector("#start-training");
    if (summary) summary.textContent = `${count} selected`;
    if (start) start.disabled = count === 0 || !retrievalEnabled();
    const boxes = [...document.querySelectorAll("[data-training-document]:not(:disabled)")];
    const allSelected = boxes.length > 0 && boxes.every((box) => box.checked);
    const selectAll = document.querySelector("#training-select-all");
    if (selectAll) selectAll.textContent = allSelected ? "Clear page" : "Select page";
  };
  document.querySelectorAll("[data-training-document]").forEach((checkbox) => checkbox.addEventListener("change", () => {
    if (checkbox.checked) state.selectedDocumentIds.add(checkbox.value);
    else state.selectedDocumentIds.delete(checkbox.value);
    updateSelection();
  }));
  document.querySelector("#training-select-all")?.addEventListener("click", () => {
    const boxes = [...document.querySelectorAll("[data-training-document]:not(:disabled)")];
    const shouldSelect = !boxes.every((box) => box.checked);
    boxes.forEach((box) => {
      box.checked = shouldSelect;
      if (shouldSelect) state.selectedDocumentIds.add(box.value);
      else state.selectedDocumentIds.delete(box.value);
    });
    updateSelection();
  });
  document.querySelector("#start-training")?.addEventListener("click", () => createTrainingJob([...state.selectedDocumentIds]));
  document.querySelector("#test-model")?.addEventListener("click", async (event) => {
    const button = event.currentTarget;
    const result = document.querySelector("#model-test-result");
    setButtonBusy(button, true);
    try {
      const payload = await apiRequest("/model/test", { method: "POST", body: {} });
      result.innerHTML = `<div class="model-test-success"><span>${badge("active")}</span><div><strong>${escapeHtml(payload.model)}</strong><p>${escapeHtml(payload.answer)}</p><small>${(Number(payload.latency_ms || 0) / 1000).toFixed(2)} seconds · reasoning ${payload.thinking_enabled ? "enabled" : "disabled for speed"}</small></div></div>`;
      showToast("Model test passed", `${payload.model} responded in ${(Number(payload.latency_ms || 0) / 1000).toFixed(2)} seconds.`);
    } catch (error) {
      result.innerHTML = `<div class="notice notice--error">${icon("alert")}<span><strong>Model test failed.</strong> ${escapeHtml(error.message)}</span></div>`;
      showToast("Model test failed", error.message, "error");
    } finally { setButtonBusy(button, false); }
  });
  document.querySelector("#whatsapp-preview-form")?.addEventListener("submit", async (event) => {
    event.preventDefault();
    const button = event.submitter;
    const form = new FormData(event.currentTarget);
    const result = document.querySelector("#whatsapp-preview-result");
    setButtonBusy(button, true);
    try {
      const payload = await apiRequest("/mentor/whatsapp-preview", { method: "POST", body: Object.fromEntries(form) });
      result.innerHTML = `<div class="preview-result__meta">${badge(payload.exact_match ? "published" : "generated")}<span>${escapeHtml(payload.model)} · ${(Number(payload.latency_ms || 0) / 1000).toFixed(2)} seconds</span></div><pre>${escapeHtml(payload.whatsapp_answer)}</pre>${payload.exact_match ? "" : '<p class="field-help">This is a generated RAG answer and wording can vary. Publish an approved answer when identical wording is required.</p>'}`;
    } catch (error) {
      result.innerHTML = `<div class="notice notice--error">${icon("alert")}<span>${escapeHtml(error.message)}</span></div>`;
    } finally { setButtonBusy(button, false); }
  });
  const clearApprovedForm = () => {
    document.querySelector("#approved-answer-form")?.reset();
    document.querySelector("#approved-answer-id").value = "";
    document.querySelector("#approved-answer-version").value = "";
    document.querySelector("#approved-cancel").hidden = true;
  };
  document.querySelector("#approved-cancel")?.addEventListener("click", clearApprovedForm);
  document.querySelector("#approved-answer-form")?.addEventListener("submit", async (event) => {
    event.preventDefault();
    const button = event.submitter;
    const id = document.querySelector("#approved-answer-id").value;
    const version = document.querySelector("#approved-answer-version").value;
    const body = {
      course: document.querySelector("#approved-course").value,
      question: document.querySelector("#approved-question").value,
      answer: document.querySelector("#approved-answer").value,
    };
    if (id) body.version = Number(version);
    setButtonBusy(button, true);
    try {
      await apiRequest(id ? `/approved-answers/${encodeURIComponent(id)}` : "/approved-answers", { method: id ? "PUT" : "POST", body });
      showToast("Answer draft saved", "Review and publish it when the wording is ready for WhatsApp.");
      if (!id) resetPage("approvedAnswers");
      await loadTraining(state.sequence, true);
    } catch (error) { showToast("Could not save answer", error.message, "error"); }
    finally { setButtonBusy(button, false); }
  });
  document.querySelectorAll("[data-approved-edit]").forEach((button) => button.addEventListener("click", () => {
    const item = state.approvedAnswers.find((answer) => answer.id === button.dataset.approvedEdit);
    if (!item) return;
    document.querySelector("#approved-answer-id").value = item.id;
    document.querySelector("#approved-answer-version").value = item.version;
    document.querySelector("#approved-course").value = item.course;
    document.querySelector("#approved-question").value = item.question;
    document.querySelector("#approved-answer").value = item.answer;
    document.querySelector("#approved-cancel").hidden = false;
    document.querySelector("#approved-question").focus();
  }));
  document.querySelectorAll("[data-approved-publish]").forEach((button) => button.addEventListener("click", async () => {
    setButtonBusy(button, true);
    try {
      await apiRequest(`/approved-answers/${encodeURIComponent(button.dataset.approvedPublish)}/publish`, { method: "POST" });
      showToast("Answer published", "WhatsApp will now return this exact answer for the matching course and question.");
      await loadTraining(state.sequence, true);
    } catch (error) { showToast("Could not publish answer", error.message, "error"); }
  }));
  document.querySelectorAll("[data-approved-delete]").forEach((button) => button.addEventListener("click", async () => {
    const confirmed = await confirmAction({
      title: "Delete approved answer?",
      message: "WhatsApp will stop using this exact answer immediately.",
      confirmLabel: "Delete answer",
      danger: true,
    });
    if (!confirmed) return;
    try {
      await apiRequest(`/approved-answers/${encodeURIComponent(button.dataset.approvedDelete)}`, { method: "DELETE" });
      showToast("Approved answer deleted", "The mentor will return to RAG generation for that question.");
      await loadTraining(state.sequence, true);
    } catch (error) { showToast("Could not delete answer", error.message, "error"); }
  }));
  document.querySelectorAll("[data-job-retry]").forEach((button) => button.addEventListener("click", () => retryTrainingJob(button.dataset.jobRetry, button)));
  bindRetrievalWarning(elements.viewRoot);
  bindPagination(elements.viewRoot);
}

function feedbackQuery() {
  const page = state.pages.feedback;
  const query = new URLSearchParams({ limit: String(page.limit), offset: String(page.offset) });
  Object.entries(state.feedbackFilters).forEach(([key, value]) => { if (value) query.set(key, value); });
  return query.toString();
}

async function loadFeedback(sequence = state.sequence) {
  const payload = await apiRequest(`/feedback?${feedbackQuery()}`);
  if (sequence !== state.sequence) return;
  state.feedback = Array.isArray(payload.items) ? payload.items : [];
  if (!applyPageResult("feedback", payload.total ?? state.feedback.length, state.feedback.length)) {
    await loadFeedback(sequence);
    return;
  }
  renderFeedback(state.pages.feedback.total);
}

function renderFeedback(total) {
  const filters = state.feedbackFilters;
  const hasFilters = Boolean(filters.search || filters.category || filters.status);
  const cards = state.feedback.map((item) => {
    const id = String(item.id || "");
    const reference = id.split("-", 1)[0] || "unknown";
    const sender = item.profile_name || item.sender || "WhatsApp student";
    return `
      <article class="feedback-card">
        <div class="feedback-card__top">
          <span class="feedback-card__sender"><strong>${escapeHtml(sender)}</strong><small>Ref #${escapeHtml(reference)} · ${escapeHtml(item.profile_name ? item.sender : "WhatsApp feedback")}</small></span>
          ${badge(item.status)}
        </div>
        <p class="feedback-card__message">${escapeHtml(item.message || "No written description provided.")}</p>
        <div class="feedback-card__footer">
          <span class="feedback-card__meta">${escapeHtml(humanize(item.category))} · ${escapeHtml(formatDate(item.created_at))}</span>
          <span class="feedback-actions">
            ${item.has_attachment ? `<button class="icon-button" type="button" data-feedback-attachment="${escapeHtml(id)}" aria-label="Open feedback screenshot">${icon("image")}</button>` : ""}
            <button class="button button--ghost button--small" type="button" data-feedback-review="${escapeHtml(id)}">Review</button>
          </span>
        </div>
      </article>`;
  }).join("");

  elements.viewRoot.innerHTML = `
    <header class="section-heading">
      <div><span class="eyebrow">WhatsApp inbox</span><h2>Student feedback</h2><p>Review requested changes and reported errors, including screenshots submitted through WhatsApp.</p></div>
    </header>
    <section class="panel" style="background:transparent;border:0;box-shadow:none">
      <div class="toolbar panel">
        <label class="toolbar__search"><span class="sr-only">Search feedback</span>${icon("search")}<input id="feedback-search" type="search" value="${escapeHtml(filters.search)}" placeholder="Search message or sender…"></label>
        <select id="feedback-category" class="select" aria-label="Filter by category"><option value="">All categories</option>${options(FEEDBACK_CATEGORIES, filters.category)}</select>
        <select id="feedback-status" class="select" aria-label="Filter by status"><option value="">All statuses</option>${options(FEEDBACK_STATUSES, filters.status)}</select>
        <span class="toolbar__count">${formatNumber(total)} item${Number(total) === 1 ? "" : "s"}</span>
      </div>
      <div style="margin-top:15px">${cards ? `<div class="feedback-grid">${cards}</div>` : `<div class="panel">${emptyMarkup(hasFilters ? "No matching feedback" : "No feedback yet", hasFilters ? "Try clearing a filter or using a broader search." : "New WhatsApp feedback will appear here for triage.", hasFilters ? '<button class="button button--secondary" type="button" data-action="clear-feedback-filters">Clear filters</button>' : "")}</div>`}</div>
      ${paginationMarkup("feedback", "Feedback items")}
    </section>`;

  const runSearch = debounce((value) => {
    state.feedbackFilters.search = value.trim();
    resetPage("feedback");
    loadRoute();
  }, 350);
  document.querySelector("#feedback-search")?.addEventListener("input", (event) => runSearch(event.target.value));
  document.querySelector("#feedback-category")?.addEventListener("change", (event) => {
    state.feedbackFilters.category = event.target.value;
    resetPage("feedback");
    loadRoute();
  });
  document.querySelector("#feedback-status")?.addEventListener("change", (event) => {
    state.feedbackFilters.status = event.target.value;
    resetPage("feedback");
    loadRoute();
  });
  document.querySelector('[data-action="clear-feedback-filters"]')?.addEventListener("click", () => {
    state.feedbackFilters = { search: "", category: "", status: "" };
    resetPage("feedback");
    loadRoute();
  });
  document.querySelectorAll("[data-feedback-review]").forEach((button) => button.addEventListener("click", () => {
    const item = state.feedback.find((feedback) => String(feedback.id) === button.dataset.feedbackReview);
    if (item) openFeedbackEditor(item);
  }));
  document.querySelectorAll("[data-feedback-attachment]").forEach((button) => button.addEventListener("click", () => viewFeedbackAttachment(button.dataset.feedbackAttachment, button)));
  bindPagination(elements.viewRoot);
}

function openFeedbackEditor(item) {
  const reference = String(item.id || "").split("-", 1)[0] || "unknown";
  openDialog({
    title: "Review feedback",
    eyebrow: "Student report",
    content: `
      <form id="feedback-edit-form" class="feedback-detail" novalidate>
        <dl class="definition-list">
          <div><dt>Reference</dt><dd>#${escapeHtml(reference)}</dd></div>
          <div><dt>From</dt><dd>${escapeHtml(item.profile_name || item.sender || "Unknown")}</dd></div>
          <div><dt>Received</dt><dd>${escapeHtml(formatDate(item.created_at))}</dd></div>
        </dl>
        <p class="feedback-detail__message">${escapeHtml(item.message || "No written description provided.")}</p>
        ${item.has_attachment ? `<button class="button button--secondary" type="button" data-dialog-attachment="${escapeHtml(item.id)}">${icon("image")}<span>Open attached screenshot</span></button>` : ""}
        <div class="form-grid">
          <div class="field"><label for="feedback-category-edit">Category</label><select id="feedback-category-edit" required>${options(FEEDBACK_CATEGORIES, item.category)}</select></div>
          <div class="field"><label for="feedback-status-edit">Status</label><select id="feedback-status-edit" required>${options(FEEDBACK_STATUSES, item.status)}</select></div>
          <div class="field field--full"><label for="feedback-notes">Internal notes</label><textarea id="feedback-notes" maxlength="6000" placeholder="Record what changed, the resolution, or context for another administrator…">${escapeHtml(item.admin_notes || "")}</textarea><p class="field-help">Internal only. These notes are not sent to the student.</p></div>
        </div>
        <p id="feedback-edit-error" class="form-error" role="alert" hidden></p>
        <div class="form-actions"><button class="button button--secondary" type="button" data-action="cancel-feedback">Cancel</button><button id="feedback-save" class="button button--primary" type="submit"><span>Save review</span>${icon("check")}</button></div>
      </form>`,
    onOpen: (root) => {
      root.querySelector('[data-action="cancel-feedback"]').addEventListener("click", closeDialog);
      root.querySelector("[data-dialog-attachment]")?.addEventListener("click", (event) => viewFeedbackAttachment(item.id, event.currentTarget));
      root.querySelector("#feedback-edit-form").addEventListener("submit", async (event) => {
        event.preventDefault();
        const submit = root.querySelector("#feedback-save");
        const error = root.querySelector("#feedback-edit-error");
        error.hidden = true;
        setButtonBusy(submit, true);
        try {
          await apiRequest(`/feedback/${encodeURIComponent(item.id)}`, {
            method: "PATCH",
            body: {
              status: root.querySelector("#feedback-status-edit").value,
              category: root.querySelector("#feedback-category-edit").value,
              admin_notes: root.querySelector("#feedback-notes").value.trim(),
            },
          });
          closeDialog();
          state.overview = null;
          showToast("Feedback updated", "The review status and internal notes were saved.");
          loadRoute(true);
        } catch (requestError) {
          error.textContent = requestError.message;
          error.hidden = false;
          setButtonBusy(submit, false);
        }
      });
    },
  });
}

function conversationsQuery() {
  const page = state.pages.conversations;
  const query = new URLSearchParams({ limit: String(page.limit), offset: String(page.offset) });
  const search = state.conversationFilters.search.trim().slice(0, 200);
  if (search) query.set("search", search);
  return query.toString();
}

function safeConversationMessage(message) {
  const value = message && typeof message === "object" ? message : {};
  return {
    id: String(value.id || ""),
    direction: value.direction === "outbound" ? "outbound" : "inbound",
    messageType: String(value.message_type || "unknown"),
    text: String(value.text || ""),
    hasMedia: value.has_media === true,
    status: String(value.status || ""),
    createdAt: value.created_at || null,
    statusAt: value.status_at || null,
  };
}

function conversationsSignature(total, items) {
  return JSON.stringify({
    total: Number(total) || 0,
    offset: state.pages.conversations.offset,
    items: items.map((item) => ({
      id: String(item.id || ""),
      displayName: String(item.display_name || ""),
      maskedPhone: String(item.masked_phone || ""),
      messageCount: Number(item.message_count) || 0,
      lastMessage: safeConversationMessage(item.last_message),
    })),
  });
}

async function loadConversations(sequence = state.sequence, { polling = false } = {}) {
  const payload = await apiRequest(`/whatsapp/conversations?${conversationsQuery()}`);
  if (sequence !== state.sequence || state.route !== "conversations") return;
  state.conversations = Array.isArray(payload.items) ? payload.items : [];
  if (!applyPageResult("conversations", payload.total ?? state.conversations.length, state.conversations.length)) {
    await loadConversations(sequence, { polling });
    return;
  }
  const signature = conversationsSignature(state.pages.conversations.total, state.conversations);
  const searchHasFocus = document.activeElement?.id === "conversation-search";
  if (!polling || (signature !== state.conversationsRenderedSignature && !searchHasFocus)) {
    renderConversations(state.pages.conversations.total);
  }
}

function conversationPreview(message) {
  const safe = safeConversationMessage(message);
  const direction = safe.direction === "outbound" ? "You: " : "";
  if (safe.hasMedia || safe.messageType === "image") {
    return `${direction}Image${safe.text ? ` — ${safe.text}` : ""}`;
  }
  return `${direction}${safe.text || humanize(safe.messageType) || "Message"}`;
}

function renderConversations(total) {
  const search = state.conversationFilters.search;
  const hasSearch = Boolean(search.trim());
  const activeElement = document.activeElement;
  const focusedRow = activeElement?.closest?.("[data-conversation-open]");
  const focusedPageButton = activeElement?.closest?.('[data-page-key="conversations"]');
  const focusTarget = focusedRow
    ? { type: "row", id: focusedRow.dataset.conversationOpen }
    : activeElement?.matches?.('[data-action="refresh-conversations"]')
      ? { type: "refresh" }
      : focusedPageButton
        ? { type: "page", direction: focusedPageButton.dataset.pageDirection }
        : state.conversationFocusTarget;
  state.conversationFocusTarget = null;
  const rows = state.conversations.map((item) => {
    const id = String(item.id || "");
    const name = item.display_name || item.profile_name || "WhatsApp student";
    const maskedPhone = item.masked_phone || "Masked number unavailable";
    const lastMessage = safeConversationMessage(item.last_message);
    return `
      <button class="conversation-row" type="button" data-conversation-open="${escapeHtml(id)}" aria-label="Open conversation with ${escapeHtml(name)}">
        <span class="conversation-row__avatar" aria-hidden="true">${icon("message")}</span>
        <span class="conversation-row__main">
          <span class="conversation-row__heading"><strong>${escapeHtml(name)}</strong><time>${escapeHtml(formatDate(lastMessage.createdAt))}</time></span>
          <span class="conversation-row__phone">${escapeHtml(maskedPhone)}</span>
          <span class="conversation-row__preview">${escapeHtml(truncate(conversationPreview(item.last_message), 150))}</span>
        </span>
        <span class="conversation-row__count">${formatNumber(item.message_count)} message${Number(item.message_count) === 1 ? "" : "s"}</span>
        <span class="conversation-row__arrow" aria-hidden="true">${icon("arrow")}</span>
      </button>`;
  }).join("");

  elements.viewRoot.innerHTML = `
    <header class="section-heading">
      <div><span class="eyebrow">WhatsApp inbox</span><h2>Conversations</h2><p>Review the protected inbound and outbound timeline for the configured Ziplin number. This inbox is view-only.</p></div>
      <div class="section-heading__actions"><button class="button button--secondary" type="button" data-action="refresh-conversations">${icon("refresh")}<span>Refresh inbox</span></button></div>
    </header>
    <section class="panel conversation-panel">
      <div class="toolbar">
        <label class="toolbar__search"><span class="sr-only">Search conversations</span>${icon("search")}<input id="conversation-search" type="search" value="${escapeHtml(search)}" placeholder="Search name or masked number…" autocomplete="off" maxlength="200"></label>
        <span class="toolbar__count">${formatNumber(total)} conversation${Number(total) === 1 ? "" : "s"}</span>
      </div>
      <div class="conversation-list">
        ${rows || emptyMarkup(hasSearch ? "No matching conversations" : "No conversations yet", hasSearch ? "Try a broader search or clear the current search." : "Messages for the configured Ziplin number will appear after genuine inbound or outbound activity.", hasSearch ? '<button class="button button--secondary" type="button" data-action="clear-conversation-search">Clear search</button>' : "")}
      </div>
      ${paginationMarkup("conversations", "Conversations")}
    </section>`;
  state.conversationsRenderedSignature = conversationsSignature(total, state.conversations);

  const runSearch = debounce((value) => {
    state.conversationFilters.search = String(value || "").trim().slice(0, 200);
    state.conversationFocusTarget = { type: "search" };
    resetPage("conversations");
    loadRoute();
  }, 350);
  elements.viewRoot.querySelector("#conversation-search")?.addEventListener("input", (event) => runSearch(event.target.value));
  elements.viewRoot.querySelector('[data-action="clear-conversation-search"]')?.addEventListener("click", () => {
    state.conversationFilters.search = "";
    state.conversationFocusTarget = { type: "search" };
    resetPage("conversations");
    loadRoute();
  });
  elements.viewRoot.querySelector('[data-action="refresh-conversations"]')?.addEventListener("click", (event) => {
    refreshConversationInbox(event.currentTarget);
  });
  elements.viewRoot.querySelectorAll("[data-conversation-open]").forEach((button) => button.addEventListener("click", () => {
    openConversationThread(button.dataset.conversationOpen);
  }));
  bindPagination(elements.viewRoot);

  let focusElement = null;
  if (focusTarget?.type === "search") {
    focusElement = elements.viewRoot.querySelector("#conversation-search");
  } else if (focusTarget?.type === "refresh") {
    focusElement = elements.viewRoot.querySelector('[data-action="refresh-conversations"]');
  } else if (focusTarget?.type === "page") {
    focusElement = [...elements.viewRoot.querySelectorAll('[data-page-key="conversations"]')]
      .find((button) => button.dataset.pageDirection === focusTarget.direction);
  } else if (focusTarget?.type === "row") {
    focusElement = [...elements.viewRoot.querySelectorAll("[data-conversation-open]")]
      .find((button) => button.dataset.conversationOpen === focusTarget.id);
    if (!focusElement) focusElement = elements.viewRoot.querySelector("#conversation-search");
  }
  if (focusElement?.disabled) {
    focusElement = [...elements.viewRoot.querySelectorAll('[data-page-key="conversations"]')]
      .find((button) => !button.disabled) || elements.viewRoot.querySelector("#conversation-search");
  }
  focusElement?.focus({ preventScroll: true });
  if (focusTarget?.type === "search" && focusElement instanceof HTMLInputElement) {
    focusElement.setSelectionRange(focusElement.value.length, focusElement.value.length);
  }
}

function conversationThreadSignature(payload) {
  const conversation = payload?.conversation || {};
  const messages = Array.isArray(payload?.items) ? payload.items : [];
  return JSON.stringify({
    conversation: {
      id: String(conversation.id || ""),
      displayName: String(conversation.display_name || ""),
      maskedPhone: String(conversation.masked_phone || ""),
    },
    total: Number(payload?.total) || 0,
    messages: messages.map(safeConversationMessage),
  });
}

function conversationMessageMarkup(rawMessage) {
  const message = safeConversationMessage(rawMessage);
  const image = message.hasMedia || message.messageType === "image";
  const statusLabel = message.status ? humanize(message.status) : (message.direction === "outbound" ? "Sent" : "Received");
  const statusTime = message.statusAt && message.statusAt !== message.createdAt
    ? `<span>Status updated ${escapeHtml(formatDate(message.statusAt))}</span>`
    : "";
  return `
    <article class="conversation-message conversation-message--${message.direction}">
      <div class="conversation-message__label"><span>${message.direction === "outbound" ? "NorthStar" : "Student"}</span><span>${escapeHtml(humanize(message.messageType))}</span></div>
      <div class="conversation-message__bubble">
        ${image ? `<div class="conversation-message__media">${icon("image")}<span>Image attachment hidden</span></div>` : ""}
        ${message.text ? `<p>${escapeHtml(message.text)}</p>` : (!image ? `<p class="muted">${escapeHtml(humanize(message.messageType))} message</p>` : "")}
      </div>
      <footer class="conversation-message__meta"><time>${escapeHtml(formatDate(message.createdAt))}</time><span>${escapeHtml(statusLabel)}</span>${statusTime}</footer>
    </article>`;
}

function renderConversationThread(payload, { preserveScroll = false, restoreActionFocus = false } = {}) {
  const conversation = payload?.conversation || {};
  const messages = Array.isArray(payload?.items) ? payload.items : [];
  const existing = elements.dialogBody.querySelector(".conversation-thread__messages");
  const restoreMessageFocus = existing?.contains(document.activeElement) === true;
  const restoreRefreshFocus = restoreActionFocus
    || document.activeElement?.matches?.('[data-action="refresh-conversation-thread"]') === true;
  const previousScrollTop = existing?.scrollTop || 0;
  const nearBottom = !existing || existing.scrollHeight - existing.scrollTop - existing.clientHeight < 80;
  const title = conversation.display_name || conversation.profile_name || "WhatsApp conversation";
  elements.dialogTitle.textContent = title;
  elements.dialogEyebrow.textContent = "Protected WhatsApp timeline";
  elements.dialogEyebrow.hidden = false;
  elements.dialogBody.innerHTML = `
    <section class="conversation-thread" aria-label="Conversation history">
      <div class="conversation-thread__summary">
        <span><strong>${escapeHtml(conversation.masked_phone || "Masked number unavailable")}</strong><small>${formatNumber(payload?.total)} message${Number(payload?.total) === 1 ? "" : "s"}</small></span>
        <button class="button button--secondary button--small" type="button" data-action="refresh-conversation-thread">${icon("refresh")}<span>Refresh</span></button>
      </div>
      ${Number(payload?.total) > messages.length ? `<p class="conversation-thread__limit">Showing the latest ${formatNumber(messages.length)} of ${formatNumber(payload.total)} messages.</p>` : ""}
      <div class="conversation-thread__messages" role="region" aria-label="Messages in chronological order" tabindex="0">
        ${messages.length ? messages.map(conversationMessageMarkup).join("") : emptyMarkup("No messages yet", "This protected conversation does not contain any displayable messages.")}
      </div>
      <p class="conversation-thread__privacy">View-only · Phone numbers stay masked · Attachments and provider metadata are not exposed.</p>
    </section>`;
  state.activeConversationSignature = conversationThreadSignature(payload);
  const messagePane = elements.dialogBody.querySelector(".conversation-thread__messages");
  if (messagePane) {
    if (!preserveScroll || nearBottom) messagePane.scrollTop = messagePane.scrollHeight;
    else messagePane.scrollTop = previousScrollTop;
  }
  elements.dialogBody.querySelector('[data-action="refresh-conversation-thread"]')?.addEventListener("click", (event) => {
    refreshConversationThreadFromControl(event.currentTarget);
  });
  if (restoreMessageFocus) {
    messagePane?.focus({ preventScroll: true });
  } else if (restoreRefreshFocus) {
    elements.dialogBody.querySelector('[data-action="refresh-conversation-thread"]')?.focus({ preventScroll: true });
  }
}

function renderConversationThreadError(error) {
  elements.dialogBody.innerHTML = `
    <div class="error-state conversation-thread__error" role="alert">
      <div class="state-content">
        <span class="state-icon">${icon("alert")}</span>
        <h3>Conversation unavailable</h3>
        <p>${escapeHtml(error.message || "The conversation could not be loaded.")}</p>
        <button class="button button--secondary" type="button" data-action="retry-conversation-thread">${icon("refresh")}<span>Try again</span></button>
      </div>
    </div>`;
  const retryButton = elements.dialogBody.querySelector('[data-action="retry-conversation-thread"]');
  retryButton?.addEventListener("click", (event) => {
    refreshConversationThreadFromControl(event.currentTarget);
  });
  retryButton?.focus({ preventScroll: true });
}

async function refreshConversationThreadFromControl(button) {
  const healthy = await refreshConversationThread(state.activeConversationId, { button });
  if (healthy && state.authenticated && state.route === "conversations") updateTimestamp();
}

async function refreshConversationThread(conversationId, { silent = false, button = null } = {}) {
  if (!conversationId) return true;
  const restoreActionFocus = Boolean(button && document.activeElement === button);
  setButtonBusy(button, true);
  try {
    const payload = await apiRequest(`/whatsapp/conversations/${encodeURIComponent(conversationId)}/messages?limit=100&offset=0`);
    if (state.activeConversationId !== conversationId || !elements.dialog.open) return true;
    const signature = conversationThreadSignature(payload);
    if (!silent || signature !== state.activeConversationSignature) {
      renderConversationThread(payload, { preserveScroll: silent, restoreActionFocus });
    }
    return true;
  } catch (error) {
    if (error.status === 401) {
      closeDialog();
      signOut("Your admin session is no longer valid. Sign in again.");
      return false;
    }
    if (state.activeConversationId !== conversationId || !elements.dialog.open) return true;
    if (error.status === 404) {
      closeDialog();
      elements.connectionLabel.textContent = "Conversation unavailable";
      showToast("Conversation closed", "It is no longer available in the protected inbox.", "error");
      return false;
    }
    elements.connectionLabel.textContent = error.status === 0 ? "Thread unavailable" : "Thread update failed";
    if (!silent) renderConversationThreadError(error);
    return false;
  } finally {
    setButtonBusy(button, false);
  }
}

function openConversationThread(conversationId) {
  const summary = state.conversations.find((item) => String(item.id) === String(conversationId));
  state.activeConversationId = String(conversationId || "");
  state.activeConversationSignature = "";
  openDialog({
    title: summary?.display_name || summary?.profile_name || "WhatsApp conversation",
    eyebrow: "Protected WhatsApp timeline",
    content: `<div class="conversation-thread__loading">${loadingMarkup()}</div>`,
  });
  elements.dialog.classList.add("dialog--conversation");
  refreshConversationThread(state.activeConversationId);
}

async function refreshConversationInbox(button = null) {
  const sequence = state.sequence;
  let threadConnectionHealthy = true;
  if (button && document.activeElement === button) {
    state.conversationFocusTarget = { type: "refresh" };
  }
  setButtonBusy(button, true);
  try {
    await loadConversations(sequence);
    if (state.activeConversationId && elements.dialog.open) {
      threadConnectionHealthy = await refreshConversationThread(state.activeConversationId);
    }
    if (sequence === state.sequence && state.route === "conversations" && threadConnectionHealthy) updateTimestamp();
  } catch (error) {
    if (error.status === 401) signOut("Your admin session is no longer valid. Sign in again.");
    else {
      elements.connectionLabel.textContent = error.status === 0 ? "Inbox unavailable" : "Inbox update failed";
      showToast("Inbox refresh failed", error.message, "error");
    }
  } finally {
    setButtonBusy(button, false);
    if (button?.isConnected && state.conversationFocusTarget?.type === "refresh") {
      state.conversationFocusTarget = null;
      button.focus({ preventScroll: true });
    }
    scheduleConversationPoll();
  }
}

async function pollConversationInbox() {
  if (!conversationPollAllowed()) return;
  const sequence = state.sequence;
  let threadConnectionHealthy = true;
  try {
    await loadConversations(sequence, { polling: true });
    if (state.activeConversationId && elements.dialog.open) {
      threadConnectionHealthy = await refreshConversationThread(state.activeConversationId, { silent: true });
    }
    if (sequence === state.sequence && conversationPollAllowed() && threadConnectionHealthy) updateTimestamp();
  } catch (error) {
    if (error.status === 401) signOut("Your admin session is no longer valid. Sign in again.");
    else elements.connectionLabel.textContent = "Inbox update failed";
  } finally {
    if (sequence === state.sequence) scheduleConversationPoll();
  }
}

function auditDetailsText(details) {
  if (!details || typeof details !== "object" || Array.isArray(details)) return "No additional details";
  const entries = Object.entries(details);
  if (!entries.length) return "No additional details";
  return entries.map(([key, value]) => {
    const rendered = Array.isArray(value) ? value.join(", ") : String(value ?? "");
    return `${humanize(key)}: ${rendered}`;
  }).join(" · ");
}

function activityQuery() {
  const page = state.pages.activity;
  const query = new URLSearchParams({ limit: String(page.limit), offset: String(page.offset) });
  if (state.activityFilters.search) query.set("search", state.activityFilters.search);
  return query.toString();
}

function analyticsBars(items = []) {
  const maximum = Math.max(1, ...items.map((item) => Number(item.value || 0)));
  return items.length ? `<div class="analytics-bars">${items.map((item) => `
    <div class="analytics-bar"><span>${escapeHtml(humanize(item.label))}</span><div><i style="width:${Math.max(3, (Number(item.value || 0) / maximum) * 100)}%"></i></div><strong>${formatNumber(item.value)}</strong></div>`).join("")}</div>` : emptyMarkup("No usage yet", "Usage will appear after students ask mentor questions.");
}

function analyticsLine(items = []) {
  if (!items.length) return emptyMarkup("No trend data yet", "The request trend appears after the first student interaction.");
  const maximum = Math.max(1, ...items.map((item) => Number(item.requests || 0)));
  const width = 720; const height = 220; const pad = 24;
  const points = items.map((item, index) => {
    const x = items.length === 1 ? width / 2 : pad + (index / (items.length - 1)) * (width - pad * 2);
    const y = height - pad - (Number(item.requests || 0) / maximum) * (height - pad * 2);
    return `${x.toFixed(1)},${y.toFixed(1)}`;
  }).join(" ");
  return `<div class="line-chart"><svg viewBox="0 0 ${width} ${height}" role="img" aria-label="Daily mentor requests"><path class="line-chart__area" d="M ${points.split(" ").join(" L ")} L ${width - pad},${height - pad} L ${pad},${height - pad} Z"></path><polyline points="${points}"></polyline></svg><div class="line-chart__labels"><span>${escapeHtml(items[0].date)}</span><span>${escapeHtml(items.at(-1).date)}</span></div></div>`;
}

async function loadAnalytics(sequence = state.sequence, days = Number(state.analytics?.days || 30)) {
  const payload = await apiRequest(`/analytics?days=${days}`);
  if (sequence !== state.sequence || state.route !== "analytics") return;
  state.analytics = payload;
  renderAnalytics();
}

function renderAnalytics() {
  const data = state.analytics || { totals: {}, daily: [], courses: [], channels: [], modes: [], students: [] };
  const totals = data.totals || {};
  const channels = data.channels || [];
  const channelTotal = Math.max(1, channels.reduce((sum, item) => sum + Number(item.value || 0), 0));
  const webShare = ((Number(channels.find((item) => item.label === "web")?.value || 0) / channelTotal) * 100).toFixed(1);
  elements.viewRoot.innerHTML = `
    <header class="section-heading"><div><span class="eyebrow">Usage intelligence</span><h2>Student analytics</h2><p>Track requests, active students, response reliability, courses, channels, modes, and per-student usage.</p></div><div class="section-heading__actions"><select id="analytics-days" class="select" aria-label="Analytics period"><option value="7"${data.days === 7 ? " selected" : ""}>Last 7 days</option><option value="30"${data.days === 30 ? " selected" : ""}>Last 30 days</option><option value="90"${data.days === 90 ? " selected" : ""}>Last 90 days</option><option value="365"${data.days === 365 ? " selected" : ""}>Last year</option></select></div></header>
    <div class="stat-grid">
      ${statCard("Mentor requests", totals.requests || 0, `Last ${data.days} days`, "message")}
      ${statCard("Active students", totals.students || 0, "Unique student identifiers", "users", "blue")}
      ${statCard("Success rate", `${totals.success_rate ?? 100}%`, `${totals.errors || 0} failed request(s)`, "check", "warm")}
      ${statCard("Average response", `${((totals.average_latency_ms || 0) / 1000).toFixed(1)}s`, "End-to-end mentor latency", "refresh", "coral")}
    </div>
    <div class="analytics-grid">
      <section class="panel analytics-panel--wide"><div class="panel__header"><div><h2>Request trend</h2><p>Daily student mentor interactions</p></div></div><div class="panel__body">${analyticsLine(data.daily)}</div></section>
      <section class="panel"><div class="panel__header"><div><h2>Channel mix</h2><p>Web compared with WhatsApp</p></div></div><div class="panel__body donut-layout"><div class="donut" style="--value:${webShare}"><strong>${webShare}%</strong><span>Web</span></div>${analyticsBars(channels)}</div></section>
      <section class="panel"><div class="panel__header"><div><h2>Usage by course</h2><p>Questions grouped by enrolled course</p></div></div><div class="panel__body">${analyticsBars(data.courses)}</div></section>
      <section class="panel"><div class="panel__header"><div><h2>Learning modes</h2><p>How students use the mentor</p></div></div><div class="panel__body">${analyticsBars(data.modes)}</div></section>
      <section class="panel analytics-panel--wide"><div class="panel__header"><div><h2>Student usage</h2><p>Up to 200 most active students in this period</p></div></div><div class="panel__body panel__body--flush">${data.students.length ? `<div class="data-table-wrap"><table class="data-table"><thead><tr><th>Student</th><th>Courses</th><th>Requests</th><th>Errors</th><th>Avg response</th><th>Last active</th></tr></thead><tbody>${data.students.map((item) => `<tr><td><strong>${escapeHtml(item.student_id)}</strong></td><td>${(item.courses || []).map((course) => `<span class="badge">${escapeHtml(course)}</span>`).join(" ")}</td><td>${formatNumber(item.requests)}</td><td>${formatNumber(item.errors)}</td><td>${(Number(item.average_latency_ms || 0) / 1000).toFixed(1)}s</td><td>${escapeHtml(formatDate(item.last_active))}</td></tr>`).join("")}</tbody></table></div>` : emptyMarkup("No student activity yet", "Student usage will appear after mentor requests are completed.")}</div></section>
    </div>`;
  document.querySelector("#analytics-days")?.addEventListener("change", (event) => loadAnalytics(state.sequence, Number(event.target.value)));
}

async function loadActivity(sequence = state.sequence) {
  const payload = await apiRequest(`/audit?${activityQuery()}`);
  if (sequence !== state.sequence) return;
  state.auditEvents = Array.isArray(payload.items) ? payload.items : [];
  if (!applyPageResult("activity", payload.total ?? state.auditEvents.length, state.auditEvents.length)) {
    await loadActivity(sequence);
    return;
  }
  renderActivity(state.pages.activity.total);
}

function renderActivity(total) {
  const search = state.activityFilters.search;
  const rows = state.auditEvents.map((event) => `
    <tr>
      <td><span class="table-primary">${escapeHtml(humanize(event.action))}</span><span class="table-secondary">#${escapeHtml(event.id)}</span></td>
      <td><span class="table-primary">${escapeHtml(humanize(event.entity_type))}</span><span class="table-secondary">${escapeHtml(event.entity_id || "System")}</span></td>
      <td><span class="table-secondary" title="${escapeHtml(auditDetailsText(event.details))}">${escapeHtml(truncate(auditDetailsText(event.details), 130))}</span></td>
      <td>${escapeHtml(formatDate(event.created_at))}</td>
    </tr>`).join("");

  elements.viewRoot.innerHTML = `
    <header class="section-heading">
      <div><span class="eyebrow">Operational history</span><h2>Admin activity</h2><p>Review document, training, feedback, configuration, and enrollment changes recorded by the control center.</p></div>
    </header>
    <section class="panel">
      <div class="toolbar">
        <label class="toolbar__search"><span class="sr-only">Search admin activity</span>${icon("search")}<input id="activity-search" type="search" value="${escapeHtml(search)}" placeholder="Search action, entity, or details…"></label>
        <span class="toolbar__count">${formatNumber(total)} event${Number(total) === 1 ? "" : "s"}</span>
      </div>
      <div class="panel__body panel__body--flush">
        ${rows ? `<div class="data-table-wrap"><table class="data-table"><thead><tr><th>Action</th><th>Target</th><th>Details</th><th>Recorded</th></tr></thead><tbody>${rows}</tbody></table></div>` : emptyMarkup(search ? "No matching activity" : "No activity recorded", search ? "Try a broader search." : "Admin changes will appear here as they occur.")}
      </div>
      ${paginationMarkup("activity", "Activity events")}
    </section>`;

  const runSearch = debounce((value) => {
    state.activityFilters.search = value.trim();
    resetPage("activity");
    loadRoute();
  }, 350);
  document.querySelector("#activity-search")?.addEventListener("input", (event) => runSearch(event.target.value));
  bindPagination(elements.viewRoot);
}

async function viewFeedbackAttachment(feedbackId, button) {
  setButtonBusy(button, true);
  const previewWindow = window.open("", "_blank", "noopener,noreferrer");
  try {
    const blob = await apiRequest(`/feedback/${encodeURIComponent(feedbackId)}/attachment`, { responseType: "blob" });
    const objectUrl = URL.createObjectURL(blob);
    if (previewWindow) {
      previewWindow.location.replace(objectUrl);
    } else {
      const link = document.createElement("a");
      link.href = objectUrl;
      link.download = `feedback-${feedbackId}`;
      link.click();
    }
    window.setTimeout(() => URL.revokeObjectURL(objectUrl), 60_000);
  } catch (error) {
    previewWindow?.close();
    showToast("Screenshot unavailable", error.message, "error");
  } finally {
    setButtonBusy(button, false);
  }
}

const SETTING_META = {
  mentor_provider: { group: "Mentor models", label: "Primary provider", description: "Provider used for mentor answers.", options: ["nvidia", "gemini", "anthropic"] },
  mentor_fallback_provider: { group: "Mentor models", label: "Fallback provider", description: "Used when the primary provider is unavailable.", options: ["none", "nvidia", "gemini", "anthropic"] },
  mentor_policy_provider: { group: "Mentor models", label: "Policy provider", description: "Performs course-scope and output checks.", options: ["gemini", "primary"] },
  nvidia_model: { group: "Mentor models", label: "NVIDIA model", description: "Model identifier for NVIDIA requests." },
  nvidia_temperature: { group: "Mentor models", label: "NVIDIA temperature", description: "Creativity level from 0 to 2.", min: 0, max: 2, step: 0.05 },
  nvidia_top_p: { group: "Mentor models", label: "NVIDIA top P", description: "Probability mass used for token sampling.", min: 0.01, max: 1, step: 0.01 },
  nvidia_max_tokens: { group: "Mentor models", label: "NVIDIA output tokens", description: "Maximum student-facing response length.", min: 64, max: 16384, step: 1 },
  nvidia_enable_thinking: { group: "Mentor models", label: "NVIDIA reasoning", description: "Enable private reasoning for eligible model requests." },
  nvidia_reasoning_budget: { group: "Mentor models", label: "NVIDIA reasoning budget", description: "Maximum private reasoning tokens.", min: 0, max: 16384, step: 1 },
  gemini_model: { group: "Mentor models", label: "Gemini model", description: "Model identifier for Gemini requests." },
  gemini_max_output_tokens: { group: "Mentor models", label: "Gemini output tokens", description: "Maximum output length for Gemini.", min: 64, max: 16384, step: 1 },
  anthropic_model: { group: "Mentor models", label: "Anthropic model", description: "Model identifier for Anthropic requests." },
  anthropic_max_tokens: { group: "Mentor models", label: "Anthropic output tokens", description: "Maximum output length for Anthropic.", min: 64, max: 16384, step: 1 },
  course_retrieval_enabled: { group: "Retrieval", label: "Course retrieval enabled", description: "Include indexed course sources in mentor requests." },
  strict_grounding: { group: "Retrieval", label: "Strict grounding", description: "Exclude results below the retrieval score threshold." },
  minimum_retrieval_score: { group: "Retrieval", label: "Minimum retrieval score", description: "Lowest similarity score accepted as context.", min: 0, max: 1, step: 0.01 },
  top_k: { group: "Retrieval", label: "Retrieved chunks", description: "Maximum source chunks included per question.", min: 1, max: 25, step: 1 },
  max_context_chars: { group: "Retrieval", label: "Context character limit", description: "Maximum retrieved source text sent to the model.", min: 500, max: 50000, step: 100 },
  cache_ttl_seconds: { group: "Student experience", label: "Answer cache lifetime", description: "Cached answer lifetime in seconds.", min: 60, max: 2592000, step: 60 },
  whatsapp_default_course: { group: "Student experience", label: "Default WhatsApp course", description: "Fallback course for a WhatsApp session.", options: COURSES },
  whatsapp_messaging_enabled: { group: "Student experience", label: "WhatsApp messaging enabled", description: "Master control for inbound processing and all outbound WhatsApp replies." },
  whatsapp_open_cma_access: { group: "Student experience", label: "Open CMA access", description: "Allow every WhatsApp sender to enter CMA Teach without an enrollment record." },
  whatsapp_default_mode: { group: "Student experience", label: "Default learning mode", description: "Mode used before a student explicitly selects one.", options: ["teach", "doubt_solving", "quiz", "revise", "job_hunt"] },
  whatsapp_default_level: { group: "Student experience", label: "Default student level", description: "Starting explanation depth for WhatsApp.", options: ["beginner", "intermediate", "advanced"] },
  whatsapp_max_reply_chars: { group: "Student experience", label: "WhatsApp reply length", description: "Maximum characters in one WhatsApp message.", min: 500, max: 4000, step: 100 },
  whatsapp_feedback_number: { group: "Student experience", label: "Feedback WhatsApp number", description: "Public E.164 number used by the feedback link; digits only." },
  whatsapp_feedback_prefill: { group: "Student experience", label: "Feedback message prompt", description: "Edit the friendly guidance only. The required FEEDBACK command is added automatically." },
};

function isSensitiveSetting(key) {
  const normalized = String(key).toLowerCase();
  return normalized === "admin_token" || /(^|_)(api_key|access_token|secret|password|credential)($|_)/.test(normalized);
}

const PROVIDER_SECRET_FIELDS = {
  nvidia: "nvidia_api_key",
  gemini: "gemini_api_key",
  anthropic: "anthropic_api_key",
};

const PROVIDER_LABELS = {
  nvidia: "NVIDIA",
  gemini: "Gemini",
  anthropic: "Anthropic",
  none: "Disabled",
};

function providerHasKey(provider) {
  if (provider === "none") return true;
  const field = PROVIDER_SECRET_FIELDS[provider];
  return Boolean(field && state.configuration?.secret_status?.[field]);
}

function providerReadinessItems(settings) {
  const primary = settings.mentor_provider || "nvidia";
  const fallback = settings.mentor_fallback_provider || "none";
  const policySelection = settings.mentor_policy_provider || "primary";
  const policyProvider = policySelection === "gemini" ? "gemini" : primary;
  return [
    { role: "Primary mentor", provider: primary, ready: providerHasKey(primary) },
    { role: "Fallback mentor", provider: fallback, ready: providerHasKey(fallback), disabled: fallback === "none" },
    { role: "Policy checks", provider: policyProvider, ready: providerHasKey(policyProvider), note: policySelection === "primary" ? "Uses primary provider" : "Dedicated Gemini checks" },
  ];
}

function providerReadinessMarkup(settings) {
  return providerReadinessItems(settings).map((item) => `
    <li>
      <span><span class="health-list__name">${escapeHtml(item.role)}</span><span class="table-secondary">${escapeHtml(item.note || PROVIDER_LABELS[item.provider] || humanize(item.provider))}</span></span>
      <span>${escapeHtml(PROVIDER_LABELS[item.provider] || humanize(item.provider))} ${badge(item.disabled ? "disabled" : item.ready ? "ready" : "blocked")}</span>
    </li>`).join("");
}

function configurationValues(form) {
  const settings = {};
  let invalidNumber = false;
  form.querySelectorAll("[data-setting-key]").forEach((input) => {
    if (input.dataset.settingType === "boolean") settings[input.dataset.settingKey] = input.checked;
    else if (input.dataset.settingType === "number") {
      const parsed = Number(input.value);
      if (!Number.isFinite(parsed)) invalidNumber = true;
      settings[input.dataset.settingKey] = parsed;
    } else settings[input.dataset.settingKey] = input.value.trim();
  });
  return { settings, invalidNumber };
}

function refreshProviderReadiness(form) {
  const list = form.querySelector("#provider-readiness");
  if (!list) return;
  list.innerHTML = providerReadinessMarkup(configurationValues(form).settings);
}

function configInput(key, value) {
  const meta = SETTING_META[key] || { group: "Other", label: humanize(key), description: "Editable runtime setting." };
  const safeKey = escapeHtml(key);
  if (key === "whatsapp_feedback_prefill") {
    const copy = String(value || "").replace(/^\s*\[?feedback\]?(?:\s*[:\-]\s*|\s*\n\s*)?/i, "").trim();
    return `
      <div class="config-field field"><label class="config-field__key" for="setting-${safeKey}">${escapeHtml(meta.label)}</label><div class="input-with-prefix"><span aria-hidden="true">FEEDBACK</span><input id="setting-${safeKey}" type="text" data-setting-key="${safeKey}" data-setting-type="string" value="${escapeHtml(copy)}" maxlength="491" required></div><p class="field-help">${escapeHtml(meta.description)}</p></div>`;
  }
  if (typeof value === "boolean") {
    return `
      <div class="config-field">
        <div class="toggle-field"><span><span class="config-field__key">${escapeHtml(meta.label)}</span><span class="field-help">${escapeHtml(meta.description)}</span></span><label class="switch"><input type="checkbox" data-setting-key="${safeKey}" data-setting-type="boolean"${value ? " checked" : ""}><span aria-hidden="true"></span></label></div>
      </div>`;
  }
  if (meta.options) {
    return `
      <div class="config-field field"><label class="config-field__key" for="setting-${safeKey}">${escapeHtml(meta.label)}</label><select id="setting-${safeKey}" data-setting-key="${safeKey}" data-setting-type="string">${options(meta.options, value)}</select><p class="field-help">${escapeHtml(meta.description)}</p></div>`;
  }
  const number = typeof value === "number";
  return `
    <div class="config-field field"><label class="config-field__key" for="setting-${safeKey}">${escapeHtml(meta.label)}</label><input id="setting-${safeKey}" type="${number ? "number" : "text"}" data-setting-key="${safeKey}" data-setting-type="${number ? "number" : "string"}" value="${escapeHtml(value)}"${meta.min !== undefined ? ` min="${meta.min}"` : ""}${meta.max !== undefined ? ` max="${meta.max}"` : ""}${meta.step !== undefined ? ` step="${meta.step}"` : ""}><p class="field-help">${escapeHtml(meta.description)}</p></div>`;
}

async function loadConfiguration(sequence = state.sequence) {
  const payload = await apiRequest("/configuration");
  if (sequence !== state.sequence) return;
  const settings = Object.fromEntries(Object.entries(payload.settings || {}).filter(([key]) => !isSensitiveSetting(key)));
  const secretStatus = Object.fromEntries(Object.entries(payload.secret_status || {}).map(([key, value]) => [key, Boolean(value)]));
  state.configuration = {
    version: Number(payload.version) || 0,
    settings,
    system_prompt: payload.system_prompt || "",
    secret_status: secretStatus,
  };
  renderConfiguration();
}

function renderConfiguration() {
  const settings = state.configuration?.settings || {};
  const groups = new Map();
  Object.entries(settings).forEach(([key, value]) => {
    const group = SETTING_META[key]?.group || "Other";
    if (!groups.has(group)) groups.set(group, []);
    groups.get(group).push(configInput(key, value));
  });
  const settingsPanels = [...groups.entries()].map(([group, fields]) => `
    <section class="panel">
      <div class="panel__header"><div><h2>${escapeHtml(group)}</h2><p>Safe runtime behavior controls</p></div></div>
      <div class="panel__body"><div class="config-grid">${fields.join("")}</div></div>
    </section>`).join("");

  elements.viewRoot.innerHTML = `
    <form id="configuration-form" novalidate>
      <header class="section-heading">
        <div><span class="eyebrow">Runtime behavior</span><h2>Mentor configuration</h2><p>Adjust approved model behavior, retrieval, WhatsApp defaults, and the system prompt.</p></div>
        <div class="section-heading__actions"><button id="configuration-save-top" class="button button--primary" type="submit">${icon("check")}<span>Save configuration</span></button></div>
      </header>
      <div class="notice notice--warning">${icon("alert")}<span><strong>Credentials are intentionally protected.</strong> API keys, tokens, passwords, and infrastructure secrets are neither returned by the API nor editable in this dashboard.</span></div>
      <section class="panel">
        <div class="panel__header"><div><h2>Provider-key readiness</h2><p>Only configuration status is shown; credential values remain protected</p></div></div>
        <ul id="provider-readiness" class="health-list">${providerReadinessMarkup(settings)}</ul>
      </section>
      ${settingsPanels || `<section class="panel">${emptyMarkup("No editable settings", "The API did not return any safe runtime settings.")}</section>`}
      <section class="panel">
        <div class="panel__header"><div><h2>System prompt</h2><p>Core policy and response behavior for the AI mentor</p></div></div>
        <div class="panel__body"><div class="field"><label for="system-prompt">Mentor instructions</label><textarea id="system-prompt" class="prompt-editor" minlength="100" maxlength="20000" required>${escapeHtml(state.configuration?.system_prompt || "")}</textarea><p class="field-help">Review carefully before saving. These instructions apply to new mentor answers.</p></div></div>
        <div class="panel__footer"><button id="configuration-save" class="button button--primary" type="submit">${icon("check")}<span>Save configuration</span></button></div>
      </section>
      <p id="configuration-error" class="form-error" role="alert" hidden></p>
    </form>`;
  const form = document.querySelector("#configuration-form");
  form?.addEventListener("submit", saveConfiguration);
  form?.addEventListener("change", (event) => {
    if (["mentor_provider", "mentor_fallback_provider", "mentor_policy_provider"].includes(event.target.dataset.settingKey)) {
      refreshProviderReadiness(form);
    }
  });
}

async function saveConfiguration(event) {
  event.preventDefault();
  const form = event.currentTarget;
  const error = form.querySelector("#configuration-error");
  const buttons = [form.querySelector("#configuration-save-top"), form.querySelector("#configuration-save")];
  error.hidden = true;
  const { settings, invalidNumber } = configurationValues(form);
  const systemPrompt = form.querySelector("#system-prompt").value.trim();
  if (invalidNumber || systemPrompt.length < 100) {
    error.textContent = invalidNumber ? "Every numeric setting must contain a valid number." : "The system prompt must contain at least 100 characters.";
    error.hidden = false;
    error.scrollIntoView({ behavior: "smooth", block: "center" });
    return;
  }
  const missingProviders = providerReadinessItems(settings).filter((item) => !item.disabled && !item.ready);
  if (missingProviders.length) {
    error.textContent = `Configuration cannot be saved: ${missingProviders.map((item) => `${item.role} needs a configured ${PROVIDER_LABELS[item.provider] || humanize(item.provider)} API key`).join("; ")}. Add credentials to the deployment environment, then reload this page.`;
    error.hidden = false;
    error.scrollIntoView({ behavior: "smooth", block: "center" });
    showToast("Provider key required", "One or more selected providers are not configured.", "error");
    return;
  }
  buttons.forEach((button) => setButtonBusy(button, true));
  try {
    const payload = await apiRequest("/configuration", {
      method: "PUT",
      body: {
        version: Number(state.configuration?.version) || 0,
        settings,
        system_prompt: systemPrompt,
      },
    });
    state.configuration = {
      version: Number(payload.version) || 0,
      settings: Object.fromEntries(Object.entries(payload.settings || {}).filter(([key]) => !isSensitiveSetting(key))),
      system_prompt: payload.system_prompt || systemPrompt,
      secret_status: payload.secret_status
        ? Object.fromEntries(Object.entries(payload.secret_status).map(([key, value]) => [key, Boolean(value)]))
        : state.configuration?.secret_status || {},
    };
    state.overview = null;
    showToast("Configuration saved", "New mentor requests will use the updated runtime behavior.");
    renderConfiguration();
    updateTimestamp();
  } catch (requestError) {
    error.textContent = requestError.status === 409
      ? `${requestError.message} Use Refresh before saving again.`
      : requestError.message;
    error.hidden = false;
    error.scrollIntoView({ behavior: "smooth", block: "center" });
    buttons.forEach((button) => setButtonBusy(button, false));
  }
}

function enrollmentSourceCopy(source) {
  if (source === "excel") return "Excel workbook · live on disk";
  if (source === "google_sheet") return "Google Sheet · live synchronization";
  return "Dashboard-managed enrollment";
}

function enrollmentNoticeMarkup() {
  const source = state.enrollment?.source;
  if (!source) {
    return `<strong>Enrollment source:</strong> search for a student to see whether access is controlled by Excel, Google Sheets, or the dashboard store.`;
  }
  if (source === "google_sheet") {
    return `<strong>Live Google Sheet:</strong> Save, Revoke, and bulk import append validated state rows to the configured Sheet immediately.`;
  }
  if (source === "redis") {
    return `<strong>Dashboard-managed access:</strong> changes are saved to the configured enrollment store immediately.`;
  }
  return `<strong>Live Excel sync:</strong> Save and Revoke update the configured workbook on disk immediately. If it is already open in Excel, close and reopen it or use Excel’s refresh/reload option.`;
}

function enrollmentResultMarkup() {
  const enrollment = state.enrollment;
  if (!enrollment) {
    return emptyMarkup("Find a WhatsApp student", "Enter an international phone number to review enrollment and send a welcome message.");
  }
  const courses = Array.isArray(enrollment.courses) ? enrollment.courses : [];
  const phone = enrollment.phone || state.enrollmentPhone;
  const initials = courses[0]?.slice(0, 2) || "WA";
  const courseChips = courses.length
    ? courses.map((course) => `<span class="chip">${escapeHtml(course)}<button class="chip__remove" type="button" data-revoke-course="${escapeHtml(course)}" aria-label="Revoke ${escapeHtml(course)} access" title="Revoke ${escapeHtml(course)} access">${icon("close")}</button></span>`).join("")
    : '<span class="muted">No courses assigned</span>';
  const editor = `<form id="enrollment-update-form" style="margin-top:24px">
        <div class="field"><label for="enrollment-course">Add or update course access</label><select id="enrollment-course" required>${options(COURSES, enrollment.course || courses[0] || "CMA")}</select><p class="field-help">${enrollment.source === "excel" ? "Saving writes this course immediately to the Excel workbook." : "Saving grants the selected course to this WhatsApp number."}</p></div>
        <p id="enrollment-update-error" class="form-error" role="alert" hidden></p>
        <div class="form-actions"><button id="enrollment-save" class="button button--primary" type="submit"><span>Save enrollment</span>${icon("check")}</button></div>
      </form>`;
  return `
    <div class="profile-card">
      <div class="profile-card__header"><span class="profile-avatar">${escapeHtml(initials)}</span><span><h3>${escapeHtml(phone)}</h3><p>${courses.length ? "Active WhatsApp enrollment" : "No active courses found"} · ${enrollmentSourceCopy(enrollment.source)}</p></span></div>
      <div><span class="field-label">Enrolled courses</span><div class="chip-list">${courseChips}</div></div>
      ${editor}
    </div>`;
}

function renderEnrollments() {
  const whatsapp = state.whatsappStatus || {};
  const queue = whatsapp.queue?.counts || {};
  const enabled = whatsapp.enabled === true;
  const directMode = whatsapp.delivery_mode === "direct_meta";
  const inboundHealthy = directMode && whatsapp.routing_ready === true && whatsapp.recent_inbound === true;
  const callback = whatsapp.webhook_callback_url || "Not configured in this deployment";
  const directCallback = whatsapp.direct_callback_path || "/v1/whatsapp/ziplin/webhook";
  const rosterRows = state.enrollmentRoster.map((item) => `<tr><td><strong>${escapeHtml(item.phone)}</strong></td><td>${(item.courses || []).map((course) => `<span class="badge">${escapeHtml(course)}</span>`).join(" ")}</td><td>${escapeHtml(enrollmentSourceCopy(item.source))}</td><td><button class="button button--ghost button--small" type="button" data-open-enrollment="${escapeHtml(item.phone)}">Manage</button></td></tr>`).join("");
  elements.viewRoot.innerHTML = `
    <header class="section-heading">
      <div><span class="eyebrow">Student access</span><h2>WhatsApp enrollments</h2><p>Look up course access, update an enrollment, or send the approved welcome template.</p></div>
    </header>
    <section class="panel whatsapp-control-panel">
      <div class="panel__header"><div><h2>WhatsApp messaging control</h2><p>Master status and non-sensitive integration details</p></div><div class="whatsapp-master-control"><span>${badge(enabled ? "active" : "paused")}</span><label class="switch" title="${enabled ? "Pause WhatsApp messaging" : "Enable WhatsApp messaging"}"><input id="whatsapp-enabled-switch" type="checkbox"${enabled ? " checked" : ""}><span aria-hidden="true"></span></label></div></div>
      <div class="panel__body">
        <div class="whatsapp-status-grid">
          <div class="status-tile"><span>Inbound routing</span><strong>${inboundHealthy ? "Messages received" : whatsapp.routing_ready ? "Configured" : "Not configured"}</strong>${badge(inboundHealthy ? "ready" : whatsapp.routing_ready ? "waiting" : "blocked")}</div>
          <div class="status-tile"><span>Outbound credentials</span><strong>${whatsapp.outbound_ready ? "Present" : "Missing"}</strong>${badge(whatsapp.outbound_ready ? "configured" : "blocked")}</div>
          <div class="status-tile"><span>Waiting / processing</span><strong>${formatNumber(Number(queue.pending || 0) + Number(queue.processing || 0))}</strong><small>${formatNumber(queue.failed || 0)} retrying</small></div>
          <div class="status-tile"><span>Completed / dead letter</span><strong>${formatNumber(queue.completed || 0)}</strong><small>${formatNumber(queue.dead_letter || 0)} need attention</small></div>
        </div>
        <dl class="definition-list whatsapp-definition-list">
          <div><dt>Configured Meta callback</dt><dd>${escapeHtml(callback)}</dd></div>
          <div><dt>Delivery target</dt><dd>${directMode ? "Direct Meta webhook" : "Direct Meta migration required"}</dd></div>
          <div><dt>Required Ziplin endpoint</dt><dd>${escapeHtml(directCallback)}</dd></div>
          <div><dt>Public HTTPS origin</dt><dd>${escapeHtml(whatsapp.public_base_url || "No stable public URL configured")}</dd></div>
          <div><dt>Bot display number</dt><dd>${escapeHtml(whatsapp.feedback_number ? `+${whatsapp.feedback_number}` : "Not configured")}</dd></div>
          <div><dt>Phone number ID</dt><dd>${escapeHtml(whatsapp.phone_number_id || "Not configured")}</dd></div>
          <div><dt>CMA access</dt><dd>${whatsapp.open_cma_access ? "Open to every sender" : "Enrollment required"}</dd></div>
          <div><dt>Business account ID</dt><dd>${escapeHtml(whatsapp.business_account_id || "Not configured")}</dd></div>
          <div><dt>Graph API</dt><dd>${escapeHtml(whatsapp.graph_api_version || "Not configured")}</dd></div>
          <div><dt>Authentication</dt><dd>Token ${whatsapp.access_token_configured ? "configured" : "missing"} · Meta signature ${whatsapp.signature_configured ? "configured" : "missing"}</dd></div>
          <div><dt>Defaults</dt><dd>${escapeHtml(whatsapp.default_course || "—")} · ${escapeHtml(humanize(whatsapp.default_mode || "—"))} · ${escapeHtml(humanize(whatsapp.default_level || "—"))}</dd></div>
          <div><dt>Enrollment source</dt><dd>${escapeHtml(enrollmentSourceCopy(whatsapp.enrollment_source || state.enrollmentSource))}</dd></div>
          <div><dt>Latest event</dt><dd>${whatsapp.queue?.latest_event ? `${escapeHtml(humanize(whatsapp.queue.latest_event.status))} · ${escapeHtml(formatDate(whatsapp.queue.latest_event.updated_at))}` : "No webhook events recorded"}</dd></div>
        </dl>
        <div class="notice ${enabled && inboundHealthy ? "" : "notice--error"}">${icon(enabled && inboundHealthy ? "info" : "alert")}<span>${!enabled ? "Messaging is paused. Student messages are discarded and outbound sends are blocked; delivery and read receipts continue updating the protected inbox." : !directMode ? `This deployment targets direct Meta delivery. Point the Ziplin Meta app callback at the permanent HTTPS origin plus ${escapeHtml(directCallback)} and remove the legacy callback before treating inbound as live.` : !whatsapp.stable_ingress_configured ? "Direct Meta delivery needs a permanent HTTPS origin. Configure NORTHSTAR_PUBLIC_BASE_URL and a named tunnel or managed ingress; quick-tunnel hostnames are not production routing." : !whatsapp.signature_configured ? "Direct Meta delivery is missing the Ziplin Meta app secret required to verify X-Hub-Signature-256." : !whatsapp.routing_ready ? "The direct Ziplin Meta webhook is missing its verification-token configuration." : !whatsapp.recent_inbound ? "The direct Ziplin webhook is configured, but no genuine inbound message has arrived recently. Send a test message before treating the route as live." : "Ziplin messaging is active and a genuine Meta webhook has reached this isolated bot. Outbound credentials are present; Meta permissions must still be monitored."}</span></div>
      </div>
    </section>
    <div class="enrollment-layout">
      <section class="panel">
        <div class="panel__header"><div><h2>Student lookup</h2><p>Use a complete international WhatsApp number</p></div></div>
        <div class="panel__body">
          <form id="enrollment-search-form">
            <div class="field"><label for="enrollment-phone">Phone number</label><div class="enrollment-search"><input id="enrollment-phone" type="tel" inputmode="tel" autocomplete="tel" maxlength="20" value="${escapeHtml(state.enrollmentPhone)}" placeholder="e.g. 919876543210" required><button id="enrollment-search-button" class="button button--primary" type="submit">${icon("search")}<span>Find student</span></button></div><p class="field-help">Include the country code. Spaces and a leading + are accepted.</p></div>
            <p id="enrollment-search-error" class="form-error" role="alert" hidden></p>
          </form>
          <div class="notice" style="margin:24px 0 0">${icon("info")}<span>${enrollmentNoticeMarkup()}</span></div>
        </div>
      </section>
      <section class="panel">
        <div class="panel__header"><div><h2>Enrollment details</h2><p>${state.enrollment ? "Current access for this number" : "Search to view a student"}</p></div>${state.enrollment && (state.enrollment.courses || []).length ? '<button id="send-hi" class="button button--secondary button--small" type="button">' + icon("phone") + '<span>Send welcome</span></button>' : ""}</div>
        <div class="panel__body panel__body--flush">${enrollmentResultMarkup()}</div>
      </section>
    </div>
    <section class="panel" style="margin-top:20px">
      <div class="panel__header"><div><h2>Bulk Excel upload</h2><p>Import up to 2,000 YES/NO rows into ${escapeHtml(enrollmentSourceCopy(state.enrollmentSource))}</p></div></div>
      <div class="panel__body"><form id="enrollment-import-form" class="bulk-import-form"><div class="field"><label for="enrollment-import-file">Excel workbook</label><input id="enrollment-import-file" type="file" accept=".xlsx,application/vnd.openxmlformats-officedocument.spreadsheetml.sheet" required><p class="field-help">Columns: phone_number, course, active; optional student_name and notes. A valid phone with blank course/active defaults to CMA/YES.</p></div><button id="enrollment-import-button" class="button button--primary" type="submit">${icon("upload")}<span>Import enrollments</span></button></form></div>
    </section>
    <section class="panel" style="margin-top:20px">
      <div class="panel__header"><div><h2>Enrollment roster</h2><p>${formatNumber(state.enrollmentRoster.length)} active student record(s)</p></div></div>
      <div class="panel__body panel__body--flush">${rosterRows ? `<div class="data-table-wrap"><table class="data-table"><thead><tr><th>Phone</th><th>Courses</th><th>Source</th><th></th></tr></thead><tbody>${rosterRows}</tbody></table></div>` : emptyMarkup("No active enrollments", "Create one above or upload an Excel workbook.")}</div>
    </section>`;
  bindEnrollmentEvents();
}

function bindEnrollmentEvents() {
  document.querySelector("#whatsapp-enabled-switch")?.addEventListener("change", async (event) => {
    const input = event.currentTarget;
    const requested = input.checked;
    input.disabled = true;
    try {
      state.whatsappStatus = await apiRequest("/whatsapp/messaging", {
        method: "PUT",
        body: { enabled: requested, version: Number(state.whatsappStatus?.configuration_version || 0) },
      });
      state.configuration = null;
      showToast(requested ? "WhatsApp messaging enabled" : "WhatsApp messaging paused", requested ? "Inbound processing and outbound replies are active." : "New inbound messages and outbound sends are now paused.");
      renderEnrollments();
    } catch (error) {
      input.checked = !requested;
      input.disabled = false;
      showToast("Could not update WhatsApp", error.message, "error");
      if (error.status === 409) {
        state.whatsappStatus = await apiRequest("/whatsapp/status");
        renderEnrollments();
      }
    }
  });
  document.querySelectorAll("[data-open-enrollment]").forEach((button) => button.addEventListener("click", async () => {
    state.enrollmentPhone = button.dataset.openEnrollment;
    state.enrollment = await apiRequest(`/whatsapp/enrollments/${encodeURIComponent(state.enrollmentPhone)}`);
    renderEnrollments();
  }));
  document.querySelector("#enrollment-import-form")?.addEventListener("submit", async (event) => {
    event.preventDefault();
    const input = document.querySelector("#enrollment-import-file");
    const button = document.querySelector("#enrollment-import-button");
    if (!input.files?.length) return;
    const form = new FormData();
    form.append("file", input.files[0]);
    setButtonBusy(button, true);
    try {
      const result = await apiRequest("/whatsapp/enrollments/import", { method: "POST", body: form });
      showToast("Enrollment import complete", `${result.rows} rows applied: ${result.granted} granted and ${result.revoked} revoked.`);
      const roster = await apiRequest("/whatsapp/enrollments?limit=200&offset=0");
      state.enrollmentRoster = roster.items || [];
      state.enrollmentSource = roster.source || "";
      renderEnrollments();
    } catch (error) {
      showToast("Import failed", error.message, "error");
      setButtonBusy(button, false);
    }
  });
  document.querySelector("#enrollment-search-form")?.addEventListener("submit", async (event) => {
    event.preventDefault();
    const phoneInput = document.querySelector("#enrollment-phone");
    const phone = phoneInput.value.trim();
    const error = document.querySelector("#enrollment-search-error");
    const button = document.querySelector("#enrollment-search-button");
    error.hidden = true;
    if (!phone) return;
    setButtonBusy(button, true);
    try {
      state.enrollment = await apiRequest(`/whatsapp/enrollments/${encodeURIComponent(phone)}`);
      state.enrollmentPhone = state.enrollment.phone || phone;
      renderEnrollments();
      updateTimestamp();
    } catch (requestError) {
      if (requestError.status === 404) {
        state.enrollmentPhone = phone;
        state.enrollment = { phone, courses: [], course: null, source: state.enrollmentSource || "redis" };
        renderEnrollments();
        showToast("No enrollment found", "Choose a course to create access for this number.", "error");
      } else {
        error.textContent = requestError.message;
        error.hidden = false;
        setButtonBusy(button, false);
      }
    }
  });
  document.querySelector("#enrollment-update-form")?.addEventListener("submit", async (event) => {
    event.preventDefault();
    const phone = state.enrollment?.phone || state.enrollmentPhone;
    const course = document.querySelector("#enrollment-course").value;
    const error = document.querySelector("#enrollment-update-error");
    const button = document.querySelector("#enrollment-save");
    error.hidden = true;
    setButtonBusy(button, true);
    try {
      state.enrollment = await apiRequest(`/whatsapp/enrollments/${encodeURIComponent(phone)}`, { method: "PUT", body: { course } });
      state.enrollmentPhone = state.enrollment.phone || phone;
      await refreshEnrollmentRoster();
      showToast(state.enrollment.source === "excel" ? "Excel workbook updated" : state.enrollment.source === "google_sheet" ? "Google Sheet updated" : "Enrollment saved", `${course} access is now active for this number.`);
      renderEnrollments();
    } catch (requestError) {
      error.textContent = requestError.message;
      error.hidden = false;
      setButtonBusy(button, false);
    }
  });
  document.querySelector("#send-hi")?.addEventListener("click", async (event) => {
    const button = event.currentTarget;
    setButtonBusy(button, true);
    try {
      await apiRequest("/whatsapp/send-hi", { method: "POST", body: { to: state.enrollment.phone || state.enrollmentPhone } });
      showToast("Welcome message sent", "WhatsApp accepted the approved start template.");
    } catch (error) {
      showToast("Message not sent", error.message, "error");
    } finally {
      setButtonBusy(button, false);
    }
  });
  document.querySelectorAll("[data-revoke-course]").forEach((button) => button.addEventListener("click", () => revokeEnrollmentCourse(button.dataset.revokeCourse, button)));
}

async function refreshEnrollmentRoster() {
  const roster = await apiRequest("/whatsapp/enrollments?limit=200&offset=0");
  state.enrollmentRoster = Array.isArray(roster.items) ? roster.items : [];
  state.enrollmentSource = roster.source || "";
}

async function revokeEnrollmentCourse(course, button) {
  const phone = state.enrollment?.phone || state.enrollmentPhone;
  if (!phone || !course) return;
  const confirmed = await confirmAction({
    title: `Revoke ${course} access?`,
    message: `This removes <strong>${escapeHtml(course)}</strong> from <strong>${escapeHtml(phone)}</strong>. The student will no longer be able to use that course through the WhatsApp mentor.`,
    confirmLabel: "Revoke course",
    danger: true,
  });
  if (!confirmed) return;
  setButtonBusy(button, true);
  setProgress(true);
  try {
    state.enrollment = await apiRequest(`/whatsapp/enrollments/${encodeURIComponent(phone)}/${encodeURIComponent(course)}`, { method: "DELETE" });
    await refreshEnrollmentRoster();
    showToast(state.enrollment.source === "excel" ? "Excel workbook updated" : state.enrollment.source === "google_sheet" ? "Google Sheet updated" : "Course access revoked", `${course} was removed from this WhatsApp enrollment.`);
    renderEnrollments();
  } catch (error) {
    showToast("Could not revoke access", error.message, "error");
    setButtonBusy(button, false);
  } finally {
    setProgress(false);
  }
}

function showLogin(message = "") {
  state.authenticated = false;
  stopTrainingPoll();
  stopConversationPoll();
  closeDialog();
  elements.app.hidden = true;
  elements.loginView.hidden = false;
  elements.loginError.textContent = message;
  elements.loginError.hidden = !message;
  elements.loginToken.type = "password";
  elements.toggleToken.setAttribute("aria-pressed", "false");
  elements.toggleToken.setAttribute("aria-label", "Show admin token");
  window.setTimeout(() => elements.loginToken.focus(), 0);
}

function enterDashboard(overview) {
  state.authenticated = true;
  state.overview = overview;
  elements.loginToken.value = "";
  elements.loginError.hidden = true;
  elements.loginView.hidden = true;
  elements.app.hidden = false;
  if (!ROUTES[location.hash.slice(1)]) history.replaceState(null, "", "#overview");
  loadRoute();
}

function signOut(message = "") {
  sessionStorage.removeItem(TOKEN_STORAGE_KEY);
  state.overview = null;
  state.documents = [];
  state.jobs = [];
  state.feedback = [];
  state.conversations = [];
  state.conversationsRenderedSignature = "";
  state.conversationFocusTarget = null;
  state.activeConversationId = null;
  state.activeConversationSignature = "";
  state.auditEvents = [];
  state.configuration = null;
  state.enrollment = null;
  state.selectedDocumentIds.clear();
  Object.values(state.pages).forEach((page) => {
    page.offset = 0;
    page.total = 0;
    page.count = 0;
  });
  closeMobileNavigation();
  showLogin(message);
}

async function authenticate(token) {
  sessionStorage.setItem(TOKEN_STORAGE_KEY, token);
  try {
    return await apiRequest("/overview");
  } catch (error) {
    sessionStorage.removeItem(TOKEN_STORAGE_KEY);
    throw error;
  }
}

function bindApplicationEvents() {
  elements.loginForm.addEventListener("submit", async (event) => {
    event.preventDefault();
    const token = elements.loginToken.value.trim();
    elements.loginError.hidden = true;
    elements.loginToken.setAttribute("aria-invalid", "false");
    if (!token) {
      elements.loginToken.setAttribute("aria-invalid", "true");
      elements.loginError.textContent = "Enter the admin token to continue.";
      elements.loginError.hidden = false;
      return;
    }
    setButtonBusy(elements.loginSubmit, true);
    try {
      const overview = await authenticate(token);
      enterDashboard(overview);
    } catch (error) {
      elements.loginToken.setAttribute("aria-invalid", "true");
      elements.loginError.textContent = error.status === 401 ? "That admin token is not valid." : error.message;
      elements.loginError.hidden = false;
    } finally {
      setButtonBusy(elements.loginSubmit, false);
    }
  });

  elements.toggleToken.addEventListener("click", () => {
    const revealing = elements.loginToken.type === "password";
    elements.loginToken.type = revealing ? "text" : "password";
    elements.toggleToken.setAttribute("aria-pressed", String(revealing));
    elements.toggleToken.setAttribute("aria-label", revealing ? "Hide admin token" : "Show admin token");
    elements.loginToken.focus();
  });
  elements.logoutButton.addEventListener("click", () => signOut());
  elements.refreshButton.addEventListener("click", () => loadRoute(true));
  elements.menuButton.addEventListener("click", () => {
    if (elements.sidebar.classList.contains("is-open")) closeMobileNavigation();
    else openMobileNavigation();
  });
  elements.sidebarBackdrop.addEventListener("click", closeMobileNavigation);
  document.querySelectorAll("[data-route]").forEach((button) => button.addEventListener("click", () => navigate(button.dataset.route)));
  window.addEventListener("hashchange", () => loadRoute());
  window.addEventListener("resize", () => { if (window.innerWidth > 960) closeMobileNavigation(); });
  document.addEventListener("visibilitychange", () => {
    if (document.visibilityState !== "visible") stopConversationPoll();
    else if (state.route === "conversations") scheduleConversationPoll();
  });
  elements.dialogClose.addEventListener("click", closeDialog);
  elements.dialog.addEventListener("click", (event) => { if (event.target === elements.dialog) closeDialog(); });
  elements.dialog.addEventListener("close", () => {
    elements.dialogBody.innerHTML = "";
    elements.dialog.classList.remove("dialog--conversation");
    state.activeConversationId = null;
    state.activeConversationSignature = "";
  });
}

async function initialize() {
  bindApplicationEvents();
  const existingToken = sessionStorage.getItem(TOKEN_STORAGE_KEY);
  if (!existingToken) {
    showLogin();
    return;
  }
  elements.loginToken.value = "";
  setButtonBusy(elements.loginSubmit, true);
  try {
    const overview = await apiRequest("/overview");
    enterDashboard(overview);
  } catch (error) {
    sessionStorage.removeItem(TOKEN_STORAGE_KEY);
    showLogin(error.status === 401 ? "Your previous admin session expired. Sign in again." : error.message);
  } finally {
    setButtonBusy(elements.loginSubmit, false);
  }
}

initialize();
