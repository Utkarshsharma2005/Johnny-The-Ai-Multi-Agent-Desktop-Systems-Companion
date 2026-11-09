"""
system.py — Real-time Hardware Telemetry & Memory Optimization for Johnny.

Features:
- Pure Linux sysfs / procfs resource reader (zero external deps):
  * CPU & RAM usage (total, free, process RSS)
  * System thermal sensors (/sys/class/thermal/)
  * GPU utilization, VRAM, and temperature via nvidia-smi (if NVIDIA GPU present)
- Memory management & arena trimmer (POST /api/v1/system/gc):
  * Invokes gc.collect()
  * Calls glibc malloc_trim(0) to release unmapped heap memory back to Linux immediately
"""

import gc
import os
import shutil
import subprocess
from pathlib import Path
from typing import Dict, Any, List
from fastapi import APIRouter

router = APIRouter(prefix="/api/v1/system", tags=["System Telemetry & Optimization"])


def _read_meminfo() -> Dict[str, int]:
    mem: Dict[str, int] = {}
    try:
        lines = Path("/proc/meminfo").read_text(encoding="utf-8").splitlines()[:15]
        for line in lines:
            if ":" in line:
                key, val = line.split(":", 1)
                mem[key.strip()] = int(val.strip().split()[0]) // 1024  # Convert kB -> MB
    except Exception:
        pass
    return mem


def _read_process_memory_mb() -> int:
    try:
        statm = Path("/proc/self/statm").read_text(encoding="utf-8").split()
        page_kb = os.sysconf("SC_PAGE_SIZE") // 1024
        return (int(statm[1]) * page_kb) // 1024
    except Exception:
        return 0


def _read_thermals() -> List[Dict[str, Any]]:
    temps: List[Dict[str, Any]] = []
    try:
        thermal_dir = Path("/sys/class/thermal")
        for tz in sorted(thermal_dir.glob("thermal_zone*")):
            temp_file = tz / "temp"
            type_file = tz / "type"
            if temp_file.exists():
                try:
                    celsius = round(int(temp_file.read_text(encoding="utf-8").strip()) / 1000.0, 1)
                    sensor_type = type_file.read_text(encoding="utf-8").strip() if type_file.exists() else tz.name
                    temps.append({"zone": tz.name, "type": sensor_type, "temp_c": celsius})
                except Exception:
                    continue
    except Exception:
        pass
    return temps


def _read_gpu_stats() -> Dict[str, Any]:
    if not shutil.which("nvidia-smi"):
        return {"available": False, "reason": "nvidia-smi not found"}

    try:
        out = subprocess.check_output(
            [
                "nvidia-smi",
                "--query-gpu=name,utilization.gpu,temperature.gpu,memory.used,memory.total",
                "--format=csv,noheader,nounits"
            ],
            timeout=1.0,
            stderr=subprocess.DEVNULL
        ).decode("utf-8").strip()

        if not out:
            return {"available": False, "reason": "No GPU output"}

        # Take first GPU
        first_line = out.splitlines()[0]
        parts = [p.strip() for p in first_line.split(",")]
        return {
            "available": True,
            "name": parts[0],
            "utilization_gpu_pct": float(parts[1]),
            "temperature_c": float(parts[2]),
            "vram_used_mb": float(parts[3]),
            "vram_total_mb": float(parts[4]),
            "vram_free_mb": round(float(parts[4]) - float(parts[3]), 1),
        }
    except Exception as e:
        return {"available": False, "reason": str(e)}


@router.get("/telemetry")
async def get_system_telemetry():
    """
    Returns live system resource telemetry: RAM, Process RSS, GPU, and Thermals.
    """
    mem = _read_meminfo()
    total_ram = mem.get("MemTotal", 0)
    avail_ram = mem.get("MemAvailable", 0)
    used_ram = total_ram - avail_ram
    ram_pct = round((used_ram / total_ram * 100.0), 1) if total_ram > 0 else 0.0

    return {
        "status": "online",
        "memory": {
            "total_mb": total_ram,
            "available_mb": avail_ram,
            "used_mb": used_ram,
            "used_percent": ram_pct,
            "johnny_process_rss_mb": _read_process_memory_mb(),
        },
        "thermals": _read_thermals(),
        "gpu": _read_gpu_stats(),
    }


@router.post("/gc")
async def run_memory_optimization():
    """
    Triggers explicit Python garbage collection and Linux glibc malloc_trim
    to reclaim unmapped memory pages immediately.
    """
    before_rss = _read_process_memory_mb()
    collected = gc.collect()

    trimmed = False
    try:
        import ctypes
        libc = ctypes.CDLL("libc.so.6")
        if hasattr(libc, "malloc_trim"):
            libc.malloc_trim(0)
            trimmed = True
    except Exception:
        pass

    after_rss = _read_process_memory_mb()
    reclaimed_mb = max(0, before_rss - after_rss)

    return {
        "status": "optimized",
        "objects_collected": collected,
        "malloc_trimmed": trimmed,
        "before_rss_mb": before_rss,
        "after_rss_mb": after_rss,
        "reclaimed_mb": reclaimed_mb,
    }
