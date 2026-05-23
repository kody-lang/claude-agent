import os
import base64
from email.mime.text import MIMEText
from dotenv import load_dotenv
import anthropic
from anthropic import beta_tool

load_dotenv()

client = anthropic.Anthropic(api_key=os.environ["ANTHROPIC_API_KEY"])

# ── Google credentials (loaded once, auto-refreshed) ──────────────────────────

_google_creds = None

def _get_google_creds():
    global _google_creds
    from google.oauth2.credentials import Credentials
    from google.auth.transport.requests import Request

    SCOPES = [
        "https://www.googleapis.com/auth/gmail.send",
        "https://www.googleapis.com/auth/gmail.readonly",
        "https://www.googleapis.com/auth/documents.readonly",
    ]

    if _google_creds is None:
        _google_creds = Credentials.from_authorized_user_file(
            os.environ["GOOGLE_TOKEN_PATH"], SCOPES
        )

    if _google_creds.expired and _google_creds.refresh_token:
        _google_creds.refresh(Request())

    return _google_creds


# ── DispatchTrack credentials + request helper ────────────────────────────────

_DT_COMPANIES = {
    "townsend": ("DISPATCHTRACK_API_KEY_TOWNSEND", "DISPATCHTRACK_ACCOUNT_CODE_TOWNSEND"),
    "jj":       ("DISPATCHTRACK_API_KEY_JJ",       "DISPATCHTRACK_ACCOUNT_CODE_JJ"),
}

def _dt_creds(company: str) -> tuple[str, str]:
    key = company.lower().strip()
    # accept common aliases
    if key in ("townsend delivery", "townsend"):
        key = "townsend"
    elif key in ("j&j", "j&j van lines", "jj van lines", "jj"):
        key = "jj"
    if key not in _DT_COMPANIES:
        raise ValueError(f"Unknown company '{company}'. Use 'townsend' or 'jj'.")
    api_var, code_var = _DT_COMPANIES[key]
    return os.environ[api_var], os.environ[code_var]


def _dt_request(company: str, method: str, endpoint: str, **kwargs) -> dict:
    import requests
    from urllib.parse import quote

    api_key, account_code = _dt_creds(company)
    base = os.environ.get("DISPATCHTRACK_BASE_URL", "https://www.dispatchtrack.com/apiv2")
    encoded = quote(account_code, safe="")
    url = f"{base}/{encoded}/{endpoint.lstrip('/')}"
    headers = {
        "Authorization": f"Bearer {api_key}",
        "Accept": "application/json",
        "Content-Type": "application/json",
    }
    resp = requests.request(method, url, headers=headers, timeout=15, **kwargs)
    resp.raise_for_status()
    return resp.json()


# ── Tools ──────────────────────────────────────────────────────────────────────

@beta_tool
def search_web(query: str) -> str:
    """Search the web for up-to-date information.

    Args:
        query: The search query string.
    """
    from tavily import TavilyClient

    tavily = TavilyClient(api_key=os.environ["TAVILY_API_KEY"])
    results = tavily.search(query=query, max_results=5)
    return "\n---\n".join(
        f"Title: {r['title']}\nURL: {r['url']}\nSummary: {r['content']}"
        for r in results["results"]
    )


@beta_tool
def read_file(file_path: str) -> str:
    """Read the text content of a local file.

    Args:
        file_path: Path to the file to read.
    """
    with open(file_path, "r", encoding="utf-8") as f:
        return f.read()


@beta_tool
def read_emails(max_results: int = 10, query: str = "") -> str:
    """Read emails from Gmail.

    Args:
        max_results: Maximum number of emails to fetch.
        query: Optional Gmail search query (e.g. 'is:unread from:boss@example.com').
    """
    from googleapiclient.discovery import build

    service = build("gmail", "v1", credentials=_get_google_creds())
    result = (
        service.users()
        .messages()
        .list(userId="me", maxResults=max_results, q=query)
        .execute()
    )

    messages = result.get("messages", [])
    if not messages:
        return "No emails found."

    output = []
    for ref in messages:
        msg = (
            service.users()
            .messages()
            .get(userId="me", id=ref["id"], format="full")
            .execute()
        )
        headers = {h["name"]: h["value"] for h in msg["payload"]["headers"]}
        subject = headers.get("Subject", "(no subject)")
        sender = headers.get("From", "unknown")
        date = headers.get("Date", "unknown")

        body = ""
        payload = msg["payload"]
        if "parts" in payload:
            for part in payload["parts"]:
                if part["mimeType"] == "text/plain":
                    data = part.get("body", {}).get("data", "")
                    if data:
                        body = base64.urlsafe_b64decode(data).decode("utf-8", errors="replace")
                        break
        elif "data" in payload.get("body", {}):
            body = base64.urlsafe_b64decode(payload["body"]["data"]).decode(
                "utf-8", errors="replace"
            )

        output.append(
            f"From: {sender}\nDate: {date}\nSubject: {subject}\n\n{body[:800]}"
        )

    return "\n\n═══\n\n".join(output)


@beta_tool
def send_email(to: str, subject: str, body: str) -> str:
    """Send an email via Gmail.

    Args:
        to: Recipient email address.
        subject: Email subject line.
        body: Plain-text email body.
    """
    from googleapiclient.discovery import build

    service = build("gmail", "v1", credentials=_get_google_creds())
    msg = MIMEText(body)
    msg["to"] = to
    msg["subject"] = subject
    raw = base64.urlsafe_b64encode(msg.as_bytes()).decode()
    service.users().messages().send(userId="me", body={"raw": raw}).execute()
    return f"Email sent to {to}."


@beta_tool
def read_google_doc(document_id: str) -> str:
    """Read the full text content of a Google Doc.

    Args:
        document_id: The document ID from the Google Docs URL
                     (the long string between /d/ and /edit).
    """
    from googleapiclient.discovery import build

    service = build("docs", "v1", credentials=_get_google_creds())
    doc = service.documents().get(documentId=document_id).execute()

    parts = []
    for element in doc.get("body", {}).get("content", []):
        if "paragraph" in element:
            for run in element["paragraph"].get("elements", []):
                if "textRun" in run:
                    parts.append(run["textRun"]["content"])

    return "".join(parts)


@beta_tool
def send_slack_message(channel: str, message: str) -> str:
    """Send a message to a Slack channel or user.

    Args:
        channel: Channel name (e.g. '#general') or a user ID (e.g. 'U012AB3CD').
        message: The message text to send.
    """
    from slack_sdk import WebClient

    slack = WebClient(token=os.environ["SLACK_BOT_TOKEN"])
    result = slack.chat_postMessage(channel=channel, text=message)
    return f"Slack message sent to {channel} (ts: {result['ts']})."


@beta_tool
def send_sms(to_number: str, message: str) -> str:
    """Send an SMS text message via Twilio.

    Args:
        to_number: Recipient phone number in E.164 format (e.g. +15551234567).
        message: The text message body (max 1600 characters).
    """
    from twilio.rest import Client

    twilio = Client(os.environ["TWILIO_ACCOUNT_SID"], os.environ["TWILIO_AUTH_TOKEN"])
    msg = twilio.messages.create(
        body=message,
        from_=os.environ["TWILIO_FROM_NUMBER"],
        to=to_number,
    )
    return f"SMS sent to {to_number} (SID: {msg.sid})."


@beta_tool
def route_message(
    content: str,
    urgency: str,
    recipient_name: str,
    recipient_email: str = "",
    recipient_phone: str = "",
    slack_channel: str = "",
) -> str:
    """Route a message to the right channel(s) based on urgency.

    - high   → SMS (if phone) + Slack (if channel) + email (if address)
    - medium → Slack (if channel) + email (if address)
    - low    → email only

    Args:
        content: The message to deliver.
        urgency: One of 'high', 'medium', or 'low'.
        recipient_name: Display name used in the email subject.
        recipient_email: Recipient email address (optional).
        recipient_phone: Recipient phone in E.164 format (optional).
        slack_channel: Slack channel name or user ID (optional).
    """
    sent = []

    if urgency == "high" and recipient_phone:
        sent.append(send_sms(to_number=recipient_phone, message=f"URGENT: {content}"))

    if urgency in ("high", "medium") and slack_channel:
        sent.append(send_slack_message(channel=slack_channel, message=content))

    if recipient_email:
        sent.append(
            send_email(
                to=recipient_email,
                subject=f"Message for {recipient_name}",
                body=content,
            )
        )

    return "\n".join(sent) if sent else "No delivery channels provided — supply at least one of: recipient_email, recipient_phone, slack_channel."


# ── DispatchTrack tools ───────────────────────────────────────────────────────

@beta_tool
def search_deliveries(company: str, date: str = "", status: str = "") -> str:
    """Search deliveries in DispatchTrack for a given company.

    Args:
        company: Which account to query — 'townsend' or 'jj'.
        date: Delivery date in YYYY-MM-DD format (optional, defaults to today).
        status: Filter by status (optional, e.g. 'delivered', 'pending', 'failed').
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
        oid      = o.get("id") or o.get("order_number") or "?"
        customer = o.get("customer_name") or o.get("name", "?")
        address  = o.get("address") or o.get("delivery_address", "?")
        st       = o.get("status", "?")
        lines.append(f"ID: {oid} | Customer: {customer} | Address: {address} | Status: {st}")

    return "\n".join(lines)


@beta_tool
def get_delivery(company: str, order_id: str) -> str:
    """Get full details for a specific delivery in DispatchTrack.

    Args:
        company: Which account to query — 'townsend' or 'jj'.
        order_id: The order or delivery ID.
    """
    import json
    data = _dt_request(company, "GET", f"orders/{order_id}")
    return json.dumps(data, indent=2)


@beta_tool
def get_routes(company: str, date: str = "") -> str:
    """Get delivery routes for a company in DispatchTrack.

    Args:
        company: Which account to query — 'townsend' or 'jj'.
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
        rid    = r.get("id") or r.get("route_id", "?")
        name   = r.get("name") or r.get("route_name", "?")
        driver = r.get("driver_name") or r.get("driver", "?")
        stops  = r.get("stop_count") or len(r.get("stops", []))
        lines.append(f"Route: {rid} | Name: {name} | Driver: {driver} | Stops: {stops}")

    return "\n".join(lines)


@beta_tool
def update_delivery_status(company: str, order_id: str, status: str, notes: str = "") -> str:
    """Update the status of a delivery in DispatchTrack.

    Args:
        company: Which account to update — 'townsend' or 'jj'.
        order_id: The order or delivery ID.
        status: New status (e.g. 'delivered', 'failed', 'rescheduled').
        notes: Optional reason or notes for the status change.
    """
    payload: dict = {"status": status}
    if notes:
        payload["notes"] = notes
    _dt_request(company, "PATCH", f"orders/{order_id}", json=payload)
    return f"Order {order_id} updated to '{status}'."


# ── Agent ──────────────────────────────────────────────────────────────────────

TOOLS = [
    search_web,
    read_file,
    read_emails,
    send_email,
    read_google_doc,
    send_slack_message,
    send_sms,
    route_message,
    # DispatchTrack — both companies via 'townsend' or 'jj' parameter
    search_deliveries,
    get_delivery,
    get_routes,
    update_delivery_status,
]


def run_agent(user_message: str) -> str:
    runner = client.beta.messages.tool_runner(
        model="claude-opus-4-7",
        max_tokens=16000,
        thinking={"type": "adaptive"},
        tools=TOOLS,
        messages=[{"role": "user", "content": user_message}],
    )

    final = None
    for message in runner:
        final = message

    if final:
        for block in final.content:
            if hasattr(block, "text") and block.text:
                return block.text

    return "(no response)"


if __name__ == "__main__":
    import sys

    prompt = " ".join(sys.argv[1:]) if len(sys.argv) > 1 else input("You: ")
    print(run_agent(prompt))
