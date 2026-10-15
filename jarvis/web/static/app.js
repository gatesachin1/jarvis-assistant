"use strict";

/* J.A.R.V.I.S web dashboard: live link to the Python backend over a WebSocket. */

const $ = (id) => document.getElementById(id);

const state = {
    socket: null,
    retryMs: 1000,
    history: [],
    historyIndex: 0,
};

/* ------------------------------------------------------------- utilities */

function timeLabel(ts) {
    const date = ts ? new Date(ts * 1000) : new Date();
    return date.toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" });
}

function setDot(element, status) {
    element.classList.remove("online-dot", "offline-dot", "busy-dot", "demo-dot");
    element.classList.add(`${status}-dot`);
}

function el(tag, className, text) {
    const node = document.createElement(tag);
    if (className) node.className = className;
    if (text !== undefined) node.textContent = text; // textContent: never inject HTML
    return node;
}

/* ----------------------------------------------------------------- clock */

function tickClock() {
    const now = new Date();
    $("clock").textContent = now.toLocaleTimeString();
    $("date").textContent = now.toLocaleDateString(undefined, {
        weekday: "long", day: "numeric", month: "long", year: "numeric",
    });
}

/* ------------------------------------------------------------------ chat */

function addMessage(sender, text) {
    const isJarvis = sender === "jarvis";
    const wrapper = el("div", `message ${isJarvis ? "jarvis-message" : "user-message"}`);
    wrapper.append(el("div", "message-avatar", isJarvis ? "J" : "U"));

    const content = el("div", "message-content");
    content.append(el("strong", "", isJarvis ? "J.A.R.V.I.S" : "YOU"));
    content.append(el("p", "", text));
    wrapper.append(content);

    const box = $("chat-messages");
    box.append(wrapper);
    box.scrollTop = box.scrollHeight;
}

/* ---------------------------------------------------------- activity log */

function logActivity(icon, color, title, detail, ts) {
    const item = el("div", "activity-item");
    item.append(el("span", `activity-icon ${color}`, icon));

    const body = el("div");
    body.append(el("strong", "", title));
    if (detail) body.append(el("p", "", detail));
    item.append(body);
    item.append(el("time", "", timeLabel(ts)));

    const list = $("activity-list");
    list.prepend(item);
    while (list.children.length > 30) list.lastChild.remove();
}

/* ------------------------------------------------------------ core state */

const CORE_TEXT = {
    idle: ["SYSTEM STANDBY", "Say “Hey JARVIS”, press the mic, or type a command."],
    busy: ["PROCESSING", "Working on your request…"],
    listening: ["LISTENING", "Speak your command now."],
};

function setCoreState(stateName, text) {
    const stage = $("core-stage");
    stage.classList.toggle("thinking", stateName === "busy");
    stage.classList.toggle("listening", stateName === "listening");

    const [title, description] = CORE_TEXT[stateName] || CORE_TEXT.idle;
    $("core-title").textContent = title;
    $("core-description").textContent = stateName === "idle" && text && text !== "SYSTEM ONLINE" ? text : description;
    setDot($("core-dot"), stateName === "idle" ? "online" : "busy");
    $("core-badge").textContent = stateName === "idle" ? "LIVE" : stateName.toUpperCase();
}

/* ------------------------------------------------------------- websocket */

function setConnection(online) {
    setDot($("conn-dot"), online ? "online" : "offline");
    setDot($("system-dot"), online ? "online" : "offline");
    $("conn-title").textContent = online ? "Backend connected" : "Backend offline";
    $("conn-detail").textContent = online
        ? "Commands run on this PC and your phone."
        : "Start it with: python -m jarvis --web";
    $("system-text").textContent = online ? "SYSTEM ONLINE" : "OFFLINE";
}

function handleEvent(event) {
    if (event.type === "history") {
        $("chat-messages").replaceChildren();
        event.events.forEach((e) => addMessage(e.sender, e.text));
        if (!event.events.length) {
            addMessage("jarvis", "Welcome back, Commander. How can I help?");
        }
        return;
    }

    if (event.type === "message") {
        addMessage(event.sender, event.text);
        if (event.sender === "user") {
            logActivity("›", "cyan", `Command (${event.source})`, event.text, event.ts);
        } else {
            const firstLine = event.text.split("\n")[0];
            logActivity("✓", "green", "JARVIS replied", firstLine.slice(0, 140), event.ts);
            refreshReminders();
        }
        return;
    }

    if (event.type === "status") {
        setCoreState(event.state, event.text);
        if (event.state === "listening") {
            logActivity("🎙", "amber", "Listening", "Microphone open", event.ts);
        }
    }
}

function connect() {
    const scheme = location.protocol === "https:" ? "wss" : "ws";
    const socket = new WebSocket(`${scheme}://${location.host}/ws`);
    state.socket = socket;

    socket.addEventListener("open", () => {
        state.retryMs = 1000;
        setConnection(true);
        logActivity("✓", "green", "Connected", "Live link to the JARVIS backend.");
        refreshStatus();
        refreshReminders();
    });

    socket.addEventListener("message", (msg) => {
        try {
            handleEvent(JSON.parse(msg.data));
        } catch (error) {
            console.error("Bad event", error);
        }
    });

    socket.addEventListener("close", () => {
        setConnection(false);
        setCoreState("idle", "Backend offline. Reconnecting…");
        setTimeout(connect, state.retryMs);
        state.retryMs = Math.min(state.retryMs * 2, 15000);
    });
}

function sendCommand(text) {
    text = text.trim();
    if (!text) return;

    if (!state.socket || state.socket.readyState !== WebSocket.OPEN) {
        addMessage("jarvis", "I'm offline right now. Start the backend with: python -m jarvis --web");
        return;
    }

    state.socket.send(JSON.stringify({ type: "command", text }));
    state.history.push(text);
    state.historyIndex = state.history.length;
}

/* --------------------------------------------------------- status cards */

function setPercent(valueId, barId, value) {
    const known = typeof value === "number";
    $(valueId).textContent = known ? `${Math.round(value)}%` : "--%";
    $(barId).style.width = known ? `${Math.min(100, value)}%` : "0%";
}

async function refreshStatus() {
    try {
        const response = await fetch("/api/status");
        if (!response.ok) return;
        const info = await response.json();

        $("version").textContent = `J.A.R.V.I.S · v${info.version}`;

        const llmReady = info.llm && info.llm.online && info.llm.model_installed;
        $("ai-status").textContent = llmReady ? "Online" : info.llm && info.llm.online ? "No model" : "Offline";
        $("ai-detail").textContent = info.llm ? info.llm.message : "Unknown";
        $("ai-footer").textContent = info.llm ? info.llm.model : "Local model";
        setDot($("ai-dot"), llmReady ? "online" : "offline");

        setPercent("cpu-value", "cpu-bar", info.cpu);
        setPercent("ram-value", "ram-bar", info.ram);
        if (info.cpu === null) {
            $("cpu-detail").textContent = $("ram-detail").textContent = "Install psutil for live stats";
        }

        const phone = info.phone || {};
        $("android-status").textContent = phone.connected ? "Connected" : "Offline";
        $("android-detail").textContent = phone.message || "";
        $("android-footer").textContent = phone.device || "USB debugging";
        setDot($("android-dot"), phone.connected ? "online" : "offline");
    } catch {
        /* backend offline: the socket handler already shows that */
    }
}

/* ------------------------------------------------------------ reminders */

async function reminderAction(id, method, path) {
    await fetch(path, { method });
    refreshReminders();
}

async function refreshReminders() {
    try {
        const response = await fetch("/api/reminders");
        if (!response.ok) return;
        const reminders = await response.json();

        const list = $("reminder-list");
        list.replaceChildren();
        $("reminder-count").textContent = `${reminders.length} pending`;

        if (!reminders.length) {
            list.append(el("p", "empty-note", "No pending reminders."));
            return;
        }

        reminders.forEach((reminder, index) => {
            const item = el("div", "activity-item reminder-item");
            item.append(el("span", "activity-icon amber", String(index + 1)));

            const body = el("div");
            body.append(el("strong", "", reminder.task));
            body.append(el("p", "", reminder.when));
            item.append(body);

            const actions = el("div", "reminder-actions");
            const done = el("button", "text-button", "Done");
            done.addEventListener("click", () =>
                reminderAction(reminder.id, "POST", `/api/reminders/${reminder.id}/done`));
            const remove = el("button", "text-button danger", "Delete");
            remove.addEventListener("click", () =>
                reminderAction(reminder.id, "DELETE", `/api/reminders/${reminder.id}`));
            actions.append(done, remove);
            item.append(actions);

            list.append(item);
        });
    } catch {
        /* offline */
    }
}

/* ----------------------------------------------------------------- setup */

function startListening() {
    fetch("/api/listen", { method: "POST" }).catch(() => {});
}

function init() {
    tickClock();
    setInterval(tickClock, 1000);
    setInterval(refreshStatus, 5000);
    setInterval(refreshReminders, 30000);

    const input = $("command-input");

    $("command-form").addEventListener("submit", (event) => {
        event.preventDefault();
        sendCommand(input.value);
        input.value = "";
    });

    input.addEventListener("keydown", (event) => {
        if (!state.history.length || !["ArrowUp", "ArrowDown"].includes(event.key)) return;
        event.preventDefault();
        const step = event.key === "ArrowUp" ? -1 : 1;
        state.historyIndex = Math.max(0, Math.min(state.history.length, state.historyIndex + step));
        input.value = state.history[state.historyIndex] || "";
    });

    document.querySelectorAll("[data-command]").forEach((button) => {
        button.addEventListener("click", () => sendCommand(button.dataset.command));
    });

    document.querySelectorAll(".nav-item").forEach((button) => {
        button.addEventListener("click", () => {
            document.querySelectorAll(".nav-item").forEach((b) => b.classList.remove("active"));
            button.classList.add("active");
            $(button.dataset.target).scrollIntoView({ behavior: "smooth", block: "start" });
        });
    });

    $("voice-button").addEventListener("click", startListening);
    $("core-listen-button").addEventListener("click", startListening);
    $("clear-log").addEventListener("click", () => $("activity-list").replaceChildren());

    setConnection(false);
    connect();
}

document.addEventListener("DOMContentLoaded", init);
