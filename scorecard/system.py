"""Machine info and RAM sampling, using only the standard library.

psutil is used when it is installed. Without it we fall back to what each
operating system offers out of the box.
"""
from __future__ import annotations

import os
import platform
import re
import subprocess
import threading
import time

try:  # optional
    import psutil  # type: ignore
except ImportError:  # pragma: no cover
    psutil = None

GB = 1024 ** 3


def _windows_memory():
    import ctypes

    class MEMORYSTATUSEX(ctypes.Structure):
        _fields_ = [("dwLength", ctypes.c_ulong), ("dwMemoryLoad", ctypes.c_ulong),
                    ("ullTotalPhys", ctypes.c_ulonglong), ("ullAvailPhys", ctypes.c_ulonglong),
                    ("ullTotalPageFile", ctypes.c_ulonglong), ("ullAvailPageFile", ctypes.c_ulonglong),
                    ("ullTotalVirtual", ctypes.c_ulonglong), ("ullAvailVirtual", ctypes.c_ulonglong),
                    ("sullAvailExtendedVirtual", ctypes.c_ulonglong)]

    stat = MEMORYSTATUSEX()
    stat.dwLength = ctypes.sizeof(MEMORYSTATUSEX)
    ctypes.windll.kernel32.GlobalMemoryStatusEx(ctypes.byref(stat))  # type: ignore[attr-defined]
    return stat.ullTotalPhys, stat.ullTotalPhys - stat.ullAvailPhys


def _linux_memory():
    info = {}
    with open("/proc/meminfo") as fh:
        for line in fh:
            key, value = line.split(":", 1)
            info[key] = int(value.split()[0]) * 1024
    total = info["MemTotal"]
    return total, total - info.get("MemAvailable", info.get("MemFree", 0))


def _mac_memory():
    total = int(subprocess.run(["sysctl", "-n", "hw.memsize"], capture_output=True, text=True).stdout)
    out = subprocess.run(["vm_stat"], capture_output=True, text=True).stdout
    page = int(re.search(r"page size of (\d+)", out).group(1))
    pages = {k.strip(): int(v.strip().rstrip(".")) for k, v in re.findall(r"^(.+?):\s+(\d+)\.?$", out, re.M)}
    free = sum(pages.get(k, 0) for k in ("Pages free", "Pages inactive", "Pages speculative"))
    return total, total - free * page


def memory():
    """Return (total_bytes, used_bytes), or (None, None) if unknown."""
    try:
        if psutil is not None:
            vm = psutil.virtual_memory()
            return vm.total, vm.total - vm.available
        system = platform.system()
        if system == "Windows":
            return _windows_memory()
        if system == "Linux":
            return _linux_memory()
        if system == "Darwin":
            return _mac_memory()
    except Exception:  # noqa: BLE001 - RAM numbers are nice to have, never fatal
        pass
    return None, None


def cpu_name() -> str:
    system = platform.system()
    try:
        if system == "Darwin":
            out = subprocess.run(["sysctl", "-n", "machdep.cpu.brand_string"], capture_output=True, text=True).stdout
            if out.strip():
                return out.strip()
        if system == "Linux":
            with open("/proc/cpuinfo") as fh:
                for line in fh:
                    if line.startswith("model name"):
                        return line.split(":", 1)[1].strip()
        if system == "Windows":
            out = subprocess.run(
                ["powershell", "-NoProfile", "-Command", "(Get-CimInstance Win32_Processor).Name"],
                capture_output=True, text=True, timeout=10,
            ).stdout
            if out.strip():
                return out.strip().splitlines()[0]
    except Exception:  # noqa: BLE001
        pass
    return platform.processor() or platform.machine()


def machine_info() -> dict:
    total, _ = memory()
    system = platform.system()
    pretty = {"Darwin": "macOS " + platform.mac_ver()[0]}.get(system, f"{system} {platform.release()}")
    return {
        "os": pretty.strip(),
        "cpu": cpu_name(),
        "cores": os.cpu_count(),
        "ram_gb": round(total / GB, 1) if total else None,
        "python": platform.python_version(),
    }


class RamSampler:
    """Samples system RAM in use once a second while a task runs."""

    def __init__(self, every: float = 1.0) -> None:
        self.every = every
        self.start_used = None
        self.peak_used = None
        self._stop = threading.Event()
        self._thread = threading.Thread(target=self._loop, daemon=True)

    def _loop(self) -> None:
        while not self._stop.is_set():
            _, used = memory()
            if used is not None:
                self.peak_used = used if self.peak_used is None else max(self.peak_used, used)
            self._stop.wait(self.every)

    def __enter__(self):
        _, self.start_used = memory()
        self._thread.start()
        return self

    def __exit__(self, *exc):
        self._stop.set()
        self._thread.join(timeout=2)

    def result(self) -> dict:
        if self.peak_used is None:
            return {"peak_ram_gb": None, "ram_added_gb": None}
        added = max(0, self.peak_used - (self.start_used or self.peak_used))
        return {"peak_ram_gb": round(self.peak_used / GB, 2), "ram_added_gb": round(added / GB, 2)}


def now() -> float:
    return time.perf_counter()
