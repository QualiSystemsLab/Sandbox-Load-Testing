# Sandbox Load Testing

This is a project to launch and teardown sandboxes concurrently via Rest API.

Once the respective orchestration process is complete, the activity feeds are scanned for errors and a JSON log report is generated.

The flow can be run all-in-one, or setup and teardown triggered independently to have control over timings.

## To Use
- download scripts to server that has connectivity to Sandbox REST service
- add python requirements to venv
- Adjust config.json settings
- Trigger run_sandboxes.py, stop_sandboxes.py, or run_full_flow.py
-  stop_sandboxes.py, if triggered as entry point, will look for latest json log file to pull in target sandbox ids
-  run_full_flow.bat can be triggered from windows scheduler 
    - use "cmd" as program with arguments "/k <path_to_file>" (to keep terminal open during execution)

Create 'config.json' in root of directory and add the following:

```
{
  "api_data": {
    "sandbox_rest_server": "localhost",
    "port": "82",
    "user": "admin",
    "password": "admin",
    "domain": "Global"
  },
  "run_config": {
    "blueprint_id": "setup throw error",
    "blueprint_params": [],
    "sandbox_duration_minutes": 20,
    "sandbox_quantity": 5,
    "orch_polling_minutes": 10,
    "polling_frequency_seconds": 20,
    "initial_timeout_minutes": 1,
    "teardown_timeout_minutes": 2
  }
}
```

- api data is used for connecting to Sandbox Rest Service
- run config is the settings for the trial
- teardown timeout minutes is how long full flow script will wait after setup before tear down
- If blueprint has inputs, blueprint params are objects of the form {"name": "value"}

```
[
    {"param_1": "val_1"},
    {"param_2": "val_2"},
]
```