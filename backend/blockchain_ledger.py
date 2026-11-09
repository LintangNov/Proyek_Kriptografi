"""
AegisVault Blockchain Ledger & Document Certification Engine
Implementasi Buku Besar Rantai Blok Lokal dan Sertifikat Keaslian Dokumen:
1. Proof-of-Work (PoW) dengan awalan hash '000'
2. Pembuatan dan Validasi Rantai Blok (Genesis Block s.d. Block N)
3. Pembungkusan Dokumen Terenkripsi (.vault) dengan Sertifikat Blockchain
4. Verifikasi Integritas dan Anti-Tampering Dokumen Impor Antar-Staf

Catatan Kepatuhan Regulasi Kode:
- Dilarang menggunakan karakter em dash pada seluruh teks, label, dan komentar (Aturan R-02).
"""

import hashlib
import hmac
import json
import os
from datetime import datetime, timezone
from typing import Dict, Any, List, Tuple, Union

from backend.crypto_engine import (
    sha256_hex,
    generate_salt,
    derive_keys,
    super_encrypt_text,
    super_decrypt_text,
)

POW_DIFFICULTY_PREFIX = "000"
DEFAULT_LEDGER_PATH = os.path.join("storage", "blockchain.json")


def get_current_utc_timestamp() -> str:
    """Mengembalikan timestamp ISO 8601 UTC terstandarisasi."""
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def compute_block_hash(
    index: int,
    timestamp: str,
    doc_uuid: str,
    author: str,
    payload_sha256: str,
    previous_hash: str,
    nonce: int
) -> str:
    """
    Menghitung hash SHA-256 blok dari penggabungan seluruh elemen header blok.
    
    Rumus:
    BlockHash = SHA256(index || timestamp || doc_uuid || author || payload_sha256 || previous_hash || nonce)
    """
    raw_payload = f"{index}{timestamp}{doc_uuid}{author}{payload_sha256}{previous_hash}{nonce}"
    return sha256_hex(raw_payload)


def mine_pow(
    index: int,
    timestamp: str,
    doc_uuid: str,
    author: str,
    payload_sha256: str,
    previous_hash: str,
    difficulty_prefix: str = POW_DIFFICULTY_PREFIX
) -> Tuple[int, str]:
    """
    Menjalankan proses Proof-of-Work (PoW) untuk menemukan nilai nonce
    sehingga BlockHash diawali dengan awalan kesulitan (default '000').
    """
    nonce = 0
    while True:
        candidate_hash = compute_block_hash(
            index, timestamp, doc_uuid, author, payload_sha256, previous_hash, nonce
        )
        if candidate_hash.startswith(difficulty_prefix):
            return nonce, candidate_hash
        nonce += 1


class Blockchain:
    """
    Pengelola Rantai Blok Lokal AegisVault.
    Menyimpan riwayat penerbitan sertifikat keaslian dokumen dan berkas.
    """

    def __init__(self, ledger_path: str = DEFAULT_LEDGER_PATH):
        self.ledger_path = ledger_path
        self.chain: List[Dict[str, Any]] = []
        self.load_or_initialize_chain()

    def create_genesis_block(self) -> Dict[str, Any]:
        """Membuat Blok Genesis (Blok Pertama) dengan PoW."""
        index = 0
        timestamp = "2026-01-01T00:00:00Z"
        doc_uuid = "GENESIS-AEGIS-VAULT"
        author = "SYSTEM_ROOT"
        asset_type = "GENESIS"
        payload_sha256 = "0" * 64
        previous_hash = "0" * 64

        nonce, block_hash = mine_pow(
            index, timestamp, doc_uuid, author, payload_sha256, previous_hash
        )

        return {
            "index": index,
            "timestamp": timestamp,
            "doc_uuid": doc_uuid,
            "author": author,
            "asset_type": asset_type,
            "payload_sha256": payload_sha256,
            "previous_hash": previous_hash,
            "nonce": nonce,
            "block_hash": block_hash
        }

    def load_or_initialize_chain(self) -> None:
        """Memuat rantai dari file ledger atau menginisialisasi Genesis Block jika belum ada."""
        if os.path.exists(self.ledger_path):
            try:
                with open(self.ledger_path, "r", encoding="utf-8") as f:
                    data = json.load(f)
                    if isinstance(data, list) and len(data) > 0:
                        self.chain = data
                        return
            except Exception:
                # Jika file rusak, inisialisasi rantai baru
                pass

        # Inisialisasi rantai baru dengan Genesis Block
        genesis = self.create_genesis_block()
        self.chain = [genesis]
        self.save_chain()

    def save_chain(self) -> None:
        """Menyimpan rantai blok ke file storage/blockchain.json secara aman."""
        os.makedirs(os.path.dirname(os.path.abspath(self.ledger_path)), exist_ok=True)
        temp_path = self.ledger_path + ".tmp"
        with open(temp_path, "w", encoding="utf-8") as f:
            json.dump(self.chain, f, indent=2, ensure_ascii=False)
        # Operasi rename atomik untuk mencegah file korup
        os.replace(temp_path, self.ledger_path)

    def get_last_block(self) -> Dict[str, Any]:
        """Mengambil blok terakhir dalam rantai."""
        return self.chain[-1]

    def mine_new_block(
        self,
        doc_uuid: str,
        author: str,
        asset_type: str,
        payload_sha256: str,
        timestamp: str | None = None
    ) -> Dict[str, Any]:
        """
        Mencetak blok sertifikat baru pada rantai melalui penambangan Proof-of-Work.
        """
        last_block = self.get_last_block()
        new_index = last_block["index"] + 1
        previous_hash = last_block["block_hash"]
        ts = timestamp if timestamp else get_current_utc_timestamp()

        nonce, block_hash = mine_pow(
            new_index, ts, doc_uuid, author, payload_sha256, previous_hash
        )

        new_block = {
            "index": new_index,
            "timestamp": ts,
            "doc_uuid": doc_uuid,
            "author": author,
            "asset_type": asset_type,
            "payload_sha256": payload_sha256,
            "previous_hash": previous_hash,
            "nonce": nonce,
            "block_hash": block_hash
        }

        self.chain.append(new_block)
        self.save_chain()
        return new_block

    def is_chain_valid(self) -> Tuple[bool, str]:
        """
        Memeriksa integritas keseluruhan rantai blok:
        1. Validasi hash blok dan nonce Proof-of-Work ('000').
        2. Validasi keterikatan previous_hash antar blok berurutan.
        """
        if not self.chain:
            return False, "Rantai blok kosong."

        # Validasi Genesis Block
        genesis = self.chain[0]
        if genesis["index"] != 0:
            return False, "Indeks Blok Genesis bukan 0."
        computed_genesis_hash = compute_block_hash(
            genesis["index"],
            genesis["timestamp"],
            genesis["doc_uuid"],
            genesis["author"],
            genesis["payload_sha256"],
            genesis["previous_hash"],
            genesis["nonce"]
        )
        if computed_genesis_hash != genesis["block_hash"]:
            return False, "Hash Blok Genesis tidak valid."
        if not genesis["block_hash"].startswith(POW_DIFFICULTY_PREFIX):
            return False, f"Hash Blok Genesis tidak memenuhi syarat PoW ('{POW_DIFFICULTY_PREFIX}')."

        # Validasi Blok 1 s.d. N
        for i in range(1, len(self.chain)):
            current = self.chain[i]
            previous = self.chain[i - 1]

            if current["index"] != i:
                return False, f"Indeks urutan blok ke-{i} tidak valid (ditemukan: {current['index']})."

            if current["previous_hash"] != previous["block_hash"]:
                return False, f"Integritas putus pada blok ke-{i}: previous_hash tidak cocok dengan hash blok ke-{i - 1}."

            computed_hash = compute_block_hash(
                current["index"],
                current["timestamp"],
                current["doc_uuid"],
                current["author"],
                current["payload_sha256"],
                current["previous_hash"],
                current["nonce"]
            )
            if computed_hash != current["block_hash"]:
                return False, f"Hash blok ke-{i} telah dimanipulasi atau tidak cocok."

            if not current["block_hash"].startswith(POW_DIFFICULTY_PREFIX):
                return False, f"Blok ke-{i} tidak memenuhi Proof-of-Work ('{POW_DIFFICULTY_PREFIX}')."

        return True, "Seluruh rantai blok valid dan konsisten."

    def get_block_by_doc_uuid(self, doc_uuid: str) -> Dict[str, Any] | None:
        """Mencari blok berdasarkan UUID dokumen yang tercatat."""
        for block in self.chain:
            if block.get("doc_uuid") == doc_uuid:
                return block
        return None

    def get_chain(self) -> List[Dict[str, Any]]:
        """Mengambil salinan seluruh blok di rantai."""
        return list(self.chain)


# =====================================================================
# Pembuatan dan Verifikasi Paket Dokumen (.vault)
# =====================================================================

def compute_vault_mac(vault_package: Dict[str, Any], k1: bytes, k2: bytes) -> str:
    """
    HMAC-SHA256 atas seluruh isi paket, dengan kunci turunan passphrase.
    Tanpa passphrase, judul, kategori, pengirim, dan sertifikat tidak bisa diubah
    tanpa terdeteksi, walaupun blok dihitung ulang.
    """
    fields = {k: vault_package[k] for k in ("vault_version", "export_salt", "metadata", "encrypted_payload", "blockchain_certificate")}
    canonical = json.dumps(fields, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode("utf-8")
    mac_key = hashlib.sha256(b"AegisVault-Vault-MAC-v1" + k1 + k2).digest()
    return hmac.new(mac_key, canonical, hashlib.sha256).hexdigest()


def package_vault_file(
    doc_uuid: str,
    author: str,
    title_plain: str,
    category_plain: str,
    plaintext_content: str,
    passphrase: str,
    block: Dict[str, Any],
    created_at: str | None = None
) -> Dict[str, Any]:
    """
    Membungkus dokumen terenkripsi dengan Passphrase Bersama dan Sertifikat Blockchain
    menjadi struktur data paket .vault siap ekspor.
    """
    if not passphrase:
        raise ValueError("Passphrase pengiriman tidak boleh kosong saat mengekspor paket .vault.")

    # Validasi bahwa hash konten cocok dengan hash di sertifikat blok
    content_hash = sha256_hex(plaintext_content)
    if block["payload_sha256"] != content_hash:
        raise ValueError("Hash konten dokumen tidak cocok dengan sertifikat blok blockchain.")

    # Bangkitkan salt 16-byte untuk ekspor
    export_salt = generate_salt(16)
    k1, k2 = derive_keys(passphrase, export_salt)

    # Super Enkripsi (Extended Vigenere + AES-128-CBC)
    encrypted_payload = super_encrypt_text(plaintext_content, k1, k2)

    created_timestamp = created_at if created_at else get_current_utc_timestamp()

    vault_package = {
        "vault_version": "1.1",
        "export_salt": export_salt.hex(),
        "metadata": {
            "doc_uuid": doc_uuid,
            "author": author,
            "title_plain": title_plain,
            "category_plain": category_plain,
            "created_at": created_timestamp
        },
        "encrypted_payload": encrypted_payload,
        "blockchain_certificate": {
            "block_index": block["index"],
            "timestamp": block["timestamp"],
            "doc_uuid": block["doc_uuid"],
            "author": block["author"],
            "payload_sha256": block["payload_sha256"],
            "previous_hash": block["previous_hash"],
            "nonce": block["nonce"],
            "block_hash": block["block_hash"]
        }
    }
    vault_package["integrity_mac"] = compute_vault_mac(vault_package, k1, k2)
    return vault_package


def export_vault_to_file(vault_package: Dict[str, Any], output_path: str) -> str:
    """Menulis struktur data paket .vault ke disk."""
    if not output_path.lower().endswith(".vault"):
        output_path = output_path + ".vault"
    os.makedirs(os.path.dirname(os.path.abspath(output_path)), exist_ok=True)
    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(vault_package, f, indent=2, ensure_ascii=False)
    return output_path


def import_and_verify_vault(
    vault_input: Union[Dict[str, Any], str],
    passphrase: str,
    local_blockchain: Blockchain | None = None
) -> Dict[str, Any]:
    """
    Mendekripsi paket .vault dan memverifikasi keabsahan Sertifikat Blockchain.
    
    Kondisi Keberhasilan:
    1. Passphrase cocok dan payload berhasil didekripsi.
    2. Hash konten hasil dekripsi identik dengan payload_sha256 pada sertifikat.
    3. Hash ulang blok cocok dengan block_hash dan memenuhi PoW ('000').
    4. Jika local_blockchain diberikan dan UUID ditemukan, block_hash harus cocok dengan buku besar lokal.
    """
    # 1. Parsing Input
    if isinstance(vault_input, str):
        # Jika berupa path file
        if os.path.exists(vault_input):
            with open(vault_input, "r", encoding="utf-8") as f:
                vault_data = json.load(f)
        else:
            try:
                vault_data = json.loads(vault_input)
            except Exception as e:
                return {
                    "valid": False,
                    "status": "INVALID_FORMAT",
                    "message": f"Format file atau JSON paket .vault rusak: {str(e)}",
                    "decrypted_content": None,
                    "metadata": None,
                    "certificate": None
                }
    elif isinstance(vault_input, dict):
        vault_data = vault_input
    else:
        return {
            "valid": False,
            "status": "INVALID_FORMAT",
            "message": "Tipe data input .vault tidak valid.",
            "decrypted_content": None,
            "metadata": None,
            "certificate": None
        }

    # Validasi Field Wajib
    # integrity_mac wajib ada: kalau boleh kosong, penyerang tinggal menghapusnya.
    required_fields = ["vault_version", "export_salt", "metadata", "encrypted_payload", "blockchain_certificate", "integrity_mac"]
    for field in required_fields:
        if field not in vault_data:
            return {
                "valid": False,
                "status": "INVALID_FORMAT",
                "message": f"Field wajib '{field}' tidak ditemukan pada paket .vault.",
                "decrypted_content": None,
                "metadata": None,
                "certificate": None
            }

    cert = vault_data["blockchain_certificate"]
    cert_fields = ["block_index", "timestamp", "doc_uuid", "author", "payload_sha256", "previous_hash", "nonce", "block_hash"]
    for cfield in cert_fields:
        if cfield not in cert:
            return {
                "valid": False,
                "status": "INVALID_FORMAT",
                "message": f"Field sertifikat '{cfield}' tidak ditemukan.",
                "decrypted_content": None,
                "metadata": vault_data.get("metadata"),
                "certificate": None
            }

    # 2. Dekripsi Payload menggunakan Passphrase
    try:
        salt = bytes.fromhex(vault_data["export_salt"])
        k1, k2 = derive_keys(passphrase, salt)
        decrypted_content = super_decrypt_text(vault_data["encrypted_payload"], k1, k2)
    except Exception as e:
        return {
            "valid": False,
            "status": "INVALID_PASSPHRASE_OR_TAMPERED",
            "message": f"Gagal mendekripsi isi dokumen: Passphrase salah atau ciphertext dokumen telah dimanipulasi ({str(e)}).",
            "decrypted_content": None,
            "metadata": vault_data.get("metadata"),
            "certificate": cert
        }

    # 3. Verifikasi Kondisi 1: Integritas Dokumen (Hash Dekripsi vs Sertifikat)
    computed_content_hash = sha256_hex(decrypted_content)
    if computed_content_hash.lower() != cert["payload_sha256"].lower():
        return {
            "valid": False,
            "status": "TAMPERED_CONTENT",
            "message": "PERINGATAN: INTEGRITAS DOKUMEN RUSAK / TERDETEKSI MANIPULASI (TAMPERED)! Hash dokumen hasil dekripsi tidak cocok dengan catatan sertifikat.",
            "decrypted_content": decrypted_content,
            "metadata": vault_data.get("metadata"),
            "certificate": cert
        }

    # 4. Verifikasi Kondisi 2: Keabsahan Sertifikat Blockchain & Proof-of-Work
    recalculated_block_hash = compute_block_hash(
        cert["block_index"],
        cert["timestamp"],
        cert["doc_uuid"],
        cert["author"],
        cert["payload_sha256"],
        cert["previous_hash"],
        cert["nonce"]
    )

    if recalculated_block_hash != cert["block_hash"]:
        return {
            "valid": False,
            "status": "TAMPERED_CERTIFICATE",
            "message": "PERINGATAN: SERTIFIKAT BLOCKCHAIN TIDAK VALID! Nilai block_hash pada sertifikat tidak sesuai dengan perhitungan ulang parameter blok.",
            "decrypted_content": decrypted_content,
            "metadata": vault_data.get("metadata"),
            "certificate": cert
        }

    if not cert["block_hash"].startswith(POW_DIFFICULTY_PREFIX):
        return {
            "valid": False,
            "status": "TAMPERED_CERTIFICATE",
            "message": f"PERINGATAN: SERTIFIKAT BLOCKCHAIN TIDAK MEMENUHI PROOF-OF-WORK (wajib diawali '{POW_DIFFICULTY_PREFIX}').",
            "decrypted_content": decrypted_content,
            "metadata": vault_data.get("metadata"),
            "certificate": cert
        }

    # Verifikasi seluruh isi paket dengan kunci turunan passphrase
    if not hmac.compare_digest(str(vault_data["integrity_mac"]), compute_vault_mac(vault_data, k1, k2)):
        return {
            "valid": False,
            "status": "TAMPERED_PACKAGE",
            "message": "PERINGATAN: ISI PAKET BERUBAH SETELAH DIEKSPOR! Judul, kategori, pengirim, atau sertifikat tidak cocok dengan kode integritas paket.",
            "decrypted_content": decrypted_content,
            "metadata": vault_data.get("metadata"),
            "certificate": cert
        }

    # 5. Verifikasi Kondisi 3: Pencocokan dengan Rantai Blok Lokal (Opsional jika ada)
    if local_blockchain is not None:
        local_block = local_blockchain.get_block_by_doc_uuid(cert["doc_uuid"])
        if local_block is not None:
            if local_block["block_hash"] != cert["block_hash"]:
                return {
                    "valid": False,
                    "status": "TAMPERED_CHAIN",
                    "message": "PERINGATAN: KONFLIK BUKU BESAR LOKAL! Dokumen dengan UUID ini ditemukan di blockchain lokal namun hash bloknya berbeda.",
                    "decrypted_content": decrypted_content,
                    "metadata": vault_data.get("metadata"),
                    "certificate": cert
                }

    # Seluruh verifikasi lulus 100%
    return {
        "valid": True,
        "status": "VALID",
        "message": "SERTIFIKAT BLOCKCHAIN VALID: DOKUMEN ASLI & BELUM DIMODIFIKASI",
        "decrypted_content": decrypted_content,
        "metadata": vault_data.get("metadata"),
        "certificate": cert
    }

