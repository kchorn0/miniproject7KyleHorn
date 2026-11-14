# INF601 - Advanced Programming in Python
# Kyle Horn
# Mini Project 7

"""Practice Hub MCP server that lets Claude Code manage your posts.

This module is a Model Context Protocol (MCP) server built with FastMCP
from the official ``mcp`` Python SDK. It wraps the INF601 Practice Hub
REST API and exposes five tools that an AI agent such as Claude Code can
call: ``list_posts``, ``get_post``, ``create_post``, ``update_post``, and
``delete_post``.

How it works:
    1. Claude Code starts this file as a subprocess (the stdio transport).
    2. Claude reads each tool's docstring to decide which tool to call.
    3. Each tool sends one HTTP request to the Practice Hub API with your
       Bearer token and returns the JSON result (or a clear error message)
       back to Claude.

Configuration is read from environment variables and is never hard-coded:
    PRACTICE_API_URL    Base URL of the Hub, e.g.
                        https://practice.fhsucyber.com
    PRACTICE_API_TOKEN  Your personal API token from Week 1.

For local development these values may also live in a git-ignored ``.env``
file next to this script. Real environment variables (for example, those
passed with ``claude mcp add --env``) always take priority over ``.env``.
"""

# --- Standard library imports (built into Python) -------------------------
# logging writes status and error messages without using print().
import logging
# os reads environment variables such as PRACTICE_API_TOKEN.
import os
# sys gives access to stderr, where all log output must go.
import sys
# Path builds the location of the .env file in an OS-independent way.
from pathlib import Path

# --- Third-party imports (installed from requirements.txt) ----------------
# requests is the HTTP client used to call the Practice Hub API (as in MP1).
import requests
# load_dotenv copies the settings in .env into the environment variables.
from dotenv import load_dotenv
# FastMCP turns ordinary Python functions into MCP tools.
from mcp.server.fastmcp import FastMCP

# --- Logging --------------------------------------------------------------
# IMPORTANT: The stdio transport uses stdout to exchange MCP messages with
# Claude Code. Anything printed to stdout would corrupt that conversation,
# so this file never calls print() and sends every log message to stderr.
logging.basicConfig(
    # Send log messages to stderr instead of stdout.
    stream=sys.stderr,
    # Show INFO, WARNING, and ERROR messages (hide DEBUG noise).
    level=logging.INFO,
    # Prefix each message with the time, level, and logger name.
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
# Create a named logger so messages show they came from this server.
log = logging.getLogger("practice-hub")

# --- Configuration --------------------------------------------------------
# Load .env from this script's own folder, because Claude Code may start
# the server from a different working directory. override=False means a
# real environment variable always wins over a value in the .env file.
load_dotenv(Path(__file__).resolve().parent / ".env", override=False)

# Read the API base URL from the environment, defaulting to the course Hub.
# rstrip("/") removes a trailing slash so URLs never contain "//".
BASE = os.environ.get(
    "PRACTICE_API_URL", "https://practice.fhsucyber.com"
).rstrip("/")
# Read the API token from the environment (None if it is not set).
TOKEN = os.environ.get("PRACTICE_API_TOKEN")
# Build the Authorization header that every API request must send.
HEADERS = {"Authorization": f"Bearer {TOKEN}"}
# Give up on any request that takes longer than this many seconds, so a
# slow or offline Hub can never freeze the server.
TIMEOUT = 15

# Check whether the token is missing.
if not TOKEN:
    # Warn instead of crashing; the tools will return a clear 401 message.
    log.warning(
        "PRACTICE_API_TOKEN is not set - API calls will fail until it is."
    )

# Create the MCP server. "practice-hub" is the name Claude Code shows.
mcp = FastMCP("practice-hub")


# --- Error helpers --------------------------------------------------------
def _handle_error(resp):
    """Convert a failed API response into a clear error dictionary.

    Unlike the Mini Project 1 version, this helper never prints (stdout
    belongs to MCP) and never raises an exception (which would crash the
    tool). Instead it returns a dictionary that Claude can read and explain
    to the user.

    Args:
        resp: The ``requests.Response`` object from a failed API call.

    Returns:
        dict: ``{"error": ..., "status_code": ..., "detail": ...}`` where
        ``error`` is a friendly message and ``detail`` is the API's own
        explanation.
    """
    # Try to read the API's own error message from the JSON body.
    try:
        detail = resp.json().get("detail", "Unknown error.")
    # Fall back to the raw text if the body is not JSON (or not a dict).
    except (ValueError, AttributeError):
        detail = resp.text or "Unknown error."

    # 401 Unauthorized: the token is missing or wrong.
    if resp.status_code == 401:
        message = (
            "Invalid or missing API token. "
            "Check that PRACTICE_API_TOKEN is set."
        )
    # 403 Forbidden: the post belongs to someone else.
    elif resp.status_code == 403:
        message = "You can only edit or delete your own posts."
    # 404 Not Found: no post has that id.
    elif resp.status_code == 404:
        message = "Post not found. No post exists with that id."
    # 422 Unprocessable Entity: a field is missing or invalid.
    elif resp.status_code == 422:
        message = "Invalid data. One or more fields are missing or not valid."
    # Any other error code gets a general message.
    else:
        message = f"The API returned HTTP {resp.status_code}."

    # Record the failure in the log (stderr, never stdout).
    log.warning("API error %s: %s", resp.status_code, detail)
    # Return the error so Claude can explain it instead of crashing.
    return {
        "error": message,
        "status_code": resp.status_code,
        "detail": detail,
    }


def _connection_error(exc):
    """Convert a network failure into a clear error dictionary.

    Args:
        exc: The ``requests`` exception raised while contacting the Hub,
            such as a timeout or a refused connection.

    Returns:
        dict: ``{"error": ...}`` with a message describing the problem.
    """
    # The Hub did not answer within TIMEOUT seconds.
    if isinstance(exc, requests.exceptions.Timeout):
        message = f"The Practice Hub did not respond within {TIMEOUT} seconds."
    # The Hub could not be reached at all (offline, wrong URL, no network).
    elif isinstance(exc, requests.exceptions.ConnectionError):
        message = f"Could not connect to the Practice Hub at {BASE}."
    # Any other problem raised by the requests library.
    else:
        message = f"Request failed: {exc}"

    # Record the failure in the log (stderr, never stdout).
    log.warning(message)
    # Return the error so Claude can explain it instead of crashing.
    return {"error": message}


# --- MCP tools ------------------------------------------------------------
# Each @mcp.tool() function below becomes a tool that Claude Code can call.
# FastMCP builds each tool's input schema from the type hints and sends the
# docstring to Claude, so the docstrings are written for the model: they say
# when to use the tool and what each argument means.


# Read (list): GET /api/v1/posts
@mcp.tool()
def list_posts(
    mine: bool = False,
    tag: str | None = None,
    limit: int = 50,
) -> list[dict] | dict:
    """List posts on the Practice Hub, newest first.

    Use this to browse posts or to find a post's id. When the user asks
    about "my posts", set mine=True so only posts owned by the token's
    account are returned.

    Args:
        mine: True to return only your own posts; False (default) to
            return everyone's posts.
        tag: Optional tag to filter by, e.g. "python". Only posts with
            this tag are returned.
        limit: Maximum number of posts to return (1-100, default 50).

    Returns:
        A list of posts (each with id, title, body, tags, author_name,
        created_at, and updated_at), or a dict with an "error" key if the
        request failed.
    """
    # Build the query string parameters, e.g. ?mine=True&limit=50.
    params = {"mine": mine, "limit": limit}
    # Only add the tag filter if one was given.
    if tag:
        params["tag"] = tag

    # Send the request; network problems raise an exception.
    try:
        resp = requests.get(
            f"{BASE}/api/v1/posts",
            headers=HEADERS,
            params=params,
            timeout=TIMEOUT,
        )
    # Turn a network failure into a clear message instead of crashing.
    except requests.exceptions.RequestException as exc:
        return _connection_error(exc)

    # resp.ok is False for any 4xx/5xx status code.
    if not resp.ok:
        return _handle_error(resp)
    # Success: convert the JSON list of posts into Python data.
    return resp.json()


# Read (one): GET /api/v1/posts/{id}
@mcp.tool()
def get_post(post_id: int) -> dict:
    """Get a single Practice Hub post by its id.

    Use this when you already know a post's id (for example, from
    list_posts) and need its full details: title, full body, tags, author,
    timestamps, and attachments.

    Args:
        post_id: The numeric id of the post to fetch.

    Returns:
        The post as a dict, or a dict with an "error" key (for example,
        404 if no post has that id).
    """
    # Send the request for this one post id.
    try:
        resp = requests.get(
            f"{BASE}/api/v1/posts/{post_id}",
            headers=HEADERS,
            timeout=TIMEOUT,
        )
    # Turn a network failure into a clear message instead of crashing.
    except requests.exceptions.RequestException as exc:
        return _connection_error(exc)

    # A 404 here means the post does not exist.
    if not resp.ok:
        return _handle_error(resp)
    # Success: convert the JSON post into a Python dict.
    return resp.json()


# Create: POST /api/v1/posts
@mcp.tool()
def create_post(
    title: str,
    body: str = "",
    tags: list[str] | None = None,
) -> dict:
    """Create a new post on the Practice Hub, owned by your account.

    Use this when the user asks to create, write, or publish a new post.
    The new post belongs to the account that owns the API token, so it can
    later be edited or deleted with update_post and delete_post.

    Args:
        title: The post's title (required, cannot be empty).
        body: The post's text (optional; Markdown is fine). Defaults to
            an empty string.
        tags: Optional list of tag strings, e.g. ["python", "mcp"]. Pass a
            list, not one comma-separated string. Leave it out for no tags.

    Returns:
        The newly created post as a dict, including its new "id", or a
        dict with an "error" key if the post could not be created.
    """
    # Reject an empty or blank title before calling the API.
    if not title or not title.strip():
        return {"error": "A title is required to create a post."}

    # Send the new post as JSON; "tags or []" turns None into an empty list.
    try:
        resp = requests.post(
            f"{BASE}/api/v1/posts",
            headers=HEADERS,
            json={"title": title, "body": body, "tags": tags or []},
            timeout=TIMEOUT,
        )
    # Turn a network failure into a clear message instead of crashing.
    except requests.exceptions.RequestException as exc:
        return _connection_error(exc)

    # A 422 here means the API rejected one of the fields.
    if not resp.ok:
        return _handle_error(resp)
    # Success (201 Created): return the new post, including its id.
    return resp.json()


# Update: PATCH /api/v1/posts/{id}
@mcp.tool()
def update_post(
    post_id: int,
    title: str | None = None,
    body: str | None = None,
    tags: list[str] | None = None,
) -> dict:
    """Edit one of your own Practice Hub posts.

    Use this when the user asks to edit, rename, or change a post they own.
    Only the fields you pass are changed; anything left out stays the same.
    If you don't know the post's id, call list_posts(mine=True) first to
    find it. Editing someone else's post is not allowed and returns a 403
    error.

    Args:
        post_id: The numeric id of the post to edit.
        title: New title (optional). Cannot be empty if given.
        body: New text for the post (optional).
        tags: New list of tag strings, e.g. ["python", "mcp"] (optional).
            This replaces the old tags. Pass [] to remove all tags; leave
            it out to keep the current tags.

    Returns:
        The updated post as a dict, or a dict with an "error" key (for
        example, 403 if the post isn't yours, 404 if no post has that id).
    """
    # Collect only the fields the caller wants to change (PATCH semantics).
    data = {}
    # "is not None" lets an intentionally empty value through, e.g. tags=[].
    if title is not None:
        # Reject a blank title before calling the API.
        if not title.strip():
            return {"error": "The title cannot be empty."}
        data["title"] = title
    if body is not None:
        data["body"] = body
    if tags is not None:
        data["tags"] = tags

    # Don't send an empty request if nothing was given to change.
    if not data:
        return {
            "error": "Nothing to update - provide a title, body, or tags."
        }

    # Send only the changed fields to the post's URL.
    try:
        resp = requests.patch(
            f"{BASE}/api/v1/posts/{post_id}",
            headers=HEADERS,
            json=data,
            timeout=TIMEOUT,
        )
    # Turn a network failure into a clear message instead of crashing.
    except requests.exceptions.RequestException as exc:
        return _connection_error(exc)

    # A 403 here means the post is not yours; a 404 means it doesn't exist.
    if not resp.ok:
        return _handle_error(resp)
    # Success: return the post as it looks after the update.
    return resp.json()


# Delete: DELETE /api/v1/posts/{id}
@mcp.tool()
def delete_post(post_id: int) -> dict:
    """Permanently delete one of your own Practice Hub posts.

    Use this only when the user asks to delete or remove a post they own.
    Deleting is permanent and cannot be undone, so confirm the exact post
    with the user first (use list_posts(mine=True) or get_post to check it
    is the right one). Deleting someone else's post is not allowed and
    returns a 403 error.

    Args:
        post_id: The numeric id of the post to delete.

    Returns:
        {"success": True, "message": "..."} if the post was deleted, or a
        dict with an "error" key (for example, 403 if the post isn't yours,
        404 if no post has that id).
    """
    # Send the delete request for this post id.
    try:
        resp = requests.delete(
            f"{BASE}/api/v1/posts/{post_id}",
            headers=HEADERS,
            timeout=TIMEOUT,
        )
    # Turn a network failure into a clear message instead of crashing.
    except requests.exceptions.RequestException as exc:
        return _connection_error(exc)

    # A 403 here means the post is not yours; a 404 means it doesn't exist.
    if not resp.ok:
        return _handle_error(resp)
    # Success is "204 No Content" (an empty body), so there is no JSON to
    # read; calling resp.json() would crash. Return a clear message instead.
    return {"success": True, "message": f"Post {post_id} was deleted."}


# Run the server only when this file is executed directly
# (python server.py), not when it is imported by a test or another module.
if __name__ == "__main__":
    # Start the server on the stdio transport, which is what
    # "claude mcp add practice-hub -- python server.py" expects.
    mcp.run()
