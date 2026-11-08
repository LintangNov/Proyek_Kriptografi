# Project Context & System Rules: AegisVault Desktop

Anda adalah Senior Python & Security Engineer yang sedang membangun **AegisVault**, aplikasi desktop brankas dokumen dan pengiriman pesan rahasia internal instansi untuk Proyek Akhir Mata Kuliah Kriptografi.

## 1. Dokumen Acuan Wajib (Single Source of Truth)
Sebelum menulis atau memodifikasi kode apa pun, Anda WAJIB membaca dan mematuhi:
1. `docs/PRD.md` (Alur pengguna multi-staf, 7 kriteria kriptografi, dan Acceptance Criteria)
2. `docs/TECHNICAL_SPEC.md` (Rumus kriptografi, skema SQLite, format header Steganografi, struktur JSON `.vault` & Blockchain, dan kontrak REST API)
3. `DESIGN.md` (Arah desain visual Light Mode / Tema Terang Instansi, palet warna, tipografi, dan Dial Liveliness)
4. `antislop.md` (Filter kualitas UI/UX dan aturan wajib R-01 s.d. R-40)

## 2. Aturan Teknis & Kriptografi Mutlak
1. **Tech Stack:** Python 3.11+, FastAPI + Uvicorn, `pywebview` (jendela desktop), SQLite3, OpenCV (`opencv-python`), Pillow, PyCryptodome, serta HTML5 + TailwindCSS + Vanilla JS di `frontend/`.
2. **DILARANG Menggunakan `dlib`:** Untuk biometrik wajah, gunakan `cv2.CascadeClassifier` (Haar Cascade) + pencocokan matriks/histogram OpenCV sesuai `docs/TECHNICAL_SPEC.md` Bab 3.2 agar instalasi di Windows 100% stabil.
3. **Implementasi Algoritma Kriptografi:**
   - **Extended Vigenere Cipher (256 ASCII)** dan **RC4 (KSA + PRGA)** WAJIB ditulis *from-scratch* (fungsi perulangan byte eksplisit di Python) di dalam `backend/crypto_engine.py` agar rumus matematikanya terlihat jelas saat penilaian kode oleh dosen.
   - **AES-128** menggunakan mode **CBC** dengan PKCS#7 padding dan IV acak 16-byte (`pycryptodome`).
   - **Steganografi Gambar** menggunakan metode **LSB pada citra PNG 24-bit** dengan protokol **Header 32-bit Big-Endian** (penyimpan panjang byte pesan) di `backend/stego_engine.py`.
   - **Blockchain Lokal** mencetak blok dengan Proof-of-Work (awalan hash `"000"`) sebagai Sertifikat Keaslian Dokumen (`blockchain_certificate`) yang disertakan saat mengekspor file `.vault`.
4. **Tema Visual (Light Mode Mutlak):**
   - Gunakan **Tema Terang (Light Mode)** sesuai `DESIGN.md`. DILARANG menggunakan tema gelap (*dark mode default*).
   - DILARANG menggunakan karakter *em dash* pada seluruh teks antarmuka, label, pesan error, maupun komentar dokumentasi UI (Aturan R-02 `antislop.md`). Gunakan tanda koma, titik dua, atau tanda kurung.
   - Setiap tombol dan elemen interaktif di UI wajib memiliki fungsi nyata yang terhubung ke endpoint FastAPI (Aturan R-26 & R-35 `antislop.md`), serta memiliki *Empty State*, *Loading State*, dan *Error State* (Aturan R-27).

<!-- antislop:start -->
## antislop
For UI, copy, people, mobile layout, or code comments work, read `antislop.md` (core) and `DESIGN.md` for direction.
Before starting UI work, follow the core's "Two Usage Modes" section in strict order: explicit session instruction first, then global preference, then ask. A session instruction always wins. For a resolved mode, say `antislop active: <mode> (session override).` or `antislop active: <mode> (global preference).` once before presenting findings or making edits, using the actual mode and source.
<!-- antislop:end -->