# INF601 - Advanced Programming in Python
# Kyle Horn
# Mini Project 7

"""
Practice Hub MCP Server

An MCP (Model Context Protocol) server built with FastMCP that wraps the
INF601 Practice Hub REST API. Once registered with Claude Code, it lets the
agent list, read, create, update, and delete your posts on the Hub.

Configuration is read from environment variables (never hard-coded):
    PRACTICE_API_URL    - base URL of the Hub (e.g. https://practice.fhsucyber.com)
    PRACTICE_API_TOKEN  - your personal API token from Week 1

For local development these can also live in a git-ignored .env file next to
this script. Real environment variables (e.g. from `claude mcp add --env`)
always take priority over the .env file.
"""

import logging
import os
import sys
from pathlib import Path

import requests
from dotenv import load_dotenv
from mcp.server.fastmcp import FastMCP

# ---------------------------------------------------------------------------
# Logging
# ---------------------------------------------------------------------------
# IMPORTANT: The stdio transport uses stdout for the MCP protocol itself.
# Anything printed to stdout would corrupt that stream, so we never use
# print() and send all log messages to stderr instead.
logging.basicConfig(
    stream=sys.stderr,
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
log = logging.getLogger("practice-hub")

# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------
# Load .env from this script's folder (Claude Code may start the server from
# a different working directory). override=False means real environment
# variables win over values in the .env file.
load_dotenv(Path(__file__).resolve().parent / ".env", override=False)

API_URL = os.environ.get("PRACTICE_API_URL", "https://practice.fhsucyber.com").rstrip("/")
API_TOKEN = os.environ.get("PRACTICE_API_TOKEN")
REQUEST_TIMEOUT = 15  # seconds

if not API_TOKEN:
    # Don't crash: the server still starts, and every tool explains the problem.
    log.warning("PRACTICE_API_TOKEN is not set - API calls will fail until it is.")

# ---------------------------------------------------------------------------
# MCP server
# ---------------------------------------------------------------------------
mcp = FastMCP("practice-hub")

# Friendly explanations for the status codes the Practice Hub API returns.
ERROR_MESSAGES = {
    400: "Bad request - the API could not understand the request.",
    401: "Unauthorized - your API token is missing or invalid. "
         "Check that PRACTICE_API_TOKEN is set correctly.",
    403: "Forbidden - you can only edit or delete your own posts.",
    404: "Not found - no post exists with that id.",
    409: "Conflict - the request conflicts with existing data.",
    422: "Validation error - one or more fields are missing or invalid.",
    429: "Too many requests - slow down and try again shortly.",
}


def api_request(method: str, path: str, **kwargs) -> dict | list:
    """Send an authenticated request to the Practice Hub API.

    Every tool goes through this one helper so authentication and error
    handling live in a single place. It never raises: on any failure it
    returns a dict like {"error": "...", "status_code": 404} that the model
    can read and explain to the user, so the MCP server keeps running.

    Args:
        method: HTTP method, e.g. "GET", "POST", "PATCH", "DELETE".
        path: API path starting with "/", e.g. "/api/v1/posts".
        **kwargs: Passed through to requests (e.g. params=..., json=...).

    Returns:
        The decoded JSON response on success, {"success": True} for an
        empty success response (like 204 No Content from DELETE), or an
        {"error": ...} dict on failure.
    """
    if not API_TOKEN:
        return {
            "error": "PRACTICE_API_TOKEN is not set. Add it to your environment "
                     "or .env file and restart the server."
        }

    url = f"{API_URL}{path}"
    headers = {"Authorization": f"Bearer {API_TOKEN}"}
    log.info("%s %s", method, path)  # never log the token

    try:
        response = requests.request(
            method, url, headers=headers, timeout=REQUEST_TIMEOUT, **kwargs
        )
    except requests.exceptions.Timeout:
        return {"error": f"The Practice Hub did not respond within {REQUEST_TIMEOUT} seconds."}
    except requests.exceptions.ConnectionError:
        return {"error": f"Could not connect to the Practice Hub at {API_URL}."}
    except requests.exceptions.RequestException as exc:
        return {"error": f"Request failed: {exc}"}

    # --- Success ----------------------------------------------------------
    if response.ok:
        if response.status_code == 204 or not response.content:
            return {"success": True, "status_code": response.status_code}
        try:
            return response.json()
        except ValueError:
            return {"error": "The API returned a response that was not valid JSON."}

    # --- Failure: build a clear message instead of raising ----------------
    # The API reports errors as {"detail": "..."}; 422 errors may use a list.
    try:
        detail = response.json().get("detail")
    except (ValueError, AttributeError):
        detail = response.text or None

    message = ERROR_MESSAGES.get(
        response.status_code, f"The API returned HTTP {response.status_code}."
    )
    log.warning("%s %s -> %s", method, path, response.status_code)

    result = {"error": message, "status_code": response.status_code}
    if detail:
        result["detail"] = detail
    return result


# ---------------------------------------------------------------------------
# Tools
# ---------------------------------------------------------------------------
# Added one step at a time:
#   list_posts, get_post, create_post, update_post, delete_post


if __name__ == "__main__":
    # Default transport is stdio, which is what `claude mcp add ... -- python server.py` expects.
    mcp.run()
