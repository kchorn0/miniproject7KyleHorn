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

#Logging
# IMPORTANT: The stdio transport uses stdout to talk to Claude Code.
# Anything printed to stdout would break that connection, so this file
# never uses print() and sends all log messages to stderr instead.
logging.basicConfig(
    stream=sys.stderr,
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
log = logging.getLogger("practice-hub")

#Config
# Loads the .env file from this script's folder (Claude Code may start the
# server from a different folder). override=False means real environment
# variables win over the values in the .env file.
load_dotenv(Path(__file__).resolve().parent / ".env", override=False)

# Gets the API URL from the environment variables (defaults to the course Hub)
BASE = os.environ.get("PRACTICE_API_URL", "https://practice.fhsucyber.com").rstrip("/")
# Gets the API token from the computer's environment variables
TOKEN = os.environ.get("PRACTICE_API_TOKEN")
# Creates the Authorization header using the API token Bearer
HEADERS = {"Authorization": f"Bearer {TOKEN}"}
# Stops a request from hanging forever if the Hub does not answer
TIMEOUT = 15  # seconds

# Checks if the API token was not found
if not TOKEN:
    # Warns instead of crashing - the tools will return a clear 401 message
    log.warning("PRACTICE_API_TOKEN is not set - API calls will fail until it is.")

# Creates the MCP server that Claude Code will connect to
mcp = FastMCP("practice-hub")


#Handle Errors
def _handle_error(resp):
    """Turn a failed API response into a clear error message.

    Unlike MP1, this never prints (stdout belongs to MCP) and never raises
    (an exception would crash the tool). It returns a dict the model can
    read and explain to the user instead.
    """
    # Gets the error details from the API response (if the body is JSON)
    try:
        detail = resp.json().get("detail", "Unknown error.")
    except (ValueError, AttributeError):
        detail = resp.text or "Unknown error."

    # Checks if the API returned a 401 error
    if resp.status_code == 401:
        message = "Invalid or missing API token. Check that PRACTICE_API_TOKEN is set."
    # Checks if the API returned a 403 error
    elif resp.status_code == 403:
        message = "You can only edit or delete your own posts."
    # Checks if the API returned a 404 error
    elif resp.status_code == 404:
        message = "Post not found. No post exists with that id."
    # Checks if the API returned a 422 error
    elif resp.status_code == 422:
        message = "Invalid data. One or more fields are missing or not valid."
    # Handles any other type of error
    else:
        message = f"The API returned HTTP {resp.status_code}."

    # Logs the failure to stderr (never stdout)
    log.warning("API error %s: %s", resp.status_code, detail)
    # Returns the error so the model can explain it instead of crashing
    return {"error": message, "status_code": resp.status_code, "detail": detail}


#Handle Connection Errors
def _connection_error(exc):
    """Turn a network problem (timeout, no connection) into a clear error message."""
    # Checks if the Hub took too long to answer
    if isinstance(exc, requests.exceptions.Timeout):
        message = f"The Practice Hub did not respond within {TIMEOUT} seconds."
    # Checks if the Hub could not be reached at all
    elif isinstance(exc, requests.exceptions.ConnectionError):
        message = f"Could not connect to the Practice Hub at {BASE}."
    # Handles any other request problem
    else:
        message = f"Request failed: {exc}"

    log.warning(message)
    return {"error": message}


#Tools
# Each tool calls one Practice Hub endpoint. The docstrings matter: the model
# reads them to decide when to call each tool and what to pass in.

#Read(List)
@mcp.tool()
def list_posts(mine: bool = False, tag: str | None = None, limit: int = 50) -> list[dict] | dict:
    """List posts on the Practice Hub, newest first.

    Use this to browse posts or to find a post's id. When the user asks about
    "my posts", set mine=True so only posts owned by the token's account are
    returned.

    Args:
        mine: True to return only your own posts; False (default) for everyone's posts.
        tag: Optional tag to filter by, e.g. "python". Only posts with this tag are returned.
        limit: Maximum number of posts to return (1-100, default 50).

    Returns:
        A list of posts (each with id, title, body, tags, author_name,
        created_at, updated_at), or a dict with an "error" key if the request failed.
    """
    # Creates the query parameters for the request
    params = {"mine": mine, "limit": limit}
    # Checks if a tag was provided
    if tag:
        # Adds the tag to the query parameters
        params["tag"] = tag

    try:
        # Sends a GET request to retrieve posts and sends the query parameters with the request
        resp = requests.get(f"{BASE}/api/v1/posts", headers=HEADERS, params=params, timeout=TIMEOUT)
    except requests.exceptions.RequestException as exc:
        # Returns a clear message if the Hub could not be reached
        return _connection_error(exc)

    # Checks if the API request was not successful
    if not resp.ok:
        # Returns the error message instead of crashing
        return _handle_error(resp)
    # Converts the response from JSON into Python data and returns it
    return resp.json()


#Read
@mcp.tool()
def get_post(post_id: int) -> dict:
    """Get a single Practice Hub post by its id.

    Use this when you already know a post's id (for example from list_posts)
    and need its full details: title, full body, tags, author, timestamps,
    and attachments.

    Args:
        post_id: The numeric id of the post to fetch.

    Returns:
        The post as a dict, or a dict with an "error" key (e.g. 404 if no
        post has that id).
    """
    try:
        # Sends a GET request for the specific post ID
        resp = requests.get(f"{BASE}/api/v1/posts/{post_id}", headers=HEADERS, timeout=TIMEOUT)
    except requests.exceptions.RequestException as exc:
        # Returns a clear message if the Hub could not be reached
        return _connection_error(exc)

    # Checks if the API request was not successful
    if not resp.ok:
        # Returns the error message instead of crashing
        return _handle_error(resp)
    # Converts the response from JSON into Python data and returns it
    return resp.json()


#Create
@mcp.tool()
def create_post(title: str, body: str = "", tags: list[str] | None = None) -> dict:
    """Create a new post on the Practice Hub, owned by your account.

    Use this when the user asks to create, write, or publish a new post.
    The new post belongs to the account that owns the API token, so you can
    later edit or delete it with update_post and delete_post.

    Args:
        title: The post's title (required, cannot be empty).
        body: The post's text (optional, Markdown is fine). Defaults to empty.
        tags: Optional list of tag strings, e.g. ["python", "mcp"]. Pass a
            list, not one comma-separated string. Leave it out for no tags.

    Returns:
        The newly created post as a dict, including its new "id", or a dict
        with an "error" key if the post could not be created.
    """
    # Checks if the title is missing or only spaces before calling the API
    if not title or not title.strip():
        return {"error": "A title is required to create a post."}

    try:
        # Sends a POST request to the posts endpoint and sends the API token in the request headers
        resp = requests.post(f"{BASE}/api/v1/posts", headers=HEADERS,
                             # Sends the title, body, and tags as JSON data
                             json={"title": title, "body": body, "tags": tags or []},
                             timeout=TIMEOUT)
    except requests.exceptions.RequestException as exc:
        # Returns a clear message if the Hub could not be reached
        return _connection_error(exc)

    # Checks if the API request was not successful
    if not resp.ok:
        # Returns the error message instead of crashing
        return _handle_error(resp)
    # Converts the response (the new post, with its id) from JSON into Python data and returns it
    return resp.json()


#Update
@mcp.tool()
def update_post(post_id: int, title: str | None = None, body: str | None = None,
                tags: list[str] | None = None) -> dict:
    """Edit one of your own Practice Hub posts.

    Use this when the user asks to edit, rename, or change a post they own.
    Only the fields you pass are changed; anything left out stays the same.
    If you don't know the post's id, call list_posts(mine=True) first to
    find it. Editing someone else's post is not allowed and returns a 403 error.

    Args:
        post_id: The numeric id of the post to edit.
        title: New title (optional). Cannot be empty if given.
        body: New text for the post (optional).
        tags: New list of tag strings, e.g. ["python", "mcp"] (optional).
            This replaces the old tags. Pass [] to remove all tags; leave it
            out to keep the current tags.

    Returns:
        The updated post as a dict, or a dict with an "error" key (e.g. 403
        if the post isn't yours, 404 if no post has that id).
    """
    # Creates an empty dictionary to hold the information we want to update
    data = {}
    # Checks if a new title was provided
    if title is not None:
        # Checks if the new title is empty or only spaces
        if not title.strip():
            return {"error": "The title cannot be empty."}
        # Adds the new title to the update data
        data["title"] = title
    # Checks if a new body was provided
    if body is not None:
        # Adds the new body to the update data
        data["body"] = body
    # Checks if new tags were provided
    if tags is not None:
        # Adds the new tags to the update data
        data["tags"] = tags

    # Checks if nothing was provided to update
    if not data:
        return {"error": "Nothing to update - provide a title, body, or tags."}

    try:
        # Sends a PATCH request to update the specific post
        resp = requests.patch(f"{BASE}/api/v1/posts/{post_id}",
                              # Sends the API token in the request headers
                              headers=HEADERS,
                              # Sends only the information that needs to be updated
                              json=data,
                              timeout=TIMEOUT)
    except requests.exceptions.RequestException as exc:
        # Returns a clear message if the Hub could not be reached
        return _connection_error(exc)

    # Checks if the API request was not successful
    if not resp.ok:
        # Returns the error message instead of crashing (e.g. 403 not your post)
        return _handle_error(resp)
    # Converts the response (the updated post) from JSON into Python data and returns it
    return resp.json()


# TODO (next step): delete_post


# Checks if this file is being run directly instead of being imported
if __name__ == "__main__":
    # Starts the server using the stdio transport, which is what
    # `claude mcp add ... -- python server.py` expects
    mcp.run()
