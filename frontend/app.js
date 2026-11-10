/* AegisVault frontend. Kontrak API: docs/FRONTEND_API_CONTRACT.md */
"use strict";

const POLL_MS = 1000;
const MAX_FILE_BYTES = 20 * 1024 * 1024;
const USERNAME_RE = /^[A-Za-z0-9][A-Za-z0-9_.\-]{0,63}$/;
const TABS = [
  ["memo", "Memo internal", "memo"],
  ["vault", "Brankas berkas", "brankas"],
  ["courier", "Kurir dan verifikasi", "kurir"],
  ["stego", "Studio steganografi", "gambar"],
  ["audit", "Blockchain dan audit", "rantai"],
];

const ICONS = {
  memo: '<path d="M6 5a2 2 0 0 1 2-2h7l4 4v12a2 2 0 0 1-2 2H8a2 2 0 0 1-2-2z"/><path d="M15 3v4h4"/><path d="M9.5 12h6M9.5 16h4"/>',
  brankas: '<rect x="3" y="4" width="18" height="16" rx="3"/><circle cx="12" cy="12" r="3.5"/><path d="M12 8.500V7M12 17v-1.500M8.500 12H7M17 12h-1.500M7 20v1.500M17 20v1.500"/>',
  kurir: '<rect x="3" y="6" width="18" height="13" rx="2.500"/><path d="M3.500 8.500 12 14l8.500-5.500"/>',
  gambar: '<rect x="3" y="4" width="18" height="16" rx="3"/><circle cx="8.500" cy="9.500" r="1.500"/><path d="m4 17 5-5 4 4 2.500-2.500L20 18"/>',
  rantai: '<path d="M10 14a4 4 0 0 0 5.700 0l3-3a4 4 0 0 0-5.700-5.700l-1 1"/><path d="M14 10a4 4 0 0 0-5.700 0l-3 3a4 4 0 0 0 5.700 5.700l1-1"/>',
  usb: '<path d="M7 9h10v9a3 3 0 0 1-3 3h-4a3 3 0 0 1-3-3z"/><path d="M9 9V3h6v6M11 5.500V6M13 5.500V6"/>',
  wajah: '<path d="M4 8V6a2 2 0 0 1 2-2h2M16 4h2a2 2 0 0 1 2 2v2M20 16v2a2 2 0 0 1-2 2h-2M8 20H6a2 2 0 0 1-2-2v-2"/><path d="M9 10v1M15 10v1M9.500 15a3.500 3.500 0 0 0 5 0"/>',
  sidik: '<path d="M12 11v3c0 2-.5 4-1.500 6"/><path d="M8.500 19.500c.8-1.800 1-3.500 1-5.500v-2a2.500 2.500 0 0 1 5 0v2c0 1.500-.1 3-.4 4.500"/><path d="M6 17c.4-1.200.5-2.200.5-3.500V12a5.500 5.500 0 0 1 9-4.200"/><path d="M17.300 11c.3 1.500.4 3 .2 5"/>',
  unggah: '<path d="M12 16V5M7.500 9.500 12 5l4.500 4.500M4 16v2a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2v-2"/>',
  unduh: '<path d="M12 5v11M7.500 11.500 12 16l4.500-4.500M4 16v2a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2v-2"/>',
  mata: '<path d="M2.500 12S6 5.500 12 5.500 21.500 12 21.500 12 18 18.500 12 18.500 2.500 12 2.500 12z"/><circle cx="12" cy="12" r="3"/>',
  kunci: '<rect x="5" y="11" width="14" height="10" rx="3"/><path d="M8 11V8a4 4 0 0 1 8 0v3"/>',
  centang: '<path d="m5 12.500 4.500 4.500L19 7.500"/>',
  peringatan: '<path d="M10.300 4.600 2.900 17.500a2 2 0 0 0 1.700 3h14.800a2 2 0 0 0 1.700-3L13.700 4.600a2 2 0 0 0-3.400 0z"/><path d="M12 10v4M12 17.500v.01"/>',
  tutup: '<path d="m6 6 12 12M18 6 6 18"/>',
  keluar: '<path d="M10 4H6a2 2 0 0 0-2 2v12a2 2 0 0 0 2 2h4M15 8l4 4-4 4M19 12h-9"/>',
  tambah: '<path d="M12 5v14M5 12h14"/>',
  segel: '<circle cx="12" cy="9.500" r="6"/><path d="M8.500 14.500 7 22l5-3 5 3-1.500-7.500"/><path d="m9.500 9.500 2 2 3-3.500"/>',
  proses: '<path d="M12 3a9 9 0 1 0 9 9"/>',
  hapus: '<path d="M4 7h16M9 7V4h6v3M6 7l1 13h10l1-13"/>',
  pilih: '<path d="m8 9 4-4 4 4M8 15l4 4 4-4"/>',
};

const icon = (name, cls = "") =>
  `<svg class="${cls}" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.750" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true">${ICONS[name]}</svg>`;

const LOGO = `<svg width="28" height="28" viewBox="0 0 64 64" fill="none" aria-hidden="true"><path d="M32 3 56 11.500V31C56 45 46.500 55.500 32 61 17.500 55.500 8 45 8 31V11.500Z" fill="#1A1D24"/><path d="M32 16 47 48H39.500L32 31.500 24.500 48H17Z" fill="#F9AE1F"/><circle cx="32" cy="44.500" r="3.500" fill="#F9AE1F"/></svg>`;

const esc = (v) => String(v ?? "").replace(/[&<>"']/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]));
const short = (h) => (h && h.length > 24 ? `${h.slice(0, 12)}...${h.slice(-8)}` : h || "");
const fmtBytes = (n) => (n >= 1048576 ? `${(n / 1048576).toFixed(1).replace(".", ",")} MB` : n >= 1024 ? `${Math.round(n / 1024)} KB` : `${n} byte`);
const fmtInt = (n) => new Intl.NumberFormat("id-ID").format(n);

/* ---------- State ---------- */

const blankLogin = () => ({ username: "", pin: "", error: "", usernameError: "" });
const blankReg = () => ({ username: "", full_name: "", pin: "", photo: null, cam: "idle", errors: {}, busy: false, formError: "" });
const blankReplace = () => ({ username: "", pin: "", photo: null, cam: "idle", errors: {}, busy: false, formError: "" });
const blankMemo = () => ({ items: null, loading: false, error: "", selId: null, detail: null, detailLoading: false, detailError: "", compose: false, saving: false, form: { title: "", category: "", content: "" }, errors: {} });
const blankVault = () => ({ items: null, loading: false, error: "", uploading: null, uploadError: "", drag: false, downloading: null });
const blankCourier = () => ({ file: null, pass: "", state: "idle", fileError: "", passError: "", result: null, drag: false });
const blankStego = () => ({ mode: "hide", cover: null, coverUrl: "", coverW: 0, coverH: 0, coverFormat: "", cap: null, capToken: 0, previewOk: true, coverError: "", msg: "", pass: "", busy: false, embedError: "", done: false, result: null, stego: null, stegoError: "", xPass: "", xBusy: false, xResult: null, xError: "", dragA: false, dragB: false });

const S = {
  view: "boot",
  status: null,
  failures: 0,
  session: null,
  locked: false,
  tab: "memo",
  accountOpen: false,
  dialog: null,
  enroll: { busy: false, error: "" },
  login: blankLogin(),
  face: { state: "ready", error: "", busy: false },
  reg: blankReg(),
  replace: blankReplace(),
  restore: { busy: false, error: "" },
  memo: blankMemo(),
  vault: blankVault(),
  courier: blankCourier(),
  stego: blankStego(),
  audit: { data: null, loading: false, checking: false, error: "" },
};

const root = () => document.getElementById("app");

/* ---------- API ---------- */

class ApiError extends Error {
  constructor(message, code, status) {
    super(message);
    this.code = code;
    this.status = status;
  }
}

async function request(path, options = {}) {
  let res;
  try {
    res = await fetch(path, options);
  } catch {
    throw new ApiError("Layanan lokal AegisVault tidak merespons. Muat ulang, atau buka ulang aplikasi kalau masalah berlanjut.", "NETWORK", 0);
  }
  if (res.ok) return res;
  let detail = {};
  try {
    const body = await res.json();
    detail = typeof body.detail === "string" ? { message: body.detail } : body.detail || body;
  } catch { /* badan respons bukan JSON */ }
  throw new ApiError(detail.message || "Permintaan gagal diproses. Coba lagi.", detail.code || "ERROR", res.status);
}

const getJson = async (path) => (await request(path)).json();
const postJson = async (path, body, method = "POST") =>
  (await request(path, { method, headers: { "Content-Type": "application/json" }, body: JSON.stringify(body ?? {}) })).json();
const postForm = (path, fields) => {
  const form = new FormData();
  for (const [k, v] of Object.entries(fields)) if (v !== null && v !== undefined && v !== "") form.append(k, v);
  return request(path, { method: "POST", body: form });
};

function saveBlob(blob, filename) {
  const url = URL.createObjectURL(blob);
  const a = document.createElement("a");
  a.href = url;
  a.download = filename;
  document.body.appendChild(a);
  a.click();
  a.remove();
  setTimeout(() => URL.revokeObjectURL(url), 2000);
}

function filenameFrom(res, fallback) {
  const header = res.headers.get("Content-Disposition") || "";
  const utf8 = /filename\*=UTF-8''([^;]+)/i.exec(header);
  if (utf8) return decodeURIComponent(utf8[1]);
  const m = /filename="?([^";]+)"?/.exec(header);
  return m ? m[1] : fallback;
}

/* ---------- Toast ---------- */

function toast(message, tone = "ok") {
  const box = document.getElementById("toasts");
  const el = document.createElement("div");
  const cls = tone === "ok" ? "bg-ok-bg text-ok-text" : "bg-bad-bg text-bad-text";
  el.className = `rise pointer-events-auto flex items-center gap-3 rounded-2xl p-4 shadow-raised ${cls}`;
  el.innerHTML = `${icon(tone === "ok" ? "centang" : "peringatan", "h-5 w-5 flex-none")}<span class="flex-1 text-body font-semibold">${esc(message)}</span><button type="button" class="flex h-8 w-8 flex-none items-center justify-center rounded-lg hover:bg-white/60" aria-label="Tutup notifikasi">${icon("tutup", "h-5 w-5")}</button>`;
  el.querySelector("button").onclick = () => el.remove();
  box.appendChild(el);
  setTimeout(() => el.remove(), 6000);
}

/* ---------- Komponen tampilan ---------- */

const button = (style, label, opts = {}) =>
  `<button type="${opts.submit ? "submit" : "button"}" class="btn btn-${style} ${opts.cls || ""}" ${opts.action ? `data-action="${opts.action}"` : ""} ${opts.data || ""} ${opts.disabled || opts.loading ? "disabled" : ""}>${opts.loading ? icon("proses", "spin") : opts.icon ? icon(opts.icon) : ""}${esc(label)}</button>`;

const badge = (tone, label, ic) => `<span class="badge badge-${tone}">${icon(ic || { ok: "centang", bad: "peringatan", warn: "proses", neutral: "kunci" }[tone])}${esc(label)}</span>`;

function field(o) {
  const describe = `${o.id}-note`;
  const note = o.error
    ? `<p id="${describe}" class="field-error" role="alert">${esc(o.error)}</p>`
    : o.help ? `<p id="${describe}" class="field-help">${esc(o.help)}</p>` : "";
  const input = `<input id="${o.id}" class="field-input ${o.error ? "is-error" : ""} ${o.secret ? "pr-12" : ""}" type="${o.secret ? "password" : "text"}" value="${esc(o.value)}" data-bind="${o.bind}" placeholder="${esc(o.placeholder || "")}" autocomplete="${o.autocomplete || "off"}" spellcheck="false" ${o.error ? 'aria-invalid="true"' : ""} ${note ? `aria-describedby="${describe}"` : ""} ${o.disabled ? "disabled" : ""}>`;
  const eye = o.secret
    ? `<button type="button" class="absolute right-1 top-0 flex h-11 w-11 items-center justify-center rounded-lg text-ink2 hover:text-ink" data-action="toggle-secret" data-target="${o.id}" aria-label="Tampilkan ${esc(o.label)}">${icon("mata", "h-5 w-5")}</button>`
    : "";
  return `<div><label class="field-label" for="${o.id}">${esc(o.label)}</label><div class="relative">${input}${eye}</div>${note}</div>`;
}

const logoBlock = () => `<div class="flex items-center gap-2.5">${LOGO}<span class="text-h3 text-ink">AegisVault</span></div>`;

const statePanel = ({ ic, tone = "neutral", title, body, action = "" }) => {
  const tile = { neutral: "bg-muted text-ink2", warn: "bg-amber-50 text-amber-800", bad: "bg-bad-bg text-bad-text" }[tone];
  return `<div class="mx-auto flex max-w-md flex-col items-center gap-4 p-8 text-center"><div class="flex h-16 w-16 items-center justify-center rounded-[20px] ${tile}">${icon(ic, `h-8 w-8 ${ic === "proses" ? "spin" : ""}`)}</div><div><h2 class="text-h2">${esc(title)}</h2><p class="mt-1 text-body text-ink2">${esc(body)}</p></div>${action}</div>`;
};

const sealCard = ({ status, index, time, nonce, hash, note }) => {
  const c = { sealed: ["border-ok-line", "ok", "Tersegel"], mining: ["border-amber-500", "warn", "Menambang"], bad: ["border-bad-line", "bad", "Tidak valid"] }[status];
  const row = (k, v) => `<div class="flex gap-3"><dt class="w-[84px] flex-none text-caption text-ink2">${esc(k)}</dt><dd class="mono text-ink">${esc(v)}</dd></div>`;
  return `<section class="seal ${c[0]} w-full max-w-[380px]" aria-label="Segel kriptografi"><div class="seal-inner ${c[0]}"><div class="mb-3 flex items-center justify-between gap-2"><span class="flex items-center gap-2 text-label">${icon("segel", "h-[22px] w-[22px] text-amber-800")}Segel kriptografi</span>${badge(c[1], c[2])}</div><dl class="space-y-2">${row("Nomor blok", index)}${row("Waktu", time)}${row("Nonce", nonce)}${row("Hash blok", hash)}</dl><p class="mt-3 text-caption text-ink2">${esc(note)}</p></div></section>`;
};

/* ---------- Layar masuk ---------- */

function sensorNote() {
  const b = S.status && S.status.biometric;
  const text = b && b.fingerprint_available
    ? "Sensor sidik jari terdeteksi. Login tetap memindai wajah."
    : "Sensor sidik jari tidak tersedia. Login memakai Face Recognition.";
  return `<div class="flex items-start gap-2.5 text-caption text-ink2">${icon("sidik", "h-5 w-5 flex-none")}<span>${text}</span></div>`;
}

function stepItem(state, n, label) {
  const m = {
    done: ["bg-ok-bg text-ok-text", icon("centang", "h-4 w-4"), "text-ink", "Selesai"],
    active: ["bg-amber-400 text-ink", n, "font-semibold text-ink", "Langkah aktif"],
    wait: ["bg-surface text-ink2", n, "text-ink2", "Menunggu"],
    fail: ["bg-bad-bg text-bad-text", icon("peringatan", "h-4 w-4"), "font-semibold text-bad-text", "Gagal"],
  }[state];
  return `<li class="flex items-center gap-3"><span class="flex h-7 w-7 items-center justify-center rounded-lg text-label ${m[0]}">${m[1]}</span><span class="text-body ${m[2]}">${esc(label)}<span class="sr-only"> (${m[3]})</span></span></li>`;
}

function authShell(steps, content, opts = {}) {
  const labels = opts.labels || ["USB dongle", "PIN", "Verifikasi wajah"];
  return `<div class="relative flex h-full">
    <aside class="glass-side hidden w-[376px] flex-none flex-col gap-10 p-8 lg:flex">
      ${logoBlock()}
      <div><p class="text-h1">${esc(opts.title || "Brankas dokumen internal instansi")}</p><p class="mt-2 text-body text-ink2">${esc(opts.sub || "Tiga pemeriksaan membuka akses Anda ke dokumen rahasia.")}</p></div>
      <ol class="space-y-4">${labels.map((l, i) => stepItem(steps[i], i + 1, l)).join("")}</ol>
      <div class="mt-auto">${sensorNote()}</div>
    </aside>
    <main class="flex min-w-0 flex-1 items-center justify-center overflow-auto bg-canvas p-6" id="main" tabindex="-1">
      <div class="${S.animate ? "rise" : ""} w-full ${opts.wide ? "max-w-[800px]" : "max-w-[540px]"} rounded-3xl bg-surface p-8 shadow-card sm:p-10">
        <div class="mb-6 lg:hidden">${logoBlock()}</div>
        ${content}
      </div>
    </main>
  </div>`;
}

const iconTile = (ic, cls) => `<div class="flex h-16 w-16 items-center justify-center rounded-[20px] ${cls}">${icon(ic, "h-8 w-8")}</div>`;

function viewBoot() {
  return `<div class="flex h-full items-center justify-center"><main id="main" class="card w-full max-w-md">${statePanel({ ic: "proses", tone: "warn", title: "Membuka AegisVault", body: "Aplikasi memeriksa USB dongle dan layanan lokal." })}</main></div>`;
}

function viewOffline() {
  return `<div class="flex h-full items-center justify-center p-6"><main id="main" class="card w-full max-w-md">${statePanel({ ic: "peringatan", tone: "bad", title: "Layanan lokal tidak merespons", body: "AegisVault tidak bisa menghubungi layanan di komputer ini. Coba lagi, atau buka ulang aplikasi kalau masalah berlanjut.", action: button("secondary", "Coba lagi", { action: "retry-status" }) })}</main></div>`;
}

function viewDongle() {
  const d = (S.status && S.status.dongle) || {};
  const wrong = d.connected && !d.valid;
  const e = S.enroll;
  const err = e.error ? `<p class="field-error" role="alert">${esc(e.error)}</p>` : "";
  let next;
  if (d.can_enroll) {
    next = `<div class="space-y-3 rounded-2xl bg-canvas p-5"><h2 class="text-body font-semibold">Pertama kali memakai AegisVault?</h2><p class="text-body text-ink2">Tancapkan flashdisk, lalu daftarkan sebagai dongle. Setelah itu, komputer ini hanya menerima dongle tersebut.</p>${button("secondary", "Daftarkan USB ini sebagai dongle", { icon: "usb", action: "enroll", loading: e.busy })}${err}</div>`;
  } else if (d.can_replace) {
    next = `<div class="space-y-3 rounded-2xl bg-canvas p-5"><h2 class="text-body font-semibold">Dongle hilang atau rusak?</h2><p class="text-body text-ink2">Ganti dengan flashdisk baru memakai akun staf. Dongle lama langsung tidak berlaku.</p>${button("secondary", "Ganti dongle", { icon: "usb", action: "go-replace" })}</div>`;
  } else {
    next = `<div class="space-y-2 rounded-2xl bg-canvas p-5"><h2 class="text-body font-semibold">Pakai dongle yang sudah didaftarkan</h2><p class="text-body text-ink2">Komputer ini sudah punya dongle, tapi belum ada akun staf. Dongle baru hanya bisa diganti setelah ada akun staf yang bisa diverifikasi.</p></div>`;
  }
  const head = wrong
    ? `${iconTile("usb", "bg-bad-bg text-bad-text")}<div><h1 class="text-display">USB ini belum terdaftar</h1><p class="mt-2 text-reading text-ink2">${esc(d.reason || "Tancapkan dongle yang terdaftar di komputer ini.")}</p></div>`
    : `${iconTile("usb", "bg-muted text-amber-800")}<div><h1 class="text-display">Tancapkan USB dongle</h1><p class="mt-2 text-reading text-ink2">AegisVault tetap terkunci sampai dongle terdaftar terdeteksi.</p></div>${badge("bad", "Dongle belum terdeteksi")}`;
  return authShell([wrong ? "fail" : "active", "wait", "wait"], `<div class="space-y-6">${head}${next}</div>`);
}

function viewReplace() {
  const r = S.replace;
  const photoErr = r.errors.photo ? `<p class="field-error" role="alert">${esc(r.errors.photo)}</p>` : "";
  const camera = r.cam === "nocam"
    ? `<div class="flex aspect-[4/3] items-center justify-center rounded-[20px] bg-muted p-4 text-center text-body text-ink2">Kamera tidak terdeteksi. Sambungkan webcam, lalu coba lagi.</div>${button("secondary", "Periksa kamera lagi", { action: "replace-camera", cls: "w-full" })}${testUpload("replace-upload")}`
    : `${cameraBox(r.photo ? "pass" : "ready", r.photo)}${r.photo ? button("secondary", "Ambil ulang foto", { action: "replace-retake", cls: "w-full" }) : button("secondary", "Ambil foto wajah", { icon: "wajah", action: "replace-capture", cls: "w-full" })}`;
  return authShell(["active", "wait", "wait"], `
    <form class="space-y-6" data-submit="replace" novalidate>
      <div><h1 class="text-h1 sm:text-display">Ganti dongle</h1><p class="mt-2 text-reading text-ink2">Tancapkan flashdisk baru, lalu buktikan identitas Anda. Dongle lama langsung tidak berlaku.</p></div>
      <div class="grid gap-6 md:grid-cols-[1fr_300px]">
        <div class="space-y-4">
          ${field({ id: "replace-user", label: "NIP atau username", value: r.username, bind: "replace.username", help: "Gunakan akun yang terdaftar pada komputer ini.", error: r.errors.username })}
          ${field({ id: "replace-pin", label: "PIN", value: r.pin, bind: "replace.pin", secret: true, placeholder: "Masukkan PIN", error: r.errors.pin })}
        </div>
        <div class="space-y-3">${camera}${photoErr}</div>
      </div>
      ${r.formError ? `<p class="field-error" role="alert">${esc(r.formError)}</p>` : ""}
      <div class="flex flex-col-reverse justify-between gap-3 sm:flex-row">${button("ghost", "Batal", { action: "replace-cancel" })}${button("primary", "Ganti dongle", { submit: true, icon: "usb", loading: r.busy })}</div>
    </form>`, { wide: true });
}

function viewDbFail() {
  const db = (S.status && S.status.db) || {};
  const rows = db.expected && db.actual ? `<dl class="space-y-1 rounded-2xl bg-muted p-4"><div class="flex gap-3"><dt class="w-24 flex-none text-caption text-ink2">Tersimpan</dt><dd class="mono">${esc(short(db.expected))}</dd></div><div class="flex gap-3"><dt class="w-24 flex-none text-caption text-ink2">Saat ini</dt><dd class="mono">${esc(short(db.actual))}</dd></div></dl>` : "";
  return authShell(["done", "wait", "wait"], `<div class="space-y-6">${iconTile("peringatan", "bg-bad-bg text-bad-text")}<div><h1 class="text-display">Database berubah</h1><p class="mt-2 text-reading text-ink2">File database berubah dari luar aplikasi, jadi login ditahan. Pulihkan salinan terakhir yang terbukti utuh. Perubahan sesudah salinan itu tidak ikut kembali.</p></div>${rows}<div>${button("primary", "Pulihkan salinan terakhir", { action: "restore", loading: S.restore.busy, cls: "w-full" })}${S.restore.error ? `<p class="field-error" role="alert">${esc(S.restore.error)}</p>` : ""}</div></div>`);
}

function viewLogin() {
  const l = S.login;
  return authShell(["done", l.rejected ? "fail" : "active", "wait"], `
    <form class="space-y-6" data-submit="login" novalidate>
      <div><h1 class="text-display">Masuk sebagai staf</h1><p class="mt-2 text-reading text-ink2">Masukkan username dan PIN. Setelah itu, aplikasi memindai wajah Anda.</p></div>
      ${field({ id: "login-user", label: "NIP atau username", value: l.username, bind: "login.username", help: "Gunakan akun yang terdaftar pada instansi.", error: l.usernameError, autocomplete: "username" })}
      ${field({ id: "login-pin", label: "PIN", value: l.pin, bind: "login.pin", secret: true, placeholder: "Masukkan PIN", help: "Gunakan PIN yang Anda buat saat mendaftar.", error: l.error, autocomplete: "current-password" })}
      <div class="space-y-2">${button("primary", l.rejected ? "Coba lagi" : "Lanjut ke verifikasi wajah", { submit: true, icon: l.rejected ? null : "wajah", cls: "w-full", loading: l.busy })}${button("ghost", "Daftar sebagai staf baru", { action: "go-register", cls: "w-full" })}</div>
    </form>`);
}

function cameraBox(state, photo) {
  const ring = { ready: "", scanning: "ring-2 ring-amber-500", pass: "ring-2 ring-ok-line", fail: "ring-2 ring-bad-line" }[state] || "";
  return `<div class="relative aspect-[4/3] w-full overflow-hidden rounded-[20px] bg-muted ${ring}">
    ${photo ? `<img src="${esc(photo)}" alt="Foto wajah yang diambil" width="640" height="480" class="h-full w-full -scale-x-100 object-cover">` : `<video id="camera" class="h-full w-full -scale-x-100 object-cover" autoplay playsinline muted aria-label="Pratinjau kamera"></video>`}
    ${state === "scanning" ? '<div class="scan-line"></div>' : ""}
  </div>`;
}

const testUpload = (action) => (S.status && S.status.test_mode
  ? `<label class="btn btn-ghost w-full cursor-pointer" for="face-file">${icon("unggah")}Unggah foto (mode uji)</label><input id="face-file" class="sr-only" type="file" accept="image/*" data-file="${action}">`
  : "");

function viewFace() {
  const f = S.face;
  if (f.state === "nocam") {
    return authShell(["done", "done", "fail"], `<div class="space-y-6">${iconTile("wajah", "bg-amber-50 text-amber-800")}<div><h1 class="text-display">Kamera tidak terdeteksi</h1><p class="mt-2 text-reading text-ink2">${esc(f.error || "Sambungkan webcam, lalu periksa izin kamera pada aplikasi.")}</p></div><div class="space-y-2">${button("primary", "Periksa kamera lagi", { action: "camera-retry", cls: "w-full" })}${testUpload("face-upload")}${button("secondary", "Kembali ke PIN", { action: "back-pin", cls: "w-full" })}</div></div>`);
  }
  const copy = {
    ready: ["Verifikasi wajah", "Hadapkan wajah ke kamera dengan pencahayaan cukup.", ["neutral", "Kamera siap", "kunci"], "Arahkan wajah ke kamera, lalu ambil gambar.", "text-ink2"],
    scanning: ["Memindai wajah", "Hasilnya muncul otomatis setelah pemindaian selesai.", ["warn", "Memindai wajah"], "Tetap menghadap kamera sebentar.", "text-ink2"],
    pass: [`Selamat datang, ${(S.session && S.session.full_name) || "staf"}`, "PIN dan wajah cocok. Akses ke brankas sudah terbuka.", ["ok", "Wajah cocok"], "Verifikasi selesai.", "text-ok-text"],
    fail: f.mismatch
      ? ["Akses ditolak", `Wajah tidak cocok dengan data ${S.login.username}, jadi brankas tetap terkunci.`, ["bad", "Wajah tidak cocok"], "Perbaiki pencahayaan, lalu coba lagi.", "text-bad-text"]
      : ["Verifikasi belum selesai", "Brankas tetap terkunci sampai verifikasi berhasil.", ["bad", "Verifikasi gagal"], f.error || "Coba lagi.", "text-bad-text"],
  }[f.state];
  const actions = {
    ready: `<div class="flex flex-col gap-3 sm:flex-row">${button("secondary", "Kembali ke PIN", { action: "back-pin", cls: "flex-1" })}${button("primary", "Ambil gambar", { icon: "wajah", action: "face-capture", cls: "flex-1" })}</div>`,
    scanning: "",
    pass: button("primary", "Masuk ke area kerja", { action: "enter-app", cls: "w-full" }),
    fail: `${testUpload("face-upload")}<div class="flex flex-col gap-3 sm:flex-row">${button("secondary", "Kembali ke PIN", { action: "back-pin", cls: "flex-1" })}${button("primary", "Pindai ulang", { icon: "wajah", action: "camera-retry", cls: "flex-1" })}</div>`,
  }[f.state];
  const steps = f.state === "pass" ? ["done", "done", "done"] : f.state === "fail" ? ["done", "done", "fail"] : ["done", "done", "active"];
  return authShell(steps, `<div class="space-y-4"><div><h1 class="text-display">${esc(copy[0])}</h1><p class="mt-2 text-reading text-ink2">${esc(copy[1])}</p></div><div class="mx-auto max-w-[400px]">${cameraBox(f.state, f.photo)}</div><div aria-live="polite" class="space-y-2">${badge(...copy[2])}<p class="text-body ${copy[4]}">${esc(copy[3])}</p></div>${actions}</div>`);
}

function viewRegister() {
  const r = S.reg;
  const photoErr = r.errors.photo ? `<p class="field-error" role="alert">${esc(r.errors.photo)}</p>` : "";
  const camera = r.cam === "nocam"
    ? `<div class="flex aspect-[4/3] items-center justify-center rounded-[20px] bg-muted p-4 text-center text-body text-ink2">Kamera tidak terdeteksi. Sambungkan webcam, lalu coba lagi.</div>${button("secondary", "Periksa kamera lagi", { action: "reg-camera", cls: "w-full" })}${testUpload("reg-upload")}`
    : `${cameraBox(r.photo ? "pass" : "ready", r.photo)}${r.photo ? button("secondary", "Ambil ulang foto", { action: "reg-retake", cls: "w-full" }) : button("secondary", "Ambil foto wajah", { icon: "wajah", action: "reg-capture", cls: "w-full" })}`;
  return authShell(["done", "active", r.photo ? "done" : "active"], `
    <form class="space-y-6" data-submit="register" novalidate>
      <div><h1 class="text-h1 sm:text-display">Buat akun staf</h1><p class="mt-2 text-reading text-ink2">PIN dan data wajah tersimpan terenkripsi di komputer ini.</p></div>
      <div class="grid gap-6 md:grid-cols-[1fr_300px]">
        <div class="space-y-4">
          ${field({ id: "reg-user", label: "NIP atau username", value: r.username, bind: "reg.username", placeholder: "Contoh: staf_budi", help: "Dipakai setiap kali login.", error: r.errors.username })}
          ${field({ id: "reg-name", label: "Nama lengkap", value: r.full_name, bind: "reg.full_name", placeholder: "Masukkan nama lengkap", help: "Sesuai data kepegawaian.", error: r.errors.full_name })}
          ${field({ id: "reg-pin", label: "PIN", value: r.pin, bind: "reg.pin", secret: true, placeholder: "Buat PIN", help: "Minimal 6 karakter. Jangan pakai tanggal lahir.", error: r.errors.pin, autocomplete: "new-password" })}
        </div>
        <div class="space-y-3">${camera}${photoErr}</div>
      </div>
      ${r.formError ? `<p class="field-error" role="alert">${esc(r.formError)}</p>` : ""}
      <div class="flex flex-col-reverse justify-between gap-3 sm:flex-row">${button("ghost", "Sudah punya akun? Masuk", { action: "go-login" })}${button("primary", "Daftarkan staf", { submit: true, loading: r.busy })}</div>
    </form>`, { labels: ["USB dongle", "Data staf", "Foto wajah"], title: "Daftarkan akun staf", sub: "Isi data diri dan ambil foto wajah. Aplikasi memakai keduanya saat Anda login.", wide: true });
}

/* ---------- Area kerja ---------- */

function statusBar() {
  const mode = "Biometrik: Face Recognition";
  const db = S.status && S.status.db;
  return `<div class="flex min-h-[56px] flex-wrap items-center gap-3 px-6 py-3">
    <span id="dongle-badge">${badge("ok", "Dongle terhubung")}</span>
    ${badge("neutral", mode, "wajah")}
    <span id="db-badge">${db && db.status === "TAMPERED" ? `<button type="button" class="badge badge-bad" data-action="open-tab" data-tab="audit">${icon("peringatan")}Database berubah dari luar aplikasi</button>` : ""}</span>
  </div>`;
}

function sidebar() {
  const name = (S.session && (S.session.full_name || S.session.username)) || "Staf";
  const user = (S.session && S.session.username) || "";
  return `<aside class="glass-side relative flex w-full flex-none flex-col px-3 py-4 lg:h-full lg:w-64 lg:pt-6">
    <div class="px-1 pb-4 lg:pb-8">${logoBlock()}</div>
    <nav aria-label="Menu utama"><ul class="flex flex-wrap gap-1 lg:flex-col">${TABS.map(([id, label, ic]) => `<li class="lg:w-full"><button type="button" class="nav-item" data-action="open-tab" data-tab="${id}" ${S.tab === id ? 'aria-current="page"' : ""}>${icon(ic)}${esc(label)}</button></li>`).join("")}</ul></nav>
    <div class="relative mt-4 lg:mt-auto" id="account">
      ${S.accountOpen ? `<div class="rise absolute bottom-full left-0 z-30 mb-2 w-full min-w-[200px] rounded-2xl bg-surface p-2 shadow-raised" role="menu" aria-label="Menu akun"><button type="button" role="menuitem" class="btn btn-ghost w-full justify-start" data-action="logout">${icon("keluar")}Keluar</button></div>` : ""}
      <button type="button" class="flex min-h-[52px] w-full items-center gap-2.5 rounded-xl p-2 text-left transition-colors duration-150 hover:bg-white/70 ${S.accountOpen ? "bg-selected" : ""}" data-action="toggle-account" aria-haspopup="menu" aria-expanded="${S.accountOpen}" aria-label="Akun ${esc(name)}">
        <span class="flex h-9 w-9 flex-none items-center justify-center rounded-[10px] bg-surface text-body font-semibold">${esc(name.charAt(0).toUpperCase())}</span>
        <span class="min-w-0 flex-1"><span class="block truncate text-body font-semibold">${esc(name)}</span><span class="mono block truncate text-ink2">${esc(user)}</span></span>
        ${icon("pilih", "h-[18px] w-[18px] flex-none text-ink2")}
      </button>
    </div>
  </aside>`;
}

function viewApp() {
  const content = { memo: tabMemo, vault: tabVault, courier: tabCourier, stego: tabStego, audit: tabAudit }[S.tab]();
  return `<div class="relative flex h-full flex-col overflow-auto lg:flex-row lg:overflow-hidden">
    ${sidebar()}
    <div class="flex min-w-0 flex-1 flex-col bg-canvas lg:min-h-0">
      ${statusBar()}
      <main id="main" tabindex="-1" class="flex-1 px-4 pb-6 sm:px-6 lg:min-h-0 lg:overflow-auto">${content}</main>
    </div>
    ${S.locked ? lockOverlay() : ""}
    ${S.dialog ? dialogView() : ""}
  </div>`;
}

const lockOverlay = () => `<div class="absolute inset-0 z-40 flex items-center justify-center bg-canvas p-6" role="alertdialog" aria-modal="true" aria-labelledby="lock-title">
  <div class="rise w-full max-w-[520px] space-y-5 rounded-3xl bg-surface p-10 shadow-card">${iconTile("usb", "bg-bad-bg text-bad-text")}<h1 id="lock-title" class="text-display">Dongle dicabut</h1><p class="text-reading text-ink2">Aplikasi mengunci layar dan menyembunyikan dokumen. Tancapkan dongle lagi untuk melanjutkan.</p>${badge("bad", "Menunggu dongle")}</div></div>`;

/* ---------- Tab Memo ---------- */

function tabMemo() {
  const m = S.memo;
  if (m.loading && !m.items) return `<div class="card flex h-full items-center justify-center">${statePanel({ ic: "proses", tone: "warn", title: "Memuat memo", body: "Aplikasi mendekripsi judul memo." })}</div>`;
  if (m.error) return `<div class="card flex h-full items-center justify-center">${statePanel({ ic: "peringatan", tone: "bad", title: "Memo gagal dimuat", body: m.error, action: button("secondary", "Muat ulang", { action: "memo-reload" }) })}</div>`;
  const items = m.items || [];
  if (!items.length && !m.compose) return `<div class="card flex h-full items-center justify-center">${statePanel({ ic: "memo", title: "Belum ada memo", body: "Tulis memo pertama, lalu segel ke blockchain sebagai bukti waktu pembuatan.", action: button("primary", "Tulis memo", { icon: "tambah", action: "memo-new" }) })}</div>`;
  return `<div class="flex h-full flex-col gap-4 lg:flex-row">
    <section class="card flex max-h-72 flex-none flex-col gap-2 overflow-auto p-3 lg:max-h-none lg:w-80" aria-label="Daftar memo">
      <div class="flex items-center justify-between gap-2 pb-1 pl-3"><h1 class="text-h2">Memo</h1>${button("secondary", "Tulis memo", { icon: "tambah", action: "memo-new", disabled: m.saving })}</div>
      <ul class="space-y-1">${items.map((d) => {
        const on = d.id === m.selId && !m.compose;
        return `<li><button type="button" class="w-full rounded-2xl px-4 py-3 text-left transition-colors duration-150 ${on ? "bg-muted" : "hover:bg-canvas"}" data-action="memo-select" data-id="${esc(d.id)}" ${on ? 'aria-current="true"' : ""}><span class="block text-body font-semibold ${on ? "text-amber-800" : "text-ink"}">${esc(d.title)}</span><span class="mt-2 flex items-center justify-between gap-2">${badge("neutral", d.category)}<span class="mono text-ink2">Blok #${esc(d.block_index)}</span></span></button></li>`;
      }).join("")}</ul>
    </section>
    <section class="card flex min-h-0 min-w-0 flex-1 flex-col overflow-auto p-8">${memoSheet()}</section>
  </div>`;
}

function memoSheet() {
  const m = S.memo;
  if (m.saving) return `<div class="flex flex-1 flex-col items-center justify-center gap-5 text-center"><h2 class="text-display">Menyegel memo</h2><p class="text-reading text-ink2">Aplikasi mengenkripsi isi memo, lalu mencari hash blok berawalan 000.</p>${sealCard({ status: "mining", index: "Blok baru", time: "Menunggu bukti kerja", nonce: "Sedang dicari", hash: "Belum ada", note: "Aplikasi mencari hash berawalan 000" })}</div>`;
  if (m.compose) return memoForm();
  if (m.detailLoading) return `<div class="flex flex-1 items-center justify-center">${statePanel({ ic: "proses", tone: "warn", title: "Mendekripsi memo", body: "Aplikasi membuka isi memo." })}</div>`;
  if (m.detailError) return `<div class="flex flex-1 items-center justify-center">${statePanel({ ic: "peringatan", tone: "bad", title: "Memo gagal dibuka", body: m.detailError, action: button("secondary", "Coba lagi", { action: "memo-select", data: `data-id="${esc(m.selId)}"` }) })}</div>`;
  const d = m.detail;
  if (!d) return `<div class="flex flex-1 items-center justify-center">${statePanel({ ic: "memo", title: "Pilih memo", body: "Pilih memo pada daftar untuk membaca isinya." })}</div>`;
  return `<article class="flex flex-1 flex-col gap-6">
    <header><h2 class="text-display">${esc(d.title)}</h2><div class="mt-3 flex flex-wrap items-center gap-3">${badge("neutral", d.category)}<span class="mono text-ink2">${esc(d.doc_uuid)}</span><span class="mono text-ink2">${esc(d.author)}</span></div></header>
    <p class="max-w-prose whitespace-pre-wrap text-reading">${esc(d.content)}</p>
    ${sealCard({ status: d.verified === false ? "bad" : "sealed", index: `#${d.block_index}`, time: d.timestamp || d.created_at, nonce: d.nonce ?? "Tidak ditemukan", hash: short(d.block_hash), note: d.verified === false ? "Isi memo atau blok tidak cocok dengan rantai lokal" : "Blok dicatat pada rantai lokal, diawali 000" })}
    <div class="mt-auto flex flex-wrap items-center gap-3 pt-2">${button("primary", "Ekspor paket .vault", { icon: "unduh", action: "memo-export" })}${button("secondary", "Lihat ciphertext", { icon: "mata", action: "memo-cipher" })}<span class="flex-1"></span>${button("ghost", "Hapus memo", { icon: "hapus", action: "memo-delete" })}</div>
  </article>`;
}

function memoForm() {
  const m = S.memo;
  return `<form class="flex flex-1 flex-col gap-5" data-submit="memo-save" novalidate>
    <h2 class="text-display">Tulis memo</h2>
    ${field({ id: "memo-title", label: "Judul memo", value: m.form.title, bind: "memo.form.title", placeholder: "Contoh: Memo Anggaran Kuartal IV", help: "AegisVault mengenkripsi judul sebelum menyimpannya ke database.", error: m.errors.title })}
    ${field({ id: "memo-category", label: "Kategori klasifikasi", value: m.form.category, bind: "memo.form.category", placeholder: "Tulis kategori sesuai aturan instansi", help: "Aplikasi mengenkripsi kategori bersama judul.", error: m.errors.category })}
    <div class="flex min-h-[180px] flex-1 flex-col"><label class="field-label" for="memo-content">Isi memo</label><textarea id="memo-content" class="field-input min-h-[140px] flex-1 ${m.errors.content ? "is-error" : ""}" data-bind="memo.form.content" ${m.errors.content ? 'aria-invalid="true" aria-describedby="memo-content-note"' : 'aria-describedby="memo-content-note"'}>${esc(m.form.content)}</textarea><p id="memo-content-note" class="${m.errors.content ? "field-error" : "field-help"}" ${m.errors.content ? 'role="alert"' : ""}>${esc(m.errors.content || "Isi memo dienkripsi dua lapis: Extended Vigenere, lalu AES-128.")}</p></div>
    ${m.errors.form ? `<p class="field-error" role="alert">${esc(m.errors.form)}</p>` : ""}
    <div class="flex justify-end gap-3">${button("secondary", "Batal", { action: "memo-cancel" })}${button("primary", "Simpan dan segel", { icon: "segel", submit: true })}</div>
  </form>`;
}

/* ---------- Dialog ---------- */

function dialogView() {
  const d = S.dialog;
  let title = "";
  let body = "";
  if (d.type === "export") {
    const file = d.target === "file";
    title = file ? "Kirim ke staf lain" : "Ekspor paket .vault";
    const intro = file
      ? `Aplikasi membungkus <span class="font-semibold text-ink">${esc(d.name)}</span> menjadi paket .vault yang terkunci passphrase bersama. Kirim paketnya lewat WA sebagai dokumen, lalu sampaikan passphrase lewat telepon atau tatap muka. Penerima membukanya di tab Kurir dan verifikasi.`
      : "Penerima butuh passphrase ini untuk membuka paket. Kirim berkas lewat WA atau email, lalu sampaikan passphrase lewat telepon atau tatap muka.";
    body = `<form class="space-y-5" data-submit="export" novalidate><p class="text-body text-ink2">${intro}</p>${field({ id: "export-pass", label: "Passphrase bersama", value: d.pass, bind: "dialog.pass", secret: true, placeholder: "Buat passphrase bersama", help: "Minimal 8 karakter. Makin panjang makin sulit ditebak.", error: d.error, autocomplete: "new-password" })}<div class="flex justify-end gap-3">${button("secondary", "Batal", { action: "close-dialog" })}${button("primary", file ? "Buat paket" : "Ekspor paket", { icon: "unduh", submit: true, loading: d.busy })}</div></form>`;
  } else if (d.type === "cipher") {
    title = "Lihat ciphertext";
    const row = (k, v) => `<div class="rounded-2xl bg-canvas px-4 py-3"><h3 class="mb-1.5 text-label text-ink2">${esc(k)}</h3><p class="mono text-[13px] leading-5">${esc(v)}</p></div>`;
    body = d.busy
      ? statePanel({ ic: "proses", tone: "warn", title: "Menghitung hasil enkripsi", body: "Aplikasi menjalankan tiap lapis enkripsi." })
      : d.error
        ? statePanel({ ic: "peringatan", tone: "bad", title: "Ciphertext gagal dimuat", body: d.error, action: button("secondary", "Coba lagi", { action: "memo-cipher" }) })
        : `<div class="space-y-3"><p class="text-body text-ink2">Hasil tiap lapis enkripsi memo ini. Hanya nilai terakhir yang tersimpan di database.</p>${row("Plainteks", d.data.plaintext)}${row("Lapis 1: Extended Vigenere (hex)", d.data.vigenere_ciphertext_hex)}${row("IV AES-128-CBC (hex)", d.data.aes_iv_hex)}${row("Lapis 2: Base64(IV + ciphertext)", d.data.final_ciphertext_b64)}<div class="flex justify-end pt-2">${button("secondary", "Tutup", { action: "close-dialog" })}</div></div>`;
  } else if (d.type === "delete") {
    title = "Hapus memo ini?";
    body = `<div class="space-y-5"><p class="text-body text-ink2">"${esc(d.memoTitle)}" terhapus dari brankas dan tidak bisa dikembalikan. Blok sertifikatnya tetap tersimpan di rantai.</p>${d.error ? `<p class="field-error" role="alert">${esc(d.error)}</p>` : ""}<div class="flex justify-end gap-3">${button("secondary", "Batal", { action: "close-dialog" })}${button("danger", "Hapus memo", { icon: "hapus", action: "memo-delete-confirm", loading: d.busy })}</div></div>`;
  }
  return `<div class="absolute inset-0 z-30 flex items-center justify-center bg-ink/40 p-6" data-action="dialog-backdrop"><div class="rise max-h-full w-full overflow-auto rounded-3xl bg-surface p-8 shadow-raised" role="dialog" aria-modal="true" aria-labelledby="dialog-title" id="dialog-box" style="max-width:${d.type === "cipher" ? 680 : 520}px"><div class="mb-3 flex items-center justify-between gap-4"><h2 id="dialog-title" class="text-h1">${esc(title)}</h2><button type="button" class="flex h-11 w-11 flex-none items-center justify-center rounded-xl text-ink2 hover:bg-canvas" data-action="close-dialog" aria-label="Tutup dialog">${icon("tutup", "h-6 w-6")}</button></div>${body}</div></div>`;
}

/* ---------- Tab Brankas ---------- */

function dropzone({ id, title, body, label, accept, onFile, error, drag, zone }) {
  return `<div class="dropzone ${error ? "is-error" : ""} ${drag ? "is-drag" : ""}" data-drop="${zone}">
    ${icon(error ? "peringatan" : "unggah", `h-8 w-8 ${error ? "text-bad-text" : "text-amber-800"}`)}
    <div><h3 class="text-h3">${esc(error ? error.title : drag ? "Lepaskan untuk memilih" : title)}</h3><p class="mt-1 text-body ${error ? "text-bad-text" : "text-ink2"}" ${error ? 'role="alert"' : ""}>${esc(error ? error.body : body)}</p></div>
    <label class="btn btn-secondary cursor-pointer has-[:focus-visible]:outline has-[:focus-visible]:outline-2 has-[:focus-visible]:outline-amber-700" for="${id}">${esc(label)}<input id="${id}" class="sr-only" type="file" accept="${accept}" data-file="${onFile}"></label>
  </div>`;
}

function tabVault() {
  const v = S.vault;
  const head = `<header class="mb-4"><h1 class="text-h1">Brankas berkas</h1><p class="mt-1 text-body text-ink2">Aplikasi mengenkripsi setiap berkas dengan RC4 saat disimpan.</p></header>`;
  const dz = dropzone({ id: "vault-file", zone: "vault", onFile: "vault-file", title: "Seret berkas ke sini, atau pilih dari komputer", body: "Maksimal 20 MB. AegisVault mengenkripsi berkas dengan RC4 saat disimpan.", label: v.uploadError ? "Pilih berkas lain" : "Pilih berkas", accept: "*/*", drag: v.drag, error: v.uploadError ? { title: "Berkas gagal diunggah", body: v.uploadError } : null });
  let table;
  if (v.loading && !v.items) table = statePanel({ ic: "proses", tone: "warn", title: "Memuat berkas", body: "Aplikasi membaca daftar berkas." });
  else if (v.error) table = statePanel({ ic: "peringatan", tone: "bad", title: "Daftar berkas gagal dimuat", body: v.error, action: button("secondary", "Muat ulang", { action: "vault-reload" }) });
  else if (!(v.items || []).length && !v.uploading) table = statePanel({ ic: "memo", title: "Belum ada berkas", body: "Unggah berkas pertama lewat kotak di atas." });
  else {
    const rows = (v.items || []).map((f) => `<tr class="transition-colors duration-150 hover:bg-amber-50"><td class="rounded-l-2xl px-5 py-3"><span class="flex items-center gap-3 font-semibold">${icon("memo", "h-[22px] w-[22px] flex-none text-ink2")}<span class="min-w-0 break-all">${esc(f.filename)}</span></span></td><td class="mono px-3 whitespace-nowrap">${esc(fmtBytes(f.size_bytes))}</td><td class="mono px-3">RC4</td><td class="mono px-3 whitespace-nowrap text-ink2">${esc(String(f.created_at || "").slice(0, 10))}</td><td class="rounded-r-2xl px-5 py-3"><div class="flex flex-wrap justify-end gap-2">${button("ghost", "Kirim ke staf lain", { icon: "kurir", action: "vault-send", data: `data-id="${esc(f.id)}" data-name="${esc(f.filename)}"` })}${button("secondary", "Dekripsi dan unduh", { icon: "unduh", action: "vault-download", data: `data-id="${esc(f.id)}" data-name="${esc(f.filename)}"`, loading: v.downloading === f.id })}</div></td></tr>`).join("");
    const up = v.uploading ? `<tr><td class="px-5 py-3"><span class="flex items-center gap-3 font-semibold">${icon("memo", "h-[22px] w-[22px] flex-none text-ink2")}<span class="break-all">${esc(v.uploading.name)}</span></span></td><td class="mono px-3">${esc(fmtBytes(v.uploading.size))}</td><td class="mono px-3">RC4</td><td></td><td class="px-5 text-right">${badge("warn", "Mengenkripsi RC4")}</td></tr>` : "";
    table = `<table class="w-full border-separate border-spacing-y-1 text-body"><caption class="sr-only">Daftar berkas terenkripsi</caption><thead><tr class="text-left text-caption text-ink2"><th class="px-5 py-2 font-medium">Nama berkas</th><th class="px-3 font-medium">Ukuran</th><th class="px-3 font-medium">Algoritma</th><th class="px-3 font-medium">Diunggah</th><th class="px-5 text-right font-medium">Aksi</th></tr></thead><tbody>${up}${rows}</tbody></table>`;
  }
  return `${head}<div class="space-y-4">${dz}<section class="card overflow-auto p-2" aria-label="Tabel berkas">${table}</section></div>`;
}

/* ---------- Tab Kurir ---------- */

function resultCard(res) {
  const cert = res.certificate || {};
  const map = {
    VALID: ["ok", "centang", "Sertifikat blockchain valid", "Dokumen asli dan belum dimodifikasi sejak disegel.", "Cocok: hash isi paket sama dengan sertifikat."],
    TAMPERED_CONTENT: ["bad", "peringatan", "Integritas dokumen rusak", "Isi paket berubah setelah disegel. Jangan pakai dokumen ini, lalu minta pengirim mengekspor ulang.", "Tidak cocok: hash isi paket berbeda dari sertifikat."],
    TAMPERED_PACKAGE: ["bad", "peringatan", "Isi paket berubah setelah diekspor", "Judul, kategori, pengirim, atau sertifikat paket ini sudah diubah. Jangan pakai dokumen ini, lalu minta pengirim mengekspor ulang.", "Tidak cocok: kode integritas paket berbeda dari hasil hitung ulang."],
    TAMPERED_CERTIFICATE: ["bad", "peringatan", "Sertifikat blockchain tidak valid", "Data sertifikat berubah atau tidak memenuhi bukti kerja. Jangan pakai dokumen ini, lalu minta pengirim mengekspor ulang.", "Tidak cocok: hash blok berbeda dari hasil hitung ulang."],
    TAMPERED_CHAIN: ["bad", "peringatan", "Sertifikat bertentangan dengan rantai lokal", "Komputer ini mencatat hash blok berbeda untuk dokumen yang sama. Jangan pakai dokumen ini, lalu laporkan ke pengirim.", "Tidak cocok: hash blok berbeda dari catatan rantai lokal."],
  }[res.status];
  const cls = map[0] === "ok" ? "text-ok-text" : "text-bad-text";
  const tile = map[0] === "ok" ? "bg-ok-bg" : "bg-bad-bg";
  const row = (k, v) => `<div class="flex gap-3"><dt class="w-20 flex-none text-caption text-ink2">${k}</dt><dd class="mono">${esc(v)}</dd></div>`;
  return `<section class="card space-y-5 p-6" aria-live="polite"><div class="flex gap-4"><div class="flex h-14 w-14 flex-none items-center justify-center rounded-2xl ${tile} ${cls}">${icon(map[1], "h-7 w-7")}</div><div><h2 class="text-h1 ${cls}">${map[2]}</h2><p class="mt-1 text-body">${map[3]}</p></div></div><dl class="space-y-2 rounded-2xl bg-muted p-4">${row("ID dokumen", cert.doc_uuid)}${row("Pembuat", cert.author)}${row("Hash isi", short(cert.payload_sha256))}${row("Hash blok", short(cert.block_hash))}</dl><p class="text-label ${cls}">${map[4]}</p></section>`;
}

function tabCourier() {
  const c = S.courier;
  const showResult = c.state === "checking" || c.state === "result";
  if (showResult) {
    const res = c.result;
    const meta = (res && res.metadata) || {};
    const right = c.state === "checking"
      ? `<section class="card space-y-3 p-6" aria-live="polite"><div class="flex items-center gap-4"><div class="flex h-14 w-14 items-center justify-center rounded-2xl bg-amber-50 text-amber-800">${icon("proses", "h-7 w-7 spin")}</div><div><h2 class="text-h1 text-amber-800">Memeriksa sertifikat</h2><p class="mt-1 text-body">Aplikasi mendekripsi paket dan menghitung ulang hash blok.</p></div></div></section>`
      : `${resultCard(res)}${res.valid && res.package_type === "file"
        ? `<section class="card flex-1 space-y-4 p-6"><h2 class="text-h2">Berkas terlampir</h2><div class="flex items-center gap-3 rounded-2xl bg-muted px-4 py-3.5">${icon("memo", "h-[22px] w-[22px] flex-none text-ink2")}<span class="min-w-0 flex-1"><span class="block break-all font-semibold">${esc(meta.filename)}</span><span class="mono text-ink2">${esc(fmtBytes(meta.size_bytes || 0))}, dikirim ${esc(meta.author || "")}</span></span></div><p class="text-body text-ink2">Berkas sudah didekripsi dan hash-nya cocok dengan sertifikat. Unduh untuk membukanya.</p>${button("primary", "Unduh berkas asli", { icon: "unduh", action: "courier-save-file" })}</section>`
        : res.valid
        ? `<section class="card flex-1 p-6"><h2 class="text-h2">${esc(meta.title_plain || "Isi dokumen")}</h2><p class="mt-2 whitespace-pre-wrap text-reading">${esc(res.decrypted_content)}</p></section>`
        : `<section class="card p-6"><h2 class="text-h3">Isi dokumen disembunyikan</h2><p class="mt-1 text-body text-ink2">Aplikasi tidak menampilkan isi paket yang gagal verifikasi.</p></section>`}`;
    const cert = (res && res.certificate) || null;
    return `<h1 class="sr-only">Kurir dan verifikasi</h1><div class="flex h-full flex-col gap-4 lg:flex-row"><section class="card flex flex-none flex-col gap-4 p-6 lg:w-[340px]"><h2 class="text-h2">Paket masuk</h2><div class="flex items-center gap-3 rounded-2xl bg-muted px-4 py-3.5">${icon("kurir", "h-[22px] w-[22px] flex-none text-ink2")}<span class="mono break-all text-[13px]">${esc(c.file ? c.file.name : "")}</span></div>${cert ? `<p class="text-caption text-ink2">Sertifikat mencatat pembuat ${esc(cert.author)} pada ${esc(cert.timestamp)}.</p>` : ""}<div class="mt-auto">${button("secondary", "Impor paket lain", { icon: "unggah", action: "courier-reset", cls: "w-full", disabled: c.state === "checking" })}</div></section><div class="flex min-w-0 flex-1 flex-col gap-4">${right}</div></div>`;
  }
  const fileBlock = c.file
    ? `<div class="flex items-center gap-3 rounded-2xl bg-muted px-4 py-3.5">${icon("kurir", "h-[22px] w-[22px] flex-none text-ink2")}<span class="mono flex-1 break-all text-[13px]">${esc(c.file.name)}</span><button type="button" class="flex h-11 w-11 flex-none items-center justify-center rounded-xl text-ink2 hover:bg-white" data-action="courier-clear" aria-label="Hapus pilihan berkas">${icon("tutup", "h-5 w-5")}</button></div>`
    : dropzone({ id: "courier-file", zone: "courier", onFile: "courier-file", title: "Seret berkas .vault ke sini, atau pilih dari komputer", body: "Pakai berkas yang Anda terima lewat WA, email, atau flashdisk.", label: "Pilih berkas", accept: ".vault,application/json", drag: c.drag, error: c.fileError ? { title: "Berkas tidak bisa dibuka", body: c.fileError } : null });
  return `<header class="mb-4"><h1 class="text-h1">Kurir dan verifikasi</h1><p class="mt-1 text-body text-ink2">Buka paket .vault berisi memo atau berkas dari staf lain, lalu periksa keaslian sertifikatnya.</p></header>
  <div class="flex flex-col gap-4 lg:flex-row"><form class="card flex min-w-0 flex-1 flex-col gap-5 p-6" data-submit="courier" novalidate><h2 class="text-h2">Impor paket masuk</h2>${fileBlock}${field({ id: "courier-pass", label: "Passphrase bersama", value: c.pass, bind: "courier.pass", secret: true, placeholder: "Masukkan passphrase bersama", help: "Tanyakan passphrase ke pengirim, jangan lewat chat yang sama dengan berkas.", error: c.passError })}${button("primary", c.passError ? "Coba lagi" : "Buka dan verifikasi paket", { icon: "segel", submit: true, cls: "w-full" })}</form>
  <section class="card flex flex-none items-center justify-center lg:w-[360px]">${c.passError ? statePanel({ ic: "peringatan", tone: "bad", title: "Paket belum terbuka", body: "Aplikasi belum bisa memeriksa sertifikat tanpa passphrase yang benar." }) : statePanel({ ic: "memo", title: "Belum ada paket dibuka", body: "Hasil pemeriksaan sertifikat dan isi memo atau berkas muncul di sini." })}</section></div>`;
}

/* ---------- Tab Studio ---------- */

const utf8Len = (s) => new TextEncoder().encode(s).length;

function stegoPayloadBytes(msg, pass) {
  const n = utf8Len(msg);
  if (!pass) return n + 4; // "RAW:" + pesan
  const aes = 16 + (Math.floor(n / 16) + 1) * 16; // IV + PKCS#7
  return 4 + 32 + 1 + Math.ceil(aes / 3) * 4; // "ENC:" + salt hex + ":" + Base64
}

const STEGO_ACCEPT = "image/png,image/jpeg,image/bmp,image/tiff,image/webp,.png,.jpg,.jpeg,.jfif,.bmp,.tif,.tiff,.webp";
const STEGO_NAME = /\.(png|jpe?g|jfif|bmp|tiff?|webp)$/i;
const STEGO_FORMATS_TEXT = "PNG, JPG, BMP, TIFF, atau WebP";
const isStegoImage = (file) => STEGO_NAME.test(file.name) || /^image\/(png|jpeg|bmp|x-ms-bmp|tiff|webp)$/.test(file.type);
// WebView tidak bisa menampilkan TIFF, jadi pratinjaunya diganti ikon.
const canPreview = (file) => !/\.tiff?$/i.test(file.name) && file.type !== "image/tiff";
const formatLabel = (fmt) => (fmt === "JPEG" ? "JPG" : fmt === "WEBP" ? "WebP" : fmt);
const stegoOver = () => {
  const s = S.stego;
  return !!(s.cover && s.cap !== null && s.msg && stegoPayloadBytes(s.msg, s.pass) > s.cap);
};

function capacityMeter() {
  const s = S.stego;
  if (!s.cover) return `<p class="text-body text-ink2">Pilih gambar dulu. Aplikasi menghitung panjang pesan yang muat.</p>`;
  if (s.cap === null) return `<div class="flex items-center gap-2 text-body text-ink2">${icon("proses", "h-5 w-5 spin")}Menghitung ruang pesan</div>`;
  const cap = s.cap;
  const used = s.msg ? stegoPayloadBytes(s.msg, s.pass) : 0;
  const over = used > cap;
  const pct = cap ? Math.min(100, (used / cap) * 100) : 0;
  const near = !over && pct >= 90;
  const left = cap - used;
  const bigger = s.coverFormat === "JPEG" ? "gambar lebih besar, atau versi PNG-nya" : "gambar lebih besar";
  const note = over ? `Pesan kelebihan ${fmtInt(used - cap)} byte. Persingkat pesan atau pakai ${bigger}.` : near ? `Tersisa ${fmtInt(left)} byte. Persingkat pesan kalau masih ada tambahan.` : `Masih muat ${fmtInt(left)} byte lagi. Satu huruf biasa memakai 1 byte.`;
  return `<div class="flex items-center justify-between gap-3"><span class="text-label">Ruang pesan</span><span class="mono text-ink2">${esc(formatLabel(s.coverFormat))}, ${s.coverW} x ${s.coverH} px</span></div><p class="mt-2 font-mono text-[14px] font-medium leading-5">${fmtInt(used)} dari ${fmtInt(cap)} byte${over ? "" : " terpakai"}</p><div class="mt-2 h-2.5 overflow-hidden rounded-lg bg-muted" role="progressbar" aria-label="Ruang pesan terpakai" aria-valuemin="0" aria-valuemax="${cap}" aria-valuenow="${Math.min(used, cap)}"><div class="h-full rounded-lg transition-[width] duration-200 ${over ? "bg-bad-line" : near ? "bg-amber-500" : "bg-amber-400"}" style="width:${pct}%"></div></div><p class="mt-2 text-caption ${over ? "text-bad-text" : near ? "text-amber-800" : "text-ink2"}" ${over ? 'role="alert"' : ""}>${note}</p>`;
}

function updateCapacity() {
  const el = document.getElementById("cap-meter");
  if (el) el.innerHTML = capacityMeter();
  const b = document.getElementById("embed-btn");
  if (b) b.disabled = stegoOver() || S.stego.busy || (S.stego.cover && S.stego.cap === null);
}

function clearStegoResult() {
  const s = S.stego;
  if (s.result && s.result.url) URL.revokeObjectURL(s.result.url);
  s.result = null;
  s.done = false;
}

const noPreview = (cls) => `<div class="flex items-center justify-center rounded-2xl bg-muted text-ink2 ${cls}">${icon("gambar", "h-7 w-7")}</div>`;

function stegoComparison() {
  const s = S.stego;
  const r = s.result.report;
  const pct = r ? (r.channels_changed / r.channels_total) * 100 : 0;
  const pctText = pct > 0 && pct < 0.01 ? "kurang dari 0,01" : pct.toFixed(2).replace(".", ",");
  const row = (k, v) => `<div class="rounded-2xl bg-canvas px-4 py-3"><dt class="text-caption text-ink2">${esc(k)}</dt><dd class="mt-1 font-mono text-[14px] font-medium leading-5">${esc(v)}</dd></div>`;
  const figure = (src, cap) => `<figure class="min-w-0">${s.previewOk ? `<img src="${esc(src)}" alt="${esc(cap)}" width="${s.coverW}" height="${s.coverH}" class="h-48 w-full rounded-2xl bg-muted object-contain">` : noPreview("h-48 w-full")}<figcaption class="mt-2 text-label">${esc(cap)}</figcaption></figure>`;
  const jpeg = r && r.method === "dct";
  const metrics = r ? `<dl class="grid gap-3 sm:grid-cols-2">
      ${row("Kemiripan (PSNR)", r.psnr_db === null ? "Identik" : `${String(r.psnr_db).replace(".", ",")} dB`)}
      ${row("Selisih warna terbesar", `${r.max_channel_diff} dari 255`)}
      ${row("Nilai warna berubah", `${pctText}%`)}
      ${row("Ukuran file", `${fmtBytes(s.cover.size)} ke ${fmtBytes(s.result.size)}`)}
    </dl><p class="text-caption text-ink2">${jpeg ? "Pada JPG, pesan disimpan di data kompresinya, jadi gambar tidak dikompres ulang. " : ""}Makin tinggi PSNR, makin mirip. Di atas 40 dB, perbedaannya tidak terlihat mata. Pesan yang lebih pendek mengubah lebih sedikit bagian gambar.</p>` : "";
  const fmt = formatLabel((r && r.format) || s.coverFormat);
  return `<section class="card space-y-4 p-6" aria-label="Perbandingan gambar"><div class="flex flex-wrap items-center justify-between gap-2"><h2 class="text-h2">Perbandingan gambar</h2>${fmt ? badge("ok", `Format tetap ${fmt}`) : ""}</div><div class="grid gap-4 sm:grid-cols-2">${figure(s.coverUrl, "Gambar asli")}${figure(s.result.url, "Hasil dengan pesan")}</div>${metrics}</section>`;
}

function stegoTabs() {
  const s = S.stego;
  const tab = (id, label, ic) => `<button type="button" role="tab" id="stego-tab-${id}" aria-controls="stego-panel" aria-selected="${s.mode === id}" class="flex min-h-[44px] items-center gap-2 rounded-xl px-4 text-body font-semibold transition-colors duration-150 ${s.mode === id ? "bg-white text-amber-800 shadow-sm" : "text-ink2 hover:text-ink"}" data-action="stego-mode" data-mode="${id}">${icon(ic, "h-5 w-5")}${esc(label)}</button>`;
  return `<div role="tablist" aria-label="Pilih kegiatan" class="mb-4 inline-flex flex-wrap gap-1 rounded-2xl bg-muted p-1">${tab("hide", "Sembunyikan pesan", "kunci")}${tab("read", "Baca pesan", "mata")}</div>`;
}

function stegoHidePanel() {
  const s = S.stego;
  const thumb = s.previewOk ? `<img src="${esc(s.coverUrl)}" alt="Pratinjau gambar" width="56" height="56" class="h-14 w-14 flex-none rounded-xl object-cover">` : noPreview("h-14 w-14 flex-none bg-white");
  const coverBlock = s.cover
    ? `<div class="flex items-center gap-3 rounded-2xl bg-muted p-3">${thumb}<span class="mono flex-1 break-all text-[13px]">${esc(s.cover.name)}</span><button type="button" class="flex h-11 w-11 flex-none items-center justify-center rounded-xl text-ink2 hover:bg-white" data-action="stego-clear-cover" aria-label="Hapus gambar">${icon("tutup", "h-5 w-5")}</button></div>`
    : dropzone({ id: "cover-file", zone: "cover", onFile: "cover-file", title: "Seret gambar ke sini, atau pilih dari komputer", body: `${STEGO_FORMATS_TEXT}. Hasilnya tetap berformat sama dengan gambar asli.`, label: "Pilih gambar", accept: STEGO_ACCEPT, drag: s.dragA, error: s.coverError ? { title: "Gambar tidak bisa dipakai", body: s.coverError } : null });
  const blocked = stegoOver() || s.busy || (s.cover && s.cap === null);
  const side = s.result
    ? stegoComparison()
    : `<section class="card flex items-center justify-center p-6">${statePanel({ ic: "gambar", title: "Belum ada hasil", body: "Setelah pesan disembunyikan, gambar asli dan hasilnya tampil berdampingan di sini." })}</section>`;
  return `<div class="grid gap-4 xl:grid-cols-2">
    <form class="card flex flex-col gap-3.5 p-6" data-submit="stego-embed" novalidate><div><h2 class="text-h2">Sembunyikan pesan di gambar</h2><p class="mt-1 text-body text-ink2">Gambar tetap terlihat sama. Pesannya hanya bisa dibaca lewat AegisVault.</p></div>${coverBlock}<div id="cap-meter" class="py-1">${capacityMeter()}</div>
      <div><label class="field-label" for="stego-msg">Pesan</label><textarea id="stego-msg" class="field-input" rows="4" data-bind="stego.msg" placeholder="Tulis pesan yang ingin disembunyikan">${esc(s.msg)}</textarea></div>
      ${field({ id: "stego-pass", label: "Kata sandi pesan (opsional)", value: s.pass, bind: "stego.pass", secret: true, placeholder: "Buat kata sandi", help: "Kalau diisi, penerima perlu kata sandi yang sama untuk membaca pesan. Sampaikan lewat jalur lain." })}
      ${s.embedError ? `<p class="field-error" role="alert">${esc(s.embedError)}</p>` : ""}
      ${s.done ? `<p class="rounded-xl bg-ok-bg p-3 text-body text-ok-text">Gambar tersimpan sebagai ${esc(s.result.name)}. Kirim lewat WA sebagai dokumen, bukan foto, agar pesan tidak hilang.</p>` : ""}
      <button id="embed-btn" type="submit" class="btn btn-primary mt-auto w-full" ${blocked ? "disabled" : ""}>${s.busy ? icon("proses", "spin") : icon("unduh")}Sembunyikan pesan dan simpan gambar</button></form>
    ${side}
  </div>`;
}

function stegoReadPanel() {
  const s = S.stego;
  const xBlock = s.stego
    ? `<div class="flex items-center gap-3 rounded-2xl bg-muted px-4 py-3.5">${icon("gambar", "h-[22px] w-[22px] flex-none text-ink2")}<span class="mono flex-1 break-all text-[13px]">${esc(s.stego.name)}</span><button type="button" class="flex h-11 w-11 flex-none items-center justify-center rounded-xl text-ink2 hover:bg-white" data-action="stego-clear-x" aria-label="Hapus gambar">${icon("tutup", "h-5 w-5")}</button></div>`
    : dropzone({ id: "stego-file", zone: "stego", onFile: "stego-file", title: "Seret gambar yang Anda terima, atau pilih dari komputer", body: `${STEGO_FORMATS_TEXT}. Pakai berkas aslinya. Gambar yang dikirim sebagai foto di WA sudah dikompres, jadi pesannya hilang.`, label: "Pilih gambar", accept: STEGO_ACCEPT, drag: s.dragB, error: s.stegoError ? { title: "Gambar tidak bisa dipakai", body: s.stegoError } : null });
  const xResult = s.xBusy
    ? `<div class="flex items-center gap-2 text-body text-amber-800">${icon("proses", "h-5 w-5 spin")}Membaca pesan dari gambar</div>`
    : s.xResult !== null
      ? `${badge("ok", "Pesan ditemukan")}<p class="mt-2.5 whitespace-pre-wrap break-words text-reading">${esc(s.xResult)}</p>`
      : s.xError
        ? `${badge("bad", "Pesan belum terbaca")}<p class="mt-2.5 text-reading" role="alert">${esc(s.xError)}</p>`
        : `<p class="text-body text-ink2">Isi pesan muncul di sini.</p>`;
  return `<div class="grid gap-4 xl:grid-cols-2">
    <form class="card flex flex-col gap-3.5 p-6" data-submit="stego-extract" novalidate><div><h2 class="text-h2">Baca pesan dari gambar</h2><p class="mt-1 text-body text-ink2">Pilih gambar yang berisi pesan dari staf lain.</p></div>${xBlock}${field({ id: "stego-xpass", label: "Kata sandi pesan (opsional)", value: s.xPass, bind: "stego.xPass", secret: true, placeholder: "Masukkan kata sandi", help: "Isi kalau pengirim memberi kata sandi." })}${button("primary", "Baca pesan", { icon: "mata", submit: true, cls: "mt-auto w-full", disabled: s.xBusy })}</form>
    <section class="card flex flex-col p-6" aria-live="polite"><h2 class="text-h2">Isi pesan</h2><div class="mt-3.5 min-h-[120px] flex-1 rounded-2xl bg-canvas px-4 py-3.5">${xResult}</div></section>
  </div>`;
}

function tabStego() {
  const s = S.stego;
  return `<header class="mb-4"><h1 class="text-h1">Studio steganografi</h1><p class="mt-1 text-body text-ink2">Sembunyikan pesan di dalam gambar, atau baca pesan dari gambar yang Anda terima.</p></header>
  ${stegoTabs()}<div id="stego-panel" role="tabpanel" aria-labelledby="stego-tab-${s.mode}">${s.mode === "read" ? stegoReadPanel() : stegoHidePanel()}</div>`;
}

/* ---------- Tab Audit ---------- */

function tabAudit() {
  const a = S.audit;
  const header = (busy) => `<header class="mb-4 flex flex-wrap items-center justify-between gap-3"><div><h1 class="text-h1">Blockchain dan audit</h1><p class="mt-1 text-body text-ink2">Periksa apakah rantai blok dan database berubah dari luar aplikasi.</p></div>${button("primary", busy ? "Memeriksa rantai" : "Periksa seluruh rantai", { icon: "rantai", action: "audit-run", loading: busy })}</header>`;
  if (a.error) return `${header(false)}<div class="card">${statePanel({ ic: "peringatan", tone: "bad", title: "Audit gagal dimuat", body: a.error, action: button("secondary", "Muat ulang", { action: "audit-run" }) })}</div>`;
  if (!a.data) return `${header(true)}<div class="card">${statePanel({ ic: "proses", tone: "warn", title: "Memuat rantai blok", body: "Aplikasi membaca seluruh blok." })}</div>`;
  const d = a.data;
  const chain = d.chain || [];
  const badIdx = d.chain_valid ? -1 : Number((/ke-(\d+)/.exec(d.message || "") || [])[1] ?? (/Genesis/.test(d.message || "") ? 0 : -1));
  const banner = a.checking
    ? ["bg-amber-50 text-amber-800", "proses", "Memeriksa hash setiap blok dari awal rantai.", "spin"]
    : d.chain_valid && d.db.status === "OK"
      ? ["bg-ok-bg text-ok-text", "centang", "Semua blok valid. Checksum database cocok.", ""]
      : ["bg-bad-bg text-bad-text", "peringatan", d.chain_valid ? "Rantai blok valid, tapi database perlu diperiksa." : d.message, ""];
  const blocks = chain.length ? chain.map((b, i) => {
    const st = a.checking ? ["neutral", "Diperiksa", "kunci"]
      : badIdx === -1 ? (i === 0 ? ["neutral", "Genesis", "kunci"] : ["ok", "Valid"])
        : i < badIdx ? (i === 0 ? ["neutral", "Genesis", "kunci"] : ["ok", "Valid"])
          : i === badIdx ? ["bad", "Tidak valid"] : ["neutral", "Tidak diperiksa", "kunci"];
    return `<li class="min-w-0 rounded-[20px] bg-canvas p-5"><div class="mb-3 flex items-center justify-between gap-2"><h3 class="text-h3">Blok #${esc(b.index)}</h3>${badge(...st)}</div><dl class="space-y-3"><div><dt class="text-caption text-ink2">Hash sebelumnya</dt><dd class="mono mt-0.5" title="${esc(b.previous_hash)}">${esc(short(b.previous_hash))}</dd></div><div><dt class="text-caption text-ink2">Hash blok</dt><dd class="mono mt-0.5" title="${esc(b.block_hash)}">${esc(short(b.block_hash))}</dd></div></dl></li>`;
  }).join("") : "";
  const db = d.db || {};
  const dbMap = { OK: ["ok", "Checksum cocok", "Hash SHA-256 file aegis_vault.db sama dengan nilai yang tersimpan terakhir kali."], TAMPERED: ["bad", "Checksum tidak cocok", "File aegis_vault.db berubah dari luar aplikasi."], MISSING_CHECKSUM: ["warn", "Checksum belum ada", "Aplikasi belum menyimpan checksum untuk database ini."], NO_DATABASE: ["warn", "Database belum ada", "Database dibuat saat data pertama disimpan."] }[db.status] || ["neutral", "Status tidak diketahui", db.message || ""];
  return `${header(a.checking)}<div class="space-y-4">
    <div class="flex flex-wrap items-center gap-3 rounded-2xl px-5 py-4 ${banner[0]}" role="status">${icon(banner[1], `h-6 w-6 flex-none ${banner[3]}`)}<p class="min-w-0 flex-1 text-body font-semibold">${esc(banner[2])}</p>${!a.checking && (!d.chain_valid || d.db.status !== "OK") ? button("secondary", "Pulihkan salinan terakhir", { action: "restore", loading: S.restore.busy }) : ""}</div>
    ${S.restore.error ? `<p class="field-error" role="alert">${esc(S.restore.error)}</p>` : ""}
    <section class="card p-6"><h2 class="mb-4 text-h2">Rantai blok lokal</h2>${chain.length ? `<ol class="grid gap-3 md:grid-cols-2 xl:grid-cols-3">${blocks}</ol>` : statePanel({ ic: "rantai", title: "Rantai masih kosong", body: "Blok pertama muncul setelah memo atau berkas disegel." })}</section>
    <section class="card p-6"><div class="flex flex-wrap items-center justify-between gap-3"><h2 class="text-h2">Checksum database</h2>${badge(dbMap[0], dbMap[1], dbMap[0] === "warn" ? "peringatan" : undefined)}</div><p class="mt-2 text-body text-ink2">${esc(dbMap[2])}</p>${db.status === "TAMPERED" ? `<dl class="mt-3 space-y-1"><div class="flex gap-3"><dt class="w-24 text-caption text-ink2">Tersimpan</dt><dd class="mono">${esc(short(db.expected))}</dd></div><div class="flex gap-3"><dt class="w-24 text-caption text-ink2">Saat ini</dt><dd class="mono">${esc(short(db.actual))}</dd></div></dl>` : ""}</section>
  </div>`;
}

/* ---------- Render ---------- */

function render({ focusMain = false } = {}) {
  const active = document.activeElement;
  const activeId = active && active.id;
  const selStart = active && "selectionStart" in active ? active.selectionStart : null;
  const views = { boot: viewBoot, offline: viewOffline, dongle: viewDongle, replace: viewReplace, dbfail: viewDbFail, login: viewLogin, face: viewFace, register: viewRegister, app: viewApp };
  S.animate = S.view !== S.lastView;
  S.lastView = S.view;
  root().innerHTML = views[S.view]();
  afterRender();
  const dlg = document.getElementById("dialog-box");
  if (dlg) {
    const again = activeId && dlg.querySelector(`#${CSS.escape(activeId)}`);
    (again || dlg.querySelector("input,button:not([aria-label='Tutup dialog']),textarea") || dlg).focus();
  } else if (focusMain) {
    const m = document.getElementById("main");
    if (m) m.focus({ preventScroll: true });
  } else if (activeId) {
    const again = document.getElementById(activeId);
    if (again) {
      again.focus({ preventScroll: true });
      if (selStart !== null && again.setSelectionRange && again.type !== "radio") { try { again.setSelectionRange(selStart, selStart); } catch { /* tipe input tanpa seleksi */ } }
    }
  }
}

function afterRender() {
  const video = document.getElementById("camera");
  if (video && camera.stream) {
    video.srcObject = camera.stream;
  }
  for (const el of document.querySelectorAll('[aria-invalid="true"]')) { el.dataset.err = "1"; }
}

function focusFirstError() {
  const el = document.querySelector('[aria-invalid="true"]');
  if (el) el.focus();
}

function go(view, opts) {
  if (view !== "face" && view !== "register" && view !== "replace") stopCamera();
  S.view = view;
  render({ focusMain: true, ...opts });
}

/* ---------- Kamera ---------- */

const camera = { stream: null };

async function startCamera() {
  if (camera.stream) return true;
  if (!navigator.mediaDevices || !navigator.mediaDevices.getUserMedia) return false;
  try {
    camera.stream = await navigator.mediaDevices.getUserMedia({ video: { width: 640, height: 480, facingMode: "user" }, audio: false });
    return true;
  } catch {
    return false;
  }
}

function stopCamera() {
  if (camera.stream) camera.stream.getTracks().forEach((t) => t.stop());
  camera.stream = null;
}

function captureFrame() {
  const video = document.getElementById("camera");
  if (!video || !video.videoWidth) return null;
  const canvas = document.createElement("canvas");
  canvas.width = video.videoWidth;
  canvas.height = video.videoHeight;
  canvas.getContext("2d").drawImage(video, 0, 0);
  return canvas.toDataURL("image/jpeg", 0.92);
}

const fileToDataUrl = (file) => new Promise((resolve, reject) => {
  const r = new FileReader();
  r.onload = () => resolve(r.result);
  r.onerror = () => reject(r.error);
  r.readAsDataURL(file);
});

async function openFace() {
  S.face = { state: "ready", error: "", photo: null };
  S.view = "face";
  const ok = await startCamera();
  if (!ok) S.face.state = "nocam";
  render({ focusMain: true });
}

function applyLoginError(err) {
  const l = S.login;
  l.usernameError = "";
  l.error = "";
  l.rejected = false;
  if (err.code === "USER_NOT_FOUND") {
    l.usernameError = "Akun belum terdaftar. Periksa username, atau daftar sebagai staf baru.";
  } else if (err.code === "PIN_INVALID") {
    l.error = "PIN salah. Periksa Caps Lock, lalu coba lagi.";
    l.rejected = true;
    l.pin = "";
  } else {
    l.error = err.message;
    l.rejected = true;
    l.pin = "";
  }
}

async function submitLogin(photo) {
  S.face.state = "scanning";
  S.face.photo = photo;
  render();
  stopCamera();
  try {
    const res = await postJson("/api/auth/login", { username: S.login.username.trim(), password: S.login.pin, face_image: photo });
    S.session = res;
    S.login.pin = "";
    S.face = { state: "pass", error: "", photo };
    render({ focusMain: true });
  } catch (err) {
    if (err.code === "PIN_INVALID" || err.code === "USER_NOT_FOUND") {
      applyLoginError(err);
      go("login");
      focusFirstError();
      return;
    }
    const msg = { NO_FACE: "Aplikasi tidak menemukan wajah pada gambar. Hadapkan wajah ke kamera, lalu coba lagi." }[err.code] || err.message;
    S.face = { state: "fail", error: msg, photo, mismatch: err.code === "FACE_MISMATCH" };
    render({ focusMain: true });
  }
}

/* ---------- Status dan penguncian ---------- */

async function pollStatus() {
  let st;
  try {
    st = await getJson("/api/system/status");
  } catch {
    S.failures += 1;
    if (S.failures >= 3 && S.view !== "offline") { S.view = "offline"; render(); }
    return;
  }
  S.failures = 0;
  const prevDb = S.status && S.status.db && S.status.db.status;
  S.status = st;
  const valid = !!(st.dongle && st.dongle.valid);
  const dbBad = !!(st.db && !st.db.ok);

  if (S.view === "boot" || S.view === "offline") {
    if (st.session) S.session = st.session;
    if (!valid) { S.view = "dongle"; render({ focusMain: true }); return; }
    if (dbBad && !S.session) { S.view = "dbfail"; render({ focusMain: true }); return; }
    if (S.session) { enterApp(); return; }
    S.view = "login";
    render({ focusMain: true });
    return;
  }

  if (S.view === "replace") {
    if (valid) { S.replace = blankReplace(); go("login"); }
    return;
  }

  if (S.view === "dbfail") {
    if (!valid) { S.view = "dongle"; render({ focusMain: true }); return; }
    if (!dbBad) { S.restore = { busy: false, error: "" }; go("login"); }
    return;
  }

  if (dbBad && valid && S.view !== "app") { stopCamera(); S.view = "dbfail"; render({ focusMain: true }); return; }

  if (S.view === "app") {
    if (!st.session) {
      S.session = null;
      S.locked = false;
      S.dialog = null;
      S.login = blankLogin();
      go(valid ? "login" : "dongle");
      toast("Sesi berakhir. Silakan masuk lagi.", "bad");
      return;
    }
    if (!valid && !S.locked) { S.locked = true; S.dialog = null; S.accountOpen = false; render(); return; }
    if (valid && S.locked) { S.locked = false; render({ focusMain: true }); return; }
    if (prevDb !== (st.db && st.db.status)) render();
    return;
  }

  if (!valid && S.view !== "dongle") { stopCamera(); S.view = "dongle"; render({ focusMain: true }); return; }
  if (valid && S.view === "dongle") { S.enroll = { busy: false, error: "" }; S.view = dbBad ? "dbfail" : "login"; render({ focusMain: true }); return; }
  if (S.view === "dongle") {
    const key = JSON.stringify(st.dongle);
    if (key !== S._dongleKey) { S._dongleKey = key; render(); }
  }
}

function enterApp() {
  stopCamera();
  S.tab = "memo";
  S.locked = false;
  S.accountOpen = false;
  S.view = "app";
  S.memo = blankMemo();
  S.vault = blankVault();
  S.courier = blankCourier();
  S.stego = blankStego();
  S.audit = { data: null, loading: false, checking: false, error: "" };
  render({ focusMain: true });
  loadMemos();
}

/* ---------- Data tab ---------- */

async function loadMemos(selectId) {
  const m = S.memo;
  m.loading = true;
  m.error = "";
  render();
  try {
    m.items = await getJson("/api/documents");
    m.loading = false;
    const target = selectId ?? (m.items.find((d) => d.id === m.selId) ? m.selId : m.items[0] && m.items[0].id);
    if (target !== undefined && target !== null) await loadDetail(target);
    else { m.selId = null; m.detail = null; render(); }
  } catch (err) {
    m.loading = false;
    m.error = err.message;
    render();
  }
}

async function loadDetail(id) {
  const m = S.memo;
  m.selId = id;
  m.compose = false;
  m.detail = null;
  m.detailError = "";
  m.detailLoading = true;
  render();
  try {
    m.detail = await getJson(`/api/documents/${encodeURIComponent(id)}`);
  } catch (err) {
    m.detailError = err.message;
  }
  m.detailLoading = false;
  render();
}

async function loadVault() {
  const v = S.vault;
  v.loading = true;
  v.error = "";
  render();
  try {
    v.items = await getJson("/api/attachments");
  } catch (err) {
    v.error = err.message;
  }
  v.loading = false;
  render();
}

async function loadAudit() {
  const a = S.audit;
  a.error = "";
  a.checking = !!a.data;
  render();
  try {
    a.data = await getJson("/api/blockchain/audit");
  } catch (err) {
    a.error = err.message;
  }
  a.checking = false;
  render();
}

async function uploadVault(file) {
  const v = S.vault;
  v.uploadError = "";
  if (file.size > MAX_FILE_BYTES) {
    v.uploadError = `Berkas ${fmtBytes(file.size)} melebihi batas 20 MB. Pilih berkas yang lebih kecil.`;
    render();
    return;
  }
  v.uploading = { name: file.name, size: file.size };
  render();
  try {
    await postForm("/api/attachments/upload", { file });
    toast(`${file.name} tersimpan terenkripsi.`);
    v.uploading = null;
    await loadVault();
  } catch (err) {
    v.uploading = null;
    v.uploadError = err.message;
    render();
  }
}

async function setCover(file) {
  const s = S.stego;
  s.coverError = "";
  clearStegoResult();
  s.embedError = "";
  if (!isStegoImage(file)) {
    s.coverError = `Pilih gambar ${STEGO_FORMATS_TEXT}.`;
    render();
    return;
  }
  if (s.coverUrl) URL.revokeObjectURL(s.coverUrl);
  const token = s.capToken + 1;
  Object.assign(s, { cover: file, coverUrl: URL.createObjectURL(file), coverW: 0, coverH: 0, coverFormat: "", cap: null, capToken: token, previewOk: canPreview(file) });
  render();
  try {
    // Ruang pesan dihitung backend, karena JPG memakai cara simpan yang berbeda dari PNG.
    const info = await (await postForm("/api/stego/capacity", { image: file })).json();
    if (s.capToken !== token) return;
    Object.assign(s, { cap: info.capacity_bytes, coverW: info.width, coverH: info.height, coverFormat: info.format });
    updateCapacity();
  } catch (err) {
    if (s.capToken !== token) return;
    URL.revokeObjectURL(s.coverUrl);
    Object.assign(s, { cover: null, coverUrl: "", cap: null, coverError: err.message });
    render();
  }
}

function setCourierFile(file) {
  const c = S.courier;
  c.fileError = "";
  c.passError = "";
  if (!/\.vault$/i.test(file.name)) {
    c.fileError = "Pilih berkas berakhiran .vault.";
    c.file = null;
  } else {
    c.file = file;
  }
  render();
}

function setStegoFile(file) {
  const s = S.stego;
  s.stegoError = "";
  s.xResult = null;
  s.xError = "";
  if (!isStegoImage(file)) {
    s.stegoError = `Pilih gambar ${STEGO_FORMATS_TEXT}.`;
    s.stego = null;
  } else {
    s.stego = file;
  }
  render();
}

/* ---------- Aksi ---------- */

const actions = {
  "retry-status": () => { S.view = "boot"; S.failures = 0; render(); pollStatus(); },
  "toggle-secret": (el) => {
    const input = document.getElementById(el.dataset.target);
    const show = input.type === "password";
    input.type = show ? "text" : "password";
    el.setAttribute("aria-label", el.getAttribute("aria-label").replace(show ? "Tampilkan" : "Sembunyikan", show ? "Sembunyikan" : "Tampilkan"));
    el.classList.toggle("text-amber-800", show);
  },
  enroll: async () => {
    S.enroll = { busy: true, error: "" };
    render();
    try {
      await postJson("/api/dongle/enroll", {});
      S.enroll = { busy: false, error: "" };
      toast("USB terdaftar sebagai dongle.");
      await pollStatus();
    } catch (err) {
      S.enroll = { busy: false, error: err.message };
      render();
    }
  },
  "go-replace": () => { S.replace = blankReplace(); openReplace(); },
  "replace-cancel": () => { S.replace = blankReplace(); go("dongle"); },
  "replace-camera": () => openReplace(),
  "replace-retake": () => { S.replace.photo = null; openReplace(); },
  "replace-capture": () => {
    const photo = captureFrame();
    if (!photo) { S.replace.errors.photo = "Kamera belum mengirim gambar. Coba lagi sebentar."; render(); return; }
    S.replace.photo = photo;
    S.replace.errors.photo = "";
    stopCamera();
    render();
  },
  restore: async () => {
    S.restore = { busy: true, error: "" };
    render();
    try {
      const res = await postJson("/api/system/restore", {});
      S.restore = { busy: false, error: "" };
      toast(res.restored.length ? `Salinan ${res.restored.join(" dan ")} sudah dipulihkan.` : "Tidak ada yang perlu dipulihkan.");
      if (S.view === "app") { S.memo = blankMemo(); S.vault = blankVault(); await loadAudit(); }
      await pollStatus();
    } catch (err) {
      S.restore = { busy: false, error: err.message };
      render();
    }
  },
  "go-register": () => { S.reg = blankReg(); S.login.error = ""; S.login.usernameError = ""; openRegister(); },
  "go-login": () => { S.login.error = ""; go("login"); },
  "back-pin": () => go("login"),
  "camera-retry": () => openFace(),
  "face-capture": () => {
    const photo = captureFrame();
    if (!photo) { S.face = { state: "nocam", error: "Kamera belum mengirim gambar. Periksa kamera, lalu coba lagi." }; stopCamera(); render(); return; }
    submitLogin(photo);
  },
  "enter-app": () => enterApp(),
  "reg-camera": () => openRegister(),
  "reg-capture": () => {
    const photo = captureFrame();
    if (!photo) { S.reg.errors.photo = "Kamera belum mengirim gambar. Coba lagi sebentar."; render(); return; }
    S.reg.photo = photo;
    S.reg.errors.photo = "";
    stopCamera();
    render();
  },
  "reg-retake": () => { S.reg.photo = null; openRegister(); },
  "open-tab": (el) => {
    const tab = el.dataset.tab;
    S.accountOpen = false;
    if (tab === S.tab) { render(); return; }
    S.tab = tab;
    render({ focusMain: true });
    if (tab === "memo" && !S.memo.items) loadMemos();
    if (tab === "vault" && !S.vault.items) loadVault();
    if (tab === "audit") loadAudit();
  },
  "toggle-account": () => { S.accountOpen = !S.accountOpen; render(); },
  logout: async () => {
    S.accountOpen = false;
    try { await postJson("/api/auth/logout", {}); } catch (err) { toast(err.message, "bad"); return; }
    S.session = null;
    S.login = blankLogin();
    go("login");
  },
  "memo-reload": () => loadMemos(),
  "memo-new": () => { const m = S.memo; m.compose = true; m.errors = {}; m.form = { title: "", category: "", content: "" }; render(); const t = document.getElementById("memo-title"); if (t) t.focus(); },
  "memo-cancel": () => { S.memo.compose = false; render(); },
  "memo-select": (el) => loadDetail(isNaN(el.dataset.id) ? el.dataset.id : Number(el.dataset.id)),
  "memo-export": () => { S.dialog = { type: "export", pass: "", error: "", busy: false }; render(); },
  "memo-cipher": async () => {
    S.dialog = { type: "cipher", busy: true };
    render();
    try {
      const data = await getJson(`/api/documents/${encodeURIComponent(S.memo.selId)}/ciphertext`);
      if (S.dialog) S.dialog = { type: "cipher", busy: false, data };
    } catch (err) {
      if (S.dialog) S.dialog = { type: "cipher", busy: false, error: err.message };
    }
    render();
  },
  "memo-delete": () => { S.dialog = { type: "delete", memoTitle: S.memo.detail.title, busy: false, error: "" }; render(); },
  "memo-delete-confirm": async () => {
    S.dialog.busy = true;
    render();
    try {
      await request(`/api/documents/${encodeURIComponent(S.memo.selId)}`, { method: "DELETE" });
      S.dialog = null;
      S.memo.selId = null;
      toast("Memo terhapus dari brankas.");
      await loadMemos();
    } catch (err) {
      S.dialog.busy = false;
      S.dialog.error = err.message;
      render();
    }
  },
  "close-dialog": () => closeDialog(),
  "dialog-backdrop": (el, ev) => { if (ev.target === el) closeDialog(); },
  "vault-reload": () => loadVault(),
  "vault-download": async (el) => {
    const id = isNaN(el.dataset.id) ? el.dataset.id : Number(el.dataset.id);
    S.vault.downloading = id;
    render();
    try {
      const res = await request(`/api/attachments/${encodeURIComponent(id)}/download`);
      saveBlob(await res.blob(), filenameFrom(res, el.dataset.name));
      toast(`${el.dataset.name} selesai didekripsi.`);
    } catch (err) {
      toast(err.message, "bad");
    }
    S.vault.downloading = null;
    render();
  },
  "vault-send": (el) => {
    const id = isNaN(el.dataset.id) ? el.dataset.id : Number(el.dataset.id);
    S.dialog = { type: "export", target: "file", id, name: el.dataset.name, pass: "", error: "", busy: false };
    render();
  },
  "courier-save-file": () => {
    const res = S.courier.result;
    const meta = res.metadata || {};
    const bytes = Uint8Array.from(atob(res.file_b64), (ch) => ch.charCodeAt(0));
    saveBlob(new Blob([bytes], { type: meta.mime_type || "application/octet-stream" }), meta.filename || "berkas");
  },
  "courier-reset": () => { S.courier = blankCourier(); render({ focusMain: true }); },
  "courier-clear": () => { S.courier.file = null; S.courier.passError = ""; render(); },
  "stego-clear-cover": () => { const s = S.stego; clearStegoResult(); if (s.coverUrl) URL.revokeObjectURL(s.coverUrl); Object.assign(s, { cover: null, coverUrl: "", coverW: 0, coverH: 0, coverFormat: "", cap: null, capToken: s.capToken + 1, embedError: "" }); render(); },
  "stego-mode": (el) => { S.stego.mode = el.dataset.mode; render(); },
  "stego-clear-x": () => { Object.assign(S.stego, { stego: null, xResult: null, xError: "", stegoError: "" }); render(); },
  "audit-run": () => loadAudit(),
};

function closeDialog() {
  S.dialog = null;
  render();
}

async function openReplace() {
  S.view = "replace";
  S.replace.cam = "idle";
  const ok = S.replace.photo ? true : await startCamera();
  if (!ok) S.replace.cam = "nocam";
  render({ focusMain: true });
}

async function openRegister() {
  S.view = "register";
  S.reg.cam = "idle";
  const ok = S.reg.photo ? true : await startCamera();
  if (!ok) S.reg.cam = "nocam";
  render({ focusMain: true });
}

const submits = {
  login: async () => {
    const l = S.login;
    l.usernameError = l.username.trim() ? "" : "Isi NIP atau username.";
    l.error = l.pin ? "" : "Isi PIN.";
    if (l.usernameError || l.error) { render(); focusFirstError(); return; }
    l.busy = true;
    render();
    try {
      await postJson("/api/auth/check", { username: l.username.trim(), password: l.pin });
      l.busy = false;
      l.rejected = false;
      openFace();
    } catch (err) {
      l.busy = false;
      if (err.code === "DB_TAMPERED") { await pollStatus(); return; }
      applyLoginError(err);
      render();
      focusFirstError();
    }
  },
  replace: async () => {
    const r = S.replace;
    const e = {};
    if (!r.username.trim()) e.username = "Isi NIP atau username.";
    if (!r.pin) e.pin = "Isi PIN.";
    if (!r.photo) e.photo = "Ambil foto wajah dulu.";
    r.errors = e;
    r.formError = "";
    if (Object.keys(e).length) { render(); focusFirstError(); return; }
    r.busy = true;
    render();
    try {
      await postJson("/api/dongle/replace", { username: r.username.trim(), password: r.pin, face_image: r.photo });
      S.replace = blankReplace();
      S.session = null;
      toast("Dongle baru terdaftar. Dongle lama tidak berlaku lagi.");
      await pollStatus();
    } catch (err) {
      r.busy = false;
      r.pin = "";
      if (err.code === "USER_NOT_FOUND") r.errors.username = "Akun belum terdaftar. Periksa username.";
      else if (err.code === "PIN_INVALID") r.errors.pin = "PIN salah. Periksa Caps Lock, lalu coba lagi.";
      else if (err.code === "NO_STAFF") { S.replace = blankReplace(); toast(err.message, "bad"); go("dongle"); return; }
      else if (err.code === "FACE_MISMATCH") { r.photo = null; r.errors.photo = "Wajah tidak cocok. Ambil ulang foto."; openReplace(); return; }
      else if (err.code === "NO_FACE") { r.photo = null; r.errors.photo = "Aplikasi tidak menemukan wajah. Ambil ulang foto."; openReplace(); return; }
      else r.formError = err.message;
      render();
      focusFirstError();
    }
  },
  register: async () => {
    const r = S.reg;
    const e = {};
    if (!USERNAME_RE.test(r.username.trim())) e.username = "Pakai huruf, angka, titik, garis bawah, atau tanda hubung, tanpa spasi.";
    if (!r.full_name.trim()) e.full_name = "Isi nama lengkap.";
    if (r.pin.length < 6) e.pin = "PIN minimal 6 karakter.";
    if (!r.photo) e.photo = "Ambil foto wajah dulu.";
    r.errors = e;
    r.formError = "";
    if (Object.keys(e).length) { render(); focusFirstError(); return; }
    r.busy = true;
    render();
    try {
      await postJson("/api/auth/register", { username: r.username.trim(), full_name: r.full_name.trim(), password: r.pin, face_image: r.photo });
      S.login = { ...blankLogin(), username: r.username.trim() };
      S.reg = blankReg();
      toast("Akun staf terdaftar. Silakan masuk.");
      go("login");
    } catch (err) {
      r.busy = false;
      if (err.code === "USERNAME_TAKEN") r.errors.username = "Username ini sudah dipakai. Pilih username lain.";
      else if (err.code === "NO_FACE") { r.errors.photo = "Aplikasi tidak menemukan wajah pada foto. Ambil ulang foto."; }
      else r.formError = err.message;
      render();
    }
  },
  "memo-save": async () => {
    const m = S.memo;
    const e = {};
    if (!m.form.title.trim()) e.title = "Isi judul memo.";
    if (!m.form.category.trim()) e.category = "Isi kategori klasifikasi.";
    if (!m.form.content.trim()) e.content = "Isi memo masih kosong.";
    m.errors = e;
    if (Object.keys(e).length) { render(); focusFirstError(); return; }
    m.saving = true;
    render();
    try {
      const doc = await postJson("/api/documents", { title: m.form.title.trim(), category: m.form.category, content: m.form.content });
      m.saving = false;
      m.compose = false;
      toast(`Memo tersegel pada blok #${doc.block_index}.`);
      await loadMemos(doc.id);
    } catch (err) {
      m.saving = false;
      m.errors = { form: err.message };
      render();
    }
  },
  export: async () => {
    const d = S.dialog;
    if (d.pass.length < 8) { d.error = "Passphrase minimal 8 karakter."; render(); return; }
    d.busy = true;
    d.error = "";
    render();
    try {
      const file = d.target === "file";
      const url = file ? `/api/attachments/${encodeURIComponent(d.id)}/export` : `/api/documents/${encodeURIComponent(S.memo.selId)}/export`;
      const res = await postJson2(url, { passphrase: d.pass });
      saveBlob(await res.blob(), filenameFrom(res, file ? `${d.name}.vault` : `${S.memo.detail.doc_uuid}.vault`));
      S.dialog = null;
      toast(file ? "Paket berkas tersimpan. Kirim lewat WA sebagai dokumen, lalu sampaikan passphrase lewat jalur lain." : "Paket tersimpan. Kirim berkasnya, lalu sampaikan passphrase lewat jalur lain.");
      render();
    } catch (err) {
      d.busy = false;
      d.error = err.message;
      render();
    }
  },
  courier: async () => {
    const c = S.courier;
    c.passError = c.pass ? "" : "Isi passphrase bersama.";
    c.fileError = c.file ? "" : "Pilih berkas .vault dulu.";
    if (c.passError || c.fileError) { render(); focusFirstError(); return; }
    c.state = "checking";
    render({ focusMain: true });
    try {
      const res = await (await postForm("/api/documents/import-verify", { file: c.file, passphrase: c.pass })).json();
      if (res.status === "INVALID_PASSPHRASE_OR_TAMPERED") {
        c.state = "idle";
        c.passError = "Passphrase salah, atau isi paket berubah. Tanyakan passphrase ke pengirim, lalu coba lagi.";
      } else if (res.status === "INVALID_FORMAT") {
        c.state = "idle";
        c.file = null;
        c.fileError = "Berkas ini bukan paket .vault yang utuh. Minta pengirim mengekspor ulang.";
      } else {
        c.state = "result";
        c.result = res;
      }
      c.pass = "";
    } catch (err) {
      c.state = "idle";
      c.fileError = err.message;
    }
    render({ focusMain: true });
  },
  "stego-embed": async () => {
    const s = S.stego;
    clearStegoResult();
    s.embedError = "";
    if (!s.cover) { s.embedError = "Pilih gambar dulu."; render(); return; }
    if (!s.msg) { s.embedError = "Tulis pesannya dulu."; render(); const t = document.getElementById("stego-msg"); if (t) t.focus(); return; }
    s.busy = true;
    render();
    try {
      const res = await postForm("/api/stego/embed", { image: s.cover, message: s.msg, passphrase: s.pass });
      const blob = await res.blob();
      let report = null;
      try { report = JSON.parse(res.headers.get("X-Stego-Report")); } catch { /* laporan tidak tersedia */ }
      const name = filenameFrom(res, s.cover.name);
      saveBlob(blob, name);
      s.result = { url: URL.createObjectURL(blob), size: blob.size, report, name };
      s.done = true;
    } catch (err) {
      s.embedError = err.message;
    }
    s.busy = false;
    render();
  },
  "stego-extract": async () => {
    const s = S.stego;
    s.xResult = null;
    s.xError = "";
    if (!s.stego) { s.stegoError = "Pilih gambar dulu."; render(); return; }
    s.xBusy = true;
    render();
    try {
      const res = await (await postForm("/api/stego/extract", { image: s.stego, passphrase: s.xPass })).json();
      s.xResult = res.message;
    } catch (err) {
      s.xError = { PASSPHRASE_REQUIRED: "Pesan ini dikunci dengan kata sandi. Isi kata sandi dari pengirim, lalu coba lagi.", PASSPHRASE_INVALID: "Kata sandi salah, atau gambarnya sudah berubah. Tanyakan lagi ke pengirim." }[err.code] || err.message;
    }
    s.xBusy = false;
    render();
  },
};

const postJson2 = (path, body) => request(path, { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify(body) });

const fileHandlers = {
  "vault-file": uploadVault,
  "courier-file": setCourierFile,
  "cover-file": setCover,
  "stego-file": setStegoFile,
  "face-upload": async (file) => { const photo = await fileToDataUrl(file); S.face.state = "ready"; submitLogin(photo); },
  "replace-upload": async (file) => { S.replace.photo = await fileToDataUrl(file); S.replace.cam = "idle"; render(); },
  "reg-upload": async (file) => { S.reg.photo = await fileToDataUrl(file); S.reg.cam = "idle"; render(); },
};
const dropMap = {
  vault: [(f) => uploadVault(f), "vault", "drag"],
  courier: [(f) => setCourierFile(f), "courier", "drag"],
  cover: [(f) => setCover(f), "stego", "dragA"],
  stego: [(f) => setStegoFile(f), "stego", "dragB"],
};

/* ---------- Delegasi event ---------- */

document.addEventListener("click", (ev) => {
  const el = ev.target.closest("[data-action]");
  if (S.accountOpen && !ev.target.closest("#account")) {
    S.accountOpen = false;
    if (!el) { render(); return; }
  }
  if (el && actions[el.dataset.action]) {
    if (el.dataset.action === "dialog-backdrop" && ev.target !== el) return;
    actions[el.dataset.action](el, ev);
  }
});

document.addEventListener("submit", (ev) => {
  const name = ev.target.dataset.submit;
  if (!name) return;
  ev.preventDefault();
  submits[name]();
});

document.addEventListener("input", (ev) => {
  const el = ev.target;
  const path = el.dataset && el.dataset.bind;
  if (!path) return;
  const keys = path.split(".");
  let obj = S;
  for (const k of keys.slice(0, -1)) obj = obj[k];
  obj[keys[keys.length - 1]] = el.value;
  if (keys[0] === "stego" && (keys[1] === "msg" || keys[1] === "pass")) updateCapacity();
});

document.addEventListener("change", (ev) => {
  const el = ev.target;
  const name = el.dataset && el.dataset.file;
  if (name && el.files[0]) fileHandlers[name](el.files[0]);
});

for (const type of ["dragover", "dragleave", "drop"]) {
  document.addEventListener(type, (ev) => {
    const zone = ev.target.closest && ev.target.closest("[data-drop]");
    if (type === "drop" || type === "dragover") ev.preventDefault();
    if (!zone) return;
    const [handler, key, flag] = dropMap[zone.dataset.drop];
    if (type === "dragover") {
      if (!S[key][flag]) { S[key][flag] = true; zone.classList.add("is-drag"); }
    } else if (type === "dragleave") {
      if (!zone.contains(ev.relatedTarget)) { S[key][flag] = false; zone.classList.remove("is-drag"); }
    } else {
      S[key][flag] = false;
      zone.classList.remove("is-drag");
      if (ev.dataTransfer.files[0]) handler(ev.dataTransfer.files[0]);
    }
  });
}

document.addEventListener("keydown", (ev) => {
  if (ev.key === "Escape") {
    if (S.dialog && !S.dialog.busy) closeDialog();
    else if (S.accountOpen) { S.accountOpen = false; render(); const b = document.querySelector('[data-action="toggle-account"]'); if (b) b.focus(); }
    return;
  }
  if (ev.key !== "Tab") return;
  const box = document.getElementById("dialog-box");
  if (!box) return;
  const items = [...box.querySelectorAll("button:not(:disabled),input,textarea,a[href]")];
  if (!items.length) return;
  const first = items[0];
  const last = items[items.length - 1];
  if (ev.shiftKey && document.activeElement === first) { ev.preventDefault(); last.focus(); }
  else if (!ev.shiftKey && document.activeElement === last) { ev.preventDefault(); first.focus(); }
});

/* ---------- Mulai ---------- */

function start() {
  render();
  pollStatus();
  setInterval(pollStatus, POLL_MS);
}

if (new URLSearchParams(location.search).has("mock")) {
  const s = document.createElement("script");
  s.src = "dev-mock.js";
  s.onload = start;
  document.head.appendChild(s);
} else {
  start();
}
