const sleep = (ms) => new Promise((resolve) => setTimeout(resolve, ms));

async function fetchWithTimeout(url, options = {}, timeoutMs = 2000) {
  const controller = new AbortController();
  const id = setTimeout(() => controller.abort(), timeoutMs);
  try {
    return await fetch(url, { ...options, signal: controller.signal });
  } finally {
    clearTimeout(id);
  }
}

async function waitForStatus(timeoutMs = 15000) {
  const loadingText = document.querySelector("#loading p");
  let attempts = 0;
  const deadline = Date.now() + timeoutMs;
  while (true) {
    attempts += 1;
    try {
      const url = new URL("/status", window.location.origin);
      url.searchParams.set("_", Date.now().toString());
      const resp = await fetchWithTimeout(url, {}, 2000);
      if (resp.ok) return await resp.json();
    } catch (e) {}
    if (loadingText) {
      loadingText.textContent = attempts > 8 ? "Starting backend…" : "Loading…";
    }
    if (Date.now() >= deadline) return null;
    await sleep(500);
  }
}

async function validateKey(key) {
  const body = { openai_api_key: key };
  const resp = await fetch("/validate_api_key", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body),
  });
  const data = await resp.json().catch(() => ({}));
  if (!resp.ok) {
    throw new Error(data.error || "validation_failed");
  }
  return data;
}

async function saveKey(key) {
  const body = { openai_api_key: key };
  const resp = await fetch("/openai_api_key", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body),
  });
  if (!resp.ok) {
    const data = await resp.json().catch(() => ({}));
    throw new Error(data.error || "save_failed");
  }
  return await resp.json();
}

function show(el, flag) {
  el.classList.toggle("hidden", !flag);
}

async function init() {
  const loading = document.getElementById("loading");
  const statusEl = document.getElementById("status");
  const formPanel = document.getElementById("form-panel");
  const configuredPanel = document.getElementById("configured");
  const saveBtn = document.getElementById("save-btn");
  const changeKeyBtn = document.getElementById("change-key-btn");
  const input = document.getElementById("api-key");

  show(loading, true);
  show(formPanel, false);
  show(configuredPanel, false);

  const st = (await waitForStatus()) || { has_key: false };

  if (st.has_key) {
    show(configuredPanel, true);
  } else {
    show(formPanel, true);
  }
  show(loading, false);

  changeKeyBtn.addEventListener("click", () => {
    show(configuredPanel, false);
    show(formPanel, true);
    input.value = "";
    statusEl.textContent = "";
    statusEl.className = "status";
  });

  input.addEventListener("input", () => {
    input.classList.remove("error");
  });

  saveBtn.addEventListener("click", async () => {
    const key = input.value.trim();
    if (!key) {
      statusEl.textContent = "Please enter a valid key.";
      statusEl.className = "status warn";
      input.classList.add("error");
      return;
    }
    statusEl.textContent = "Validating API key...";
    statusEl.className = "status";
    input.classList.remove("error");
    try {
      const validation = await validateKey(key);
      if (!validation.valid) {
        statusEl.textContent = "Invalid API key. Please check your key and try again.";
        statusEl.className = "status error";
        input.classList.add("error");
        return;
      }
      statusEl.textContent = "Key valid! Saving...";
      statusEl.className = "status ok";
      await saveKey(key);
      statusEl.textContent = "Saved. Reloading…";
      statusEl.className = "status ok";
      window.location.reload();
    } catch (e) {
      input.classList.add("error");
      if (e.message === "invalid_api_key") {
        statusEl.textContent = "Invalid API key. Please check your key and try again.";
      } else {
        statusEl.textContent = "Failed to validate/save key. Please try again.";
      }
      statusEl.className = "status error";
    }
  });
}

async function loadEventConfig() {
  const eventPanel = document.getElementById("event-config-panel");
  try {
    const resp = await fetchWithTimeout("/event_config", {}, 3000);
    if (!resp.ok) return;
    const data = await resp.json();
    const set = (id, val) => { if (val) document.getElementById(id).value = val; };
    set("content-repo-url", data.content_repo_url);
    set("event-provider", data.event_provider);
    set("event-name", data.event_name);
    set("luma-client-version", data.luma_client_version);
    const keyInput = document.getElementById("luma-session-key");
    keyInput.placeholder = data.has_luma_session_key
      ? "Leave blank to keep current key"
      : "Paste fresh key from browser devtools";
  } catch (e) {}
  show(eventPanel, true);
}

async function saveEventConfig() {
  const statusEl = document.getElementById("event-status");
  statusEl.textContent = "Saving…";
  statusEl.className = "status";

  const body = {
    content_repo_url: document.getElementById("content-repo-url").value.trim(),
    event_provider: document.getElementById("event-provider").value.trim(),
    event_name: document.getElementById("event-name").value.trim(),
    luma_client_version: document.getElementById("luma-client-version").value.trim(),
  };
  const lumaKey = document.getElementById("luma-session-key").value.trim();
  if (lumaKey) body.luma_session_key = lumaKey;

  try {
    const resp = await fetch("/event_config", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(body),
    });
    const data = await resp.json().catch(() => ({}));
    if (!resp.ok) {
      statusEl.textContent = data.error || "Save failed. Please try again.";
      statusEl.className = "status error";
      return;
    }
    statusEl.textContent = "Settings saved.";
    statusEl.className = "status ok";
    document.getElementById("luma-session-key").value = "";
    await loadEventConfig();
  } catch (e) {
    statusEl.textContent = "Save failed. Please try again.";
    statusEl.className = "status error";
  }
}

window.addEventListener("DOMContentLoaded", async () => {
  await init();
  await loadEventConfig();
  document.getElementById("event-save-btn").addEventListener("click", saveEventConfig);
});