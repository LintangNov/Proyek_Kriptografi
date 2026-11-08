"""
AegisVault Cryptographic Engine
Implementasi Modul Kriptografi Tunggal untuk AegisVault:
1. PBKDF2-HMAC-SHA256 untuk Penurunan Kunci (Key Derivation)
2. SHA-256 + Dynamic Salt untuk Autentikasi Kredensial Login
3. Super Enkripsi Teks (Extended Vigenere 256 ASCII from-scratch + AES-128-CBC PKCS#7)
4. Enkripsi Berkas RC4 (KSA & PRGA from-scratch dengan 16-byte nonce unik)

Catatan Kepatuhan Regulasi Kode:
- Algoritma Extended Vigenere dan RC4 ditulis from-scratch dengan perulangan byte eksplisit.
- Dilarang menggunakan karakter em dash pada seluruh teks, label, dan komentar (Aturan R-02).
"""

import base64
import hashlib
import hmac
import os
from typing import Tuple, Dict, Any
from Crypto.Cipher import AES


# =====================================================================
# 1. Manajemen & Penurunan Kunci (PBKDF2-HMAC-SHA256)
# =====================================================================

def generate_salt(length: int = 16) -> bytes:
    """Membangkitkan cryptographically secure random salt."""
    if length <= 0:
        raise ValueError("Panjang salt harus lebih besar dari 0 byte.")
    return os.urandom(length)


def derive_keys(
    passphrase: str | bytes,
    salt: bytes,
    iterations: int = 100_000
) -> Tuple[bytes, bytes]:
    """
    Menurunkan dua kunci simetris 16-byte dari satu passphrase menggunakan PBKDF2-HMAC-SHA256.
    
    Rumus:
    DerivedMaterial = PBKDF2_HMAC_SHA256(Passphrase, Salt, iterations=100000, dklen=32)
    - K1 (16-byte): Extended Vigenere Key = DerivedMaterial[0:16]
    - K2 (16-byte): AES-128 Key = DerivedMaterial[16:32]
    """
    if isinstance(passphrase, str):
        passphrase_bytes = passphrase.encode("utf-8")
    else:
        passphrase_bytes = passphrase

    if not passphrase_bytes:
        raise ValueError("Passphrase tidak boleh kosong.")
    if len(salt) < 8:
        raise ValueError("Panjang salt minimal 8 byte (disarankan 16 byte).")

    derived_material = hashlib.pbkdf2_hmac(
        hash_name="sha256",
        password=passphrase_bytes,
        salt=salt,
        iterations=iterations,
        dklen=32
    )

    k1_vigenere = derived_material[0:16]
    k2_aes = derived_material[16:32]
    return k1_vigenere, k2_aes


# =====================================================================
# 2. Hashing Autentikasi Login (SHA-256 + Dynamic Salt)
# =====================================================================

def sha256_hex(data: bytes | str) -> str:
    """Menghitung ringkasan hash SHA-256 dalam bentuk string heksadesimal."""
    if isinstance(data, str):
        data = data.encode("utf-8")
    return hashlib.sha256(data).hexdigest()


def sha256_bytes(data: bytes | str) -> bytes:
    """Menghitung ringkasan hash SHA-256 dalam bentuk barisan byte mentah."""
    if isinstance(data, str):
        data = data.encode("utf-8")
    return hashlib.sha256(data).digest()


def hash_password(password: str, salt: bytes | None = None) -> Tuple[str, str]:
    """
    Melakukan hashing password pengguna dengan Dynamic Salt 16-byte.
    
    Rumus:
    PasswordHash = SHA256(Salt || UTF8(Password))
    
    Mengembalikan:
    (password_hash_hex, salt_hex)
    """
    if not password:
        raise ValueError("Password tidak boleh kosong.")
    if salt is None:
        salt = generate_salt(16)
    elif len(salt) < 8:
        raise ValueError("Salt minimal 8 byte.")

    password_bytes = password.encode("utf-8")
    combined = salt + password_bytes
    password_hash = hashlib.sha256(combined).hexdigest()
    return password_hash, salt.hex()


def verify_password(password: str, salt_hex: str, expected_hash_hex: str) -> bool:
    """
    Memvalidasi kesesuaian input password terhadap hash dan salt yang tersimpan.
    Menggunakan hmac.compare_digest untuk mencegah timing attack.
    """
    try:
        salt = bytes.fromhex(salt_hex)
    except ValueError:
        return False

    computed_hash, _ = hash_password(password, salt=salt)
    return hmac.compare_digest(computed_hash.lower(), expected_hash_hex.lower())


# =====================================================================
# 3. Tahap 1 Super Enkripsi: Extended Vigenere Cipher (256 ASCII)
# =====================================================================

def vigenere_256_encrypt(data: bytes, key: bytes) -> bytes:
    """
    Enkripsi Extended Vigenere Cipher pada domain byte 0..255 (From-Scratch).
    
    Rumus:
    C[i] = (P[i] + K[i mod m]) mod 256
    """
    if not key:
        raise ValueError("Kunci Extended Vigenere tidak boleh kosong.")
    if not data:
        return b""

    key_len = len(key)
    out = bytearray(len(data))
    for i in range(len(data)):
        out[i] = (data[i] + key[i % key_len]) % 256
    return bytes(out)


def vigenere_256_decrypt(ciphertext: bytes, key: bytes) -> bytes:
    """
    Dekripsi Extended Vigenere Cipher pada domain byte 0..255 (From-Scratch).
    
    Rumus:
    P[i] = (C[i] - K[i mod m]) mod 256
    """
    if not key:
        raise ValueError("Kunci Extended Vigenere tidak boleh kosong.")
    if not ciphertext:
        return b""

    key_len = len(key)
    out = bytearray(len(ciphertext))
    for i in range(len(ciphertext)):
        out[i] = (ciphertext[i] - key[i % key_len]) % 256
    return bytes(out)


# =====================================================================
# 4. Tahap 2 Super Enkripsi: AES-128 Mode CBC (PKCS#7 Padding)
# =====================================================================

def pkcs7_pad(data: bytes, block_size: int = 16) -> bytes:
    """Menerapkan PKCS#7 padding sehingga panjang data kelipatan block_size."""
    pad_len = block_size - (len(data) % block_size)
    return data + bytes([pad_len] * pad_len)


def pkcs7_unpad(data: bytes, block_size: int = 16) -> bytes:
    """Menghapus dan memvalidasi PKCS#7 padding."""
    if not data or (len(data) % block_size != 0):
        raise ValueError("Panjang data tidak valid untuk PKCS#7 unpadding.")
    pad_len = data[-1]
    if pad_len < 1 or pad_len > block_size:
        raise ValueError("Nilai padding byte tidak valid.")
    if data[-pad_len:] != bytes([pad_len] * pad_len):
        raise ValueError("Integritas PKCS#7 padding rusak.")
    return data[:-pad_len]


def aes_128_cbc_encrypt(data: bytes, key: bytes, iv: bytes | None = None) -> Tuple[bytes, bytes]:
    """
    Enkripsi AES-128 Mode CBC dengan PKCS#7 padding.
    Kunci wajib 16 byte (128 bit).
    Mengembalikan (ciphertext_bytes, iv_bytes).
    """
    if len(key) != 16:
        raise ValueError(f"Panjang kunci AES-128 wajib 16 byte, diterima: {len(key)} byte.")
    if iv is None:
        iv = os.urandom(16)
    elif len(iv) != 16:
        raise ValueError(f"Panjang IV wajib 16 byte, diterima: {len(iv)} byte.")

    padded_data = pkcs7_pad(data, 16)
    cipher = AES.new(key, AES.MODE_CBC, iv)
    ciphertext = cipher.encrypt(padded_data)
    return ciphertext, iv


def aes_128_cbc_decrypt(ciphertext: bytes, key: bytes, iv: bytes) -> bytes:
    """
    Dekripsi AES-128 Mode CBC dengan verifikasi PKCS#7 padding.
    """
    if len(key) != 16:
        raise ValueError(f"Panjang kunci AES-128 wajib 16 byte, diterima: {len(key)} byte.")
    if len(iv) != 16:
        raise ValueError(f"Panjang IV wajib 16 byte, diterima: {len(iv)} byte.")
    if len(ciphertext) == 0 or (len(ciphertext) % 16 != 0):
        raise ValueError("Panjang ciphertext AES wajib kelipatan 16 byte dan tidak kosong.")

    cipher = AES.new(key, AES.MODE_CBC, iv)
    decrypted_padded = cipher.decrypt(ciphertext)
    return pkcs7_unpad(decrypted_padded, 16)


# =====================================================================
# 5. Super Enkripsi Teks (Extended Vigenere + AES-128-CBC)
# =====================================================================

def super_encrypt_text(
    plaintext: str | bytes,
    key_vigenere: bytes,
    key_aes: bytes,
    iv: bytes | None = None
) -> str:
    """
    Melakukan Super Enkripsi dua tahap secara sekuensial:
    1. Plaintext byte dienkripsi dengan Extended Vigenere (K1).
    2. Hasil byte dienkripsi dengan AES-128-CBC (K2) dan IV acak.
    3. IV (16 byte) digabungkan di depan ciphertext dan di-encode ke Base64.
    """
    if isinstance(plaintext, str):
        plaintext_bytes = plaintext.encode("utf-8")
    else:
        plaintext_bytes = plaintext

    # Tahap 1: Extended Vigenere
    c1 = vigenere_256_encrypt(plaintext_bytes, key_vigenere)

    # Tahap 2: AES-128-CBC
    c2, iv_out = aes_128_cbc_encrypt(c1, key_aes, iv=iv)

    # Penggabungan IV + Ciphertext AES
    final_payload = iv_out + c2
    return base64.b64encode(final_payload).decode("ascii")


def super_decrypt_text(
    ciphertext_b64: str,
    key_vigenere: bytes,
    key_aes: bytes
) -> str:
    """
    Melakukan Super Dekripsi dua tahap secara terbalik:
    1. Decode Base64 dan pisahkan 16 byte pertama sebagai IV.
    2. Dekripsi AES-128-CBC dan unpad PKCS#7 untuk memperoleh C1.
    3. Dekripsi Extended Vigenere C1 dengan K1 untuk memperoleh plainteks asli.
    """
    try:
        raw_bytes = base64.b64decode(ciphertext_b64)
    except Exception as e:
        raise ValueError(f"Format Base64 tidak valid: {str(e)}")

    if len(raw_bytes) < 32:
        raise ValueError("Ukuran payload Super Enkripsi tidak valid (minimal 32 byte untuk IV + AES block).")

    iv = raw_bytes[:16]
    c2 = raw_bytes[16:]

    # Tahap 1 Balik: AES-128-CBC
    c1 = aes_128_cbc_decrypt(c2, key_aes, iv)

    # Tahap 2 Balik: Extended Vigenere
    plaintext_bytes = vigenere_256_decrypt(c1, key_vigenere)
    return plaintext_bytes.decode("utf-8")


def super_encrypt_inspect(
    plaintext: str,
    key_vigenere: bytes,
    key_aes: bytes
) -> Dict[str, Any]:
    """
    Menjalankan Super Enkripsi dengan mengembalikan rincian artefak tiap tahap
    untuk keperluan demonstrasi visual / inspeksi akademik kepada penguji.
    """
    p_bytes = plaintext.encode("utf-8")
    c1 = vigenere_256_encrypt(p_bytes, key_vigenere)
    c2, iv = aes_128_cbc_encrypt(c1, key_aes)
    final_b64 = base64.b64encode(iv + c2).decode("ascii")

    return {
        "plaintext": plaintext,
        "plaintext_bytes_len": len(p_bytes),
        "plaintext_hex": p_bytes.hex(),
        "vigenere_key_hex": key_vigenere.hex(),
        "vigenere_ciphertext_hex": c1.hex(),
        "aes_key_hex": key_aes.hex(),
        "aes_iv_hex": iv.hex(),
        "aes_ciphertext_hex": c2.hex(),
        "final_ciphertext_b64": final_b64
    }


def super_encrypt_with_passphrase(
    plaintext: str,
    passphrase: str,
    salt: bytes | None = None
) -> Tuple[str, str]:
    """
    Wrapper Super Enkripsi langsung dengan Passphrase dan Salt (PBKDF2).
    Mengembalikan (ciphertext_b64, salt_hex).
    """
    if salt is None:
        salt = generate_salt(16)
    k1, k2 = derive_keys(passphrase, salt)
    ciphertext_b64 = super_encrypt_text(plaintext, k1, k2)
    return ciphertext_b64, salt.hex()


def super_decrypt_with_passphrase(
    ciphertext_b64: str,
    passphrase: str,
    salt_hex: str
) -> str:
    """
    Wrapper Super Dekripsi langsung dengan Passphrase dan Salt Hex.
    """
    salt = bytes.fromhex(salt_hex)
    k1, k2 = derive_keys(passphrase, salt)
    return super_decrypt_text(ciphertext_b64, k1, k2)


# =====================================================================
# 6. Enkripsi Berkas Lampiran: RC4 Stream Cipher (From-Scratch)
# =====================================================================

def rc4_crypt(data: bytes, key: bytes) -> bytes:
    """
    Algoritma RC4 (ARCFOUR Stream Cipher) From-Scratch.
    Terdiri dari Key-Scheduling Algorithm (KSA) dan Pseudo-Random Generation Algorithm (PRGA).
    Sifat XOR simetris: fungsi ini dapat digunakan untuk enkripsi maupun dekripsi.
    """
    if not key:
        raise ValueError("Kunci RC4 tidak boleh kosong.")
    if not data:
        return b""

    # Tahap 1: Key-Scheduling Algorithm (KSA)
    S = list(range(256))
    j = 0
    key_len = len(key)
    for i in range(256):
        j = (j + S[i] + key[i % key_len]) % 256
        S[i], S[j] = S[j], S[i]

    # Tahap 2: Pseudo-Random Generation Algorithm (PRGA) & XOR
    i = 0
    j = 0
    out = bytearray(len(data))
    for k in range(len(data)):
        i = (i + 1) % 256
        j = (j + S[i]) % 256
        S[i], S[j] = S[j], S[i]
        t = (S[i] + S[j]) % 256
        out[k] = data[k] ^ S[t]

    return bytes(out)


def encrypt_file_rc4(
    data: bytes,
    key: bytes,
    nonce: bytes | None = None
) -> bytes:
    """
    Mengenksipsi aliran byte berkas dengan RC4 dan 16-byte nonce unik.
    
    Pencegahan Penggunaan Ulang Keystream (Per-File Nonce):
    Kunci efektif U = K_rc4 || file_nonce
    Format biner keluaran: file_nonce (16 byte) || Ciphertext
    """
    if not key:
        raise ValueError("Kunci enkripsi berkas RC4 tidak boleh kosong.")
    if nonce is None:
        nonce = os.urandom(16)
    elif len(nonce) != 16:
        raise ValueError(f"Panjang nonce berkas wajib 16 byte, diterima: {len(nonce)} byte.")

    # Gabungkan kunci dasar dengan nonce acak per file
    effective_key = key + nonce
    ciphertext = rc4_crypt(data, effective_key)
    return nonce + ciphertext


def decrypt_file_rc4(encrypted_data: bytes, key: bytes) -> bytes:
    """
    Mendekripsi berkas biner terenkripsi RC4 yang memiliki 16-byte nonce di awal berkas.
    """
    if not key:
        raise ValueError("Kunci dekripsi berkas RC4 tidak boleh kosong.")
    if len(encrypted_data) < 16:
        raise ValueError("Ukuran berkas terenkripsi RC4 tidak valid (minimal 16 byte nonce).")

    nonce = encrypted_data[:16]
    ciphertext = encrypted_data[16:]
    effective_key = key + nonce
    return rc4_crypt(ciphertext, effective_key)

