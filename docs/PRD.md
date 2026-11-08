# Product Requirement Document (PRD): AegisVault Desktop

**Nama Produk:** AegisVault (Sistem Brankas Dokumen & Pengiriman Rahasia Internal Instansi)  
**Platform:** Aplikasi Desktop Mandiri (Python FastAPI + `pywebview` Desktop Window)  
**Tema Antarmuka:** Institutional Archival Light Theme (Tema Terang Berkontras Tinggi)  
**Target Pengguna:** Staf Instansi / Organisasi yang menangani dokumen rahasia, memo internal, dan pertukaran berkas sensitif.  

---

## 1. Latar Belakang & Tujuan Produk (Product Overview)

Instansi pemerintah maupun divisi riset perusahaan membutuhkan sistem penyimpanan dokumen internal serta pertukaran informasi rahasia antar-staf yang terlindungi dari kebocoran data, pencurian basis data fisik, hingga pemalsuan isi dokumen. 

**AegisVault** adalah aplikasi brankas dokumen desktop multi-pengguna (*multi-staff*) yang mengintegrasikan pengamanan perangkat keras (USB Hardware Dongle), verifikasi biometrik adaptif, enkripsi berlapis untuk teks dan berkas, penyembunyian pesan melalui citra digital (Steganografi), serta buku besar rantai blok lokal (Blockchain) sebagai penerbit **Sertifikat Keaslian Dokumen (e-Seal Proof of Existence)**.

---

## 2. Pemetaan Kebutuhan Akademik (7 Kriteria Utama)

Produk ini dirancang untuk memenuhi seluruh kriteria proyek akhir mata kuliah Kriptografi secara fungsional dan terintegrasi:

| Kode | Kriteria Proyek Akhir | Implementasi Fitur pada AegisVault | Algoritma / Teknologi |
| :--- | :--- | :--- | :--- |
| **KR-01** | Aplikasi memiliki fungsi login biometrik dan hanya dapat dihidupkan dengan bantuan dongle | Layar *Hardware Gatekeeper* yang memblokir aplikasi hingga USB Flashdisk terdaftar ditancapkan, diikuti verifikasi Biometrik adaptif (cek sensor Fingerprint PC $\rightarrow$ *fallback* otomatis ke Face Recognition via Webcam). | Deteksi Hardware USB Serial + File `dongle.key` (SHA-256) + OpenCV Face Recognition |
| **KR-02** | Login aplikasi menggunakan algoritma kriptografi | Kredensial PIN/Password staf tidak disimpan dalam plainteks melainkan di-hash dengan *Dynamic Salt*. | SHA-256 + 128-bit Random Salt & PBKDF2-HMAC-SHA256 |
| **KR-03** | Pesan berupa teks dienkripsi menggunakan Super Enkripsi (Klasik + Modern) | Fitur **Memo Internal Rahasia**: teks memo dienkripsi dua tahap secara berurutan sebelum disimpan atau dibagikan. | Extended Vigenère Cipher (256 ASCII) + AES-128 Mode CBC |
| **KR-04** | Pesan File dienkripsi menggunakan kriptografi yang berbeda dari teks | Fitur **Brankas Berkas Lampiran (File Vault)**: mengenkripsi berkas dokumen instansi (`.pdf`, `.docx`, `.mp3`, `.zip`). | RC4 (ARCFOUR) Stream Cipher dengan *per-file Nonce* |
| **KR-05** | Pesan penting dienkripsi pada basis data yang digunakan | Seluruh *field* sensitif pada database SQLite disimpan dalam bentuk *ciphertext* disertai penjagaan *Checksum* integritas file database. | Field-Level Encryption (AES-128 / RC4) + SHA-256 DB Checksum |
| **KR-06** | Pesan Gambar diamankan menggunakan konsep Steganografi | Fitur **Steganography Covert Studio**: menyisipkan pesan/instruksi rahasia ke dalam citra `.PNG` untuk diekspor dan diekstrak oleh staf penerima. | Least Significant Bit (LSB) 24-bit PNG + 32-bit Length Header |
| **KR-07** | Aset penting diamankan menggunakan teknologi Blockchain sederhana | Fitur **Sertifikat Keaslian Dokumen (e-Seal Blockchain)**: setiap penerbitan dokumen mencetak blok baru di rantai blok lokal dan menyertakan sertifikat digital saat dokumen diekspor ke staf lain. | SHA-256 Hash Chain + Proof-of-Work (PoW) + JSON Certificate Verification |

---

## 3. Persona Pengguna & Konsep Multi-User

Aplikasi mendukung banyak akun staf (*Multi-User*) dalam satu instalasi maupun pertukaran lintas perangkat melalui mekanisme ekspor/impor file:
1. **Staf Pengirim / Pembuat Dokumen (Contoh: Staf Budi):** Memiliki akun staf dan wajah terdaftar, membuat memo rahasia atau mengunggah berkas penting, menyegelnya ke dalam Blockchain, lalu mengekspor paket dokumen terenkripsi (`.vault`) atau gambar Steganografi (`.png`) menggunakan *Passphrase Rahasia Bersama*.
2. **Staf Penerima (Contoh: Staf Siti):** Login dengan akun dan biometriknya sendiri, mengimpor file `.vault` atau gambar `.png` dari Staf Budi, memasukkan *Passphrase Rahasia Bersama* untuk mendekripsi isi pesan, serta memverifikasi keaslian Sertifikat Blockchain yang menempel pada dokumen tersebut.
3. **Penguji / Auditor Keamanan:** Memeriksa isi tabel mentah database SQLite, menguji pencabutan USB Dongle, serta menguji manipulasi isi file `.vault` atau database untuk membuktikan sistem deteksi pemalsuan Blockchain bekerja.

---

## 4. Alur Pengguna Utama (User Flows)

### 4.1 Alur Inisialisasi & Validasi USB Dongle (Gatekeeper)
1. Pengguna membuka aplikasi AegisVault.
2. Sistem langsung memindai seluruh port penyimpanan USB yang terpasang.
3. **Kondisi A (USB Dongle Valid Terpasang):** Sistem menemukan USB dengan nomor seri perangkat keras yang cocok dengan tanda tangan kriptografi di dalam file `dongle.key` pada USB tersebut. Layar Login Staf dibuka.
4. **Kondisi B (USB Dongle Tidak Terpasang):** Layar terkunci pada halaman *"Hardware Security Dongle Required"*. Tombol login dinonaktifkan. Tersedia menu *"Inisialisasi USB Flashdisk Sebagai Dongle Baru"* (untuk keperluan *setup* pertama kali saat pengujian/demo) yang akan menulis file `dongle.key` ke flashdisk yang sedang ditancapkan.
5. Jika USB Dongle dicabut saat staf sedang berada di dalam dashboard, aplikasi otomatis mengunci layar kembali dalam waktu maksimal 3 detik.

### 4.2 Alur Registrasi & Login Staf (Kriptografi + Biometrik Adaptif)
1. **Pengecekan Kapabilitas Perangkat Keras Biometrik:** Saat layar autentikasi dimuat, sistem memeriksa ketersediaan sensor sidik jari (Windows Biometric Framework / Windows Hello). Jika PC tidak memiliki sensor sidik jari, UI menampilkan indikator *"Sensor Fingerprint Tidak Tersedia: Mode Biometrik Face Recognition Aktif"*.
2. **Registrasi Staf Baru:** Staf menginput NIP/Username, Nama Lengkap, PIN/Password Master, dan mengambil foto wajah melalui kamera webcam pada antarmuka aplikasi. Sistem menyimpan hash password (`SHA-256 + Salt`) dan fitur matriks wajah staf.
3. **Login Staf:** Staf memilih/mengetik Username, memasukkan PIN/Password, dan melakukan pemindaian wajah melalui kamera. Hanya jika **PIN cocok DAN Biometrik cocok**, staf diizinkan masuk ke Dashboard.

### 4.3 Alur Manajemen Memo Teks (Super Enkripsi) & Sertifikat Blockchain
1. Staf membuat dokumen memo baru (Judul, Kategori Klasifikasi, dan Isi Memo).
2. Saat tombol **"Simpan & Segel ke Blockchain"** diklik:
   * Isi memo dienkripsi lapis pertama menggunakan **Extended Vigenère Cipher**, lalu hasilnya dienkripsi lapis kedua menggunakan **AES-128-CBC**.
   * Judul dan kategori dienkripsi pada level *field* sebelum disimpan ke database SQLite.
   * Sistem menghitung hash dokumen dan mencetak **Blok Baru** pada rantai blok lokal (`blockchain.json`) melalui proses *Proof-of-Work* sebagai bukti waktu pembuatan dan keaslian dokumen.

### 4.4 Alur Brankas Berkas Lampiran (RC4 File Vault)
1. Staf memilih berkas dari komputer (misal `.pdf`, `.txt`, `.jpg`, `.mp3`) untuk disimpan ke brankas instansi.
2. Sistem mengenkripsi biner berkas menggunakan algoritma **RC4 Stream Cipher** dan menyimpannya sebagai berkas terenkripsi `.rc4` di dalam folder `storage/attachments/`.
3. Saat staf ingin mengunduh/membuka berkas tersebut, sistem mendekripsi aliran byte menggunakan RC4 dan mengembalikan berkas ke format aslinya.

### 4.5 Alur Berbagi Dokumen Antar-Staf & Verifikasi Sertifikat Blockchain (`.vault`)
1. **Ekspor (Staf Pengirim):** Pada salah satu memo atau berkas, staf mengklik **"Bagikan / Ekspor Paket (.vault)"** dan mengetikkan **Passphrase Rahasia Bersama** (kunci pengiriman).
2. Sistem menghasilkan satu file `.vault` yang dapat diunduh. Di dalamnya terdapat payload dokumen yang telah dienkripsi menggunakan Passphrase tersebut, ditambah **Sertifikat Blockchain** (berisi ID Blok, Timestamp, Pembuat, Hash Asli Dokumen, dan Bukti Hash Blok).
3. **Impor & Verifikasi (Staf Penerima):** Staf penerima login ke akunnya, membuka menu **"Impor & Verifikasi Paket Masuk"**, mengunggah file `.vault`, dan mengetikkan **Passphrase Rahasia Bersama**.
4. Sistem mendekripsi isi pesan dan mencocokkan hash dokumen hasil dekripsi dengan **Sertifikat Blockchain**:
   * Jika cocok: Tampilkan isi dokumen beserta lencana hijau **"SERTIFIKAT BLOCKCHAIN VALID: DOKUMEN ASLI & BELUM DIMODIFIKASI"**.
   * Jika file `.vault` sempat diedit secara ilegal di perjalanan: Tampilkan peringatan merah **"PERINGATAN: INTEGRITAS DOKUMEN RUSAK / TERDETEKSI MANIPULASI (TAMPERED)!"**.

### 4.6 Alur Steganografi Gambar (`.PNG` Covert Dispatch)
1. **Penyisipan (Embed):** Staf mengunggah gambar sampul berformat `.png` atau `.bmp`. Sistem menghitung dan menampilkan kapasitas maksimal karakter yang dapat ditampung gambar tersebut.
2. Staf mengetikkan pesan rahasia (serta Passphrase opsional untuk mengenkripsi pesan sebelum disisipkan).
3. Sistem menyisipkan bit pesan ke dalam bit paling tidak signifikan (*Least Significant Bit* / LSB) piksel RGB gambar, lalu staf mengekspor gambar hasil steganografi (`stego_image.png`) untuk dikirimkan ke staf lain.
4. **Ekstraksi (Extract):** Staf penerima membuka tab **"Ekstrak Steganografi"**, mengunggah file `stego_image.png` (dan memasukkan Passphrase jika pesan dienkripsi), lalu sistem mengekstrak dan menampilkan pesan rahasia secara utuh.

---

## 5. Acceptance Criteria (Skenario Pengujian Keberhasilan)

Setiap fitur dinyatakan selesai (*Done*) jika lulus skenario uji berikut:

* **AC-01 (USB Dongle Gatekeeper):**
  * *Given* aplikasi dijalankan tanpa USB Flashdisk yang memiliki file `dongle.key` valid, *When* pengguna mencoba mengakses halaman login, *Then* sistem memblokir akses dan menampilkan layar penguncian perangkat keras.
* **AC-02 (Biometrik Adaptif & Login SHA-256):**
  * *Given* USB Dongle terpasang dan PC tidak memiliki sensor sidik jari, *When* pengguna membuka layar login, *Then* sistem otomatis mengaktifkan kamera Face Recognition dan memvalidasi kecocokan wajah beserta hash PIN SHA-256.
* **AC-03 (Super Enkripsi Teks & Enkripsi Database):**
  * *Given* staf menyimpan memo bertuliskan `"Rapat Anggaran Rahasia 2026!"`, *When* file `aegis_vault.db` dibuka paksa menggunakan aplikasi pembuka SQLite eksternal, *Then* kolom judul dan isi memo hanya menampilkan string *ciphertext* Base64/Hex tanpa ada teks asli yang terbaca.
* **AC-04 (Enkripsi Berkas RC4):**
  * *Given* staf mengunggah file dokumen berukuran hingga $10\text{ MB}$, *When* proses enkripsi RC4 selesai, *Then* file tersimpan di folder `storage/attachments/` dalam keadaan terenkripsi (tidak bisa dibuka aplikasi PDF/Gambar biasa) dan ketika didekripsi di dalam aplikasi menghasilkan file yang identik 100% (hash SHA-256 file awal sama dengan file hasil dekripsi).
* **AC-05 (Steganografi LSB Imperceptible & Recovery):**
  * *Given* staf menyisipkan pesan sepanjang $500$ karakter ke dalam gambar PNG $512 \times 512$ piksel, *When* gambar diekspor dan diunggah kembali ke menu ekstraksi, *Then* gambar terlihat identik secara visual oleh mata manusia dan pesan yang diekstrak sama persis 100% dengan pesan awal tanpa karakter sampah di akhir kalimat.
* **AC-06 (Sertifikat Blockchain & Anti-Tampering):**
  * *Given* sebuah memo telah disegel ke Blockchain dan diekspor menjadi file `.vault`, *When* isi ciphertext atau metadata di dalam file `.vault` (atau di dalam tabel SQLite) diubah 1 byte saja menggunakan teks editor eksternal, *Then* fitur Verifikasi Blockchain akan langsung menampilkan status **INVALID / TAMPERED**.

---

## 6. Spesifikasi Antarmuka (UI/UX Scope - Institutional Light Theme)

Antarmuka dibangun dalam 1 halaman aplikasi responsif (*Single-Page Application*) dengan **Tema Terang (Institutional Archival Light Theme)** mengacu pada `DESIGN.md` dan `antislop.md`:
1. **Palet Warna & Kepatuhan `antislop.md`:**
   * Latar Belakang Utama: `#F8FAFC` (Warm Paper) dengan kartu dokumen putih `#FFFFFF` berbingkai `#CBD5E1`.
   * Teks Utama: `#0F172A` (kontras tinggi memenuhi WCAG AA R-25).
   * Aksen Utama: `#1E3A8A` (Institutional Navy), Hijau Verifikasi `#059669`, dan Merah Peringatan `#DC2626`.
   * Bebas dari karakter *em-dash* (R-02) dan wajib menyertakan *Empty State*, *Loading State*, serta *Error State* (R-27) di setiap tab.
2. **Top Status Bar:** Menampilkan indikator *real-time* status USB Dongle (`Connected` / `Disconnected`), Mode Biometrik Aktif, Nama Staf yang sedang login, dan tombol *Switch User / Logout*.
3. **Modal/Overlay Gatekeeper Dongle:** Tampil menutupi seluruh layar jika dongle belum terdeteksi, dilengkapi tombol *Inisialisasi USB Flashdisk Saat Ini Sebagai Dongle*.
4. **Halaman Auth (Login & Registrasi Staf):** Dilengkapi *live preview* kamera webcam untuk pengambilan dan pencocokan wajah.
5. **Sidebar Navigasi Utama (5 Menu):**
   * **Menu 1: Memo Internal (Super Encryption)** : Daftar memo, form tambah memo, komponen *Cryptographic Seal Stamp*, tombol lihat detail ciphertext (untuk keperluan demonstrasi ke dosen), dan tombol *Ekspor `.vault`*.
   * **Menu 2: Brankas Berkas (RC4 File Vault)** : Tabel berkas terenkripsi, tombol *Unggah & Enkripsi RC4*, serta tombol *Dekripsi & Unduh*.
   * **Menu 3: Kurir & Verifikasi Dokumen (`.vault` Sharing)** : Area unggah file `.vault` dari staf lain, input *Shared Passphrase*, tampilan isi dokumen yang didekripsi, dan kartu **Sertifikat Keaslian Blockchain**.
   * **Menu 4: Steganography Studio (`.PNG`)** : Panel kiri untuk *Sisipkan Pesan ke PNG* (lengkap dengan kalkulator kapasitas byte) dan panel kanan untuk *Ekstrak Pesan dari PNG*.
   * **Menu 5: Blockchain Explorer & DB Security Audit** : Visualisasi rantai blok (Genesis Block $\rightarrow$ Block $N$), tombol *Verifikasi Integritas Rantai Blok*, dan status *Database SHA-256 Checksum*.

---

## 7. Non-Functional Requirements (NFR) & Penanganan Kasus Batas (Edge Cases)

1. **Batas Ukuran Berkas RC4:** Maksimal ukuran berkas lampiran dibatasi hingga $20\text{ MB}$ per file agar enkripsi RC4 berbasis Python berjalan di bawah $3$ detik tanpa membekukan antarmuka.
2. **Tingkat Kesulitan Proof-of-Work (PoW) Blockchain:** *Difficulty target* ditetapkan pada $3$ angka nol di depan (`"000"`). Target ini cukup untuk mendemonstrasikan iterasi *mining* (`Nonce`) secara nyata ($100\text{ ms} - 800\text{ ms}$), namun tidak membuat aplikasi *not responding*.
3. **Validasi Format Gambar Steganografi:** Jika pengguna mengunggah file `.jpg`/`.jpeg` sebagai gambar sampul, sistem otomatis mengonversinya ke memori matriks RGB `.png` tak terkompresi (*lossless*) terlebih dahulu dan mengekspor hasilnya secara wajib dalam ekstensi `.png` agar bit LSB tidak rusak oleh kompresi JPEG.
4. **Fallback Kamera & Simulasi Dongle (Mode Pengujian):** Jika dijalankan pada PC tanpa webcam saat pengujian kode, sistem menyediakan opsi *Unggah Foto Wajah* sebagai pengganti tangkapan webcam langsung.