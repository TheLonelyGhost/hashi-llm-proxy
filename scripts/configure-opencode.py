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


LITELLM_PROXY_URL = os.environ["LITELLM_PROXY_URL"]
OPENCODE_CONFIG_DIR = pathlib.Path("~/.config/opencode").expanduser().resolve()


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
    http = httpx.Client(base_url=LITELLM_PROXY_URL)
    output = http.get("/v1/models").raise_for_status().json()

    models = {}
    for model in output["data"]:
        if not isinstance(model, dict):
            continue
        if "id" not in model:
            continue

        models[model["id"]] = {"name": model["id"]}

    OPENCODE_CONFIG_DIR.mkdir(parents=True, exist_ok=True)
    config_path = OPENCODE_CONFIG_DIR / "opencode.json"
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
