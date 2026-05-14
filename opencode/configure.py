#!/usr/bin/env python3

import json
import os
import pathlib
import subprocess


LITELLM_PROXY_URL = os.environ["LITELLM_PROXY_URL"]


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
    proc = subprocess.run(
        ["curl", f"{LITELLM_PROXY_URL}/models"],
        check=True,
        capture_output=True,
        text=True,
    )

    output = json.loads(proc.stdout)
    models = {}
    for model in output["data"]:
        if not isinstance(model, dict):
            continue
        if "id" not in model:
            continue

        m = {"name": model["id"]}

        if m["name"].startswith("ibm-bob/"):
            m["provider"] = {"npm": "@ai-sdk/openai-compatible"}

        models[model["id"]] = m

    config_path = pathlib.Path("~/.config/opencode/opencode.json").expanduser()
    config_path.parent.mkdir(parents=True, exist_ok=True)
    if config_path.exists():
        with config_path.open("r") as f:
            config = json.load(f)
    else:
        config = {}

    config.setdefault("$schema", "https://opencode.ai/config.json")
    config.setdefault("provider", {})
    providers = config["provider"]
    providers.setdefault("litellm", {})
    litellm = config["provider"]["litellm"]

    litellm.setdefault("npm", "@ai-sdk/openai")
    litellm.setdefault("name", "LiteLLM")
    litellm.setdefault("options", {})
    options = litellm["options"]
    options.setdefault("baseURL", LITELLM_PROXY_URL)
    litellm.setdefault("models", {})
    litellm["models"] = merge(litellm["models"], models)

    with config_path.open("w") as f:
        json.dump(config, f, indent=2)


if __name__ == "__main__":
    main()
