# Kontrak API Frontend AegisVault

Melengkapi `TECHNICAL_SPEC.md` Bab 4 dengan bentuk data yang dipakai `frontend/app.js`, untuk acuan `main.py`.

Error memakai `{"detail": {"code": "KODE", "message": "Kalimat untuk pengguna"}}`. Kalimat `message` ditampilkan apa adanya, kecuali kode yang punya teks sendiri di frontend.

## Endpoint di luar tabel spesifikasi

Frontend butuh tiga endpoint ini, dan `backend/` sudah punya fungsinya.

| Metode | Path | Fungsi backend |
| :--- | :--- | :--- |
| `GET` | `/api/documents/{id}` | Mendekripsi isi memo dan menggabungkan data bloknya |
| `GET` | `/api/documents/{id}/ciphertext` | Nilai tersimpan, IV-nya, dan `vigenere_256_encrypt` |
| `DELETE` | `/api/documents/{id}` | `Database.delete_document` |

## Bentuk data

| Endpoint | Permintaan | Respons |
| :--- | :--- | :--- |
| `GET /api/system/status` | | `dongle` (hasil `validate_dongle`), `biometric` (hasil `detect_fingerprint_capability`), `db` (hasil `check_integrity`), `session` (`{username, full_name}` atau `null`), `test_mode` (bool) |
| `POST /api/dongle/enroll` | `{}` | hasil `enroll_dongle` |
| `POST /api/auth/register` | `{username, full_name, password, face_image}` | `{username, full_name}` |
| `POST /api/auth/login` | `{username, password, face_image}` | `{username, full_name}` |
| `POST /api/auth/logout` | `{}` | `{ok: true}` |
| `GET /api/documents` | | `[{id, doc_uuid, title, category, author, block_index, block_hash, created_at}]` |
| `POST /api/documents` | `{title, category, content}` | `{id, block_index, ...}` |
| `GET /api/documents/{id}` | | data daftar ditambah `content`, `nonce`, `timestamp`, `verified` |
| `GET /api/documents/{id}/ciphertext` | | `{plaintext, vigenere_ciphertext_hex, aes_iv_hex, final_ciphertext_b64}` |
| `POST /api/documents/{id}/export` | `{passphrase}` | berkas `.vault`, nama pada `Content-Disposition` |
| `POST /api/documents/import-verify` | multipart `file`, `passphrase` | hasil `import_and_verify_vault` |
| `GET /api/attachments` | | `[{id, filename, size_bytes, created_at}]` |
| `POST /api/attachments/upload` | multipart `file` | `{id, ...}` |
| `GET /api/attachments/{id}/download` | | berkas asli, nama pada `Content-Disposition` |
| `POST /api/stego/embed` | multipart `image`, `message`, `passphrase` opsional | berkas PNG |
| `POST /api/stego/extract` | multipart `image`, `passphrase` opsional | `{message}` |
| `GET /api/blockchain/audit` | | `{chain, chain_valid, message, db}`: `chain_valid` dan `message` dari `is_chain_valid`, `db` dari `check_integrity` |

`face_image` berupa data URL Base64 dari kamera.

## Kode error dengan teks khusus

| Kode | Dipakai pada | Tampilan |
| :--- | :--- | :--- |
| `CREDENTIALS_INVALID` | login | Kembali ke layar PIN |
| `FACE_MISMATCH` | login | Layar akses ditolak |
| `NO_FACE` | login, registrasi | Minta ambil gambar ulang |
| `FACE_NOT_ENROLLED` | login | Minta daftar ulang |
| `USERNAME_TAKEN` | registrasi | Pesan pada kolom username |
| `PASSPHRASE_REQUIRED` | ekstrak stego | Minta isi passphrase |

Login tetap satu permintaan: frontend mengumpulkan PIN dan foto wajah, lalu mengirim keduanya. Backend menolak salah satu lewat kode di atas.

## Kebutuhan jendela desktop

Jendela memakai bingkai asli sistem operasi, jadi tombol perkecil, perbesar, dan tutup tidak dibuat di antarmuka. Unduhan perlu `webview.settings["ALLOW_DOWNLOADS"] = True`.

`test_mode` hanya boleh `true` saat pengujian, karena opsi unggah foto melewati kamera.

## Kunci dan sesi

- Memo dienkripsi dengan K1 dan K2 dari PIN staf dan `password_salt`, yang tersimpan di memori selama sesi. Hanya pembuat yang bisa membuka memonya. Staf lain menerimanya lewat `.vault`.
- Berkas RC4 memakai `K_RC4 = SHA256("AegisVault-RC4-v1" || K1 || K2)[:16]`.
- Sesi memakai cookie `aegis_session` (HttpOnly, SameSite=Strict) dan hilang saat aplikasi ditutup.
- Layanan hanya menerima host `127.0.0.1` atau `localhost`, dan menolak aksi dari origin lain.
