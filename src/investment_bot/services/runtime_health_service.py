from dataclasses import dataclass, field
import os
import subprocess
from typing import Callable


@dataclass
class RuntimeHealthService:
    cpu_count_fn: Callable[[], int | None] = os.cpu_count
    loadavg_fn: Callable[[], tuple[float, float, float]] = os.getloadavg
    meminfo_fn: Callable[[], dict[str, int]] | None = None
    process_lines_fn: Callable[[], list[str]] | None = None
    qmd_process_keywords: tuple[str, ...] = ("qmd", "bun")

    def assess(self) -> dict:
        cpu_count = max(1, int(self.cpu_count_fn() or 1))
        load1, load5, load15 = self.loadavg_fn()
        meminfo = self._read_meminfo()
        mem_total_kb = meminfo.get("MemTotal", 0)
        mem_available_kb = meminfo.get("MemAvailable", 0)
        mem_available_pct = round((mem_available_kb / mem_total_kb) * 100, 2) if mem_total_kb else None
        load_per_cpu = round(load1 / cpu_count, 2)
        qmd_processes = self._find_qmd_processes()

        warnings: list[str] = []
        criticals: list[str] = []
        recommendations: list[str] = []

        if load_per_cpu >= 2.0:
            criticals.append(f"CPU load is saturated ({load1:.2f} on {cpu_count} CPU threads)")
        elif load_per_cpu >= 1.0:
            warnings.append(f"CPU load is elevated ({load1:.2f} on {cpu_count} CPU threads)")

        if mem_available_pct is not None:
            if mem_available_pct < 15:
                criticals.append(f"Available memory is low ({mem_available_pct:.2f}% free)")
            elif mem_available_pct < 30:
                warnings.append(f"Available memory is tightening ({mem_available_pct:.2f}% free)")

        if len(qmd_processes) >= 2:
            warnings.append("Multiple qmd/bun processes are active; avoid overlapping heavy jobs")

        if criticals:
            status = "critical"
            safe_for_batch = False
            recommendations.append("Pause semi-live batches and heavy backtests until load drops")
        elif warnings:
            status = "warning"
            safe_for_batch = False
            recommendations.append("Prefer one light operation at a time on this VM")
        else:
            status = "ok"
            safe_for_batch = True
            recommendations.append("Small local runs are safe at the moment")

        if qmd_processes:
            recommendations.append("Keep QMD-heavy queries serialized to reduce CPU/RAM contention")

        return {
            "status": status,
            "safe_for_batch": safe_for_batch,
            "cpu": {
                "count": cpu_count,
                "load": {"1m": round(load1, 2), "5m": round(load5, 2), "15m": round(load15, 2)},
                "load_per_cpu_1m": load_per_cpu,
            },
            "memory": {
                "total_kb": mem_total_kb,
                "available_kb": mem_available_kb,
                "available_pct": mem_available_pct,
            },
            "qmd_activity": {
                "process_count": len(qmd_processes),
                "samples": qmd_processes[:5],
            },
            "warnings": warnings,
            "criticals": criticals,
            "recommendations": recommendations,
        }

    def _read_meminfo(self) -> dict[str, int]:
        if self.meminfo_fn:
            return self.meminfo_fn()

        result: dict[str, int] = {}
        with open("/proc/meminfo", "r", encoding="utf-8") as handle:
            for line in handle:
                key, value = line.split(":", 1)
                result[key] = int(value.strip().split()[0])
        return result

    def _find_qmd_processes(self) -> list[str]:
        lines = self.process_lines_fn() if self.process_lines_fn else self._default_process_lines()
        keywords = tuple(keyword.lower() for keyword in self.qmd_process_keywords)
        return [line for line in lines if any(keyword in line.lower() for keyword in keywords)]

    def _default_process_lines(self) -> list[str]:
        result = subprocess.run(
            ["ps", "-eo", "comm,args", "--no-headers"],
            check=False,
            capture_output=True,
            text=True,
        )
        if result.returncode != 0:
            return []
        return [line.strip() for line in result.stdout.splitlines() if line.strip()]
