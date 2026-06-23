from __future__ import annotations

import json
import shutil
from datetime import datetime
from pathlib import Path

from .errors import fail
from .pipeline_paths import (
    CONFIG_FILES,
    MANAGER_INPUT_DIR,
    MANAGER_OUTPUT_DIR,
    PIPELINE_ROOT,
    PROFILE_INPUT_DIRS,
    PROFILE_OUTPUT_DIRS,
    FEDERATION_INPUT_DIR,
    FEDERATION_OUTPUT_DIR,
    relative_to_repo,
    resolve_repo_path,
)
from .xmi_validation import validate_sysml_v1_export

FEDERATION_TERRAFORM_STATE_ENTRIES = {
    ".terraform",
    ".terraform.lock.hcl",
    "terraform.tfstate",
    "terraform.tfstate.backup",
}


def clean_pipeline_dir(path: Path) -> None:
    path = _safe_pipeline_child(path)
    if path.exists() and not path.is_dir():
        fail(f"Expected directory but found file: {path}")
    if path.exists():
        shutil.rmtree(path)
    path.mkdir(parents=True, exist_ok=True)


def ensure_dir(path: Path) -> None:
    path.mkdir(parents=True, exist_ok=True)


def stage_converter_input(converter: str, source: Path, *, clean_stage: bool) -> tuple[str | None, list[Path]]:
    input_dir = PROFILE_INPUT_DIRS[converter]
    output_dir = PROFILE_OUTPUT_DIRS[converter]

    if clean_stage:
        clean_pipeline_dir(input_dir)
        clean_pipeline_dir(output_dir)
    else:
        ensure_dir(input_dir)
        ensure_dir(output_dir)

    if converter == "v1":
        return _stage_sysml_v1_input(source, input_dir)

    staged_files = _stage_sysml_v2_input(source, input_dir)
    return None, staged_files


def find_converter_output(converter: str, *, generated_twin_dir: str | None) -> Path:
    output_root = PROFILE_OUTPUT_DIRS[converter]

    if generated_twin_dir:
        expected_dir = output_root / generated_twin_dir
        if has_config_set(expected_dir):
            return expected_dir
        fail(f"Expected converter output directory is missing or incomplete: {relative_to_repo(expected_dir)}")

    candidates = set()
    if has_config_set(output_root):
        candidates.add(output_root)

    for config_json in output_root.rglob("config.json"):
        candidate = config_json.parent
        if has_config_set(candidate):
            candidates.add(candidate)

    if not candidates:
        fail(f"No complete config set found under {relative_to_repo(output_root)}")

    sorted_candidates = sorted(candidates, key=_latest_config_mtime, reverse=True)
    if len(sorted_candidates) > 1:
        print(f"Multiple converter outputs found. Using newest: {relative_to_repo(sorted_candidates[0])}")
    return sorted_candidates[0]


def prepare_manager_stage(*, clean_stage: bool, keep_credentials: bytes | None) -> None:
    if clean_stage:
        clean_pipeline_dir(MANAGER_INPUT_DIR)
        clean_pipeline_dir(MANAGER_OUTPUT_DIR)
    else:
        ensure_dir(MANAGER_INPUT_DIR)
        ensure_dir(MANAGER_OUTPUT_DIR)

    if keep_credentials is not None:
        (MANAGER_INPUT_DIR / "config_credentials.json").write_bytes(keep_credentials)


def prepare_federation_stage(*, clean_stage: bool) -> None:
    strategy_input_dir = FEDERATION_INPUT_DIR / "strategyInputs"
    if clean_stage:
        ensure_dir(FEDERATION_INPUT_DIR)
        clean_pipeline_dir(strategy_input_dir)
        clean_federation_output_dir()
    else:
        ensure_dir(FEDERATION_INPUT_DIR)
        ensure_dir(strategy_input_dir)
        ensure_dir(FEDERATION_OUTPUT_DIR)


def clean_federation_output_dir() -> None:
    path = _safe_pipeline_child(FEDERATION_OUTPUT_DIR)
    if path.exists() and not path.is_dir():
        fail(f"Expected directory but found file: {path}")
    path.mkdir(parents=True, exist_ok=True)

    for child in path.iterdir():
        if child.name in FEDERATION_TERRAFORM_STATE_ENTRIES:
            continue
        if child.is_dir() and not child.is_symlink():
            shutil.rmtree(child)
        else:
            child.unlink()


def read_existing_manager_credentials() -> bytes | None:
    credentials = MANAGER_INPUT_DIR / "config_credentials.json"
    if credentials.is_file():
        return credentials.read_bytes()
    return None


def copy_configs_to_manager(converter_output_dir: Path, aws_credentials_file: Path | None) -> None:
    for file_name in CONFIG_FILES:
        source = converter_output_dir / file_name
        target = MANAGER_INPUT_DIR / file_name
        shutil.copy2(source, target)
        print(f"Copied {relative_to_repo(source)} -> {relative_to_repo(target)}")

    if aws_credentials_file:
        credentials = resolve_repo_path(aws_credentials_file)
        if not credentials.is_file():
            fail(f"Credentials file does not exist: {relative_to_repo(credentials)}")
        target = MANAGER_INPUT_DIR / "config_credentials.json"
        shutil.copy2(credentials, target)
        print(f"Copied AWS credentials to {relative_to_repo(target)}")


def stage_federation_inputs() -> list[Path]:
    for file_name in ("fedtwin.json", "brokerConfig.json"):
        config_file = FEDERATION_INPUT_DIR / file_name
        if not config_file.is_file():
            fail(f"Missing fed-sysml config file: {relative_to_repo(config_file)}")

    source_files = sorted(MANAGER_OUTPUT_DIR.glob("*_federation_input.json"))
    if not source_files:
        fail(f"No federation input files found under {relative_to_repo(MANAGER_OUTPUT_DIR)}")

    target_dir = FEDERATION_INPUT_DIR / "strategyInputs"
    ensure_dir(target_dir)

    staged_files: list[Path] = []
    for source in source_files:
        target = target_dir / source.name
        shutil.copy2(source, target)
        staged_files.append(target)
        print(f"Copied {relative_to_repo(source)} -> {relative_to_repo(target)}")

    return staged_files


def print_config_set(label: str, config_dir: Path) -> None:
    print(f"\n=== {label}: {relative_to_repo(config_dir)} ===")
    for file_name in CONFIG_FILES:
        path = config_dir / file_name
        print(f"\n--- {file_name} ---")
        try:
            with path.open("r", encoding="utf-8") as file:
                data = json.load(file)
            print(json.dumps(data, indent=2, ensure_ascii=False))
        except json.JSONDecodeError:
            print(path.read_text(encoding="utf-8", errors="replace"))


def print_manager_outputs() -> None:
    federation_outputs = sorted(MANAGER_OUTPUT_DIR.glob("*_federation_input.json"))
    if not federation_outputs:
        return

    print(f"\n=== digital-twin-manager output: {relative_to_repo(MANAGER_OUTPUT_DIR)} ===")
    for output in federation_outputs:
        print(f"\n--- {output.name} ---")
        print(output.read_text(encoding="utf-8", errors="replace"))


def print_file_listing(label: str, files: list[Path]) -> None:
    print(f"\n=== {label} ===")
    if not files:
        print("(no files)")
        return

    for file_path in files:
        if not file_path.exists():
            print(f"missing        -                    {relative_to_repo(file_path)}")
            continue
        if file_path.is_dir():
            print(f"dir            -                    {relative_to_repo(file_path)}")
            continue
        size = _format_size(file_path.stat().st_size)
        modified = datetime.fromtimestamp(file_path.stat().st_mtime).strftime("%Y-%m-%d %H:%M:%S")
        print(f"file  {size:>10} {modified}  {relative_to_repo(file_path)}")


def print_text_files(label: str, files: list[Path]) -> None:
    print(f"\n=== {label} ===")
    if not files:
        print("(no files)")
        return

    for file_path in files:
        print(f"\n--- {relative_to_repo(file_path)} ---")
        print(file_path.read_text(encoding="utf-8", errors="replace"))


def has_config_set(path: Path) -> bool:
    return all((path / file_name).is_file() for file_name in CONFIG_FILES)


def _stage_sysml_v1_input(source: Path, input_dir: Path) -> tuple[str, list[Path]]:
    source = _select_sysml_v1_input(source)
    if not source.is_file():
        fail(f"Enterprise Architect export file does not exist: {relative_to_repo(source)}")
    validate_sysml_v1_export(source)

    target = input_dir / source.name
    shutil.copy2(source, target)
    print(f"Copied Enterprise Architect export to {relative_to_repo(target)}")
    return f"/pipeline/input/{target.name}", [source]


def _stage_sysml_v2_input(source: Path, input_dir: Path) -> list[Path]:
    sources = _select_sysml_v2_inputs(source)
    for source_file in sources:
        target = input_dir / source_file.name
        shutil.copy2(source_file, target)
        print(f"Copied SysML v2 source to {relative_to_repo(target)}")
    return sources


def _select_sysml_v1_input(source: Path) -> Path:
    if source.is_dir():
        candidates = sorted(source.glob("*.xmi")) + sorted(source.glob("*.xml"))
        if not candidates:
            fail(f"No .xmi or .xml files found in {relative_to_repo(source)}")
        if len(candidates) > 1:
            names = ", ".join(relative_to_repo(path) for path in candidates)
            fail(f"More than one .xmi/.xml file found. Export or update one file at a time. Candidates: {names}")
        return candidates[0]
    return source


def _select_sysml_v2_inputs(source: Path) -> list[Path]:
    if source.is_dir():
        sources = _files_with_suffixes(source, ".sysml")
        if not sources:
            xml_exports = _files_with_suffixes(source, ".xml", ".xmi")
            if xml_exports:
                names = ", ".join(relative_to_repo(path) for path in xml_exports)
                fail(
                    "Found Enterprise Architect XML/XMI export(s), but sysml-v2 cannot read them: "
                    f"{names}. XML/XMI exports are routed to sysml-v1; sysml-v2 needs a .sysml text file."
                )
            fail(
                f"No .sysml files found in {relative_to_repo(source)}. "
                "SysML v2 parser reads .sysml text files only."
            )
        return sources

    if not source.is_file():
        fail(f"Enterprise Architect export file does not exist: {relative_to_repo(source)}")
    if source.suffix.lower() != ".sysml":
        if source.suffix.lower() in (".xml", ".xmi"):
            fail(
                "sysml-v2 cannot read Enterprise Architect XML/XMI exports. "
                f"XML/XMI exports are routed to sysml-v1: {relative_to_repo(source)}."
            )
        fail(f"SysML v2 parser reads .sysml text files only, got: {relative_to_repo(source)}")
    return [source]


def _latest_config_mtime(path: Path) -> float:
    return max((path / file_name).stat().st_mtime for file_name in CONFIG_FILES)


def _files_with_suffixes(directory: Path, *suffixes: str) -> list[Path]:
    wanted = {suffix.lower() for suffix in suffixes}
    return sorted(
        path for path in directory.iterdir()
        if path.is_file() and path.suffix.lower() in wanted
    )


def _format_size(size: int) -> str:
    units = ("B", "KB", "MB", "GB")
    value = float(size)
    for unit in units:
        if value < 1024 or unit == units[-1]:
            return f"{value:.1f} {unit}" if unit != "B" else f"{size} B"
        value /= 1024
    return f"{size} B"


def _safe_pipeline_child(path: Path) -> Path:
    resolved = path.resolve()
    pipeline_root = PIPELINE_ROOT.resolve()
    if resolved == pipeline_root:
        fail("Refusing to clean the pipeline root itself.")
    try:
        resolved.relative_to(pipeline_root)
    except ValueError:
        fail(f"Refusing to clean path outside pipeline directory: {resolved}")
    return resolved
