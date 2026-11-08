# Design Direction: AegisVault (Institutional Archival Light Theme)

Dokumen ini memenuhi syarat **R-37 (Design Direction Required)** dan **R-31 (Every Decision Must Have a Reason)** pada `antislop.md`. Letakkan file ini di direktori paling luar (*root folder*) proyek sejajar dengan `antislop.md`.

---

## 1. Design Read & Liveliness Dials

* **Design Read:** Reading this as a desktop institutional document vault and cryptographic verification studio for agency staff, in a Swiss Archival & High-Contrast Paper light style, dial **ENERGY 1 / RHYTHM 2 / MOTION 1**.
* **Dial Settings:**
  * **ENERGY: 1 (Calm & Authoritative)** : Aplikasi menangani dokumen rahasia instansi dan verifikasi sertifikat kriptografi, sehingga membutuhkan ketenangan visual setara sistem arsip perbankan atau pemerintahan tanpa dekorasi berlebihan.
  * **RHYTHM: 2 (Balanced Structural Variation)** : Mengombinasikan tata letak tabel arsip yang terstruktur pada brankas dokumen dengan tampilan terbagi dua panel (*split-pane inspector*) pada studio Steganografi dan verifikasi sertifikat Blockchain.
  * **MOTION: 1 (Functional Hover & State Transitions Only)** : Animasi dibatasi hanya pada indikator pemindaian biometrik/dongle dan umpan balik status enkripsi/verifikasi agar aplikasi terasa instan dan presisi.

---

## 2. Identitas Visual & Palet Warna (Light Mode Mutlak - R-21, R-25, R-29)

Aplikasi menggunakan **Tema Terang (Light Mode)** yang terinspirasi dari kertas dokumen resmi bersegel dan brankas arsip fisik. Dilarang menggunakan tema gelap (*dark mode default*).

1. **Background Primary (Warm Archival Paper):** `#F8FAFC` (Slate-50) untuk latar utama halaman dan `#F1F5F9` (Slate-100) untuk bilah navigasi samping (*sidebar*) serta pengelompokan panel.
   * *Alasan (R-31):* Memberikan kontras lembut yang tidak menyilaukan mata saat staf membaca memo panjang dibandingkan latar putih murni di seluruh layar.
2. **Surface / Card Background (Crisp Document White):** `#FFFFFF` dengan garis tepi tegas `1px solid #CBD5E1` (Slate-300).
   * *Alasan (R-31):* Memisahkan lembar kerja dokumen dan kartu sertifikat dari latar belakang secara struktural tanpa bergantung pada bayangan kabur (*overly soft shadows*).
3. **Typography & Ink Colors (WCAG AA High Contrast - R-25):**
   * Teks Utama (Judul & Isi Dokumen): `#0F172A` (Slate-900, rasio kontras $> 15:1$ di atas putih).
   * Teks Sekunder (Label Form & Metadata): `#334155` (Slate-700, rasio kontras $> 8:1$ di atas putih, menghindari teks abu-abu muda di atas latar abu-abu).
4. **Core Accent & Semantic Verification Colors (Maksimal 3 Warna Inti - R-29):**
   * **Primary Brand Accent (Institutional Navy):** `#1E3A8A` (Blue-900) dengan warna *hover* `#1D4ED8` (Blue-700) dan teks tombol putih `#FFFFFF` untuk aksi utama (Simpan & Segel, Ekspor `.vault`, Sisipkan Steganografi).
     * *Alasan (R-31):* Biru tua melambangkan otoritas dokumen resmi instansi dan memberikan kontras teks putih yang tajam.
   * **Authentic / Verified Seal (Archival Emerald):** Latar `#ECFDF5`, garis tepi `#059669`, teks `#065F46` khusus untuk status USB Dongle Terhubung dan Sertifikat Blockchain Valid.
     * *Alasan (R-31):* Memberikan sinyal visual instan bahwa integritas kriptografi dokumen terjamin 100%.
   * **Tampered / Security Alert (Wax Seal Crimson):** Latar `#FEF2F2`, garis tepi `#DC2626`, teks `#991B1B` khusus untuk peringatan manipulasi data (*Tampered*) atau USB Dongle Dicabut.
     * *Alasan (R-31):* Membedakan secara tegas kondisi kegagalan verifikasi kriptografi dari informasi biasa.

---

## 3. Tipografi & Hierarki (R-06)

* **UI & Document Body Font:** `Plus Jakarta Sans` atau `Inter` (sistem sans-serif bersih) untuk keterbacaan optimal pada form memo, tabel berkas, dan label navigasi.
  * *Alasan (R-31):* Karakter huruf memiliki tinggi *x-height* yang besar sehingga mudah dibaca pada ukuran antarmuka desktop rapat ($14\text{px} - 16\text{px}$).
* **Cryptographic Data Font (Monospace Purposeful):** `JetBrains Mono` atau `Consolas` digunakan **hanya** untuk menampilkan nilai Hash SHA-256, Nomor Seri USB Dongle, *Ciphertext* Base64, *Nonce* Blockchain, dan ukuran byte kapasitas LSB.
  * *Alasan (R-31):* Font monospace diperlukan pada string heksadesimal dan Base64 agar staf dan dosen penguji dapat membandingkan kesamaan karakter demi karakter (seperti awalan `"000"` pada Proof-of-Work) tanpa distorsi lebar huruf.

---

## 4. Komponen, Tata Letak, & Motif Identitas (R-05, R-11, R-14, R-20)

* **Identity Motif (Segel & Stempel Arsip Kriptografi):** Setiap dokumen memo dan paket `.vault` menampilkan komponen **"Cryptographic Seal Stamp"**, yaitu kotak berbingkai garis ganda (`border-double border-4`) seperti stempel akta resmi yang memuat Nomor Blok, Timestamp ISO, dan potongan Hash SHA-256.
* **Satu Titik Fokus per Layar (Focal Point Lever):**
  * Pada layar *Memo Vault*, titik fokus adalah lembar pembaca/editor dokumen beserta segel Blockchain-nya.
  * Pada layar *Kurir & Verifikasi `.vault`*, titik fokus adalah kartu hasil verifikasi Sertifikat Blockchain.
  * Pada layar *Steganography Studio*, titik fokus adalah panel perbandingan gambar asli dan kalkulator kapasitas bit LSB.
* **Border Radius (R-11):** Gunakan sudut tegas dan konsisten (`rounded-md` / `6px` untuk kartu dan input, `rounded` / `4px` untuk tombol dan lencana status). Dilarang membuat seluruh tombol, kartu, dan input berbentuk kapsul bundar (*pill-shaped*).
* **Larangan Karakter Em-Dash (R-02):** Dilarang menggunakan karakter *em dash* pada seluruh teks UI. Gunakan tanda titik dua (`:`), koma (`,`), atau tanda kurung.
* **Kelengkapan State UI (R-27):** Setiap tabel dan panel hasil wajib memiliki tampilan *Empty State* (saat belum ada memo/berkas), *Loading State* (saat *mining* blok PoW atau enkripsi RC4 berjalan), dan *Error State* (saat passphrase salah atau gambar bukan PNG).