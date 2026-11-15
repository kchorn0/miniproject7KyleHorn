# miniproject7KyleHorn

INF601 - Advanced Programming in Python
Kyle Horn
Mini Project 7

## Practice Hub MCP Server

A Model Context Protocol (MCP) server, built with FastMCP, that wraps the INF601 Practice Hub REST API so Claude Code can read, create, update, and delete my posts on the Hub through natural-language requests.

## Description

This project connects the Practice Hub API I first called by hand in Mini Project 1 to an AI agent. Instead of running a script, I can ask Claude Code something like *"show me my posts"* or *"create a post titled…"*, and Claude calls the matching tool on my server.

**How it works:**

1. Claude Code starts `server.py` as a local subprocess using the **stdio** transport.
2. The server exposes five **tools**. Claude reads each tool's docstring to decide which one to call and what to pass in.
3. Each tool sends one HTTP request to the Practice Hub API with my Bearer token and returns the JSON result, or a clear error message, back to Claude.

**The five tools:**

| Tool | API endpoint | What it does |
|------|--------------|--------------|
| `list_posts` | `GET /api/v1/posts` | Lists posts, newest first. Supports `mine=True` (only my posts), `tag`, and `limit`. |
| `get_post` | `GET /api/v1/posts/{id}` | Gets one post by its id. |
| `create_post` | `POST /api/v1/posts` | Creates a new post with a `title`, optional `body`, and optional `tags` list. |
| `update_post` | `PATCH /api/v1/posts/{id}` | Edits one of my own posts. Only the fields passed in are changed. |
| `delete_post` | `DELETE /api/v1/posts/{id}` | Permanently deletes one of my own posts. |

**Error handling:** no API error crashes the server. Each tool returns a readable message instead:

| Situation | Message returned |
|-----------|------------------|
| 401 – missing or invalid token | "Invalid or missing API token. Check that PRACTICE_API_TOKEN is set." |
| 403 – post belongs to someone else | "You can only edit or delete your own posts." |
| 404 – no post with that id | "Post not found. No post exists with that id." |
| 422 – missing or invalid field | "Invalid data. One or more fields are missing or not valid." |
| Hub too slow (15 s timeout) | "The Practice Hub did not respond within 15 seconds." |
| Hub unreachable | "Could not connect to the Practice Hub at …" |

All logging goes to **stderr**, never stdout, because the stdio transport uses stdout to talk to Claude Code.

**Project files:**

* `server.py` — the MCP server and its five tools
* `requirements.txt` — Python packages (`mcp`, `requests`, `python-dotenv`)
* `.env.example` — template for the two environment variables (the real `.env` is git-ignored)
* `docs/acceptance_test/` — screenshots and transcript proving the acceptance test:
  * `01_mcp_list.png` — `claude mcp list` showing `practice-hub` ✓ Connected
  * `02_mcp_tools.png` — `/mcp` in Claude Code showing all 5 tools
  * `03__read_posts.png` — Claude Code reading my posts
  * `04_create_post.png` — Claude Code creating post #59
  * `05_update_post.png` — Claude Code changing post #59's title
  * `06_confirm_post.png` — Claude Code reading post #59 back to confirm the edit
  * `transcript.txt` — exported text of the full Claude Code session

## Getting Started

### Dependencies

* Python 3.10 or newer
* `pip` (comes with Python)
* An API token from the INF601 Practice Hub (`https://practice.fhsucyber.com/`). See step 1 of [Executing program](#executing-program) for how to get one.
* [Claude Code](https://code.claude.com/docs) installed and signed in (see Installing, step 5)
* Internet access (every tool calls the live API)
* All Python packages are listed in `requirements.txt` and installed with `pip`. You do not need to install `mcp`, `requests`, or `python-dotenv` separately.

Works on both Windows and Linux (Ubuntu). Commands for both are given at every step below.

### Installing

1. Clone the repository:

Windows (PowerShell) and Linux (bash) — same command:
```
git clone https://github.com/kchorn0/miniproject7KyleHorn.git
cd miniproject7KyleHorn
```

2. Create a virtual environment:

Windows (PowerShell):
```
python -m venv .venv
```
Linux (bash):
```
python3 -m venv .venv
```

3. Activate the virtual environment:

Windows (PowerShell):
```
.\.venv\Scripts\Activate.ps1
```
If PowerShell blocks this with a "running scripts is disabled" error, run `Set-ExecutionPolicy -Scope CurrentUser RemoteSigned` once in your own PowerShell, then try again.

Linux (bash):
```
source .venv/bin/activate
```

4. Install the required packages (with the venv activated):

Windows and Linux — same command:
```
pip install -r requirements.txt
```
Note: `requirements.txt` pins `mcp` below version 2, because version 2 renamed `FastMCP`. This project uses `from mcp.server.fastmcp import FastMCP`, as the course requires.

5. Install Claude Code (skip this if `claude --version` already works):

Windows (PowerShell, **not** as Administrator):
```
irm https://claude.ai/install.ps1 | iex
```
Linux (bash):
```
curl -fsSL https://claude.ai/install.sh | bash
```
Close and reopen your terminal, then confirm it works:
```
claude --version
```

### Executing program

1. Get a Practice Hub API token (skip this if you already have one):

Linux (bash):
```
curl -X POST https://practice.fhsucyber.com/api/v1/auth/register \
  -H "Content-Type: application/json" \
  -d '{"name":"Your Name","email":"you@example.com","password":"yourpassword123"}'
```
Windows (PowerShell):
```
Invoke-RestMethod -Method Post -Uri https://practice.fhsucyber.com/api/v1/auth/register -ContentType "application/json" -Body '{"name":"Your Name","email":"you@example.com","password":"yourpassword123"}'
```
This returns JSON containing an `api_token`. Copy that value. If you already registered but lost your token, POST your email and password to `/api/v1/auth/token` instead (this replaces your old token).

2. Set the two required environment variables. The server reads these instead of hard-coding the URL and token, so nothing sensitive is stored in the code. Choose **one** of the two options.

**Option A — `.env` file (recommended, and what I used).** It is saved permanently and is never committed, because `.env` is listed in `.gitignore`.

Windows (PowerShell):
```
Copy-Item .env.example .env
```
Linux (bash):
```
cp .env.example .env
```
Then open `.env` and replace `your-token-here` with your token (no quotes, no spaces):
```
PRACTICE_API_URL=https://practice.fhsucyber.com
PRACTICE_API_TOKEN=your-token-here
```

**Option B — terminal environment variables.** These only last for the current terminal session.

Windows (PowerShell):
```
$env:PRACTICE_API_URL = "https://practice.fhsucyber.com"
$env:PRACTICE_API_TOKEN = "paste-your-token-here"
```
Linux (bash):
```
export PRACTICE_API_URL="https://practice.fhsucyber.com"
export PRACTICE_API_TOKEN="paste-your-token-here"
```

3. (Optional) Check that the server starts, from the project's root folder with the venv activated:

Windows (PowerShell):
```
python .\server.py
```
Linux (bash):
```
python3 server.py
```
If it works, the terminal shows almost nothing and just waits. That is correct: it is waiting for Claude Code to connect over stdin/stdout. Press `Ctrl+C` to stop it.

4. Register the server with Claude Code. Run this **from the project's root folder**, because the registration applies to the folder it is run from. Always point it at the **venv's Python**, because the system Python does not have the packages installed.

**If you used Option A (`.env` file)** — this is the exact command I used:

Windows (PowerShell, one line; replace the path with your own and keep the quotes):
```
claude mcp add practice-hub -- "C:\path\to\miniproject7KyleHorn\.venv\Scripts\python.exe" "C:\path\to\miniproject7KyleHorn\server.py"
```
Linux (bash):
```
claude mcp add practice-hub -- "$(pwd)/.venv/bin/python" "$(pwd)/server.py"
```

**If you used Option B, or prefer to pass the variables to Claude Code directly** (the course's `--env` form):

Windows (PowerShell, one line):
```
claude mcp add practice-hub --env PRACTICE_API_URL=https://practice.fhsucyber.com --env PRACTICE_API_TOKEN=your-token -- "C:\path\to\miniproject7KyleHorn\.venv\Scripts\python.exe" "C:\path\to\miniproject7KyleHorn\server.py"
```
Linux (bash):
```
claude mcp add practice-hub \
  --env PRACTICE_API_URL=https://practice.fhsucyber.com \
  --env PRACTICE_API_TOKEN=your-token \
  -- "$(pwd)/.venv/bin/python" "$(pwd)/server.py"
```

5. Confirm the server is registered and connected:

Windows and Linux — same command:
```
claude mcp list
```
You should see `practice-hub: ... ✓ Connected`.

6. Run the acceptance test. From the project's root folder, start a **new** Claude Code session (MCP servers load when a session starts):
```
claude
```
Type `/mcp` and confirm `practice-hub` is connected with 5 tools. Then send these prompts one at a time:
```
Use the practice-hub tools to show me my posts.
```
```
Use the practice-hub tools to create a new post with title "MP7 acceptance test", body "Created by Claude Code through my MCP server", and tags MP7, ClaudeCode, MCP.
```
```
Use the practice-hub tools to change that post's title to "MP7 acceptance test (edited)".
```
```
Use the practice-hub tools to get that post again so I can confirm the change.
```
Claude Code may ask permission before each tool call; approve it. To save the session as evidence, type `/export`.

7. Check the output. My results are in `docs/acceptance_test/`. Claude Code chose and called these tools from my docstrings alone:

| Step | Tool called | Input | Result |
|------|-------------|-------|--------|
| Read | `list_posts` | `{"mine": true}` | Listed my 3 posts (#57, #56, #4) |
| Create | `create_post` | `{"title": "MP7 acceptance test", "body": "Created by Claude Code through my MCP server", "tags": ["MP7", "ClaudeCode", "MCP"]}` | Created post #59 |
| Modify | `update_post` | `{"post_id": 59, "title": "MP7 acceptance test (edited)"}` | Title changed; body and tags unchanged |
| Confirm | `get_post` | `{"post_id": 59}` | Returned the edited title |

## Help

* `claude : The term 'claude' is not recognized` (Windows) — Claude Code's folder is not on your PATH, or the terminal was opened before you installed it. Close and reopen the terminal. In VS Code, fully exit and restart VS Code. If it still fails, add `%USERPROFILE%\.local\bin` to your user PATH, or run it by its full path: `& "$env:USERPROFILE\.local\bin\claude.exe"`.
* `claude mcp list` shows practice-hub as **Failed to connect** — the command most likely points at the system Python instead of the venv's Python, or a path containing spaces is not in quotes. Remove the registration with `claude mcp remove practice-hub` and re-run step 4 of Executing program.
* `ModuleNotFoundError: No module named 'mcp'` (or `requests` / `dotenv`) — your virtual environment isn't activated, or the packages weren't installed into it. Re-run steps 3 and 4 of Installing.
* `No module named 'mcp.server.fastmcp'` — `mcp` version 2 is installed. Run `pip install -r requirements.txt` again to install the pinned 1.x version.
* `running scripts is disabled on this system` (Windows only) — run `Set-ExecutionPolicy -Scope CurrentUser RemoteSigned` once, or skip activation and use `.\.venv\Scripts\python.exe` directly.
* A tool returns **"Invalid or missing API token"** (401) — `PRACTICE_API_TOKEN` is not set where the server can see it. Check your `.env` file, or the `--env` value in your `claude mcp add` command.
* A tool returns **"You can only edit or delete your own posts"** (403) — the post belongs to another user. Use `list_posts` with `mine=True` to find your own post ids.
* A tool returns **"Post not found"** (404) — no post exists with that id. Check the id with `list_posts`.
* Claude Code does not see the server at all — make sure you started `claude` from the project's root folder (the folder you registered from), and that `server.py` has not been changed to `print()` anything (stdout is reserved for the MCP protocol).
* "Could not connect to the Practice Hub" — confirm `https://practice.fhsucyber.com/health` responds with `{"status": "ok"}` in a browser.

## Authors

Kyle Horn ([kchorn@mail.fhsu.edu](mailto:kchorn@mail.fhsu.edu))

## Acknowledgments

Inspiration, code snippets, etc.

* [Practice Hub API Guide](https://practice.fhsucyber.com/docs-guide)
* [MCP Python SDK (FastMCP)](https://github.com/modelcontextprotocol/python-sdk)
* [Model Context Protocol documentation](https://modelcontextprotocol.io)
* [Claude Code MCP documentation](https://code.claude.com/docs/en/mcp)
* My Mini Project 1 Practice Hub client, which this server's tool structure and error handling are based on

## AI Usage

**What AI helped with:** I used Claude Code as a pair-programming assistant and worked through the project one step at a time, planning each phase and approving each change before it was made. Following my direction, it scaffolded the FastMCP server structure, the five tool functions (adapted from my own Mini Project 1 client), and the shared error-handling helpers. It also helped me set up and troubleshoot my environment (installing Claude Code and fixing my PATH), checked the code against PEP 8 and PEP 257, and ran test calls against the API so I could verify each tool before moving on.

**What I personally did:** I read the assignment and planned the project in phases, and I chose to build and test create, update, and delete as separate steps so I could review each one on its own. I chose `requests` over `httpx` so the server would match the style of my Mini Project 1 client, and I provided that client as the model for the code structure. I set up and managed my own API token in a git-ignored `.env` file, and chose to register the server that way so my token never appears in a command or in the repository. I set a rule that testing must never send requests to another student's post, so the 403 error handling was verified with a simulated response instead. I chose the content of every test post, installed and registered Claude Code on my machine, ran the full acceptance test myself in a new Claude Code session, captured the screenshots and transcript, and handled all git commits and pushes for the repository.

**What AI did that I changed/modified:** The first version of the server used one generic request helper and `httpx`. I had it rewritten to match my Mini Project 1 style, with each tool calling its own endpoint using `requests` and an `if not resp.ok` / `_handle_error()` pattern, and I had the error handler changed to return messages instead of printing them, since stdout is reserved for MCP. When the newest `mcp` package turned out to have renamed `FastMCP`, I pinned the version below 2 to keep the project consistent with the course requirements. I also had the comments and docstrings reworked so they meet PEP 8 and PEP 257 and explain each line in a way that reflects my own understanding of the code. AI also drafted the initial README content, which I reviewed and edited myself.
