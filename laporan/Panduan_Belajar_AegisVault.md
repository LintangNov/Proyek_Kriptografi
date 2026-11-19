# Panduan Belajar AegisVault

Panduan ini memakai istilah dari materi dosen (folder `Kriptografi/materi`). Istilah yang tidak ada di materi ditandai **(di luar materi)**. Semua angka contoh berasal dari demo yang dijalankan di folder sementara, bukan dari `storage/` asli Anda.

Sumber materi yang dipakai: Materi 1 (dasar), 3 dan 4 (klasik dan Vigenere), 5 (modern, XOR, cipher aliran), 6 (cipher blok, mode), 7 (contoh implementasi: AES, RC4), 8 (fungsi hash), 9 (steganografi).

---

## 0. Peta besar

Tema proyek: **brankas dokumen rahasia instansi**. Setiap ancaman dijawab satu lapis perlindungan.

| Yang dilindungi | Ancaman | Teknik | Materi |
| --- | --- | --- | --- |
| Pintu masuk aplikasi | Orang lain membuka aplikasi | USB dongle, PIN (hash), wajah | 8 |
| Teks memo | Dibaca orang lain | Super enkripsi: Vigenere lalu AES-CBC | 1, 3, 4, 6, 7 |
| Berkas lampiran | Dibaca orang lain | RC4 (cipher aliran) | 5, 7 |
| File database | File dicuri dari komputer | AES-CBC per kolom | 6, 7 |
| Pesan di gambar | Pesan terlihat mencurigakan | LSB dan JSteg | 9 |
| Keaslian dokumen | Isi diubah diam-diam | Hash SHA-256 dan rantai blok | 8 |
| Kiriman antarstaf | Paket diganti di jalan | Passphrase dan HMAC | 8 (HMAC di luar materi) |

Kenapa algoritmanya berbeda-beda: kriteria tugas meminta teks memakai super enkripsi (klasik + modern), berkas memakai algoritma yang berbeda dari teks, dan database memakai enkripsi sendiri. Selain itu tiap lapis menjawab ancaman yang berbeda.

---

## 1. Glosarium

### A. Dasar (Materi 1)

| Istilah | Artinya |
| --- | --- |
| Plainteks (P) | Pesan asli yang bisa dibaca |
| Cipherteks (C) | Pesan setelah disandikan |
| Kunci | Parameter rahasia untuk enkripsi dan dekripsi. Algoritmanya boleh diketahui, kuncinya rahasia |
| Enkripsi / Dekripsi | P menjadi C / C kembali menjadi P |
| Cipher | Nama lain algoritma kriptografi |

### B. Operasi dasar (Materi 5)

| Istilah | Artinya |
| --- | --- |
| Bit, byte | 1 byte = 8 bit, nilainya 0 sampai 255 |
| Heksadesimal (hex) | Cara menulis byte dengan 2 karakter (0 sampai 9, A sampai F). `0x52` = 82 |
| XOR (⊕) | 0⊕0=0, 0⊕1=1, 1⊕0=1, 1⊕1=0. Aturan penting: a⊕a=0, sehingga C = P⊕K dan P = C⊕K |
| Modulo 256 | Hitungan memutar. 250 + 10 = 4 (bukan 260), karena byte hanya 0 sampai 255 |
| Base64 **(di luar materi)** | Cara menulis byte sebagai huruf dan angka biasa supaya muat disimpan sebagai teks |

### C. Jenis cipher (Materi 3, 4, 5, 6, 7)

| Istilah | Artinya |
| --- | --- |
| Cipher klasik | Bekerja per karakter. Contoh: Vigenere. Kunci diulang periodik di sepanjang pesan |
| Extended Vigenere 256 | Vigenere yang bekerja per byte, bukan per huruf A sampai Z: C = (P + K) mod 256 |
| Cipher modern | Bekerja pada bit. Ada dua kategori: cipher aliran dan cipher blok |
| Cipher aliran (stream cipher) | Mengenkripsi bit demi bit atau byte demi byte dengan **keystream**. Contoh: RC4 |
| Keystream | Barisan byte acak semu dari kunci. Dipakai untuk di-XOR dengan plainteks |
| Cipher blok | Mengenkripsi per blok. AES memakai blok 16 byte |
| Padding | Byte tambahan supaya blok terakhir penuh (Materi 5, slide padding bits) |
| Mode operasi | Cara menyambung blok. Aplikasi memakai **CBC** (Materi 6) |
| CBC | Setiap blok P di-XOR dengan C blok sebelumnya sebelum dienkripsi. Blok yang sama tidak menghasilkan C yang sama |
| IV (initialization vector) | Blok awal acak untuk blok pertama CBC. Tidak rahasia, disimpan di depan cipherteks |
| AES-128 | Cipher blok, blok 16 byte, kunci 16 byte (128 bit) |
| Super enkripsi | Dua enkripsi berurutan: klasik dulu, modern sesudahnya (Materi 1, 3, 5) |

### D. Hash dan turunannya (Materi 8, kecuali yang ditandai)

| Istilah | Artinya |
| --- | --- |
| Fungsi hash | h = H(M). Pesan sembarang panjang menjadi nilai berukuran tetap. SHA-256 menghasilkan 256 bit = 64 karakter hex |
| Message digest, nilai hash | Nama lain keluaran fungsi hash |
| Satu arah (irreversible) | Hash tidak bisa dikembalikan ke pesan. Karena itu **hash bukan enkripsi** |
| Integritas | Pesan berubah 1 bit, hash berubah total. Bandingkan hash lama dan baru untuk tahu pesan dimodifikasi atau tidak |
| Salt **(di luar materi)** | Bilangan acak yang ditempel ke PIN sebelum di-hash. PIN sama + salt beda = hash beda |
| Pepper **(di luar materi)** | Rahasia tetap milik sistem, sama untuk semua pengguna. Di aplikasi ini tertulis di `backend/config.py` |
| PBKDF2 **(di luar materi)** | Alat penurun kunci: PIN + salt diaduk **100.000 kali** dengan hash, hasilnya dipakai sebagai kunci. Memperlambat tebakan PIN |
| HMAC **(di luar materi)** | Hash yang memakai kunci. Hanya pemegang kunci yang bisa membuat atau memeriksa nilainya |
| Checksum | Hash dari sebuah berkas untuk mengecek apakah berkas berubah |

### E. Kunci di aplikasi ini

| Istilah | Artinya |
| --- | --- |
| PIN | Kata sandi staf, minimal 6 karakter. Satu-satunya yang diingat pengguna |
| K1 | 16 byte pertama hasil PBKDF2. Kunci untuk Vigenere |
| K2 | 16 byte kedua hasil PBKDF2. Kunci untuk AES |
| K_RC4 | Kunci RC4, dihitung dari K1 dan K2: SHA-256("AegisVault-RC4-v1" + K1 + K2), diambil 16 byte |
| Nonce | Bilangan acak 16 byte yang ditempel ke K_RC4 untuk setiap berkas, supaya keystream tidak pernah sama |
| Passphrase | Kata sandi bersama untuk paket `.vault` dan pesan steganografi. Dipakai pengganti PIN, karena penerima tidak boleh tahu PIN pengirim |

### F. Steganografi (Materi 9)

| Istilah | Artinya |
| --- | --- |
| Steganografi | Menyembunyikan **keberadaan** pesan. Kriptografi menyembunyikan **isi** pesan |
| Embedded message / hiddentext | Pesan yang disembunyikan |
| Cover-object | Gambar pembawa (asli) |
| Stego-object | Gambar setelah disisipi pesan |
| Stego-key | Kunci penyisipan dan ekstraksi. Di aplikasi: passphrase |
| LSB | Bit paling kanan sebuah byte. Mengganti LSB hanya mengubah nilai byte paling banyak 1 |
| Imperceptible | Perubahan tidak terlihat mata |
| DCT, JPEG, JSteg | JPEG menyimpan gambar sebagai koefisien DCT. JSteg menyisipkan bit ke koefisien itu, bukan ke piksel |
| PSNR **(di luar materi)** | Ukuran seberapa mirip gambar asli dan hasil, dalam dB. Makin besar makin mirip |

### G. Blockchain (di luar materi, dasarnya hash dari Materi 8)

| Istilah | Artinya |
| --- | --- |
| Blok | Satu catatan: indeks, waktu, ID dokumen, pembuat, hash isi dokumen, hash blok sebelumnya, nonce, hash blok |
| previous_hash | Hash blok sebelumnya. Inilah yang "merantai" blok |
| Proof-of-Work | Mencari nonce sampai hash blok diawali `000`. Sulit dicari, mudah diperiksa |
| Genesis | Blok pertama, dibuat saat rantai baru dibuat |
| e-Seal | Sertifikat keaslian: dokumen disegel pada satu blok |

### H. Perangkat dan aplikasi

| Istilah | Artinya |
| --- | --- |
| Dongle | USB flashdisk sebagai "kunci fisik". Berisi `dongle.key` |
| Volume serial | Nomor seri partisi USB yang dibaca dari Windows |
| Biometrik | Ciri tubuh sebagai bukti identitas. Di sini: wajah |
| Haar Cascade | Metode OpenCV untuk menemukan wajah pada gambar |
| NCC | Normalized Cross-Correlation: ukuran kemiripan dua gambar |
| `.npy` | Format berkas array NumPy. Wajah disimpan di sini |
| Sesi, cookie | Tanda bahwa staf sudah login. Cookie `aegis_session` |
| RAM | Memori sementara komputer. Hilang saat aplikasi ditutup |
| Enkripsi tingkat kolom | Hanya kolom tertentu di database yang dienkripsi, bukan seluruh berkas |
| `.vault` | Paket kiriman antarstaf berformat JSON |

---

## 2. K1, K2, dan K_RC4 dengan bahasa materi

Setiap algoritma butuh **kunci** sendiri, tetapi pengguna hanya mengingat satu PIN. Karena itu aplikasi **menurunkan** kunci dari PIN.

```
PIN + salt (16 byte, tersimpan di database)
        |
        v   PBKDF2: diaduk 100.000 kali dengan hash
   32 byte
   |-- 16 byte pertama  = K1  -> kunci Vigenere
   |-- 16 byte kedua    = K2  -> kunci AES
        |
        v   SHA-256("AegisVault-RC4-v1" + K1 + K2), ambil 16 byte
      K_RC4 -> kunci RC4
```

Hubungan dengan Materi 4: kunci Vigenere adalah string yang **diulang periodik** sepanjang pesan. Di aplikasi, string itu adalah K1 sepanjang 16 byte.

Tiga hal yang perlu diingat:

1. K1, K2, dan K_RC4 **tidak disimpan** di mana pun. Dihitung ulang saat login dan disimpan di RAM selama sesi.
2. Satu kunci tidak dipakai dua algoritma. Itu alasan K_RC4 dibuat terpisah dari K1 dan K2.
3. Kunci hanya bisa dihitung dari PIN yang benar. Tanpa PIN yang sama, memo dan berkas tidak bisa dibuka. Di daftar endpoint tidak ada fitur ganti atau reset PIN.

Contoh nilai dari demo (PIN `123456`, salt acak). Angka ini berubah untuk setiap PIN dan salt.

| Kunci | Nilai (hex) |
| --- | --- |
| K1 | `2f1eb8d37ea885ab1df8e5e272b6a901` |
| K2 | `096255b960b01494ffe84823cb85a5da` |
| K_RC4 | `209eca12ece31b5b245ccc529643949d` |

---

## 3. Penjelasan per fitur

### 3.1 Login (3 syarat)

Tiga faktor harus terpenuhi: **dongle terpasang**, **PIN benar**, **wajah cocok**.

**PIN dan hash**

- Saat registrasi, aplikasi membuat salt acak 16 byte lalu menghitung `hash = SHA-256(salt + PIN)`.
- Yang disimpan di tabel `users`: kolom `password_hash` (64 karakter hex) dan `password_salt` (32 karakter hex). **PIN tidak disimpan.**
- Saat login, aplikasi menghitung ulang `SHA-256(salt + PIN yang diketik)` lalu membandingkannya dengan `password_hash`.
- Hash bukan enkripsi (Materi 8): satu arah dan tidak memakai kunci. Karena itu tidak ada yang bisa "mendekripsi" hash PIN.
- Contoh dari demo (PIN `123456`):

```
salt = af40057827e4c526eab78c2d9ca63e7e
hash = 093837629408e71db83fb38614a7bf3d47d06c3648dac1f61775fc176dde04ce
```

PIN yang sama dengan salt lain menghasilkan hash lain. Itulah gunanya salt.

**Wajah**

1. Saat registrasi, kamera mengirim satu frame. OpenCV (Haar Cascade) mencari wajah, mengambil wajah terbesar, mengubahnya ke keabuan, mengecilkannya ke **128 x 128 piksel**, lalu meratakan histogramnya.
2. Hasilnya disimpan sebagai matriks angka di `storage/faces/<username>.npy`. Ukuran berkas 16.512 byte (128 byte header + 128 x 128 piksel).
3. Berkas ini **bukan hash dan bukan terenkripsi**. Isinya gambar abu-abu 128 x 128. Siapa pun yang bisa membuka folder `storage/faces` bisa melihat wajahnya. Ini keterbatasan yang perlu Anda sebut jujur saat presentasi.
4. Saat login, frame baru diproses dengan cara yang sama lalu dibandingkan: `skor = 0,6 x NCC + 0,4 x korelasi histogram`. Cocok bila skor ≥ 0,72.

Kenapa wajah tidak di-hash? Materi 8: hash berubah total bila 1 bit berubah. Dua foto wajah yang sama tidak pernah identik bit demi bit, jadi wajah harus dibandingkan dengan **ukuran kemiripan**, bukan kesamaan persis.

**Dongle**

`dongle.key` di USB berisi `dongle_id`, `volume_serial`, dan tanda tangan `SHA-256(dongle_id : volume_serial : pepper)`. Aplikasi membaca nomor seri USB dari Windows lalu menghitung ulang tanda tangannya. Dongle disalin ke USB lain akan gagal, karena nomor seri volume berbeda. Dicek tiap 1 detik. USB dicabut, aplikasi terkunci.

### 3.2 Memo teks (super enkripsi)

Alur: plainteks, **Extended Vigenere (K1)**, **AES-128-CBC (K2, IV acak)**, IV ditempel di depan, **Base64**.

Contoh nyata dari demo, memo `RAPAT`, dengan K1 di atas:

| Huruf | Kode | + K1 (mod 256) | Hasil |
| --- | --- | --- | --- |
| R | 0x52 (82) | + 0x2f | 0x81 |
| A | 0x41 (65) | + 0x1e | 0x5f |
| P | 0x50 (80) | + 0xb8 | 0x08 (264 - 256) |
| A | 0x41 (65) | + 0xd3 | 0x14 (276 - 256) |
| T | 0x54 (84) | + 0x7e | 0xd2 |

Jadi lapis 1 menghasilkan `81 5f 08 14 d2`. Kunci K1 hanya terpakai 5 byte karena pesannya pendek (kunci diulang bila pesan lebih panjang dari 16 byte).

Lapis 2: 5 byte itu diberi **padding** sampai 16 byte, lalu dienkripsi AES-CBC dengan K2 dan IV acak. Hasil akhir = IV (16 byte) + cipherteks AES (16 byte) = 32 byte, ditulis Base64 menjadi 44 karakter. Di demo: `GrXkqlVvwRNJ+yVhfaVLYCfS0hCQvGEj/E82mMKGAvo=`.

Memo yang sama ditulis dua kali menghasilkan cipherteks berbeda, karena IV acak. Ini sifat mode CBC (Materi 6).

Fitur "Inspeksi Ciphertext" di aplikasi menampilkan ketiga tahap itu: hex hasil Vigenere, IV, dan Base64 akhir.

### 3.3 Berkas lampiran (RC4)

- Berkas dienkripsi byte demi byte: `C = P XOR keystream`.
- Kunci RC4 yang dipakai adalah **K_RC4 + nonce acak 16 byte** (32 byte). Nonce baru untuk setiap berkas, sehingga dua berkas tidak pernah memakai keystream yang sama.
- Disimpan di `storage/attachments/ATT-XXXXXXXXXXXX.rc4` dengan format `nonce (16 byte) + cipherteks`.
- **Ukuran `.rc4` = ukuran asli + 16 byte.** RC4 tidak memakai padding. Di demo: 1.100 byte menjadi 1.116 byte.
- Nama asli berkas tidak ada di nama `.rc4`. Nama aslinya disimpan terenkripsi di database.
- Saat diunduh: aplikasi membaca nonce, mendekripsi, lalu **menghitung SHA-256 hasilnya** dan membandingkannya dengan hash yang tersimpan. Bila beda, aplikasi menolak (`FILE_TAMPERED`).

### 3.4 Database (enkripsi per kolom)

- Tiga tabel: `users`, `documents`, `attachments`.
- Kolom yang berakhiran `_enc` dienkripsi **AES-128-CBC dengan IV acak**, disimpan sebagai Base64 dari IV + cipherteks.
- Kuncinya diturunkan dari **pepper** sistem, **bukan dari PIN**. Alasan yang masuk akal (inferensi dari desain): kuncinya milik sistem sehingga aplikasi tidak bergantung pada PIN tertentu untuk membaca kolom seperti nama staf.
- Konsekuensinya: pepper tertulis di kode (`backend/config.py`), jadi pelindung ini lebih lemah daripada kunci dari PIN. Ini tercatat di Subbab 3.5 laporan.

Contoh isi tabel `users` dari demo (dibaca langsung dengan sqlite3):

```
username      : 198001
full_name_enc : IHJye9GGHcEKiCLZOSlWZUY0Z68oib+HUHM6zMakKb0=
role_enc      : pLeaso1VGyi6XQm4hL0pw5nMfyrxso9Jg1ypfIc6oiE=
password_hash : 093837629408e71db83fb38614a7bf3d47d06c3648dac1f61775fc176dde04ce
password_salt : af40057827e4c526eab78c2d9ca63e7e
face_model_path: ...\faces\198001.npy
```

Pengamanan keutuhan file database (selain enkripsi kolom):

| Berkas | Isi |
| --- | --- |
| `db_checksum.sha256` | SHA-256 dari seluruh file `aegis_vault.db` |
| `aegis_vault.db.hmac` | HMAC dari file database (penyerang tidak bisa memalsukannya tanpa kunci) |
| `aegis_vault.db.bak` | Salinan cadangan yang sah, dipakai tombol pemulihan |

Sebelum membaca atau menulis, aplikasi menghitung ulang dan membandingkan. Beda berarti file diubah dari luar (`DB_TAMPERED`).

### 3.5 Steganografi

- **PNG, BMP, TIFF, WebP:** LSB. Aplikasi mengganti bit paling kanan dari kanal R, G, B piksel dengan bit pesan.
- **JPEG:** JSteg. Bit pesan disisipkan ke koefisien DCT terkuantisasi, kecuali koefisien bernilai 0 dan 1, tanpa kompres ulang.
- Bentuk muatan: **4 byte panjang** + `RAW:` + pesan (tanpa passphrase), atau `ENC:` + salt + cipherteks Base64 (dengan passphrase, memakai super enkripsi).
- Tanpa passphrase, siapa pun yang tahu cara kerjanya bisa membaca pesan. Dengan passphrase, pesan juga terenkripsi (kriptografi + steganografi, saling melengkapi, Materi 9).
- Kapasitas citra W x H: `(W x H x 3) / 8 - 4` byte. Citra 300 x 200 = 22.496 byte.

### 3.6 Blockchain (rantai blok)

Setiap memo atau berkas yang disimpan menambah satu blok:

```
index, timestamp, doc_uuid, author, payload_sha256, previous_hash, nonce
        |
        v  SHA-256
   block_hash   (harus diawali "000")
```

- `payload_sha256` = hash isi dokumen asli.
- `previous_hash` = hash blok sebelumnya, sehingga blok **terkait** ke belakang.
- **Proof-of-Work**: nonce dicoba dari 0 naik 1 per percobaan sampai hash diawali `000`. Rata-rata perlu sekitar 4.096 percobaan (16 pangkat 3). Blok Genesis di `storage/blockchain.json` Anda memakai nonce 10447 dan hash `00052da2...`.
- **Ini bukan enkripsi** (Materi 8: hash tidak memakai kunci). Tujuannya membuktikan isi dokumen **tidak berubah**: ubah satu huruf di dokumen, hash isinya berbeda, dan hash itu tidak cocok dengan yang disegel di blok.
- Ubah blok lama, hash blok itu berubah, `previous_hash` blok berikutnya tidak cocok, dan rantai putus. Aplikasi menampilkan peringatan.

### 3.7 Kirim antarstaf (`.vault`)

- Pengirim mengetik **passphrase bersama** (min. 8 karakter). Aplikasi membuat salt baru, lalu PBKDF2 menurunkan K1 dan K2 dari **passphrase** (bukan dari PIN pengirim).
- Memo dienkripsi dengan super enkripsi. Berkas dienkripsi dengan RC4.
- Paket JSON berisi: cipherteks, metadata, sertifikat blok, dan `integrity_mac` (**HMAC-SHA256** atas seluruh isi).
- Penerima memasukkan passphrase. Aplikasi memeriksa HMAC, mendekripsi, menghitung ulang hash isi, memeriksa hash blok dan Proof-of-Work, lalu membandingkan dengan rantai lokal bila ada. Ubah 1 byte di paket, verifikasi gagal.
- Keterbatasan: pemegang passphrase bisa mengubah isi lalu menghitung ulang HMAC. Tanda tangan digital asimetris akan mengatasinya (tercatat di laporan).

---

## 4. Jawaban untuk daftar QnA

### 4.1 Tema dan korelasi enkripsi

Tema satu: dokumen rahasia instansi. Jenis datanya berbeda (teks, berkas, kolom database, gambar, keaslian), jadi tiap jenis memakai teknik yang cocok. Korelasinya: **semua kunci turun dari satu PIN** (kecuali kunci sistem untuk database), sehingga pengguna cukup mengingat satu PIN.

### 4.2 Enkripsi per fitur

| Fitur | Algoritma | Kunci | Keluaran |
| --- | --- | --- | --- |
| Login (PIN) | SHA-256 + salt (hash) | Tidak ada kunci | 64 karakter hex |
| Kunci sesi | PBKDF2-HMAC-SHA256, 100.000 iterasi | PIN + salt | K1, K2 (16 byte masing-masing) |
| Memo | Extended Vigenere lalu AES-128-CBC | K1, K2 | Base64 (IV + cipherteks) |
| Berkas | RC4 | K_RC4 + nonce | `nonce + cipherteks` (`.rc4`) |
| Kolom database | AES-128-CBC | Dari pepper | Base64 (IV + cipherteks) |
| Gambar | LSB atau JSteg | Passphrase (opsional) | Gambar stego |
| Keaslian | SHA-256 + Proof-of-Work | Tidak ada kunci | Blok dengan hash `000...` |
| Paket `.vault` | PBKDF2, super enkripsi atau RC4, HMAC | Passphrase | JSON `.vault` |
| Dongle | SHA-256 | Pepper | Tanda tangan di `dongle.key` |

### 4.3 Cek file yang dienkripsi (di folder)

Semua data aplikasi ada di `storage/` (di dalam folder proyek, tidak ikut git):

| Lokasi | Isi | Bisa dibaca? |
| --- | --- | --- |
| `storage/aegis_vault.db` | Database SQLite | Struktur terbaca. Kolom `_enc` berupa Base64 acak, isi memo juga acak |
| `storage/attachments/*.rc4` | Berkas terenkripsi | Tidak. Bila dibuka, isinya byte acak |
| `storage/faces/*.npy` | Wajah staf | **Terbaca** sebagai gambar abu-abu (tidak terenkripsi) |
| `storage/blockchain.json` | Rantai blok | Terbaca (isinya hash, bukan isi dokumen) |
| `db_checksum.sha256`, `*.hmac`, `*.bak` | Pengaman keutuhan | Hash dan salinan |
| `dongle.key` (di USB) | Identitas dongle | Terbaca (JSON) |

Saat ini `storage/` Anda masih kosong: 0 pengguna, 0 memo, 0 berkas, dan baru blok Genesis. Daftarkan satu staf lalu simpan satu memo dan satu berkas, baru isinya bisa dilihat.

### 4.4 Server dan cache: tertinggal atau tidak?

Dari kode (`main.py`, `stego_engine.py`):

| Tempat | Yang tertinggal? |
| --- | --- |
| RAM server | Ya, selama sesi: username, K1, K2 (K_RC4 dihitung dari keduanya). Hanya **satu** sesi aktif. Saat logout, sesi di-set kosong. Saat aplikasi ditutup, prosesnya mati dan RAM dilepas |
| Disk | Berkas hasil dekripsi **tidak ditulis** ke disk. Unduhan dikirim langsung dari memori. Yang ditulis hanya versi terenkripsi |
| Folder sementara | Untuk JPEG, `jpeglib` hanya mau membaca dari berkas, jadi aplikasi membuat folder `aegis-stego-...` di folder temp Windows, lalu menghapusnya setelah selesai. Folder bisa tertinggal hanya bila proses dimatikan paksa di tengah. Saat dicek, tidak ada folder sisa |
| Cache peramban | Semua respons `/api/` memakai header `Cache-Control: no-store`, artinya peramban diminta tidak menyimpannya |
| Frame wajah | Diproses di memori. Yang disimpan hanya matriks 128 x 128 saat registrasi |

### 4.5 Database

Lihat Bagian 3.4. Ringkasnya: 3 tabel, kolom `_enc` terenkripsi AES-CBC, isi memo super terenkripsi, hash disimpan sebagai pembanding, dan tiga berkas pengaman keutuhan.

### 4.6 File terenkripsi: ukuran dan bentuk

| Jenis | Rumus ukuran | Contoh |
| --- | --- | --- |
| Berkas `.rc4` | asli + 16 byte | 1.100 menjadi 1.116 byte |
| Memo (sebelum Base64) | 16 (IV) + AES, AES = (n dibagi 16, dibulatkan ke bawah, ditambah 1) x 16 | n = 5: 16 + 16 = 32 byte |
| Memo (setelah Base64) | 4 x pembulatan ke atas dari (byte / 3) | 32 byte menjadi 44 karakter. 100 byte menjadi 128 byte, 172 karakter |
| Hash SHA-256 | tetap | 32 byte = 64 karakter hex |
| Wajah `.npy` | 128 + 128 x 128 | 16.512 byte |
| Gambar stego | Dimensi sama. Ukuran file hampir sama | PNG tetap PNG |

Ingat: AES-CBC menambah padding (selalu ada, bahkan bila n kelipatan 16 ditambah satu blok penuh), sedangkan RC4 tidak.

### 4.7 Pembuktian steganografi

Di demo, pesan `Lari jam satu` disisipkan ke gambar acak 300 x 200:

| Bukti | Hasil |
| --- | --- |
| Pesan terekstrak | `Lari jam satu` |
| Selisih nilai terbesar per kanal | 1 (sesuai Materi 9: LSB hanya mengubah byte paling banyak 1) |
| Kanal yang berubah | 79 dari 180.000 |
| PSNR | 81,71 dB (makin besar makin mirip) |
| 32 bit LSB pertama | `00000000 00000000 00000000 00010001` = 17 |

Angka 17 adalah panjang muatan: `RAW:` (4 byte) + `Lari jam satu` (13 byte) = 17. Jadi header panjang yang disebut di laporan benar-benar ada di bit paling kanan piksel pertama.

Cara membuktikan di depan dosen:

1. Sisipkan pesan di tab Studio Steganografi. Catat laporan PSNR dari aplikasi.
2. Bandingkan gambar asli dan gambar hasil. Tidak terlihat bedanya.
3. Ekstrak pesan di tab yang sama. Pesan keluar utuh.
4. Dengan passphrase: ekstrak tanpa passphrase, aplikasi menolak (`PASSPHRASE_REQUIRED`).

### 4.8 Alur program

1. Jalankan aplikasi. Server lokal hidup di 127.0.0.1 dan jendela terbuka.
2. **Gatekeeper:** cek USB dongle tiap 1 detik. Tidak valid, layar terkunci. Dongle belum terdaftar dan belum ada staf: daftarkan USB.
3. **Registrasi (sekali per staf):** NIP, nama, PIN, foto wajah. Disimpan hash PIN + salt, nama terenkripsi, wajah `.npy`.
4. **Login tahap 1:** username dan PIN dicek (hash).
5. **Login tahap 2:** kamera, wajah dibandingkan, skor ≥ 0,72 lolos.
6. PBKDF2 menurunkan K1 dan K2, disimpan di RAM, cookie sesi diterbitkan.
7. **Memo:** super enkripsi, hash isi disegel ke blok baru (Proof-of-Work), disimpan di database.
8. **Berkas:** RC4, hash disegel ke blok, file `.rc4` disimpan.
9. **Kurir:** ekspor `.vault` dengan passphrase, atau impor dan verifikasi.
10. **Stego:** sisipkan atau ekstrak pesan di gambar.
11. **Audit:** periksa rantai blok dan keutuhan database. Bila rusak, pulihkan dari cadangan.
12. **Logout:** sesi dan kunci di RAM dihapus.

---

## 5. Coba sendiri

Semua perintah dijalankan dari folder proyek `Proyek_Kriptografi`. Daftarkan satu staf dan simpan satu memo dan satu berkas lebih dulu.

Lihat isi tabel `users` (hanya membaca):

```bash
.venv/Scripts/python.exe -c "import sqlite3;c=sqlite3.connect('file:storage/aegis_vault.db?mode=ro',uri=True);[print(r) for r in c.execute('select username,full_name_enc,password_hash,password_salt from users')]"
```

Lihat isi memo yang tersimpan (hanya Base64 acak):

```bash
.venv/Scripts/python.exe -c "import sqlite3;c=sqlite3.connect('file:storage/aegis_vault.db?mode=ro',uri=True);[print(r) for r in c.execute('select title_enc,content_super_enc from documents')]"
```

Hitung sendiri hash PIN dan cocokkan dengan database (ganti SALT dan PIN):

```bash
.venv/Scripts/python.exe -c "import hashlib;print(hashlib.sha256(bytes.fromhex('SALT')+'PIN'.encode()).hexdigest())"
```

Lihat wajah yang tersimpan sebagai gambar (ganti NIP):

```bash
.venv/Scripts/python.exe -c "import numpy as np;from PIL import Image;a=np.load('storage/faces/NIP.npy');print(a.shape,a.dtype);Image.fromarray(a).resize((256,256)).save('wajah.png')"
```

Lihat ukuran berkas terenkripsi:

```bash
ls -l storage/attachments
```

---

## 6. Kemungkinan pertanyaan dosen

| Pertanyaan | Jawaban singkat |
| --- | --- |
| Hash PIN itu enkripsi? | Bukan. Hash satu arah dan tanpa kunci (Materi 8). Tidak bisa dikembalikan ke PIN |
| Untuk apa salt? | PIN yang sama menghasilkan hash berbeda, dan tabel hash yang sudah dihitung jadi tidak berguna |
| Bedanya hash dan HMAC? | HMAC memakai kunci. Hanya pemegang kunci yang bisa membuat atau memeriksanya |
| Kenapa Vigenere saja tidak cukup? | Kunci diulang, polanya bisa dianalisis (Materi 4). Karena itu dilapis AES |
| Kenapa ada IV? | Supaya pesan sama menghasilkan cipherteks berbeda pada mode CBC (Materi 6) |
| Kenapa RC4 butuh nonce? | Keystream yang sama dipakai dua kali membuat dua cipherteks bisa di-XOR dan membocorkan pesan |
| Apa bedanya cipher aliran dan blok? | Aliran: bit atau byte satu per satu dengan keystream (RC4). Blok: per blok 16 byte (AES) |
| Steganografi vs kriptografi? | Steganografi menyembunyikan keberadaan pesan, kriptografi menyembunyikan isinya (Materi 9) |
| Apa itu Proof-of-Work di sini? | Mencari nonce sampai hash blok diawali `000` |
| Apakah blockchain ini terdistribusi? | Tidak. Rantai lokal satu komputer, tanpa konsensus |
| Apa kelemahan aplikasi? | Pepper tertulis di kode, tidak ada pembatasan tebakan PIN, wajah hanya 2D (foto bisa menipu) dan `.npy` tidak terenkripsi, RC4 sudah dianggap lemah, HMAC `.vault` berbasis passphrase bersama |
| Kalau PIN lupa? | K1 dan K2 hanya bisa dihitung dari PIN, jadi memo dan berkas lama tidak bisa dibuka. Tidak ada fitur reset PIN di daftar endpoint |
