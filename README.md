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

Pipeline settings live in:

```text
orchestrator_config.json
```

## Enterprise Architect UI Storage

Enterprise Architect is available at:

```text
http://127.0.0.1:6080
```

The repository directory `enterprise-architect` is mounted into the UI
container at:

```text
/home/ea/.wine/drive_c/users/ea/Documents/enterprise-architect
```

In Enterprise Architect's Wine file picker, the same directory is available as:

```text
C:\users\ea\Documents\enterprise-architect
```

Save Enterprise Architect project files (`.qea`, `.qeax`, `.eap`, `.eapx`) under:

```text
enterprise-architect/projects
```

Save Enterprise Architect exports under this host directory:

```text
pipeline/enterprise-architect/output
```

The run loop watches this directory. When a new export is created or an existing
export is updated, it prints the run configuration and asks whether to run the
pipeline.

Those files are stored on the host and survive container restarts. The existing
input example is stored on the host under:

```text
pipeline/enterprise-architect/input/demo_model.xml
```

Inside Enterprise Architect, input and output are still available through the
usual Wine file picker paths:

```text
C:\users\ea\Documents\enterprise-architect\input\demo_model.xml
C:\users\ea\Documents\enterprise-architect\output
```

## Running The Pipeline

Start the watcher from the repository root:

```powershell
python run_pipeline.py
```

On startup it brings up:

- `enterprise-architect`
- `sysml-kernel`

Then it watches:

```text
pipeline/enterprise-architect/output
```

Type this into the running process to stop it:

```text
exit
```

To run automatically without confirmation when an export changes:

```powershell
python run_pipeline.py --auto-run
```

You can also set this in `orchestrator_config.json`:

```json
"auto_run": true
```

To stop and remove the `enterprise-architect` and `sysml-kernel` containers
when the watcher exits:

```powershell
python run_pipeline.py --remove-infrastructure-on-exit
```

Or set this in `orchestrator_config.json`:

```json
"remove_infrastructure_on_exit": true
```

This removes only the containers. Docker volumes such as the Enterprise
Architect Wine prefix are kept.

## Export Routing

The converter is selected from the updated export file extension:

- `.xml` or `.xmi` -> `digital-twin-profile-sysml-v1`
- `.sysml` -> `digital-twin-profile-sysml-v2`

For `.xml` or `.xmi`, export from Enterprise Architect as XMI 2.1/UML 2.1 with
Enterprise Architect extension data. The sysml-v1 converter does not support
the older XMI 1.1/UML 1.3 export layout.

The current demo `path_maps` value in `orchestrator_config.json` is required
because the XML model contains a hardcoded absolute path from another machine:

```text
C:\Users\marco\Git-projects\anyFile\digital-twin-manager\lambda_functions\event_actions\stopCharging
```

Inside the Docker pipeline, Lambda code is mounted under:

```text
/pipeline/code
```

So the config maps the old path to:

```text
/pipeline/code/microgrid/stopCharging
```

For this to work, the repository must include the demo Lambda folder:

```text
demo-code/microgrid/stopCharging
```

## Config

The main settings are stored in `orchestrator_config.json`:

```json
{
  "compose_file": "docker-compose.yaml",
  "compose_profiles": ["pipeline"],
  "digital_twin_name": "dtwin",
  "path_maps": [],
  "show_container_logs": false,
  "show_configs": true,
  "deploy_to_aws": false,
  "auto_run": false,
  "remove_infrastructure_on_exit": false
}
```

## What The Demo Shows

The run loop prints:

- the changed Enterprise Architect export file;
- the selected converter;
- the Docker Compose file;
- the config that will be used for this run;
- the generated config files copied into `digital-twin-manager` input.

When `show_configs` is `true`, configs are printed from:

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

AWS deploy is controlled by `deploy_to_aws`. Leave it `false` during safe demos
unless AWS credentials and deploy intent are confirmed. Set it to `null` or omit
it to ask for AWS deploy confirmation during interactive runs; auto-run keeps
deploy disabled when the setting is unset.

## Federation Artifacts

Each `digital-twin-manager` stage still handles one digital twin. After configs
are staged, the orchestrator saves the reusable manager input under:

```text
pipeline/digital-twin-manager/deployments/<digital_twin_name>/input
```

After a successful deploy, it saves the generated output under:

```text
pipeline/digital-twin-manager/deployments/<digital_twin_name>/output
```

For example, after staging and deploying `PV` and `Battery`, the saved artifacts
look like:

```text
pipeline/digital-twin-manager/deployments/PV/input/config.json
pipeline/digital-twin-manager/deployments/PV/output/PV_federation_input.json
pipeline/digital-twin-manager/deployments/Battery/input/config.json
pipeline/digital-twin-manager/deployments/Battery/output/Battery_federation_input.json
```

The `continue digital-twin-manager` and `destroy digital-twin-manager` commands
use saved deployment inputs. Without an argument, they show a numbered menu. You
can also select a twin directly:

```text
continue digital-twin-manager PV
destroy digital-twin-manager Battery
```

The federation stage is still separate. When you type:

```text
continue fed-sysml
```

the orchestrator reads:

```text
pipeline/fed-sysml/input/fedtwin.json
```

It extracts the required twin names from strategy references such as:

```json
"strategies": [
  "PV.production",
  "Battery.status"
]
```

Then it copies only those saved artifacts into:

```text
pipeline/fed-sysml/input/strategyInputs
```

and runs `fed-sysml`. In other words, `fedtwin.json` defines what gets
federated, while `deployments/<Twin>/output` defines which deployed twins are
available for federation.
