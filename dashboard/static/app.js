// App JS per la Kanban Dashboard con WebSocket Real-time

const CONFIG = {
  API_BASE: "/api",
};

let socket = null;

function initWebSocket() {
  const protocol = window.location.protocol === "https:" ? "wss:" : "ws:";
  const wsUrl = `${protocol}//${window.location.host}/ws`;
  socket = new WebSocket(wsUrl);
  socket.onmessage = (e) => {
    if (JSON.parse(e.data).type === "update_ready") updateDashboard();
  };
  socket.onclose = () => setTimeout(initWebSocket, 5000);
}

const AGENT_COLORS = {
  orchestrator: "#6366f1",
  backend: "#8b5cf6",
  frontend: "#d946ef",
  database: "#10b981",
  devops: "#0ea5e9",
  qa: "#f59e0b",
  testing: "#64748b",
  researcher: "#ec4899",
  architect: "#f97316",
  scrum_master: "#f43f5e",
  planner: "#f97316",
  reviewer: "#84cc16",
};

const AGENT_ICONS = {
  orchestrator: "🎯",
  backend: "⚙️",
  frontend: "🎨",
  database: "💾",
  devops: "🚀",
  qa: "🔍",
  testing: "🧪",
  researcher: "🔭",
  architect: "📐",
  scrum_master: "👔",
  planner: "📅",
};

const PROJECT_PALETTE = [
  "#38bdf8",
  "#818cf8",
  "#d946ef",
  "#10b981",
  "#f59e0b",
  "#f43f5e",
  "#fbbf24",
  "#2dd4bf",
];

function getProjectColor(projectId) {
  if (!projectId || projectId === "default" || projectId === "undefined")
    return "#94a3b8";
  let hash = 0;
  for (let i = 0; i < projectId.length; i++) {
    hash = projectId.charCodeAt(i) + ((hash << 5) - hash);
  }
  const index = Math.abs(hash) % PROJECT_PALETTE.length;
  return PROJECT_PALETTE[index];
}

let currentProjectId = localStorage.getItem("selectedProjectId") || "";

// Theme System
const currentTheme = localStorage.getItem("selectedTheme") || "midnight";

function applyTheme(theme) {
  // Rimuove dinamicamente qualsiasi classe che inizia con "theme-"
  Array.from(document.body.classList).forEach((cls) => {
    if (cls.startsWith("theme-")) {
      document.body.classList.remove(cls);
    }
  });

  if (theme !== "midnight") {
    document.body.classList.add(`theme-${theme}`);
  }
  localStorage.setItem("selectedTheme", theme);
  const selector = document.getElementById("theme-selector");
  if (selector) selector.value = theme;
}

// Applica immediatamente il tema salvato o quello predefinito
applyTheme(currentTheme);

// Notification System
const notifications = JSON.parse(localStorage.getItem("noti_history") || "[]");
let notificationsEnabled = localStorage.getItem("noti_enabled") !== "false";
let previousProjectStates = {}; // id -> {count, completed}

class NotificationManager {
  static init() {
    this.updateBadge();
    this.renderList();

    // Toggle settiing
    const toggle = document.getElementById("noti-toggle");
    toggle.checked = notificationsEnabled;
    toggle.addEventListener("change", (e) => {
      notificationsEnabled = e.target.checked;
      localStorage.setItem("noti_enabled", notificationsEnabled);
    });

    // Bell click
    document.getElementById("noti-bell-btn").addEventListener("click", (e) => {
      e.stopPropagation();
      const dropdown = document.getElementById("noti-dropdown");
      const isVisible = dropdown.style.display !== "none";
      dropdown.style.display = isVisible ? "none" : "block";

      if (!isVisible) {
        this.markAllAsRead();
      }
    });

    // Test notification button
    const testBtn = document.getElementById("test-noti-btn");
    if (testBtn) {
      testBtn.addEventListener("click", (e) => {
        e.stopPropagation();
        const mockProjects = ["VerifyExit", "InventoryApp", "CRM_System"];
        const randomProject =
          mockProjects[Math.floor(Math.random() * mockProjects.length)];
        this.add(
          "Test Notifica",
          `Notifica di test per il progetto ${randomProject}!`,
          `started project=${randomProject}`,
        );
      });
    }

    // Clear notification button
    const clearBtn = document.getElementById("clear-noti-btn");
    if (clearBtn) {
      clearBtn.addEventListener("click", (e) => {
        e.stopPropagation();
        this.clearAll();
      });
    }

    // Auto-close dropdown
    window.addEventListener("click", () => {
      document.getElementById("noti-dropdown").style.display = "none";
    });
    document
      .getElementById("noti-dropdown")
      .addEventListener("click", (e) => e.stopPropagation());
  }

  static add(title, message, type = "info") {
    const noti = {
      id: Date.now(),
      title,
      message,
      type,
      time: new Date().toISOString(),
      unread: true,
      projectColor: type.includes("project=")
        ? getProjectColor(type.split("project=")[1])
        : null,
      projectName: type.includes("project=") ? type.split("project=")[1] : null,
    };

    // Clean up type if it was used for project passing
    if (noti.projectName) noti.type = type.split("project=")[0];

    notifications.unshift(noti);
    if (notifications.length > 50) notifications.pop();
    localStorage.setItem("noti_history", JSON.stringify(notifications));

    if (notificationsEnabled) {
      this.showToast(noti);
      this.shakeBell();
    }

    this.updateBadge();
    this.renderList();
  }

  static showToast(noti) {
    const container =
      document.getElementById("toast-container") || this.createToastContainer();
    const toast = document.createElement("div");
    toast.className = `toast ${noti.type}`;
    toast.style.background = "rgba(15, 23, 42, 0.9)";
    toast.style.backdropFilter = "blur(20px)";

    const icon = noti.type === "finished" ? "🎉" : "🚀";
    const accentColor =
      noti.projectColor ||
      (noti.type === "finished" ? "var(--completed)" : "var(--accent-primary)");

    toast.innerHTML = `
      <div class="toast-icon" style="background: ${accentColor}20; color: ${accentColor}">${icon}</div>
      <div class="toast-content">
        <div class="toast-header-row">
          <h4>${noti.title}</h4>
          ${noti.projectName ? `<span class="toast-project-tag" style="border-color: ${accentColor}; color: ${accentColor}">${noti.projectName}</span>` : ""}
        </div>
        <p>${noti.message}</p>
      </div>
    `;

    if (noti.projectColor) {
      toast.style.borderColor = noti.projectColor;
      toast.style.boxShadow = `0 10px 30px ${noti.projectColor}20`;
    }

    container.appendChild(toast);
    setTimeout(() => {
      toast.style.opacity = "0";
      toast.style.transform = "translateX(20px)";
      setTimeout(() => toast.remove(), 400);
    }, 5000);
  }

  static createToastContainer() {
    const div = document.createElement("div");
    div.id = "toast-container";
    div.className = "toast-container";
    document.body.appendChild(div);
    return div;
  }

  static updateBadge() {
    const unreadCount = notifications.filter((n) => n.unread).length;
    const badge = document.getElementById("noti-badge");
    if (unreadCount > 0) {
      badge.style.display = "flex";
      badge.innerText = unreadCount > 9 ? "9+" : unreadCount;
    } else {
      badge.style.display = "none";
    }
  }

  static renderList() {
    const list = document.getElementById("noti-list");
    if (notifications.length === 0) {
      list.innerHTML = '<div class="empty-noti">Nessuna nuova notifica</div>';
      return;
    }

    list.innerHTML = notifications
      .map(
        (n) => `
      <div class="noti-item ${n.unread ? "unread" : ""}" ${n.projectColor ? `style="border-left: 3px solid ${n.projectColor}"` : ""}>
        <div class="noti-title-row">
          <span class="noti-title">${n.title}</span>
          ${n.projectName ? `<span class="noti-project-badge" style="background: ${n.projectColor}15; color: ${n.projectColor}">${n.projectName}</span>` : ""}
        </div>
        <span class="noti-msg">${n.message}</span>
        <span class="noti-time">${new Date(n.time).toLocaleTimeString()}</span>
      </div>
    `,
      )
      .join("");
  }

  static markAllAsRead() {
    notifications.forEach((n) => (n.unread = false));
    localStorage.setItem("noti_history", JSON.stringify(notifications));
    this.updateBadge();
    this.renderList();
  }

  static clearAll() {
    notifications.length = 0;
    localStorage.removeItem("noti_history");
    this.updateBadge();
    this.renderList();
  }

  static shakeBell() {
    const btn = document.getElementById("noti-bell-btn");
    btn.classList.add("shake");
    setTimeout(() => btn.classList.remove("shake"), 600);
  }

  static trackProjects(projects, tasks) {
    // tasks here is expected to be ALL tasks from all projects to track backgrounds
    // but the API currently returns tasks for current project if query is present.
    // For robust tracking, we'd need a "all tasks" endpoint or check per project.
    // Simple version: track projects we see in the tasks call.

    const projectTasks = {};
    tasks.forEach((t) => {
      const pid = t.project_id || "default";
      if (!projectTasks[pid]) projectTasks[pid] = [];
      projectTasks[pid].push(t);
    });

    const isFirstRun = Object.keys(previousProjectStates).length === 0;

    Object.entries(projectTasks).forEach(([pid, tasks]) => {
      const total = tasks.length;
      const completed = tasks.filter((t) => t.status === "completed").length;
      const failed = tasks.filter((t) => t.status === "failed").length;
      const doneValue = completed + failed;

      const prevState = previousProjectStates[pid];

      // Detect Start (was 0, now > 0 or first seen with tasks)
      // Only notify if it's NOT the very first time we see any projects (refreshed page)
      if (!prevState && total > 0 && !isFirstRun) {
        this.add(
          "Progetto Avviato",
          `Il progetto ${pid} è in corso con ${total} task.`,
          `started project=${pid}`,
        );
      }

      // Detect Finish
      if (
        prevState &&
        prevState.done < prevState.total &&
        doneValue === total &&
        total > 0
      ) {
        this.add(
          "Progetto Completato",
          `Tutti i ${total} task del progetto ${pid} sono terminati.`,
          `finished project=${pid}`,
        );
      }

      previousProjectStates[pid] = { total, done: doneValue };
    });
  }
}

async function updateDashboard() {
  try {
    const query = currentProjectId ? `?project_id=${currentProjectId}` : "";

    const [
      projectsResponse,
      tasksResponse,
      logsResponse,
      statusResponse,
      agentsStatsResponse,
    ] = await Promise.all([
      fetch(`${CONFIG.API_BASE}/projects`),
      fetch(`${CONFIG.API_BASE}/tasks${query}`),
      fetch(`${CONFIG.API_BASE}/logs${query}`),
      fetch(`${CONFIG.API_BASE}/status${query}`),
      fetch(`${CONFIG.API_BASE}/agents${query}`),
    ]);

    const projects = await projectsResponse.json();
    const tasks = await tasksResponse.json();
    const logs = await logsResponse.json();
    const agents = await statusResponse.json();
    const agentsStats = await agentsStatsResponse.json();

    updateProjectSelector(projects);
    renderTasks(tasks);
    renderBacklog(tasks);
    renderLogs(logs);
    renderSidebarAgents(agents);
    updateProjectProgress(tasks);
    updateProjectTokenSummary(agentsStats);

    // Releases + Refinement (non bloccanti)
    Promise.all([
      fetchReleases(currentProjectId),
      fetchSprintCounter(currentProjectId),
      fetchRefinement(currentProjectId),
    ])
      .then(([releases, counter, refinement]) => {
        renderReleases(releases, counter);
        renderRefinement(refinement);
      })
      .catch(() => {});

    // BACKGROUND TRACKING: Fetch ALL tasks for notification monitoring
    fetch(`${CONFIG.API_BASE}/tasks`)
      .then((res) => res.json())
      .then((allTasks) => {
        NotificationManager.trackProjects(projects, allTasks);
      })
      .catch((err) => console.error("Notification track error:", err));

    // Reapply search filter after render (if any)
    if (searchQuery) {
      filterTasksBySearch();
    }

    // Restore search input value
    const searchInput = document.getElementById("task-search");
    if (searchInput) {
      searchInput.value = searchQuery;
    }

    document.getElementById("last-update").innerText =
      `Ultimo aggiornamento: ${new Date().toLocaleTimeString()}`;
    document.getElementById("connection-status").className =
      "status-badge online";
    document.getElementById("connection-status").innerText = "Sistema Online";
  } catch (error) {
    console.error("Errore durante l'aggiornamento:", error);
    document.getElementById("connection-status").className =
      "status-badge offline";
    document.getElementById("connection-status").innerText = "Disconnesso";
  }
}

function updateProjectSelector(projects) {
  const selector = document.getElementById("project-selector");

  // Mantieni "Tutti i Progetti"
  selector.innerHTML = '<option value="">Tutti i Progetti</option>';

  projects.forEach((project) => {
    const option = document.createElement("option");
    option.value = project;
    option.innerText = project;
    selector.appendChild(option);
  });

  selector.value = currentProjectId;
}

function renderTasks(tasks) {
  const columns = {
    pending: document.querySelector("#pending .task-list"),
    assigned: document.querySelector("#in_progress .task-list"),
    in_progress: document.querySelector("#in_progress .task-list"),
    under_review: document.querySelector("#under_review .task-list"),
    completed: document.querySelector("#completed .task-list"),
    failed: document.querySelector("#failed .task-list"),
  };

  // Pulisci le colonne
  Object.values(columns).forEach((col) => (col.innerHTML = ""));

  // Group tasks by status, then by agent
  const groupedByStatus = {};
  tasks.forEach((task) => {
    const status = task.status || "pending";
    if (!groupedByStatus[status]) {
      groupedByStatus[status] = {};
    }
    const agentType = task.agent_type || "unknown";
    if (!groupedByStatus[status][agentType]) {
      groupedByStatus[status][agentType] = [];
    }
    groupedByStatus[status][agentType].push(task);
  });

  // Render grouped tasks
  Object.entries(groupedByStatus).forEach(([status, agentGroups]) => {
    const column = columns[status] || columns["pending"];

    Object.entries(agentGroups).forEach(([agentType, agentTasks]) => {
      // Create agent group container
      const agentGroup = document.createElement("div");
      agentGroup.className = "agent-group";

      // Create agent group header
      const agentHeader = document.createElement("div");
      agentHeader.className = "agent-group-header";
      agentHeader.innerHTML = `
        <span class="agent-group-title">
          <span class="agent-tag" style="background: ${AGENT_COLORS[agentType.toLowerCase()] || "var(--pending)"}; color: #fff;">${agentType}</span>
          <span class="task-count">(${agentTasks.length})</span>
        </span>
        <span class="collapse-icon">▼</span>
      `;

      // Create task container
      const taskContainer = document.createElement("div");
      taskContainer.className = "agent-tasks-container";

      // Restore expanded state from localStorage
      const storageKey = `agent-group-${status}-${agentType}`;
      const isExpanded = localStorage.getItem(storageKey) !== "collapsed";

      if (!isExpanded) {
        taskContainer.style.display = "none";
        agentHeader.querySelector(".collapse-icon").innerText = "▶";
      }

      // Add click handler for collapse/expand
      agentHeader.addEventListener("click", () => {
        const isCurrentlyExpanded = taskContainer.style.display !== "none";
        taskContainer.style.display = isCurrentlyExpanded ? "none" : "block";
        agentHeader.querySelector(".collapse-icon").innerText =
          isCurrentlyExpanded ? "▶" : "▼";
        localStorage.setItem(
          storageKey,
          isCurrentlyExpanded ? "collapsed" : "expanded",
        );
      });

      // Add tasks to container
      agentTasks.forEach((task) => {
        const card = createTaskCard(task);
        taskContainer.appendChild(card);
      });

      agentGroup.appendChild(agentHeader);
      agentGroup.appendChild(taskContainer);
      column.appendChild(agentGroup);
    });
  });
}

function updateProjectProgress(tasks) {
  const container = document.getElementById("project-progress-container");
  if (!currentProjectId || tasks.length === 0) {
    container.style.display = "none";
    return;
  }

  // Exclude infrastructure tasks created at runtime (reviews, commits) — they inflate total
  // and are never "completed" in the traditional sense, causing the bar to freeze below 100%.
  const SYSTEM_TASK_TYPES = new Set([
    "review_task",
    "speaking_commit",
    "scrum_improvement",
    "backlog_item",
  ]);
  const primaryTasks = tasks.filter((t) => !SYSTEM_TASK_TYPES.has(t.type));

  container.style.display = "block";
  const completed = primaryTasks.filter((t) => t.status === "completed").length;
  const failed = primaryTasks.filter((t) => t.status === "failed").length;
  const total = primaryTasks.length;

  // Use completed-only for the visual bar (failed tasks shown separately).
  const percentage = total > 0 ? Math.floor((completed / total) * 100) : 0;

  const bar = document.getElementById("project-progress-bar");
  const label = document.getElementById("project-percentage");

  bar.style.width = `${percentage}%`;
  label.innerText = `${percentage}%`;

  // Color adjustment based on percentage
  if (percentage === 100) {
    bar.style.background = "var(--completed)";
  } else {
    bar.style.background =
      "linear-gradient(90deg, var(--accent-primary), var(--accent-secondary))";
  }
}

function updateProjectTokenSummary(agentsStats) {
  const container = document.getElementById("project-token-summary");
  if (!currentProjectId || !agentsStats || agentsStats.length === 0) {
    container.style.display = "none";
    return;
  }

  let totalPrompt = 0;
  let totalCompletion = 0;
  let totalTokens = 0;
  let totalCost = 0;
  let totalSaved = 0;

  agentsStats.forEach((agent) => {
    totalPrompt += agent.total_prompt_tokens || 0;
    totalCompletion += agent.total_completion_tokens || 0;
    totalTokens += agent.grand_total_tokens || 0;
    totalCost += agent.total_cost || 0;
    totalSaved += agent.total_saved_tokens || 0;
  });

  document.getElementById("proj-prompt-tokens").innerText =
    totalPrompt.toLocaleString();
  document.getElementById("proj-completion-tokens").innerText =
    totalCompletion.toLocaleString();
  document.getElementById("proj-total-tokens").innerText =
    totalTokens.toLocaleString();
  document.getElementById("proj-total-cost").innerText =
    `$${totalCost.toFixed(4)}`;

  const savingsPill = document.getElementById("toon-savings-pill");
  if (totalSaved > 0) {
    const standardTotal = totalTokens + totalSaved;
    const savingsPercent = ((totalSaved / standardTotal) * 100).toFixed(1);

    document.getElementById("proj-savings-value").innerText =
      `${savingsPercent}%`;
    document.getElementById("proj-standard-total").innerText =
      `(Standard: ${standardTotal.toLocaleString()})`;
    savingsPill.style.display = "flex";
  } else {
    savingsPill.style.display = "none";
  }

  container.style.display = "flex";
}

function createTaskCard(task) {
  const template = document.getElementById("task-card-template");
  const clone = template.content.cloneNode(true);

  const card = clone.querySelector(".task-card");
  const status = task.status || "pending";
  card.setAttribute("data-status", status);

  const agentType = task.agent_type.toLowerCase();

  const tag = clone.querySelector(".agent-tag");
  tag.innerText = task.agent_type;
  tag.style.background = AGENT_COLORS[agentType] || "var(--pending)";
  tag.style.color = "#fff";

  clone.querySelector(".task-id").innerText = `#${task.task_id.slice(-6)}`;
  clone.querySelector(".task-desc").innerText = task.description;

  const priorityEl = clone.querySelector(".priority");
  priorityEl.innerText = `Prio: ${task.priority}`;

  if (task.assigned_to) {
    const assignedEl = document.createElement("span");
    assignedEl.className = "assigned-to";
    assignedEl.innerText = ` 👤 ${task.assigned_to.split("_")[0]}`;
    assignedEl.style.fontSize = "0.75rem";
    assignedEl.style.opacity = "0.8";
    priorityEl.appendChild(assignedEl);
  }

  // Show rejection notice if last_error exists
  if (task.metadata && task.metadata.last_error) {
    const notice = document.createElement("div");
    notice.className = "rejection-notice";
    notice.innerText = "⚠️ REJECTED (feedback inside)";
    card.querySelector(".task-desc").after(notice);
  }

  // Add click handler for modal
  card.style.cursor = "pointer";
  card.onclick = () => openTaskModal(task);

  return card;
}

function openTaskModal(task) {
  const taskModal = document.getElementById("task-modal");
  const modalTitle = document.getElementById("task-modal-title");
  const modalTags = document.getElementById("task-modal-tags");
  const modalDesc = document.getElementById("task-modal-desc");
  const modalRejection = document.getElementById("task-modal-rejection");
  const modalMeta = document.getElementById("task-modal-meta");
  const modalDeps = document.getElementById("task-modal-deps");

  // Format Title
  modalTitle.innerHTML = `<span style="color: var(--text-muted); font-weight: 300;">Task:</span> ${task.type || task.description.slice(0, 40)}`;

  // Tags row
  const agentColor =
    AGENT_COLORS[task.agent_type.toLowerCase()] || "var(--pending)";
  modalTags.innerHTML = `
    <span class="agent-tag" style="background: ${agentColor}20; color: ${agentColor}; border: 1px solid ${agentColor}40; padding: 2px 8px; border-radius: 6px; font-size: 11px;">${task.agent_type}</span>
    <span style="font-size: 11px; color: var(--text-muted); font-family: monospace;">#${task.task_id.slice(-8)}</span>
    <span style="font-size: 11px; font-weight: 600; color: var(--accent-primary);">${task.status.toUpperCase()}</span>
    <span style="font-size: 11px; color: var(--text-muted);">Priorità: ${task.priority}</span>
  `;

  // Rejection feedback
  if (task.metadata && task.metadata.last_error) {
    modalRejection.style.display = "block";
    modalRejection.innerHTML = `
      <h3>🚨 Feedback di Revisione</h3>
      <div class="rejection-content">${task.metadata.last_error}</div>
    `;
  } else {
    modalRejection.style.display = "none";
    modalRejection.innerHTML = "";
  }

  // Description
  modalDesc.innerHTML = `
    <div style="margin-bottom: 20px;">
        <h3 style="margin-bottom: 8px; font-size: 0.9rem; color: var(--accent-primary); text-transform: uppercase; letter-spacing: 0.05em;">Descrizione</h3>
        <div style="white-space: pre-wrap; background: rgba(255,255,255,0.03); padding: 12px; border-radius: 12px; border: 1px solid rgba(255,255,255,0.05); font-size: 0.95rem;">${task.description}</div>
    </div>
  `;

  // Metadata JSON (if relevant)
  const filteredMetadata = { ...(task.metadata || {}) };
  delete filteredMetadata.last_error;
  if (Object.keys(filteredMetadata).length > 0) {
    modalMeta.innerHTML = `
        <h3 style="margin-bottom: 8px; font-size: 0.9rem; color: var(--accent-primary); text-transform: uppercase;">Dati Tecnici</h3>
        <pre style="background: rgba(0,0,0,0.25); padding: 12px; border-radius: 10px; border: 1px solid rgba(255,255,255,0.03); overflow-x: auto; font-size: 11px; font-family: 'JetBrains Mono', monospace;">${JSON.stringify(filteredMetadata, null, 2)}</pre>
    `;
  } else {
    modalMeta.innerHTML = "";
  }

  // Dependencies
  if (task.depends_on && task.depends_on.length > 0) {
    modalDeps.innerHTML = `
        <h3 style="margin-bottom: 8px; font-size: 0.9rem; color: var(--accent-primary); text-transform: uppercase;">Dipendenze</h3>
        <div style="display: flex; gap: 8px; flex-wrap: wrap;">
          ${task.depends_on.map((d) => `<span style="background: rgba(255,255,255,0.05); padding: 4px 10px; border-radius: 6px; font-size: 11px; border: 1px solid rgba(255,255,255,0.1);">#${d.slice(-6)}</span>`).join("")}
        </div>
    `;
  } else {
    modalDeps.innerHTML = "";
  }

  taskModal.style.display = "block";
}

function renderLogs(logs) {
  const logList = document.getElementById("log-list");
  logList.innerHTML = "";

  logs.forEach((log) => {
    const item = document.createElement("div");
    item.className = "log-item";

    const time = new Date(log.timestamp).toLocaleTimeString([], {
      hour: "2-digit",
      minute: "2-digit",
    });

    item.onclick = (() => {
      const logData = log; // Capture current log data
      return () => openLogModal(logData);
    })();

    item.innerHTML = `
            <div>
                <span class="time">${time}</span> | 
                <span class="agent">${log.agent}</span>
            </div>
            <p>${log.description}</p>
        `;
    logList.appendChild(item);
  });
}

// Modal Logic
const modal = document.getElementById("log-modal");
const closeButton = document.querySelector(".close-button");

function openLogModal(log) {
  const modalTitle = document.getElementById("modal-title");
  const modalMeta = document.getElementById("modal-meta");
  const modalBody = document.getElementById("modal-body");

  modalTitle.innerHTML = `<span style="color: var(--text-muted); font-weight: 300;">Log:</span> ${log.agent}`;

  const time = new Date(log.timestamp).toLocaleString();
  modalMeta.innerHTML = `
    <div class="meta-item">
      <span class="meta-label">Timestamp</span>
      <span class="meta-value">${time}</span>
    </div>
    <div class="meta-item">
      <span class="meta-label">Agente</span>
      <span class="meta-value">${log.agent}</span>
    </div>
  `;

  // Format description if it contains JSON or code
  let content = log.description;
  let isJson = false;
  try {
    if (content.trim().startsWith("{") || content.trim().startsWith("[")) {
      const parsed = JSON.parse(content);
      content = JSON.stringify(parsed, null, 2);
      isJson = true;
    }
  } catch (e) {}

  if (isJson) {
    modalBody.innerHTML = `
      <h3 style="margin-bottom: 8px; font-size: 0.9rem; color: var(--accent-primary); text-transform: uppercase;">Dati Log</h3>
      <pre style="background: rgba(0,0,0,0.25); padding: 12px; border-radius: 10px; border: 1px solid rgba(255,255,255,0.03); overflow-x: auto; font-size: 11px; font-family: 'JetBrains Mono', monospace;">${content}</pre>
    `;
  } else {
    modalBody.innerHTML = `
      <h3 style="margin-bottom: 8px; font-size: 0.9rem; color: var(--accent-primary); text-transform: uppercase;">Descrizione</h3>
      <div style="white-space: pre-wrap; background: rgba(255,255,255,0.03); padding: 12px; border-radius: 12px; border: 1px solid rgba(255,255,255,0.05); font-size: 0.95rem;">${content}</div>
    `;
  }

  modal.style.display = "block";
}

// Initial modal logic cleanup - removing individual handlers in favor of unified ones below
// (kept some functions for compatibility with explicit onclick calls in HTML)
function closeTaskModal() {
  const modal = document.getElementById("task-modal");
  if (modal) modal.style.display = "none";
}

// Close any modal when clicking outside of the content
window.addEventListener("click", function (event) {
  if (event.target.classList.contains("modal")) {
    event.target.style.display = "none";
    // Cleanup for docs modal if needed
    if (event.target.id === "docs-modal") {
      currentDocsAgent = null;
    }
  }
});

// Close modal on Escape key
window.addEventListener("keydown", function (event) {
  if (event.key === "Escape") {
    document.querySelectorAll(".modal").forEach((modal) => {
      if (modal.style.display === "block") {
        modal.style.display = "none";
        if (modal.id === "docs-modal") {
          currentDocsAgent = null;
        }
      }
    });
  }
});

// Unified close function for all modals with the .close-button class
document.addEventListener("click", function (event) {
  if (event.target.classList.contains("close-button")) {
    const modal = event.target.closest(".modal");
    if (modal) {
      modal.style.display = "none";
      if (modal.id === "docs-modal") {
        currentDocsAgent = null;
      }
    }
  }
});

// Render sidebar mini-list (used by updateDashboard on every poll)
function renderSidebarAgents(agents) {
  const agentsList = document.getElementById("agents-list");
  agentsList.innerHTML = "";

  Object.entries(agents).forEach(([name, info]) => {
    const agentType = name.split("_")[0].toLowerCase();
    const color = AGENT_COLORS[agentType] || "var(--accent-primary)";

    const item = document.createElement("div");
    item.className = "agent-item";
    item.innerHTML = `
            <div class="agent-avatar" style="background: ${color}; box-shadow: 0 0 8px ${color}"></div>
            <div class="agent-info">
                <span class="name">${name}</span>
                <span class="status">${info.last_action}: ${info.description.slice(0, 30)}...</span>
            </div>
        `;
    agentsList.appendChild(item);
  });
}

// Render full agent grid in the Agents tab (tokens, cost, prompts, docs)
function renderAgentsGrid(agentsData) {
  const container = document.getElementById("agents-grid");

  if (!agentsData || agentsData.length === 0) {
    container.innerHTML = `
      <div class="empty-releases">
        <div class="empty-icon">🤖</div>
        <p>Nessun dato di tracking per gli agenti. Avvia un progetto per iniziare.</p>
      </div>`;
    return;
  }

  container.innerHTML = agentsData
    .map((agent) => {
      const typeKey = agent.agent_id.split("_")[0];
      const color = AGENT_COLORS[typeKey] || "var(--accent-primary)";
      const costStr = agent.total_cost
        ? `$${agent.total_cost.toFixed(4)}`
        : "$0.0000";

      const safePrompt = agent.system_prompt
        ? agent.system_prompt
            .replace(/&/g, "&amp;")
            .replace(/</g, "&lt;")
            .replace(/>/g, "&gt;")
            .replace(/"/g, "&quot;")
        : "";

      return `
      <div class="agent-detail-card" style="border-top: 3px solid ${color}">
        <div class="agent-card-header">
           <span class="agent-tag" style="background:${color}20; color:${color}; font-size:1.1rem; padding: 4px 10px">${agent.agent_id}</span>
           <div class="agent-cost-badge">${costStr}</div>
        </div>
        <div class="agent-stats-row">
           <div class="agent-stat">
             <span class="stat-label">Docs</span>
             <span class="stat-value highlight" style="color:var(--completed)">${agent.doc_count || 0}</span>
           </div>
           <div class="agent-stat">
             <span class="stat-label">Prompt Tokens</span>
             <span class="stat-value">${(agent.total_prompt_tokens || 0).toLocaleString()}</span>
           </div>
           <div class="agent-stat">
             <span class="stat-label">Completion Tokens</span>
             <span class="stat-value">${(agent.total_completion_tokens || 0).toLocaleString()}</span>
           </div>
           <div class="agent-stat">
             <span class="stat-label">Total Tokens</span>
             <span class="stat-value highlight">${(agent.grand_total_tokens || 0).toLocaleString()}</span>
           </div>
        </div>
        <div style="display: flex; gap: 10px; margin-top: 5px;">
           <button class="save-prompt-btn" style="flex: 1; justify-content: center;" onclick="openDocsModal('${typeKey}')">
             📄 Documenti (${agent.doc_count || 0})
           </button>
        </div>
        <div class="agent-prompt-section">
           <label class="prompt-label">SYSTEM PROMPT</label>
           <textarea class="agent-prompt-textarea" id="prompt_${agent.agent_id}">${safePrompt}</textarea>
           <button class="save-prompt-btn" onclick="saveAgentPrompt('${agent.agent_id}', '${typeKey}')">
             <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" style="width:14px; height:14px; margin-right:4px;">
               <path d="M19 21H5a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h11l5 5v11a2 2 0 0 1-2 2z"></path>
               <polyline points="17 21 17 13 7 13 7 21"></polyline>
               <polyline points="7 3 7 8 15 8"></polyline>
             </svg>
             Salva Prompt
           </button>
        </div>
      </div>
    `;
    })
    .join("");
}

// Search functionality
let searchQuery = localStorage.getItem("taskSearchQuery") || "";

function filterTasksBySearch() {
  const allTaskCards = document.querySelectorAll(".task-card");
  const allAgentGroups = document.querySelectorAll(".agent-group");

  allTaskCards.forEach((card) => {
    const taskDesc = card.querySelector(".task-desc").innerText.toLowerCase();
    const taskId = card.querySelector(".task-id").innerText.toLowerCase();
    const matches =
      searchQuery === "" ||
      taskDesc.includes(searchQuery.toLowerCase()) ||
      taskId.includes(searchQuery.toLowerCase());
    card.style.display = matches ? "block" : "none";
  });

  // Hide agent groups with no visible tasks
  allAgentGroups.forEach((group) => {
    const visibleTasks = group.querySelectorAll(
      '.task-card:not([style*="display: none"])',
    );
    group.style.display = visibleTasks.length > 0 ? "block" : "none";
  });
}

// Event Listeners
document.getElementById("project-selector").addEventListener("change", (e) => {
  currentProjectId = e.target.value;
  localStorage.setItem("selectedProjectId", currentProjectId);
  updateDashboard();
});

document.getElementById("theme-selector").addEventListener("change", (e) => {
  applyTheme(e.target.value);
});

document.getElementById("task-search").addEventListener("input", (e) => {
  searchQuery = e.target.value;
  localStorage.setItem("taskSearchQuery", searchQuery);
  filterTasksBySearch();
});

document.getElementById("expand-all-btn").addEventListener("click", () => {
  document.querySelectorAll(".agent-tasks-container").forEach((container) => {
    container.style.display = "block";
  });
  document.querySelectorAll(".collapse-icon").forEach((icon) => {
    icon.innerText = "▼";
  });
  // Clear all localStorage collapse states
  Object.keys(localStorage).forEach((key) => {
    if (key.startsWith("agent-group-")) {
      localStorage.removeItem(key);
    }
  });
});

document.getElementById("collapse-all-btn").addEventListener("click", () => {
  document.querySelectorAll(".agent-tasks-container").forEach((container) => {
    container.style.display = "none";
  });
  document.querySelectorAll(".collapse-icon").forEach((icon) => {
    icon.innerText = "▶";
  });
  // Set all agent groups to collapsed with correct keys
  // We need to extract the status and agentType from the header to build the correct key
  document.querySelectorAll(".agent-group").forEach((group) => {
    const header = group.querySelector(".agent-group-header");
    const agentTag = header.querySelector(".agent-tag");
    const agentType = agentTag ? agentTag.innerText : "unknown";

    // Find the parent column to determine status
    const column = group.closest(".kanban-column");
    const status = column ? column.id : "pending";

    const storageKey = `agent-group-${status}-${agentType}`;
    localStorage.setItem(storageKey, "collapsed");
  });
});

// Tab Switching Logic
document.querySelectorAll(".tab-btn").forEach((btn) => {
  btn.addEventListener("click", () => {
    const target = btn.getAttribute("data-target");

    // UI active state
    document
      .querySelectorAll(".tab-btn")
      .forEach((b) => b.classList.remove("active"));
    btn.classList.add("active");

    // Section visibility
    document
      .querySelectorAll(
        ".kanban-section, .backlog-section, .releases-section, .retro-section, .refinement-section, .agents-section",
      )
      .forEach((s) => {
        if (s) s.classList.add("hidden");
      });
    const targetEl = document.querySelector(`.${target}`);
    if (targetEl) targetEl.classList.remove("hidden");

    // Fetch data if needed
    if (target === "retro-section") fetchRetrospectives();
    if (target === "agents-section") fetchAgents();

    // Save preference
    localStorage.setItem("activeTab", target);
  });
});

async function fetchRetrospectives() {
  try {
    const query = currentProjectId ? `?project_id=${currentProjectId}` : "";
    const response = await fetch(`${CONFIG.API_BASE}/retrospectives${query}`);
    const data = await response.json();
    renderRetrospectives(data);
  } catch (error) {
    console.error("Errore recupero retrospective:", error);
  }
}

function renderRetrospectives(data) {
  const container = document.getElementById("retro-timeline");
  if (data.length === 0) {
    container.innerHTML =
      '<div class="empty-noti">Nessuna retrospective disponibile per questo progetto.</div>';
    return;
  }

  container.innerHTML = data
    .map((item) => {
      const sprint = item.sprint;
      const feedbacks = item.feedbacks || [];
      const stats = item.stats || { completed_tasks: 0, failed_tasks: 0, total_tasks: 0 };
      const date = new Date(sprint.completed_at).toLocaleString();

      // Crea un oggetto sicuro per essere passato alla funzione onclick
      const safeItem = JSON.stringify(item).replace(/'/g, "&apos;");

      return `
      <div class="retro-report clickable-retro" onclick='openRetroModal(${safeItem})'>
        <div class="retro-header">
          <h3>Sprint #${sprint.sprint_number || sprint.sprint_id} - ${sprint.project_id}</h3>
          <span class="retro-date">${date}</span>
        </div>
        <div style="display: flex; justify-content: space-between; align-items: center;">
          <div class="retro-feedbacks-preview">
            ${feedbacks.slice(0, 5).map(f => `<span class="agent-dot" title="${f.agent_type}" style="background: ${AGENT_COLORS[f.agent_type.toLowerCase()] || "var(--text-main)"}"></span>`).join("")}
            ${feedbacks.length > 5 ? `<span style="font-size: 10px; color: var(--text-muted)">+${feedbacks.length - 5}</span>` : ""}
          </div>
          <div style="font-size: 11px; display: flex; gap: 8px;">
            <span style="color: var(--completed)">✅ ${stats.completed_tasks}</span>
            <span style="color: var(--failed)">❌ ${stats.failed_tasks}</span>
          </div>
        </div>
      </div>
    `;
    })
    .join("");
}

function openRetroModal(item) {
  const modal = document.getElementById("retro-modal");
  const modalTitle = document.getElementById("retro-modal-title");
  const modalMeta = document.getElementById("retro-modal-meta");
  const modalBody = document.getElementById("retro-modal-body");

  if (!modal) return;

  const sprint = item.sprint;
  const feedbacks = item.feedbacks || [];
  const stats = item.stats || { completed_tasks: 0, failed_tasks: 0, total_tasks: 0 };
  const date = new Date(sprint.completed_at).toLocaleString();

  modalTitle.textContent = `Retrospective Sprint #${sprint.sprint_id}`;
  modalMeta.innerHTML = `
    <div class="meta-item">
      <span class="meta-label">Progetto</span>
      <span class="meta-value">${sprint.project_id}</span>
    </div>
    <div class="meta-item">
      <span class="meta-label">Data Completamento</span>
      <span class="meta-value">${date}</span>
    </div>
  `;

  modalBody.innerHTML = `
    <!-- Sprint Summary Section -->
    <div class="sprint-summary-section">
      <div class="stat-box total">
        <span class="label">Total Tasks</span>
        <span class="value">${stats.total_tasks}</span>
      </div>
      <div class="stat-box success">
        <span class="label">Completed</span>
        <span class="value">${stats.completed_tasks}</span>
      </div>
      <div class="stat-box failure">
        <span class="label">Failed</span>
        <span class="value">${stats.failed_tasks}</span>
      </div>
    </div>

    <h3 style="margin-bottom: 15px; font-size: 1rem; color: var(--text-muted); text-transform: uppercase; letter-spacing: 1px;">Agent Feedbacks</h3>
    
    <div class="retro-feedbacks-list">
      ${feedbacks.map(f => {
        const type = f.agent_type.toLowerCase();
        const color = AGENT_COLORS[type] || "var(--accent-primary)";
        const icon = AGENT_ICONS[type] || "🤖";
        return `
        <div class="agent-feedback ${f.sentiment || "neutral"}" style="border-left: 4px solid ${color}">
          <div class="feedback-header">
            <div class="agent-icon-name">
              <div class="agent-avatar-mini" style="background: ${color}20; color: ${color}; border: 1px solid ${color}40">
                ${icon}
              </div>
              <span class="agent-name" style="color: ${color}">${f.agent_type.toUpperCase()}</span>
            </div>
            <span class="sentiment-badge">${f.sentiment?.toUpperCase() || "NEUTRAL"}</span>
          </div>
          <p class="feedback-text">${f.feedback}</p>
        </div>
      `}).join("")}
    </div>
  `;

  modal.style.display = "block";
}

// Refresh button for retrospectives
document
  .getElementById("refresh-retro-btn")
  .addEventListener("click", fetchRetrospectives);

// Restore active tab
const savedTab = localStorage.getItem("activeTab");
if (savedTab) {
  const btn = document.querySelector(`.tab-btn[data-target="${savedTab}"]`);
  if (btn) btn.click();
}

function renderBacklog(tasks) {
  const container = document.getElementById("backlog-list");
  const backlogTasks = tasks.filter(
    (t) => (t.status || "pending") === "pending",
  );

  if (backlogTasks.length === 0) {
    container.innerHTML =
      '<div class="empty-noti">Nessun task nel backlog.</div>';

    // Update Badge
    const badge = document.getElementById("backlog-badge");
    if (badge) {
      badge.style.display = "none";
    }
    return;
  }

  // Update Badge
  const badge = document.getElementById("backlog-badge");
  if (badge) {
    badge.textContent = backlogTasks.length;
    badge.style.display = "inline-flex";
  }

  container.innerHTML = "";
  backlogTasks.forEach((task) => {
    const color =
      AGENT_COLORS[(task.agent_type || "").toLowerCase()] || "var(--pending)";

    const div = document.createElement("div");
    div.className = "backlog-item";
    div.style.borderLeft = `4px solid ${color}`;
    div.onclick = () => openTaskModal(task);

    div.innerHTML = `
      <div class="info">
        <span class="title">${task.description}</span>
        <span class="meta">#${(task.task_id || "").slice(-6)} | ${(task.agent_type || "unknown").toUpperCase()} | Priorità: ${task.priority || "Normal"}</span>
      </div>
      <div class="actions">
        <span class="status-badge" style="background: rgba(148, 163, 184, 0.1); color: var(--text-muted)">PENDING</span>
      </div>
    `;
    container.appendChild(div);
  });
}

// Backlog filtering
document.getElementById("backlog-search").addEventListener("input", (e) => {
  const q = e.target.value.toLowerCase();
  document.querySelectorAll(".backlog-item").forEach((item) => {
    const text = item.innerText.toLowerCase();
    item.style.display = text.includes(q) ? "flex" : "none";
  });
});

// ========================================================
// RELEASES
// ========================================================

async function fetchReleases(projectId) {
  try {
    const url = projectId
      ? `${CONFIG.API_BASE}/releases?project_id=${projectId}`
      : `${CONFIG.API_BASE}/releases`;
    const res = await fetch(url);
    return await res.json();
  } catch (e) {
    return [];
  }
}

async function fetchSprintCounter(projectId) {
  try {
    const url = projectId
      ? `${CONFIG.API_BASE}/sprint-counter?project_id=${projectId}`
      : `${CONFIG.API_BASE}/sprint-counter`;
    const res = await fetch(url);
    return await res.json();
  } catch (e) {
    return null;
  }
}

function renderReleases(releases, counter) {
  const container = document.getElementById("releases-list");
  const badge = document.getElementById("releases-badge");

  // Update badge
  if (releases.length > 0) {
    badge.textContent = releases.length;
    badge.style.display = "inline-flex";
  } else {
    badge.style.display = "none";
  }

  // Update release cycle progress bar
  if (counter) {
    const pct = counter.release_progress_pct || 0;
    const remaining = counter.sprints_to_next_release || 8;
    const total = counter.total_sprints_completed || 0;
    document.getElementById("release-cycle-bar").style.width = `${pct}%`;
    document.getElementById("release-cycle-pct").textContent = `${pct}%`;
    document.getElementById("release-cycle-sprints").textContent =
      `Sprint completati: ${total} | Prossima release in: ${remaining} sprint`;
  }

  if (releases.length === 0) {
    container.innerHTML = `
      <div class="empty-releases">
        <div class="empty-icon">🚀</div>
        <p>Nessuna Release ancora. La prima release verrà creata dopo ${8} sprint completati.</p>
      </div>`;
    return;
  }

  container.innerHTML = releases
    .map((r) => {
      const date = r.created_at
        ? new Date(r.created_at).toLocaleDateString("it-IT")
        : "—";
      // Clica sulla release per aprire il modal dei log o simili, non richiesto ora ma miglioriamo layout
      const summary = r.summary
        ? r.summary.substring(0, 300) + (r.summary.length > 300 ? "…" : "")
        : "Nessuna nota disponibile.";
      return `
        <div class="release-card" onclick='openReleaseModal(${JSON.stringify(r).replace(/'/g, "&apos;")})' style="cursor: pointer;">
          <div class="release-header">
            <div class="release-version">${r.version || "?.?"}</div>
            <div class="release-meta">
              <span class="release-sprint-range">Sprint ${r.sprint_start} → ${r.sprint_end}</span>
              <span class="release-date">${date}</span>
              <span class="release-status release-status-${r.status || "completed"}">${(r.status || "completed").toUpperCase()}</span>
            </div>
          </div>
          <div class="release-summary">${summary}</div>
        </div>`;
    })
    .join("");
}

function openReleaseModal(r) {
  const modal = document.getElementById("release-detail-modal");
  document.getElementById("release-detail-title").textContent =
    `Release ${r.version || "?.?"}`;

  const date = r.created_at
    ? new Date(r.created_at).toLocaleString("it-IT")
    : "—";
  document.getElementById("release-detail-meta").innerHTML = `
    <span class="agent-tag" style="background: var(--bg-hover); color: var(--text-main);">Sprint ${r.sprint_start} → ${r.sprint_end}</span>
    <span class="task-date">${date}</span>
    <span class="status-badge status-${r.status || "completed"}">${(r.status || "completed").toUpperCase()}</span>
  `;

  document.getElementById("release-detail-body").textContent =
    r.summary || "Nessuna nota di rilascio disponibile.";
  modal.style.display = "block";
}

// ========================================================
// BACKLOG REFINEMENT
// ========================================================

async function fetchRefinement(projectId) {
  try {
    const url = projectId
      ? `${CONFIG.API_BASE}/refinement?project_id=${projectId}`
      : `${CONFIG.API_BASE}/refinement`;
    const res = await fetch(url);
    return await res.json();
  } catch (e) {
    return [];
  }
}

function renderRefinement(proposals) {
  const container = document.getElementById("refinement-list");

  if (proposals.length === 0) {
    container.innerHTML = `
      <div class="empty-releases">
        <div class="empty-icon">🗂️</div>
        <p>Nessuna proposta ancora. Il Backlog Refinement avviene automaticamente dopo ogni sprint completato.</p>
      </div>`;
    return;
  }

  // Group by sprint
  const bySprint = {};
  proposals.forEach((p) => {
    const sNum = p.sprint_number || p.sprint_id;
    const k = `Sprint #${sNum}`;
    if (!bySprint[k]) bySprint[k] = [];
    bySprint[k].push(p);
  });

  container.innerHTML = Object.entries(bySprint)
    .map(([sprintLabel, items]) => {
      const itemsHtml = items
        .map((p) => {
          const agentColor =
            AGENT_COLORS[p.proposed_by?.toLowerCase()] || "var(--pending)";
          const accepted =
            p.accepted === 1
              ? "✅ Accettata"
              : p.accepted === 2
                ? "❌ Rifiutata"
                : "⏳ In valutazione";
          const acceptedClass =
            p.accepted === 1
              ? "accepted"
              : p.accepted === 2
                ? "rejected"
                : "pending";
          return `
            <div class="refinement-item refinement-${acceptedClass}">
              <div class="refinement-left">
                <span class="agent-tag" style="background: ${agentColor}20; color: ${agentColor}; border: 1px solid ${agentColor}40">
                  ${p.proposed_by || "unknown"}
                </span>
                <span class="refinement-priority">P${p.priority || 1}</span>
              </div>
              <div class="refinement-desc">${p.description}</div>
              <div class="refinement-status-badge ${acceptedClass}">${accepted}</div>
            </div>`;
        })
        .join("");
      return `
        <div class="refinement-sprint-group">
          <div class="refinement-sprint-label">${sprintLabel}</div>
          ${itemsHtml}
        </div>`;
    })
    .join("");
}

// ========================================================
// AGENT MANAGEMENT (TOKEN TRACKING & PROMPTS)
// ========================================================

async function fetchAgents() {
  try {
    const url = currentProjectId
      ? `${CONFIG.API_BASE}/agents?project_id=${currentProjectId}`
      : `${CONFIG.API_BASE}/agents`;
    const res = await fetch(url);
    const data = await res.json();
    renderAgentsGrid(data);
  } catch (e) {
    console.error("Errore recupero agenti:", e);
  }
}

// (renderAgents is now split into renderSidebarAgents and renderAgentsGrid above)
// Stub for backward compat
function renderAgents(agentsData) {
  renderAgentsGrid(agentsData);
}

async function saveAgentPrompt(agentId, agentType) {
  const textarea = document.getElementById(`prompt_${agentId}`);
  const newPrompt = textarea.value;

  try {
    const res = await fetch(`${CONFIG.API_BASE}/agents/${agentType}/prompt`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ system_prompt: newPrompt }),
    });

    if (res.ok) {
      NotificationManager.add(
        "Prompt Aggiornato",
        `Il system prompt di ${agentType} è stato salvato con successo.`,
        "success",
      );
    } else {
      NotificationManager.add(
        "Errore",
        `Impossibile aggiornare il prompt di ${agentType}.`,
        "error",
      );
    }
  } catch (e) {
    console.error("Errore salvataggio prompt:", e);
    NotificationManager.add(
      "Errore di Rete",
      "Connessione al server persa.",
      "error",
    );
  }
}

// ========================================================
// AGENT DOCUMENTS MODAL & LOGIC
// ========================================================

let currentDocsAgent = null;

function openDocsModal(agentType) {
  currentDocsAgent = agentType;
  document.getElementById("docs-modal-agent").textContent =
    agentType.toUpperCase();
  document.getElementById("docs-modal").style.display = "block";
  loadAgentDocs();
}

function closeDocsModal() {
  document.getElementById("docs-modal").style.display = "none";
  currentDocsAgent = null;
}

function toggleDocInput() {
  const type = document.getElementById("doc-type-select").value;
  document.getElementById("doc-input-url").style.display =
    type === "url" ? "block" : "none";
  document.getElementById("doc-input-text").style.display =
    type === "text" ? "block" : "none";
  document.getElementById("doc-input-pdf").style.display =
    type === "pdf" ? "block" : "none";
}

async function loadAgentDocs() {
  const listEl = document.getElementById("docs-list");
  listEl.innerHTML = "<p>Caricamento in corso...</p>";

  try {
    const res = await fetch(
      `${CONFIG.API_BASE}/agents/${currentDocsAgent}/docs`,
    );
    const docs = await res.json();

    if (docs.length === 0) {
      listEl.innerHTML =
        "<p style='color: var(--text-muted); font-size: 0.9rem;'>Nessun documento collegato a questo agente.</p>";
      return;
    }

    listEl.innerHTML = docs
      .map(
        (d) => `
      <div style="display: flex; justify-content: space-between; align-items: center; padding: 10px; background: var(--bg-main); border: 1px solid var(--border-color); border-radius: 6px; margin-bottom: 8px;">
        <div>
          <span style="font-size: 0.8rem; background: var(--accent-primary); color: white; padding: 2px 6px; border-radius: 4px; margin-right: 8px; text-transform: uppercase;">${d.doc_type}</span>
          <span style="font-size: 0.95rem;">${d.source}</span>
          <div style="font-size: 0.75rem; color: var(--text-muted); margin-top: 4px;">Inserito il: ${new Date(d.created_at).toLocaleString()}</div>
        </div>
        <button onclick="deleteAgentDoc('${d.id}')" style="background: transparent; border: none; color: var(--rejected); cursor: pointer; padding: 5px;">
           <svg viewBox="0 0 24 24" width="18" height="18" stroke="currentColor" stroke-width="2" fill="none" stroke-linecap="round" stroke-linejoin="round"><polyline points="3 6 5 6 21 6"></polyline><path d="M19 6v14a2 2 0 0 1-2 2H7a2 2 0 0 1-2-2V6m3 0V4a2 2 0 0 1 2-2h4a2 2 0 0 1 2 2v2"></path></svg>
        </button>
      </div>
    `,
      )
      .join("");
  } catch (e) {
    listEl.innerHTML =
      "<p style='color: var(--rejected);'>Errore nel caricamento documenti.</p>";
  }
}

async function submitNewDoc() {
  const type = document.getElementById("doc-type-select").value;
  const btn = document.querySelector("#docs-modal .save-prompt-btn");
  const originalLabel = btn ? btn.textContent : "Carica Documento";

  const setLoading = (loading, label = "Carica Documento") => {
    if (btn) {
      btn.disabled = loading;
      btn.textContent = loading ? label : "Carica Documento";
    }
  };

  const handleError = async (res) => {
    let detail = "Operazione fallita.";
    try {
      const body = await res.json();
      detail = body.detail || detail;
    } catch (_) {}
    NotificationManager.add("Errore Documento", `${detail}`, "error");
  };

  try {
    if (type === "pdf") {
      const fileInput = document.getElementById("doc-pdf-file");
      if (!fileInput.files.length) return alert("Seleziona un file PDF o DOCX prima.");

      setLoading(true, "Caricamento...");
      const formData = new FormData();
      formData.append("file", fileInput.files[0]);

      const res = await fetch(
        `${CONFIG.API_BASE}/agents/${currentDocsAgent}/docs/upload`,
        { method: "POST", body: formData },
      );
      if (res.ok) {
        NotificationManager.add(
          "Documento Caricato",
          "File caricato ed estratto con successo.",
          "success",
        );
        fileInput.value = "";
      } else {
        await handleError(res);
      }
    } else {
      let source = "",
        content = "";
      if (type === "url") {
        source = document.getElementById("doc-url-val").value.trim();
        if (!source) return alert("Inserisci un URL valido.");
        content = "";
        setLoading(true, "⏳ Scrapando URL...");
      } else if (type === "text") {
        source =
          document.getElementById("doc-title-val").value.trim() || "Testo Manuale";
        content = document.getElementById("doc-text-val").value;
        if (!content) return alert("Inserisci del testo.");
        setLoading(true, "Salvataggio...");
      }

      const res = await fetch(
        `${CONFIG.API_BASE}/agents/${currentDocsAgent}/docs`,
        {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ doc_type: type, source, content }),
        },
      );

      if (res.ok) {
        NotificationManager.add(
          "Documento Aggiunto",
          type === "url"
            ? "Pagina web scrapata e salvata con successo."
            : "Documento salvato con successo.",
          "success",
        );
        if (type === "url") document.getElementById("doc-url-val").value = "";
        if (type === "text") {
          document.getElementById("doc-title-val").value = "";
          document.getElementById("doc-text-val").value = "";
        }
      } else {
        await handleError(res);
      }
    }

    loadAgentDocs();
    updateDashboard();
  } catch (e) {
    console.error(e);
    NotificationManager.add(
      "Errore di Rete",
      "Connessione al server persa.",
      "error",
    );
  } finally {
    setLoading(false);
  }
}

async function deleteAgentDoc(id) {
  if (
    !confirm(
      "Sei sicuro di voler rimuovere questo documento dal contesto dell'agente?",
    )
  )
    return;

  try {
    const res = await fetch(`${CONFIG.API_BASE}/docs/${id}`, {
      method: "DELETE",
    });
    if (res.ok) {
      NotificationManager.add(
        "Documento Rimosso",
        "Il documento è stato rimosso con successo.",
        "success",
      );
      loadAgentDocs();
      updateDashboard();
    }
  } catch (e) {
    NotificationManager.add(
      "Errore",
      "Impossibile eliminare il documento.",
      "error",
    );
  }
}

// Avvio
initWebSocket();
NotificationManager.init();
updateDashboard();
setInterval(updateDashboard, 10000); // Fallback se WS fallisce
