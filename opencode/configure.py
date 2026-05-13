#!/usr/bin/env python3

import json
import os
import pathlib
import subprocess


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
        ["litellm-proxy", "models", "list", "--format", "json"],
        check=True,
        capture_output=True,
        text=True,
    )

    models = json.loads(proc.stdout)
    output = {
        model["id"]: {"name": model["id"]}
        for model in models
        if isinstance(model, dict) and "id" in model
    }

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

    litellm.setdefault("npm", "@ai-sdk/openai-compatible")
    litellm.setdefault("name", "LiteLLM")
    litellm.setdefault("options", {})
    options = litellm["options"]
    options.setdefault("baseURL", os.environ["LITELLM_PROXY_URL"])
    litellm.setdefault("models", {})
    litellm["models"] = merge(litellm["models"], output)

    with config_path.open("w") as f:
        json.dump(config, f, indent=2)


if __name__ == "__main__":
    main()
