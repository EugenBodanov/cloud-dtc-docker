from __future__ import annotations

from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_COMPOSE_FILE = REPO_ROOT / "docker-compose.yaml"
PIPELINE_ROOT = REPO_ROOT / "pipeline"
ENTERPRISE_ARCHITECT_INPUT_DIR = REPO_ROOT / "enterprise-architect" / "input"

CONFIG_FILES = (
    "config.json",
    "config_hierarchy.json",
    "config_iot_devices.json",
    "config_events.json",
)

PROFILE_SERVICES = {
    "v1": "digital-twin-profile-sysml-v1",
    "v2": "digital-twin-profile-sysml-v2",
}

PROFILE_INPUT_DIRS = {
    "v1": PIPELINE_ROOT / "digital-twin-profile-sysml-v1" / "input",
    "v2": PIPELINE_ROOT / "digital-twin-profile-sysml-v2" / "input",
}

PROFILE_OUTPUT_DIRS = {
    "v1": PIPELINE_ROOT / "digital-twin-profile-sysml-v1" / "output",
    "v2": PIPELINE_ROOT / "digital-twin-profile-sysml-v2" / "output",
}

MANAGER_INPUT_DIR = PIPELINE_ROOT / "digital-twin-manager" / "input"
MANAGER_OUTPUT_DIR = PIPELINE_ROOT / "digital-twin-manager" / "output"


def normalize_converter(value: str) -> str:
    if value == "sysml-v1":
        return "v1"
    if value == "sysml-v2":
        return "v2"
    raise ValueError(f"Unsupported converter: {value}")


def converter_label(converter: str) -> str:
    return "sysml-v1" if converter == "v1" else "sysml-v2"


def default_enterprise_architect_export(converter: str) -> Path:
    if converter == "v1":
        return ENTERPRISE_ARCHITECT_INPUT_DIR / "model.xml"
    return ENTERPRISE_ARCHITECT_INPUT_DIR


def resolve_repo_path(path: Path) -> Path:
    if path.is_absolute():
        return path.resolve()
    return (REPO_ROOT / path).resolve()


def relative_to_repo(path: Path) -> str:
    try:
        return str(path.resolve().relative_to(REPO_ROOT))
    except ValueError:
        return str(path)
