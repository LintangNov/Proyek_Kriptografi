"""
AegisVault USB Hardware Dongle Gatekeeper
Implementasi docs/TECHNICAL_SPEC.md Bab 3.1.

Alur kerja:
1. Pemindaian drive: psutil.disk_partitions(all=False) untuk partisi 'removable',
   ditambah drive mana pun yang memuat berkas dongle.key.
2. Identitas perangkat keras: Volume Serial Number dibaca lewat
   ctypes.windll.kernel32.GetVolumeInformationW (Windows). Pada OS lain dipakai
   fallback berupa ID turunan dari path perangkat partisi.
3. Berkas dongle.key (JSON, di root USB):
   signature = SHA256(dongle_id + ":" + volume_serial + ":" + SYSTEM_SECRET_PEPPER)
4. Validasi: dongle sah jika signature cocok dengan Volume Serial Number fisik drive
   tempat berkas berada. Berkas yang disalin ke harddisk atau flashdisk lain ditolak
   karena nomor seri drive berbeda dari yang tertulis dan ditandatangani.

Mode pengujian (PRD Bab 7 butir 4): jika variabel lingkungan AEGIS_DONGLE_SIMULATION
berisi path folder, folder tersebut diperlakukan sebagai satu drive USB tersimulasi
dengan Volume Serial Number tetap. Pengujian otomatis juga dapat menyuntikkan
drive_provider dan serial_provider ke DongleGuard tanpa memakai variabel lingkungan.

Catatan Kepatuhan Regulasi Kode:
- Dilarang menggunakan karakter em dash pada seluruh teks dan komentar (Aturan R-02).
"""

import contextlib
import hashlib
import hmac
import json
import os
import sys
import threading
import uuid
from datetime import datetime, timezone
from typing import Any, Callable, Dict, List, Optional

import psutil

from backend import config

SIMULATION_ENV_VAR = "AEGIS_DONGLE_SIMULATION"
SIMULATED_VOLUME_SERIAL = "5E70-0001"

DRIVE_REMOVABLE = 2  # nilai kembalian GetDriveTypeW untuk media removable


# =====================================================================
# Pengecualian Khusus
# =====================================================================

class DongleError(Exception):
    """Kesalahan umum operasi dongle (tidak ada USB, drive tidak dapat ditulis, dan sebagainya)."""


class MultipleDrivesError(DongleError):
    """Lebih dari satu USB terdeteksi saat registrasi. Pemanggil harus memilih mountpoint."""

    def __init__(self, drives: List[Dict[str, Any]]):
        self.drives = drives
        names = ", ".join(d["mountpoint"] for d in drives)
        super().__init__(f"Lebih dari satu USB terdeteksi ({names}). Pilih salah satu drive.")


# =====================================================================
# Fungsi dasar: tanda tangan dan pembacaan identitas perangkat keras
# =====================================================================

def compute_signature(dongle_id: str, volume_serial: str, pepper: Optional[str] = None) -> str:
    """signature = SHA256(dongle_id + ':' + volume_serial + ':' + SYSTEM_SECRET_PEPPER)."""
    pepper = config.SYSTEM_SECRET_PEPPER if pepper is None else pepper
    return hashlib.sha256(f"{dongle_id}:{volume_serial}:{pepper}".encode("utf-8")).hexdigest()


def _format_serial(serial_number: int) -> str:
    """Mengubah serial 32-bit menjadi bentuk 'A8F4-9902'."""
    return f"{(serial_number >> 16) & 0xFFFF:04X}-{serial_number & 0xFFFF:04X}"


def _windows_volume_serial(mountpoint: str) -> Optional[str]:
    """Membaca Volume Serial Number lewat GetVolumeInformationW. None jika gagal."""
    import ctypes  # impor lokal agar modul tetap dapat dimuat pada OS non-Windows

    root = os.path.splitdrive(mountpoint)[0] + "\\"
    serial = ctypes.c_ulong(0)
    kernel32 = ctypes.windll.kernel32
    # SEM_FAILCRITICALERRORS (0x1): hindari dialog sistem saat drive tidak siap.
    previous_mode = kernel32.SetErrorMode(0x1)
    try:
        ok = kernel32.GetVolumeInformationW(
            ctypes.c_wchar_p(root),
            None, 0,
            ctypes.byref(serial),
            None, None,
            None, 0,
        )
    finally:
        kernel32.SetErrorMode(previous_mode)
    if not ok:
        return None
    return _format_serial(serial.value)


def _fallback_volume_serial(device: str) -> str:
    """Fallback non-Windows: ID stabil turunan dari path perangkat partisi."""
    digest = hashlib.sha256(device.encode("utf-8")).digest()
    return _format_serial(int.from_bytes(digest[:4], "big"))


def get_volume_serial(drive: Dict[str, Any]) -> Optional[str]:
    """
    Mengambil Volume Serial Number sebuah drive hasil list_candidate_drives().
    Drive simulasi memakai serial tetap. Windows memakai ctypes, OS lain memakai fallback.
    """
    if drive.get("simulated"):
        return SIMULATED_VOLUME_SERIAL
    if sys.platform == "win32":
        return _windows_volume_serial(drive["mountpoint"])
    return _fallback_volume_serial(drive.get("device") or drive["mountpoint"])


# =====================================================================
# Pemindaian drive
# =====================================================================

def _simulated_drive() -> Optional[Dict[str, Any]]:
    path = os.environ.get(SIMULATION_ENV_VAR)
    if path and os.path.isdir(path):
        return {
            "mountpoint": os.path.abspath(path),
            "device": "SIMULATED",
            "fstype": "simulated",
            "removable": True,
            "simulated": True,
        }
    return None


def _is_removable(partition: Any) -> bool:
    if "removable" in (partition.opts or "").lower():
        return True
    if sys.platform == "win32":
        try:
            import ctypes
            return ctypes.windll.kernel32.GetDriveTypeW(ctypes.c_wchar_p(partition.mountpoint)) == DRIVE_REMOVABLE
        except Exception:
            return False
    return False


def list_candidate_drives() -> List[Dict[str, Any]]:
    """
    Daftar drive kandidat dongle: partisi removable, ditambah drive mana pun yang
    memuat berkas dongle.key. Setiap item: mountpoint, device, fstype, removable, simulated.
    """
    drives: List[Dict[str, Any]] = []
    seen = set()

    simulated = _simulated_drive()
    if simulated:
        drives.append(simulated)
        seen.add(simulated["mountpoint"].lower())

    try:
        partitions = psutil.disk_partitions(all=False)
    except Exception:
        partitions = []

    for partition in partitions:
        mountpoint = partition.mountpoint
        if not mountpoint or mountpoint.lower() in seen:
            continue
        removable = _is_removable(partition)
        has_key = os.path.isfile(os.path.join(mountpoint, config.DONGLE_KEY_FILENAME))
        if not (removable or has_key):
            continue
        seen.add(mountpoint.lower())
        drives.append({
            "mountpoint": mountpoint,
            "device": partition.device,
            "fstype": partition.fstype,
            "removable": removable,
            "simulated": False,
        })
    return drives


# =====================================================================
# Penjaga Dongle
# =====================================================================

class DongleGuard:
    """
    Registrasi dan validasi USB Dongle. drive_provider dan serial_provider dapat
    disuntikkan untuk pengujian tanpa perangkat keras.
    """

    def __init__(
        self,
        drive_provider: Optional[Callable[[], List[Dict[str, Any]]]] = None,
        serial_provider: Optional[Callable[[Dict[str, Any]], Optional[str]]] = None,
        pepper: Optional[str] = None,
    ):
        self._drive_provider = drive_provider or list_candidate_drives
        self._serial_provider = serial_provider or get_volume_serial
        self._pepper = config.SYSTEM_SECRET_PEPPER if pepper is None else pepper

    # ------------------------------------------------------------------
    # Pembacaan berkas dongle.key
    # ------------------------------------------------------------------

    @staticmethod
    def _key_path(drive: Dict[str, Any]) -> str:
        return os.path.join(drive["mountpoint"], config.DONGLE_KEY_FILENAME)

    def read_key_file(self, drive: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """Membaca dan mem-parsing dongle.key. None jika tidak ada atau formatnya rusak."""
        try:
            with open(self._key_path(drive), "r", encoding="utf-8") as f:
                data = json.load(f)
        except (OSError, ValueError):
            return None
        required = ("dongle_id", "volume_serial", "issued_at", "signature")
        if not isinstance(data, dict) or not all(isinstance(data.get(k), str) for k in required):
            return None
        return data

    def _check_drive(self, drive: Dict[str, Any]) -> Dict[str, Any]:
        """Memeriksa satu drive. Mengembalikan dict dengan kunci valid dan reason."""
        info: Dict[str, Any] = {
            "valid": False,
            "mountpoint": drive["mountpoint"],
            "dongle_id": None,
            "volume_serial": None,
            "reason": "",
        }
        key = self.read_key_file(drive)
        if key is None:
            info["reason"] = "Berkas dongle.key tidak ditemukan atau formatnya rusak."
            return info

        actual_serial = self._serial_provider(drive)
        info["dongle_id"] = key["dongle_id"]
        info["volume_serial"] = actual_serial
        if not actual_serial:
            info["reason"] = "Volume Serial Number drive tidak dapat dibaca."
            return info
        if not hmac.compare_digest(key["volume_serial"].upper(), actual_serial.upper()):
            info["reason"] = "Nomor seri drive tidak cocok dengan dongle.key (kemungkinan berkas disalin)."
            return info

        expected = compute_signature(key["dongle_id"], actual_serial, self._pepper)
        if not hmac.compare_digest(key["signature"].lower(), expected.lower()):
            info["reason"] = "Tanda tangan dongle.key tidak valid."
            return info

        info["valid"] = True
        info["reason"] = "Dongle valid."
        return info

    # ------------------------------------------------------------------
    # Validasi real-time
    # ------------------------------------------------------------------

    def validate_dongle(self) -> Dict[str, Any]:
        """
        Memindai drive saat ini dan mengembalikan status dongle:
        {connected, valid, dongle_id, mountpoint, volume_serial, reason, drives_scanned}.
        connected berarti ada drive USB atau drive dengan dongle.key. valid berarti
        ada setidaknya satu drive dengan dongle.key yang lolos verifikasi. Murah
        dipanggil berulang kali untuk polling.
        """
        drives = self._drive_provider()
        last_reason = "Tidak ada USB Flashdisk terdeteksi."
        for drive in drives:
            result = self._check_drive(drive)
            if result["valid"]:
                result.update({"connected": True, "drives_scanned": len(drives)})
                return result
            last_reason = result["reason"]
        return {
            "connected": bool(drives),
            "valid": False,
            "dongle_id": None,
            "mountpoint": None,
            "volume_serial": None,
            "reason": last_reason,
            "drives_scanned": len(drives),
        }

    def is_dongle_valid(self) -> bool:
        return bool(self.validate_dongle()["valid"])

    # ------------------------------------------------------------------
    # Registrasi USB baru
    # ------------------------------------------------------------------

    def enroll_dongle(self, mountpoint: Optional[str] = None) -> Dict[str, Any]:
        """
        Menulis dongle.key ke root USB yang sedang tertancap.

        - mountpoint None: dipakai satu-satunya drive removable. Jika tidak ada
          dilempar DongleError, jika lebih dari satu dilempar MultipleDrivesError.
        - Jika drive sudah memiliki dongle.key yang valid, berkas tidak ditimpa
          (already_enrolled True). Berkas rusak atau tidak cocok akan diganti.
        """
        drive = self._select_enroll_drive(mountpoint)

        existing = self._check_drive(drive)
        if existing["valid"]:
            existing.update({"enrolled": True, "already_enrolled": True})
            return existing

        serial = self._serial_provider(drive)
        if not serial:
            raise DongleError("Volume Serial Number drive tidak dapat dibaca. Registrasi dibatalkan.")

        dongle_id = f"AEGIS-DONGLE-{uuid.uuid4().hex[:8].upper()}"
        payload = {
            "dongle_id": dongle_id,
            "volume_serial": serial,
            "issued_at": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
            "signature": compute_signature(dongle_id, serial, self._pepper),
        }

        key_path = self._key_path(drive)
        temp_path = key_path + ".tmp"
        try:
            with open(temp_path, "w", encoding="utf-8") as f:
                json.dump(payload, f, indent=2)
            os.replace(temp_path, key_path)
        except OSError as exc:
            with contextlib.suppress(OSError):
                os.remove(temp_path)
            raise DongleError(f"Gagal menulis dongle.key ke {drive['mountpoint']}: {exc}") from exc

        result = self._check_drive(drive)
        result.update({"enrolled": result["valid"], "already_enrolled": False})
        return result

    def _select_enroll_drive(self, mountpoint: Optional[str]) -> Dict[str, Any]:
        drives = self._drive_provider()
        if mountpoint is not None:
            target = os.path.normcase(os.path.abspath(mountpoint))
            for drive in drives:
                if os.path.normcase(os.path.abspath(drive["mountpoint"])) == target:
                    return drive
            raise DongleError(f"Drive {mountpoint} bukan USB yang terdeteksi.")

        removable = [d for d in drives if d.get("removable")]
        if not removable:
            raise DongleError("Tidak ada USB Flashdisk yang tertancap. Colokkan flashdisk lalu coba lagi.")
        if len(removable) > 1:
            raise MultipleDrivesError(removable)
        return removable[0]


# =====================================================================
# Monitor real-time (polling latar belakang)
# =====================================================================

class DongleMonitor:
    """
    Memantau dongle di thread latar belakang dan menyimpan status terakhir.
    on_change dipanggil dengan status baru setiap kali status valid berubah
    (misalnya USB dicabut), sehingga lapisan API dapat segera mengunci sesi.
    """

    def __init__(
        self,
        guard: Optional[DongleGuard] = None,
        interval: float = config.DONGLE_POLL_INTERVAL_SECONDS,
        on_change: Optional[Callable[[Dict[str, Any]], None]] = None,
    ):
        self.guard = guard or DongleGuard()
        self.interval = interval
        self.on_change = on_change
        self._status: Dict[str, Any] = self.guard.validate_dongle()
        self._lock = threading.Lock()
        self._stop = threading.Event()
        self._thread: Optional[threading.Thread] = None

    def get_status(self) -> Dict[str, Any]:
        with self._lock:
            return dict(self._status)

    def refresh(self) -> Dict[str, Any]:
        """Memindai sekarang juga, memperbarui cache, dan memicu on_change bila berubah."""
        new_status = self.guard.validate_dongle()
        with self._lock:
            changed = new_status["valid"] != self._status["valid"]
            self._status = new_status
        if changed and self.on_change:
            try:
                self.on_change(dict(new_status))
            except Exception:
                pass  # kegagalan callback tidak boleh menghentikan pemantauan
        return dict(new_status)

    def _run(self) -> None:
        while not self._stop.wait(self.interval):
            self.refresh()

    def start(self) -> None:
        if self._thread and self._thread.is_alive():
            return
        self._stop.clear()
        self._thread = threading.Thread(target=self._run, name="DongleMonitor", daemon=True)
        self._thread.start()

    def stop(self) -> None:
        self._stop.set()
        if self._thread:
            self._thread.join(timeout=self.interval + 2)
            self._thread = None
