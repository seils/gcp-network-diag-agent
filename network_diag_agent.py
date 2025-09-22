import sys
import logging
import os  # <-- THE MISSING IMPORT
import requests
from google.adk.agents import Agent
from urllib.parse import urlparse
import socket

# A default User-Agent is a good practice
USER_AGENT = "gcp-network-diag-agent/1.0"
DEFAULT_TIMEOUT = 5


def get_url_connection_report(url: str) -> dict:
    """Sends a GET request to a URL and returns a structured report for debugging, 
    including DNS, timing, and redirect information.

    Args:
        url (str): The URL to send the GET request to.

    Returns:
        dict: A structured dictionary containing diagnostic information.
    """
    
    try:
        timeout_seconds = int(os.environ.get("DIAG_TIMEOUT_SECONDS", DEFAULT_TIMEOUT))
    except ValueError:
        timeout_seconds = DEFAULT_TIMEOUT

    report = {
        "url": url,
        "status": "error",
        "error_message": "",
        "status_code": None,
        "final_url": None,
        "headers": {},
        "content_preview": "REMOVED",
        "ip_addresses": [],
        "response_time_seconds": None,
        "redirect_history": [],
    }

    # --- 1. DNS Lookup Step ---
    try:
        parsed_url = urlparse(url)
        hostname = parsed_url.hostname
        if not hostname:
            raise ValueError("Could not parse hostname from URL")
        
        port = parsed_url.port or 443
        info = socket.getaddrinfo(hostname, port, family=socket.AF_INET)
        report["ip_addresses"] = list(set([item[4][0] for item in info]))
    except (socket.gaierror, ValueError, TypeError) as e:
        # These are expected errors if DNS fails or URL is bad,
        # we can pass and let the main requests.get() handle it.
        pass
    # --- END DNS Step ---

    # --- 2. Main Request Step ---
    try:
        response = requests.get(
            url,
            timeout=timeout_seconds,
            allow_redirects=True,
            headers={"User-Agent": USER_AGENT}
        )
        
        report.update({
            "status": "success",
            "status_code": response.status_code,
            "final_url": response.url,
            "headers": dict(response.headers),
            "response_time_seconds": response.elapsed.total_seconds(),
            "redirect_history": [(r.status_code, r.url) for r in response.history],
        })

    # --- 3. Exception Handling (with server-side fix) ---
    except requests.exceptions.Timeout:
        report["error_message"] = f"Request timed out after {timeout_seconds} seconds. Timeout set to {timeout_seconds}s."
    except requests.exceptions.ConnectionError as e:
        error_details = str(e).replace("'", '"')
        report["error_message"] = f"Connection error occurred (DNS/Firewall/Route). Details: {error_details}"
    except requests.exceptions.RequestException as e:
        error_details = str(e).replace("'", '"')
        report["error_message"] = f"An unexpected request error occurred. Details: {error_details}"
    except Exception as e:
        # This is the main catch-all
        error_details = str(e).replace("'", '"')
        report["error_message"] = f"A general exception occurred. Details: {error_details}"
    # --- END MODIFICATIONS ---

    return report


# Define the Agent
root_agent = Agent(
    name="network_diag_agent",
    model="gemini-2.0-flash",
    description=(
        "An agent for diagnosing network connectivity issues by performing HTTP GET requests "
        "and providing a structured, clean debugging report."
    ),
    instruction=(
        "You are a simple API. The user will provide a URL as their query. "
        "You MUST NOT respond with any text. "
        "You MUST call the `get_url_connection_report` tool using the exact URL provided by the user. "
        "Your final response MUST be ONLY the raw JSON dictionary returned by that tool."
    ),
    tools=[get_url_connection_report],
)
