# DispatchTrack MCP Server Design

**Date:** 2026-05-23  
**Repo:** kody-lang/claude-agent  
**Deployed at:** https://claude-agent-production-0a70.up.railway.app

---

## Goal

Expose DispatchTrack delivery data as an MCP server so Claude Code can query it directly. Later phases will add write tools and a Slack/email automation agent.

---

## Architecture

```
Claude Code ──MCP over HTTP──► Railway MCP Server ──REST──► DispatchTrack (jjvanlines.dispatchtrack.com)
```

The `claude-agent` Railway service is rewritten from a generic AI agent into a focused MCP server using `fastmcp`. No Anthropic API key required on Railway.

---

## DispatchTrack API

- **Base URL:** `https://jjvanlines.dispatchtrack.com`
- **Account path:** `/a18/`
- **Auth:** `Authorization: Bearer <api_key>` (per-company key)
- **Companies:**
  - `jj` — J&J Van Lines (main account)
  - `townsend` — Townsend Delivery (sub-account, same path, different API key)

---

## MCP Tools (Phase 1 — Read Only)

| Tool | Parameters | Description |
|---|---|---|
| `search_deliveries` | `company`, `date?`, `status?` | List deliveries, optionally filtered |
| `get_delivery` | `company`, `order_id` | Full details for a specific order |
| `get_routes` | `company`, `date?` | List routes and drivers for a day |

All tools accept `company` as either `"jj"` or `"townsend"`.

---

## Files Changed

| File | Change |
|---|---|
| `server.py` | New — fastmcp MCP server (replaces agent.py + app.py) |
| `requirements.txt` | Trimmed to: `fastmcp`, `requests`, `python-dotenv` |
| `Procfile` | Updated start command for fastmcp |
| `agent.py` | Deleted |
| `app.py` | Deleted |
| `setup_google_auth.py` | Deleted |

---

## Environment Variables (Railway)

| Variable | Value |
|---|---|
| `DISPATCHTRACK_BASE_URL` | `https://jjvanlines.dispatchtrack.com` |
| `DISPATCHTRACK_ACCOUNT_CODE` | `a18` |
| `DISPATCHTRACK_API_KEY_JJ` | (J&J API key) |
| `DISPATCHTRACK_API_KEY_TOWNSEND` | (Townsend API key) |

---

## Claude Code Integration

Add to `~/.claude/settings.json`:

```json
{
  "mcpServers": {
    "dispatchtrack": {
      "type": "http",
      "url": "https://claude-agent-production-0a70.up.railway.app/mcp"
    }
  }
}
```

---

## Future Phases

- **Phase 2:** Write tools — `update_delivery_status`, `create_order`
- **Phase 3:** Email ingestion agent — parse delivery emails → create/update DispatchTrack orders → post to Slack
