from manual_bioadhesives_workcell.health import (
    HealthTarget,
    failed_health_names,
    format_health_report,
    run_health_checks,
)


def test_health_report_uses_green_checks_and_names_failures():
    results = run_health_checks(
        [
            HealthTarget("Opentrons Flex", lambda: {"status": "ok", "device": "flex"}),
            HealthTarget("SHARC station", lambda: {"status": "ok", "station_id": "sharc"}),
            HealthTarget("ASMI station", lambda: (_ for _ in ()).throw(RuntimeError("offline"))),
        ]
    )

    report = format_health_report(results)

    assert "✅ Opentrons Flex" in report
    assert "✅ SHARC station" in report
    assert "❌ ASMI station" in report
    assert failed_health_names(results) == ["ASMI station"]


def test_busy_health_is_not_ok():
    results = run_health_checks(
        [HealthTarget("ASMI station", lambda: {"status": "ok", "busy": True, "current_run_id": "r1"})]
    )

    assert failed_health_names(results) == ["ASMI station"]
    assert "busy with r1" in format_health_report(results)


def test_opentrons_full_status_is_ok():
    results = run_health_checks(
        [HealthTarget("Opentrons Flex", lambda: {"status": "full", "device": "flex"})]
    )

    assert failed_health_names(results) == []
    assert "✅ Opentrons Flex" in format_health_report(results)


def test_skipped_health_status_is_ok():
    results = run_health_checks(
        [HealthTarget("SHARC station", lambda: {"status": "skipped", "device": "sharc"})]
    )

    assert failed_health_names(results) == []
    assert "status=skipped" in format_health_report(results)
