"""
AegisVault Steganography Engine
Implementasi Penyisipan dan Ekstraksi Pesan Rahasia pada Citra Digital:
1. Format hasil sama dengan format gambar asli (PNG, BMP, TIFF, WebP, JPEG)
2. Protokol Header 32-bit (4-byte Big-Endian) untuk presisi panjang payload
3. PNG, BMP, TIFF, WebP: substitusi LSB pada setiap kanal warna R, G, B
4. JPEG: substitusi LSB pada koefisien DCT AC terkuantisasi selain 0 dan 1 (JSteg), jadi
   gambar tidak dikompres ulang dan pesan tetap utuh
5. Framing Protocol: RAW:<pesan> atau ENC:<salt_hex>:<ciphertext_b64>

Catatan Kepatuhan Regulasi Kode:
- Dilarang menggunakan karakter em dash pada seluruh teks, label, dan komentar (Aturan R-02).
"""

import io
import math
import os
import shutil
import tempfile
from typing import Any, Dict, Optional, Tuple, Union
import numpy as np
from PIL import Image, ImageOps

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


def _load_cover(image_input: Union[str, Image.Image, bytes], keep_orientation_tag: bool = False) -> Tuple[Image.Image, Optional[Image.Image], Dict[str, Any]]:
    """
    Memuat gambar sampul agar hasilnya tampak sama dengan aslinya.
    Mengembalikan (citra RGB, kanal alfa atau None, metadata tampilan).
    """
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

    info = {key: img.info[key] for key in ("dpi", "gamma") if key in img.info}
    # Profil warna CMYK tidak berlaku lagi setelah gambar menjadi RGB.
    if img.mode != "CMYK" and img.info.get("icc_profile"):
        info["icc_profile"] = img.info["icc_profile"]

    if keep_orientation_tag:
        # Hasil membawa EXIF asli, termasuk arah putar, jadi piksel dibiarkan seperti di berkas.
        exif = img.getexif()
        if len(exif):
            info["exif"] = exif.tobytes()
    else:
        # Foto HP menyimpan arah putar di EXIF. Tanpa EXIF di hasil, pikselnya yang diputar.
        img = ImageOps.exif_transpose(img)

    # Konversi langsung memotong nilai 16-bit ke 255 sehingga gambar menjadi putih.
    if img.mode.startswith("I") or img.mode == "F":
        depth = np.asarray(img, dtype=np.float64)
        scale = 257.0 if depth.max(initial=0) > 255 else 1.0
        img = Image.fromarray(np.clip(np.rint(depth / scale), 0, 255).astype(np.uint8))

    if img.mode in ("RGBA", "LA", "PA") or "transparency" in img.info:
        rgba = img.convert("RGBA")
        return rgba.convert("RGB"), rgba.getchannel("A"), info
    return img.convert("RGB"), None, info


def similarity_report(cover_rgb: Image.Image, stego_rgb: Image.Image) -> Dict[str, Any]:
    """Mengukur perbedaan piksel asli dan hasil. psnr_db bernilai None jika tidak ada yang berubah."""
    cover = np.asarray(cover_rgb, dtype=np.int16)
    stego = np.asarray(stego_rgb, dtype=np.int16)
    diff = np.abs(cover - stego)
    mse = float(np.mean(diff.astype(np.float64) ** 2))
    return {
        "channels_changed": int(np.count_nonzero(diff)),
        "channels_total": int(diff.size),
        "max_channel_diff": int(diff.max(initial=0)),
        "psnr_db": None if mse == 0 else round(10 * math.log10(255 ** 2 / mse), 2),
    }


def save_stego_png(stego: Image.Image) -> bytes:
    """PNG tanpa kompresi hilang, membawa profil warna dan DPI gambar asli."""
    options: Dict[str, Any] = {"format": "PNG"}
    for key in ("icc_profile", "dpi", "exif"):
        if stego.info.get(key):
            options[key] = stego.info[key]
    # Tidak ada satu pengaturan yang selalu paling kecil, jadi ukuran file dipilih dari hasilnya.
    candidates = []
    for extra in ({"compress_level": 9}, {"optimize": True}):
        out = io.BytesIO()
        stego.save(out, **options, **extra)
        candidates.append(out.getvalue())
    return min(candidates, key=len)


def embed_message_into_image(
    image_input: Union[str, Image.Image, bytes],
    message: str,
    passphrase: str | None = None
) -> Image.Image:
    """Menyisipkan pesan dan mengembalikan citra hasilnya saja."""
    return embed_with_report(image_input, message, passphrase)[0]


def embed_with_report(
    image_input: Union[str, Image.Image, bytes],
    message: str,
    passphrase: str | None = None
) -> Tuple[Image.Image, Dict[str, Any]]:
    """
    Menyisipkan pesan rahasia ke dalam bit LSB citra RGB 24-bit.
    Hanya kanal R, G, dan B yang berubah. Kanal alfa dan metadata tampilan dipertahankan.
    Mengembalikan (citra hasil, laporan kemiripan).

    Framing Protocol:
    - Jika passphrase diisi: dienkripsi dengan Super Enkripsi -> "ENC:<salt_hex>:<ciphertext_b64>"
    - Jika passphrase kosong: plainteks langsung -> "RAW:<message>"
    - Header 4-byte Big-Endian memuat panjang byte payload.
    """
    img, alpha, display_info = _load_cover(image_input)
    return _embed_pixels(img, alpha, display_info, _build_stream(message, passphrase))


def _build_stream(message: str, passphrase: str | None) -> bytes:
    """Header 4 byte Big-Endian berisi panjang payload, diikuti payload RAW: atau ENC:."""
    if not message:
        raise ValueError("Pesan rahasia tidak boleh kosong.")
    if passphrase:
        salt = generate_salt(16)
        k1, k2 = derive_keys(passphrase, salt)
        cipher_b64 = super_encrypt_text(message, k1, k2)
        payload_str = f"ENC:{salt.hex()}:{cipher_b64}"
    else:
        payload_str = f"RAW:{message}"
    payload_bytes = payload_str.encode("utf-8")
    return len(payload_bytes).to_bytes(4, byteorder="big", signed=False) + payload_bytes


def _too_big(stream: bytes, capacity: int) -> ValueError:
    return ValueError(
        f"Ukuran payload ({len(stream) - 4} byte) melebihi kapasitas maksimal citra ({capacity} byte). "
        f"Gunakan citra berdimensi lebih besar atau perpendek pesan."
    )


def _embed_pixels(img: Image.Image, alpha: Optional[Image.Image], display_info: Dict[str, Any], stream_bytes: bytes) -> Tuple[Image.Image, Dict[str, Any]]:
    w, h = img.width, img.height
    max_capacity = calculate_capacity(w, h)
    if len(stream_bytes) - 4 > max_capacity:
        raise _too_big(stream_bytes, max_capacity)

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
    stego_rgb = Image.fromarray(modified_array)
    report = similarity_report(img, stego_rgb)
    result = stego_rgb
    if alpha is not None:
        result = stego_rgb.convert("RGBA")
        result.putalpha(alpha)
    result.info.update(display_info)
    return result, report


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
    return _parse_payload(_extract_payload(image_input), passphrase)


def _extract_payload(image_input: Union[str, Image.Image, bytes]) -> bytes:
    """Membaca header dan payload mentah. JPEG dibaca dari koefisien DCT, format lain dari piksel."""
    if not isinstance(image_input, Image.Image) and detect_format(image_input) in JPEG_FORMATS:
        return _extract_jpeg_payload(_read_bytes(image_input))
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
    return np.packbits(payload_bits).tobytes()


def _parse_payload(payload_bytes: bytes, passphrase: str | None) -> str:
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
    with open(output_png_path, "wb") as f:
        f.write(save_stego_png(stego_img))
    return output_png_path


def extract_from_png_file(
    png_file_path: str,
    passphrase: str | None = None
) -> str:
    """Helper untuk mengekstrak pesan langsung dari path file citra PNG."""
    return extract_message_from_image(png_file_path, passphrase=passphrase)



# ---------- Format hasil sama dengan format asli ----------

# Pillow menyebut foto HP bergambar ganda sebagai MPO. Isinya tetap JPEG.
JPEG_FORMATS = ("JPEG", "MPO")
SUPPORTED_FORMATS: Dict[str, Tuple[str, str]] = {
    "PNG": (".png", "image/png"),
    "JPEG": (".jpg", "image/jpeg"),
    "BMP": (".bmp", "image/bmp"),
    "TIFF": (".tif", "image/tiff"),
    "WEBP": (".webp", "image/webp"),
}
UNSUPPORTED_MESSAGE = "Format gambar ini belum didukung. Pakai PNG, JPG, BMP, TIFF, atau WebP."
_LOSSLESS_TIFF = ("raw", "tiff_lzw", "tiff_adobe_deflate", "tiff_deflate", "packbits")


def _read_bytes(image_input: Union[str, bytes]) -> bytes:
    if isinstance(image_input, str):
        with open(image_input, "rb") as f:
            return f.read()
    return bytes(image_input)


def detect_format(image_input: Union[str, bytes]) -> Optional[str]:
    """Format berdasarkan isi berkas, bukan nama berkas. None jika bukan gambar."""
    try:
        with Image.open(io.BytesIO(_read_bytes(image_input))) as img:
            return img.format
    except Exception:
        return None


def _supported_format(data: bytes) -> str:
    """Mengembalikan nama format baku, atau ValueError dengan alasan yang bisa dibaca pengguna."""
    try:
        with Image.open(io.BytesIO(data)) as img:
            fmt = "JPEG" if img.format in JPEG_FORMATS else img.format
            frames = getattr(img, "n_frames", 1)
    except Exception:
        raise ValueError("Berkas ini bukan gambar yang bisa dibaca.")
    if fmt == "GIF":
        raise ValueError("GIF hanya punya 256 warna, jadi pesan akan rusak. Pakai PNG, JPG, BMP, TIFF, atau WebP.")
    if fmt not in SUPPORTED_FORMATS:
        raise ValueError(UNSUPPORTED_MESSAGE)
    if frames > 1 and fmt != "JPEG":
        raise ValueError("Gambar bergerak atau berhalaman banyak belum didukung. Pakai gambar diam satu halaman.")
    return fmt


class _JpegFile:
    """jpeglib hanya bekerja dengan path berkas, jadi isi JPEG ditulis ke folder sementara."""

    def __init__(self, data: bytes):
        self.data = data

    def __enter__(self):
        self.dir = tempfile.mkdtemp(prefix="aegis-stego-")
        self.src = os.path.join(self.dir, "asli.jpg")
        self.dst = os.path.join(self.dir, "hasil.jpg")
        with open(self.src, "wb") as f:
            f.write(self.data)
        return self

    def __exit__(self, *exc):
        shutil.rmtree(self.dir, ignore_errors=True)


def _read_dct(path: str):
    import jpeglib  # dimuat saat dibutuhkan agar format lain tetap jalan tanpa pustaka ini
    try:
        jpeg = jpeglib.read_dct(path)
        jpeg.Y  # koefisien dimuat malas, jadi berkas rusak baru ketahuan di sini
        return jpeg
    except Exception:
        raise ValueError("Berkas JPEG ini rusak atau tidak bisa dibaca.")


def _dct_components(jpeg) -> list:
    comps = [jpeg.Y]
    if jpeg.has_chrominance:
        comps += [jpeg.Cb, jpeg.Cr]
    k = getattr(jpeg, "K", None)
    if k is not None:
        comps.append(k)
    return comps


def _usable_indices(comp: np.ndarray) -> np.ndarray:
    """
    Koefisien AC selain 0 dan 1 (cara JSteg). Mengganti bit terendahnya hanya menukar
    2 dengan 3 atau -2 dengan -1, jadi nilainya tidak pernah menjadi 0 atau 1 dan pembaca
    pesan menemukan posisi yang sama. Koefisien DC tidak disentuh.
    """
    mask = (comp != 0) & (comp != 1)
    mask[..., 0, 0] = False
    return np.flatnonzero(mask)


def _jpeg_capacity(jpeg) -> int:
    usable = sum(len(_usable_indices(c)) for c in _dct_components(jpeg))
    return max(0, usable // 8 - 4)


def _embed_jpeg(data: bytes, stream_bytes: bytes) -> Tuple[bytes, Dict[str, Any]]:
    with _JpegFile(data) as tmp:
        jpeg = _read_dct(tmp.src)
        capacity = _jpeg_capacity(jpeg)
        if len(stream_bytes) - 4 > capacity:
            raise _too_big(stream_bytes, capacity)
        bits = np.unpackbits(np.frombuffer(stream_bytes, dtype=np.uint8)).astype(np.int16)
        pos, changed = 0, 0
        for comp in _dct_components(jpeg):
            if pos >= len(bits):
                break
            take = _usable_indices(comp)[: len(bits) - pos]
            flat = comp.reshape(-1).copy()
            values = flat[take]
            # Bit terendah bilangan komplemen dua: (c & ~1) | bit, perubahan paling besar 1.
            new_values = (values & ~1) | bits[pos: pos + len(take)]
            changed += int(np.count_nonzero(new_values != values))
            flat[take] = new_values
            comp[...] = flat.reshape(comp.shape)
            pos += len(take)
        jpeg.write_dct(tmp.dst)
        with open(tmp.dst, "rb") as f:
            out = f.read()
    cover = Image.open(io.BytesIO(data)).convert("RGB")
    stego = Image.open(io.BytesIO(out)).convert("RGB")
    report = similarity_report(cover, stego)
    report.update({"coefficients_changed": changed, "coefficients_used": pos})
    return out, report


def _extract_jpeg_payload(data: bytes) -> bytes:
    with _JpegFile(data) as tmp:
        jpeg = _read_dct(tmp.src)
        capacity = _jpeg_capacity(jpeg)
        bits = np.concatenate([c.reshape(-1)[_usable_indices(c)] & 1 for c in _dct_components(jpeg)]).astype(np.uint8)
    if len(bits) < 32:
        raise ValueError("Ukuran citra terlalu kecil untuk memuat header steganografi.")
    payload_len = int.from_bytes(np.packbits(bits[:32]).tobytes(), byteorder="big", signed=False)
    if payload_len <= 0 or payload_len > capacity:
        raise ValueError("Header steganografi tidak valid atau citra ini tidak memuat pesan rahasia AegisVault.")
    return np.packbits(bits[32: 32 + payload_len * 8]).tobytes()


def _save_same_format(stego: Image.Image, fmt: str, source_info: Dict[str, Any]) -> bytes:
    """Menyimpan tanpa kompresi hilang dalam format yang sama dengan berkas asli."""
    if fmt == "PNG":
        return save_stego_png(stego)
    keep = {key: stego.info[key] for key in ("icc_profile", "dpi", "exif") if stego.info.get(key)}
    out = io.BytesIO()
    if fmt == "BMP":
        stego.save(out, format="BMP", **({"dpi": keep["dpi"]} if "dpi" in keep else {}))
    elif fmt == "TIFF":
        compression = source_info.get("compression")
        stego.save(out, format="TIFF", compression=compression if compression in _LOSSLESS_TIFF else "tiff_lzw", **keep)
    elif fmt == "WEBP":
        # exact menjaga warna di bawah piksel transparan, yang juga membawa bit pesan.
        stego.save(out, format="WEBP", lossless=True, exact=True, quality=100, method=4, **keep)
    return out.getvalue()


def capacity_info(data: bytes) -> Dict[str, Any]:
    """Kapasitas pesan dalam byte untuk berkas gambar ini, sesuai cara penyisipan formatnya."""
    fmt = _supported_format(data)
    with Image.open(io.BytesIO(data)) as img:
        width, height = img.size
    if fmt == "JPEG":
        with _JpegFile(data) as tmp:
            capacity = _jpeg_capacity(_read_dct(tmp.src))
    else:
        capacity = calculate_capacity(width, height)
    ext, mime = SUPPORTED_FORMATS[fmt]
    return {"format": fmt, "extension": ext, "mime": mime, "capacity_bytes": capacity,
            "width": width, "height": height, "method": "dct" if fmt == "JPEG" else "lsb"}


def embed_file(data: bytes, message: str, passphrase: str | None = None) -> Tuple[bytes, Dict[str, Any], str]:
    """
    Menyisipkan pesan dan mengembalikan (isi berkas hasil, laporan kemiripan, format).
    Format hasil selalu sama dengan format berkas asli.
    """
    fmt = _supported_format(data)
    stream = _build_stream(message, passphrase)
    if fmt == "JPEG":
        out, report = _embed_jpeg(data, stream)
        report["method"] = "dct"
    else:
        with Image.open(io.BytesIO(data)) as src:
            source_info = dict(src.info)
        img, alpha, display_info = _load_cover(data, keep_orientation_tag=True)
        stego, report = _embed_pixels(img, alpha, display_info, stream)
        report["method"] = "lsb"
        out = _save_same_format(stego, fmt, source_info)
    # Hasil dibaca ulang, supaya berkas yang diunduh pasti memuat pesan yang sama.
    if _extract_payload(out) != stream[4:]:
        raise RuntimeError("Pesan tidak terbaca ulang dari berkas hasil.")
    report["format"] = fmt
    return out, report, fmt
