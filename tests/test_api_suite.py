"""
Tes endpoint main.py dengan kriptografi, database, dan buku besar asli.
Hanya pencocokan wajah yang diganti, karena Slice 3 sudah mengujinya di test_system_suite.py
dan tes ini tidak punya foto wajah sungguhan.
"""
import base64
import hashlib
import io
import json
import os
import sqlite3

import numpy as np
import pytest
from fastapi.testclient import TestClient
from PIL import Image, ImageOps

import main
from backend import biometric_auth as biometric
from backend.blockchain_ledger import Blockchain, import_and_verify_vault, mine_pow

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
    assert code(login(client, pin="salah99")) == "PIN_INVALID"
    assert code(login(client, username="tidak_ada")) == "USER_NOT_FOUND"
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
    key = usb / "dongle.key"
    saved = key.read_bytes()
    key.unlink()
    core.monitor.refresh()
    assert code(client.get("/api/documents")) == "DONGLE_REQUIRED"
    key.write_bytes(saved)
    core.monitor.refresh()
    assert client.get("/api/documents").status_code == 200


def use_usb(monkeypatch, core, path):
    path.mkdir(exist_ok=True)
    monkeypatch.setenv("AEGIS_DONGLE_SIMULATION", str(path))
    core.monitor.refresh()


def test_other_usb_cannot_be_enrolled_after_setup(staff, tmp_path, monkeypatch):
    client, core, _ = staff
    use_usb(monkeypatch, core, tmp_path / "usb_lain")
    st = client.get("/api/system/status").json()["dongle"]
    assert st["valid"] is False and st["can_enroll"] is False
    r = client.post("/api/dongle/enroll", json={})
    assert r.status_code == 403 and code(r) == "DONGLE_LOCKED"
    assert not (tmp_path / "usb_lain" / "dongle.key").exists()
    assert code(client.get("/api/documents")) == "DONGLE_REQUIRED"


def test_signed_usb_from_other_install_is_rejected(staff, tmp_path, monkeypatch):
    client, core, _ = staff
    other = tmp_path / "usb_kantor_lain"
    other.mkdir()
    monkeypatch.setenv("AEGIS_DONGLE_SIMULATION", str(other))
    assert core.guard.enroll_dongle()["valid"] is True
    core.monitor.refresh()
    st = client.get("/api/system/status").json()["dongle"]
    assert st["valid"] is False and "bukan dongle" in st["reason"]
    assert code(client.get("/api/documents")) == "DONGLE_REQUIRED"


def test_replace_dongle_needs_pin_and_face(staff, tmp_path, monkeypatch):
    client, core, usb = staff
    use_usb(monkeypatch, core, tmp_path / "usb_baru")
    body = {"username": "staf_budi", "password": "123456", "face_image": GOOD_FACE}
    assert code(client.post("/api/dongle/replace", json={**body, "password": "keliru1"})) == "PIN_INVALID"
    assert code(client.post("/api/dongle/replace", json={**body, "face_image": OTHER_FACE})) == "FACE_MISMATCH"
    assert code(client.post("/api/dongle/replace", json={**body, "username": "tidak_ada"})) == "USER_NOT_FOUND"
    assert client.post("/api/dongle/replace", json=body).status_code == 200
    assert (tmp_path / "usb_baru" / "dongle.key").exists()
    assert client.get("/api/system/status").json()["dongle"]["valid"] is True
    assert client.get("/api/system/status").json()["session"] is None
    monkeypatch.setenv("AEGIS_DONGLE_SIMULATION", str(usb))
    core.monitor.refresh()
    assert client.get("/api/system/status").json()["dongle"]["valid"] is False


def test_no_staff_means_no_replace(env, tmp_path, monkeypatch):
    client, core, usb = env
    enroll(client, core)
    assert client.get("/api/system/status").json()["dongle"]["can_replace"] is False
    use_usb(monkeypatch, core, tmp_path / "usb_lain")
    st = client.get("/api/system/status").json()["dongle"]
    assert st["valid"] is False and st["can_enroll"] is False and st["can_replace"] is False
    r = client.post("/api/dongle/replace", json={"username": "siapa", "password": "123456", "face_image": GOOD_FACE})
    assert r.status_code == 409 and code(r) == "NO_STAFF"
    assert not (tmp_path / "usb_lain" / "dongle.key").exists()
    use_usb(monkeypatch, core, usb)
    assert client.get("/api/system/status").json()["dongle"]["valid"] is True
    signup(client)
    assert client.get("/api/system/status").json()["dongle"]["can_replace"] is True


def test_edited_registry_is_rejected(staff):
    client, core, _ = staff
    data = json.load(open(core.registry_path, encoding="utf-8"))
    data["dongle_id"] = "AEGIS-DONGLE-PALSU"
    json.dump(data, open(core.registry_path, "w", encoding="utf-8"))
    st = client.get("/api/system/status").json()["dongle"]
    assert st["valid"] is False and st["can_enroll"] is False


def test_deleted_registry_does_not_reopen_enroll(staff):
    client, core, _ = staff
    os.remove(core.registry_path)
    st = client.get("/api/system/status").json()["dongle"]
    assert st["valid"] is False and st["can_enroll"] is False
    assert client.post("/api/dongle/enroll", json={}).status_code == 403


def test_new_computer_accepts_existing_dongle(tmp_path, monkeypatch):
    usb = tmp_path / "usb"
    usb.mkdir()
    monkeypatch.setenv("AEGIS_DONGLE_SIMULATION", str(usb))
    first = main.create_app(str(tmp_path / "laptop_a"), test_mode=False).state.core
    first.guard.enroll_dongle()
    app = main.create_app(str(tmp_path / "laptop_b"), test_mode=False)
    with TestClient(app, base_url="http://127.0.0.1") as c:
        app.state.core.monitor.refresh()
        assert c.get("/api/system/status").json()["dongle"]["valid"] is True
        assert app.state.core.registered_dongle()


# ---------- Cek akun dan batas percobaan ----------

def test_check_reports_unregistered_before_camera(env):
    client, core, _ = env
    enroll(client, core)
    signup(client)
    assert code(client.post("/api/auth/check", json={"username": "belum_ada", "password": "123456"})) == "USER_NOT_FOUND"
    assert code(client.post("/api/auth/check", json={"username": "staf_budi", "password": "keliru1"})) == "PIN_INVALID"
    assert client.post("/api/auth/check", json={"username": "staf_budi", "password": "123456"}).json() == {"ok": True}


def test_failed_attempts_are_not_limited(env):
    client, core, _ = env
    enroll(client, core)
    signup(client)
    for _ in range(30):
        assert code(client.post("/api/auth/check", json={"username": "staf_budi", "password": "keliru1"})) == "PIN_INVALID"
        assert code(login(client, pin="keliru1")) == "PIN_INVALID"
    assert login(client).status_code == 200
    assert not os.path.exists(os.path.join(core.paths.root, "login_attempts.json"))


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
    assert res["valid"] is False and res["status"] == "TAMPERED_PACKAGE" and res["decrypted_content"] is None


def test_vault_title_and_category_tamper_detected(staff):
    client, _, _ = staff
    pkg = json.loads(export_vault(client, make_memo(client)))
    pkg["metadata"]["title_plain"] = "Judul palsu"
    res = import_vault(client, json.dumps(pkg).encode())
    assert res["valid"] is False and res["status"] == "TAMPERED_PACKAGE" and res["decrypted_content"] is None
    pkg = json.loads(export_vault(client, make_memo(client)))
    pkg["metadata"]["category_plain"] = "BIASA"
    assert import_vault(client, json.dumps(pkg).encode())["status"] == "TAMPERED_PACKAGE"


def test_vault_forged_sender_on_other_computer_detected(staff, tmp_path):
    client, core, _ = staff
    pkg = json.loads(export_vault(client, make_memo(client)))
    cert = pkg["blockchain_certificate"]
    pkg["metadata"]["author"] = cert["author"] = "pejabat_palsu"
    cert["nonce"], cert["block_hash"] = mine_pow(cert["block_index"], cert["timestamp"], cert["doc_uuid"], cert["author"], cert["payload_sha256"], cert["previous_hash"])
    other = Blockchain(str(tmp_path / "rantai_komputer_lain.json"))
    res = import_and_verify_vault(pkg, "arsip-kuartal-empat", other)
    assert res["valid"] is False and res["status"] == "TAMPERED_PACKAGE"


def test_vault_without_mac_rejected(staff):
    client, _, _ = staff
    pkg = json.loads(export_vault(client, make_memo(client)))
    del pkg["integrity_mac"]
    assert import_vault(client, json.dumps(pkg).encode())["status"] == "INVALID_FORMAT"


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


FILE_PASS = "kirim-berkas-aman"


def upload_file(client, name="rahasia.pdf", data=None):
    data = data if data is not None else os.urandom(2048) + b"%PDF-penanda-asli"
    return client.post("/api/attachments/upload", files={"file": (name, data, "application/pdf")}).json(), data


def export_file(client, att, passphrase=FILE_PASS):
    return client.post(f"/api/attachments/{att['id']}/export", json={"passphrase": passphrase})


def test_file_package_opened_by_other_staff(staff):
    client, _, _ = staff
    att, data = upload_file(client, name="laporan ñ.pdf")
    r = export_file(client, att)
    assert r.status_code == 200 and "laporan%20%C3%B1.pdf.vault" in r.headers["content-disposition"]
    raw = r.content
    assert b"%PDF-penanda-asli" not in raw
    pkg = json.loads(raw)
    assert pkg["package_type"] == "file" and pkg["metadata"]["filename"] == "laporan ñ.pdf"
    # Staf lain tidak punya PIN pengirim, cukup kata sandi bersama.
    client.post("/api/auth/logout", json={})
    signup(client, username="siti", name="Siti", pin="654321")
    login(client, username="siti", pin="654321")
    res = import_vault(client, raw, passphrase=FILE_PASS)
    assert res["valid"] is True and res["status"] == "VALID" and res["package_type"] == "file"
    assert base64.b64decode(res["file_b64"]) == data and res["metadata"]["size_bytes"] == len(data)
    assert res["certificate"]["doc_uuid"] == att["att_uuid"]


def test_file_package_wrong_passphrase_and_tamper(staff):
    client, _, _ = staff
    att, _ = upload_file(client)
    raw = export_file(client, att).content
    res = import_vault(client, raw, passphrase="kata-sandi-keliru")
    assert res["valid"] is False and res["status"] == "INVALID_PASSPHRASE_OR_TAMPERED" and res["file_b64"] is None
    for change in ("payload", "filename", "cert"):
        pkg = json.loads(raw)
        if change == "payload":
            b = bytearray(base64.b64decode(pkg["encrypted_payload"]))
            b[30] ^= 1
            pkg["encrypted_payload"] = base64.b64encode(bytes(b)).decode()
        elif change == "filename":
            pkg["metadata"]["filename"] = "virus.exe"
        else:
            pkg["blockchain_certificate"]["author"] = "penyusup"
        res = import_vault(client, json.dumps(pkg).encode(), passphrase=FILE_PASS)
        assert res["valid"] is False and res["file_b64"] is None, change


def test_file_package_forged_with_new_passphrase_fails_on_certificate(staff):
    client, _, _ = staff
    att, data = upload_file(client)
    pkg = json.loads(export_file(client, att).content)
    from backend.blockchain_ledger import package_file_vault
    block = {**{k: v for k, v in pkg["blockchain_certificate"].items() if k != "block_index"}, "index": pkg["blockchain_certificate"]["block_index"]}
    block["payload_sha256"] = hashlib.sha256(b"berkas palsu").hexdigest()
    forged = package_file_vault(att["att_uuid"], pkg["metadata"]["author"], "rahasia.pdf", "application/pdf", b"berkas palsu", "kunci-penyusup", block)
    res = import_vault(client, json.dumps(forged).encode(), passphrase="kunci-penyusup")
    assert res["valid"] is False and res["status"] == "TAMPERED_CERTIFICATE"


def test_file_package_rules(staff):
    client, core, _ = staff
    att, _ = upload_file(client)
    assert code(export_file(client, att, passphrase="pendek")) == "PASSPHRASE_TOO_SHORT"
    assert client.get(f"/api/attachments/{att['id']}/download-encrypted").status_code in (404, 405)
    client.post("/api/auth/logout", json={})
    assert export_file(client, att).status_code == 401
    signup(client, username="siti", name="Siti", pin="654321")
    login(client, username="siti", pin="654321")
    assert export_file(client, att).status_code == 404
    client.post("/api/auth/logout", json={})
    login(client)
    path = os.path.join(core.paths.attachments, f"{att['att_uuid']}.rc4")
    raw = bytearray(open(path, "rb").read())
    raw[-1] ^= 1
    open(path, "wb").write(raw)
    assert code(export_file(client, att)) == "FILE_TAMPERED"
    os.remove(path)
    assert code(export_file(client, att)) == "FILE_UNREADABLE"


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


def encode(fmt, img=None, **kw):
    out = io.BytesIO()
    (img or Image.open(io.BytesIO(png_bytes(256, 256)))).save(out, format=fmt, **kw)
    return out.getvalue()


def photo_like(w=640, h=480):
    # Gambar bertekstur seperti foto, supaya JPEG punya cukup koefisien untuk pesan.
    y, x = np.mgrid[0:h, 0:w]
    base = np.stack([(x * 0.7) % 256, (y * 0.9) % 256, ((x + y) * 0.4) % 256], -1)
    noise = np.random.default_rng(7).integers(-20, 20, (h, w, 3))
    return Image.fromarray(np.clip(base + noise, 0, 255).astype(np.uint8))


def test_stego_keeps_jpeg_as_jpeg(staff):
    client, _, _ = staff
    cover = encode("JPEG", photo_like(), quality=90)
    r = client.post("/api/stego/embed", files={"image": ("foto rapat.jpeg", cover, "image/jpeg")}, data={"message": "dari jpg", "passphrase": "kunci"})
    assert r.status_code == 200 and r.headers["content-type"] == "image/jpeg"
    assert "foto%20rapat.jpeg" in r.headers["content-disposition"]
    assert Image.open(io.BytesIO(r.content)).format == "JPEG"
    assert abs(len(r.content) - len(cover)) < len(cover) * 0.05
    rep = report_of(r)
    assert rep["format"] == "JPEG" and rep["method"] == "dct" and rep["psnr_db"] > 40
    assert extract(client, r.content, "kunci").json()["message"] == "dari jpg"


@pytest.mark.parametrize("fmt,mime,name", [("BMP", "image/bmp", "a.bmp"), ("TIFF", "image/tiff", "a.tiff"), ("WEBP", "image/webp", "a.webp"), ("PNG", "image/png", "a.png")])
def test_stego_keeps_lossless_format(staff, fmt, mime, name):
    client, _, _ = staff
    cover = encode(fmt, lossless=True) if fmt == "WEBP" else encode(fmt)
    r = client.post("/api/stego/embed", files={"image": (name, cover, mime)}, data={"message": "format sama", "passphrase": ""})
    assert r.status_code == 200 and r.headers["content-type"] == mime
    assert Image.open(io.BytesIO(r.content)).format == fmt and name in r.headers["content-disposition"]
    assert np.abs(rgba_of(cover) - rgba_of(r.content)).max() <= 1
    assert extract(client, r.content).json()["message"] == "format sama"


def test_stego_lossy_webp_stays_webp(staff):
    client, _, _ = staff
    cover = encode("WEBP", quality=70)
    r = embed(client, image=cover, message="webp")
    assert Image.open(io.BytesIO(r.content)).format == "WEBP"
    assert np.abs(rgba_of(cover) - rgba_of(r.content)).max() <= 1
    assert extract(client, r.content).json()["message"] == "webp"


def test_stego_capacity_per_format(staff):
    client, _, _ = staff
    png = client.post("/api/stego/capacity", files={"image": ("a.png", png_bytes(100, 80), "image/png")}).json()
    assert png["format"] == "PNG" and png["capacity_bytes"] == 100 * 80 * 3 // 8 - 4 and png["method"] == "lsb"
    jpg = client.post("/api/stego/capacity", files={"image": ("a.jpg", encode("JPEG", photo_like()), "image/jpeg")}).json()
    assert jpg["format"] == "JPEG" and jpg["method"] == "dct" and jpg["capacity_bytes"] > 1000
    gif = client.post("/api/stego/capacity", files={"image": ("a.gif", encode("GIF"), "image/gif")})
    assert code(gif) == "IMAGE_UNSUPPORTED"
    assert code(embed(client, image=encode("GIF"), message="x")) == "IMAGE_UNSUPPORTED"


def report_of(response):
    return json.loads(response.headers["x-stego-report"])


def rgba_of(data):
    return np.array(Image.open(io.BytesIO(data)).convert("RGBA"), dtype=np.int32)


def test_stego_only_touches_lowest_bit_and_reports_it(staff):
    client, _, _ = staff
    cover = png_bytes(512, 512)
    r = embed(client, image=cover)
    diff = np.abs(rgba_of(cover) - rgba_of(r.content))
    assert diff.max() == 1 and diff[..., 3].max() == 0
    rep = report_of(r)
    assert rep["max_channel_diff"] == 1 and rep["channels_total"] == 512 * 512 * 3
    assert rep["channels_changed"] == int(np.count_nonzero(diff))
    assert rep["psnr_db"] > 60


def test_stego_keeps_transparency(staff):
    client, _, _ = staff
    arr = np.random.default_rng(2).integers(0, 255, (128, 128, 4), dtype=np.uint8)
    arr[:64, :64, 3] = 0
    out = io.BytesIO()
    Image.fromarray(arr).save(out, format="PNG")
    r = embed(client, image=out.getvalue(), message="pesan alfa")
    result = Image.open(io.BytesIO(r.content))
    assert result.mode == "RGBA"
    got = np.array(result, dtype=np.int32)
    assert (got[..., 3] == arr[..., 3]).all() and np.abs(got[..., :3] - arr[..., :3]).max() <= 1
    assert extract(client, r.content).json()["message"] == "pesan alfa"


def test_stego_keeps_phone_photo_orientation(staff):
    client, _, _ = staff
    arr = np.array(photo_like(240, 120))
    arr[:, :120, 0], arr[:, 120:, 2] = 250, 250
    exif = Image.Exif()
    exif[274] = 6
    out = io.BytesIO()
    Image.fromarray(arr).save(out, format="JPEG", quality=95, exif=exif)
    r = embed(client, image=out.getvalue(), message="foto hp")
    result = Image.open(io.BytesIO(r.content))
    # Tanda arah putar ikut tersimpan, jadi foto tampil tegak seperti aslinya.
    assert result.getexif().get(274) == 6
    shown = ImageOps.exif_transpose(result)
    assert shown.size == (120, 240)
    pixels = np.array(shown.convert("RGB"), dtype=np.int32)
    assert pixels[60, 60, 0] > 200 and pixels[180, 60, 2] > 200
    assert extract(client, r.content).json()["message"] == "foto hp"


def test_stego_keeps_16bit_gradient_visible(staff):
    client, _, _ = staff
    ramp = (np.indices((64, 256))[1] * 257).astype(np.uint16)
    out = io.BytesIO()
    Image.fromarray(ramp).save(out, format="PNG")
    r = embed(client, image=out.getvalue(), message="enam belas bit")
    got = np.array(Image.open(io.BytesIO(r.content)).convert("L"), dtype=np.int32)
    assert np.abs(got[0] - np.arange(256)).max() <= 2
    assert extract(client, r.content).json()["message"] == "enam belas bit"


def test_stego_keeps_color_profile_and_dpi(staff):
    client, _, _ = staff
    out = io.BytesIO()
    Image.open(io.BytesIO(png_bytes(64, 64))).save(out, format="PNG", icc_profile=b"profil-warna-contoh", dpi=(300, 300))
    r = embed(client, image=out.getvalue(), message="profil")
    info = Image.open(io.BytesIO(r.content)).info
    assert info["icc_profile"] == b"profil-warna-contoh" and round(info["dpi"][0]) == 300


def test_stego_palette_cover_stays_visually_same(staff):
    client, _, _ = staff
    out = io.BytesIO()
    Image.open(io.BytesIO(png_bytes(64, 64))).convert("P", palette=Image.ADAPTIVE, colors=64).save(out, format="PNG")
    r = embed(client, image=out.getvalue(), message="palet")
    assert np.abs(rgba_of(out.getvalue()) - rgba_of(r.content)).max() <= 1


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


def rewrite_chain(core):
    chain = json.load(open(core.paths.blockchain, encoding="utf-8"))
    chain[1]["author"] = "penyusup"
    prev = chain[0]["block_hash"]
    for blk in chain[1:]:
        blk["previous_hash"] = prev
        blk["nonce"], blk["block_hash"] = mine_pow(blk["index"], blk["timestamp"], blk["doc_uuid"], blk["author"], blk["payload_sha256"], blk["previous_hash"])
        prev = blk["block_hash"]
    json.dump(chain, open(core.paths.blockchain, "w", encoding="utf-8"))


def test_remined_chain_detected_and_restorable(staff):
    client, core, _ = staff
    memo = make_memo(client)
    rewrite_chain(core)
    a = client.get("/api/blockchain/audit").json()
    assert a["chain_valid"] is False and "tanda tangan" in a["message"]
    assert code(client.post("/api/documents", json={"title": "x", "category": "y", "content": "z"})) == "CHAIN_INVALID"
    assert client.post("/api/system/restore", json={}).json() == {"restored": ["rantai blok"]}
    a = client.get("/api/blockchain/audit").json()
    assert a["chain_valid"] is True and a["chain"][1]["author"] == "staf_budi"
    assert client.get(f"/api/documents/{memo['id']}").json()["verified"] is True


def test_audit_catches_database_and_chain_disagreement(staff):
    client, core, _ = staff
    make_memo(client)
    with sqlite3.connect(core.paths.db) as db:
        db.execute("UPDATE documents SET block_hash='000palsu'")
    core.db.update_checksum()
    a = client.get("/api/blockchain/audit").json()
    assert a["chain_valid"] is False and "catatan database" in a["message"]


def test_recomputed_sha256_still_detected(staff):
    client, core, _ = staff
    make_memo(client)
    with sqlite3.connect(core.paths.db) as db:
        db.execute("UPDATE documents SET block_index=99")
    open(core.paths.db_checksum, "w", encoding="ascii").write(hashlib.sha256(open(core.paths.db, "rb").read()).hexdigest())
    st = client.get("/api/system/status").json()["db"]
    assert st["status"] == "TAMPERED" and "HMAC" in st["message"]
    assert code(client.get("/api/documents")) == "DB_TAMPERED"


def test_tampered_database_restores_without_login(staff):
    client, core, usb = staff
    memo = make_memo(client)
    client.post("/api/auth/logout", json={})
    with open(core.paths.db, "ab") as f:
        f.write(b"\x00")
    assert code(login(client)) == "DB_TAMPERED"
    assert client.get("/api/system/status").json()["db"]["ok"] is False
    assert client.post("/api/system/restore", json={}).json() == {"restored": ["database"]}
    assert client.get("/api/system/status").json()["db"]["ok"] is True
    assert login(client).status_code == 200
    assert client.get(f"/api/documents/{memo['id']}").json()["content"] == MEMO_TEXT


def test_tampered_backup_is_not_restored(staff):
    client, core, _ = staff
    make_memo(client)
    with open(core.paths.db, "ab") as f:
        f.write(b"\x00")
    with open(core.db.backup_path, "ab") as f:
        f.write(b"\x01")
    r = client.post("/api/system/restore", json={})
    assert r.status_code == 409 and code(r) == "NO_BACKUP"


def test_restore_needs_registered_dongle(staff, tmp_path, monkeypatch):
    client, core, _ = staff
    use_usb(monkeypatch, core, tmp_path / "usb_lain")
    assert code(client.post("/api/system/restore", json={})) == "DONGLE_REQUIRED"


def test_install_from_older_version_keeps_working(staff, tmp_path):
    client, core, usb = staff
    memo = make_memo(client)
    for path in (core.db.hmac_path, core.db.backup_path, core.chain_sig_path, core.chain_backup_path, core.registry_path):
        os.remove(path)
    app = main.create_app(str(core.paths.root), test_mode=False)
    with TestClient(app, base_url="http://127.0.0.1") as c:
        app.state.core.monitor.refresh()
        st = c.get("/api/system/status").json()
        assert st["db"]["ok"] is True and st["dongle"]["valid"] is True
        assert login(c).status_code == 200
        assert c.get("/api/blockchain/audit").json()["chain_valid"] is True
        assert c.get(f"/api/documents/{memo['id']}").json()["content"] == MEMO_TEXT


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


# ---------- Nama berkas unduhan ----------

@pytest.mark.parametrize("chosen,suggested,expected", [
    ("C:/u/rahasia", "foto kegiatan.jpg", "C:/u/rahasia.jpg"),
    ("C:/u/rahasia.JPEG", "foto.jpg", "C:/u/rahasia.JPEG"),
    ("C:/u/rahasia.png", "foto.png", "C:/u/rahasia.png"),
    ("C:/u/laporan.v2", "gambar.png", "C:/u/laporan.v2.png"),
    ("C:/u/scan.tiff", "scan.tif", "C:/u/scan.tiff"),
    ("C:/u/paket", "memo.vault", "C:/u/paket.vault"),
    ("C:/u/catatan", "README", "C:/u/catatan"),
])
def test_download_keeps_original_extension(chosen, suggested, expected):
    assert main.with_original_extension(chosen, suggested) == expected
