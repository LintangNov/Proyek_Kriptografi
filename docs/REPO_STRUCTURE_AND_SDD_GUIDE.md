# Panduan Struktur Repositori, Pembagian Tugas 3 Orang & Alur SDD

**Nama Proyek:** AegisVault (Sistem Brankas Dokumen & Pengiriman Rahasia Internal Instansi)  
**Tech Stack:** Python 3.11+ (FastAPI + `pywebview`), HTML5 + TailwindCSS (Light Theme) + JavaScript, SQLite3, OpenCV, PyCryptodome  

---

## 1. Struktur Folder Repositori Lengkap (Tempat Menaruh Semua File)

Berikut adalah posisi peletakan seluruh file spesifikasi Anda di dalam folder proyek `aegis-vault/`:

~~~text
aegis-vault/
├── .cursorrules                        <-- [TARUH DI ROOT] File aturan AI (duplikat jadi CLAUDE.md / GEMINI.md jika perlu)
├── antislop.md                         <-- [TARUH DI ROOT] File filter kualitas UI yang Anda lampirkan
├── DESIGN.md                           <-- [TARUH DI ROOT] Arah desain Light Mode (syarat R-37 antislop.md)
├── docs/                               <-- [FOLDER DOKUMEN SPESIFIKASI]
│   ├── REPO_STRUCTURE_AND_SDD_GUIDE.md <-- Dokumen panduan & pembagian kerja ini
│   ├── PRD.md                          <-- Dokumen Kebutuhan Produk (Tema Terang / Light Mode)
│   └── TECHNICAL_SPEC.md               <-- Spesifikasi Algoritma, Skema Database SQLite, & Kontrak API
│
├── requirements.txt                    <-- Daftar library Python
├── main.py                             <-- [ORANG 3] Entry point aplikasi (FastAPI + jendela desktop pywebview)
│
├── backend/                            <-- [MODUL MESIN UTAMA PYTHON]
│   ├── __init__.py
│   ├── config.py                       <-- [ORANG 2] Konfigurasi path folder storage & konstanta sistem
│   ├── crypto_engine.py                <-- [ORANG 1] SHA-256, Extended Vigenere, AES-128-CBC, RC4, & PBKDF2
│   ├── stego_engine.py                 <-- [ORANG 1] Steganografi LSB Citra PNG 24-bit dengan Header 32-bit
│   ├── blockchain_ledger.py            <-- [ORANG 1] Mesin Blockchain lokal (PoW, Sertifikat, Paket .vault)
│   ├── database.py                     <-- [ORANG 2] Manajer SQLite, Field-Level Encryption, & Checksum DB
│   ├── dongle_guard.py                 <-- [ORANG 2] Deteksi Hardware USB Flashdisk (Serial Number + dongle.key)
│   └── biometric_auth.py               <-- [ORANG 2] Deteksi kapabilitas Fingerprint OS & OpenCV Face Recognition
│
├── frontend/                           <-- [ORANG 3 - ANTARMUKA PENGGUNA DESKTOP (LIGHT THEME)]
│   ├── index.html                      <-- Antarmuka utama berbasis TailwindCSS (Light Mode)
│   └── app.js                          <-- Logika komunikasi frontend ke endpoint FastAPI lokal
│
├── storage/                            <-- [FOLDER DATA LOKAL OTOMATIS]
│   ├── aegis_vault.db
│   ├── db_checksum.sha256
│   ├── blockchain.json
│   ├── faces/
│   └── attachments/
│
└── tests/                              <-- [PENGUJIAN OTOMATIS]
    ├── test_crypto_suite.py            <-- [ORANG 1] Unit test untuk Slice 1
    └── test_system_suite.py            <-- [ORANG 2] Unit test untuk Slice 2 & 3
~~~

**Catatan Nama File Aturan AI di Root Folder:**
* Jika menggunakan **Cursor**: simpan sebagai `aegis-vault/.cursorrules`
* Jika menggunakan **Antigravity / Gemini**: simpan atau duplikat sebagai `aegis-vault/GEMINI.md` dan `aegis-vault/AGENTS.md`
* Jika menggunakan **Claude Code**: simpan atau duplikat sebagai `aegis-vault/CLAUDE.md`

---

## 2. Pembagian Kerja 5 Slice untuk 3 Orang (Paralel & Bebas Bentrok Git)

Karena seluruh kontrak fungsi dan skema data sudah dikunci di `docs/TECHNICAL_SPEC.md`, ketiga anggota tim dapat melakukan *Vibe Coding* pada *file* masing-masing tanpa saling menimpa kode:

| Anggota Tim | Tanggung Jawab Slice | File yang Dikerjakan | Beban & Fokus Utama |
| :--- | :--- | :--- | :--- |
| **Orang 1 (Crypto, Stego & Blockchain Engineer)** | **Slice 1** | `requirements.txt`, `backend/crypto_engine.py`, `backend/stego_engine.py`, `backend/blockchain_ledger.py`, `tests/test_crypto_suite.py` | Mengimplementasikan rumus matematika kriptografi (Vigenere, AES-128, RC4, SHA-256), LSB Steganografi, dan Blockchain PoW beserta pengujiannya. |
| **Orang 2 (Security Infrastructure, DB & Biometric Engineer)** | **Slice 2 & Slice 3** | `backend/config.py`, `backend/database.py`, `backend/dongle_guard.py`, `backend/biometric_auth.py`, `tests/test_system_suite.py` | Mengimplementasikan database SQLite terenkripsi + Checksum, pembacaan USB Hardware Dongle, deteksi sensor Fingerprint PC, dan Face Recognition OpenCV. |
| **Orang 3 (Fullstack API & Light-UI Engineer)** | **Slice 4 & Slice 5** | `main.py`, `frontend/index.html`, `frontend/app.js` | Merakit endpoint REST API FastAPI + `pywebview`, serta membangun seluruh layar UI bertema terang (*Light Mode*) yang mematuhi `DESIGN.md` dan `antislop.md`. |

---

## 3. Urutan Prompt Vibe Coding per Anggota Tim

### A. Prompt untuk Orang 1 (Slice 1: Core Crypto, Stego & Blockchain Engine)

Salin dan berikan instruksi ini ke AI Coding Assistant:

~~~text
Baca dokumen @docs/PRD.md dan @docs/TECHNICAL_SPEC.md secara menyeluruh. Saya bertugas mengerjakan Slice 1 (Core Cryptographic, Steganography & Blockchain Engine). Tolong buatkan:
1. requirements.txt sesuai daftar library pada spesifikasi teknis.
2. backend/crypto_engine.py yang mengimplementasikan PBKDF2-HMAC-SHA256, Hashing Login SHA-256 + Salt, Super Enkripsi Teks (Extended Vigenere 256 ASCII from-scratch + AES-128-CBC PKCS#7), serta Enkripsi File RC4 (KSA & PRGA from-scratch dengan 16-byte nonce unik).
3. backend/stego_engine.py untuk penyisipan dan ekstraksi LSB pada gambar PNG 24-bit menggunakan protokol Header panjang 32-bit Big-Endian.
4. backend/blockchain_ledger.py untuk pembuatan blok sertifikat keaslian dokumen dengan Proof-of-Work (awalan hash '000'), validasi rantai blok, dan pembungkusan/verifikasi paket file .vault.
5. tests/test_crypto_suite.py untuk menguji seluruh fungsi di atas secara otomatis di terminal.
Jangan membuat UI dulu. Pastikan semua fungsi diuji dan lulus 100% di test_crypto_suite.py.
~~~

---

### B. Prompt untuk Orang 2 (Slice 2: Database & Dongle + Slice 3: Biometric)

**Prompt Langkah 1 (Slice 2):**
~~~text
Baca @docs/PRD.md dan @docs/TECHNICAL_SPEC.md bagian Bab 3.1, 3.2, dan 3.5. Saya bertugas mengerjakan Slice 2 (Database Layer & Hardware Dongle Security). Tolong buatkan:
1. backend/config.py untuk menginisialisasi direktori storage/, storage/faces/, dan storage/attachments/.
2. backend/database.py menggunakan sqlite3 sesuai skema tabel users, documents, dan attachments di spesifikasi teknis. Implementasikan Field-Level Encryption untuk kolom berakhiran _enc dan mekanisme validasi/update Database Integrity Checksum (storage/db_checksum.sha256).
3. backend/dongle_guard.py untuk memindai drive USB menggunakan psutil dan ctypes (Volume Serial Number Windows beserta fallback pengujian), membuat file dongle.key saat registrasi USB baru, dan memvalidasi keberadaan USB Dongle secara real-time.
4. tests/test_system_suite.py untuk menguji fungsi database dan validasi dongle.
~~~

**Prompt Langkah 2 (Slice 3):**
~~~text
Sekarang lanjut ke Slice 3 (Biometric Authentication Layer) mengacu pada @docs/TECHNICAL_SPEC.md Bab 3.2. Tolong buatkan backend/biometric_auth.py yang memiliki fitur:
1. Pengecekan ketersediaan sensor sidik jari (Windows Biometric / Windows Hello) di PC saat ini. Jika PC tidak memilikinya, kembalikan status fingerprint_available: False dan aktifkan mode FACE_RECOGNITION.
2. Fungsi pendaftaran wajah (Face Enrollment) dan verifikasi wajah (Face Verification) dari frame gambar base64 menggunakan OpenCV Haar Cascade (haarcascade_frontalface_default.xml), normalisasi histogram grayscale 128x128, dan pencocokan skor kemiripan tanpa menggunakan library dlib. Tambahkan pengujiannya ke tests/test_system_suite.py.
~~~

---

### C. Prompt untuk Orang 3 (Slice 4: FastAPI Bridge + Slice 5: Light Mode UI)

**Prompt Langkah 1 (Slice 4):**
~~~text
Baca @docs/PRD.md dan @docs/TECHNICAL_SPEC.md Bab 4. Saya bertugas mengerjakan Slice 4 (FastAPI Backend Bridge & Desktop Launcher). Tolong buatkan main.py yang:
1. Menyediakan seluruh endpoint REST API lokal sesuai tabel kontrak API di @docs/TECHNICAL_SPEC.md Bab 4 dengan mengintegrasikan modul di backend/.
2. Melayani file statis dari folder frontend/ dan membuka jendela aplikasi desktop mandiri menggunakan pywebview (serta mendukung akses via browser lokal di http://127.0.0.1:8000 untuk kemudahan inspeksi).
~~~

**Prompt Langkah 2 (Slice 5: Mengaktifkan `antislop.md` mode `during` + `DESIGN.md` Light Mode):**
~~~text
Use antislop during for this session. Baca @antislop.md, @DESIGN.md, dan @docs/PRD.md Bab 6. Kita akan mengerjakan Slice 5 (Frontend UI/UX - Institutional Archival Light Theme).
Tolong buatkan frontend/index.html dan frontend/app.js menggunakan TailwindCSS dengan Tema Terang (Light Mode) sesuai palet warna, tipografi, dan dial ENERGY 1 / RHYTHM 2 / MOTION 1 di @DESIGN.md.
Pastikan seluruh elemen dan layar berikut berfungsi penuh, memiliki Empty/Loading/Error state (R-27), bebas dari karakter em-dash (R-02), dan terhubung ke API main.py:
1. Layar Gatekeeper USB Dongle: Menolak akses jika USB Dongle belum dicolokkan, serta menyediakan tombol inisialisasi/registrasi USB Flashdisk untuk setup awal.
2. Layar Multi-User Login & Registrasi Staf: Form NIP/Username + PIN/Password + Live Webcam Preview untuk verifikasi wajah (beserta indikator status sensor Fingerprint PC).
3. Tab Memo Internal (Super Enkripsi) & Segel Blockchain: Buat, baca, dan hapus memo teks, tampilkan komponen Cryptographic Seal Stamp, tombol Inspect Ciphertext (menampilkan hasil Extended Vigenere & AES-128), dan tombol Ekspor Paket .vault dengan Passphrase Bersama.
4. Tab Brankas Berkas (RC4 File Vault): Upload dokumen lampiran, enkripsi otomatis dengan RC4 Stream Cipher, dan dekripsi/unduh kembali.
5. Tab Kurir & Verifikasi Dokumen Masuk (.vault): Import file .vault dari staf lain, masukkan Passphrase Bersama, dekripsi isi dokumen, dan tampilkan kartu hasil verifikasi Sertifikat Blockchain (Hijau #059669 jika asli/utuh, Merah #DC2626 jika terdeteksi manipulasi/tampered).
6. Tab Steganography Studio (.PNG): Panel kiri untuk Embed Pesan ke PNG (lengkap dengan kalkulator kapasitas byte) dan panel kanan untuk Ekstrak Pesan dari PNG.
7. Tab Blockchain Explorer & DB Audit: Visualisasi rantai blok lokal beserta tombol verifikasi integritas seluruh blok dan checksum SHA-256 database SQLite.
Sertakan laporan Delivery Gate sesuai @antislop.md setelah selesai.
~~~