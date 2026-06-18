# Cloud DTC Pipeline Demo

This repository contains a Docker Compose based pipeline:

```text
enterprise-architect
  -> digital-twin-profile-sysml-v1 or digital-twin-profile-sysml-v2
  -> digital-twin-manager
  -> AWS deploy
```

## Prerequisites

Run commands from the repository root:

```powershell
cd path\to\cloud-dtc-docker
```

Docker Desktop must be running.

The default compose file is:

```text
docker-compose.yaml
```

To use another compose file, pass:

```powershell
--compose-file path/to/docker-compose.yaml
```

## Demo: SysML v1

SysML v1 reads the Enterprise Architect XML/XMI export from:

```text
enterprise-architect/models
```

Demo command:

```powershell
python -m orchestrate_pipeline `
  --converter sysml-v1 `
  --ea-export enterprise-architect/models `
  --show-configs `
  --stop-before-aws-deploy `
  --hide-container-logs `
  --path-map "C:/Users/marco/Git-projects/anyFile/digital-twin-manager/lambda_functions/event_actions/stopCharging=/pipeline/code/microgrid/stopCharging"
```

The `--path-map` is required because `model.xml` contains a hardcoded absolute
path from another machine:

```text
C:\Users\marco\Git-projects\anyFile\digital-twin-manager\lambda_functions\event_actions\stopCharging
```

Inside the Docker pipeline, Lambda code is mounted under:

```text
/pipeline/code
```

So the demo maps the old path to:

```text
/pipeline/code/microgrid/stopCharging
```

For this to work, the repository must include the demo Lambda folder:

```text
demo-code/microgrid/stopCharging
```

## Demo: SysML v2

SysML v2 reads `.sysml` files from:

```text
enterprise-architect/models
```

Demo command:

```powershell
python -m orchestrate_pipeline `
  --converter sysml-v2 `
  --ea-export enterprise-architect/models `
  --show-configs `
  --stop-before-aws-deploy `
  --hide-container-logs
```

## What The Demo Shows

The orchestrator prints:

- the selected converter;
- the Docker Compose file name;
- the input model file name or `.sysml` content;
- the generated config files copied into `digital-twin-manager` input.

With `--show-configs`, configs are printed from:

```text
pipeline/digital-twin-manager/input
```

These are the files that `digital-twin-manager` would use for deploy:

```text
config.json
config_hierarchy.json
config_iot_devices.json
config_events.json
```

The command stops before AWS deploy because of:

```powershell
--stop-before-aws-deploy
```

## Useful Flags

```text
--hide-container-logs
```

Hides Docker/container logs during a clean demo. If a container fails, the error
output is still shown.

```text
--show-configs
```

Prints the final configs prepared for `digital-twin-manager` input.

```text
--show-output-configs
```

Also prints configs directly from the converter output directory. This is off by
default to avoid duplicate config output during presentation.

```text
--build-images
```

Builds Docker images before running containers. By default, the orchestrator
uses existing local images.

```text
--deploy-to-aws
```

Runs `digital-twin-manager deploy`. Do not use this during the safe demo unless
AWS credentials and deploy intent are confirmed.
