"""
AegisVault Cryptographic Test Suite (Slice 1)
Pengujian Otomatis Komprehensif untuk:
1. PBKDF2-HMAC-SHA256 & Dynamic Salt Password Hashing
2. Extended Vigenere 256 ASCII (From-Scratch)
3. AES-128-CBC PKCS#7 Padding
4. Super Enkripsi Teks (Extended Vigenere + AES-128-CBC)
5. RC4 Stream Cipher (KSA + PRGA From-Scratch) & Enkripsi Berkas Nonce
6. Steganografi LSB Citra PNG 24-bit dengan Header 32-bit Big-Endian
7. Blockchain Ledger (PoW '000'), Integritas Rantai, & Paket .vault Anti-Tampering

Bebas dari karakter em dash sesuai Aturan R-02 antislop.md.
"""

import json
import os
import shutil
import sys
import tempfile
import unittest
from pathlib import Path

# Memastikan direktori root proyek berada dalam sys.path
ROOT_DIR = str(Path(__file__).resolve().parent.parent)
if ROOT_DIR not in sys.path:
    sys.path.insert(0, ROOT_DIR)

import numpy as np
from PIL import Image

from backend.crypto_engine import (
    generate_salt,
    derive_keys,
    hash_password,
    verify_password,
    sha256_hex,
    sha256_bytes,
    vigenere_256_encrypt,
    vigenere_256_decrypt,
    pkcs7_pad,
    pkcs7_unpad,
    aes_128_cbc_encrypt,
    aes_128_cbc_decrypt,
    super_encrypt_text,
    super_decrypt_text,
    super_encrypt_inspect,
    super_encrypt_with_passphrase,
    super_decrypt_with_passphrase,
    rc4_crypt,
    encrypt_file_rc4,
    decrypt_file_rc4,
)
from backend.stego_engine import (
    calculate_capacity,
    get_image_capacity,
    embed_message_into_image,
    extract_message_from_image,
    embed_and_save_png,
    extract_from_png_file,
)
from backend.blockchain_ledger import (
    Blockchain,
    compute_block_hash,
    mine_pow,
    package_vault_file,
    export_vault_to_file,
    import_and_verify_vault,
    POW_DIFFICULTY_PREFIX,
)


class TestKeyDerivationAndAuth(unittest.TestCase):
    """Pengujian Modul PBKDF2-HMAC-SHA256 dan Hashing Password SHA-256 + Salt."""

    def test_generate_salt(self):
        salt1 = generate_salt(16)
        salt2 = generate_salt(16)
        self.assertEqual(len(salt1), 16)
        self.assertEqual(len(salt2), 16)
        self.assertNotEqual(salt1, salt2, "Salt acak harus unik.")

    def test_derive_keys_deterministic_and_lengths(self):
        passphrase = "MasterPasswordInstansi2026!"
        salt = b"0123456789abcdef"
        k1_a, k2_a = derive_keys(passphrase, salt, iterations=1000)
        k1_b, k2_b = derive_keys(passphrase, salt, iterations=1000)

        # Panjang masing-masing wajib 16 byte (128 bit)
        self.assertEqual(len(k1_a), 16)
        self.assertEqual(len(k2_a), 16)
        # Sifat deterministik (input sama menghasilkan output sama)
        self.assertEqual(k1_a, k1_b)
        self.assertEqual(k2_a, k2_b)
        # Kunci K1 dan K2 harus berbeda
        self.assertNotEqual(k1_a, k2_a)

    def test_derive_keys_empty_passphrase_raises(self):
        with self.assertRaises(ValueError):
            derive_keys("", b"0123456789abcdef")

    def test_hash_password_and_verification(self):
        password = "PIN-Rahasia-Staff-9921"
        pw_hash, salt_hex = hash_password(password)

        self.assertEqual(len(pw_hash), 64)
        self.assertEqual(len(salt_hex), 32)  # 16 byte = 32 hex chars

        # Verifikasi password benar
        self.assertTrue(verify_password(password, salt_hex, pw_hash))
        # Verifikasi password salah
        self.assertFalse(verify_password("PIN-Salah-1234", salt_hex, pw_hash))
        # Verifikasi salt korup
        self.assertFalse(verify_password(password, "invalid_hex", pw_hash))

    def test_sha256_utilities(self):
        raw = b"AegisVault Document Security"
        h_hex = sha256_hex(raw)
        h_bytes = sha256_bytes(raw)
        self.assertEqual(len(h_hex), 64)
        self.assertEqual(len(h_bytes), 32)
        self.assertEqual(bytes.fromhex(h_hex), h_bytes)


class TestExtendedVigenere256(unittest.TestCase):
    """Pengujian Modul Extended Vigenere 256 ASCII From-Scratch."""

    def test_vigenere_roundtrip_ascii_and_unicode(self):
        key = b"KunciVigenere256"
        plaintext = "Rapat Koordinasi Anggaran Instansi 2026: SANGAT RAHASIA!".encode("utf-8")

        ciphertext = vigenere_256_encrypt(plaintext, key)
        self.assertEqual(len(ciphertext), len(plaintext))
        self.assertNotEqual(ciphertext, plaintext)

        decrypted = vigenere_256_decrypt(ciphertext, key)
        self.assertEqual(decrypted, plaintext)

    def test_vigenere_roundtrip_full_byte_spectrum(self):
        # Menguji seluruh 256 nilai byte (0x00 s.d. 0xFF)
        full_spectrum = bytes(range(256))
        key = bytes([0xAA, 0x55, 0x00, 0xFF, 0x7F, 0x80])

        ciphertext = vigenere_256_encrypt(full_spectrum, key)
        decrypted = vigenere_256_decrypt(ciphertext, key)
        self.assertEqual(decrypted, full_spectrum)

    def test_vigenere_mathematical_formula_explicit(self):
        # Verifikasi rumus C[i] = (P[i] + K[i mod m]) mod 256
        p = bytes([100, 200, 250])
        k = bytes([50, 100])
        # c[0] = (100 + 50) % 256 = 150
        # c[1] = (200 + 100) % 256 = 44
        # c[2] = (250 + 50) % 256 = 44
        expected_c = bytes([150, 44, 44])
        actual_c = vigenere_256_encrypt(p, k)
        self.assertEqual(actual_c, expected_c)

    def test_vigenere_empty_and_error_cases(self):
        key = b"Key"
        self.assertEqual(vigenere_256_encrypt(b"", key), b"")
        self.assertEqual(vigenere_256_decrypt(b"", key), b"")
        with self.assertRaises(ValueError):
            vigenere_256_encrypt(b"Test", b"")
        with self.assertRaises(ValueError):
            vigenere_256_decrypt(b"Test", b"")


class TestAES128CBC(unittest.TestCase):
    """Pengujian Modul AES-128 Mode CBC dengan PKCS#7 Padding."""

    def test_pkcs7_padding_multiples(self):
        # Kelipatan 16 byte (misal 16 byte) harus mendapat 16 byte padding tambahan bernilai 16
        data_16 = b"A" * 16
        padded_16 = pkcs7_pad(data_16, 16)
        self.assertEqual(len(padded_16), 32)
        self.assertEqual(padded_16[-1], 16)
        self.assertEqual(pkcs7_unpad(padded_16, 16), data_16)

        # 10 byte harus mendapat 6 byte padding bernilai 6
        data_10 = b"B" * 10
        padded_10 = pkcs7_pad(data_10, 16)
        self.assertEqual(len(padded_10), 16)
        self.assertEqual(padded_10[-1], 6)
        self.assertEqual(pkcs7_unpad(padded_10, 16), data_10)

    def test_pkcs7_invalid_padding_raises(self):
        corrupt_data = b"0123456789abcdef"  # Nilai byte terakhir bukan padding valid
        with self.assertRaises(ValueError):
            pkcs7_unpad(corrupt_data, 16)

    def test_aes_128_cbc_roundtrip(self):
        key = os.urandom(16)
        sample_data = b"Pengujian Enkripsi AES-128-CBC untuk Brankas Dokumen"

        ciphertext, iv = aes_128_cbc_encrypt(sample_data, key)
        self.assertEqual(len(iv), 16)
        self.assertEqual(len(ciphertext) % 16, 0)

        decrypted = aes_128_cbc_decrypt(ciphertext, key, iv)
        self.assertEqual(decrypted, sample_data)


class TestSuperEncryption(unittest.TestCase):
    """Pengujian Super Enkripsi Teks (Extended Vigenere 256 + AES-128-CBC)."""

    def setUp(self):
        self.k1 = b"0123456789abcdef"
        self.k2 = b"fedcba9876543210"
        self.memo_text = "Instruksi Khusus Direktur: Amankan seluruh aset digital instansi sebelum audit!"

    def test_super_encrypt_decrypt_roundtrip(self):
        ciphertext_b64 = super_encrypt_text(self.memo_text, self.k1, self.k2)
        self.assertIsInstance(ciphertext_b64, str)

        decrypted_text = super_decrypt_text(ciphertext_b64, self.k1, self.k2)
        self.assertEqual(decrypted_text, self.memo_text)

    def test_super_encrypt_inspect_structure(self):
        inspect_data = super_encrypt_inspect(self.memo_text, self.k1, self.k2)
        required_keys = [
            "plaintext", "plaintext_bytes_len", "plaintext_hex",
            "vigenere_key_hex", "vigenere_ciphertext_hex",
            "aes_key_hex", "aes_iv_hex", "aes_ciphertext_hex",
            "final_ciphertext_b64"
        ]
        for rk in required_keys:
            self.assertIn(rk, inspect_data)
        self.assertEqual(inspect_data["plaintext"], self.memo_text)

    def test_super_encrypt_with_passphrase_roundtrip(self):
        passphrase = "SharedPassphraseUntukStafBudi"
        ct_b64, salt_hex = super_encrypt_with_passphrase(self.memo_text, passphrase)

        decrypted = super_decrypt_with_passphrase(ct_b64, passphrase, salt_hex)
        self.assertEqual(decrypted, self.memo_text)

    def test_super_decrypt_wrong_key_fails(self):
        ct_b64 = super_encrypt_text(self.memo_text, self.k1, self.k2)
        wrong_k1 = b"xxxxxxxxxxxxxxxx"
        wrong_k2 = b"yyyyyyyyyyyyyyyy"

        with self.assertRaises(Exception):
            super_decrypt_text(ct_b64, wrong_k1, wrong_k2)


class TestRC4StreamCipher(unittest.TestCase):
    """Pengujian Modul RC4 (ARCFOUR) Stream Cipher From-Scratch & Enkripsi Berkas."""

    def test_rc4_wikipedia_test_vector(self):
        # Test vector standar RC4 Wikipedia: Key="Key", Plaintext="Plaintext" -> Hex "BBF316E8D940AF0AD3"
        key = b"Key"
        plaintext = b"Plaintext"
        expected_hex = "BBF316E8D940AF0AD3"

        ciphertext = rc4_crypt(plaintext, key)
        self.assertEqual(ciphertext.hex().upper(), expected_hex)

        # Sifat XOR simetris: enkripsi ulang menghasilkan plainteks
        decrypted = rc4_crypt(ciphertext, key)
        self.assertEqual(decrypted, plaintext)

    def test_rc4_file_encryption_with_nonce_roundtrip(self):
        key = b"FileSecretMasterKey123"
        # Simulasikan isi file PDF / binary berukuran 64 KB
        file_content = os.urandom(64 * 1024)
        original_hash = sha256_hex(file_content)

        encrypted_file_bytes = encrypt_file_rc4(file_content, key)
        # Format wajib: 16 byte nonce unik di depan
        self.assertEqual(len(encrypted_file_bytes), len(file_content) + 16)

        decrypted_file_bytes = decrypt_file_rc4(encrypted_file_bytes, key)
        decrypted_hash = sha256_hex(decrypted_file_bytes)

        # Kepatuhan AC-04: Hash SHA-256 berkas awal sama dengan berkas hasil dekripsi 100%
        self.assertEqual(decrypted_hash, original_hash)
        self.assertEqual(decrypted_file_bytes, file_content)

    def test_rc4_nonce_uniqueness_prevents_keystream_reuse(self):
        key = b"VaultKeyCommon"
        same_content = b"Surat_Keputusan_Kerahasiaan_2026.pdf"

        # Dua kali enkripsi file yang sama harus menghasilkan ciphertext berbeda karena nonce acak
        enc1 = encrypt_file_rc4(same_content, key)
        enc2 = encrypt_file_rc4(same_content, key)

        self.assertNotEqual(enc1[:16], enc2[:16], "Nonce harus acak dan berbeda per file.")
        self.assertNotEqual(enc1, enc2, "Ciphertext file harus berbeda.")

        # Namun keduanya dapat didekripsi menghasilkan data yang sama
        self.assertEqual(decrypt_file_rc4(enc1, key), same_content)
        self.assertEqual(decrypt_file_rc4(enc2, key), same_content)


class TestSteganographyLSB(unittest.TestCase):
    """Pengujian Steganografi Citra PNG 24-bit dengan Header 32-bit Big-Endian."""

    def setUp(self):
        # Buat citra uji 100 x 100 piksel RGB
        self.test_img = Image.new("RGB", (100, 100), color=(140, 160, 190))
        self.secret_message = "Perintah Rahasia Operasional 2026: Koordinasikan tim keamanan."
        self.temp_dir = tempfile.mkdtemp()

    def tearDown(self):
        shutil.rmtree(self.temp_dir, ignore_errors=True)

    def test_capacity_calculation(self):
        # Citra 100 x 100 x 3 = 30,000 byte kanal warna.
        # Total byte = 30000 // 8 = 3750 byte.
        # Max payload = 3750 - 4 (header) = 3746 byte.
        cap = calculate_capacity(100, 100)
        self.assertEqual(cap, 3746)

    def test_embed_and_extract_raw(self):
        stego_img = embed_message_into_image(self.test_img, self.secret_message)
        extracted = extract_message_from_image(stego_img)

        # Kepatuhan AC-05: Teks terekstrak sama persis 100% tanpa karakter sampah di akhir
        self.assertEqual(extracted, self.secret_message)

    def test_embed_and_extract_encrypted(self):
        passphrase = "KunciStegoInstansi123"
        stego_img = embed_message_into_image(
            self.test_img, self.secret_message, passphrase=passphrase
        )

        # Ekstraksi dengan passphrase benar
        extracted = extract_message_from_image(stego_img, passphrase=passphrase)
        self.assertEqual(extracted, self.secret_message)

        # Ekstraksi tanpa passphrase harus memunculkan error
        with self.assertRaises(ValueError):
            extract_message_from_image(stego_img, passphrase=None)

        # Ekstraksi dengan passphrase salah harus gagal
        with self.assertRaises(ValueError):
            extract_message_from_image(stego_img, passphrase="PassphraseSalah")

    def test_payload_exceeding_capacity_raises(self):
        # Citra kecil 4 x 4 x 3 = 48 kanal warna = 6 byte total.
        # Max payload = 6 - 4 = 2 byte.
        small_img = Image.new("RGB", (4, 4), color=(50, 50, 50))
        long_msg = "Pesan ini terlalu panjang untuk citra 4x4 piksel."
        with self.assertRaises(ValueError):
            embed_message_into_image(small_img, long_msg)

    def test_save_and_extract_png_file(self):
        png_path = os.path.join(self.temp_dir, "test_stego_output.png")
        saved_path = embed_and_save_png(
            self.test_img, png_path, self.secret_message, passphrase=None
        )
        self.assertTrue(os.path.exists(saved_path))

        extracted_file_msg = extract_from_png_file(saved_path, passphrase=None)
        self.assertEqual(extracted_file_msg, self.secret_message)


class TestBlockchainLedger(unittest.TestCase):
    """Pengujian Rantai Blok Lokal, Proof-of-Work, dan Integritas Rantai."""

    def setUp(self):
        self.temp_dir = tempfile.mkdtemp()
        self.ledger_path = os.path.join(self.temp_dir, "test_blockchain.json")
        self.blockchain = Blockchain(self.ledger_path)

    def tearDown(self):
        shutil.rmtree(self.temp_dir, ignore_errors=True)

    def test_genesis_block(self):
        chain = self.blockchain.get_chain()
        self.assertEqual(len(chain), 1)
        genesis = chain[0]
        self.assertEqual(genesis["index"], 0)
        self.assertTrue(genesis["block_hash"].startswith(POW_DIFFICULTY_PREFIX))
        valid, msg = self.blockchain.is_chain_valid()
        self.assertTrue(valid, msg)

    def test_mine_multiple_blocks_and_pow(self):
        b1 = self.blockchain.mine_new_block(
            doc_uuid="DOC-001",
            author="staf_budi",
            asset_type="MEMO_TEXT",
            payload_sha256=sha256_hex("Memo 1")
        )
        self.assertEqual(b1["index"], 1)
        self.assertTrue(b1["block_hash"].startswith(POW_DIFFICULTY_PREFIX))

        b2 = self.blockchain.mine_new_block(
            doc_uuid="DOC-002",
            author="staf_siti",
            asset_type="FILE_ATTACHMENT",
            payload_sha256=sha256_hex("Berkas Lampiran 2")
        )
        self.assertEqual(b2["index"], 2)
        self.assertEqual(b2["previous_hash"], b1["block_hash"])
        self.assertTrue(b2["block_hash"].startswith(POW_DIFFICULTY_PREFIX))

        valid, msg = self.blockchain.is_chain_valid()
        self.assertTrue(valid, msg)

    def test_detect_tampered_block_content(self):
        self.blockchain.mine_new_block(
            doc_uuid="DOC-001",
            author="staf_budi",
            asset_type="MEMO_TEXT",
            payload_sha256=sha256_hex("Data Asli")
        )
        # Manipulasi isi payload_sha256 blok ke-1
        self.blockchain.chain[1]["payload_sha256"] = sha256_hex("Data Palsu")
        valid, msg = self.blockchain.is_chain_valid()
        self.assertFalse(valid, "Manipulasi data blok harus terdeteksi.")

    def test_detect_tampered_previous_hash(self):
        self.blockchain.mine_new_block("DOC-001", "budi", "MEMO_TEXT", sha256_hex("1"))
        self.blockchain.mine_new_block("DOC-002", "budi", "MEMO_TEXT", sha256_hex("2"))

        # Putus keterikatan hash rantai
        self.blockchain.chain[2]["previous_hash"] = "0" * 64
        valid, msg = self.blockchain.is_chain_valid()
        self.assertFalse(valid, "Pemutusan rantai blok harus terdeteksi.")


class TestVaultPackageVerification(unittest.TestCase):
    """Pengujian Pembuatan dan Verifikasi File Paket .vault Antar-Staf (AC-06)."""

    def setUp(self):
        self.temp_dir = tempfile.mkdtemp()
        self.ledger_path = os.path.join(self.temp_dir, "test_blockchain.json")
        self.blockchain = Blockchain(self.ledger_path)

        self.doc_uuid = "DOC-2026-CONFIDENTIAL"
        self.author = "staf_budi"
        self.title = "Memo Rapat Anggaran Rahasia 2026"
        self.category = "SANGAT RAHASIA"
        self.content = "Rapat anggaran rahasia akan dilaksanakan pada tanggal 15 November 2026."
        self.passphrase = "SharedPassphraseStaff2026"

        self.content_hash = sha256_hex(self.content)
        self.block = self.blockchain.mine_new_block(
            doc_uuid=self.doc_uuid,
            author=self.author,
            asset_type="MEMO_TEXT",
            payload_sha256=self.content_hash
        )

        self.vault_package = package_vault_file(
            doc_uuid=self.doc_uuid,
            author=self.author,
            title_plain=self.title,
            category_plain=self.category,
            plaintext_content=self.content,
            passphrase=self.passphrase,
            block=self.block
        )

    def tearDown(self):
        shutil.rmtree(self.temp_dir, ignore_errors=True)

    def test_import_valid_vault(self):
        result = import_and_verify_vault(
            self.vault_package, self.passphrase, local_blockchain=self.blockchain
        )
        self.assertTrue(result["valid"])
        self.assertEqual(result["status"], "VALID")
        self.assertEqual(result["decrypted_content"], self.content)
        self.assertEqual(result["metadata"]["title_plain"], self.title)

    def test_export_and_import_vault_file(self):
        file_path = os.path.join(self.temp_dir, "dokumen_rahasia.vault")
        export_vault_to_file(self.vault_package, file_path)
        self.assertTrue(os.path.exists(file_path))

        result = import_and_verify_vault(
            file_path, self.passphrase, local_blockchain=self.blockchain
        )
        self.assertTrue(result["valid"])
        self.assertEqual(result["status"], "VALID")
        self.assertEqual(result["decrypted_content"], self.content)

    def test_tamper_encrypted_payload(self):
        # Kepatuhan AC-06: Mengubah 1 karakter ciphertext pada file .vault
        tampered_pkg = json.loads(json.dumps(self.vault_package))
        # Ganti karakter ciphertext
        orig_ct = tampered_pkg["encrypted_payload"]
        tampered_pkg["encrypted_payload"] = ("A" if orig_ct[0] != "A" else "B") + orig_ct[1:]

        result = import_and_verify_vault(
            tampered_pkg, self.passphrase, local_blockchain=self.blockchain
        )
        self.assertFalse(result["valid"])
        self.assertIn(result["status"], ["INVALID_PASSPHRASE_OR_TAMPERED", "TAMPERED_CONTENT"])

    def test_tamper_blockchain_certificate_payload_hash(self):
        # Kepatuhan AC-06: Mengubah payload_sha256 pada sertifikat
        tampered_pkg = json.loads(json.dumps(self.vault_package))
        tampered_pkg["blockchain_certificate"]["payload_sha256"] = sha256_hex("Konten Berbeda")

        result = import_and_verify_vault(
            tampered_pkg, self.passphrase, local_blockchain=self.blockchain
        )
        self.assertFalse(result["valid"])
        self.assertEqual(result["status"], "TAMPERED_CONTENT")

    def test_tamper_blockchain_certificate_block_hash(self):
        # Kepatuhan AC-06: Mengubah nilai block_hash pada sertifikat
        tampered_pkg = json.loads(json.dumps(self.vault_package))
        tampered_pkg["blockchain_certificate"]["block_hash"] = "000" + "f" * 61

        result = import_and_verify_vault(
            tampered_pkg, self.passphrase, local_blockchain=self.blockchain
        )
        self.assertFalse(result["valid"])
        self.assertEqual(result["status"], "TAMPERED_CERTIFICATE")

    def test_wrong_passphrase_fails(self):
        result = import_and_verify_vault(
            self.vault_package, "PassphraseSalah123", local_blockchain=self.blockchain
        )
        self.assertFalse(result["valid"])
        self.assertEqual(result["status"], "INVALID_PASSPHRASE_OR_TAMPERED")

    def test_local_blockchain_conflict_detection(self):
        # Buat blockchain lokal terpisah di mana blok untuk doc_uuid ini memiliki hash berbeda
        other_ledger = os.path.join(self.temp_dir, "other_blockchain.json")
        other_chain = Blockchain(other_ledger)
        other_chain.mine_new_block(
            doc_uuid=self.doc_uuid,
            author="hacker",
            asset_type="MEMO_TEXT",
            payload_sha256=sha256_hex("Konten Palsu Lain")
        )

        result = import_and_verify_vault(
            self.vault_package, self.passphrase, local_blockchain=other_chain
        )
        self.assertFalse(result["valid"])
        self.assertEqual(result["status"], "TAMPERED_CHAIN")


if __name__ == "__main__":
    unittest.main(verbosity=2)
