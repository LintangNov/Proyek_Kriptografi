"""
AegisVault Configuration
Konfigurasi path folder storage dan konstanta sistem.

Folder yang diinisialisasi oleh ensure_storage_dirs():
- storage/               : data lokal aplikasi (database, checksum, blockchain)
- storage/faces/         : matriks wajah staf (.npy)
- storage/attachments/   : berkas lampiran terenkripsi RC4 (.rc4)

Catatan Kepatuhan Regulasi Kode:
- Dilarang menggunakan karakter em dash pada seluruh teks dan komentar (Aturan R-02).
"""

import os
from typing import NamedTuple

# Direktori akar proyek (satu level di atas folder backend/).
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

# Lokasi storage bawaan. Dapat dialihkan lewat variabel lingkungan AEGIS_STORAGE_DIR
# (dipakai oleh pengujian otomatis agar tidak menyentuh data asli).
STORAGE_DIR = os.environ.get("AEGIS_STORAGE_DIR") or os.path.join(BASE_DIR, "storage")

# Nama berkas di dalam storage.
DB_FILENAME = "aegis_vault.db"
DB_CHECKSUM_FILENAME = "db_checksum.sha256"
BLOCKCHAIN_FILENAME = "blockchain.json"
FACES_DIRNAME = "faces"
ATTACHMENTS_DIRNAME = "attachments"

# Nama berkas dongle pada root USB Flashdisk.
DONGLE_KEY_FILENAME = "dongle.key"

# Pepper sistem untuk tanda tangan dongle.key dan penurunan kunci Field-Level Encryption.
# Dapat diganti lewat variabel lingkungan AEGIS_SYSTEM_PEPPER pada deployment nyata.
SYSTEM_SECRET_PEPPER = os.environ.get("AEGIS_SYSTEM_PEPPER") or "AegisVault::Kriptografi::2026::Pepper"

# Salt tetap untuk penurunan kunci sistem (Field-Level Encryption). Bukan rahasia,
# fungsinya memisahkan domain kunci agar tidak bentrok dengan penggunaan PBKDF2 lain.
SYSTEM_FIELD_KEY_SALT = b"AegisVault-FieldKey-v1"

# Interval polling dongle (detik). PRD mensyaratkan layar terkunci maksimal 3 detik
# setelah USB dicabut, sehingga nilai bawaan dibuat 1 detik.
DONGLE_POLL_INTERVAL_SECONDS = 1.0

# Batas ukuran berkas lampiran RC4 (PRD Bab 7 butir 1).
MAX_ATTACHMENT_BYTES = 20 * 1024 * 1024


class StoragePaths(NamedTuple):
    """Kumpulan path absolut seluruh komponen storage."""
    root: str
    db: str
    db_checksum: str
    blockchain: str
    faces: str
    attachments: str


def get_storage_paths(storage_dir: str | None = None) -> StoragePaths:
    """Menghitung seluruh path storage tanpa membuat folder apa pun."""
    root = os.path.abspath(storage_dir or STORAGE_DIR)
    return StoragePaths(
        root=root,
        db=os.path.join(root, DB_FILENAME),
        db_checksum=os.path.join(root, DB_CHECKSUM_FILENAME),
        blockchain=os.path.join(root, BLOCKCHAIN_FILENAME),
        faces=os.path.join(root, FACES_DIRNAME),
        attachments=os.path.join(root, ATTACHMENTS_DIRNAME),
    )


def ensure_storage_dirs(storage_dir: str | None = None) -> StoragePaths:
    """
    Membuat folder storage/, storage/faces/, dan storage/attachments/ jika belum ada.
    Aman dipanggil berulang kali (idempoten). Mengembalikan StoragePaths.
    """
    paths = get_storage_paths(storage_dir)
    for folder in (paths.root, paths.faces, paths.attachments):
        os.makedirs(folder, exist_ok=True)
    return paths

