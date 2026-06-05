"""Tests for startup Alembic migration handling."""
from __future__ import annotations

import subprocess

import pytest

from backend import main


@pytest.mark.asyncio
async def test_run_alembic_upgrade_with_retries_succeeds_after_transient_failure(monkeypatch):
    calls = 0
    sleeps: list[float] = []

    def fake_upgrade() -> None:
        nonlocal calls
        calls += 1
        if calls == 1:
            raise RuntimeError("database is still starting")

    async def fake_to_thread(func, *args, **kwargs):
        return func(*args, **kwargs)

    async def fake_sleep(delay: float) -> None:
        sleeps.append(delay)

    monkeypatch.setattr(main, "_run_alembic_upgrade", fake_upgrade)
    monkeypatch.setattr(main.asyncio, "to_thread", fake_to_thread)
    monkeypatch.setattr(main.asyncio, "sleep", fake_sleep)

    await main._run_alembic_upgrade_with_retries(attempts=3, delay_seconds=0.25)

    assert calls == 2
    assert sleeps == [0.25]


@pytest.mark.asyncio
async def test_run_alembic_upgrade_with_retries_raises_final_failure(monkeypatch):
    calls = 0
    sleeps: list[float] = []

    def fake_upgrade() -> None:
        nonlocal calls
        calls += 1
        raise RuntimeError(f"failure {calls}")

    async def fake_to_thread(func, *args, **kwargs):
        return func(*args, **kwargs)

    async def fake_sleep(delay: float) -> None:
        sleeps.append(delay)

    monkeypatch.setattr(main, "_run_alembic_upgrade", fake_upgrade)
    monkeypatch.setattr(main.asyncio, "to_thread", fake_to_thread)
    monkeypatch.setattr(main.asyncio, "sleep", fake_sleep)

    with pytest.raises(RuntimeError, match="failure 3"):
        await main._run_alembic_upgrade_with_retries(attempts=3, delay_seconds=0.25)

    assert calls == 3
    assert sleeps == [0.25, 0.25]


def test_run_alembic_upgrade_uses_python_module_with_project_pythonpath(monkeypatch):
    captured: dict[str, object] = {}

    def fake_run(*args, **kwargs):
        captured["args"] = args[0]
        captured["cwd"] = kwargs.get("cwd")
        captured["env"] = kwargs.get("env")
        return subprocess.CompletedProcess(
            args=args[0],
            returncode=0,
            stdout="",
            stderr="",
        )

    monkeypatch.setattr(main.subprocess, "run", fake_run)

    main._run_alembic_upgrade()

    assert captured["args"] == [main.sys.executable, "-m", "alembic", "upgrade", "head"]
    assert captured["cwd"] == str(main._PROJECT_ROOT)
    env = captured["env"]
    assert isinstance(env, dict)
    assert env["DATABASE_URL"] == main.settings.database_url
    assert str(main._PROJECT_ROOT) in env["PYTHONPATH"].split(main.os.pathsep)


def test_run_alembic_upgrade_reports_stdout_when_stderr_is_empty(monkeypatch):
    monkeypatch.setattr(
        main.subprocess,
        "run",
        lambda *args, **kwargs: subprocess.CompletedProcess(
            args=args[0],
            returncode=1,
            stdout="stdout-only failure detail\n",
            stderr="",
        ),
    )

    with pytest.raises(RuntimeError) as excinfo:
        main._run_alembic_upgrade()

    message = str(excinfo.value)
    assert "alembic upgrade head exited 1" in message
    assert "stdout-only failure detail" in message
