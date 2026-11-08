"""
AegisVault Biometric Authentication Layer
Implementasi docs/TECHNICAL_SPEC.md Bab 3.2 B.

1. Deteksi kapabilitas sensor sidik jari (Windows Biometric Framework, winbio.dll
   lewat ctypes). Jika tidak ada sensor yang siap, mode aktif adalah FACE_RECOGNITION.
2. Pendaftaran dan verifikasi wajah dengan OpenCV (tanpa dlib):
   - Deteksi: cv2.CascadeClassifier(haarcascade_frontalface_default.xml)
   - Normalisasi: crop wajah, grayscale, resize 128x128, cv2.equalizeHist()
   - Penyimpanan: matriks 128x128 uint8 di storage/faces/{username}.npy
   - Pencocokan: kombinasi Normalized Cross-Correlation (cv2.matchTemplate) dan
     Histogram Comparison (cv2.compareHist). Cocok jika skor >= 0.72.

Rumus skor kemiripan:
    score = 0.6 * NCC + 0.4 * HIST, masing-masing dibatasi ke [0, 1]
    NCC  : cv2.matchTemplate(A, B, TM_CCOEFF_NORMED) pada dua matriks 128x128
    HIST : rata-rata korelasi (cv2.compareHist, HISTCMP_CORREL) histogram 32 bin
           pada grid 4x4 sel, agar histogram membawa informasi letak fitur wajah

Catatan: sensor sidik jari hanya dideteksi kapabilitasnya. Faktor biometrik yang
benar-benar diverifikasi aplikasi adalah pencocokan wajah.

Catatan Kepatuhan Regulasi Kode:
- Dilarang menggunakan karakter em dash pada seluruh teks dan komentar (Aturan R-02).
"""

import base64
import binascii
import os
import re
import sys
from typing import Any, Callable, Dict, List, Optional, Tuple

import cv2
import numpy as np

from backend import config

FACE_SIZE = 128
MATCH_THRESHOLD = 0.72
NCC_WEIGHT = 0.6
HIST_WEIGHT = 0.4
HIST_GRID = 4
HIST_BINS = 32
CASCADE_FILENAME = "haarcascade_frontalface_default.xml"

MODE_FINGERPRINT = "FINGERPRINT"
MODE_FACE = "FACE_RECOGNITION"

MAX_IMAGE_BYTES = 10 * 1024 * 1024
_USERNAME_PATTERN = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_.\-]{0,63}$")


# =====================================================================
# Pengecualian Khusus
# =====================================================================

class BiometricError(Exception):
    """Kesalahan umum lapisan biometrik."""


class InvalidImageError(BiometricError):
    """Data gambar bukan base64 gambar yang dapat didekode."""


class NoFaceDetectedError(BiometricError):
    """Tidak ada wajah terdeteksi pada frame."""


class FaceNotEnrolledError(BiometricError):
    """Staf belum memiliki matriks wajah terdaftar."""


# =====================================================================
# 1. Deteksi kapabilitas sidik jari (Windows Biometric Framework)
# =====================================================================

WINBIO_TYPE_FINGERPRINT = 0x00000008


def _windows_fingerprint_unit_count() -> int:
    """Jumlah unit biometrik sidik jari yang terdaftar di WBF. 0 jika tidak ada atau gagal."""
    import ctypes
    from ctypes import POINTER, byref, c_size_t, c_void_p

    winbio = ctypes.WinDLL("winbio.dll")
    enum_units = winbio.WinBioEnumBiometricUnits
    enum_units.argtypes = [ctypes.c_uint32, POINTER(c_void_p), POINTER(c_size_t)]
    enum_units.restype = ctypes.c_long
    free = winbio.WinBioFree
    free.argtypes = [c_void_p]
    free.restype = ctypes.c_long

    schema_array = c_void_p()
    count = c_size_t(0)
    hresult = enum_units(WINBIO_TYPE_FINGERPRINT, byref(schema_array), byref(count))
    try:
        return int(count.value) if hresult == 0 else 0
    finally:
        if schema_array.value:
            free(schema_array)


def detect_fingerprint_capability(
    unit_counter: Optional[Callable[[], int]] = None,
) -> Dict[str, Any]:
    """
    Mengecek sensor sidik jari PC. unit_counter dapat disuntikkan untuk pengujian.

    Mengembalikan:
        {"fingerprint_available": bool,
         "active_mode": "FINGERPRINT" | "FACE_RECOGNITION",
         "face_verification_enabled": True,
         "detail": str}
    Tanpa sensor siap pakai: {"fingerprint_available": False, "active_mode": "FACE_RECOGNITION"}.
    """
    detail = ""
    available = False
    try:
        if unit_counter is not None:
            available = unit_counter() > 0
        elif sys.platform == "win32":
            available = _windows_fingerprint_unit_count() > 0
        else:
            detail = "Windows Biometric Framework hanya tersedia di Windows."
    except Exception as exc:
        available = False
        detail = f"Pengecekan sensor gagal: {exc}"

    if not detail:
        detail = ("Sensor sidik jari terdeteksi." if available
                  else "Sensor Fingerprint Tidak Tersedia: Mode Biometrik Face Recognition Aktif.")
    return {
        "fingerprint_available": available,
        "active_mode": MODE_FINGERPRINT if available else MODE_FACE,
        "face_verification_enabled": True,
        "detail": detail,
    }


# =====================================================================
# 2. Pengolahan gambar dan deteksi wajah
# =====================================================================

_cascade: Optional[cv2.CascadeClassifier] = None


def _get_cascade() -> cv2.CascadeClassifier:
    global _cascade
    if _cascade is None:
        cascade = cv2.CascadeClassifier(cv2.data.haarcascades + CASCADE_FILENAME)
        if cascade.empty():
            raise BiometricError(f"Berkas {CASCADE_FILENAME} tidak dapat dimuat dari OpenCV.")
        _cascade = cascade
    return _cascade


def decode_base64_image(data: str) -> np.ndarray:
    """
    Mendekode string base64 (boleh berawalan data URL 'data:image/jpeg;base64,')
    menjadi citra BGR OpenCV.
    """
    if not isinstance(data, str) or not data.strip():
        raise InvalidImageError("Data gambar kosong.")
    payload = data.strip()
    if payload.startswith("data:"):
        _header, _sep, payload = payload.partition(",")
    try:
        raw = base64.b64decode(payload, validate=True)
    except (binascii.Error, ValueError) as exc:
        raise InvalidImageError("Data gambar bukan base64 yang valid.") from exc
    if not raw:
        raise InvalidImageError("Data gambar kosong.")
    if len(raw) > MAX_IMAGE_BYTES:
        raise InvalidImageError("Ukuran gambar melebihi batas 10 MB.")
    image = cv2.imdecode(np.frombuffer(raw, dtype=np.uint8), cv2.IMREAD_COLOR)
    if image is None:
        raise InvalidImageError("Data bukan gambar yang dikenali.")
    return image


def normalize_face(gray_crop: np.ndarray) -> np.ndarray:
    """Resize ke 128x128 lalu cv2.equalizeHist(). Masukan grayscale uint8."""
    resized = cv2.resize(gray_crop, (FACE_SIZE, FACE_SIZE), interpolation=cv2.INTER_AREA)
    return cv2.equalizeHist(resized)


def extract_face(image_bgr: np.ndarray) -> np.ndarray:
    """
    Mendeteksi wajah dengan Haar Cascade, memilih wajah terbesar, lalu mengembalikan
    matriks 128x128 uint8 ternormalisasi. Melempar NoFaceDetectedError bila tidak ada.
    """
    gray = cv2.cvtColor(image_bgr, cv2.COLOR_BGR2GRAY)
    faces = _get_cascade().detectMultiScale(
        gray, scaleFactor=1.1, minNeighbors=5, minSize=(60, 60)
    )
    if faces is None or len(faces) == 0:
        raise NoFaceDetectedError("Wajah tidak terdeteksi. Pastikan wajah terlihat jelas dan pencahayaan cukup.")
    x, y, w, h = max(faces, key=lambda f: int(f[2]) * int(f[3]))
    return normalize_face(gray[y:y + h, x:x + w])


def extract_face_from_base64(frame_b64: str) -> np.ndarray:
    return extract_face(decode_base64_image(frame_b64))


# =====================================================================
# 3. Pencocokan wajah: NCC + Histogram
# =====================================================================

def _grid_histogram(face: np.ndarray) -> np.ndarray:
    """Histogram 32 bin per sel pada grid 4x4, dinormalisasi, digabung menjadi satu vektor."""
    cell = FACE_SIZE // HIST_GRID
    parts: List[np.ndarray] = []
    for row in range(HIST_GRID):
        for col in range(HIST_GRID):
            patch = face[row * cell:(row + 1) * cell, col * cell:(col + 1) * cell]
            hist = cv2.calcHist([patch], [0], None, [HIST_BINS], [0, 256])
            cv2.normalize(hist, hist, alpha=1.0, beta=0.0, norm_type=cv2.NORM_L1)
            parts.append(hist)
    return np.concatenate(parts, axis=0).astype(np.float32)


def compute_similarity(face_a: np.ndarray, face_b: np.ndarray) -> Dict[str, float]:
    """
    Skor kemiripan dua matriks wajah 128x128 uint8.
    Mengembalikan {"score", "ncc", "hist"}, seluruhnya dalam rentang [0, 1].
    """
    for face in (face_a, face_b):
        if face.shape != (FACE_SIZE, FACE_SIZE) or face.dtype != np.uint8:
            raise ValueError(f"Matriks wajah wajib {FACE_SIZE}x{FACE_SIZE} bertipe uint8.")

    ncc_raw = float(cv2.matchTemplate(face_a, face_b, cv2.TM_CCOEFF_NORMED)[0][0])
    if not np.isfinite(ncc_raw):  # citra seragam: varians nol
        ncc_raw = 0.0
    ncc = min(1.0, max(0.0, ncc_raw))

    # compareHist(CORREL) pada vektor gabungan seluruh sel grid
    hist_raw = float(cv2.compareHist(_grid_histogram(face_a), _grid_histogram(face_b), cv2.HISTCMP_CORREL))
    if not np.isfinite(hist_raw):
        hist_raw = 0.0
    hist = min(1.0, max(0.0, hist_raw))

    score = NCC_WEIGHT * ncc + HIST_WEIGHT * hist
    return {"score": round(score, 4), "ncc": round(ncc, 4), "hist": round(hist, 4)}


# =====================================================================
# 4. Pendaftaran dan verifikasi wajah (storage/faces/{username}.npy)
# =====================================================================

def _validate_username(username: str) -> str:
    if not isinstance(username, str) or not _USERNAME_PATTERN.match(username):
        raise BiometricError(
            "Username hanya boleh huruf, angka, titik, garis bawah, atau tanda hubung (maksimal 64 karakter)."
        )
    return username


def face_model_path(username: str, storage_dir: Optional[str] = None) -> str:
    """Path absolut storage/faces/{username}.npy."""
    faces_dir = config.get_storage_paths(storage_dir).faces
    return os.path.join(faces_dir, f"{_validate_username(username)}.npy")


def face_exists(username: str, storage_dir: Optional[str] = None) -> bool:
    return os.path.isfile(face_model_path(username, storage_dir))


def enroll_face(
    username: str,
    frame_b64: str,
    storage_dir: Optional[str] = None,
) -> Dict[str, Any]:
    """
    Mendaftarkan wajah dari satu frame base64 (webcam atau foto unggahan).
    Menyimpan matriks 128x128 ke storage/faces/{username}.npy.
    Mengembalikan {"username", "face_model_path"}.
    """
    path = face_model_path(username, storage_dir)
    face = extract_face_from_base64(frame_b64)
    config.ensure_storage_dirs(storage_dir)

    temp_path = path + ".tmp"
    with open(temp_path, "wb") as f:
        np.save(f, face, allow_pickle=False)
    os.replace(temp_path, path)
    return {"username": username, "face_model_path": path}


def load_enrolled_face(username: str, storage_dir: Optional[str] = None) -> np.ndarray:
    path = face_model_path(username, storage_dir)
    if not os.path.isfile(path):
        raise FaceNotEnrolledError(f"Wajah untuk {username} belum terdaftar.")
    try:
        face = np.load(path, allow_pickle=False)
    except Exception as exc:
        raise BiometricError(f"Berkas wajah terdaftar rusak: {exc}") from exc
    if face.shape != (FACE_SIZE, FACE_SIZE) or face.dtype != np.uint8:
        raise BiometricError("Berkas wajah terdaftar memiliki format tidak valid.")
    return face


def verify_face(
    username: str,
    frame_b64: str,
    storage_dir: Optional[str] = None,
    threshold: float = MATCH_THRESHOLD,
) -> Dict[str, Any]:
    """
    Memverifikasi wajah pada frame terhadap wajah terdaftar milik username.
    Mengembalikan {"match": bool, "score", "ncc", "hist", "threshold"}.
    match True jika score >= threshold (bawaan 0.72).
    """
    enrolled = load_enrolled_face(username, storage_dir)
    candidate = extract_face_from_base64(frame_b64)
    result = compute_similarity(enrolled, candidate)
    result["match"] = result["score"] >= threshold
    result["threshold"] = threshold
    return result


def delete_face(username: str, storage_dir: Optional[str] = None) -> bool:
    path = face_model_path(username, storage_dir)
    if os.path.isfile(path):
        os.remove(path)
        return True
    return False

