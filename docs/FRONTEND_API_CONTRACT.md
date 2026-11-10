# Kontrak API Frontend AegisVault

Melengkapi `TECHNICAL_SPEC.md` Bab 4 dengan bentuk data yang dipakai `frontend/app.js`, untuk acuan `main.py`.

Error memakai `{"detail": {"code": "KODE", "message": "Kalimat untuk pengguna"}}`. Kalimat `message` ditampilkan apa adanya, kecuali kode yang punya teks sendiri di frontend.

## Endpoint di luar tabel spesifikasi

Frontend butuh endpoint ini, dan semuanya sudah ada di `main.py`.

| Metode | Path | Fungsi backend |
| :--- | :--- | :--- |
| `GET` | `/api/documents/{id}` | Mendekripsi isi memo dan menggabungkan data bloknya |
| `GET` | `/api/documents/{id}/ciphertext` | Nilai tersimpan, IV-nya, dan `vigenere_256_encrypt` |
| `DELETE` | `/api/documents/{id}` | `Database.delete_document` |
| `POST` | `/api/auth/check` | Memeriksa akun dan PIN sebelum kamera dinyalakan |
| `POST` | `/api/dongle/replace` | Mengganti dongle hilang dengan username, PIN, dan wajah |
| `POST` | `/api/system/restore` | Memulihkan salinan database atau rantai blok yang HMAC-nya cocok |

## Bentuk data

| Endpoint | Permintaan | Respons |
| :--- | :--- | :--- |
| `GET /api/system/status` | | `dongle` (hasil `validate_dongle` ditambah `can_enroll` dan `can_replace`, dan `valid` hanya benar untuk dongle terdaftar), `biometric` (hasil `detect_fingerprint_capability`), `db` (hasil `check_integrity`), `session` (`{username, full_name}` atau `null`), `test_mode` (bool) |
| `POST /api/dongle/enroll` | `{}` | hasil `enroll_dongle` |
| `POST /api/dongle/replace` | `{username, password, face_image}` | hasil `enroll_dongle` |
| `POST /api/system/restore` | `{}` | `{restored: [...]}` |
| `POST /api/auth/check` | `{username, password}` | `{ok: true}` |
| `POST /api/auth/register` | `{username, full_name, password, face_image}` | `{username, full_name}` |
| `POST /api/auth/login` | `{username, password, face_image}` | `{username, full_name}` |
| `POST /api/auth/logout` | `{}` | `{ok: true}` |
| `GET /api/documents` | | `[{id, doc_uuid, title, category, author, block_index, block_hash, created_at}]` |
| `POST /api/documents` | `{title, category, content}` | `{id, block_index, ...}` |
| `GET /api/documents/{id}` | | data daftar ditambah `content`, `nonce`, `timestamp`, `verified` |
| `GET /api/documents/{id}/ciphertext` | | `{plaintext, vigenere_ciphertext_hex, aes_iv_hex, final_ciphertext_b64}` |
| `POST /api/documents/{id}/export` | `{passphrase}` | berkas `.vault`, nama pada `Content-Disposition` |
| `POST /api/documents/import-verify` | multipart `file`, `passphrase` | hasil `import_and_verify_vault`. Untuk paket berkas: hasil `import_and_verify_file_vault` ditambah `package_type: "file"` dan `file_b64` (isi berkas asli, hanya kalau `valid`) |
| `GET /api/attachments` | | `[{id, filename, size_bytes, created_at}]` |
| `POST /api/attachments/upload` | multipart `file` | `{id, ...}` |
| `GET /api/attachments/{id}/download` | | berkas asli, nama pada `Content-Disposition` |
| `POST /api/attachments/{id}/export` | `{passphrase}` | paket `.vault` berisi berkas (`package_type: "file"`), bernama `<nama asli>.vault` |
| `POST /api/stego/capacity` | multipart `image` | `{format, extension, mime, capacity_bytes, width, height, method}`, `method` bernilai `lsb` atau `dct` (JPEG) |
| `POST /api/stego/embed` | multipart `image`, `message`, `passphrase` opsional | berkas berformat sama dengan aslinya, nama sama pada `Content-Disposition`, dengan header `X-Stego-Report`: `{channels_changed, channels_total, max_channel_diff, psnr_db, method, format}`, ditambah `coefficients_changed` dan `coefficients_used` untuk JPEG |
| `POST /api/stego/extract` | multipart `image`, `passphrase` opsional | `{message}` |
| `GET /api/blockchain/audit` | | `{chain, chain_valid, message, db}`: `chain_valid` dan `message` dari `is_chain_valid`, `db` dari `check_integrity` |

`face_image` berupa data URL Base64 dari kamera.

## Kode error dengan teks khusus

| Kode | Dipakai pada | Tampilan |
| :--- | :--- | :--- |
| `USER_NOT_FOUND` | cek akun, login | "Akun belum terdaftar" pada kolom username |
| `PIN_INVALID` | cek akun, login | "PIN salah" pada kolom PIN |
| `DONGLE_LOCKED` | daftar dongle | Pendaftaran tanpa login ditolak, tampilkan "Ganti dongle" |
| `NO_STAFF` | ganti dongle | Belum ada staf, kembali ke layar dongle dan minta dongle terdaftar |
| `DB_TAMPERED` | semua data | Layar "Database berubah" dengan tombol pulihkan |
| `FACE_MISMATCH` | login | Layar akses ditolak |
| `NO_FACE` | login, registrasi | Minta ambil gambar ulang |
| `FACE_NOT_ENROLLED` | login | Minta daftar ulang |
| `USERNAME_TAKEN` | registrasi | Pesan pada kolom username |
| `PASSPHRASE_REQUIRED` | baca pesan gambar | Minta isi kata sandi pesan |
| `PASSPHRASE_INVALID` | baca pesan gambar | Kata sandi salah atau gambar berubah |
| `IMAGE_UNSUPPORTED` | ruang pesan, sembunyikan pesan | Format gambar ditolak (GIF, animasi, atau format lain) |

Frontend memanggil `/api/auth/check` sebelum kamera menyala, jadi akun belum terdaftar atau PIN salah langsung terlihat. `/api/auth/login` tetap memeriksa keduanya lagi bersama wajah.

## Kebutuhan jendela desktop

Jendela memakai bingkai asli sistem operasi, jadi tombol perkecil, perbesar, dan tutup tidak dibuat di antarmuka. Unduhan perlu `webview.settings["ALLOW_DOWNLOADS"] = True`.

`test_mode` hanya boleh `true` saat pengujian, karena opsi unggah foto melewati kamera.

## Kunci dan sesi

- Memo dienkripsi dengan K1 dan K2 dari PIN staf dan `password_salt`, yang tersimpan di memori selama sesi. Hanya pembuat yang bisa membuka memonya. Staf lain menerimanya lewat `.vault`.
- Berkas RC4 memakai `K_RC4 = SHA256("AegisVault-RC4-v1" || K1 || K2)[:16]`.
- Sesi memakai cookie `aegis_session` (HttpOnly, SameSite=Strict) dan hilang saat aplikasi ditutup.
- Layanan hanya menerima host `127.0.0.1` atau `localhost`, dan menolak aksi dari origin lain.
