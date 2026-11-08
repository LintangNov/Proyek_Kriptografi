"""
AegisVault Steganography Engine
Implementasi Penyisipan dan Ekstraksi Pesan Rahasia pada Citra Digital:
1. Citra RGB 24-bit (PNG Lossless)
2. Protokol Header 32-bit (4-byte Big-Endian) untuk presisi panjang payload
3. Substitusi LSB (Least Significant Bit) pada setiap kanal warna R, G, B
4. Framing Protocol: RAW:<pesan> atau ENC:<salt_hex>:<ciphertext_b64>

Catatan Kepatuhan Regulasi Kode:
- Dilarang menggunakan karakter em dash pada seluruh teks, label, dan komentar (Aturan R-02).
"""

import io
import os
from typing import Union
import numpy as np
from PIL import Image

from backend.crypto_engine import (
    generate_salt,
    derive_keys,
    super_encrypt_text,
    super_decrypt_text,
)


def calculate_capacity(width: int, height: int) -> int:
    """
    Menghitung kapasitas maksimal muatan (payload) dalam satuan byte
    untuk citra RGB 24-bit dengan dimensi W x H.
    
    Rumus:
    MaxPayloadBytes = floor((W * H * 3) / 8) - 4
    (4 byte dicadangkan untuk Header 32-bit Big-Endian).
    """
    total_channel_bytes = width * height * 3
    total_bytes = total_channel_bytes // 8
    max_payload = total_bytes - 4
    return max(0, max_payload)


def get_image_capacity(image_input: Union[str, Image.Image, bytes]) -> int:
    """Mengambil kapasitas muatan byte dari gambar input."""
    img = _load_image_rgb(image_input)
    return calculate_capacity(img.width, img.height)


def _load_image_rgb(image_input: Union[str, Image.Image, bytes]) -> Image.Image:
    """Memuat gambar dan memastikan formatnya adalah RGB 24-bit."""
    if isinstance(image_input, Image.Image):
        img = image_input
    elif isinstance(image_input, str):
        if not os.path.exists(image_input):
            raise FileNotFoundError(f"File citra tidak ditemukan: {image_input}")
        img = Image.open(image_input)
    elif isinstance(image_input, (bytes, bytearray)):
        img = Image.open(io.BytesIO(image_input))
    else:
        raise ValueError("Tipe input citra tidak didukung.")

    if img.mode != "RGB":
        img = img.convert("RGB")
    return img


def embed_message_into_image(
    image_input: Union[str, Image.Image, bytes],
    message: str,
    passphrase: str | None = None
) -> Image.Image:
    """
    Menyisipkan pesan rahasia ke dalam bit LSB citra RGB 24-bit.
    
    Framing Protocol:
    - Jika passphrase diisi: dienkripsi dengan Super Enkripsi -> "ENC:<salt_hex>:<ciphertext_b64>"
    - Jika passphrase kosong: plainteks langsung -> "RAW:<message>"
    - Header 4-byte Big-Endian memuat panjang byte payload.
    """
    if not message:
        raise ValueError("Pesan rahasia tidak boleh kosong.")

    img = _load_image_rgb(image_input)
    w, h = img.width, img.height
    max_capacity = calculate_capacity(w, h)

    # Siapkan string payload sesuai framing protocol
    if passphrase:
        salt = generate_salt(16)
        k1, k2 = derive_keys(passphrase, salt)
        cipher_b64 = super_encrypt_text(message, k1, k2)
        payload_str = f"ENC:{salt.hex()}:{cipher_b64}"
    else:
        payload_str = f"RAW:{message}"

    payload_bytes = payload_str.encode("utf-8")
    payload_len = len(payload_bytes)

    if payload_len > max_capacity:
        raise ValueError(
            f"Ukuran payload ({payload_len} byte) melebihi kapasitas maksimal citra ({max_capacity} byte). "
            f"Gunakan citra berdimensi lebih besar atau perpendek pesan."
        )

    # Bentuk Header 4-byte (32-bit Big-Endian)
    header_bytes = payload_len.to_bytes(4, byteorder="big", signed=False)
    stream_bytes = header_bytes + payload_bytes

    # Konversi byte stream menjadi barisan bit (0 atau 1) dengan urutan Big-Endian
    stream_bits = np.unpackbits(np.frombuffer(stream_bytes, dtype=np.uint8))
    total_bits = len(stream_bits)

    # Ambil array piksel RGB
    img_array = np.array(img, dtype=np.uint8)
    flat_channels = img_array.flatten()

    # Substitusi LSB: (ChannelByte & 254) | bit
    flat_channels[:total_bits] = (flat_channels[:total_bits] & 0xFE) | stream_bits

    # Bentuk kembali citra RGB hasil modifikasi LSB
    modified_array = flat_channels.reshape((h, w, 3))
    return Image.fromarray(modified_array, mode="RGB")


def extract_message_from_image(
    image_input: Union[str, Image.Image, bytes],
    passphrase: str | None = None
) -> str:
    """
    Mengekstrak pesan rahasia dari citra LSB 24-bit.
    1. Membaca 32 bit pertama untuk menyusun integer panjang L (Big-Endian).
    2. Membaca L * 8 bit berikutnya untuk menyusun payload byte.
    3. Mengurai prefix framing (RAW: atau ENC:).
    """
    img = _load_image_rgb(image_input)
    w, h = img.width, img.height
    max_capacity = calculate_capacity(w, h)

    img_array = np.array(img, dtype=np.uint8)
    flat_channels = img_array.flatten()

    if len(flat_channels) < 32:
        raise ValueError("Ukuran citra terlalu kecil untuk memuat header steganografi.")

    # 1. Ekstraksi Header 32-bit (4 byte)
    header_bits = flat_channels[:32] & 1
    header_bytes = np.packbits(header_bits).tobytes()
    payload_len = int.from_bytes(header_bytes, byteorder="big", signed=False)

    if payload_len <= 0 or payload_len > max_capacity:
        raise ValueError(
            "Header steganografi tidak valid atau citra ini tidak memuat pesan rahasia AegisVault."
        )

    # 2. Ekstraksi Payload L * 8 bit
    payload_end_bit = 32 + (payload_len * 8)
    if payload_end_bit > len(flat_channels):
        raise ValueError("Panjang payload pada header melebihi ukuran kanal piksel citra.")

    payload_bits = flat_channels[32:payload_end_bit] & 1
    payload_bytes = np.packbits(payload_bits).tobytes()

    try:
        payload_str = payload_bytes.decode("utf-8")
    except UnicodeDecodeError:
        raise ValueError("Data payload steganografi rusak atau tidak dapat di-decode sebagai teks UTF-8.")

    # 3. Penguraian Framing Protocol
    if payload_str.startswith("RAW:"):
        return payload_str[4:]
    elif payload_str.startswith("ENC:"):
        if not passphrase:
            raise ValueError(
                "Pesan rahasia di dalam citra ini terenkripsi. Silakan masukkan Passphrase pengiriman."
            )
        parts = payload_str.split(":", 2)
        if len(parts) != 3:
            raise ValueError("Struktur payload steganografi terenkripsi tidak valid.")

        salt_hex = parts[1]
        cipher_b64 = parts[2]

        try:
            salt = bytes.fromhex(salt_hex)
            k1, k2 = derive_keys(passphrase, salt)
            decrypted_message = super_decrypt_text(cipher_b64, k1, k2)
            return decrypted_message
        except Exception as e:
            raise ValueError(
                f"Gagal mendekripsi pesan steganografi. Pastikan passphrase yang dimasukkan benar. Detail: {str(e)}"
            )
    else:
        raise ValueError("Format framing steganografi tidak dikenali (bukan RAW maupun ENC).")


def embed_and_save_png(
    input_image_path: str,
    output_png_path: str,
    message: str,
    passphrase: str | None = None
) -> str:
    """
    Helper untuk menyisipkan pesan dari file gambar sumber dan menyimpannya sebagai file PNG.
    """
    stego_img = embed_message_into_image(input_image_path, message, passphrase=passphrase)
    # Pastikan ekstensi selalu .png untuk menjaga sifat lossless LSB
    if not output_png_path.lower().endswith(".png"):
        output_png_path = output_png_path + ".png"

    os.makedirs(os.path.dirname(os.path.abspath(output_png_path)), exist_ok=True)
    stego_img.save(output_png_path, format="PNG")
    return output_png_path


def extract_from_png_file(
    png_file_path: str,
    passphrase: str | None = None
) -> str:
    """Helper untuk mengekstrak pesan langsung dari path file citra PNG."""
    return extract_message_from_image(png_file_path, passphrase=passphrase)

