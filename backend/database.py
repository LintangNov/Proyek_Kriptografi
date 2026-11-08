"""
AegisVault Database Layer
Manajer SQLite dengan Field-Level Encryption dan Database Integrity Checksum
sesuai docs/TECHNICAL_SPEC.md Bab 3.5.

Mekanisme proteksi:
1. Field-Level Encryption: kolom ber-akhiran _enc yang diisi plainteks oleh aplikasi
   (full_name_enc, role_enc, title_enc, category_enc, original_filename_enc, mime_type_enc)
   dienkripsi dengan AES-128-CBC (kunci sistem hasil PBKDF2) sebelum masuk ke SQLite.
   Format nilai tersimpan: Base64(IV 16 byte || AES_CBC_Encrypt(Pad(plaintext))).
   Kolom content_super_enc TIDAK dienkripsi ulang di sini karena sudah berupa
   ciphertext Super Enkripsi (Extended Vigenere + AES-128-CBC) dari pemanggil.
2. Database File Integrity Checksum: setiap transaksi tulis (INSERT/DELETE) diakhiri
   dengan perhitungan SHA-256 seluruh file storage/aegis_vault.db yang disimpan di
   storage/db_checksum.sha256. Setiap operasi baca dan tulis memverifikasi checksum
   terlebih dahulu. Jika berubah dari luar aplikasi, DatabaseIntegrityError dilempar.

Catatan Kepatuhan Regulasi Kode:
- Dilarang menggunakan karakter em dash pada seluruh teks dan komentar (Aturan R-02).
"""

import base64
import contextlib
import functools
import hashlib
import hmac
import os
import sqlite3
import threading
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from backend import config
from backend.crypto_engine import aes_128_cbc_decrypt, aes_128_cbc_encrypt, derive_keys


# =====================================================================
# Pengecualian Khusus
# =====================================================================

class DatabaseIntegrityError(Exception):
    """File database berubah dari luar aplikasi, checksum hilang, atau field tidak terdekripsi."""


class DuplicateRecordError(ValueError):
    """Data dengan kunci unik yang sama (username, doc_uuid, att_uuid) sudah ada."""


# =====================================================================
# Skema Tabel (identik dengan docs/TECHNICAL_SPEC.md Bab 3.5)
# =====================================================================

SCHEMA_SQL = """
CREATE TABLE IF NOT EXISTS users (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    username TEXT UNIQUE NOT NULL,
    full_name_enc TEXT NOT NULL,
    role_enc TEXT NOT NULL,
    password_hash TEXT NOT NULL,
    password_salt TEXT NOT NULL,
    face_model_path TEXT NOT NULL,
    created_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS documents (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    doc_uuid TEXT UNIQUE NOT NULL,
    author_username TEXT NOT NULL,
    title_enc TEXT NOT NULL,
    category_enc TEXT NOT NULL,
    content_super_enc TEXT NOT NULL,
    plaintext_sha256 TEXT NOT NULL,
    block_index INTEGER NOT NULL,
    block_hash TEXT NOT NULL,
    created_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS attachments (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    att_uuid TEXT UNIQUE NOT NULL,
    owner_username TEXT NOT NULL,
    original_filename_enc TEXT NOT NULL,
    mime_type_enc TEXT NOT NULL,
    encrypted_filepath TEXT NOT NULL,
    file_size_bytes INTEGER NOT NULL,
    original_sha256 TEXT NOT NULL,
    block_index INTEGER NOT NULL,
    block_hash TEXT NOT NULL,
    created_at TEXT NOT NULL
);
"""

# Kolom yang dienkripsi pada level field oleh lapisan database ini.
ENCRYPTED_COLUMNS: Dict[str, tuple] = {
    "users": ("full_name_enc", "role_enc"),
    "documents": ("title_enc", "category_enc"),
    "attachments": ("original_filename_enc", "mime_type_enc"),
}

VALID_TABLES = ("users", "documents", "attachments")

# Status hasil pemeriksaan integritas.
STATUS_OK = "OK"
STATUS_TAMPERED = "TAMPERED"
STATUS_MISSING_CHECKSUM = "MISSING_CHECKSUM"
STATUS_NO_DATABASE = "NO_DATABASE"


def _utc_now() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


@functools.lru_cache(maxsize=8)
def _system_field_key(pepper: str) -> bytes:
    """Menurunkan kunci AES-128 sistem (K2) dari pepper dengan PBKDF2-HMAC-SHA256."""
    _k1, k2 = derive_keys(pepper, config.SYSTEM_FIELD_KEY_SALT)
    return k2


# =====================================================================
# Field-Level Encryption
# =====================================================================

def encrypt_field(plaintext: str, key: bytes) -> str:
    """AES-128-CBC dengan IV acak. Mengembalikan Base64(IV || ciphertext)."""
    ciphertext, iv = aes_128_cbc_encrypt(plaintext.encode("utf-8"), key)
    return base64.b64encode(iv + ciphertext).decode("ascii")


def decrypt_field(token: str, key: bytes) -> str:
    """Kebalikan encrypt_field. Melempar DatabaseIntegrityError jika token rusak."""
    try:
        raw = base64.b64decode(token, validate=True)
        if len(raw) < 32:
            raise ValueError("payload terlalu pendek")
        return aes_128_cbc_decrypt(raw[16:], key, raw[:16]).decode("utf-8")
    except Exception as exc:
        raise DatabaseIntegrityError(f"Field terenkripsi tidak dapat didekripsi: {exc}") from exc


# =====================================================================
# Manajer Database
# =====================================================================

class Database:
    """
    Pembungkus SQLite thread-safe. Satu koneksi dibuka per operasi dan ditutup
    sebelum checksum dihitung, sehingga isi file di disk selalu konsisten.
    """

    def __init__(self, storage_dir: Optional[str] = None, pepper: Optional[str] = None):
        self.paths = config.ensure_storage_dirs(storage_dir)
        self._field_key = _system_field_key(pepper or config.SYSTEM_SECRET_PEPPER)
        self._lock = threading.RLock()
        self._initialize()

    # ------------------------------------------------------------------
    # Inisialisasi & koneksi
    # ------------------------------------------------------------------

    def _initialize(self) -> None:
        """
        Database baru: buat skema lalu tulis checksum awal.
        Database lama: dibiarkan apa adanya, keutuhannya diperiksa saat dibaca.
        """
        with self._lock:
            if os.path.exists(self.paths.db):
                return
            with contextlib.closing(self._connect()) as conn:
                conn.executescript(SCHEMA_SQL)
                conn.commit()
            self.update_checksum()

    def _connect(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self.paths.db)
        conn.row_factory = sqlite3.Row
        return conn

    # ------------------------------------------------------------------
    # Database Integrity Checksum
    # ------------------------------------------------------------------

    def compute_db_checksum(self) -> str:
        """SHA-256 dari seluruh file biner aegis_vault.db."""
        digest = hashlib.sha256()
        with open(self.paths.db, "rb") as f:
            for chunk in iter(lambda: f.read(65536), b""):
                digest.update(chunk)
        return digest.hexdigest()

    def update_checksum(self) -> str:
        """Menghitung ulang checksum dan menyimpannya ke db_checksum.sha256 secara atomik."""
        with self._lock:
            checksum = self.compute_db_checksum()
            temp_path = self.paths.db_checksum + ".tmp"
            with open(temp_path, "w", encoding="ascii") as f:
                f.write(checksum)
            os.replace(temp_path, self.paths.db_checksum)
            return checksum

    def check_integrity(self) -> Dict[str, Any]:
        """
        Membandingkan checksum tersimpan dengan checksum file database saat ini.
        Mengembalikan dict: status, ok, expected_sha256, actual_sha256, message.
        """
        with self._lock:
            if not os.path.exists(self.paths.db):
                return self._report(STATUS_NO_DATABASE, None, None,
                                    "File database tidak ditemukan.")
            actual = self.compute_db_checksum()
            if not os.path.exists(self.paths.db_checksum):
                return self._report(STATUS_MISSING_CHECKSUM, None, actual,
                                    "File checksum database hilang.")
            with open(self.paths.db_checksum, "r", encoding="ascii", errors="replace") as f:
                expected = f.read().strip().lower()
            if hmac.compare_digest(expected, actual):
                return self._report(STATUS_OK, expected, actual,
                                    "Checksum database cocok. File tidak berubah.")
            return self._report(STATUS_TAMPERED, expected, actual,
                                "Checksum tidak cocok. File database diubah dari luar aplikasi.")

    @staticmethod
    def _report(status: str, expected: Optional[str], actual: Optional[str], message: str) -> Dict[str, Any]:
        return {
            "status": status,
            "ok": status == STATUS_OK,
            "expected_sha256": expected,
            "actual_sha256": actual,
            "message": message,
        }

    def assert_integrity(self) -> None:
        """Melempar DatabaseIntegrityError jika checksum tidak valid."""
        report = self.check_integrity()
        if not report["ok"]:
            raise DatabaseIntegrityError(f"[{report['status']}] {report['message']}")

    # ------------------------------------------------------------------
    # Primitif baca dan tulis
    # ------------------------------------------------------------------

    def _read(self, sql: str, params: tuple = ()) -> List[sqlite3.Row]:
        with self._lock:
            self.assert_integrity()
            with contextlib.closing(self._connect()) as conn:
                return conn.execute(sql, params).fetchall()

    def _write(self, sql: str, params: tuple = ()) -> int:
        """Menjalankan satu INSERT/DELETE, lalu memperbarui checksum. Mengembalikan rowcount."""
        with self._lock:
            self.assert_integrity()
            try:
                with contextlib.closing(self._connect()) as conn:
                    cursor = conn.execute(sql, params)
                    conn.commit()
                    affected = cursor.rowcount
            except sqlite3.IntegrityError as exc:
                raise DuplicateRecordError(str(exc)) from exc
            self.update_checksum()
            return affected

    def _row_to_dict(self, table: str, row: sqlite3.Row) -> Dict[str, Any]:
        """Mengubah baris menjadi dict dengan seluruh kolom field-level terdekripsi."""
        data = dict(row)
        for column in ENCRYPTED_COLUMNS[table]:
            data[column] = decrypt_field(data[column], self._field_key)
        return data

    def get_raw_rows(self, table: str) -> List[Dict[str, Any]]:
        """Baris mentah (masih ciphertext) untuk inspeksi auditor dan demonstrasi AC-03."""
        if table not in VALID_TABLES:
            raise ValueError(f"Tabel tidak dikenal: {table}")
        return [dict(r) for r in self._read(f"SELECT * FROM {table} ORDER BY id")]

    # ------------------------------------------------------------------
    # Tabel users
    # ------------------------------------------------------------------

    def create_user(
        self,
        username: str,
        full_name: str,
        role: str,
        password_hash: str,
        password_salt: str,
        face_model_path: str,
    ) -> int:
        """Menyimpan staf baru. full_name dan role dienkripsi pada level field."""
        if not username or not username.strip():
            raise ValueError("Username tidak boleh kosong.")
        self._write(
            "INSERT INTO users (username, full_name_enc, role_enc, password_hash, "
            "password_salt, face_model_path, created_at) VALUES (?, ?, ?, ?, ?, ?, ?)",
            (
                username.strip(),
                encrypt_field(full_name, self._field_key),
                encrypt_field(role, self._field_key),
                password_hash,
                password_salt,
                face_model_path,
                _utc_now(),
            ),
        )
        return self.get_user(username.strip())["id"]

    def get_user(self, username: str) -> Optional[Dict[str, Any]]:
        rows = self._read("SELECT * FROM users WHERE username = ?", (username,))
        return self._row_to_dict("users", rows[0]) if rows else None

    def list_users(self) -> List[Dict[str, Any]]:
        return [self._row_to_dict("users", r) for r in self._read("SELECT * FROM users ORDER BY id")]

    def user_exists(self, username: str) -> bool:
        return bool(self._read("SELECT 1 FROM users WHERE username = ?", (username,)))

    def delete_user(self, username: str) -> bool:
        return self._write("DELETE FROM users WHERE username = ?", (username,)) > 0

    # ------------------------------------------------------------------
    # Tabel documents
    # ------------------------------------------------------------------

    def insert_document(
        self,
        doc_uuid: str,
        author_username: str,
        title: str,
        category: str,
        content_super_enc: str,
        plaintext_sha256: str,
        block_index: int,
        block_hash: str,
    ) -> int:
        """
        Menyimpan memo. title dan category dienkripsi pada level field.
        content_super_enc wajib sudah berupa ciphertext Super Enkripsi dari pemanggil.
        """
        self._write(
            "INSERT INTO documents (doc_uuid, author_username, title_enc, category_enc, "
            "content_super_enc, plaintext_sha256, block_index, block_hash, created_at) "
            "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
            (
                doc_uuid,
                author_username,
                encrypt_field(title, self._field_key),
                encrypt_field(category, self._field_key),
                content_super_enc,
                plaintext_sha256,
                int(block_index),
                block_hash,
                _utc_now(),
            ),
        )
        return self.get_document(doc_uuid)["id"]

    def get_document(self, doc_uuid: str) -> Optional[Dict[str, Any]]:
        rows = self._read("SELECT * FROM documents WHERE doc_uuid = ?", (doc_uuid,))
        return self._row_to_dict("documents", rows[0]) if rows else None

    def get_document_by_id(self, doc_id: int) -> Optional[Dict[str, Any]]:
        rows = self._read("SELECT * FROM documents WHERE id = ?", (doc_id,))
        return self._row_to_dict("documents", rows[0]) if rows else None

    def list_documents(self, author_username: Optional[str] = None) -> List[Dict[str, Any]]:
        if author_username is None:
            rows = self._read("SELECT * FROM documents ORDER BY id DESC")
        else:
            rows = self._read(
                "SELECT * FROM documents WHERE author_username = ? ORDER BY id DESC",
                (author_username,),
            )
        return [self._row_to_dict("documents", r) for r in rows]

    def delete_document(self, doc_uuid: str, author_username: Optional[str] = None) -> bool:
        """Menghapus memo. Jika author_username diberikan, hanya pemilik yang boleh menghapus."""
        if author_username is None:
            return self._write("DELETE FROM documents WHERE doc_uuid = ?", (doc_uuid,)) > 0
        return self._write(
            "DELETE FROM documents WHERE doc_uuid = ? AND author_username = ?",
            (doc_uuid, author_username),
        ) > 0

    # ------------------------------------------------------------------
    # Tabel attachments
    # ------------------------------------------------------------------

    def insert_attachment(
        self,
        att_uuid: str,
        owner_username: str,
        original_filename: str,
        mime_type: str,
        encrypted_filepath: str,
        file_size_bytes: int,
        original_sha256: str,
        block_index: int,
        block_hash: str,
    ) -> int:
        """Menyimpan metadata lampiran. Nama berkas dan MIME dienkripsi pada level field."""
        self._write(
            "INSERT INTO attachments (att_uuid, owner_username, original_filename_enc, "
            "mime_type_enc, encrypted_filepath, file_size_bytes, original_sha256, "
            "block_index, block_hash, created_at) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
            (
                att_uuid,
                owner_username,
                encrypt_field(original_filename, self._field_key),
                encrypt_field(mime_type, self._field_key),
                encrypted_filepath,
                int(file_size_bytes),
                original_sha256,
                int(block_index),
                block_hash,
                _utc_now(),
            ),
        )
        return self.get_attachment(att_uuid)["id"]

    def get_attachment(self, att_uuid: str) -> Optional[Dict[str, Any]]:
        rows = self._read("SELECT * FROM attachments WHERE att_uuid = ?", (att_uuid,))
        return self._row_to_dict("attachments", rows[0]) if rows else None

    def get_attachment_by_id(self, att_id: int) -> Optional[Dict[str, Any]]:
        rows = self._read("SELECT * FROM attachments WHERE id = ?", (att_id,))
        return self._row_to_dict("attachments", rows[0]) if rows else None

    def list_attachments(self, owner_username: Optional[str] = None) -> List[Dict[str, Any]]:
        if owner_username is None:
            rows = self._read("SELECT * FROM attachments ORDER BY id DESC")
        else:
            rows = self._read(
                "SELECT * FROM attachments WHERE owner_username = ? ORDER BY id DESC",
                (owner_username,),
            )
        return [self._row_to_dict("attachments", r) for r in rows]

    def delete_attachment(self, att_uuid: str, owner_username: Optional[str] = None) -> bool:
        """Menghapus metadata lampiran. Berkas .rc4 di disk dihapus oleh pemanggil."""
        if owner_username is None:
            return self._write("DELETE FROM attachments WHERE att_uuid = ?", (att_uuid,)) > 0
        return self._write(
            "DELETE FROM attachments WHERE att_uuid = ? AND owner_username = ?",
            (att_uuid, owner_username),
        ) > 0

