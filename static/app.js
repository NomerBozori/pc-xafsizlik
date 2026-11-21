/* PC Xavfsizlik dashboard — tashqi kutubxonasiz */
const $ = (sel) => document.querySelector(sel);

const state = {
  armed: false,
  events: [],
  timer: null,
  busy: false,
};

/* ------------------------------------------------------------------ utils */
async function api(path, opts = {}) {
  const res = await fetch(path, {
    headers: { "Content-Type": "application/json" },
    ...opts,
  });
  const text = await res.text();
  let data = {};
  try { data = text ? JSON.parse(text) : {}; } catch { data = { raw: text }; }
  if (!res.ok) throw new Error(data.error || `HTTP ${res.status}`);
  return data;
}

function toast(msg, isError = false) {
  const el = $("#toast");
  el.textContent = msg;
  el.hidden = false;
  el.classList.toggle("err", isError);
  clearTimeout(toast._t);
  toast._t = setTimeout(() => { el.hidden = true; }, 4200);
}

function fmtTime(iso) {
  if (!iso) return "—";
  const d = new Date(iso);
  if (Number.isNaN(d.getTime())) return iso;
  return d.toLocaleString("uz-UZ", {
    day: "2-digit", month: "2-digit", year: "numeric",
    hour: "2-digit", minute: "2-digit", second: "2-digit",
  });
}

function esc(s) {
  return String(s ?? "").replace(/[&<>"']/g, (c) =>
    ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]));
}

function withBusy(btn, fn) {
  return async (...args) => {
    if (btn) btn.disabled = true;
    try { return await fn(...args); }
    finally { if (btn) btn.disabled = false; }
  };
}

/* ----------------------------------------------------------------- status */
function renderStatus(s) {
  state.armed = !!s.armed;
  const pill = $("#statePill");
  pill.classList.toggle("pill-on", s.armed);
  pill.classList.toggle("pill-off", !s.armed);
  $("#stateText").textContent = s.armed ? "Qo'riqlashda" : "O'chirilgan";

  $("#statSeen").textContent = s.stats?.seen ?? 0;
  $("#statEvents").textContent = s.stats?.events ?? 0;
  $("#statPhotos").textContent = s.counters?.photos ?? 0;

  const cam = s.camera || {};
  const backendName = { opencv: "OpenCV", fswebcam: "fswebcam", simulate: "demo" }[cam.backend] || cam.backend;
  $("#statCamera").textContent = `${backendName} · ${cam.resolution || "—"}`;

  $("#cfgThreshold").textContent = s.threshold;
  $("#cfgWindow").textContent = s.window_seconds;
  $("#snapDir").textContent = s.snapshot_dir || "—";
  $("#logSources").textContent = (s.stats?.sources?.join(", ") || "avtomatik");
  $("#lastError").textContent = s.last_error || "yo'q";

  $("#btnArm").disabled = s.armed;
  $("#btnDisarm").disabled = !s.armed;

  const list = $("#attemptList");
  const rows = s.recent_attempts || [];
  if (!rows.length) {
    list.innerHTML = '<li class="muted">Hozircha urinish yo\'q</li>';
  } else {
    list.innerHTML = rows.map((a) => `
      <li>
        <span><span class="who">${esc(a.user)}</span> · ${esc(a.source)}</span>
        <span class="when">${fmtTime(a.at)}</span>
      </li>`).join("");
  }
}

async function refreshStatus() {
  try {
    const s = await api("/api/status");
    renderStatus(s);
  } catch (e) {
    console.warn("status", e);
  }
}

/* ----------------------------------------------------------------- events */
function renderEvents(rows) {
  const wrap = $("#events");
  $("#eventCount").textContent = `${rows.length} voqea`;
  if (!rows.length) {
    wrap.innerHTML = '<p class="muted">Hozircha voqea yo\'q. «Demo» tugmasini bosib ko\'ring.</p>';
    return;
  }
  wrap.innerHTML = rows.map((ev) => {
    const photos = (ev.photos || []).map((p) => `
      <figure class="thumb" data-full="/api/events/${esc(ev.id)}/photos/${esc(p.file)}"
              data-caption="${esc(p.taken_at)} · ${esc(p.backend)}">
        <img loading="lazy" src="/api/events/${esc(ev.id)}/photos/${esc(p.file)}"
             alt="Voqea rasmi ${esc(p.taken_at)}" />
        <figcaption>${fmtTime(p.taken_at)}</figcaption>
      </figure>`).join("");

    const samples = (ev.samples || []).length
      ? `<ul class="samples">${ev.samples.map((s) => `<li>${esc(s)}</li>`).join("")}</ul>` : "";

    return `
      <article class="event">
        <div class="event-head">
          <div class="event-title">
            <span class="badge">${ev.attempts || 0} xato urinish</span>
            ${ev.error ? '<span class="badge ok">rasm yo\'q</span>' : ""}
            <span class="muted">${(ev.users || []).map(esc).join(", ") || "—"}</span>
          </div>
          <div class="event-when">${fmtTime(ev.detected_at)}</div>
        </div>
        <div class="event-body">
          <div class="event-facts">
            <span>Manba: <b>${(ev.sources || []).map(esc).join(", ") || "—"}</b></span>
            <span>Oraliq: <b>${esc(ev.window_seconds ?? "—")} s</b></span>
            <span>Rasmlar: <b>${(ev.photos || []).length}</b></span>
          </div>
          ${ev.error ? `<div class="err">Kamera xatosi: ${esc(ev.error)}</div>` : ""}
          ${photos ? `<div class="thumbs">${photos}</div>` : ""}
          ${samples}
        </div>
      </article>`;
  }).join("");

  wrap.querySelectorAll(".thumb").forEach((fig) => {
    fig.addEventListener("click", () => openLightbox(fig.dataset.full, fig.dataset.caption));
  });
}

async function refreshEvents() {
  try {
    const data = await api("/api/events?limit=100");
    state.events = data.events || [];
    renderEvents(state.events);
  } catch (e) {
    console.warn("events", e);
  }
}

/* --------------------------------------------------------------- lightbox */
function openLightbox(src, caption) {
  $("#lbImg").src = src;
  $("#lbCaption").textContent = caption || "";
  $("#lightbox").hidden = false;
}
function closeLightbox() {
  $("#lightbox").hidden = true;
  $("#lbImg").src = "";
}

/* ------------------------------------------------------------------ paint */
async function paintAll() {
  await refreshStatus();
  await refreshEvents();
}

/* ----------------------------------------------------------------- wiring */
function wire() {
  $("#btnArm").addEventListener("click", withBusy($("#btnArm"), async () => {
    try {
      const r = await api("/api/arm", { method: "POST" });
      toast(`Qo'riqlash yoqildi. Kuzatilmoqda: ${(r.watching || []).join(", ") || "journal"}`);
      await paintAll();
    } catch (e) { toast(`Xato: ${e.message}`, true); }
  }));

  $("#btnDisarm").addEventListener("click", withBusy($("#btnDisarm"), async () => {
    try {
      await api("/api/disarm", { method: "POST" });
      toast("Qo'riqlash to'xtatildi.");
      await paintAll();
    } catch (e) { toast(`Xato: ${e.message}`, true); }
  }));

  $("#btnTest").addEventListener("click", withBusy($("#btnTest"), async () => {
    try {
      const r = await api("/api/test", { method: "POST" });
      toast(`Sinov rasmi olindi (${(r.event?.photos || []).length} ta).`);
      await paintAll();
    } catch (e) { toast(`Kamera xatosi: ${e.message}`, true); }
  }));

  $("#btnSimOne").addEventListener("click", async () => {
    try {
      const r = await api("/api/simulate", {
        method: "POST", body: JSON.stringify({ count: 1 }),
      });
      const fired = (r.events || []).length;
      toast(fired ? "Chegara oshdi — rasmga olindi!" : "1 xato urinish qayd etildi.");
      await paintAll();
    } catch (e) { toast(`Xato: ${e.message}`, true); }
  });

  $("#btnSimulate").addEventListener("click", withBusy($("#btnSimulate"), async () => {
    try {
      const r = await api("/api/simulate", {
        method: "POST", body: JSON.stringify({ count: 4 }),
      });
      const fired = (r.events || []).length;
      toast(fired
        ? `${r.attempts} ta soxta urinish → ${fired} voqea, kamera ishga tushdi.`
        : `${r.attempts} ta urinish qayd etildi, chegara hali oshmadi.`);
      await paintAll();
    } catch (e) { toast(`Xato: ${e.message}`, true); }
  }));

  $("#btnCamTest").addEventListener("click", withBusy($("#btnCamTest"), async () => {
    try {
      const r = await api("/api/selftest", { method: "POST" });
      toast(r.ok
        ? `Kamera ishlaydi (${r.backend}, ${r.shots} kadr).`
        : `Kamera javob bermadi (${r.backend}): ${r.error || "sabab noma'lum"}`, !r.ok);
    } catch (e) { toast(`Xato: ${e.message}`, true); }
  }));

  $("#btnPurge").addEventListener("click", withBusy($("#btnPurge"), async () => {
    try {
      const r = await api("/api/purge", { method: "POST" });
      toast(`${r.removed} ta eski rasm o'chirildi.`);
      await paintAll();
    } catch (e) { toast(`Xato: ${e.message}`, true); }
  }));

  $("#btnClear").addEventListener("click", async () => {
    if (!confirm("Barcha rasmlar va voqealar o'chirilsinmi? Bu amalni qaytarib bo'lmaydi.")) return;
    try {
      const r = await api("/api/events", { method: "DELETE" });
      toast(`Tozalandi: ${r.removed_photos} ta rasm.`);
      await paintAll();
    } catch (e) { toast(`Xato: ${e.message}`, true); }
  });

  $("#lbClose").addEventListener("click", closeLightbox);
  $("#lightbox").addEventListener("click", (e) => {
    if (e.target.id === "lightbox") closeLightbox();
  });
  document.addEventListener("keydown", (e) => {
    if (e.key === "Escape") closeLightbox();
  });
}

/* ------------------------------------------------------------------- boot */
wire();
paintAll();
state.timer = setInterval(refreshStatus, 3000);
setInterval(refreshEvents, 7000);
