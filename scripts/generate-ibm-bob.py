#!/usr/bin/env -S uv run --script
# /// script
# requires-python = ">=3.10"
# dependencies = [
#     "httpx>=0.28.1",
# ]
# ///

import json
import os
import pathlib

import httpx


DEFAULT_OLD_BACKEND_URL = "https://prod.ibm-bob-staging.cloud.ibm.com"
DEFAULT_BACKEND_URL = "https://api.us-east.bob.ibm.com"

BOB_URL = os.environ.get("BOB_API_BACKEND_URL", DEFAULT_OLD_BACKEND_URL)
BOB_KEY = os.environ["BOBSHELL_API_KEY"]


def merge(a: dict, b: dict, path=[]):
    for key in b:
        if key in a:
            if isinstance(a[key], dict) and isinstance(b[key], dict):
                merge(a[key], b[key], path + [str(key)])
            elif a[key] != b[key]:
                raise Exception("Conflict at " + ".".join(path + [str(key)]))
        else:
            a[key] = b[key]
    return a


def main() -> None:
    http = httpx.Client(
        base_url=BOB_URL,
        headers={
            "Authorization": f"Bearer {BOB_KEY}",
        },
    )
    output = http.get("/v1/model/info").raise_for_status().json()

    models = []
    for m in output["data"]:
        if not isinstance(m, dict):
            continue
        if "model_name" not in m:
            continue

        model = {
            "model_name": f"ibm-bob/{m['model_name']}",
            "litellm_params": {
                "model": f"openai/{m['model_name']}",
                "litellm_credential_name": "ibm-bob-creds",
            },
            "model_info": m["model_info"],
        }
        for key in list(model["model_info"].keys()):
            if key in [
                "litellm_provider",
                "alternatives_ibm",
                "id",
                "key",
                "db_model",
                "exposed",
            ]:
                del model["model_info"][key]
                continue
            if model["model_info"][key] is None:
                del model["model_info"][key]
                continue

        models.append(model)

    config = {
        "model_list": models,
        "credential_list": [
            {
                "credential_name": "ibm-bob-creds",
                "credential_values": {
                    "api_key": "os.environ/BOBSHELL_API_KEY",
                    "api_base": BOB_URL,
                },
                "credential_info": {
                    "description": "IBM Bob credentials",
                },
            }
        ],
    }
    config_path = (
        pathlib.Path(__file__).parent / ".." / "litellm" / "providers" / "ibm_bob.yaml"
    ).resolve()
    config_path.parent.mkdir(parents=True, exist_ok=True)

    with config_path.open("w") as f:
        json.dump(config, f, indent=2)


if __name__ == "__main__":
    main()
