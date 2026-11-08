# Technical Specification Document: AegisVault
Dokumen ini adalah acuan teknis tunggal (*Single Source of Truth*) untuk penulisan kode mesin kriptografi, struktur basis data, protokol steganografi, struktur rantai blok, dan endpoint API lokal.

---

## 1. Lingkungan Eksekusi & Daftar Pustaka (`requirements.txt`)

Aplikasi berjalan di atas Python 3.11+ dengan pustaka standar dan pihak ketiga yang stabil di Windows tanpa memerlukan kompilasi C++ yang rumit (dilarang menggunakan `dlib`):

```text
fastapi>=0.110.0
uvicorn>=0.29.0
pywebview>=5.0.0
pycryptodome>=3.20.0
opencv-python>=4.9.0.80
numpy>=1.26.0
Pillow>=10.3.0
psutil>=5.9.8
python-multipart>=0.0.9
pydantic>=2.7.0
```
*(Catatan: Jika berjalan di Windows, modul `ctypes` / `subprocess` `wmic` bawaan Python digunakan bersama `psutil` untuk membaca Volume Serial Number USB).*

---

## 2. Manajemen & Penurunan Kunci (Key Derivation Architecture)

Untuk mencegah kelemahan penggunaan kunci yang sama secara berulang, sistem menggunakan mekanisme penurunan kunci terstruktur berbasis **PBKDF2-HMAC-SHA256** (`hashlib.pbkdf2_hmac`):

1. **Master Key Pengguna (Penyimpanan Lokal):**
   Saat staf login menggunakan `PasswordMaster` (atau ketika mengenkripsi data brankas), sistem menurunkan kunci utama 32-byte (256-bit) menggunakan `user_salt` (16 byte):
   $$\text{DerivedMaterial} = \text{PBKDF2\_HMAC\_SHA256}(\text{PasswordMaster}, \text{Salt}, \text{iterations}=100000, \text{dklen}=32)$$
   * **Kunci Extended Vigenère ($K_1$):** Diambil dari 16 byte pertama $\text{DerivedMaterial}[0:16]$.
   * **Kunci AES-128 ($K_2$):** Diambil dari 16 byte kedua $\text{DerivedMaterial}[16:32]$.
2. **Kunci Pengiriman Antar-Staf (Shared Passphrase pada File `.vault`):**
   Saat staf mengekspor dokumen untuk staf lain menggunakan `SharedPassphrase`, sistem membangkitkan `export_salt` acak 16-byte dan menurunkan pasangan kunci ($K_1, K_2$) dengan rumus PBKDF2 yang sama. `export_salt` disertakan di dalam metadata file `.vault`.

---

## 3. Spesifikasi Detail 7 Modul Keamanan & Kriptografi

### 3.1 Modul 1: USB Hardware Dongle Gatekeeper (`backend/dongle_guard.py`)
1. **Deteksi Drive USB:** Menggunakan `psutil.disk_partitions(all=False)` untuk mendeteksi partisi dengan opsi `'removable'` (atau mencari drive yang memiliki file `dongle.key`).
2. **Pembacaan Identitas Perangkat Keras:** Mengambil *Volume Serial Number* dari drive USB (melalui `ctypes.windll.kernel32.GetVolumeInformationW` di Windows, atau *fallback* ID partisi pada OS lain).
3. **Struktur File `dongle.key`:** Berada di *root directory* USB Flashdisk (misal `E:\dongle.key`), berisi JSON:
   ```json
   {
     "dongle_id": "AEGIS-DONGLE-01",
     "volume_serial": "A8F4-9902",
     "issued_at": "2026-11-08T09:00:00Z",
     "signature": "<SHA256(dongle_id + ':' + volume_serial + ':' + SYSTEM_SECRET_PEPPER)>"
   }
   ```
4. **Validasi:** Dongle dinyatakan valid jika file `dongle.key` ditemukan pada drive yang terpasang DAN perhitungan ulang `signature` cocok dengan *Volume Serial Number* perangkat keras fisik tempat file itu berada (sehingga file `dongle.key` tidak akan berfungsi jika sekadar di-*copy-paste* ke folder harddisk lokal atau flashdisk lain yang berbeda nomor serinya).

### 3.2 Modul 2: Biometrik Adaptif & Hashing Kredensial (`backend/biometric_auth.py` & `crypto_engine.py`)

#### A. Hashing Login (SHA-256 + Dynamic Salt)
Saat staf mendaftar, sistem membangkitkan `salt` acak berukuran 16 byte (`os.urandom(16)`), lalu menghitung:
$$\text{PasswordHash} = \text{SHA256}(\text{Salt} \parallel \text{UTF8}(\text{Password}))$$
Nilai `salt` (dalam hex) dan `PasswordHash` (dalam hex) disimpan ke tabel `users`.

#### B. Deteksi Sensor Fingerprint & Face Recognition OpenCV
1. **Deteksi Kapabilitas Fingerprint PC:** Mengecek ketersediaan perangkat *Biometric* pada OS (misal melalui query status perangkat biometrik Windows). Jika tidak ditemukan perangkat keras sensor sidik jari yang siap digunakan, fungsi mengembalikan `{"fingerprint_available": False, "active_mode": "FACE_RECOGNITION"}`.
2. **Pendaftaran & Pencocokan Wajah (OpenCV):**
   * Menggunakan `cv2.CascadeClassifier(cv2.data.haarcascades + 'haarcascade_frontalface_default.xml')` untuk mendeteksi area wajah dari *frame* gambar webcam.
   * Area wajah yang terdeteksi di-*crop*, diubah ke *grayscale*, di-*resize* ke ukuran standar $128 \times 128$ piksel, dan dinormalisasi dengan `cv2.equalizeHist()`.
   * Saat registrasi, matriks wajah disimpan sebagai file terenkripsi/biner di `storage/faces/{username}.npy`.
   * Saat login, sistem membandingkan wajah baru dengan wajah terdaftar menggunakan kombinasi **Normalized Cross-Correlation (`cv2.matchTemplate`)** dan **Histogram Comparison (`cv2.compareHist`)**. Jika skor kemiripan $\ge 0.72$, verifikasi biometrik dinyatakan berhasil.

### 3.3 Modul 3: Super Enkripsi Teks Memo (`backend/crypto_engine.py`)
Menggabungkan algoritma klasik **Extended Vigenère Cipher (256 ASCII)** dan algoritma modern **AES-128 Mode CBC**.

#### Tahap 1: Extended Vigenère Cipher (Byte-Level)
Beroperasi langsung pada barisan byte UTF-8 dari plainteks $P$ dengan panjang kunci $m = \text{len}(K_1)$:
* **Rumus Enkripsi Lapis Pertama:**
  $$C_1[i] = (P[i] + K_1[i \bmod m]) \bmod 256$$
* **Rumus Dekripsi Lapis Pertama:**
  $$P[i] = (C_1[i] - K_1[i \bmod m]) \bmod 256$$

*(Wajib diimplementasikan dengan perulangan byte secara eksplisit di dalam kode Python tanpa library instan).*

#### Tahap 2: AES-128 Mode CBC dengan PKCS#7 Padding
Hasil byte $C_1$ dari Extended Vigenère dienkripsi kembali menggunakan AES-128:
1. Bangkitkan *Initialization Vector* ($\text{IV}$) acak sepanjang 16 byte (`os.urandom(16)`).
2. Terapkan **PKCS#7 Padding** pada $C_1$ sehingga panjang byte menjadi kelipatan 16 byte (128 bit).
3. Enkripsi menggunakan `AES.new(K_2, AES.MODE_CBC, iv)` dari `Crypto.Cipher`.
4. Gabungkan $\text{IV}$ di depan ciphertext akhir dan ubah ke Base64:
   $$\text{Ciphertext}_{\text{final}} = \text{Base64}(\text{IV} \parallel \text{AES\_CBC\_Encrypt}(K_2, \text{IV}, \text{Pad}(C_1)))$$

Proses dekripsi melakukan urutan kebalikannya: Decode Base64 $\rightarrow$ Pisahkan 16 byte pertama sebagai $\text{IV}$ $\rightarrow$ Dekripsi AES-128-CBC $\rightarrow$ Hapus PKCS#7 Padding untuk memperoleh $C_1$ $\rightarrow$ Dekripsi Extended Vigenère untuk memperoleh plainteks $P$.

### 3.4 Modul 4: Enkripsi Berkas Lampiran dengan RC4 (`backend/crypto_engine.py`)
Sesuai kriteria proyek akhir, enkripsi berkas wajib menggunakan algoritma yang berbeda dari enkripsi teks, yaitu **RC4 (ARCFOUR Stream Cipher)** yang ditulis *from-scratch*:

1. **Pencegahan Penggunaan Ulang Keystream (Per-File Nonce):**
   Untuk setiap berkas yang dienkripsi, sistem membangkitkan `file_nonce` acak 16 byte. Kunci efektif RC4 ($U$) adalah gabungan kunci dasar dan nonce: $U = K_{\text{RC4}} \parallel \text{file\_nonce}$.
2. **Tahap Key-Scheduling Algorithm (KSA):**
   Inisialisasi larik $S = [0, 1, 2, \dots, 255]$. Lakukan permutasi untuk $i = 0 \dots 255$:
   $$j = (j + S[i] + U[i \bmod \text{len}(U)]) \bmod 256$$
   Tukar nilai $S[i]$ dan $S[j]$.
3. **Tahap Pseudo-Random Generation Algorithm (PRGA) & Operasi XOR:**
   Untuk setiap byte ke-$k$ dari berkas plainteks $B[k]$:
   $$i = (i + 1) \bmod 256$$
   $$j = (j + S[i]) \bmod 256$$
   Tukar nilai $S[i]$ dan $S[j]$, lalu hitung indeks aliran kunci $t = (S[i] + S[j]) \bmod 256$ dan hasilkan byte terenkripsi:
   $$C_{\text{file}}[k] = B[k] \oplus S[t]$$
4. **Format Penyimpanan Berkas `.rc4`:**
   16 byte pertama berkas `.rc4` adalah `file_nonce`, diikuti oleh seluruh byte $C_{\text{file}}$.

### 3.5 Modul 5: Skema Database SQLite & Enkripsi Basis Data (`backend/database.py`)
Basis data disimpan di `storage/aegis_vault.db`.

#### Skema Tabel SQLite:
```sql
CREATE TABLE IF NOT EXISTS users (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    username TEXT UNIQUE NOT NULL,
    full_name_enc TEXT NOT NULL,       -- Dienkripsi (Field-Level)
    role_enc TEXT NOT NULL,            -- Dienkripsi (Field-Level)
    password_hash TEXT NOT NULL,       -- SHA-256 Hex Digest
    password_salt TEXT NOT NULL,       -- 16-byte Hex Salt
    face_model_path TEXT NOT NULL,
    created_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS documents (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    doc_uuid TEXT UNIQUE NOT NULL,
    author_username TEXT NOT NULL,
    title_enc TEXT NOT NULL,           -- Dienkripsi (Field-Level RC4/AES Base64)
    category_enc TEXT NOT NULL,        -- Dienkripsi (Field-Level RC4/AES Base64)
    content_super_enc TEXT NOT NULL,   -- Dienkripsi dengan Super Enkripsi (Extended Vigenere + AES-128-CBC)
    plaintext_sha256 TEXT NOT NULL,    -- Hash SHA-256 dari isi asli untuk verifikasi
    block_index INTEGER NOT NULL,      -- Referensi nomor blok pada Blockchain
    block_hash TEXT NOT NULL,          -- Hash blok sertifikat pada Blockchain
    created_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS attachments (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    att_uuid TEXT UNIQUE NOT NULL,
    owner_username TEXT NOT NULL,
    original_filename_enc TEXT NOT NULL, -- Dienkripsi (Field-Level)
    mime_type_enc TEXT NOT NULL,         -- Dienkripsi (Field-Level)
    encrypted_filepath TEXT NOT NULL,    -- Path ke file .rc4
    file_size_bytes INTEGER NOT NULL,
    original_sha256 TEXT NOT NULL,       -- Hash SHA-256 file asli sebelum dienkripsi
    block_index INTEGER NOT NULL,
    block_hash TEXT NOT NULL,
    created_at TEXT NOT NULL
);
```

#### Mekanisme Proteksi Basis Data:
1. **Field-Level Encryption:** Seluruh kolom berakhiran `_enc` (`full_name_enc`, `title_enc`, `category_enc`, `original_filename_enc`) dienkripsi menggunakan kunci sistem aplikasi sebelum disimpan ke SQLite.
2. **Database File Integrity Checksum:** Setiap kali aplikasi selesai melakukan transaksi tulis (`INSERT`/`DELETE`), aplikasi menghitung hash SHA-256 dari keseluruhan file biner `storage/aegis_vault.db` dan menyimpannya ke `storage/db_checksum.sha256`. Saat aplikasi membaca data, nilai checksum diperiksa untuk mendeteksi apakah file `.db` telah dimodifikasi dari luar aplikasi.

### 3.6 Modul 6: Steganografi Citra Digital LSB (`backend/stego_engine.py`)
Menggunakan metode **Least Significant Bit (LSB)** pada citra RGB 24-bit (3 byte per piksel: $R, G, B$) dengan protokol *Header* eksplisit agar proses ekstraksi presisi.

1. **Kapasitas Maksimal Payload (dalam Byte):**
   Untuk citra berukuran lebar $W$ dan tinggi $H$ piksel, dikurangi 4 byte (32 bit) yang dicadangkan untuk menyimpan *Header* panjang pesan:
   $$\text{MaxPayloadBytes} = \left\lfloor \frac{W \times H \times 3}{8} \right\rfloor - 4$$
2. **Struktur Bit yang Disisipkan (Framing Protocol):**
   * Jika pengguna mengisi `Passphrase` opsional pada menu steganografi, pesan teks dienkripsi terlebih dahulu dengan Super Enkripsi dan diberi awalan penanda `"ENC:"`. Jika tanpa passphrase, diberi awalan `"RAW:"`.
   * Ubah string payload menjadi barisan byte UTF-8 dengan panjang $L$ byte.
   * Bentuk *Header* 4-byte (32-bit unsigned integer, *Big-Endian*): $\text{Header} = L.\text{to\_bytes}(4, \text{'big'})$.
   * Total byte yang disisipkan adalah $\text{Stream} = \text{Header} \parallel \text{PayloadBytes}$ (total $(4 + L) \times 8$ bit).
3. **Rumus Substitusi Bit LSB:**
   Untuk setiap komponen warna ke-$k$ ($\text{ChannelByte}_k \in [0, 255]$) dan bit pesan ke-$k$ ($b_k \in \{0, 1\}$):
   $$\text{ChannelByte}'_k = (\text{ChannelByte}_k \land 254) \lor b_k$$
4. **Prosedur Ekstraksi:**
   * Baca 32 piksel kanal warna pertama (32 bit pertama) dari gambar `.png`, susun menjadi integer 32-bit Big-Endian untuk mendapatkan nilai panjang $L$.
   * Validasi bahwa $0 < L \le \text{MaxPayloadBytes}$.
   * Baca tepat $L \times 8$ bit berikutnya dari LSB piksel gambar, susun kembali menjadi byte array, dan kembalikan pesan teksnya (atau dekripsi jika diawali `"ENC:"`).

### 3.7 Modul 7: Sertifikat Keaslian Blockchain & Paket `.vault` (`backend/blockchain_ledger.py`)

#### A. Struktur Blok pada `storage/blockchain.json`
 setiap blok dalam rantai memiliki struktur berikut:
```json
{
  "index": 1,
  "timestamp": "2026-11-08T10:30:00Z",
  "doc_uuid": "DOC-9012-AB",
  "author": "staf_budi",
  "asset_type": "MEMO_TEXT",
  "payload_sha256": "e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855",
  "previous_hash": "0000000000000000000000000000000000000000000000000000000000000000",
  "nonce": 1842,
  "block_hash": "000a8f92c11d..."
}
```
* **Rumus Hash Blok & Proof-of-Work (PoW):**
  $$\text{BlockHash} = \text{SHA256}(\text{index} \parallel \text{timestamp} \parallel \text{doc\_uuid} \parallel \text{author} \parallel \text{payload\_sha256} \parallel \text{previous\_hash} \parallel \text{nonce})$$
  Proses *Proof-of-Work* menaikkan nilai `nonce` mulai dari $0, 1, 2, \dots$ hingga ditemukan $\text{BlockHash}$ yang diawali dengan `"000"`.

#### B. Struktur File Ekspor Antar-Staf (`.vault`)
Saat staf mengekspor memo untuk dikirim ke staf lain, aplikasi menghasilkan file JSON berekstensi `.vault`:
```json
{
  "vault_version": "1.0",
  "export_salt": "<16-byte-hex-salt>",
  "metadata": {
    "doc_uuid": "DOC-9012-AB",
    "author": "staf_budi",
    "title_plain": "Memo Anggaran Kuartal IV",
    "category_plain": "SANGAT RAHASIA",
    "created_at": "2026-11-08T10:30:00Z"
  },
  "encrypted_payload": "<Ciphertext Super Enkripsi menggunakan Shared Passphrase>",
  "blockchain_certificate": {
    "block_index": 1,
    "timestamp": "2026-11-08T10:30:00Z",
    "doc_uuid": "DOC-9012-AB",
    "author": "staf_budi",
    "payload_sha256": "<SHA256 dari plainteks asli>",
    "previous_hash": "0000...",
    "nonce": 1842,
    "block_hash": "000a8f92c11d..."
  }
}
```
* **Algoritma Verifikasi Saat Impor `.vault` oleh Staf Penerima:**
  1. Turunkan kunci ($K_1, K_2$) dari `SharedPassphrase` + `export_salt`.
  2. Dekripsi `encrypted_payload` menggunakan Super Dekripsi (AES-128-CBC $\rightarrow$ Extended Vigenère) untuk mendapatkan `decrypted_plaintext`.
  3. Hitung $H_{\text{hitung}} = \text{SHA256}(\text{decrypted\_plaintext})$.
  4. Hitung ulang hash blok dari objek `blockchain_certificate` dan pastikan tiga syarat terpenuhi:
     * $H_{\text{hitung}} == \text{blockchain\_certificate.payload\_sha256}$ (Isi pesan tidak pernah diubah).
     * Hash ulang blok cocok dengan `block_hash` dan diawali `"000"` (Sertifikat blok valid).
     * Jika blok dengan `doc_uuid` tersebut ada di rantai blok lokal instansi, pastikan `block_hash`-nya identik dengan catatan di `blockchain.json`.

---

## 4. Kontrak REST API Lokal (`main.py` — FastAPI)

| Method | Endpoint | Deskripsi Fungsi |
| :--- | :--- | :--- |
| `GET` | `/api/system/status` | Mengecek status USB Dongle, kapabilitas sensor Fingerprint/Webcam, status integritas Checksum DB, dan sesi user aktif. |
| `POST` | `/api/dongle/enroll` | Mendaftarkan USB Flashdisk yang sedang tertancap dan membuat file `dongle.key` di dalamnya. |
| `POST` | `/api/auth/register` | Mendaftarkan akun staf baru (simpan hash PIN SHA-256 + matriks wajah dari base64 webcam). |
| `POST` | `/api/auth/login` | Memverifikasi PIN SHA-256 dan kecocokan biometrik wajah staf. |
| `POST` | `/api/auth/logout` | Mengakhiri sesi staf yang sedang login. |
| `GET` | `/api/documents` | Mengambil daftar memo internal milik instansi/staf dan mendekripsi *field* judulnya. |
| `POST` | `/api/documents` | Menyimpan memo baru dengan Super Enkripsi (Extended Vigenère + AES-128-CBC) & mencetak blok sertifikat di Blockchain. |
| `POST` | `/api/documents/{id}/export` | Mengekspor memo menjadi file paket `.vault` terenkripsi menggunakan *Shared Passphrase* dilengkapi Sertifikat Blockchain. |
| `POST` | `/api/documents/import-verify` | Mengimpor file `.vault`, mendekripsi isinya dengan *Shared Passphrase*, dan memverifikasi keaslian Sertifikat Blockchain. |
| `GET` | `/api/attachments` | Mengambil daftar berkas di dalam Brankas File (RC4 Vault). |
| `POST` | `/api/attachments/upload` | Mengunggah berkas, mengenkripsinya dengan RC4 Stream Cipher, dan mencatat sertifikatnya ke Blockchain. |
| `GET` | `/api/attachments/{id}/download` | Mendekripsi berkas `.rc4` dan mengunduhnya kembali ke format berkas asli. |
| `POST` | `/api/stego/embed` | Menerima file gambar, pesan rahasia, dan passphrase opsional, lalu mengembalikan file gambar `.png` hasil Steganografi LSB. |
| `POST` | `/api/stego/extract` | Menerima file gambar `.png` steganografi dan mengekstrak pesan rahasia di dalamnya. |
| `GET` | `/api/blockchain/audit` | Mengambil seluruh rantai blok serta hasil audit validitas tiap blok dan *Database Checksum*. |