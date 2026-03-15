// ---- WASD motor control ----
const pressed = new Set();
const keyEl = { w: "key-w", a: "key-a", s: "key-s", d: "key-d" };

function sendKey(key) {
  fetch("/command", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ key }),
  });
}

document.addEventListener("keydown", (e) => {
  const key = e.key.toLowerCase();
  if ("wasd".includes(key) && !pressed.has(key)) {
    pressed.add(key);
    document.getElementById(keyEl[key])?.classList.add("active");
    sendKey(key);
  }
});

document.addEventListener("keyup", (e) => {
  const key = e.key.toLowerCase();
  if (pressed.has(key)) {
    pressed.delete(key);
    document.getElementById(keyEl[key])?.classList.remove("active");
    if (pressed.size === 0) sendKey("stop");
  }
});

// ---- Sensor polling ----
async function pollSensors() {
  try {
    const res = await fetch("/sensors");
    const data = await res.json();

    if (data.error) return;

    document.getElementById("tds").textContent = Math.round(data.tds);

    const badge = document.getElementById("quality-badge");
    badge.textContent = data.quality;
    badge.className = data.quality;

    setStatus(true);
  } catch {
    setStatus(false);
  }
}

// ---- Connection status ----
function setStatus(online) {
  const el = document.getElementById("connection-status");
  const text = document.getElementById("status-text");
  el.className = online ? "online" : "offline";
  text.textContent = online ? "online" : "offline";
}

pollSensors();
setInterval(pollSensors, 2000);
