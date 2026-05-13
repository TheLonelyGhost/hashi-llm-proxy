# hashi-llm-proxy

LiteLLM proxy setup for macOS, managed with `task`.

## What It Does

This repo sets up a local LiteLLM authenticating proxy and wires other tools to use it through a standard OpenAI-compatible base URL.

The default proxy URL is `http://127.0.0.1:4444/v1`.

## Requirements

- macOS (support for select Linux distros coming later)
- [Task](https://taskfile.dev)
- Homebrew or the LiteLLM install script for `uv`
- A working GitHub Copilot or IBM Bob provider setup, depending on the models you want

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

## LiteLLM On macOS

The macOS flow uses a LaunchAgent named `com.litellm.server`.

Runtime files are stored in:

- `~/.config/litellm/config.yaml`
- `~/.config/litellm/providers/`
- `~/.local/state/litellm/`
- `~/Library/LaunchAgents/com.litellm.server.plist`

The proxy runs with `LITELLM_LOG=DEBUG` and listens on port `4444` by default.

## Provider Config

Included provider files live in `litellm/providers/`:

- `github_copilot.yaml` (as authorized by IBM's restrictions)
- `ibm_bob.yaml`

These are merged into the generated LiteLLM config by `task litellm:configure`.

## OpenCode Config

`task opencode:configure` runs `opencode/configure.py`, which:

- reads the models exposed by `litellm-proxy`
- writes them into `~/.config/opencode/opencode.json`
- sets the LiteLLM provider base URL to `http://127.0.0.1:4444/v1`

## Stop Or Restart

```sh
task litellm:stop
task litellm:restart
```
