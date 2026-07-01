from pathlib import Path

from automated_bioadhesives_workcell.arm_server_process import ArmServerSettings, ManagedArmServer


class FakeProcess:
    returncode = None

    def __init__(self):
        self.terminated = False
        self.killed = False

    def poll(self):
        return None if not self.terminated else 0

    def terminate(self):
        self.terminated = True
        self.returncode = 0

    def kill(self):
        self.killed = True
        self.returncode = -9

    def wait(self, timeout=None):
        return self.returncode or 0


class FakeArmClient:
    health_calls = 0
    stop_calls = 0

    def __init__(self, *args, **kwargs):
        pass

    def health(self):
        type(self).health_calls += 1
        return {"status": "ok"}

    def stop(self):
        type(self).stop_calls += 1
        return {"stopped": True}


def _settings():
    return ArmServerSettings(
        python="/tmp/python",
        host="127.0.0.1",
        port=5004,
        base_url="http://127.0.0.1:5004",
        startup_timeout_s=1.0,
        mock_arm=True,
        ot_plate_type="black",
        cwd=Path("/tmp/repo"),
    )


def test_managed_arm_server_builds_bundled_server_command():
    server = ManagedArmServer(_settings(), output_fn=lambda _line: None)

    assert server.command() == [
        "/tmp/python",
        "-m",
        "automated_bioadhesives_workcell.arm_server",
        "--host",
        "127.0.0.1",
        "--port",
        "5004",
        "--ot-plate",
        "black",
        "--mock",
    ]


def test_managed_arm_server_starts_waits_and_stops(monkeypatch):
    import automated_bioadhesives_workcell.arm_server_process as module

    fake_process = FakeProcess()
    popen_calls = []

    def fake_popen(cmd, cwd):
        popen_calls.append((cmd, cwd))
        return fake_process

    FakeArmClient.health_calls = 0
    FakeArmClient.stop_calls = 0
    monkeypatch.setattr(module, "ArmTransferClient", FakeArmClient)
    server = ManagedArmServer(_settings(), output_fn=lambda _line: None, popen=fake_popen)

    with server:
        assert popen_calls
        assert FakeArmClient.health_calls == 1

    assert FakeArmClient.stop_calls == 1
    assert fake_process.terminated is True
