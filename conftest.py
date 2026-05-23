import os

# Force test values before any test module imports server.
# These override real env vars so tests are isolated from production credentials.
os.environ["DISPATCHTRACK_BASE_URL"] = "https://jjvanlines.dispatchtrack.com"
os.environ["DISPATCHTRACK_ACCOUNT_CODE"] = "a18"
os.environ["DISPATCHTRACK_API_KEY_JJ"] = "test-jj-key"
os.environ["DISPATCHTRACK_API_KEY_TOWNSEND"] = "test-townsend-key"
