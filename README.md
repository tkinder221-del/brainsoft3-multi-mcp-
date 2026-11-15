# Brainsoft3 Multi-MCP

Python MCP gateway for multiple upstream MCP servers, deployable on Manufact. **This is a tool gateway, not a standalone LLM chat or autonomous agent.**

## Security model
- All endpoints except `/health` require `Authorization: Bearer <GATEWAY_API_KEY>`.
- HTTPS upstreams only. Upstream URLs and secrets come from environment variables, not source control.
- Discovery is available after authentication; remote execution is disabled by default.
- Tool calls require both `ALLOW_REMOTE_CALLS=true` and an exact `ALLOWED_REMOTE_TOOLS` allowlist.
- Treat upstream MCP output as untrusted. Do not enable destructive tools without approval.
- Keep GitHub tokens, Context7 keys and Prompts.chat keys in Manufact secrets; rotate previously exposed keys.

## Manufact deployment
1. Connect the GitHub repository `tkinder221-del/brainsoft3-multi-mcp-` to Manufact.
2. Build with the included Dockerfile; container port **8000**. The start command is `python server.py`.
3. Set `GATEWAY_API_KEY` to a long random value in Manufact environment settings **before deploying**.
4. Set `MCP_SERVERS_JSON` to a JSON object of named upstreams. Start with `{}` for a safe first deployment.
5. Deploy. Test `/health` and then the MCP endpoint `/mcp` using an authenticated MCP client.
6. Add upstream connections one by one; never paste keys into chat or GitHub.

Example Manufact environment variables (placeholders only):

```text
GATEWAY_API_KEY=<random secret>
PORT=8000
MCP_SERVERS_JSON={"prompts":{"url":"https://prompts.brainsoft3.dpdns.org/api/mcp?users=brainsoft3admin","auth_env":"PROMPTS_API_KEY","auth_header":"x-api-key"}}
PROMPTS_API_KEY=<new rotated secret>
ALLOW_REMOTE_CALLS=false
ALLOWED_REMOTE_TOOLS=
```

## Tools
- `list_connected_servers` — configured aliases
- `list_remote_tools(server)` — upstream discovery
- `call_remote_tool(server, tool, arguments)` — allowlisted calls, disabled by default

## Local development
```bash
python -m venv .venv
pip install -r requirements.txt
export GATEWAY_API_KEY=local-development-only-secret
export MCP_SERVERS_JSON='{}'
python server.py
```

## Scope
GitHub and Context7 are **not** automatically connected just because they are mentioned here. Add a compatible MCP endpoint and its credentials after verifying availability and access. The existing Brainsoft3 Prompts.chat endpoint is a candidate; its actual availability must be tested separately.

## Limitations
The gateway currently handles streamable HTTP upstreams and lists the first page of tools. It does not provide an LLM, multi-agent scheduling, OAuth, audit trails, per-user permissions, or rate limiting. For production, use an access proxy, monitoring, secret rotation, and restrict access to trusted clients.
