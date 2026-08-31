import { mkdtemp, rm } from "node:fs/promises";
import { tmpdir } from "node:os";
import { join } from "node:path";
import { spawn } from "node:child_process";

const chromePath = process.env.CHROME_PATH;
const dashboardUrl = process.env.DASHBOARD_URL || "http://127.0.0.1:8000/admin/";
const adminToken = process.env.DASHBOARD_ADMIN_TOKEN;
const debuggingPort = Number(process.env.CHROME_DEBUGGING_PORT || 9228);

if (!chromePath || !adminToken) {
  throw new Error("Set CHROME_PATH and DASHBOARD_ADMIN_TOKEN before running this smoke test.");
}

const profile = await mkdtemp(join(tmpdir(), "northstar-dashboard-smoke-"));
const chrome = spawn(chromePath, [
  "--headless=new",
  "--disable-gpu",
  "--no-first-run",
  `--remote-debugging-port=${debuggingPort}`,
  `--user-data-dir=${profile}`,
  dashboardUrl,
], { stdio: "ignore" });

const delay = (milliseconds) => new Promise((resolve) => setTimeout(resolve, milliseconds));

async function targets() {
  for (let attempt = 0; attempt < 30; attempt += 1) {
    try {
      const response = await fetch(`http://127.0.0.1:${debuggingPort}/json`);
      if (response.ok) return response.json();
    } catch {
      // Chrome may still be starting.
    }
    await delay(200);
  }
  throw new Error("Chrome DevTools endpoint did not become ready.");
}

let socket;
try {
  const page = (await targets()).find((target) => target.type === "page");
  if (!page) throw new Error("Chrome did not create a page target.");
  socket = new WebSocket(page.webSocketDebuggerUrl);
  await new Promise((resolve, reject) => {
    socket.onopen = resolve;
    socket.onerror = reject;
  });

  let sequence = 0;
  const pending = new Map();
  const exceptions = [];
  socket.onmessage = (event) => {
    const message = JSON.parse(event.data);
    if (message.id && pending.has(message.id)) {
      const request = pending.get(message.id);
      pending.delete(message.id);
      if (message.error) request.reject(new Error(message.error.message));
      else request.resolve(message.result);
    }
    if (message.method === "Runtime.exceptionThrown") {
      exceptions.push(message.params.exceptionDetails.exception?.description || message.params.exceptionDetails.text);
    }
  };

  const send = (method, params = {}) => new Promise((resolve, reject) => {
    const id = ++sequence;
    pending.set(id, { resolve, reject });
    socket.send(JSON.stringify({ id, method, params }));
  });
  const evaluate = async (expression) => {
    const response = await send("Runtime.evaluate", { expression, returnByValue: true, awaitPromise: true });
    if (response.exceptionDetails) throw new Error(response.exceptionDetails.text);
    return response.result.value;
  };

  await send("Runtime.enable");
  await send("Page.enable");
  await evaluate(`sessionStorage.setItem("northstar.admin.token", ${JSON.stringify(adminToken)}); location.hash = "#overview"; location.reload()`);
  await delay(1800);

  const expected = {
    overview: "Overview",
    knowledge: "Knowledge",
    training: "Training",
    feedback: "Feedback",
    enrollments: "Enrollments",
    analytics: "Analytics",
    activity: "Activity",
    configuration: "Configuration",
  };
  const viewports = [
    { label: "desktop", width: 1440, height: 1000 },
    { label: "mobile", width: 390, height: 844 },
  ];
  const results = [];

  for (const viewport of viewports) {
    await send("Emulation.setDeviceMetricsOverride", {
      width: viewport.width,
      height: viewport.height,
      deviceScaleFactor: 1,
      mobile: viewport.label === "mobile",
    });
    for (const [route, expectedTitle] of Object.entries(expected)) {
      await evaluate(`location.hash = ${JSON.stringify(`#${route}`)}`);
      await delay(route === "training" ? 1300 : 700);
      const state = JSON.parse(await evaluate(`JSON.stringify({
        title: document.querySelector("#page-title")?.textContent?.trim() || "",
        content: document.querySelector("#view-root")?.innerText?.trim() || "",
        loading: Boolean(document.querySelector("#view-root .skeleton")),
        error: document.querySelector("#view-root .error-state")?.innerText || "",
        overflow: document.documentElement.scrollWidth > document.documentElement.clientWidth + 1,
        offenders: [...document.querySelectorAll("body *")]
          .filter((element) => element.getBoundingClientRect().right > document.documentElement.clientWidth + 1)
          .slice(0, 8)
          .map((element) => ({ tag: element.tagName, className: element.className, right: Math.round(element.getBoundingClientRect().right) }))
      })`));
      const requiredText = route === "training"
        ? "WhatsApp answer preview"
        : route === "enrollments" ? "WhatsApp messaging control" : "";
      const passed = state.title === expectedTitle
        && state.content.length > 0
        && (!requiredText || state.content.includes(requiredText))
        && !state.loading
        && !state.error
        && !state.overflow;
      results.push({ viewport: viewport.label, route, passed, ...state, content: undefined });
    }
  }

  const failures = results.filter((result) => !result.passed);
  process.stdout.write(`${JSON.stringify({ passed: results.length - failures.length, total: results.length, failures, exceptions }, null, 2)}\n`);
  if (failures.length || exceptions.length) process.exitCode = 1;
} finally {
  socket?.close();
  chrome.kill("SIGTERM");
  await delay(250);
  await rm(profile, { recursive: true, force: true });
}
