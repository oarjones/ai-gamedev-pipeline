import json
from pathlib import Path

from app.services.agent_runner import AgentRunner, AgentConfig


def test_build_from_config_resolves_relative_executable(tmp_path: Path, monkeypatch):
    # Arrange: create a dummy executable file
    proj = tmp_path / "proj-1"
    agp = proj / ".agp"
    agp.mkdir(parents=True)
    exe = proj / "bin.py"
    exe.write_text("print('ok')\n", encoding="utf-8")

    cfg = AgentConfig(
        executable="bin.py",
        args=["--flag", "value"],
        env={"API_KEY": "secret"},
        default_timeout=5.0,
        terminate_grace=3.0,
    )

    # Act
    cmd, env = AgentRunner._build_from_config(proj, cfg)

    # Assert
    assert Path(cmd[0]) == exe.resolve()
    assert cmd[1:] == ["--flag", "value"]
    assert env.get("API_KEY") == "secret"


def test_load_project_agent_config_prefers_project_json(tmp_path: Path):
    proj = tmp_path / "proj-2"
    agp = proj / ".agp"
    agp.mkdir(parents=True)
    (agp / "project.json").write_text(
        json.dumps({
            "agent": {"executable": "python", "args": ["-m", "x"], "env": {"X":"1"}}
        }),
        encoding="utf-8",
    )

    cfg = AgentRunner._load_project_agent_config(proj)
    assert cfg.executable == "python"
    assert cfg.args == ["-m", "x"]
    assert cfg.env.get("X") == "1"

