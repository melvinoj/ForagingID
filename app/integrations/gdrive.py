"""
Google Drive sync via the Drive MCP server.

Uploads CHANGELOG.md to a 'ForagingID' folder in the root of Google Drive.

MCP endpoint : https://drivemcp.googleapis.com/mcp/v1
Auth         : OAuth2 Bearer token (stored in the 'gdrive_access_token' setting)
Drive scope  : https://www.googleapis.com/auth/drive.file

Tool calls used (standard Drive MCP):
  search_files  — locate existing folder / file by Drive query syntax
  create_file   — create a new folder or file (with content)
  update_file   — overwrite file content in-place

All public functions are async and raise GDriveError on any failure so the
caller can wrap with try/except and surface a readable message without crashing.
"""

import json
import logging
from pathlib import Path
from typing import Any, Dict, Optional

import httpx

MCP_URL     = "https://drivemcp.googleapis.com/mcp/v1"
FOLDER_NAME = "ForagingID"
FILE_NAME   = "CHANGELOG.md"
TIMEOUT_S   = 30

log = logging.getLogger(__name__)

_CHANGELOG_PATH = Path(__file__).parent.parent.parent / "CHANGELOG.md"


# ---------------------------------------------------------------------------
# Error type
# ---------------------------------------------------------------------------

class GDriveError(Exception):
    """Raised when any step of the Google Drive MCP sync fails."""


# ---------------------------------------------------------------------------
# Low-level MCP call
# ---------------------------------------------------------------------------

async def _mcp_call(tool: str, args: Dict[str, Any], token: str) -> Dict:
    """
    Issue a single tools/call request to the Drive MCP server.

    The MCP JSON-RPC response wraps tool output as:
        { "result": { "content": [{"type": "text", "text": "<json-string>"}] } }

    We parse the first text item as JSON and return it; if it isn't JSON we
    return {"raw": "<text>"}.  On any error we raise GDriveError.
    """
    payload = {
        "jsonrpc": "2.0",
        "method":  "tools/call",
        "id":      1,
        "params":  {"name": tool, "arguments": args},
    }
    headers = {
        "Authorization": f"Bearer {token}",
        "Content-Type":  "application/json",
        "Accept":        "application/json",
    }

    try:
        async with httpx.AsyncClient(timeout=TIMEOUT_S) as client:
            resp = await client.post(MCP_URL, json=payload, headers=headers)
    except httpx.ConnectError as exc:
        raise GDriveError(f"Cannot reach Drive MCP ({MCP_URL}): {exc}") from exc
    except httpx.TimeoutException:
        raise GDriveError(f"Drive MCP timed out after {TIMEOUT_S}s")

    if resp.status_code == 401:
        raise GDriveError(
            "Drive token expired or invalid — update it in Settings → Google Drive"
        )
    if resp.status_code == 403:
        raise GDriveError(
            "Drive access denied — check token scopes (needs drive.file)"
        )
    resp.raise_for_status()

    data = resp.json()
    if "error" in data:
        err = data["error"]
        raise GDriveError(
            f"MCP error {err.get('code', '')}: {err.get('message', err)}"
        )

    # Unwrap MCP content envelope
    result   = data.get("result", {})
    contents = result.get("content", [])
    for item in contents:
        if item.get("type") == "text":
            try:
                return json.loads(item["text"])
            except (json.JSONDecodeError, KeyError):
                return {"raw": item.get("text", "")}

    return result  # fallback — return raw result dict


# ---------------------------------------------------------------------------
# Folder helpers
# ---------------------------------------------------------------------------

async def _get_or_create_folder(token: str) -> str:
    """Return the ForagingID folder ID, creating it at Drive root if absent."""
    search = await _mcp_call("search_files", {
        "query": (
            f"name='{FOLDER_NAME}'"
            " and mimeType='application/vnd.google-apps.folder'"
            " and 'root' in parents"
            " and trashed=false"
        ),
        "fields": "files(id,name)",
    }, token)

    files = search.get("files", [])
    if files:
        fid = files[0]["id"]
        log.debug("gdrive: found folder '%s' (%s)", FOLDER_NAME, fid)
        return fid

    create = await _mcp_call("create_file", {
        "name":     FOLDER_NAME,
        "mimeType": "application/vnd.google-apps.folder",
        "parents":  ["root"],
    }, token)
    fid = create.get("id")
    if not fid:
        raise GDriveError(
            f"create_file (folder) returned no 'id': {create}"
        )
    log.info("gdrive: created folder '%s' (%s)", FOLDER_NAME, fid)
    return fid


async def _find_file(folder_id: str, token: str) -> Optional[str]:
    """Return the CHANGELOG.md file ID inside folder_id, or None."""
    result = await _mcp_call("search_files", {
        "query": (
            f"name='{FILE_NAME}'"
            f" and '{folder_id}' in parents"
            " and trashed=false"
        ),
        "fields": "files(id,name)",
    }, token)
    files = result.get("files", [])
    return files[0]["id"] if files else None


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

