from __future__ import annotations

import argparse
import os
from dataclasses import dataclass
from pathlib import Path

from .pipeline_paths import normalize_converter


@dataclass(frozen=True)
class PipelineOptions:
    compose_file: Path
    converter: str
    enterprise_architect_export: Path | None
    digital_twin_name: str
    generated_twin_dir: str | None
    aws_credentials_file: Path | None
    path_maps: tuple[str, ...]
    start_infrastructure: bool
    build_images: bool
    clean_stage: bool
    show_container_logs: bool
    show_configs: bool
    show_output_configs: bool
    deploy_to_aws: bool


def parse_args() -> PipelineOptions:
    parser = argparse.ArgumentParser(
        description="Run the Enterprise Architect -> SysML profile -> Digital Twin Manager pipeline.",
        epilog=(
            "Examples:\n"
            "  python -m scripts.orchestrator.orchestrate_pipeline --converter sysml-v1 "
            "--ea-export enterprise-architect/models/model.xml --digital-twin-name dtwin "
            "--show-configs\n"
            "  python -m scripts.orchestrator.orchestrate_pipeline --converter sysml-v2 "
            "--ea-export enterprise-architect/models/model.sysml --stop-before-aws-deploy"
        ),
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )

    parser.add_argument(
        "--compose-file",
        type=Path,
        default=Path("docker-compose.yaml"),
        help="Docker Compose file to use. Default: docker-compose.yaml.",
    )

    parser.add_argument(
        "--converter",
        choices=("sysml-v1", "sysml-v2"),
        default="sysml-v1",
        help="Which converter to run: sysml-v1 reads .xmi/.xml, sysml-v2 reads .sysml.",
    )

    parser.add_argument(
        "--ea-export",
        type=Path,
        help=(
            "Input file or directory for the selected converter. "
            "sysml-v1 expects Enterprise Architect .xml/.xmi. "
            "sysml-v2 expects .sysml text files. "
            "Default for sysml-v1: enterprise-architect/models/model.xml. "
            "Default for sysml-v2: enterprise-architect/models."
        ),
    )

    parser.add_argument(
        "--digital-twin-name",
        default=os.getenv("DIGITAL_TWIN_NAME", "dtwin"),
        help="Digital twin name for sysml-v1 output and manager config. Default: dtwin.",
    )

    parser.add_argument(
        "--generated-twin-dir",
        help=(
            "Generated converter output directory to send to manager. "
            "Usually not needed; use it when several twin outputs exist."
        ),
    )

    parser.add_argument(
        "--aws-credentials",
        type=Path,
        help="Optional config_credentials.json to copy into digital-twin-manager input.",
    )

    parser.add_argument(
        "--path-map",
        action="append",
        default=[],
        metavar="SOURCE_PREFIX=CONTAINER_PREFIX",
        help=(
            "Rewrite absolute pathToCode prefixes from model files to container paths. "
            "Can be used multiple times. Example: C:/old/path=/pipeline/code"
        ),
    )

    parser.add_argument(
        "--skip-infra-up",
        dest="start_infrastructure",
        action="store_false",
        default=True,
        help="Do not run docker compose up for Enterprise Architect/sysml-kernel.",
    )

    parser.add_argument(
        "--build-images",
        dest="build_images",
        action="store_true",
        default=False,
        help="Build Docker images before running containers. Default: use existing local images.",
    )

    parser.add_argument(
        "--keep-stage",
        dest="clean_stage",
        action="store_false",
        default=True,
        help="Keep existing files in pipeline staging directories.",
    )

    parser.add_argument(
        "--hide-container-logs",
        dest="show_container_logs",
        action="store_false",
        default=True,
        help="Do not print Docker Compose/container stdout and stderr unless a command fails.",
    )

    config_output = parser.add_mutually_exclusive_group()
    config_output.add_argument(
        "--show-configs",
        dest="show_configs",
        action="store_true",
        default=False,
        help="Print config JSON files copied into digital-twin-manager input.",
    )
    config_output.add_argument(
        "--hide-configs",
        dest="show_configs",
        action="store_false",
        help="Do not print config JSON files. This is the default.",
    )

    parser.add_argument(
        "--show-output-configs",
        dest="show_output_configs",
        action="store_true",
        default=False,
        help="Also print config JSON files directly from the converter output directory.",
    )

    deploy = parser.add_mutually_exclusive_group()
    deploy.add_argument(
        "--deploy-to-aws",
        dest="deploy_to_aws",
        action="store_true",
        default=False,
        help="After config handoff, run digital-twin-manager deploy.",
    )
    deploy.add_argument(
        "--stop-before-aws-deploy",
        dest="deploy_to_aws",
        action="store_false",
        help="Stop after copying configs into digital-twin-manager input. This is the default.",
    )

    args = parser.parse_args()
    return PipelineOptions(
        compose_file=args.compose_file,
        converter=normalize_converter(args.converter),
        enterprise_architect_export=args.ea_export,
        digital_twin_name=args.digital_twin_name,
        generated_twin_dir=args.generated_twin_dir,
        aws_credentials_file=args.aws_credentials,
        path_maps=tuple(args.path_map),
        start_infrastructure=args.start_infrastructure,
        build_images=args.build_images,
        clean_stage=args.clean_stage,
        show_container_logs=args.show_container_logs,
        show_configs=args.show_configs,
        show_output_configs=args.show_output_configs,
        deploy_to_aws=args.deploy_to_aws,
    )
