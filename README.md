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
[+] up 2/2
 ✔ Network litellm_default   Created         0.0s
 ✔ Container litellm-proxy-1 Started         0.1s
```

Then edit your `~/.config/litellm/config.yaml` to include preferred provider models,
followed by `task litellm:restart`.

Optionally, generate OpenCode configurations mapping to all available models served
by LiteLLM under a "LiteLLM" provider: `task opencode:configure`

## Taskfile Summary

```sh
task: Available tasks for this project:
* litellm:                  Installs and starts LiteLLM authenticating proxy      (aliases: default)
* litellm:configure:        Configures LiteLLM authenticating proxy
* litellm:env:              Refreshes LiteLLM credentials
* litellm:logs:             View logs for LiteLLM authenticating proxy
* litellm:providers:        Configure LiteLLM backend providers
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

Provider files in `litellm/providers/` are generated via `./scripts/generate-*.py`
scripts. The model lists are regenerated on-demand by `task litellm:providers`.

Supports:

- GitHub Copilot (individual, business, or enterprise)
- IBM Bob

## OpenCode Config

`task opencode:configure` runs `./scripts/configure-opencode.py`, which:

- Creates a "LiteLLM" provider to talk to the LiteLM authenticating proxy (`http://127.0.0.1:4444`)
- Reads the models exposed via `http://127.0.0.1:4444/v1/models`
- Writes any models exposed by LiteLLM into the LiteLLM provider models in `~/.config/opencode/opencode.json`

## LiteLLM Service Management

```bash
task litellm:start
task litellm:stop
task litellm:restart
```
