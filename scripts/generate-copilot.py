#!/usr/bin/env -S uv run --script
# /// script
# requires-python = ">=3.10"
# dependencies = [
#     "httpx>=0.28.1",
# ]
# ///

import json
import pathlib
import logging
import os
import time
from datetime import datetime
from typing import Any, Optional

import httpx


_ROOT = (pathlib.Path(__file__).parent / "..").resolve()


# Constants (default values — overridable via environment variables at call time)
DEFAULT_GITHUB_CLIENT_ID = "Iv1.b507a08c87ecfe98"
DEFAULT_GITHUB_DEVICE_CODE_URL = "https://github.com/login/device/code"
DEFAULT_GITHUB_ACCESS_TOKEN_URL = "https://github.com/login/oauth/access_token"
DEFAULT_GITHUB_API_KEY_URL = "https://api.github.com/copilot_internal/v2/token"


class BaseLLMException(Exception):
    def __init__(
        self,
        status_code: int,
        message: str,
        headers: Optional[dict[str, str | list[str]] | httpx.Headers] = None,
        request: Optional[httpx.Request] = None,
        response: Optional[httpx.Response] = None,
        body: Optional[dict[str, Any]] = None,
    ):
        self.status_code = status_code
        self.message: str = message
        self.headers = headers
        if request:
            self.request = request
        else:
            self.request = httpx.Request(
                method="POST", url="https://docs.litellm.ai/docs"
            )
        if response:
            self.response = response
        else:
            self.response = httpx.Response(
                status_code=status_code, request=self.request
            )
        self.body = body
        super().__init__(
            self.message
        )  # Call the base class constructor with the parameters it needs


class GithubCopilotError(BaseLLMException):
    def __init__(
        self,
        status_code,
        message,
        request: Optional[httpx.Request] = None,
        response: Optional[httpx.Response] = None,
        headers: Optional[httpx.Headers | dict[str, str | list[str]]] = None,
        body: Optional[dict] = None,
    ):
        super().__init__(
            status_code=status_code,
            message=message,
            request=request,
            response=response,
            headers=headers,
            body=body,
        )


class GetDeviceCodeError(GithubCopilotError):
    pass


class GetAccessTokenError(GithubCopilotError):
    pass


class APIKeyExpiredError(GithubCopilotError):
    pass


class RefreshAPIKeyError(GithubCopilotError):
    pass


class GetAPIKeyError(GithubCopilotError):
    pass


class Authenticator:
    token_dir: pathlib.Path
    access_token_file: pathlib.Path
    api_key_file: pathlib.Path
    http: httpx.Client

    def __init__(self) -> None:
        """Initialize the GitHub Copilot authenticator with configurable token paths."""
        self.http = httpx.Client()
        # Token storage paths
        self.token_dir = pathlib.Path(
            os.getenv(
                "GITHUB_COPILOT_TOKEN_DIR", "~/.local/state/litellm/github_copilot"
            )
        ).expanduser()
        self.access_token_file = self.token_dir / os.getenv(
            "GITHUB_COPILOT_ACCESS_TOKEN_FILE", "access-token"
        )
        self.api_key_file = self.token_dir / os.getenv(
            "GITHUB_COPILOT_API_KEY_FILE", "api-key.json"
        )
        self._ensure_token_dir()

    def get_access_token(self) -> str:
        """
        Login to Copilot with retry 3 times.

        Returns:
            str: The GitHub access token.

        Raises:
            GetAccessTokenError: If unable to obtain an access token after retries.
        """
        try:
            with self.access_token_file.open("r") as f:
                access_token = f.read().strip()
                if access_token:
                    return access_token
        except IOError:
            logging.warning("No existing access token found or error reading file")

        for attempt in range(3):
            logging.debug(f"Access token acquisition attempt {attempt + 1}/3")
            try:
                access_token = self._login()
                try:
                    with self.access_token_file.open("w") as f:
                        f.write(access_token)
                except IOError:
                    logging.error("Error saving access token to file")
                return access_token
            except (GetDeviceCodeError, GetAccessTokenError, RefreshAPIKeyError) as e:
                logging.warning(f"Failed attempt {attempt + 1}: {str(e)}")
                continue

        raise GetAccessTokenError(
            message="Failed to get access token after 3 attempts",
            status_code=401,
        )

    def get_api_key(self) -> str:
        """
        Get the API key, refreshing if necessary.

        Returns:
            str: The GitHub Copilot API key.

        Raises:
            GetAPIKeyError: If unable to obtain an API key.
        """
        try:
            with self.api_key_file.open("r") as f:
                api_key_info = json.load(f)
                if api_key_info.get("expires_at", 0) > datetime.now().timestamp():
                    return api_key_info.get("token")
                else:
                    logging.warning("API key expired, refreshing")
                    raise APIKeyExpiredError(
                        message="API key expired",
                        status_code=401,
                    )
        except IOError:
            logging.warning("No API key file found or error opening file")
        except (json.JSONDecodeError, KeyError) as e:
            logging.warning(f"Error reading API key from file: {str(e)}")
        except APIKeyExpiredError:
            pass  # Already logged in the try block

        try:
            api_key_info = self._refresh_api_key()
            with self.api_key_file.open("w") as f:
                json.dump(api_key_info, f)
            token = api_key_info.get("token")
            if token:
                return token
            else:
                raise GetAPIKeyError(
                    message="API key response missing token",
                    status_code=401,
                )
        except IOError as e:
            logging.error(f"Error saving API key to file: {str(e)}")
            raise GetAPIKeyError(
                message=f"Failed to save API key: {str(e)}",
                status_code=500,
            )
        except RefreshAPIKeyError as e:
            raise GetAPIKeyError(
                message=f"Failed to refresh API key: {str(e)}",
                status_code=401,
            )

    def get_api_base(self) -> Optional[str]:
        """
        Get the API endpoint from the api-key.json file.

        Returns:
            Optional[str]: The GitHub Copilot API endpoint, or None if not found.
        """
        try:
            with self.api_key_file.open("r") as f:
                api_key_info = json.load(f)
                endpoints = api_key_info.get("endpoints", {})
                api_endpoint = endpoints.get("api")
                return api_endpoint
        except (IOError, json.JSONDecodeError, KeyError) as e:
            logging.warning(f"Error reading API endpoint from file: {str(e)}")
            return None

    def _refresh_api_key(self) -> dict[str, Any]:
        """
        Refresh the API key using the access token.

        Returns:
            Dict[str, Any]: The API key information including token and expiration.

        Raises:
            RefreshAPIKeyError: If unable to refresh the API key.
        """
        access_token = self.get_access_token()
        headers = self._get_github_headers(access_token)
        api_key_url = os.getenv(
            "GITHUB_COPILOT_API_KEY_URL", DEFAULT_GITHUB_API_KEY_URL
        )

        max_retries = 3
        for attempt in range(max_retries):
            try:
                response = self.http.get(api_key_url, headers=headers)
                response_json = response.raise_for_status().json()

                if "token" in response_json:
                    return response_json
                else:
                    logging.warning(f"API key response missing token: {response_json}")
            except httpx.HTTPStatusError as e:
                logging.error(
                    f"HTTP error refreshing API key (attempt {attempt + 1}/{max_retries}): {str(e)}"
                )
            except Exception as e:
                logging.error(f"Unexpected error refreshing API key: {str(e)}")

        raise RefreshAPIKeyError(
            message="Failed to refresh API key after maximum retries",
            status_code=401,
        )

    def _ensure_token_dir(self) -> None:
        """Ensure the token directory exists."""
        if not os.path.exists(self.token_dir):
            os.makedirs(self.token_dir, exist_ok=True)

    def _get_github_headers(self, access_token: Optional[str] = None) -> dict[str, str]:
        """
        Generate standard GitHub headers for API requests.

        Args:
            access_token: Optional access token to include in the headers.

        Returns:
            Dict[str, str]: Headers for GitHub API requests.
        """
        headers = {
            "Accept": "application/json",
            "Accept-Encoding": "gzip,deflate,br",
            "Editor-Version": "vscode/1.85.1",
            "Editor-Plugin-Version": "copilot/1.155.0",
            "User-Agent": "GithubCopilot/1.155.0",
        }

        if access_token:
            headers["Authorization"] = f"token {access_token}"

        return headers

    def _get_device_code(self) -> dict[str, str]:
        """
        Get a device code for GitHub authentication.

        Returns:
            Dict[str, str]: Device code information.

        Raises:
            GetDeviceCodeError: If unable to get a device code.
        """
        try:
            device_code_url = os.getenv(
                "GITHUB_COPILOT_DEVICE_CODE_URL", DEFAULT_GITHUB_DEVICE_CODE_URL
            )
            client_id = os.getenv("GITHUB_COPILOT_CLIENT_ID", DEFAULT_GITHUB_CLIENT_ID)
            resp = self.http.post(
                device_code_url,
                headers=self._get_github_headers(),
                json={"client_id": client_id, "scope": "read:user"},
            )
            resp.raise_for_status()
            resp_json = resp.json()

            required_fields = ["device_code", "user_code", "verification_uri"]
            if not all(field in resp_json for field in required_fields):
                logging.error(f"Response missing required fields: {resp_json}")
                raise GetDeviceCodeError(
                    message="Response missing required fields",
                    status_code=400,
                )

            return resp_json
        except httpx.HTTPStatusError as e:
            logging.error(f"HTTP error getting device code: {str(e)}")
            raise GetDeviceCodeError(
                message=f"Failed to get device code: {str(e)}",
                status_code=400,
            )
        except json.JSONDecodeError as e:
            logging.error(f"Error decoding JSON response: {str(e)}")
            raise GetDeviceCodeError(
                message=f"Failed to decode device code response: {str(e)}",
                status_code=400,
            )
        except Exception as e:
            logging.error(f"Unexpected error getting device code: {str(e)}")
            raise GetDeviceCodeError(
                message=f"Failed to get device code: {str(e)}",
                status_code=400,
            )

    def _poll_for_access_token(self, device_code: str) -> str:
        """
        Poll for an access token after user authentication.

        Args:
            device_code: The device code to use for polling.

        Returns:
            str: The access token.

        Raises:
            GetAccessTokenError: If unable to get an access token.
        """
        max_attempts = 12  # 1 minute (12 * 5 seconds)

        access_token_url = os.getenv(
            "GITHUB_COPILOT_ACCESS_TOKEN_URL", DEFAULT_GITHUB_ACCESS_TOKEN_URL
        )
        client_id = os.getenv("GITHUB_COPILOT_CLIENT_ID", DEFAULT_GITHUB_CLIENT_ID)

        for attempt in range(max_attempts):
            try:
                resp = self.http.post(
                    access_token_url,
                    headers=self._get_github_headers(),
                    json={
                        "client_id": client_id,
                        "device_code": device_code,
                        "grant_type": "urn:ietf:params:oauth:grant-type:device_code",
                    },
                )
                resp.raise_for_status()
                resp_json = resp.json()

                if "access_token" in resp_json:
                    logging.info("Authentication successful!")
                    return resp_json["access_token"]
                elif (
                    "error" in resp_json
                    and resp_json.get("error") == "authorization_pending"
                ):
                    logging.debug(
                        f"Authorization pending (attempt {attempt + 1}/{max_attempts})"
                    )
                else:
                    logging.warning(f"Unexpected response: {resp_json}")
            except httpx.HTTPStatusError as e:
                logging.error(f"HTTP error polling for access token: {str(e)}")
                raise GetAccessTokenError(
                    message=f"Failed to get access token: {str(e)}",
                    status_code=400,
                )
            except json.JSONDecodeError as e:
                logging.error(f"Error decoding JSON response: {str(e)}")
                raise GetAccessTokenError(
                    message=f"Failed to decode access token response: {str(e)}",
                    status_code=400,
                )
            except Exception as e:
                logging.error(f"Unexpected error polling for access token: {str(e)}")
                raise GetAccessTokenError(
                    message=f"Failed to get access token: {str(e)}",
                    status_code=400,
                )

            time.sleep(5)

        raise GetAccessTokenError(
            message="Timed out waiting for user to authorize the device",
            status_code=400,
        )

    def _login(self) -> str:
        """
        Login to GitHub Copilot using device code flow.

        Returns:
            str: The GitHub access token.

        Raises:
            GetDeviceCodeError: If unable to get a device code.
            GetAccessTokenError: If unable to get an access token.
        """
        device_code_info = self._get_device_code()

        device_code = device_code_info["device_code"]
        user_code = device_code_info["user_code"]
        verification_uri = device_code_info["verification_uri"]

        print(  # noqa: T201
            f"Please visit {verification_uri} and enter code {user_code} to authenticate.",
            # When this is running in docker, it may not be flushed immediately
            # so we force flush to ensure the user sees the message
            flush=True,
        )

        return self._poll_for_access_token(device_code)


def copilot_client() -> httpx.Client:
    authn = Authenticator()
    headers = {
        "Authorization": f"Bearer {authn.get_api_key()}",
        "Accept": "application/json",
        "Copilot-Integration-Id": "vscode-chat",
        "Editor-Version": "vscode/1.117.0",
        "Editor-Plugin-Version": "copilot-chat/0.26.7",
        "User-Agent": "GitHubCopilotChat/0.26.7",
        "OpenAI-Intent": "conversation-panel",
        "X-GitHub-API-Version": "2025-04-01",
        "X-VSCode-User-Agent-Library-Version": "electron-fetch",
    }
    return httpx.Client(
        base_url=authn.get_api_base(),
        headers=headers,
        follow_redirects=True,
    )


def get_access_token() -> str: ...


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
    copilot = copilot_client()
    output = copilot.get("/models").raise_for_status().json()

    models = []
    for m in output["data"]:
        if not isinstance(m, dict):
            continue
        m.setdefault("policy", {})
        m.setdefault("capabilities", {})

        if m["policy"].get("state") != "enabled":
            continue

        model = {
            "model_name": f"copilot/{m['id']}",
            "litellm_params": {
                "model": f"github_copilot/{m['id']}",
            },
            "model_info": {},
        }
        model["model_info"].update(
            {"key": m["version"], "litellm_provider": "github_copilot"}
        )
        # info = model["model_info"]
        # caps = m["capabilities"]
        # caps.setdefault("limits", {})
        # limits = caps["limits"]
        # caps.setdefault("supports", {})
        # supports = caps["supports"]
        # if "type" in caps:
        #     match caps["type"]:
        #         case "embeddings":
        #             info["mode"] = "embedding"
        #         case _:
        #             info["mode"] = caps["type"]
        # if "max_output_tokens" in limits:
        #     info["max_output_tokens"] = limits["max_output_tokens"]
        # if "max_prompt_tokens" in limits:
        #     info["max_input_tokens"] = limits["max_prompt_tokens"]
        # if "max_context_window_tokens" in limits:
        #     info["max_tokens"] = limits["max_context_window_tokens"]
        # if "tool_calls" in supports:
        #     info["supports_function_calling"] = supports["tool_calls"]
        # if "parallel_tool_calls" in supports:
        #     info["supports_parallel_function_calling"] = supports["parallel_tool_calls"]
        # if "vision" in supports:
        #     info["supports_vision"] = supports["vision"]
        # if "reasoning_effort" in supports and len(supports["reasoning_effort"]) > 0:
        #     info["supports_reasoning"] = True
        # else:
        #     info["supports_reasoning"] = False
        # if "response_schema" in supports:
        #     info["supports_response_schema"] = supports["response_schema"]
        # if "vision" in limits and limits["vision"].get("max_prompt_images", 0) > 0:
        #     info["supports_image_input"] = True
        # if "supported_endpoints" in m:
        #     info["supported_endpoints"] = m["supported_endpoints"]

        models.append(model)

    config = {
        "model_list": models,
    }
    config_path = _ROOT / "litellm" / "providers" / "github_copilot.yaml"
    config_path.parent.mkdir(parents=True, exist_ok=True)

    with config_path.open("w") as f:
        json.dump(config, f, indent=2)


if __name__ == "__main__":
    logging.basicConfig()
    main()
