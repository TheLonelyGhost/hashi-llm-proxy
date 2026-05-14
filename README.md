# hashi-llm-proxy

LiteLLM proxy setup for macOS, managed with `task`.

## What It Does

This repo sets up a local LiteLLM authenticating proxy and wires other tools to use it through a standard OpenAI-compatible base URL.

Additional customizations are recommended in `~/.config/litellm/config.yaml` for setting up preferred backend models in some kind of load balancing scheme. Maybe after X tokens are used, [defer to model Y](https://docs.litellm.ai/docs/proxy/reliability)? Add [guardrails](https://docs.litellm.ai/docs/proxy/guardrails/quick_start) in certain ways? Your choice!

The default proxy URL is `http://127.0.0.1:4444/v1`.

## Requirements

- macOS (support for select Linux distros coming later)
- [Task](https://taskfile.dev)
- A GitHub Copilot subscription
- An API key for IBM Bob, via `BOBSHELL_API_KEY` environment variable

## Quick Start

```bash
~/workspace $ task

task: Task "litellm:configure" is up to date
task: Task "macos:service:register" is up to date
task: Task "macos:uv:bootstrap" is up to date
task: Task "macos:litellm:install" is up to date
task: Task "macos:service:start" is up to date
```

(Optionally):

```bash
~/workspace $ task opencode:configure
```

## Taskfile Summary

```
task: Available tasks for this project:
* litellm:                  Installs and starts LiteLLM authenticating proxy      (aliases: default)
* litellm:configure:        Configures LiteLLM authenticating proxy
* litellm:restart:          Restarts LiteLLM authenticating proxy
* litellm:start:            Starts LiteLLM authenticating proxy
* litellm:stop:             Stops LiteLLM authenticating proxy
* opencode:configure:       Configures OpenCode to include LiteLLM proxy info
```

## LiteLLM

Runtime files are stored in:

- `~/.config/litellm/`
- `~/.local/state/litellm/`

The proxy runs listening on port `4444/tcp` (on `127.0.0.1`) by default.

## Provider Config

Included provider files live in `litellm/providers/`:

- `github_copilot.yaml` (as authorized by IBM's restrictions)
- `ibm_bob.yaml`

These are merged into the generated LiteLLM config by `task litellm:configure`.

## OpenCode Config

`task opencode:configure` runs `opencode/configure.py`, which:

- Creates/updates a "LiteLLM" provider to talk to `http://127.0.0.1:4444/v1`
- reads the models exposed via `http://127.0.0.1:4444/v1/models`
- writes them into `~/.config/opencode/opencode.json`

## Stop Or Restart

```sh
task litellm:stop
task litellm:restart
```
