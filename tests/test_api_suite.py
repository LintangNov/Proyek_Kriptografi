"""
Tes endpoint main.py dengan kriptografi, database, dan buku besar asli.
Hanya pencocokan wajah yang diganti, karena Slice 3 sudah mengujinya di test_system_suite.py
dan tes ini tidak punya foto wajah sungguhan.
"""
import base64
import io
import json
import os
import sqlite3

import numpy as np
import pytest
from fastapi.testclient import TestClient
from PIL import Image

import main
from backend import biometric_auth as biometric

GOOD_FACE = "data:image/jpeg;base64,V0FKQUg="
OTHER_FACE = "data:image/jpeg;base64,TEFJTg=="
NO_FACE = "data:image/jpeg;base64,S09TT05H"
MEMO_TEXT = "Rapat Anggaran Rahasia 2026!"


def fake_enroll(username, frame, storage_dir=None):
    if frame == NO_FACE:
        raise biometric.NoFaceDetectedError("tidak ada wajah")
    return {"username": username, "face_model_path": f"{storage_dir}/faces/{username}.npy"}


def fake_verify(username, frame, storage_dir=None):
    if frame == NO_FACE:
        raise biometric.NoFaceDetectedError("tidak ada wajah")
    return {"match": frame == GOOD_FACE, "score": 0.9 if frame == GOOD_FACE else 0.1}


@pytest.fixture
def env(tmp_path, monkeypatch):
    usb = tmp_path / "usb"
    usb.mkdir()
    monkeypatch.setenv("AEGIS_DONGLE_SIMULATION", str(usb))
    monkeypatch.setattr(biometric, "enroll_face", fake_enroll)
    monkeypatch.setattr(biometric, "verify_face", fake_verify)
    app = main.create_app(str(tmp_path / "storage"), test_mode=False)
    with TestClient(app, base_url="http://127.0.0.1") as client:
        yield client, app.state.core, usb


def enroll(client, core):
    assert client.post("/api/dongle/enroll", json={}).status_code == 200
    core.monitor.refresh()


def signup(client, username="staf_budi", name="Staf Budi", pin="123456"):
    r = client.post("/api/auth/register", json={"username": username, "full_name": name, "password": pin, "face_image": GOOD_FACE})
    assert r.status_code == 200, r.text


def login(client, username="staf_budi", pin="123456", face=GOOD_FACE):
    return client.post("/api/auth/login", json={"username": username, "password": pin, "face_image": face})


@pytest.fixture
def staff(env):
    client, core, usb = env
    enroll(client, core)
    signup(client)
    assert login(client).status_code == 200
    return client, core, usb


def make_memo(client, title="Memo Anggaran Kuartal IV", content=MEMO_TEXT):
    r = client.post("/api/documents", json={"title": title, "category": "Sangat rahasia", "content": content})
    assert r.status_code == 200, r.text
    return r.json()


def png_bytes(w=64, h=64, seed=1):
    arr = np.random.default_rng(seed).integers(0, 255, (h, w, 3), dtype=np.uint8)
    out = io.BytesIO()
    Image.fromarray(arr, "RGB").save(out, format="PNG")
    return out.getvalue()


def code(response):
    return response.json()["detail"]["code"]


# ---------- Dongle dan login ----------

def test_status_without_dongle_blocks_login(env):
    client, core, _ = env
    st = client.get("/api/system/status").json()
    assert st["dongle"]["valid"] is False and st["session"] is None and st["test_mode"] is False
    assert st["biometric"]["face_verification_enabled"] is True
    assert code(login(client)) == "DONGLE_REQUIRED"


def test_enroll_opens_status(env):
    client, core, usb = env
    enroll(client, core)
    assert (usb / "dongle.key").exists()
    assert client.get("/api/system/status").json()["dongle"]["valid"] is True


def test_register_validation(env):
    client, core, _ = env
    enroll(client, core)
    base = {"username": "siti", "full_name": "Siti", "password": "123456", "face_image": GOOD_FACE}
    assert code(client.post("/api/auth/register", json={**base, "username": "si ti"})) == "USERNAME_INVALID"
    assert code(client.post("/api/auth/register", json={**base, "password": "123"})) == "PIN_TOO_SHORT"
    assert code(client.post("/api/auth/register", json={**base, "face_image": NO_FACE})) == "NO_FACE"
    assert client.post("/api/auth/register", json=base).status_code == 200
    assert code(client.post("/api/auth/register", json=base)) == "USERNAME_TAKEN"


def test_password_not_stored_plain(env):
    client, core, _ = env
    enroll(client, core)
    signup(client, pin="rahasia-sekali")
    raw = json.dumps(core.db.get_raw_rows("users"))
    assert "rahasia-sekali" not in raw and "Staf Budi" not in raw


def test_login_outcomes(env):
    client, core, _ = env
    enroll(client, core)
    signup(client)
    assert code(login(client, pin="salah99")) == "CREDENTIALS_INVALID"
    assert code(login(client, username="tidak_ada")) == "CREDENTIALS_INVALID"
    assert code(login(client, face=OTHER_FACE)) == "FACE_MISMATCH"
    assert code(login(client, face=NO_FACE)) == "NO_FACE"
    assert client.get("/api/system/status").json()["session"] is None
    r = login(client)
    assert r.json() == {"username": "staf_budi", "full_name": "Staf Budi"}
    cookie = r.headers["set-cookie"].lower()
    assert "httponly" in cookie and "samesite=strict" in cookie
    assert client.get("/api/system/status").json()["session"]["username"] == "staf_budi"
    assert client.post("/api/auth/logout", json={}).status_code == 200
    assert client.get("/api/system/status").json()["session"] is None
    assert code(client.get("/api/documents")) == "SESSION_REQUIRED"


def test_routes_need_session(env):
    client, core, _ = env
    enroll(client, core)
    for method, path in [("get", "/api/documents"), ("get", "/api/attachments"), ("get", "/api/blockchain/audit"), ("get", "/api/documents/1"), ("get", "/api/documents/1/ciphertext"), ("delete", "/api/documents/1"), ("get", "/api/attachments/1/download")]:
        assert getattr(client, method)(path).status_code == 401, path


def test_removing_dongle_locks_api(staff):
    client, core, usb = staff
    (usb / "dongle.key").unlink()
    core.monitor.refresh()
    assert code(client.get("/api/documents")) == "DONGLE_REQUIRED"
    client.post("/api/dongle/enroll", json={})
    core.monitor.refresh()
    assert client.get("/api/documents").status_code == 200


# ---------- Memo (AC-03) ----------

def test_memo_lifecycle_encrypted_at_rest(staff):
    client, core, _ = staff
    memo = make_memo(client)
    assert memo["title"] == "Memo Anggaran Kuartal IV" and memo["block_index"] == 1 and memo["block_hash"].startswith("000")
    with sqlite3.connect(core.paths.db) as conn:
        row = conn.execute("SELECT title_enc, category_enc, content_super_enc FROM documents").fetchone()
    joined = " ".join(row)
    for plain in ("Anggaran", "rahasia", "Rapat"):
        assert plain not in joined
    detail = client.get(f"/api/documents/{memo['id']}").json()
    assert detail["content"] == MEMO_TEXT and detail["verified"] is True and isinstance(detail["nonce"], int)
    assert client.delete(f"/api/documents/{memo['id']}").status_code == 200
    assert client.get("/api/documents").json() == []
    assert len(json.load(open(core.paths.blockchain, encoding="utf-8"))) == 2


def test_ciphertext_shows_stored_value(staff):
    client, core, _ = staff
    memo = make_memo(client)
    data = client.get(f"/api/documents/{memo['id']}/ciphertext").json()
    stored = core.db.get_document_by_id(memo["id"])["content_super_enc"]
    assert data["final_ciphertext_b64"] == stored
    assert data["aes_iv_hex"] == base64.b64decode(stored)[:16].hex()
    assert data["plaintext"] == MEMO_TEXT and len(data["vigenere_ciphertext_hex"]) == len(MEMO_TEXT.encode()) * 2
    assert "key" not in " ".join(data)


def test_memo_validation(staff):
    client, _, _ = staff
    assert code(client.post("/api/documents", json={"title": " ", "category": "Rahasia", "content": "x"})) == "MEMO_INCOMPLETE"


def test_staff_cannot_read_others_memo(staff):
    client, core, _ = staff
    memo = make_memo(client)
    client.post("/api/auth/logout", json={})
    signup(client, username="siti", name="Siti", pin="654321")
    assert login(client, username="siti", pin="654321").status_code == 200
    assert client.get("/api/documents").json() == []
    assert client.get(f"/api/documents/{memo['id']}").status_code == 404
    assert client.delete(f"/api/documents/{memo['id']}").status_code == 404


# ---------- Paket .vault (AC-06) ----------

def export_vault(client, memo, passphrase="arsip-kuartal-empat"):
    r = client.post(f"/api/documents/{memo['id']}/export", json={"passphrase": passphrase})
    assert r.status_code == 200, r.text
    assert ".vault" in r.headers["content-disposition"]
    return r.content


def import_vault(client, raw, passphrase="arsip-kuartal-empat", name="paket.vault"):
    r = client.post("/api/documents/import-verify", files={"file": (name, raw, "application/json")}, data={"passphrase": passphrase})
    assert r.status_code == 200, r.text
    return r.json()


def test_vault_roundtrip_valid(staff):
    client, _, _ = staff
    raw = export_vault(client, make_memo(client))
    res = import_vault(client, raw)
    assert res["valid"] is True and res["status"] == "VALID" and res["decrypted_content"] == MEMO_TEXT


def test_vault_short_passphrase_rejected(staff):
    client, _, _ = staff
    memo = make_memo(client)
    assert code(client.post(f"/api/documents/{memo['id']}/export", json={"passphrase": "pendek"})) == "PASSPHRASE_TOO_SHORT"


def test_vault_wrong_passphrase(staff):
    client, _, _ = staff
    res = import_vault(client, export_vault(client, make_memo(client)), passphrase="passphrase-keliru")
    assert res["valid"] is False and res["decrypted_content"] is None
    assert res["status"] in ("INVALID_PASSPHRASE_OR_TAMPERED", "TAMPERED_CONTENT")


def test_vault_tampered_ciphertext_detected(staff):
    client, _, _ = staff
    pkg = json.loads(export_vault(client, make_memo(client)))
    b = bytearray(base64.b64decode(pkg["encrypted_payload"]))
    b[20] ^= 1
    pkg["encrypted_payload"] = base64.b64encode(bytes(b)).decode()
    res = import_vault(client, json.dumps(pkg).encode())
    assert res["valid"] is False and res["decrypted_content"] is None


def test_vault_tampered_certificate_detected(staff):
    client, _, _ = staff
    pkg = json.loads(export_vault(client, make_memo(client)))
    pkg["blockchain_certificate"]["author"] = "penyusup"
    res = import_vault(client, json.dumps(pkg).encode())
    assert res["valid"] is False and res["status"] == "TAMPERED_CERTIFICATE"


def test_vault_metadata_author_mismatch_detected(staff):
    client, _, _ = staff
    pkg = json.loads(export_vault(client, make_memo(client)))
    pkg["metadata"]["author"] = "penyusup"
    res = import_vault(client, json.dumps(pkg).encode())
    assert res["valid"] is False and res["status"] == "TAMPERED_CERTIFICATE" and res["decrypted_content"] is None


@pytest.mark.parametrize("raw", [b"bukan json", b"[]", b'{"vault_version":"1.0"}', b"\xff\xfe"])
def test_vault_bad_format(staff, raw):
    client, _, _ = staff
    assert import_vault(client, raw)["status"] == "INVALID_FORMAT"


def test_vault_path_text_is_not_opened_as_file(staff):
    client, core, _ = staff
    res = import_vault(client, json.dumps(core.paths.blockchain).encode())
    assert res["status"] == "INVALID_FORMAT"


# ---------- Brankas (AC-04) ----------

def test_attachment_roundtrip_encrypted(staff):
    client, core, _ = staff
    data = os.urandom(4096) + b"%PDF-penanda-asli"
    r = client.post("/api/attachments/upload", files={"file": ("laporan ñ.pdf", data, "application/pdf")})
    assert r.status_code == 200, r.text
    att = r.json()
    assert att["filename"] == "laporan ñ.pdf" and att["size_bytes"] == len(data)
    on_disk = open(os.path.join(core.paths.attachments, f"{att['att_uuid']}.rc4"), "rb").read()
    assert b"%PDF-penanda-asli" not in on_disk and len(on_disk) == len(data) + 16
    d = client.get(f"/api/attachments/{att['id']}/download")
    assert d.content == data and "filename*=UTF-8''laporan%20%C3%B1.pdf" in d.headers["content-disposition"]


def test_attachment_path_traversal_name_is_flattened(staff):
    client, _, _ = staff
    r = client.post("/api/attachments/upload", files={"file": ("..\\..\\jahat.txt", b"isi", "text/plain")})
    assert r.json()["filename"] == "jahat.txt"


def test_attachment_size_limit(staff):
    client, _, _ = staff
    r = client.post("/api/attachments/upload", files={"file": ("besar.bin", b"0" * (20 * 1024 * 1024 + 1), "application/octet-stream")})
    assert r.status_code == 413 and code(r) == "FILE_TOO_LARGE"


def test_attachment_tamper_detected(staff):
    client, core, _ = staff
    att = client.post("/api/attachments/upload", files={"file": ("a.bin", b"data penting", "application/octet-stream")}).json()
    path = os.path.join(core.paths.attachments, f"{att['att_uuid']}.rc4")
    raw = bytearray(open(path, "rb").read())
    raw[-1] ^= 1
    open(path, "wb").write(raw)
    assert code(client.get(f"/api/attachments/{att['id']}/download")) == "FILE_TAMPERED"


# ---------- Steganografi (AC-05) ----------

def embed(client, image=None, message="x" * 500, passphrase=""):
    return client.post("/api/stego/embed", files={"image": ("s.png", image or png_bytes(512, 512), "image/png")}, data={"message": message, "passphrase": passphrase})


def extract(client, image, passphrase=""):
    return client.post("/api/stego/extract", files={"image": ("s.png", image, "image/png")}, data={"passphrase": passphrase})


def test_stego_roundtrip_raw(staff):
    client, _, _ = staff
    r = embed(client)
    assert r.status_code == 200 and r.headers["content-type"] == "image/png"
    assert extract(client, r.content).json()["message"] == "x" * 500


def test_stego_roundtrip_encrypted(staff):
    client, _, _ = staff
    r = embed(client, message="rahasia", passphrase="kunci-bersama")
    assert extract(client, r.content, "kunci-bersama").json()["message"] == "rahasia"
    assert code(extract(client, r.content)) == "PASSPHRASE_REQUIRED"
    assert code(extract(client, r.content, "kunci-keliru")) == "PASSPHRASE_INVALID"


def test_stego_jpeg_cover_exports_png(staff):
    client, _, _ = staff
    out = io.BytesIO()
    Image.open(io.BytesIO(png_bytes(128, 128))).save(out, format="JPEG")
    r = embed(client, image=out.getvalue(), message="dari jpg")
    assert Image.open(io.BytesIO(r.content)).format == "PNG"
    assert extract(client, r.content).json()["message"] == "dari jpg"


def test_stego_errors(staff):
    client, _, _ = staff
    assert code(embed(client, image=png_bytes(8, 8), message="x" * 200)) == "EMBED_FAILED"
    assert code(embed(client, image=b"bukan gambar", message="x")) == "IMAGE_INVALID"
    assert code(extract(client, png_bytes(64, 64))) == "NO_MESSAGE"


# ---------- Audit ----------

def test_audit_valid_then_block_tampered(staff):
    client, core, _ = staff
    make_memo(client)
    make_memo(client, title="Kedua")
    a = client.get("/api/blockchain/audit").json()
    assert a["chain_valid"] is True and len(a["chain"]) == 3 and a["db"]["status"] == "OK"
    chain = json.load(open(core.paths.blockchain, encoding="utf-8"))
    chain[1]["author"] = "penyusup"
    json.dump(chain, open(core.paths.blockchain, "w", encoding="utf-8"))
    a = client.get("/api/blockchain/audit").json()
    assert a["chain_valid"] is False and "ke-1" in a["message"]
    r = client.post("/api/documents", json={"title": "Baru", "category": "Rahasia", "content": "x"})
    assert code(r) == "CHAIN_INVALID"


def test_corrupt_ledger_is_reported_not_overwritten(staff):
    client, core, _ = staff
    open(core.paths.blockchain, "w", encoding="utf-8").write("{rusak")
    a = client.get("/api/blockchain/audit").json()
    assert a["chain_valid"] is False
    assert open(core.paths.blockchain, encoding="utf-8").read() == "{rusak"


def test_corrupt_ledger_at_startup_is_preserved(tmp_path, monkeypatch):
    monkeypatch.setenv("AEGIS_DONGLE_SIMULATION", str(tmp_path))
    storage = tmp_path / "s"
    storage.mkdir()
    (storage / "blockchain.json").write_text("{rusak", encoding="utf-8")
    core = main.create_app(str(storage), test_mode=False).state.core
    assert core.ledger_warning
    assert any(n.startswith("blockchain.json.rusak-") for n in os.listdir(storage))


def test_db_tamper_reported_and_blocks_reads(staff):
    client, core, _ = staff
    make_memo(client)
    with open(core.paths.db, "ab") as f:
        f.write(b"\x00")
    st = client.get("/api/system/status").json()
    assert st["db"]["status"] == "TAMPERED"
    assert code(client.get("/api/documents")) == "DB_TAMPERED"
    a = client.get("/api/blockchain/audit").json()
    assert a["db"]["status"] == "TAMPERED" and a["db"]["expected"] != a["db"]["actual"]


# ---------- Pengamanan layanan lokal dan berkas antarmuka ----------

def test_foreign_origin_rejected(staff):
    client, _, _ = staff
    r = client.post("/api/auth/logout", json={}, headers={"Origin": "https://situs-jahat.example"})
    assert r.status_code == 403 and code(r) == "ORIGIN_DENIED"
    assert client.get("/api/system/status").json()["session"] is not None
    assert client.post("/api/auth/logout", json={}, headers={"Origin": "http://127.0.0.1"}).status_code == 200


def test_foreign_host_rejected(env):
    client, _, _ = env
    assert client.get("/api/system/status", headers={"Host": "situs-jahat.example"}).status_code == 400


def test_frontend_served_with_headers(env):
    client, _, _ = env
    r = client.get("/")
    assert r.status_code == 200 and "AegisVault" in r.text
    assert "default-src 'self'" in r.headers["content-security-policy"]
    assert client.get("/assets/styles.css").status_code == 200
    assert client.get("/app.js").status_code == 200


def test_mock_hidden_outside_test_mode(env, tmp_path, monkeypatch):
    client, _, _ = env
    assert client.get("/dev-mock.js").status_code == 404
    app = main.create_app(str(tmp_path / "uji"), test_mode=True)
    with TestClient(app, base_url="http://127.0.0.1") as c:
        assert c.get("/dev-mock.js").status_code == 200
        assert c.get("/api/system/status").json()["test_mode"] is True
