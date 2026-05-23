import os
import json
import requests
from dotenv import load_dotenv
from fastmcp import FastMCP

load_dotenv()

# Module-level config constants
_BASE_URL = os.environ.get("DISPATCHTRACK_BASE_URL", "https://jjvanlines.dispatchtrack.com")
_ACCOUNT_CODE = os.environ.get("DISPATCHTRACK_ACCOUNT_CODE", "a18")
_API_KEYS = {
    "jj": os.environ.get("DISPATCHTRACK_API_KEY_JJ", ""),
    "townsend": os.environ.get("DISPATCHTRACK_API_KEY_TOWNSEND", ""),
}

mcp = FastMCP("DispatchTrack")

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
