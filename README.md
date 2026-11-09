# AegisVault Desktop

Sistem Brankas Dokumen dan Pengiriman Pesan Rahasia Internal Instansi berbasis desktop multi-pengguna (*multi-staff*), dirancang untuk Proyek Akhir Mata Kuliah Kriptografi.

Aplikasi ini mengintegrasikan pengamanan perangkat keras (USB Hardware Dongle), verifikasi biometrik adaptif (Face Recognition via OpenCV), enkripsi teks dan berkas berlapis, penyembunyian pesan melalui citra digital (Steganografi LSB), serta buku besar rantai blok lokal (Blockchain Proof-of-Work) untuk penerbitan Sertifikat Keaslian Dokumen (*e-Seal*).

---

## Fitur Utama dan Kriteria Kriptografi

1. **Hardware Dongle Gatekeeper (KR-01):** Validasi nomor seri perangkat keras USB Flashdisk dan berkas verifikasi `dongle.key` bertanda tangan SHA-256. Layar terkunci otomatis jika dongle dicabut.
2. **Biometrik Adaptif dan Login Kriptografis (KR-01, KR-02):** Deteksi wajah menggunakan Haar Cascade OpenCV dan pencocokan matriks (Normalized Cross-Correlation + Histogram). Hash kata sandi menggunakan SHA-256 dengan salt acak 128-bit dan derivasi kunci PBKDF2-HMAC-SHA256.
3. **Super Enkripsi Teks Memo (KR-03):** Enkripsi dua lapis berurutan menggabungkan algoritma klasik Extended Vigenere Cipher (256 ASCII) dan algoritma modern AES-128 Mode CBC (PKCS#7 padding, IV acak 16-byte).
4. **Enkripsi Berkas Lampiran (KR-04):** Pengamanan berkas dokumen (`.pdf`, `.docx`, `.zip`, `.mp3`) menggunakan stream cipher RC4 (ARCFOUR) dengan nonce unik per berkas.
5. **Enkripsi Basis Data dan Integritas (KR-05):** Field-Level Encryption pada SQLite untuk data sensitif, dilengkapi pemantauan checksum integritas berkas basis data via SHA-256.
6. **Steganografi Citra Digital (KR-06):** Penyisipan pesan rahasia ke dalam citra PNG 24-bit menggunakan metode Least Significant Bit (LSB) dengan protokol Header 32-bit Big-Endian panjang pesan.
7. **Sertifikat Keaslian Blockchain (KR-07):** Pencetakan blok rantai lokal dengan Proof-of-Work (awalan hash `000`) dan penerbitan sertifikat digital saat mengekspor paket dokumen `.vault`.

---

## Prasyarat Sistem

* **Sistem Operasi:** Windows 10 atau Windows 11 (direkomendasikan)
* **Python:** Versi 3.11 atau lebih baru (teruji di Python 3.11, 3.12, dan 3.13)
* **Web Runtime:** Microsoft Edge WebView2 Runtime (bawaan Windows 10/11)
* **Perangkat Keras Tambahan:**
  * 1 unit USB Flashdisk (sebagai Hardware Dongle)
  * Kamera Web / Webcam (untuk pendaftaran dan verifikasi wajah)

---

## Panduan Instalasi

### 1. Clone atau Buka Folder Proyek
Buka terminal (PowerShell atau Command Prompt) pada direktori proyek:
```powershell
cd "d:\KULIAH\Semester 5\Kriptografi\aegis-vault"
```

### 2. Buat dan Aktifkan Virtual Environment (Disarankan)
```powershell
# Membuat virtual environment
python -m venv .venv

# Mengaktifkan virtual environment di PowerShell
.venv\Scripts\Activate.ps1

# (Jika menggunakan CMD biasa)
# .venv\Scripts\activate.bat
```

> [!TIP]
> Jika muncul pesan error *Execution of scripts is disabled on this system* di PowerShell, jalankan perintah berikut sekali:
> `Set-ExecutionPolicy -ExecutionPolicy RemoteSigned -Scope CurrentUser`

### 3. Pasang Dependensi Python
Pasang seluruh pustaka yang tercantum pada `requirements.txt`:
```powershell
pip install -r requirements.txt
```

---

## Cara Menjalankan Aplikasi

Aplikasi dijalankan melalui berkas [main.py](main.py) dengan beberapa opsi mode:

### Opsi A: Mode Desktop GUI (Bawaan / Rekomendasi)
Menjalankan backend FastAPI sekaligus membuka jendela desktop mandiri berbasis `pywebview`:
```powershell
python main.py
```

### Opsi B: Mode Web Browser (`--no-window`)
Menjalankan backend FastAPI tanpa jendela desktop. Sangat berguna untuk pengujian, proses debugging inspect element devtools, atau jika webcam pada webview mengalami kendala:
```powershell
python main.py --no-window
```
Setelah perintah dijalankan, buka peramban web dan akses alamat:
**http://127.0.0.1:8000**

---

## Konfigurasi Variabel Lingkungan (Environment Variables)

Aplikasi mendukung konfigurasi melalui environment variables:

| Variabel | Bawaan | Deskripsi |
| :--- | :--- | :--- |
| `AEGIS_PORT` | `8000` | Port HTTP lokal untuk layanan FastAPI. |
| `AEGIS_TEST_MODE` | `0` | Nilai `1` mengaktifkan tombol unggah foto wajah pengganti kamera fisik (cocok untuk demo tanpa webcam). |
| `AEGIS_STORAGE_DIR`| `./storage` | Lokasi folder penyimpanan database, blockchain, wajah, dan berkas lampiran. |

### Contoh Menjalankan dengan Pengaturan Khusus:

**Menjalankan dengan Test Mode (Unggah Foto Pengganti Webcam):**
```powershell
$env:AEGIS_TEST_MODE="1"; python main.py
```

**Menjalankan pada Port Khusus (misal Port 8080):**
```powershell
$env:AEGIS_PORT="8080"; python main.py --no-window
```

---

## Alur Penggunaan Pertama Kali (Setup & Demo)

1. **Inisialisasi USB Dongle:**
   * Tancapkan USB Flashdisk ke komputer.
   * Jalankan aplikasi. Pada layar awal *Hardware Security Dongle Required*, pilih menu inisialisasi flashdisk untuk membuat berkas `dongle.key`.
   * Pendaftaran tanpa login hanya tersedia saat komputer belum punya dongle dan belum punya staf. Setelah itu, komputer hanya menerima dongle tersebut. Kalau dongle hilang, gunakan menu **Ganti dongle** dengan username, PIN, dan wajah.
2. **Pendaftaran Akun Staf Pertama:**
   * Masukkan NIP/Username dan PIN/Kata Sandi.
   * Lakukan pengambilan sampel wajah via webcam (atau unggah foto jika `AEGIS_TEST_MODE=1`).
3. **Login dan Masuk Dashboard:**
   * Lakukan autentikasi kredensial dan pemindaian wajah.
   * Setelah lolos, dashboard brankas internal instansi siap digunakan.
4. **Pencabutan Dongle:**
   * Jika USB Flashdisk dicabut dari port, aplikasi akan otomatis mendeteksi dan mengunci antarmuka dalam 3 detik untuk melindungi kerahasiaan data.

---

## Menjalankan Pengujian Otomatis (Unit Tests)

Proyek ini dilengkapi rangkaian pengujian unit otomatis untuk memvalidasi implementasi kriptografi dan sistem:

```powershell
# Uji coba seluruh suite kriptografi (Vigenere, RC4, AES-128, Stegano LSB, Blockchain)
python -m unittest tests/test_crypto_suite.py

# Uji coba fungsionalitas sistem (Database encryption, Dongle, Biometrik)
python -m unittest tests/test_system_suite.py

# Uji coba seluruh endpoint API FastAPI
python -m unittest tests/test_api_suite.py

# Menjalankan seluruh pengujian sekaligus
python -m unittest discover tests
```

---

## Struktur Direktori

```text
aegis-vault/
├── main.py                     # Entry point aplikasi (FastAPI + pywebview)
├── requirements.txt            # Daftar dependensi pustaka Python
├── README.md                   # Panduan instalasi dan penggunaan
├── DESIGN.md                   # Pedoman desain Institutional Light Mode
├── backend/                    # Modul inti kriptografi dan sistem
│   ├── config.py               # Konfigurasi path dan konstanta
│   ├── crypto_engine.py        # Super enkripsi teks, AES-128, RC4, KDF, Hash
│   ├── stego_engine.py         # Steganografi LSB citra PNG 24-bit
│   ├── blockchain_ledger.py    # Ledger blockchain lokal dan sertifikat digital
│   ├── database.py             # SQLite manager dan field-level encryption
│   ├── dongle_guard.py         # Deteksi nomor seri hardware USB dan dongle.key
│   └── biometric_auth.py       # Pendaftaran dan verifikasi wajah OpenCV
├── frontend/                   # Antarmuka desktop (Light Mode)
│   ├── index.html              # Struktur UI dokumen instansi
│   ├── app.js                  # Logika interaksi frontend dan pemanggilan API
│   └── assets/                 # Berkas CSS terkompilasi dan font lokal
├── storage/                    # Direktori penyimpanan data lokal otomatis
│   ├── aegis_vault.db          # Database SQLite terenkripsi
│   ├── blockchain.json         # Rantai blok lokal
│   ├── faces/                  # Data matriks fitur wajah staf (.npy)
│   └── attachments/            # Berkas lampiran terenkripsi RC4
├── tests/                      # Unit test otomatis
│   ├── test_crypto_suite.py
│   ├── test_system_suite.py
│   └── test_api_suite.py
└── docs/                       # Dokumen spesifikasi dan PRD
    ├── PRD.md
    ├── TECHNICAL_SPEC.md
    └── REPO_STRUCTURE_AND_SDD_GUIDE.md
```

