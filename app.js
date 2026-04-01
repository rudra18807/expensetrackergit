const state = {
  tracker: null,
};

const serverStatusText = document.getElementById("server-status-text");

const createTrackerBtn = document.getElementById("create-tracker-btn");
const existingIdInput = document.getElementById("existing-id-input");
const loadTrackerBtn = document.getElementById("load-tracker-btn");
const authStatus = document.getElementById("auth-status");

const authSection = document.getElementById("auth-section");
const trackerSection = document.getElementById("tracker-section");
const trackerIdLabel = document.getElementById("tracker-id-label");
const balanceLabel = document.getElementById("balance-label");
const txList = document.getElementById("tx-list");
const txForm = document.getElementById("tx-form");
const txDescription = document.getElementById("tx-description");
const txAmount = document.getElementById("tx-amount");
const txType = document.getElementById("tx-type");
const logoutBtn = document.getElementById("logout-btn");

function setAuthStatus(message, isError) {
  authStatus.textContent = message;
  authStatus.style.color = isError ? "#dc2626" : "#0f766e";
}

function setServerStatus(message, isError) {
  serverStatusText.textContent = message;
  serverStatusText.style.color = isError ? "#dc2626" : "#16a34a";
}

async function apiRequest(path, options = {}) {
  const response = await fetch(path, {
    ...options,
    headers: {
      "Content-Type": "application/json",
      ...(options.headers || {}),
    },
  });

  if (!response.ok) {
    const details = await response.text();
    throw new Error(`Server error: ${response.status} ${details}`);
  }

  return response.json();
}

async function createTracker() {
  setAuthStatus("Creating tracker...", false);
  try {
    const result = await apiRequest("/api/tracker", { method: "POST" });
    state.tracker = {
      trackerId: result.clientId,
      transactions: [],
    };
    setAuthStatus(`Tracker created. Your ID is ${result.clientId}`, false);
    renderTracker();
  } catch (error) {
    setAuthStatus(error.message, true);
  }
}

function parseTransactions(raw) {
  if (!raw) return [];
  try {
    const parsed = JSON.parse(raw);
    return Array.isArray(parsed) ? parsed : [];
  } catch {
    return [];
  }
}

async function loadExistingTracker() {
  const trackerId = existingIdInput.value.trim();
  if (!/^\d{10}$/.test(trackerId)) {
    setAuthStatus("Please enter a valid 10-digit ID.", true);
    return;
  }

  setAuthStatus("Looking up tracker...", false);

  try {
    const result = await apiRequest(`/api/tracker/${trackerId}`, { method: "GET" });
    state.tracker = {
      trackerId: result.clientId,
      transactions: Array.isArray(result.transactions) ? result.transactions : [],
    };

    setAuthStatus("Tracker loaded.", false);
    renderTracker();
  } catch (error) {
    setAuthStatus(error.message, true);
  }
}

function getBalance() {
  return state.tracker.transactions.reduce((total, tx) => {
    return tx.type === "expense" ? total - Number(tx.amount) : total + Number(tx.amount);
  }, 0);
}

function formatCurrency(value) {
  return new Intl.NumberFormat("en-US", {
    style: "currency",
    currency: "USD",
  }).format(value);
}

function renderTransactions() {
  txList.innerHTML = "";
  const txs = [...state.tracker.transactions].reverse();
  if (!txs.length) {
    txList.innerHTML = '<p class="muted">No transactions yet.</p>';
    return;
  }

  for (const tx of txs) {
    const item = document.createElement("article");
    item.className = `tx-item ${tx.type}`;

    const left = document.createElement("div");
    left.className = "tx-meta";
    left.innerHTML = `<strong>${tx.description}</strong><span>${new Date(
      tx.createdAt
    ).toLocaleString()}</span>`;

    const right = document.createElement("div");
    right.className = "tx-amount";
    right.textContent = `${tx.type === "expense" ? "-" : "+"}${formatCurrency(
      Number(tx.amount)
    )}`;

    item.appendChild(left);
    item.appendChild(right);
    txList.appendChild(item);
  }
}

function renderTracker() {
  authSection.classList.add("hidden");
  trackerSection.classList.remove("hidden");
  trackerIdLabel.textContent = state.tracker.trackerId;
  balanceLabel.textContent = formatCurrency(getBalance());
  renderTransactions();
}

async function handleAddTransaction(event) {
  event.preventDefault();
  const description = txDescription.value.trim();
  const amount = Number(txAmount.value);
  const type = txType.value;

  if (!description || !amount || amount <= 0) {
    return;
  }

  const tx = {
    description,
    amount,
    type,
    createdAt: new Date().toISOString(),
  };

  try {
    const result = await apiRequest(`/api/tracker/${state.tracker.trackerId}/transactions`, {
      method: "POST",
      body: JSON.stringify(tx),
    });
    state.tracker.transactions = Array.isArray(result.transactions) ? result.transactions : [];
    txForm.reset();
    txType.value = "income";
    balanceLabel.textContent = formatCurrency(getBalance());
    renderTransactions();
  } catch (error) {
    alert(`Failed to save transaction: ${error.message}`);
  }
}

function switchTracker() {
  state.recordId = null;
  state.tracker = null;
  trackerSection.classList.add("hidden");
  authSection.classList.remove("hidden");
  existingIdInput.value = "";
  setAuthStatus("", false);
}

createTrackerBtn.addEventListener("click", createTracker);
loadTrackerBtn.addEventListener("click", loadExistingTracker);
txForm.addEventListener("submit", handleAddTransaction);
logoutBtn.addEventListener("click", switchTracker);

async function checkServer() {
  try {
    const res = await apiRequest("/health", { method: "GET" });
    setServerStatus(res.ok ? "Server is running." : "Server responded unexpectedly.", !res.ok);
  } catch (error) {
    setServerStatus(
      "Server not reachable. Start `server.py` and refresh this page.",
      true
    );
  }
}

checkServer();
