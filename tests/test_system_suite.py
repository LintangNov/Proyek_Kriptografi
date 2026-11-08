"""
Pengujian otomatis Slice 2: Database Layer dan Hardware Dongle Security.

Jalankan dengan:
    python -m unittest tests.test_system_suite -v

Seluruh pengujian memakai folder sementara. Data di storage/ dan USB nyata tidak disentuh.
"""

import base64
import json
import os
import shutil
import sqlite3
import sys
import tempfile
import time
import unittest
from unittest import mock

import cv2
import numpy as np

from backend import biometric_auth
from backend import config
from backend import dongle_guard
from backend.crypto_engine import hash_password, sha256_hex, super_encrypt_with_passphrase
from backend.database import (
    STATUS_MISSING_CHECKSUM,
    STATUS_OK,
    STATUS_TAMPERED,
    Database,
    DatabaseIntegrityError,
    DuplicateRecordError,
    decrypt_field,
    encrypt_field,
)
from backend.dongle_guard import (
    DongleError,
    DongleGuard,
    DongleMonitor,
    MultipleDrivesError,
    compute_signature,
)


class TempDirTestCase(unittest.TestCase):
    """Dasar: menyediakan folder sementara yang dibersihkan setelah tiap pengujian."""

    def make_dir(self) -> str:
        path = tempfile.mkdtemp(prefix="aegis_test_")
        self.addCleanup(shutil.rmtree, path, ignore_errors=True)
        return path


# =====================================================================
# config.py
# =====================================================================

class TestConfig(TempDirTestCase):
    def test_ensure_storage_dirs_creates_all_folders(self):
        root = os.path.join(self.make_dir(), "storage")
        paths = config.ensure_storage_dirs(root)
        self.assertTrue(os.path.isdir(paths.root))
        self.assertTrue(os.path.isdir(os.path.join(root, "faces")))
        self.assertTrue(os.path.isdir(os.path.join(root, "attachments")))

    def test_ensure_storage_dirs_is_idempotent(self):
        root = os.path.join(self.make_dir(), "storage")
        first = config.ensure_storage_dirs(root)
        second = config.ensure_storage_dirs(root)
        self.assertEqual(first, second)

    def test_storage_paths_filenames(self):
        paths = config.get_storage_paths(self.make_dir())
        self.assertEqual(os.path.basename(paths.db), "aegis_vault.db")
        self.assertEqual(os.path.basename(paths.db_checksum), "db_checksum.sha256")
        self.assertEqual(os.path.basename(paths.blockchain), "blockchain.json")


# =====================================================================
# database.py
# =====================================================================

class TestFieldEncryption(unittest.TestCase):
    KEY = bytes(range(16))

    def test_roundtrip_including_unicode(self):
        for text in ("Budi Santoso", "", "Rahasia \u2603 \u00e9", "x" * 500):
            self.assertEqual(decrypt_field(encrypt_field(text, self.KEY), self.KEY), text)

    def test_random_iv_gives_different_ciphertexts(self):
        self.assertNotEqual(encrypt_field("sama", self.KEY), encrypt_field("sama", self.KEY))

    def test_ciphertext_hides_plaintext(self):
        token = encrypt_field("Rapat Anggaran Rahasia 2026!", self.KEY)
        self.assertNotIn("Rapat", token)

    def test_wrong_key_or_garbage_raises(self):
        token = encrypt_field("data", self.KEY)
        with self.assertRaises(DatabaseIntegrityError):
            decrypt_field(token, bytes(16))
        with self.assertRaises(DatabaseIntegrityError):
            decrypt_field("bukan-base64!!", self.KEY)
        with self.assertRaises(DatabaseIntegrityError):
            decrypt_field("QUJD", self.KEY)


class TestDatabase(TempDirTestCase):
    def setUp(self):
        self.storage = self.make_dir()
        self.db = Database(self.storage)

    def stored_checksum(self) -> str:
        with open(self.db.paths.db_checksum, encoding="ascii") as f:
            return f.read()

    def _add_user(self, username="staf_budi"):
        pw_hash, salt_hex = hash_password("PIN-12345")
        return self.db.create_user(
            username, "Budi Santoso", "Staf Arsip", pw_hash, salt_hex,
            os.path.join("storage", "faces", f"{username}.npy"),
        )

    def _add_document(self, doc_uuid="DOC-0001", author="staf_budi"):
        cipher, _salt = super_encrypt_with_passphrase("Rapat Anggaran Rahasia 2026!", "kunci")
        return self.db.insert_document(
            doc_uuid, author, "Memo Anggaran Kuartal IV", "SANGAT RAHASIA",
            cipher, sha256_hex("Rapat Anggaran Rahasia 2026!"), 1, "000abc",
        ), cipher

    def _add_attachment(self, att_uuid="ATT-0001", owner="staf_budi"):
        return self.db.insert_attachment(
            att_uuid, owner, "laporan_keuangan.pdf", "application/pdf",
            os.path.join("storage", "attachments", f"{att_uuid}.rc4"),
            2048, sha256_hex("isi berkas"), 2, "000def",
        )

    # --- inisialisasi ---

    def test_init_creates_database_and_checksum(self):
        self.assertTrue(os.path.isfile(self.db.paths.db))
        self.assertTrue(os.path.isfile(self.db.paths.db_checksum))
        self.assertEqual(self.db.check_integrity()["status"], STATUS_OK)

    def test_init_creates_all_three_tables(self):
        with sqlite3.connect(self.db.paths.db) as conn:
            names = {r[0] for r in conn.execute("SELECT name FROM sqlite_master WHERE type='table'")}
        self.assertTrue({"users", "documents", "attachments"} <= names)

    def test_reopen_existing_database_keeps_data(self):
        self._add_user()
        reopened = Database(self.storage)
        self.assertEqual(reopened.get_user("staf_budi")["full_name_enc"], "Budi Santoso")
        self.assertTrue(reopened.check_integrity()["ok"])

    # --- users ---

    def test_user_fields_encrypted_at_rest_and_decrypted_on_read(self):
        self._add_user()
        raw = self.db.get_raw_rows("users")[0]
        self.assertNotIn("Budi", raw["full_name_enc"])
        self.assertNotIn("Arsip", raw["role_enc"])
        user = self.db.get_user("staf_budi")
        self.assertEqual(user["full_name_enc"], "Budi Santoso")
        self.assertEqual(user["role_enc"], "Staf Arsip")
        self.assertEqual(len(user["password_salt"]), 32)
        self.assertEqual(len(user["password_hash"]), 64)

    def test_duplicate_username_rejected(self):
        self._add_user()
        with self.assertRaises(DuplicateRecordError):
            self._add_user()

    def test_user_lookup_helpers(self):
        self.assertIsNone(self.db.get_user("tidak_ada"))
        self.assertFalse(self.db.user_exists("staf_budi"))
        self._add_user("staf_budi")
        self._add_user("staf_siti")
        self.assertTrue(self.db.user_exists("staf_siti"))
        self.assertEqual([u["username"] for u in self.db.list_users()], ["staf_budi", "staf_siti"])
        self.assertTrue(self.db.delete_user("staf_siti"))
        self.assertFalse(self.db.delete_user("staf_siti"))

    def test_blank_username_rejected(self):
        with self.assertRaises(ValueError):
            self.db.create_user("  ", "A", "B", "h", "s", "p")

    # --- documents ---

    def test_document_fields_encrypted_and_super_content_untouched(self):
        _id, cipher = self._add_document()
        raw = self.db.get_raw_rows("documents")[0]
        self.assertNotIn("Anggaran", raw["title_enc"])
        self.assertNotIn("RAHASIA", raw["category_enc"])
        self.assertEqual(raw["content_super_enc"], cipher)

        doc = self.db.get_document("DOC-0001")
        self.assertEqual(doc["title_enc"], "Memo Anggaran Kuartal IV")
        self.assertEqual(doc["category_enc"], "SANGAT RAHASIA")
        self.assertEqual(doc["block_index"], 1)

    def test_database_file_has_no_readable_plaintext(self):
        """AC-03: file .db dibuka paksa tidak menampakkan teks asli."""
        self._add_user()
        self._add_document()
        self._add_attachment()
        with open(self.db.paths.db, "rb") as f:
            blob = f.read()
        for secret in (b"Budi Santoso", b"Staf Arsip", b"Memo Anggaran", b"SANGAT RAHASIA",
                       b"laporan_keuangan", b"application/pdf", b"Rapat Anggaran"):
            self.assertNotIn(secret, blob)

    def test_document_listing_and_author_scoped_delete(self):
        self._add_document("DOC-0001", "staf_budi")
        self._add_document("DOC-0002", "staf_siti")
        self.assertEqual([d["doc_uuid"] for d in self.db.list_documents()], ["DOC-0002", "DOC-0001"])
        self.assertEqual([d["doc_uuid"] for d in self.db.list_documents("staf_budi")], ["DOC-0001"])

        self.assertFalse(self.db.delete_document("DOC-0001", author_username="staf_siti"))
        self.assertIsNotNone(self.db.get_document("DOC-0001"))
        self.assertTrue(self.db.delete_document("DOC-0001", author_username="staf_budi"))
        self.assertIsNone(self.db.get_document("DOC-0001"))
        self.assertTrue(self.db.delete_document("DOC-0002"))

    def test_duplicate_document_uuid_rejected(self):
        self._add_document()
        with self.assertRaises(DuplicateRecordError):
            self._add_document()

    def test_get_document_by_id(self):
        doc_id, _ = self._add_document()
        self.assertEqual(self.db.get_document_by_id(doc_id)["doc_uuid"], "DOC-0001")
        self.assertIsNone(self.db.get_document_by_id(9999))

    # --- attachments ---

    def test_attachment_fields_encrypted_and_decrypted(self):
        self._add_attachment()
        raw = self.db.get_raw_rows("attachments")[0]
        self.assertNotIn("laporan", raw["original_filename_enc"])
        self.assertNotIn("pdf", raw["mime_type_enc"])
        att = self.db.get_attachment("ATT-0001")
        self.assertEqual(att["original_filename_enc"], "laporan_keuangan.pdf")
        self.assertEqual(att["mime_type_enc"], "application/pdf")
        self.assertEqual(att["file_size_bytes"], 2048)

    def test_attachment_listing_and_owner_scoped_delete(self):
        self._add_attachment("ATT-0001", "staf_budi")
        self._add_attachment("ATT-0002", "staf_siti")
        self.assertEqual(len(self.db.list_attachments()), 2)
        self.assertEqual(len(self.db.list_attachments("staf_siti")), 1)
        self.assertFalse(self.db.delete_attachment("ATT-0001", owner_username="staf_siti"))
        self.assertTrue(self.db.delete_attachment("ATT-0001", owner_username="staf_budi"))
        self.assertTrue(self.db.delete_attachment("ATT-0002"))
        self.assertEqual(self.db.list_attachments(), [])

    def test_get_raw_rows_rejects_unknown_table(self):
        with self.assertRaises(ValueError):
            self.db.get_raw_rows("sqlite_master; DROP TABLE users")

    # --- checksum ---

    def test_checksum_matches_file_hash_and_changes_on_write(self):
        before = self.stored_checksum()
        self._add_user()
        after = self.stored_checksum()
        self.assertNotEqual(before, after)
        self.assertEqual(after, self.db.compute_db_checksum())
        self.assertTrue(self.db.check_integrity()["ok"])

    def test_checksum_updates_on_delete(self):
        self._add_user()
        before = self.stored_checksum()
        self.db.delete_user("staf_budi")
        self.assertNotEqual(before, self.stored_checksum())
        self.assertTrue(self.db.check_integrity()["ok"])

    def test_reads_do_not_change_checksum(self):
        self._add_user()
        before = self.stored_checksum()
        self.db.list_users()
        self.db.get_user("staf_budi")
        self.assertEqual(before, self.db.compute_db_checksum())
        self.assertEqual(before, self.stored_checksum())

    def test_byte_flip_detected_and_blocks_reads_and_writes(self):
        self._add_user()
        with open(self.db.paths.db, "r+b") as f:
            f.seek(-1, os.SEEK_END)
            last = f.read(1)
            f.seek(-1, os.SEEK_END)
            f.write(bytes([last[0] ^ 0x01]))
        report = self.db.check_integrity()
        self.assertEqual(report["status"], STATUS_TAMPERED)
        self.assertFalse(report["ok"])
        self.assertNotEqual(report["expected_sha256"], report["actual_sha256"])
        with self.assertRaises(DatabaseIntegrityError):
            self.db.list_users()
        with self.assertRaises(DatabaseIntegrityError):
            self._add_user("staf_lain")

    def test_external_sqlite_edit_detected(self):
        self._add_user()
        with sqlite3.connect(self.db.paths.db) as conn:
            conn.execute("UPDATE users SET password_hash = ? WHERE username = ?", ("0" * 64, "staf_budi"))
        self.assertEqual(self.db.check_integrity()["status"], STATUS_TAMPERED)
        with self.assertRaises(DatabaseIntegrityError):
            self.db.get_user("staf_budi")

    def test_missing_checksum_file_detected(self):
        os.remove(self.db.paths.db_checksum)
        self.assertEqual(self.db.check_integrity()["status"], STATUS_MISSING_CHECKSUM)
        with self.assertRaises(DatabaseIntegrityError):
            self.db.list_documents()

    def test_update_checksum_rebaselines_after_external_change(self):
        self._add_user()
        with sqlite3.connect(self.db.paths.db) as conn:
            conn.execute("DELETE FROM users")
        self.assertFalse(self.db.check_integrity()["ok"])
        self.db.update_checksum()
        self.assertTrue(self.db.check_integrity()["ok"])

    def test_tampered_field_ciphertext_raises_on_decrypt(self):
        """Ciphertext field dirusak lalu checksum disesuaikan: dekripsi tetap gagal."""
        self._add_user()
        with sqlite3.connect(self.db.paths.db) as conn:
            conn.execute("UPDATE users SET full_name_enc = ?", ("QUJDREVGR0hJSktMTU5PUA==",))
        self.db.update_checksum()
        with self.assertRaises(DatabaseIntegrityError):
            self.db.get_user("staf_budi")

    def test_different_pepper_cannot_read_fields(self):
        self._add_user()
        other = Database(self.storage, pepper="pepper-lain")
        with self.assertRaises(DatabaseIntegrityError):
            other.get_user("staf_budi")


# =====================================================================
# dongle_guard.py
# =====================================================================

SERIAL_A = "A8F4-9902"
SERIAL_B = "1B2C-3D4E"


class FakeUsbBench(TempDirTestCase):
    """Dua 'flashdisk' palsu berupa folder dengan nomor seri berbeda, tanpa perangkat keras."""

    def setUp(self):
        self.usb_a = self.make_dir()
        self.usb_b = self.make_dir()
        self.serials = {self.usb_a: SERIAL_A, self.usb_b: SERIAL_B}
        self.plugged = [self.usb_a]
        self.guard = self.make_guard()

    def drive(self, path):
        return {"mountpoint": path, "device": path, "fstype": "FAT32", "removable": True, "simulated": False}

    def make_guard(self, pepper=None):
        return DongleGuard(
            drive_provider=lambda: [self.drive(p) for p in self.plugged],
            serial_provider=lambda d: self.serials.get(d["mountpoint"]),
            pepper=pepper,
        )

    def key_path(self, usb):
        return os.path.join(usb, "dongle.key")

    def read_key(self, usb):
        with open(self.key_path(usb), encoding="utf-8") as f:
            return json.load(f)

    def write_key(self, usb, data):
        with open(self.key_path(usb), "w", encoding="utf-8") as f:
            json.dump(data, f)


class TestDongleSignature(unittest.TestCase):
    def test_signature_formula(self):
        import hashlib
        expected = hashlib.sha256(b"AEGIS-DONGLE-01:A8F4-9902:pepper-x").hexdigest()
        self.assertEqual(compute_signature("AEGIS-DONGLE-01", "A8F4-9902", "pepper-x"), expected)

    def test_signature_depends_on_every_input(self):
        base = compute_signature("ID", SERIAL_A, "p")
        self.assertNotEqual(base, compute_signature("ID2", SERIAL_A, "p"))
        self.assertNotEqual(base, compute_signature("ID", SERIAL_B, "p"))
        self.assertNotEqual(base, compute_signature("ID", SERIAL_A, "q"))

    def test_serial_format(self):
        self.assertEqual(dongle_guard._format_serial(0xA8F49902), "A8F4-9902")
        self.assertEqual(dongle_guard._format_serial(0x00010002), "0001-0002")

    def test_fallback_serial_is_stable_and_formatted(self):
        first = dongle_guard._fallback_volume_serial("/dev/sdb1")
        self.assertEqual(first, dongle_guard._fallback_volume_serial("/dev/sdb1"))
        self.assertNotEqual(first, dongle_guard._fallback_volume_serial("/dev/sdc1"))
        self.assertRegex(first, r"^[0-9A-F]{4}-[0-9A-F]{4}$")


class TestDongleEnrollAndValidate(FakeUsbBench):
    def test_no_usb_means_locked(self):
        self.plugged = []
        status = self.guard.validate_dongle()
        self.assertFalse(status["connected"])
        self.assertFalse(status["valid"])
        self.assertIn("Tidak ada USB", status["reason"])

    def test_usb_without_key_is_connected_but_invalid(self):
        status = self.guard.validate_dongle()
        self.assertTrue(status["connected"])
        self.assertFalse(status["valid"])

    def test_enroll_writes_spec_conform_key_file(self):
        result = self.guard.enroll_dongle()
        self.assertTrue(result["enrolled"])
        self.assertFalse(result["already_enrolled"])
        key = self.read_key(self.usb_a)
        self.assertEqual(set(key), {"dongle_id", "volume_serial", "issued_at", "signature"})
        self.assertTrue(key["dongle_id"].startswith("AEGIS-DONGLE-"))
        self.assertEqual(key["volume_serial"], SERIAL_A)
        self.assertRegex(key["issued_at"], r"^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}Z$")
        self.assertEqual(key["signature"], compute_signature(key["dongle_id"], SERIAL_A))
        self.assertFalse(os.path.exists(self.key_path(self.usb_a) + ".tmp"))

    def test_enrolled_usb_validates(self):
        self.guard.enroll_dongle()
        status = self.guard.validate_dongle()
        self.assertTrue(status["valid"])
        self.assertTrue(status["connected"])
        self.assertEqual(status["volume_serial"], SERIAL_A)
        self.assertEqual(status["mountpoint"], self.usb_a)
        self.assertTrue(self.guard.is_dongle_valid())

    def test_unplug_invalidates_immediately(self):
        self.guard.enroll_dongle()
        self.assertTrue(self.guard.is_dongle_valid())
        self.plugged = []
        self.assertFalse(self.guard.is_dongle_valid())

    def test_enroll_without_usb_raises(self):
        self.plugged = []
        with self.assertRaises(DongleError):
            self.guard.enroll_dongle()

    def test_enroll_is_idempotent_for_valid_dongle(self):
        first = self.guard.enroll_dongle()
        second = self.guard.enroll_dongle()
        self.assertTrue(second["already_enrolled"])
        self.assertEqual(first["dongle_id"], second["dongle_id"])

    def test_corrupt_key_file_is_replaced_on_enroll(self):
        with open(self.key_path(self.usb_a), "w") as f:
            f.write("{bukan json")
        self.assertFalse(self.guard.is_dongle_valid())
        result = self.guard.enroll_dongle()
        self.assertTrue(result["enrolled"])
        self.assertTrue(self.guard.is_dongle_valid())

    def test_multiple_removable_drives_require_explicit_choice(self):
        self.plugged = [self.usb_a, self.usb_b]
        with self.assertRaises(MultipleDrivesError) as ctx:
            self.guard.enroll_dongle()
        self.assertEqual(len(ctx.exception.drives), 2)
        result = self.guard.enroll_dongle(mountpoint=self.usb_b)
        self.assertEqual(result["volume_serial"], SERIAL_B)
        self.assertTrue(os.path.exists(self.key_path(self.usb_b)))
        self.assertFalse(os.path.exists(self.key_path(self.usb_a)))

    def test_enroll_unknown_mountpoint_rejected(self):
        with self.assertRaises(DongleError):
            self.guard.enroll_dongle(mountpoint=self.make_dir())

    def test_unreadable_serial_blocks_enrollment(self):
        self.serials[self.usb_a] = None
        with self.assertRaises(DongleError):
            self.guard.enroll_dongle()
        self.assertFalse(os.path.exists(self.key_path(self.usb_a)))

    def test_non_removable_drive_with_key_is_still_scanned(self):
        """Spesifikasi 3.1 butir 1: drive yang memuat dongle.key ikut dipindai."""
        self.guard.enroll_dongle()
        fixed = dict(self.drive(self.usb_a), removable=False)
        guard = DongleGuard(
            drive_provider=lambda: [fixed],
            serial_provider=lambda d: self.serials[d["mountpoint"]],
        )
        self.assertTrue(guard.is_dongle_valid())


class TestDongleAntiCopy(FakeUsbBench):
    """AC-01: dongle.key tidak boleh berfungsi di drive lain atau jika diubah."""

    def setUp(self):
        super().setUp()
        self.guard.enroll_dongle()

    def test_key_copied_to_other_usb_is_rejected(self):
        shutil.copy(self.key_path(self.usb_a), self.key_path(self.usb_b))
        self.plugged = [self.usb_b]
        status = self.guard.validate_dongle()
        self.assertFalse(status["valid"])
        self.assertIn("nomor seri", status["reason"].lower())

    def test_forged_serial_field_is_rejected_by_signature(self):
        forged = self.read_key(self.usb_a)
        forged["volume_serial"] = SERIAL_B
        self.write_key(self.usb_b, forged)
        self.plugged = [self.usb_b]
        status = self.guard.validate_dongle()
        self.assertFalse(status["valid"])
        self.assertIn("tanda tangan", status["reason"].lower())

    def test_modified_dongle_id_is_rejected(self):
        key = self.read_key(self.usb_a)
        key["dongle_id"] = "AEGIS-DONGLE-HACKED"
        self.write_key(self.usb_a, key)
        self.assertFalse(self.guard.is_dongle_valid())

    def test_modified_signature_is_rejected(self):
        key = self.read_key(self.usb_a)
        key["signature"] = "0" * 64
        self.write_key(self.usb_a, key)
        self.assertFalse(self.guard.is_dongle_valid())

    def test_missing_field_is_rejected(self):
        key = self.read_key(self.usb_a)
        del key["issued_at"]
        self.write_key(self.usb_a, key)
        self.assertFalse(self.guard.is_dongle_valid())

    def test_key_signed_with_other_pepper_is_rejected(self):
        other = self.make_guard(pepper="pepper-lain")
        self.assertFalse(other.is_dongle_valid())

    def test_serial_comparison_is_case_insensitive(self):
        key = self.read_key(self.usb_a)
        key["volume_serial"] = key["volume_serial"].lower()
        self.write_key(self.usb_a, key)
        self.assertTrue(self.guard.is_dongle_valid())


class TestDongleSimulationAndHardwareScan(TempDirTestCase):
    def test_simulation_env_adds_drive_with_fixed_serial(self):
        sim = self.make_dir()
        with mock.patch.dict(os.environ, {dongle_guard.SIMULATION_ENV_VAR: sim}):
            drives = dongle_guard.list_candidate_drives()
            simulated = [d for d in drives if d.get("simulated")]
            self.assertEqual(len(simulated), 1)
            self.assertEqual(dongle_guard.get_volume_serial(simulated[0]), dongle_guard.SIMULATED_VOLUME_SERIAL)

    def test_simulation_env_end_to_end(self):
        sim = self.make_dir()
        with mock.patch.dict(os.environ, {dongle_guard.SIMULATION_ENV_VAR: sim}):
            guard = DongleGuard()
            result = guard.enroll_dongle(mountpoint=sim)
            self.assertTrue(result["enrolled"])
            self.assertTrue(os.path.isfile(os.path.join(sim, "dongle.key")))
            self.assertTrue(guard.validate_dongle()["valid"])
        with mock.patch.dict(os.environ, {dongle_guard.SIMULATION_ENV_VAR: ""}):
            self.assertFalse([d for d in dongle_guard.list_candidate_drives() if d.get("simulated")])

    def test_simulation_ignored_when_folder_missing(self):
        missing = os.path.join(self.make_dir(), "tidak_ada")
        with mock.patch.dict(os.environ, {dongle_guard.SIMULATION_ENV_VAR: missing}):
            self.assertFalse([d for d in dongle_guard.list_candidate_drives() if d.get("simulated")])

    def test_psutil_scan_returns_well_formed_list(self):
        with mock.patch.dict(os.environ, {dongle_guard.SIMULATION_ENV_VAR: ""}):
            for drive in dongle_guard.list_candidate_drives():
                self.assertTrue({"mountpoint", "device", "fstype", "removable", "simulated"} <= set(drive))

    def test_removable_partition_from_psutil_is_listed(self):
        fake = mock.Mock(mountpoint="E:\\", device="E:\\", fstype="FAT32", opts="rw,removable")
        with mock.patch.dict(os.environ, {dongle_guard.SIMULATION_ENV_VAR: ""}), \
                mock.patch.object(dongle_guard.psutil, "disk_partitions", return_value=[fake]):
            drives = dongle_guard.list_candidate_drives()
        self.assertEqual([d["mountpoint"] for d in drives], ["E:\\"])
        self.assertTrue(drives[0]["removable"])

    def test_fixed_partition_without_key_is_ignored(self):
        fixed_dir = self.make_dir()
        fake = mock.Mock(mountpoint=fixed_dir, device="C:\\", fstype="NTFS", opts="rw,fixed")
        with mock.patch.dict(os.environ, {dongle_guard.SIMULATION_ENV_VAR: ""}), \
                mock.patch.dict(dongle_guard.__dict__, {"_is_removable": lambda p: False}), \
                mock.patch.object(dongle_guard.psutil, "disk_partitions", return_value=[fake]):
            self.assertEqual(dongle_guard.list_candidate_drives(), [])

    def test_psutil_failure_is_handled(self):
        with mock.patch.dict(os.environ, {dongle_guard.SIMULATION_ENV_VAR: ""}), \
                mock.patch.object(dongle_guard.psutil, "disk_partitions", side_effect=OSError("boom")):
            self.assertEqual(dongle_guard.list_candidate_drives(), [])

    @unittest.skipUnless(sys.platform == "win32", "GetVolumeInformationW hanya tersedia di Windows")
    def test_windows_volume_serial_of_system_drive(self):
        drive_letter = os.path.splitdrive(os.environ.get("SystemRoot", "C:\\Windows"))[0]
        serial = dongle_guard.get_volume_serial({"mountpoint": drive_letter + "\\", "simulated": False})
        self.assertRegex(serial, r"^[0-9A-F]{4}-[0-9A-F]{4}$")
        self.assertEqual(serial, dongle_guard.get_volume_serial({"mountpoint": drive_letter + "\\", "simulated": False}))

    @unittest.skipUnless(sys.platform == "win32", "GetVolumeInformationW hanya tersedia di Windows")
    def test_windows_volume_serial_of_missing_drive_is_none(self):
        used = {os.path.splitdrive(p.mountpoint)[0].upper() for p in dongle_guard.psutil.disk_partitions(all=True)}
        free = [c + ":" for c in "ZYXWVUTSRQP" if c + ":" not in used]
        self.assertTrue(free)
        self.assertIsNone(dongle_guard.get_volume_serial({"mountpoint": free[0] + "\\", "simulated": False}))


class TestDongleMonitor(FakeUsbBench):
    def test_refresh_detects_unplug_and_fires_callback_once(self):
        self.guard.enroll_dongle()
        events = []
        monitor = DongleMonitor(self.guard, interval=0.05, on_change=events.append)
        self.assertTrue(monitor.get_status()["valid"])

        self.plugged = []
        monitor.refresh()
        monitor.refresh()
        self.assertFalse(monitor.get_status()["valid"])
        self.assertEqual(len(events), 1)
        self.assertFalse(events[0]["valid"])

        self.plugged = [self.usb_a]
        monitor.refresh()
        self.assertTrue(monitor.get_status()["valid"])
        self.assertEqual(len(events), 2)

    def test_background_thread_notices_unplug_within_three_seconds(self):
        self.guard.enroll_dongle()
        monitor = DongleMonitor(self.guard, interval=0.05)
        monitor.start()
        self.addCleanup(monitor.stop)
        self.assertTrue(monitor.get_status()["valid"])

        self.plugged = []
        deadline = time.time() + 3.0
        while time.time() < deadline and monitor.get_status()["valid"]:
            time.sleep(0.02)
        self.assertFalse(monitor.get_status()["valid"])

    def test_start_stop_are_safe_to_repeat(self):
        monitor = DongleMonitor(self.guard, interval=0.05)
        monitor.start()
        monitor.start()
        monitor.stop()
        monitor.stop()

    def test_failing_callback_does_not_break_monitor(self):
        self.guard.enroll_dongle()

        def boom(_status):
            raise RuntimeError("callback gagal")

        monitor = DongleMonitor(self.guard, interval=0.05, on_change=boom)
        self.plugged = []
        monitor.refresh()
        self.assertFalse(monitor.get_status()["valid"])


# =====================================================================
# biometric_auth.py
# =====================================================================

def make_synthetic_face_image(seed: int, size: int = 200) -> np.ndarray:
    """
    Citra BGR sintetis berpola acak halus, satu seed satu 'identitas'.
    Haar Cascade tidak mengenalinya sebagai wajah, sehingga pengujian
    memakai FakeCascade yang menandai seluruh citra sebagai wajah.
    """
    rng = np.random.default_rng(seed)
    noise = rng.integers(0, 256, (size, size)).astype(np.float32)
    smooth = cv2.GaussianBlur(noise, (0, 0), 6)
    smooth = cv2.normalize(smooth, None, 0, 255, cv2.NORM_MINMAX).astype(np.uint8)
    return cv2.cvtColor(smooth, cv2.COLOR_GRAY2BGR)


def to_base64_png(image: np.ndarray, data_url: bool = False) -> str:
    ok, buffer = cv2.imencode(".png", image)
    assert ok
    encoded = base64.b64encode(buffer.tobytes()).decode("ascii")
    return f"data:image/png;base64,{encoded}" if data_url else encoded


class FakeCascade:
    """Pengganti CascadeClassifier: mengembalikan kotak wajah yang ditentukan pengujian."""

    def __init__(self, boxes=None):
        self.boxes = boxes

    def empty(self):
        return False

    def detectMultiScale(self, gray, **_kwargs):
        if self.boxes is None:
            height, width = gray.shape[:2]
            return np.array([[0, 0, width, height]])
        return np.array(self.boxes, dtype=int).reshape(-1, 4) if self.boxes else ()


class TestFingerprintCapability(unittest.TestCase):
    def test_no_sensor_activates_face_recognition(self):
        result = biometric_auth.detect_fingerprint_capability(unit_counter=lambda: 0)
        self.assertIs(result["fingerprint_available"], False)
        self.assertEqual(result["active_mode"], "FACE_RECOGNITION")
        self.assertIn("Face Recognition", result["detail"])

    def test_sensor_present_reports_fingerprint(self):
        result = biometric_auth.detect_fingerprint_capability(unit_counter=lambda: 1)
        self.assertIs(result["fingerprint_available"], True)
        self.assertEqual(result["active_mode"], "FINGERPRINT")

    def test_face_verification_always_enabled(self):
        for count in (0, 2):
            result = biometric_auth.detect_fingerprint_capability(unit_counter=lambda c=count: c)
            self.assertTrue(result["face_verification_enabled"])

    def test_detection_error_falls_back_to_face(self):
        def broken():
            raise OSError("winbio.dll tidak tersedia")

        result = biometric_auth.detect_fingerprint_capability(unit_counter=broken)
        self.assertIs(result["fingerprint_available"], False)
        self.assertEqual(result["active_mode"], "FACE_RECOGNITION")
        self.assertIn("gagal", result["detail"])

    def test_non_windows_falls_back_to_face(self):
        with mock.patch.object(biometric_auth.sys, "platform", "linux"):
            result = biometric_auth.detect_fingerprint_capability()
        self.assertIs(result["fingerprint_available"], False)
        self.assertEqual(result["active_mode"], "FACE_RECOGNITION")

    @unittest.skipUnless(sys.platform == "win32", "Windows Biometric Framework hanya tersedia di Windows")
    def test_real_windows_query_returns_consistent_result(self):
        result = biometric_auth.detect_fingerprint_capability()
        self.assertIsInstance(result["fingerprint_available"], bool)
        expected = "FINGERPRINT" if result["fingerprint_available"] else "FACE_RECOGNITION"
        self.assertEqual(result["active_mode"], expected)


class TestImageDecoding(unittest.TestCase):
    def test_decode_plain_base64_and_data_url(self):
        image = make_synthetic_face_image(1)
        for data in (to_base64_png(image), to_base64_png(image, data_url=True)):
            decoded = biometric_auth.decode_base64_image(data)
            self.assertEqual(decoded.shape, image.shape)
            self.assertTrue(np.array_equal(decoded, image))

    def test_invalid_inputs_raise_invalid_image_error(self):
        not_an_image = base64.b64encode(b"ini bukan gambar").decode("ascii")
        for bad in ("", "   ", None, "###bukan-base64###", not_an_image):
            with self.assertRaises(biometric_auth.InvalidImageError):
                biometric_auth.decode_base64_image(bad)

    def test_oversized_image_rejected(self):
        huge = base64.b64encode(b"\x00" * (biometric_auth.MAX_IMAGE_BYTES + 1)).decode("ascii")
        with self.assertRaises(biometric_auth.InvalidImageError):
            biometric_auth.decode_base64_image(huge)


class TestFaceExtraction(unittest.TestCase):
    def setUp(self):
        self.addCleanup(setattr, biometric_auth, "_cascade", biometric_auth._cascade)

    def test_real_haar_cascade_file_loads(self):
        biometric_auth._cascade = None
        cascade = biometric_auth._get_cascade()
        self.assertFalse(cascade.empty())

    def test_real_cascade_finds_no_face_in_blank_image(self):
        biometric_auth._cascade = None
        blank = np.full((240, 320, 3), 127, dtype=np.uint8)
        with self.assertRaises(biometric_auth.NoFaceDetectedError):
            biometric_auth.extract_face(blank)

    def test_normalize_face_is_128x128_uint8_and_histogram_equalized(self):
        low_contrast = np.random.default_rng(0).integers(100, 140, (90, 70)).astype(np.uint8)
        face = biometric_auth.normalize_face(low_contrast)
        self.assertEqual(face.shape, (128, 128))
        self.assertEqual(face.dtype, np.uint8)
        self.assertGreater(int(face.max()) - int(face.min()), 200)  # kontras diregangkan equalizeHist

    def test_extract_crops_detected_region(self):
        image = make_synthetic_face_image(2, size=300)
        biometric_auth._cascade = FakeCascade([[50, 60, 120, 140]])
        face = biometric_auth.extract_face(image)
        expected = biometric_auth.normalize_face(cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)[60:200, 50:170])
        self.assertTrue(np.array_equal(face, expected))

    def test_largest_face_is_chosen(self):
        image = make_synthetic_face_image(3, size=300)
        biometric_auth._cascade = FakeCascade([[0, 0, 70, 70], [100, 100, 180, 180], [10, 200, 80, 80]])
        face = biometric_auth.extract_face(image)
        gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
        self.assertTrue(np.array_equal(face, biometric_auth.normalize_face(gray[100:280, 100:280])))

    def test_no_detection_raises(self):
        biometric_auth._cascade = FakeCascade([])
        with self.assertRaises(biometric_auth.NoFaceDetectedError):
            biometric_auth.extract_face(make_synthetic_face_image(4))

    def test_dlib_is_not_used(self):
        self.assertNotIn("dlib", sys.modules)
        with open(biometric_auth.__file__, encoding="utf-8") as f:
            source = f.read()
        self.assertNotRegex(source, r"(?m)^\s*(import|from)\s+(dlib|face_recognition)\b")


class TestFaceSimilarity(unittest.TestCase):
    def face(self, seed):
        return biometric_auth.normalize_face(
            cv2.cvtColor(make_synthetic_face_image(seed), cv2.COLOR_BGR2GRAY))

    def test_identical_faces_score_one(self):
        a = self.face(10)
        result = biometric_auth.compute_similarity(a, a.copy())
        self.assertAlmostEqual(result["score"], 1.0, places=3)
        self.assertAlmostEqual(result["ncc"], 1.0, places=3)
        self.assertAlmostEqual(result["hist"], 1.0, places=3)

    def test_different_faces_fall_below_threshold(self):
        for other in (11, 12, 13, 14):
            result = biometric_auth.compute_similarity(self.face(10), self.face(other))
            self.assertLess(result["score"], biometric_auth.MATCH_THRESHOLD, result)

    def test_same_face_with_noise_and_brightness_shift_stays_above_threshold(self):
        base = make_synthetic_face_image(10)
        rng = np.random.default_rng(99)
        shifted = np.clip(base.astype(np.int16) + 12 + rng.normal(0, 4, base.shape), 0, 255).astype(np.uint8)
        a = biometric_auth.normalize_face(cv2.cvtColor(base, cv2.COLOR_BGR2GRAY))
        b = biometric_auth.normalize_face(cv2.cvtColor(shifted, cv2.COLOR_BGR2GRAY))
        result = biometric_auth.compute_similarity(a, b)
        self.assertGreaterEqual(result["score"], biometric_auth.MATCH_THRESHOLD, result)

    def test_score_is_weighted_combination_in_unit_range(self):
        result = biometric_auth.compute_similarity(self.face(20), self.face(21))
        expected = biometric_auth.NCC_WEIGHT * result["ncc"] + biometric_auth.HIST_WEIGHT * result["hist"]
        self.assertAlmostEqual(result["score"], expected, places=3)
        for key in ("score", "ncc", "hist"):
            self.assertTrue(0.0 <= result[key] <= 1.0)

    def test_uniform_image_does_not_produce_nan(self):
        flat = np.full((128, 128), 90, dtype=np.uint8)
        result = biometric_auth.compute_similarity(flat, self.face(10))
        self.assertTrue(all(np.isfinite(v) for v in result.values()))
        self.assertLess(result["score"], biometric_auth.MATCH_THRESHOLD)

    def test_wrong_shape_or_dtype_rejected(self):
        good = self.face(10)
        with self.assertRaises(ValueError):
            biometric_auth.compute_similarity(good, np.zeros((64, 64), dtype=np.uint8))
        with self.assertRaises(ValueError):
            biometric_auth.compute_similarity(good, good.astype(np.float32))


class TestFaceEnrollmentAndVerification(TempDirTestCase):
    def setUp(self):
        self.storage = self.make_dir()
        self.addCleanup(setattr, biometric_auth, "_cascade", biometric_auth._cascade)
        biometric_auth._cascade = FakeCascade()  # seluruh citra dianggap satu wajah
        self.budi = to_base64_png(make_synthetic_face_image(100))
        self.siti = to_base64_png(make_synthetic_face_image(200))

    def test_enroll_saves_128x128_npy_in_faces_folder(self):
        result = biometric_auth.enroll_face("staf_budi", self.budi, self.storage)
        expected_path = os.path.join(self.storage, "faces", "staf_budi.npy")
        self.assertEqual(result["face_model_path"], expected_path)
        self.assertTrue(biometric_auth.face_exists("staf_budi", self.storage))
        matrix = np.load(expected_path, allow_pickle=False)
        self.assertEqual(matrix.shape, (128, 128))
        self.assertEqual(matrix.dtype, np.uint8)
        self.assertFalse(os.path.exists(expected_path + ".tmp"))

    def test_enroll_accepts_data_url_frames(self):
        frame = to_base64_png(make_synthetic_face_image(100), data_url=True)
        biometric_auth.enroll_face("staf_budi", frame, self.storage)
        self.assertTrue(biometric_auth.verify_face("staf_budi", frame, self.storage)["match"])

    def test_owner_face_matches(self):
        biometric_auth.enroll_face("staf_budi", self.budi, self.storage)
        result = biometric_auth.verify_face("staf_budi", self.budi, self.storage)
        self.assertTrue(result["match"])
        self.assertGreaterEqual(result["score"], 0.72)
        self.assertEqual(result["threshold"], 0.72)

    def test_other_persons_face_is_rejected(self):
        biometric_auth.enroll_face("staf_budi", self.budi, self.storage)
        result = biometric_auth.verify_face("staf_budi", self.siti, self.storage)
        self.assertFalse(result["match"])
        self.assertLess(result["score"], 0.72)

    def test_each_user_is_checked_against_own_template(self):
        biometric_auth.enroll_face("staf_budi", self.budi, self.storage)
        biometric_auth.enroll_face("staf_siti", self.siti, self.storage)
        self.assertTrue(biometric_auth.verify_face("staf_budi", self.budi, self.storage)["match"])
        self.assertTrue(biometric_auth.verify_face("staf_siti", self.siti, self.storage)["match"])
        self.assertFalse(biometric_auth.verify_face("staf_siti", self.budi, self.storage)["match"])

    def test_custom_threshold_is_applied(self):
        biometric_auth.enroll_face("staf_budi", self.budi, self.storage)
        strict = biometric_auth.verify_face("staf_budi", self.budi, self.storage, threshold=1.01)
        self.assertFalse(strict["match"])

    def test_verify_without_enrollment_raises(self):
        with self.assertRaises(biometric_auth.FaceNotEnrolledError):
            biometric_auth.verify_face("staf_budi", self.budi, self.storage)

    def test_no_face_in_frame_does_not_create_template(self):
        biometric_auth._cascade = FakeCascade([])
        with self.assertRaises(biometric_auth.NoFaceDetectedError):
            biometric_auth.enroll_face("staf_budi", self.budi, self.storage)
        self.assertFalse(biometric_auth.face_exists("staf_budi", self.storage))

    def test_no_face_during_verification_raises(self):
        biometric_auth.enroll_face("staf_budi", self.budi, self.storage)
        biometric_auth._cascade = FakeCascade([])
        with self.assertRaises(biometric_auth.NoFaceDetectedError):
            biometric_auth.verify_face("staf_budi", self.budi, self.storage)

    def test_invalid_frame_raises_before_writing(self):
        with self.assertRaises(biometric_auth.InvalidImageError):
            biometric_auth.enroll_face("staf_budi", "bukan-gambar", self.storage)
        self.assertFalse(biometric_auth.face_exists("staf_budi", self.storage))

    def test_unsafe_usernames_rejected(self):
        for bad in ("../hack", "a/b", "a\\b", "", ".tersembunyi", "x" * 65, "nama spasi", None):
            with self.assertRaises(biometric_auth.BiometricError):
                biometric_auth.enroll_face(bad, self.budi, self.storage)
        self.assertEqual(os.listdir(os.path.join(self.storage)) if os.path.isdir(self.storage) else [], [])

    def test_re_enrollment_replaces_template(self):
        biometric_auth.enroll_face("staf_budi", self.budi, self.storage)
        biometric_auth.enroll_face("staf_budi", self.siti, self.storage)
        self.assertTrue(biometric_auth.verify_face("staf_budi", self.siti, self.storage)["match"])
        self.assertFalse(biometric_auth.verify_face("staf_budi", self.budi, self.storage)["match"])

    def test_corrupt_or_malformed_template_raises_biometric_error(self):
        biometric_auth.enroll_face("staf_budi", self.budi, self.storage)
        path = biometric_auth.face_model_path("staf_budi", self.storage)
        with open(path, "wb") as f:
            f.write(b"bukan file npy")
        with self.assertRaises(biometric_auth.BiometricError):
            biometric_auth.verify_face("staf_budi", self.budi, self.storage)
        np.save(path, np.zeros((10, 10), dtype=np.uint8))
        with self.assertRaises(biometric_auth.BiometricError):
            biometric_auth.verify_face("staf_budi", self.budi, self.storage)

    def test_delete_face(self):
        biometric_auth.enroll_face("staf_budi", self.budi, self.storage)
        self.assertTrue(biometric_auth.delete_face("staf_budi", self.storage))
        self.assertFalse(biometric_auth.delete_face("staf_budi", self.storage))
        self.assertFalse(biometric_auth.face_exists("staf_budi", self.storage))

    def test_face_model_path_matches_database_column_usage(self):
        """face_model_path() dapat langsung disimpan ke kolom users.face_model_path."""
        db = Database(self.storage)
        enrolled = biometric_auth.enroll_face("staf_budi", self.budi, self.storage)
        pw_hash, salt_hex = hash_password("PIN-12345")
        db.create_user("staf_budi", "Budi Santoso", "Staf Arsip", pw_hash, salt_hex,
                       enrolled["face_model_path"])
        stored = db.get_user("staf_budi")["face_model_path"]
        self.assertTrue(os.path.isfile(stored))


if __name__ == "__main__":
    unittest.main(verbosity=2)
