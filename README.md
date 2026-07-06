# Cloud DTC User Guide

Cloud DTC runs a Docker Compose pipeline for digital twin creation.

```text
Enterprise Architect / SysML export
  -> SysML profile converter
  -> digital-twin-manager
  -> optional federation, Terraform, simulator, Grafana
```

## Requirements

- Docker Desktop is running.
- Python 3 is available as `python`.
- AWS credentials (needed for real deploy, destroy, or Terraform actions).

## Quick Start

Run from the repository root:

```powershell
python run_pipeline.py
```

This starts Enterprise Architect, starts `sysml-kernel`, and watches:

```text
pipeline/enterprise-architect/output
```

Open Enterprise Architect:

```text
http://127.0.0.1:6080
```

Save or update an export in the watched output folder. The run loop will ask
whether to run the pipeline.

Stop the run loop:

```text
exit
```

Useful launch options:

```powershell
python run_pipeline.py --auto-run
python run_pipeline.py --config path\to\orchestrator_config.json
python run_pipeline.py --remove-infrastructure-on-exit
```

## Enterprise Architect Paths

Use these paths inside the Enterprise Architect Wine file picker:

| Use               | Wine path                                             | Host path                              |
| ----------------- | ----------------------------------------------------- | -------------------------------------- |
| Input examples    | `C:\users\ea\Documents\enterprise-architect\input`    | `pipeline/enterprise-architect/input`  |
| Save exports here | `C:\users\ea\Documents\enterprise-architect\output`   | `pipeline/enterprise-architect/output` |
| EA project files  | `C:\users\ea\Documents\enterprise-architect\projects` | `enterprise-architect/projects`        |

## Export Types

| Export         | Converter                       |
| -------------- | ------------------------------- |
| `.xml`, `.xmi` | `digital-twin-profile-sysml-v1` |
| `.sysml`       | `digital-twin-profile-sysml-v2` |

## Normal Run

1. Save an export in `pipeline/enterprise-architect/output`.
2. Answer `y` to `Run pipeline for this export?`.
3. Answer `n` to AWS deploy if you only want local generated configs.

If deploy is skipped, generated manager configs are ready in:

```text
pipeline/digital-twin-manager/input
```

The same input is saved by twin name:

```text
pipeline/digital-twin-manager/deployments/<Twin>/input
```

## Commands

Type commands in the running `python run_pipeline.py` terminal.

| Command                                | Purpose                                                    |
| -------------------------------------- | ---------------------------------------------------------- |
| `help`                                 | Show commands.                                             |
| `continue sysml-v1`                    | Run staged v1 converter input.                             |
| `continue sysml-v2 [file]`             | Run one staged v2 `.sysml` file. Omit `[file]` for a menu. |
| `continue digital-twin-manager [name]` | Deploy a saved twin input. Omit `[name]` for a menu.       |
| `destroy digital-twin-manager [name]`  | Destroy a saved twin deployment.                           |
| `continue fed-sysml`                   | Build federation output from saved deployed twins.         |
| `fed terraform plan`                   | Plan generated federation Terraform.                       |
| `fed terraform apply`                  | Plan, confirm, then apply federation Terraform.            |
| `fed terraform destroy`                | Confirm, then destroy federation Terraform resources.      |
| `start simulator [name]`               | Start a local simulator for a saved twin input.            |
| `stop simulator [name]`                | Stop a running simulator.                                  |
| `start grafana`                        | Start local Grafana.                                       |
| `stop grafana`                         | Stop local Grafana.                                        |
| `exit`                                 | Stop the watcher.                                          |

## Staged SysML v2 Run

Put `.sysml` files here:

```text
pipeline/digital-twin-profile-sysml-v2/input
```

Run one file:

```text
continue sysml-v2 Battery2.sysml
```

The converter prepares `digital-twin-manager` input and then asks whether to
continue with deploy.

## Deploy, Destroy, Federate

Deploy or destroy a saved twin:

```text
continue digital-twin-manager Battery2
destroy digital-twin-manager Battery2
```

Deployment output is saved here:

```text
pipeline/digital-twin-manager/deployments/<Twin>/output
```

To federate, first deploy every twin referenced in:

```text
pipeline/fed-sysml/input/fedtwin.json
```

Then run:

```text
continue fed-sysml
```

Federation inputs are staged in:

```text
pipeline/fed-sysml/input/strategyInputs
```

Federation output is written to:

```text
pipeline/fed-sysml/output
```

## Simulator And Grafana

Start a simulator for a saved twin:

```text
start simulator Battery2
```

Simulator ports start at `5000`. State is saved in:

```text
pipeline/digital-twin-manager/deployments/<Twin>/simulator.json
```

Start Grafana:

```text
start grafana
```

Default Grafana URL and login:

```text
http://127.0.0.1:3000
admin / admin123
```

## Configuration

Main config:

```text
orchestrator_config.json
```

Most used fields:

| Field                           | Use                                                               |
| ------------------------------- | ----------------------------------------------------------------- |
| `digital_twin_name`             | Name passed to the v1 converter.                                  |
| `path_maps`                     | Maps model paths to container paths such as `/pipeline/code/...`. |
| `deploy_to_aws`                 | `false` stops before deploy, `true` deploys, `null` asks.         |
| `run_federation_workflow`       | Runs `fed-sysml` after manager deploy.                            |
| `fed_sysml_terraform_action`    | `none`, `plan`, `apply`, or `destroy`.                            |
| `auto_run`                      | Runs detected exports without asking.                             |
| `remove_infrastructure_on_exit` | Removes Enterprise Architect and `sysml-kernel` on exit.          |
| `watch.directory`               | Folder watched for exports.                                       |

Optional environment file:

```powershell
Copy-Item .env.example .env
```

Use `.env` for AWS credentials, code mount folders, path maps, Grafana plugins,
and port overrides. Docker Compose reads it automatically.
