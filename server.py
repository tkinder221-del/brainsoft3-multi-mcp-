"""Brainsoft3 Multi-MCP gateway: authenticated, allowlisted remote MCP access."""
import json
import logging
import os
import secrets
from contextlib import asynccontextmanager

import uvicorn
from mcp import ClientSession
from mcp.client.streamable_http import streamablehttp_client
from mcp.server.fastmcp import FastMCP
from starlette.responses import JSONResponse, PlainTextResponse

logging.basicConfig(level=logging.INFO)
log = logging.getLogger("brainsoft3")
PORT = int(os.getenv("PORT", "8000"))
mcp = FastMCP("Brainsoft3 Multi-MCP", host="0.0.0.0", port=PORT, stateless_http=True, json_response=True)


def config():
    raw = os.getenv("MCP_SERVERS_JSON", "{}")
    servers = json.loads(raw)
    if not isinstance(servers, dict):
        raise ValueError("MCP_SERVERS_JSON must be a JSON object")
    for alias, spec in servers.items():
        if not isinstance(spec, dict) or not str(spec.get("url", "")).startswith("https://"):
            raise ValueError(f"Server {alias}: HTTPS url required")
    return servers


def allowed_names():
    return {x.strip() for x in os.getenv("ALLOWED_REMOTE_TOOLS", "").split(",") if x.strip()}


@asynccontextmanager
async def remote_session(alias: str):
    spec = config().get(alias)
    if not spec:
        raise ValueError("Unknown server alias")
    headers = {}
    env_name = spec.get("auth_env")
    if env_name:
        token = os.getenv(env_name, "")
        if not token:
            raise ValueError(f"Missing configured credential: {env_name}")
        header = spec.get("auth_header", "Authorization")
        headers[header] = f"Bearer {token}" if header.lower() == "authorization" else token
    async with streamablehttp_client(spec["url"], headers=headers, timeout=20) as (read, write, _):
        async with ClientSession(read, write) as session:
            await session.initialize()
            yield session


@mcp.tool()
async def list_connected_servers() -> list[str]:
    """List configured upstream MCP aliases (no credentials are returned)."""
    return sorted(config().keys())


@mcp.tool()
async def list_remote_tools(server: str) -> list[dict]:
    """Discover tools of one configured upstream MCP server."""
    async with remote_session(server) as session:
        result = await session.list_tools()
        return [{"name": t.name, "description": t.description or ""} for t in result.tools]


@mcp.tool()
async def call_remote_tool(server: str, tool: str, arguments: dict | None = None) -> dict:
    """Call an explicitly allowlisted upstream tool; disabled by default."""
    if os.getenv("ALLOW_REMOTE_CALLS", "false").lower() != "true":
        raise ValueError("Remote calls disabled: set ALLOW_REMOTE_CALLS=true after review")
    if tool not in allowed_names():
        raise ValueError("Tool not in ALLOWED_REMOTE_TOOLS")
    async with remote_session(server) as session:
        listed = await session.list_tools()
        if tool not in {t.name for t in listed.tools}:
            raise ValueError("Upstream tool not found")
        response = await session.call_tool(tool, arguments or {})
        return response.model_dump(mode="json")


class AuthenticatedGateway:
    """ASGI wrapper: protect /mcp and /inspector; expose only unauthenticated health."""
    def __init__(self, app):
        self.app = app

    async def __call__(self, scope, receive, send):
        if scope["type"] == "http":
            path = scope.get("path", "")
            if path == "/health":
                await JSONResponse({"status": "ok", "service": "brainsoft3-multi-mcp"})(scope, receive, send)
                return
            key = os.getenv("GATEWAY_API_KEY", "")
            headers = dict(scope.get("headers", []))
            auth = headers.get(b"authorization", b"").decode("utf-8", "replace")
            if not key or not secrets.compare_digest(auth, f"Bearer {key}"):
                await PlainTextResponse("Unauthorized", status_code=401)(scope, receive, send)
                return
        await self.app(scope, receive, send)


if __name__ == "__main__":
    # Validate at boot: fail closed on invalid server definitions or missing gateway key.
    config()
    if not os.getenv("GATEWAY_API_KEY"):
        raise SystemExit("GATEWAY_API_KEY must be configured")
    app = AuthenticatedGateway(mcp.streamable_http_app())
    uvicorn.run(app, host="0.0.0.0", port=PORT, log_level="info")
