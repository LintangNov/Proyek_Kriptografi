/* Data tiruan khusus pengujian: hanya aktif dengan index.html?mock=1 dan tidak melakukan kriptografi apa pun. Panel kuning menandai mode ini. */
(function () {
  const M = {
    dongle: "valid", face: "cocok", pin: "123456", session: null, nextId: 4, fail: "",
    users: { staf_budi: "Staf Budi" },
    docs: [
      { id: 1, doc_uuid: "DOC-9012-AB", title: "Memo Anggaran Kuartal IV", category: "Sangat rahasia", author: "staf_budi", content: "Rapat Anggaran Rahasia 2026!", block_index: 1, nonce: 7485, timestamp: "2026-11-08T09:30:00Z", created_at: "2026-11-08T09:30:00Z", block_hash: "00068046b3657674405cf2da64fe1bf21ebf41fc01be23edb6bc0cc766d7fea0" },
    ],
    files: [{ id: 1, filename: "anggaran-kuartal-iv.pdf", size_bytes: 2516582, created_at: "2026-11-08T10:00:00Z" }],
    chainBad: false, dbBad: false,
  };
  const realFetch = window.fetch.bind(window);
  const wait = (ms) => new Promise((r) => setTimeout(r, ms));
  const json = (body, status = 200) => new Response(JSON.stringify(body), { status, headers: { "Content-Type": "application/json" } });
  const fail = (status, code, message) => json({ detail: { code, message } }, status);
  const blob = (text, name, type) => new Response(new Blob([text], { type }), { status: 200, headers: { "Content-Disposition": `attachment; filename="${name}"` } });
  const cert = { block_index: 1, timestamp: "2026-11-08T09:30:00Z", doc_uuid: "DOC-9012-AB", author: "staf_budi", payload_sha256: "d0831e744a17e45a028245b43d13d90fef83caa587033f70319c3d92085e7914", previous_hash: "0".repeat(64), nonce: 7485, block_hash: M.docs[0].block_hash };
  const meta = { doc_uuid: "DOC-9012-AB", author: "staf_budi", title_plain: "Memo Anggaran Kuartal IV", category_plain: "Sangat rahasia" };
  const genesis = { index: 0, previous_hash: "0".repeat(64), block_hash: "000" + "a".repeat(61) };

  window.fetch = async (url, opt = {}) => {
    const path = String(url);
    if (!path.startsWith("/api/")) return realFetch(url, opt);
    const method = opt.method || "GET";
    const body = opt.headers && opt.body && typeof opt.body === "string" ? JSON.parse(opt.body) : {};
    const form = opt.body instanceof FormData ? opt.body : null;
    const key = `${method} ${path}`;
    if (M.fail && path.startsWith(M.fail)) { await wait(150); return fail(500, "ERROR", "Layanan lokal AegisVault tidak merespons. Muat ulang, atau buka ulang aplikasi kalau masalah berlanjut."); }
    if (key === "GET /api/system/status") {
      return json({ dongle: { valid: M.dongle === "valid", connected: M.dongle !== "none", can_enroll: false, reason: M.dongle === "wrong" ? "USB ini bukan dongle yang terdaftar di komputer ini." : "" }, biometric: { fingerprint_available: false, active_mode: "FACE_RECOGNITION" }, db: { ok: !M.dbBad, status: M.dbBad ? "TAMPERED" : "OK", expected: M.dbBad ? "a".repeat(64) : null, actual: M.dbBad ? "b".repeat(64) : null }, session: M.session, test_mode: true });
    }
    await wait(500);
    if (key === "POST /api/dongle/enroll") return fail(403, "DONGLE_LOCKED", "Komputer ini sudah punya dongle terdaftar.");
    if (key === "POST /api/dongle/replace") { if (M.dongle === "none") return fail(400, "NO_DRIVE", "Tidak ada USB terdeteksi. Tancapkan flashdisk, lalu coba lagi."); M.dongle = "valid"; sync(); M.session = null; return json({ enrolled: true }); }
    if (key === "POST /api/system/restore") { const was = M.dbBad || M.chainBad; M.dbBad = false; M.chainBad = false; return json({ restored: was ? ["database"] : [] }); }
    if (key === "POST /api/auth/check") { if (!M.users[body.username]) return fail(404, "USER_NOT_FOUND", "Akun belum terdaftar."); if (body.password !== M.pin) return fail(401, "PIN_INVALID", "PIN salah."); return json({ ok: true }); }
    if (key === "POST /api/auth/register") { if (M.users[body.username]) return fail(409, "USERNAME_TAKEN", "Username sudah dipakai."); M.users[body.username] = body.full_name; return json({ username: body.username, full_name: body.full_name }); }
    if (key === "POST /api/auth/login") {
      await wait(900);
      if (!M.users[body.username]) return fail(404, "USER_NOT_FOUND", "Akun belum terdaftar.");
      if (body.password !== M.pin) return fail(401, "PIN_INVALID", "PIN salah.");
      if (M.face === "tolak") return fail(401, "FACE_MISMATCH", "Wajah tidak cocok.");
      if (M.face === "kosong") return fail(422, "NO_FACE", "Wajah tidak terdeteksi.");
      M.session = { username: body.username, full_name: M.users[body.username] };
      return json(M.session);
    }
    if (key === "POST /api/auth/logout") { M.session = null; return json({ ok: true }); }
    if (key === "GET /api/documents") return json(M.docs.map(({ content, ...d }) => d));
    if (key === "POST /api/documents") {
      await wait(1400);
      const id = M.nextId++;
      const doc = { id, doc_uuid: `DOC-CONTOH-${id}`, title: body.title, category: body.category, author: M.session.username, content: body.content, block_index: M.docs.length + 1, nonce: 1000 + id, timestamp: "2026-11-10T08:00:00Z", created_at: "2026-11-10T08:00:00Z", block_hash: "000" + String(id).repeat(61) };
      M.docs.unshift(doc);
      return json(doc);
    }
    let m = /^\/api\/documents\/([^/]+)$/.exec(path);
    if (m && method === "GET") { const d = M.docs.find((x) => String(x.id) === m[1]); return d ? json(d) : fail(404, "NOT_FOUND", "Memo tidak ditemukan."); }
    if (m && method === "DELETE") { M.docs = M.docs.filter((x) => String(x.id) !== m[1]); return json({ ok: true }); }
    m = /^\/api\/documents\/([^/]+)\/ciphertext$/.exec(path);
    if (m) return json({ plaintext: "Rapat Anggaran Rahasia 2026!", vigenere_ciphertext_hex: "a52f64139977ba14289e89b832cdfdb1b43655258eb899d8f1695e67", aes_iv_hex: "0f1e2d3c4b5a69788796a5b4c3d2e1f0", final_ciphertext_b64: "Dx4tPEtaaXiHlqW0w9Lh8LbZDw5agoFSmcIjdw19C/jU49VASveqsp0n0x7lmdkc" });
    if (/\/export$/.test(path)) return blob("{}", "memo-contoh.vault", "application/json");
    if (key === "POST /api/documents/import-verify") {
      await wait(1000);
      const name = form.get("file").name, pass = form.get("passphrase");
      if (pass === "salah") return json({ valid: false, status: "INVALID_PASSPHRASE_OR_TAMPERED" });
      if (name.includes("rusak")) return json({ valid: false, status: "INVALID_FORMAT" });
      if (name.includes("manipulasi")) return json({ valid: false, status: "TAMPERED_CONTENT", metadata: meta, certificate: cert, decrypted_content: "Isi yang sudah berubah" });
      return json({ valid: true, status: "VALID", metadata: meta, certificate: cert, decrypted_content: "Rapat Anggaran Rahasia 2026!" });
    }
    if (key === "GET /api/attachments") return json(M.files);
    if (key === "POST /api/attachments/upload") { await wait(800); const f = form.get("file"); M.files.unshift({ id: M.nextId++, filename: f.name, size_bytes: f.size, created_at: "2026-11-10T08:00:00Z" }); return json({ ok: true }); }
    if (/^\/api\/attachments\/.+\/download-encrypted$/.test(path)) return blob("nonce dan ciphertext contoh", "ATT-CONTOH.rc4", "application/octet-stream");
    if (/^\/api\/attachments\/.+\/download$/.test(path)) return blob("isi contoh", "berkas-contoh.txt", "text/plain");
    if (key === "POST /api/stego/embed") return blob("png contoh", "stego_image.png", "image/png");
    if (key === "POST /api/stego/extract") { const n = form.get("image").name; if (n.includes("chat")) return fail(422, "NO_MESSAGE", "Gambar ini tidak memuat pesan yang bisa dibaca. Minta pengirim mengirim PNG asli sebagai dokumen, bukan foto."); return json({ message: "Rapat Anggaran Rahasia 2026!" }); }
    if (key === "GET /api/blockchain/audit") {
      await wait(700);
      const chain = [genesis, { index: 1, previous_hash: genesis.block_hash, block_hash: M.docs[M.docs.length - 1].block_hash }, { index: 2, previous_hash: M.docs[M.docs.length - 1].block_hash, block_hash: "000" + "b".repeat(61) }];
      return json({ chain, chain_valid: !M.chainBad, message: M.chainBad ? "Hash blok ke-2 telah dimanipulasi atau tidak cocok." : "Seluruh rantai blok valid dan konsisten.", db: M.dbBad ? { status: "TAMPERED", expected: "a".repeat(64), actual: "b".repeat(64) } : { status: "OK" } });
    }
    return fail(404, "NOT_FOUND", `Mock belum punya ${key}`);
  };

  window.__mock = M;

  const sel = (id, label, opts, val) => `<label class="block">${label}<select id="${id}" class="mt-0.5 block w-full rounded border border-line bg-white px-1 py-0.5">${opts.map((o) => `<option ${o === val ? "selected" : ""}>${o}</option>`).join("")}</select></label>`;
  function sync() { const d = document.getElementById("m-dongle"); if (d) d.value = M.dongle; }
  const whenReady = (fn) => (document.readyState === "loading" ? window.addEventListener("DOMContentLoaded", fn) : fn());
  whenReady(() => {
    const p = document.createElement("aside");
    p.className = "fixed right-3 top-3 z-[60] w-44 space-y-1 rounded-xl bg-amber-100 p-2.5 text-caption text-amber-800 shadow-raised";
    p.setAttribute("aria-label", "Panel mode uji");
    p.innerHTML = `<strong class="block">Mode uji: data tiruan</strong>${sel("m-dongle", "Dongle", ["valid", "none", "wrong"], M.dongle)}${sel("m-face", "Hasil wajah", ["cocok", "tolak", "kosong"], M.face)}${sel("m-fail", "API gagal", ["", "/api/documents", "/api/attachments", "/api/blockchain"], "")}<label class="flex items-center gap-1"><input id="m-chain" type="checkbox">Rantai rusak</label><label class="flex items-center gap-1"><input id="m-db" type="checkbox">Database berubah</label>`;
    document.body.appendChild(p);
    p.addEventListener("change", (e) => {
      const t = e.target;
      if (t.id === "m-dongle") M.dongle = t.value;
      if (t.id === "m-face") M.face = t.value;
      if (t.id === "m-fail") M.fail = t.value;
      if (t.id === "m-chain") M.chainBad = t.checked;
      if (t.id === "m-db") M.dbBad = t.checked;
    });
  });
})();
