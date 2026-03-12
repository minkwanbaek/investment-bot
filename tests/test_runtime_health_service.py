from investment_bot.services.runtime_health_service import RuntimeHealthService


def test_runtime_health_service_reports_ok_when_load_and_memory_are_comfortable():
    service = RuntimeHealthService(
        cpu_count_fn=lambda: 2,
        loadavg_fn=lambda: (0.4, 0.3, 0.2),
        meminfo_fn=lambda: {"MemTotal": 4_000_000, "MemAvailable": 2_000_000},
        process_lines_fn=lambda: ["python app.py"],
    )

    result = service.assess()

    assert result["status"] == "ok"
    assert result["safe_for_batch"] is True
    assert result["cpu"]["load_per_cpu_1m"] == 0.2
    assert result["memory"]["available_pct"] == 50.0
    assert result["qmd_activity"]["process_count"] == 0


def test_runtime_health_service_reports_warning_when_qmd_contention_is_present():
    service = RuntimeHealthService(
        cpu_count_fn=lambda: 2,
        loadavg_fn=lambda: (2.2, 1.9, 1.5),
        meminfo_fn=lambda: {"MemTotal": 4_000_000, "MemAvailable": 900_000},
        process_lines_fn=lambda: [
            "bun qmd.js query memory",
            "bun qmd.js query notes",
            "python worker.py",
        ],
    )

    result = service.assess()

    assert result["status"] == "warning"
    assert result["safe_for_batch"] is False
    assert any("CPU load is elevated" in item for item in result["warnings"])
    assert any("Multiple qmd/bun processes" in item for item in result["warnings"])
    assert result["qmd_activity"]["process_count"] == 2


def test_runtime_health_service_reports_critical_when_vm_is_under_heavy_pressure():
    service = RuntimeHealthService(
        cpu_count_fn=lambda: 2,
        loadavg_fn=lambda: (4.5, 3.0, 2.0),
        meminfo_fn=lambda: {"MemTotal": 4_000_000, "MemAvailable": 400_000},
        process_lines_fn=lambda: ["bun qmd.js query memory"],
    )

    result = service.assess()

    assert result["status"] == "critical"
    assert result["safe_for_batch"] is False
    assert any("CPU load is saturated" in item for item in result["criticals"])
    assert any("Available memory is low" in item for item in result["criticals"])
