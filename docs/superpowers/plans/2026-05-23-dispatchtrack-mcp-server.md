# DispatchTrack MCP Server Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Replace the existing claude-agent FastAPI app with a FastMCP server exposing DispatchTrack delivery data as tools Claude Code can call directly.

**Architecture:** A single `server.py` uses FastMCP's streamable-HTTP transport to serve three read tools at `/mcp`. Railway runs it via `python server.py`. Claude Code connects via its HTTP MCP config pointing at the Railway URL.

**Tech Stack:** Python 3.13, fastmcp, requests, python-dotenv, pytest

---

## File Map

| File | Action | Responsibility |
|---|---|---|
| `server.py` | Create | FastMCP server + all DispatchTrack tools |
| `requirements.txt` | Modify | Trim to fastmcp, requests, python-dotenv |
| `Procfile` | Modify | `web: python server.py` |
| `tests/__init__.py` | Create | Makes tests a package |
| `tests/test_server.py` | Create | Unit tests with mocked HTTP calls |
| `agent.py` | Delete | Replaced by server.py |
| `app.py` | Delete | Replaced by server.py |
| `setup_google_auth.py` | Delete | No longer needed |

---

## Task 1: Clean up old files and update dependencies

**Files:**
- Modify: `requirements.txt`
- Modify: `Procfile`
- Delete: `agent.py`, `app.py`, `setup_google_auth.py`

- [ ] **Step 1: Delete old files**

```bash
cd /Users/kodytownsend/claude-agent
git rm agent.py app.py setup_google_auth.py
```

- [ ] **Step 2: Rewrite requirements.txt**

Replace the entire file with:

```
fastmcp>=2.0.0
requests>=2.31.0
python-dotenv>=1.0.0
pytest>=8.0.0
```

- [ ] **Step 3: Update Procfile**

Replace the entire file with:

```
web: python server.py
```

- [ ] **Step 4: Commit**

```bash
git add requirements.txt Procfile
git commit -m "chore: remove old agent files, slim deps for MCP server"
```

---

## Task 2: Write failing tests

**Files:**
- Create: `tests/__init__.py`
- Create: `tests/test_server.py`

- [ ] **Step 1: Create tests directory and package file**

```bash
mkdir -p tests
touch tests/__init__.py
```

- [ ] **Step 2: Write tests/test_server.py**

```python
import os
os.environ.setdefault("DISPATCHTRACK_BASE_URL", "https://jjvanlines.dispatchtrack.com")
os.environ.setdefault("DISPATCHTRACK_ACCOUNT_CODE", "a18")
os.environ.setdefault("DISPATCHTRACK_API_KEY_JJ", "test-jj-key")
os.environ.setdefault("DISPATCHTRACK_API_KEY_TOWNSEND", "test-townsend-key")

from unittest.mock import patch, MagicMock
import pytest
import server


def _mock_resp(data):
    m = MagicMock()
    m.json.return_value = data
    m.raise_for_status.return_value = None
    return m


class TestSearchDeliveries:
    @patch("server.requests.request")
    def test_returns_formatted_deliveries(self, mock_req):
        mock_req.return_value = _mock_resp([
            {"id": "123", "customer_name": "John Doe", "address": "123 Main St", "status": "pending"}
        ])
        result = server.search_deliveries("jj")
        assert "123" in result
        assert "John Doe" in result
        assert "pending" in result

    @patch("server.requests.request")
    def test_uses_jj_api_key(self, mock_req):
        mock_req.return_value = _mock_resp([])
        server.search_deliveries("jj")
        headers = mock_req.call_args[1]["headers"]
        assert headers["Authorization"] == "Bearer test-jj-key"

    @patch("server.requests.request")
    def test_uses_townsend_api_key(self, mock_req):
        mock_req.return_value = _mock_resp([])
        server.search_deliveries("townsend")
        headers = mock_req.call_args[1]["headers"]
        assert headers["Authorization"] == "Bearer test-townsend-key"

    @patch("server.requests.request")
    def test_empty_returns_no_deliveries_message(self, mock_req):
        mock_req.return_value = _mock_resp([])
        assert server.search_deliveries("jj") == "No deliveries found."

    @patch("server.requests.request")
    def test_passes_date_param(self, mock_req):
        mock_req.return_value = _mock_resp([])
        server.search_deliveries("jj", date="2026-05-23")
        assert mock_req.call_args[1]["params"]["date"] == "2026-05-23"

    @patch("server.requests.request")
    def test_passes_status_param(self, mock_req):
        mock_req.return_value = _mock_resp([])
        server.search_deliveries("jj", status="delivered")
        assert mock_req.call_args[1]["params"]["status"] == "delivered"


class TestGetDelivery:
    @patch("server.requests.request")
    def test_returns_json_string(self, mock_req):
        mock_req.return_value = _mock_resp({"id": "456", "status": "delivered"})
        result = server.get_delivery("jj", "456")
        assert "456" in result
        assert "delivered" in result

    @patch("server.requests.request")
    def test_url_contains_order_id(self, mock_req):
        mock_req.return_value = _mock_resp({})
        server.get_delivery("townsend", "999")
        url = mock_req.call_args[0][1]
        assert "999" in url


class TestGetRoutes:
    @patch("server.requests.request")
    def test_returns_formatted_routes(self, mock_req):
        mock_req.return_value = _mock_resp([
            {"id": "R1", "name": "Route A", "driver_name": "Bob", "stop_count": 5}
        ])
        result = server.get_routes("jj")
        assert "R1" in result
        assert "Bob" in result
        assert "5" in result

    @patch("server.requests.request")
    def test_empty_returns_no_routes_message(self, mock_req):
        mock_req.return_value = _mock_resp([])
        assert server.get_routes("jj") == "No routes found."

    @patch("server.requests.request")
    def test_passes_date_param(self, mock_req):
        mock_req.return_value = _mock_resp([])
        server.get_routes("jj", date="2026-05-24")
        assert mock_req.call_args[1]["params"]["date"] == "2026-05-24"
```

- [ ] **Step 3: Install deps and run tests to verify they fail**

```bash
pip install fastmcp requests python-dotenv pytest
pytest tests/test_server.py -v
```

Expected: `ModuleNotFoundError: No module named 'server'` (server.py doesn't exist yet)

---

## Task 3: Implement server.py

**Files:**
- Create: `server.py`

- [ ] **Step 1: Create server.py**

```python
import os
import json
import requests
from dotenv import load_dotenv
from fastmcp import FastMCP

load_dotenv()

mcp = FastMCP("DispatchTrack")

_BASE_URL = os.environ.get("DISPATCHTRACK_BASE_URL", "https://jjvanlines.dispatchtrack.com")
_ACCOUNT_CODE = os.environ.get("DISPATCHTRACK_ACCOUNT_CODE", "a18")
_API_KEYS = {
    "jj": os.environ.get("DISPATCHTRACK_API_KEY_JJ", ""),
    "townsend": os.environ.get("DISPATCHTRACK_API_KEY_TOWNSEND", ""),
}


def _dt_request(company: str, method: str, endpoint: str, **kwargs) -> dict:
    key = company.lower().strip()
    if key in ("j&j", "j&j van lines", "jj van lines"):
        key = "jj"
    elif key in ("townsend delivery",):
        key = "townsend"
    if key not in _API_KEYS:
        raise ValueError(f"Unknown company '{company}'. Use 'jj' or 'townsend'.")
    url = f"{_BASE_URL}/{_ACCOUNT_CODE}/{endpoint.lstrip('/')}"
    headers = {
        "Authorization": f"Bearer {_API_KEYS[key]}",
        "Accept": "application/json",
        "Content-Type": "application/json",
    }
    resp = requests.request(method, url, headers=headers, timeout=15, **kwargs)
    resp.raise_for_status()
    return resp.json()


@mcp.tool()
def search_deliveries(company: str, date: str = "", status: str = "") -> str:
    """Search deliveries in DispatchTrack.

    Args:
        company: Which account — 'jj' (J&J Van Lines) or 'townsend' (Townsend Delivery).
        date: Filter by delivery date in YYYY-MM-DD format (optional).
        status: Filter by status, e.g. 'delivered', 'pending', 'failed' (optional).
    """
    params = {}
    if date:
        params["date"] = date
    if status:
        params["status"] = status
    data = _dt_request(company, "GET", "orders", params=params)
    orders = data if isinstance(data, list) else data.get("orders", data.get("data", []))
    if not orders:
        return "No deliveries found."
    lines = []
    for o in orders[:25]:
        oid = o.get("id") or o.get("order_number", "?")
        customer = o.get("customer_name") or o.get("name", "?")
        address = o.get("address") or o.get("delivery_address", "?")
        st = o.get("status", "?")
        lines.append(f"ID: {oid} | Customer: {customer} | Address: {address} | Status: {st}")
    return "\n".join(lines)


@mcp.tool()
def get_delivery(company: str, order_id: str) -> str:
    """Get full details for a specific delivery order.

    Args:
        company: Which account — 'jj' or 'townsend'.
        order_id: The order or delivery ID.
    """
    data = _dt_request(company, "GET", f"orders/{order_id}")
    return json.dumps(data, indent=2)


@mcp.tool()
def get_routes(company: str, date: str = "") -> str:
    """Get delivery routes and drivers for a company.

    Args:
        company: Which account — 'jj' or 'townsend'.
        date: Route date in YYYY-MM-DD format (optional, defaults to today).
    """
    params = {}
    if date:
        params["date"] = date
    data = _dt_request(company, "GET", "routes", params=params)
    routes = data if isinstance(data, list) else data.get("routes", data.get("data", []))
    if not routes:
        return "No routes found."
    lines = []
    for r in routes:
        rid = r.get("id") or r.get("route_id", "?")
        name = r.get("name") or r.get("route_name", "?")
        driver = r.get("driver_name") or r.get("driver", "?")
        stops = r.get("stop_count") or len(r.get("stops", []))
        lines.append(f"Route: {rid} | Name: {name} | Driver: {driver} | Stops: {stops}")
    return "\n".join(lines)


if __name__ == "__main__":
    mcp.run(
        transport="streamable-http",
        host="0.0.0.0",
        port=int(os.environ.get("PORT", 8000)),
    )
```

- [ ] **Step 2: Run tests to verify they all pass**

```bash
pytest tests/test_server.py -v
```

Expected output:
```
tests/test_server.py::TestSearchDeliveries::test_returns_formatted_deliveries PASSED
tests/test_server.py::TestSearchDeliveries::test_uses_jj_api_key PASSED
tests/test_server.py::TestSearchDeliveries::test_uses_townsend_api_key PASSED
tests/test_server.py::TestSearchDeliveries::test_empty_returns_no_deliveries_message PASSED
tests/test_server.py::TestSearchDeliveries::test_passes_date_param PASSED
tests/test_server.py::TestSearchDeliveries::test_passes_status_param PASSED
tests/test_server.py::TestGetDelivery::test_returns_json_string PASSED
tests/test_server.py::TestGetDelivery::test_url_contains_order_id PASSED
tests/test_server.py::TestGetRoutes::test_returns_formatted_routes PASSED
tests/test_server.py::TestGetRoutes::test_empty_returns_no_routes_message PASSED
tests/test_server.py::TestGetRoutes::test_passes_date_param PASSED
11 passed in 0.XXs
```

- [ ] **Step 3: Commit**

```bash
git add server.py tests/
git commit -m "feat: DispatchTrack MCP server with search_deliveries, get_delivery, get_routes"
```

---

## Task 4: Set Railway environment variables

- [ ] **Step 1: Set all 4 env vars on Railway via MCP agent**

Use the Railway MCP railway-agent tool to set these variables on service `deac7571-4678-49ce-9fcf-d8f3800f15e5` in environment `02b2abc6-bc45-4863-ab6e-faf126d90401`:

| Variable | Value |
|---|---|
| `DISPATCHTRACK_BASE_URL` | `https://jjvanlines.dispatchtrack.com` |
| `DISPATCHTRACK_ACCOUNT_CODE` | `a18` |
| `DISPATCHTRACK_API_KEY_JJ` | (J&J key from conversation) |
| `DISPATCHTRACK_API_KEY_TOWNSEND` | (Townsend key from conversation) |

---

## Task 5: Deploy to Railway and connect Claude Code

- [ ] **Step 1: Push to GitHub**

```bash
git push origin main
```

- [ ] **Step 2: Verify Railway build succeeds**

Check logs via Railway MCP. Expected final log line:
```
Uvicorn running on http://0.0.0.0:<PORT>
```

- [ ] **Step 3: Add MCP server to Claude Code settings**

Edit `~/.claude/settings.json`. Add the `mcpServers` key (or merge into existing):

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

- [ ] **Step 4: Verify tools load in Claude Code**

Start a new Claude Code session and run `/mcp`. Expected:

```
dispatchtrack
  search_deliveries
  get_delivery
  get_routes
```
