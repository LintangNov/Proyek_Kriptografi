"""
Entry point AegisVault: REST API lokal FastAPI dan jendela desktop pywebview.

Jalankan:
    python main.py              buka jendela desktop
    python main.py --no-window  layanan saja, akses lewat http://127.0.0.1:8000

Variabel lingkungan:
    AEGIS_PORT       port layanan (bawaan 8000)
    AEGIS_TEST_MODE  "1" untuk memunculkan unggah foto pengganti kamera. Matikan saat demo akhir.
"""

import argparse
import base64
import hashlib
import hmac
import io
import json
import os
import secrets
import shutil
import socket
import sys
import threading
import time
import traceback
import uuid

FROZEN = getattr(sys, "frozen", False)
if FROZEN:
    # Folder .exe satu file dihapus saat aplikasi ditutup, jadi data disimpan di profil pengguna.
    # Variabel ini harus ada sebelum backend.config diimpor.
    os.environ.setdefault("AEGIS_STORAGE_DIR", os.path.join(os.environ.get("LOCALAPPDATA") or os.path.expanduser("~"), "AegisVault", "storage"))
    # Mode jendela tidak punya konsol, sedangkan uvicorn menulis ke stdout dan stderr.
    if sys.stdout is None:
        sys.stdout = open(os.devnull, "w", encoding="utf-8")
    if sys.stderr is None:
        sys.stderr = open(os.devnull, "w", encoding="utf-8")

from contextlib import asynccontextmanager
from dataclasses import dataclass
from typing import Any, Dict, List, NoReturn, Optional, Tuple
from urllib.parse import quote, urlparse

from fastapi import Cookie, FastAPI, File, Form, HTTPException, Request, UploadFile
from fastapi.responses import JSONResponse, Response
from fastapi.staticfiles import StaticFiles
from PIL import Image, UnidentifiedImageError
from pydantic import BaseModel
from starlette.middleware.trustedhost import TrustedHostMiddleware

from backend import biometric_auth as biometric
from backend import config
from backend.blockchain_ledger import Blockchain, import_and_verify_vault, package_vault_file
from backend.crypto_engine import (
    decrypt_file_rc4,
    derive_keys,
    encrypt_file_rc4,
    hash_password,
    sha256_hex,
    super_decrypt_text,
    super_encrypt_text,
    verify_password,
    vigenere_256_encrypt,
)
from backend.database import Database, DatabaseIntegrityError, DuplicateRecordError
from backend.dongle_guard import DongleError, DongleGuard, DongleMonitor, MultipleDrivesError
from backend.stego_engine import embed_with_report, extract_message_from_image, save_stego_png

BASE_DIR = getattr(sys, "_MEIPASS", os.path.dirname(os.path.abspath(__file__)))
FRONTEND_DIR = os.path.join(BASE_DIR, "frontend")
HOST = "127.0.0.1"
SESSION_COOKIE = "aegis_session"
MIN_PIN_LENGTH = 6
MIN_PASSPHRASE_LENGTH = 8
MAX_VAULT_BYTES = 5 * 1024 * 1024
MAX_IMAGE_BYTES = config.MAX_ATTACHMENT_BYTES
USERNAME_HELP = "Pakai huruf, angka, titik, garis bawah, atau tanda hubung, tanpa spasi."
CSP = (
    "default-src 'self'; img-src 'self' data: blob:; style-src 'self' 'unsafe-inline'; "
    "font-src 'self'; connect-src 'self'; media-src 'self' blob:; object-src 'none'; "
    "base-uri 'none'; frame-ancestors 'none'"
)


def fail(status: int, code: str, message: str) -> NoReturn:
    raise HTTPException(status_code=status, detail={"code": code, "message": message})


def attachment_headers(filename: str) -> Dict[str, str]:
    ascii_name = filename.encode("ascii", "ignore").decode().replace('"', "").replace("\\", "") or "berkas"
    return {"Content-Disposition": f"attachment; filename=\"{ascii_name}\"; filename*=UTF-8''{quote(filename)}"}


class LoginBody(BaseModel):
    username: str
    password: str
    face_image: str


class RegisterBody(LoginBody):
    full_name: str


class MemoBody(BaseModel):
    title: str
    category: str
    content: str


class ExportBody(BaseModel):
    passphrase: str


class CheckBody(BaseModel):
    username: str
    password: str


@dataclass
class Session:
    token: str
    username: str
    full_name: str
    k1: bytes
    k2: bytes

    @property
    def public(self) -> Dict[str, str]:
        return {"username": self.username, "full_name": self.full_name}

    @property
    def rc4_key(self) -> bytes:
        # Kunci terpisah dari K1 dan K2, supaya RC4 dan AES tidak memakai kunci yang sama.
        return hashlib.sha256(b"AegisVault-RC4-v1" + self.k1 + self.k2).digest()[:16]


class Core:
    """Status aplikasi: database, buku besar, pemantau dongle, dan sesi staf aktif."""

    def __init__(self, storage_dir: Optional[str], test_mode: bool):
        self.paths = config.ensure_storage_dirs(storage_dir)
        self.test_mode = test_mode
        # Data dari versi sebelum ada HMAC diterima sekali, selama SHA-256-nya masih cocok.
        self.legacy_install = os.path.exists(self.paths.db) and not os.path.exists(self.paths.db + ".hmac")
        self.db = Database(storage_dir)
        if self.legacy_install:
            self.db.adopt_legacy_checksum()
        self.key = self.db.integrity_key
        self.chain_sig_path = self.paths.blockchain + ".sig"
        self.chain_backup_path = self.paths.blockchain + ".bak"
        self.registry_path = os.path.join(self.paths.root, "dongle_registry.json")
        self.registry_lock = threading.RLock()
        self.guard = DongleGuard()
        self.monitor = DongleMonitor(self.guard)
        # Dibaca sekali saja, karena frontend meminta status setiap detik.
        self.biometric = biometric.detect_fingerprint_capability()
        self.session: Optional[Session] = None
        self.chain_lock = threading.RLock()
        self.ledger_warning = ""
        fresh_ledger = not os.path.exists(self.paths.blockchain)
        self._preserve_corrupt_ledger()
        self.ledger = Blockchain(self.paths.blockchain)
        if fresh_ledger or self.legacy_install:
            self.sign_chain()

    # ---------- Tanda tangan buku besar ----------

    def _chain_mac(self, chain: List[Dict[str, Any]]) -> str:
        canonical = json.dumps(chain, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode("utf-8")
        return hmac.new(self.key, b"AegisVault-Chain-v1" + canonical, hashlib.sha256).hexdigest()

    def sign_chain(self) -> None:
        """Hanya aplikasi yang punya kunci, jadi rantai yang ditambang ulang di luar aplikasi tertangkap."""
        with open(self.chain_sig_path + ".tmp", "w", encoding="ascii") as f:
            f.write(self._chain_mac(self.ledger.chain))
        os.replace(self.chain_sig_path + ".tmp", self.chain_sig_path)
        shutil.copyfile(self.paths.blockchain, self.chain_backup_path + ".tmp")
        os.replace(self.chain_backup_path + ".tmp", self.chain_backup_path)

    def chain_signature_ok(self) -> bool:
        try:
            with open(self.chain_sig_path, "r", encoding="ascii", errors="replace") as f:
                return hmac.compare_digest(f.read().strip(), self._chain_mac(self.ledger.chain))
        except OSError:
            return False

    def restore_chain(self) -> bool:
        with self.chain_lock:
            try:
                with open(self.chain_backup_path, "r", encoding="utf-8") as f:
                    chain = json.load(f)
                with open(self.chain_sig_path, "r", encoding="ascii", errors="replace") as f:
                    if not hmac.compare_digest(f.read().strip(), self._chain_mac(chain)):
                        return False
            except (OSError, ValueError):
                return False
            shutil.copyfile(self.chain_backup_path, self.paths.blockchain + ".restore")
            os.replace(self.paths.blockchain + ".restore", self.paths.blockchain)
            self.ledger.chain = chain
            self.ledger_warning = ""
            return True

    # ---------- Dongle terdaftar ----------

    def _registry_mac(self, dongle_id: str) -> str:
        return hmac.new(self.key, b"AegisVault-Dongle-v1" + dongle_id.encode("utf-8"), hashlib.sha256).hexdigest()

    def registered_dongle(self) -> Optional[str]:
        """None berarti belum ada dongle. String kosong berarti file catatannya sudah diubah."""
        try:
            with open(self.registry_path, "r", encoding="utf-8") as f:
                data = json.load(f)
            dongle_id = data["dongle_id"]
            return dongle_id if hmac.compare_digest(data["mac"], self._registry_mac(dongle_id)) else ""
        except FileNotFoundError:
            return None
        except (OSError, ValueError, KeyError, TypeError):
            return ""

    def register_dongle(self, dongle_id: str) -> None:
        with self.registry_lock:
            temp_path = self.registry_path + ".tmp"
            with open(temp_path, "w", encoding="utf-8") as f:
                json.dump({"dongle_id": dongle_id, "mac": self._registry_mac(dongle_id)}, f)
            os.replace(temp_path, self.registry_path)

    def has_users(self) -> bool:
        try:
            return bool(self.db.get_raw_rows("users"))
        except DatabaseIntegrityError:
            return True

    def dongle_status(self) -> Dict[str, Any]:
        """Status monitor hanya membuktikan USB bertanda tangan sah. Di sini USB-nya harus yang terdaftar."""
        status = self.monitor.get_status()
        with self.registry_lock:
            registered = self.registered_dongle()
            empty = registered is None and not self.has_users()
            # Komputer baru, atau data versi lama: dongle sah pertama menjadi dongle terdaftar.
            if registered is None and status.get("valid") and (empty or self.legacy_install):
                self.register_dongle(status["dongle_id"])
                registered = status["dongle_id"]
                self.legacy_install = False
        if status.get("valid") and status.get("dongle_id") != registered:
            status.update(valid=False, reason="USB ini bukan dongle yang terdaftar di komputer ini.")
        status["can_enroll"] = empty and registered is None
        return status

    def _preserve_corrupt_ledger(self) -> None:
        """Blockchain() menimpa file rusak dengan rantai baru, jadi file itu diamankan sebagai bukti audit."""
        path = self.paths.blockchain
        if not os.path.exists(path):
            return
        try:
            with open(path, "r", encoding="utf-8") as f:
                if isinstance(json.load(f), list):
                    return
        except (ValueError, OSError):
            pass
        os.replace(path, f"{path}.rusak-{int(time.time())}")
        self.ledger_warning = "File blockchain.json rusak saat aplikasi dibuka. Salinannya disimpan, lalu aplikasi membuat rantai baru."

    def reload_chain(self) -> Tuple[bool, str]:
        """Membaca ulang file buku besar, karena auditor bisa mengubahnya saat aplikasi berjalan."""
        try:
            with open(self.paths.blockchain, "r", encoding="utf-8") as f:
                data = json.load(f)
            if not isinstance(data, list) or not data:
                raise ValueError("bukan daftar blok")
        except (ValueError, OSError):
            return False, "File blockchain.json hilang atau rusak."
        self.ledger.chain = data
        return True, ""

    def check_chain(self) -> Tuple[bool, str]:
        with self.chain_lock:
            ok, message = self.reload_chain()
            if not ok:
                return False, message
            try:
                valid, message = self.ledger.is_chain_valid()
            except (KeyError, TypeError, AttributeError):
                return False, "Struktur data blok rusak."
            if valid and not self.chain_signature_ok():
                return False, "Rantai blok berubah dari luar aplikasi: tanda tangan rantai tidak cocok."
            return valid, message

    def seal(self, doc_uuid: str, author: str, asset_type: str, payload_sha256: str) -> Dict[str, Any]:
        with self.chain_lock:
            self.db.assert_integrity()
            ok, message = self.check_chain()
            if not ok:
                fail(409, "CHAIN_INVALID", f"Rantai blok tidak valid, jadi aplikasi menolak menyegel data baru. {message}")
            block = self.ledger.mine_new_block(doc_uuid, author, asset_type, payload_sha256)
            self.sign_chain()
            return block

    def verify_user(self, username: str, password: str) -> Dict[str, Any]:
        user = self.db.get_user(username)
        if not user:
            fail(404, "USER_NOT_FOUND", "Akun belum terdaftar.")
        if not verify_password(password, user["password_salt"], user["password_hash"]):
            fail(401, "PIN_INVALID", "PIN salah.")
        return user

    def verify_user_face(self, username: str, face_image: str) -> None:
        try:
            result = biometric.verify_face(username, face_image, str(self.paths.root))
        except biometric.FaceNotEnrolledError:
            fail(409, "FACE_NOT_ENROLLED", "Akun ini belum punya data wajah. Daftarkan ulang staf.")
        except biometric.NoFaceDetectedError:
            fail(422, "NO_FACE", "Aplikasi tidak menemukan wajah pada gambar.")
        except biometric.InvalidImageError:
            fail(422, "INVALID_IMAGE", "Gambar tidak bisa dibaca. Ambil gambar lagi.")
        if not result["match"]:
            fail(401, "FACE_MISMATCH", "Wajah tidak cocok.")

    def block_of(self, doc_uuid: str) -> Optional[Dict[str, Any]]:
        with self.chain_lock:
            self.reload_chain()
            return self.ledger.get_block_by_doc_uuid(doc_uuid)

    def db_report(self) -> Dict[str, Any]:
        report = self.db.check_integrity()
        report["expected"] = report.get("expected_sha256")
        report["actual"] = report.get("actual_sha256")
        return report

    def require_dongle(self) -> None:
        if not self.dongle_status().get("valid"):
            fail(423, "DONGLE_REQUIRED", "Dongle tidak terdeteksi. Tancapkan dongle untuk melanjutkan.")

    def current(self, token: Optional[str]) -> Optional[Session]:
        s = self.session
        if s and token and hmac.compare_digest(s.token, token):
            return s
        return None

    def require_session(self, token: Optional[str]) -> Session:
        self.require_dongle()
        session = self.current(token)
        if not session:
            fail(401, "SESSION_REQUIRED", "Sesi berakhir. Silakan masuk lagi.")
        return session


def read_upload(file: UploadFile, limit: int, label: str) -> bytes:
    data = file.file.read(limit + 1)
    if len(data) > limit:
        fail(413, "FILE_TOO_LARGE", f"{label} melebihi batas {limit // (1024 * 1024)} MB. Pilih yang lebih kecil.")
    return data


def create_app(storage_dir: Optional[str] = None, test_mode: Optional[bool] = None) -> FastAPI:
    if test_mode is None:
        test_mode = os.environ.get("AEGIS_TEST_MODE") == "1"
    core = Core(storage_dir, test_mode)

    @asynccontextmanager
    async def lifespan(_app: FastAPI):
        core.monitor.refresh()
        core.monitor.start()
        yield
        core.monitor.stop()

    app = FastAPI(title="AegisVault Local API", docs_url=None, redoc_url=None, openapi_url=None, lifespan=lifespan)
    app.state.core = core

    @app.middleware("http")
    async def guard_requests(request: Request, call_next):
        # Situs lain tidak boleh memicu aksi pada layanan lokal lewat browser pengguna.
        origin = request.headers.get("origin")
        if origin and request.method not in ("GET", "HEAD") and urlparse(origin).netloc != request.headers.get("host"):
            return JSONResponse({"detail": {"code": "ORIGIN_DENIED", "message": "Permintaan dari luar aplikasi ditolak."}}, status_code=403)
        response = await call_next(request)
        response.headers["Content-Security-Policy"] = CSP
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["Referrer-Policy"] = "no-referrer"
        if request.url.path.startswith("/api/"):
            response.headers["Cache-Control"] = "no-store"
        return response

    # Dipasang terakhir agar berjalan paling awal, sekaligus mencegah DNS rebinding.
    app.add_middleware(TrustedHostMiddleware, allowed_hosts=[HOST, "localhost"])

    @app.exception_handler(DatabaseIntegrityError)
    async def on_db_integrity(_request: Request, _exc: DatabaseIntegrityError):
        return JSONResponse(status_code=409, content={"detail": {"code": "DB_TAMPERED", "message": "Database berubah dari luar aplikasi, jadi aplikasi menolak membacanya. Buka menu Blockchain dan audit, atau pulihkan database."}})

    # ---------- Sistem dan dongle ----------

    @app.get("/api/system/status")
    def system_status(aegis_session: Optional[str] = Cookie(default=None)):
        session = core.current(aegis_session)
        return {
            "dongle": core.dongle_status(),
            "biometric": core.biometric,
            "db": core.db_report(),
            "session": session.public if session else None,
            "test_mode": core.test_mode,
        }

    def write_dongle() -> Dict[str, Any]:
        try:
            result = core.guard.enroll_dongle()
        except MultipleDrivesError:
            fail(409, "MULTIPLE_DRIVES", "Ada lebih dari satu USB tertancap. Sisakan satu USB, lalu coba lagi.")
        except DongleError as exc:
            fail(400, "NO_DRIVE", str(exc))
        core.register_dongle(result["dongle_id"])
        core.monitor.refresh()
        return result

    @app.post("/api/dongle/enroll")
    def dongle_enroll():
        # Tanpa login hanya boleh saat komputer ini belum punya dongle dan belum punya staf.
        if not core.dongle_status()["can_enroll"]:
            fail(403, "DONGLE_LOCKED", "Komputer ini sudah punya dongle terdaftar. Tancapkan dongle itu, atau ganti dengan akun staf.")
        return write_dongle()

    @app.post("/api/dongle/replace")
    def dongle_replace(body: LoginBody):
        # Untuk dongle hilang: dongle lama langsung tidak berlaku, dan sesi aktif berakhir.
        username = body.username.strip()
        core.verify_user(username, body.password)
        core.verify_user_face(username, body.face_image)
        result = write_dongle()
        core.session = None
        return result

    @app.post("/api/system/restore")
    def system_restore():
        core.require_dongle()
        restored: List[str] = []
        if not core.db.check_integrity()["ok"]:
            if not core.db.restore_backup():
                fail(409, "NO_BACKUP", "Salinan database yang utuh tidak ditemukan, jadi database tidak bisa dipulihkan.")
            restored.append("database")
        valid, _message = core.check_chain()
        if not valid or core.ledger_warning:
            if not core.restore_chain():
                fail(409, "NO_BACKUP", "Salinan rantai blok yang utuh tidak ditemukan, jadi rantai tidak bisa dipulihkan.")
            restored.append("rantai blok")
        return {"restored": restored}

    # ---------- Autentikasi ----------

    @app.post("/api/auth/register")
    def register(body: RegisterBody):
        core.require_dongle()
        username = body.username.strip()
        full_name = body.full_name.strip()
        if not biometric._USERNAME_PATTERN.match(username):
            fail(422, "USERNAME_INVALID", USERNAME_HELP)
        if not full_name:
            fail(422, "NAME_REQUIRED", "Isi nama lengkap.")
        if len(body.password) < MIN_PIN_LENGTH:
            fail(422, "PIN_TOO_SHORT", f"PIN minimal {MIN_PIN_LENGTH} karakter.")
        if core.db.user_exists(username):
            fail(409, "USERNAME_TAKEN", "Username ini sudah dipakai. Pilih username lain.")
        try:
            enrolled = biometric.enroll_face(username, body.face_image, str(core.paths.root))
        except biometric.NoFaceDetectedError:
            fail(422, "NO_FACE", "Aplikasi tidak menemukan wajah pada foto. Ambil ulang foto.")
        except biometric.InvalidImageError:
            fail(422, "INVALID_IMAGE", "Foto tidak bisa dibaca. Ambil ulang foto.")
        password_hash, salt_hex = hash_password(body.password)
        try:
            core.db.create_user(username, full_name, "STAF", password_hash, salt_hex, enrolled["face_model_path"])
        except DuplicateRecordError:
            fail(409, "USERNAME_TAKEN", "Username ini sudah dipakai. Pilih username lain.")
        except DatabaseIntegrityError:
            biometric.delete_face(username, str(core.paths.root))
            raise
        return {"username": username, "full_name": full_name}

    @app.post("/api/auth/check")
    def auth_check(body: CheckBody):
        """Memeriksa akun dan PIN sebelum kamera dinyalakan."""
        core.verify_user(body.username.strip(), body.password)
        return {"ok": True}

    @app.post("/api/auth/login")
    def login(body: LoginBody):
        core.require_dongle()
        username = body.username.strip()
        user = core.verify_user(username, body.password)
        core.verify_user_face(username, body.face_image)
        k1, k2 = derive_keys(body.password, bytes.fromhex(user["password_salt"]))
        core.session = Session(secrets.token_urlsafe(32), username, user["full_name_enc"], k1, k2)
        response = JSONResponse(core.session.public)
        response.set_cookie(SESSION_COOKIE, core.session.token, httponly=True, samesite="strict", path="/")
        return response

    @app.post("/api/auth/logout")
    def logout(aegis_session: Optional[str] = Cookie(default=None)):
        if core.current(aegis_session):
            core.session = None
        response = JSONResponse({"ok": True})
        response.delete_cookie(SESSION_COOKIE, path="/")
        return response

    # ---------- Memo ----------

    def memo_public(row: Dict[str, Any]) -> Dict[str, Any]:
        return {
            "id": row["id"],
            "doc_uuid": row["doc_uuid"],
            "title": row["title_enc"],
            "category": row["category_enc"],
            "author": row["author_username"],
            "block_index": row["block_index"],
            "block_hash": row["block_hash"],
            "created_at": row["created_at"],
        }

    def own_memo(doc_id: int, session: Session) -> Dict[str, Any]:
        row = core.db.get_document_by_id(doc_id)
        if not row or row["author_username"] != session.username:
            fail(404, "NOT_FOUND", "Memo tidak ditemukan.")
        return row

    def memo_plaintext(row: Dict[str, Any], session: Session) -> str:
        try:
            return super_decrypt_text(row["content_super_enc"], session.k1, session.k2)
        except (ValueError, UnicodeDecodeError):
            fail(409, "DOC_UNREADABLE", "Isi memo tidak bisa didekripsi. Data memo mungkin berubah.")

    @app.get("/api/documents")
    def list_documents(aegis_session: Optional[str] = Cookie(default=None)):
        session = core.require_session(aegis_session)
        return [memo_public(r) for r in core.db.list_documents(session.username)]

    @app.post("/api/documents")
    def create_document(body: MemoBody, aegis_session: Optional[str] = Cookie(default=None)):
        session = core.require_session(aegis_session)
        title, category = body.title.strip(), body.category.strip()
        if not title or not category or not body.content.strip():
            fail(422, "MEMO_INCOMPLETE", "Judul, klasifikasi, dan isi memo wajib diisi.")
        doc_uuid = f"DOC-{uuid.uuid4().hex[:12].upper()}"
        digest = sha256_hex(body.content)
        ciphertext = super_encrypt_text(body.content, session.k1, session.k2)
        with core.chain_lock:
            block = core.seal(doc_uuid, session.username, "MEMO_TEXT", digest)
            doc_id = core.db.insert_document(doc_uuid, session.username, title, category, ciphertext, digest, block["index"], block["block_hash"])
        return memo_public(core.db.get_document_by_id(doc_id))

    @app.get("/api/documents/{doc_id}")
    def get_document(doc_id: int, aegis_session: Optional[str] = Cookie(default=None)):
        session = core.require_session(aegis_session)
        row = own_memo(doc_id, session)
        content = memo_plaintext(row, session)
        block = core.block_of(row["doc_uuid"]) or {}
        verified = sha256_hex(content) == row["plaintext_sha256"] and block.get("block_hash") == row["block_hash"]
        return {**memo_public(row), "content": content, "nonce": block.get("nonce"), "timestamp": block.get("timestamp"), "verified": verified}

    @app.get("/api/documents/{doc_id}/ciphertext")
    def get_ciphertext(doc_id: int, aegis_session: Optional[str] = Cookie(default=None)):
        session = core.require_session(aegis_session)
        row = own_memo(doc_id, session)
        plaintext = memo_plaintext(row, session)
        stored = row["content_super_enc"]
        # Menampilkan nilai yang benar-benar tersimpan, bukan hasil enkripsi ulang dengan IV baru.
        return {
            "plaintext": plaintext,
            "vigenere_ciphertext_hex": vigenere_256_encrypt(plaintext.encode("utf-8"), session.k1).hex(),
            "aes_iv_hex": base64.b64decode(stored)[:16].hex(),
            "final_ciphertext_b64": stored,
        }

    @app.delete("/api/documents/{doc_id}")
    def delete_document(doc_id: int, aegis_session: Optional[str] = Cookie(default=None)):
        session = core.require_session(aegis_session)
        row = own_memo(doc_id, session)
        core.db.delete_document(row["doc_uuid"], session.username)
        return {"ok": True}

    @app.post("/api/documents/{doc_id}/export")
    def export_document(doc_id: int, body: ExportBody, aegis_session: Optional[str] = Cookie(default=None)):
        session = core.require_session(aegis_session)
        if len(body.passphrase) < MIN_PASSPHRASE_LENGTH:
            fail(422, "PASSPHRASE_TOO_SHORT", f"Passphrase minimal {MIN_PASSPHRASE_LENGTH} karakter.")
        row = own_memo(doc_id, session)
        content = memo_plaintext(row, session)
        block = core.block_of(row["doc_uuid"])
        if not block or block["block_hash"] != row["block_hash"] or block["payload_sha256"] != sha256_hex(content):
            fail(409, "BLOCK_MISMATCH", "Segel memo ini tidak cocok dengan rantai blok, jadi paket tidak bisa diekspor.")
        package = package_vault_file(row["doc_uuid"], row["author_username"], row["title_enc"], row["category_enc"], content, body.passphrase, block, row["created_at"])
        return Response(json.dumps(package, indent=2, ensure_ascii=False).encode("utf-8"), media_type="application/json", headers=attachment_headers(f"{row['doc_uuid']}.vault"))

    @app.post("/api/documents/import-verify")
    def import_verify(file: UploadFile = File(...), passphrase: str = Form(""), aegis_session: Optional[str] = Cookie(default=None)):
        core.require_session(aegis_session)
        invalid = {"valid": False, "status": "INVALID_FORMAT", "message": "Berkas bukan paket .vault yang utuh.", "metadata": None, "certificate": None, "decrypted_content": None}
        try:
            package = json.loads(read_upload(file, MAX_VAULT_BYTES, "Paket").decode("utf-8"))
        except (ValueError, UnicodeDecodeError):
            return invalid
        if not isinstance(package, dict) or not isinstance(package.get("metadata"), dict) or not isinstance(package.get("blockchain_certificate"), dict):
            return invalid
        if not passphrase:
            fail(422, "PASSPHRASE_REQUIRED", "Isi passphrase bersama.")
        with core.chain_lock:
            core.reload_chain()
            try:
                result = import_and_verify_vault(package, passphrase, local_blockchain=core.ledger)
            except (KeyError, TypeError, ValueError, AttributeError):
                return invalid
        cert, meta = package["blockchain_certificate"], package["metadata"]
        if result["valid"] and (meta.get("doc_uuid") != cert.get("doc_uuid") or meta.get("author") != cert.get("author")):
            result.update(valid=False, status="TAMPERED_CERTIFICATE", message="Metadata paket berbeda dari sertifikat.")
        if not result["valid"]:
            result["decrypted_content"] = None
        return result

    # ---------- Brankas berkas ----------

    def attachment_public(row: Dict[str, Any]) -> Dict[str, Any]:
        return {"id": row["id"], "att_uuid": row["att_uuid"], "filename": row["original_filename_enc"], "size_bytes": row["file_size_bytes"], "block_index": row["block_index"], "created_at": row["created_at"]}

    @app.get("/api/attachments")
    def list_attachments(aegis_session: Optional[str] = Cookie(default=None)):
        session = core.require_session(aegis_session)
        return [attachment_public(r) for r in core.db.list_attachments(session.username)]

    @app.post("/api/attachments/upload")
    def upload_attachment(file: UploadFile = File(...), aegis_session: Optional[str] = Cookie(default=None)):
        session = core.require_session(aegis_session)
        data = read_upload(file, config.MAX_ATTACHMENT_BYTES, "Berkas")
        if not data:
            fail(422, "FILE_EMPTY", "Berkas kosong. Pilih berkas lain.")
        filename = os.path.basename((file.filename or "berkas").replace("\\", "/")) or "berkas"
        att_uuid = f"ATT-{uuid.uuid4().hex[:12].upper()}"
        digest = sha256_hex(data)
        encrypted = encrypt_file_rc4(data, session.rc4_key)
        path = os.path.join(core.paths.attachments, f"{att_uuid}.rc4")
        with core.chain_lock:
            block = core.seal(att_uuid, session.username, "FILE_ATTACHMENT", digest)
            with open(path, "wb") as f:
                f.write(encrypted)
            att_id = core.db.insert_attachment(att_uuid, session.username, filename, file.content_type or "application/octet-stream", path, len(data), digest, block["index"], block["block_hash"])
        return attachment_public(core.db.get_attachment_by_id(att_id))

    @app.get("/api/attachments/{att_id}/download")
    def download_attachment(att_id: int, aegis_session: Optional[str] = Cookie(default=None)):
        session = core.require_session(aegis_session)
        row = core.db.get_attachment_by_id(att_id)
        if not row or row["owner_username"] != session.username:
            fail(404, "NOT_FOUND", "Berkas tidak ditemukan.")
        try:
            with open(row["encrypted_filepath"], "rb") as f:
                data = decrypt_file_rc4(f.read(), session.rc4_key)
        except (OSError, ValueError):
            fail(409, "FILE_UNREADABLE", "Berkas terenkripsi hilang atau rusak.")
        if sha256_hex(data) != row["original_sha256"]:
            fail(409, "FILE_TAMPERED", "Berkas berubah setelah disimpan, jadi aplikasi menolak mengembalikannya.")
        return Response(data, media_type="application/octet-stream", headers=attachment_headers(row["original_filename_enc"]))

    @app.get("/api/attachments/{att_id}/download-encrypted")
    def download_attachment_encrypted(att_id: int, aegis_session: Optional[str] = Cookie(default=None)):
        session = core.require_session(aegis_session)
        row = core.db.get_attachment_by_id(att_id)
        if not row or row["owner_username"] != session.username:
            fail(404, "NOT_FOUND", "Berkas tidak ditemukan.")
        try:
            with open(row["encrypted_filepath"], "rb") as f:
                data = f.read()
        except OSError:
            fail(409, "FILE_UNREADABLE", "Berkas terenkripsi hilang atau rusak.")
        # Nama UUID, supaya nama asli berkas tidak ikut terbaca saat salinan ini berpindah.
        return Response(data, media_type="application/octet-stream", headers=attachment_headers(f"{row['att_uuid']}.rc4"))

    # ---------- Steganografi ----------

    def load_image(file: UploadFile) -> bytes:
        data = read_upload(file, MAX_IMAGE_BYTES, "Gambar")
        try:
            Image.open(io.BytesIO(data)).verify()
        except (UnidentifiedImageError, OSError, SyntaxError, ValueError, Image.DecompressionBombError):
            fail(422, "IMAGE_INVALID", "Berkas ini bukan gambar yang bisa dibaca. Pilih gambar lain.")
        return data

    @app.post("/api/stego/embed")
    def stego_embed(image: UploadFile = File(...), message: str = Form(...), passphrase: str = Form(""), aegis_session: Optional[str] = Cookie(default=None)):
        core.require_session(aegis_session)
        data = load_image(image)
        try:
            result, report = embed_with_report(data, message, passphrase or None)
        except ValueError as exc:
            fail(422, "EMBED_FAILED", str(exc))
        headers = {**attachment_headers("stego_image.png"), "X-Stego-Report": json.dumps(report)}
        return Response(save_stego_png(result), media_type="image/png", headers=headers)

    @app.post("/api/stego/extract")
    def stego_extract(image: UploadFile = File(...), passphrase: str = Form(""), aegis_session: Optional[str] = Cookie(default=None)):
        core.require_session(aegis_session)
        data = load_image(image)
        try:
            return {"message": extract_message_from_image(data, passphrase or None)}
        except ValueError as exc:
            text = str(exc)
            if "terenkripsi" in text:
                fail(422, "PASSPHRASE_REQUIRED", "Pesan ini terenkripsi. Isi passphrase dari pengirim.")
            if "mendekripsi" in text:
                fail(422, "PASSPHRASE_INVALID", "Passphrase salah, atau pesan di dalam gambar rusak.")
            fail(422, "NO_MESSAGE", "Gambar ini tidak memuat pesan yang bisa dibaca. Minta pengirim mengirim PNG asli sebagai dokumen, bukan foto.")

    # ---------- Audit ----------

    @app.get("/api/blockchain/audit")
    def blockchain_audit(aegis_session: Optional[str] = Cookie(default=None)):
        core.require_session(aegis_session)
        with core.chain_lock:
            valid, message = core.check_chain()
            chain = list(core.ledger.chain)
        if core.ledger_warning and valid:
            valid, message = False, core.ledger_warning
        report = core.db_report()
        if valid and report["ok"]:
            # Database menyimpan hash asli tiap blok, jadi keduanya harus saling cocok.
            by_uuid = {b["doc_uuid"]: b for b in chain}
            rows = [(r["doc_uuid"], r["block_hash"]) for r in core.db.get_raw_rows("documents")]
            rows += [(r["att_uuid"], r["block_hash"]) for r in core.db.get_raw_rows("attachments")]
            for item_uuid, block_hash in rows:
                block = by_uuid.get(item_uuid)
                if not block or block["block_hash"] != block_hash:
                    index = block["index"] if block else "?"
                    valid, message = False, f"Hash blok ke-{index} tidak cocok dengan catatan database."
                    break
        return {"chain": chain, "chain_valid": valid, "message": message, "db": report}

    # ---------- Berkas antarmuka ----------

    if not core.test_mode:
        @app.get("/dev-mock.js")
        def hide_mock():
            fail(404, "NOT_FOUND", "Tidak ditemukan.")

    app.mount("/", StaticFiles(directory=FRONTEND_DIR, html=True), name="frontend")
    return app


# ---------- Jendela desktop ----------


def wait_for_port(port: int, timeout: float = 20.0) -> bool:
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        with socket.socket() as sock:
            sock.settimeout(0.25)
            if sock.connect_ex((HOST, port)) == 0:
                return True
        time.sleep(0.1)
    return False


def available_port(preferred: int) -> int:
    """Memakai port pilihan jika kosong. Jika dipakai program lain, sistem memilihkan port kosong."""
    with socket.socket() as sock:
        try:
            sock.bind((HOST, preferred))
        except OSError:
            sock.bind((HOST, 0))
        return sock.getsockname()[1]


def show_error(message: str) -> None:
    if sys.platform == "win32":
        import ctypes
        ctypes.windll.user32.MessageBoxW(None, message, "AegisVault", 0x10)
    else:
        print(message, file=sys.stderr)


def already_running() -> bool:
    """Dua proses tidak boleh menulis database dan buku besar yang sama."""
    if sys.platform != "win32":
        return False
    import ctypes
    kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
    kernel32.CreateMutexW.restype = ctypes.c_void_p
    # Pegangan mutex sengaja tidak ditutup, supaya bertahan selama proses berjalan.
    kernel32.CreateMutexW(None, False, "Local\\AegisVaultDesktop")
    return ctypes.get_last_error() == 183  # ERROR_ALREADY_EXISTS


def main() -> None:
    import uvicorn

    parser = argparse.ArgumentParser(description="AegisVault Desktop")
    parser.add_argument("--no-window", action="store_true", help="jalankan layanan tanpa jendela desktop")
    args = parser.parse_args()
    if already_running():
        show_error("AegisVault sudah berjalan. Buka jendela yang sudah ada.")
        return
    port = int(os.environ.get("AEGIS_PORT", "8000"))
    if not args.no_window:
        port = available_port(port)
    server = uvicorn.Server(uvicorn.Config(create_app(), host=HOST, port=port, log_level="warning"))

    if args.no_window:
        print(f"AegisVault berjalan di http://{HOST}:{port}")
        server.run()
        return

    import webview

    thread = threading.Thread(target=server.run, daemon=True)
    thread.start()
    if not wait_for_port(port):
        raise SystemExit(f"Layanan gagal berjalan pada port {port}.")
    webview.settings["ALLOW_DOWNLOADS"] = True
    webview.create_window("AegisVault", f"http://{HOST}:{port}", width=1280, height=800, min_size=(1024, 700), background_color="#F5F6F8")
    webview.start()
    server.should_exit = True
    thread.join(timeout=5)


if __name__ == "__main__":
    try:
        main()
    except Exception:
        if not FROZEN:
            raise
        log_path = os.path.join(os.environ["AEGIS_STORAGE_DIR"], "aegisvault-error.log")
        os.makedirs(os.path.dirname(log_path), exist_ok=True)
        with open(log_path, "a", encoding="utf-8") as log:
            log.write(traceback.format_exc() + "\n")
        show_error(f"AegisVault gagal dibuka. Pastikan Microsoft Edge WebView2 Runtime terpasang, lalu coba lagi.\n\nCatatan kesalahan: {log_path}")
