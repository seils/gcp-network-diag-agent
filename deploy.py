import sys
import os
import asyncio
import vertexai
import logging
from network_diag_agent import root_agent
from vertexai import agent_engines

# --- Configuration ---
try:
    PROJECT_ID = os.environ["PROJECT_ID"]
    LOCATION = os.environ["LOCATION"] 
    STAGING_BUCKET = os.environ["STAGING_BUCKET"]
    
    # Make PSC config dynamic via environment variables
    AGENT_NETWORK_ATTACHMENT = os.environ["AGENT_NETWORK_ATTACHMENT"]
    
    # Optional DNS Peering Config
    AGENT_PEER_DOMAIN = os.environ.get("AGENT_PEER_DOMAIN")
    AGENT_PEER_PROJECT = os.environ.get("AGENT_PEER_PROJECT")
    AGENT_PEER_NETWORK = os.environ.get("AGENT_PEER_NETWORK")

except KeyError as e:
    print(f"ERROR: Required environment variable {e} is not set.", file=sys.stderr)
    print("Please set: PROJECT_ID, LOCATION, STAGING_BUCKET, AGENT_NETWORK_ATTACHMENT", file=sys.stderr)
    sys.exit(1)

print(f"Configuration: PROJECT_ID={PROJECT_ID}, LOCATION={LOCATION}, STAGING_BUCKET={STAGING_BUCKET}")
print(f"Network Attachment: {AGENT_NETWORK_ATTACHMENT}")

# Agent requirements
AGENT_REQUIREMENTS = [
    "google-cloud-aiplatform[adk,agent_engines]",
    "pydantic",
    "cloudpickle",
    "requests"
]

# --- End Configuration ---


# Initialize the Vertex AI SDK
vertexai.init(
    project=PROJECT_ID,
    location=LOCATION,
    staging_bucket=STAGING_BUCKET,
)

# Wrap the agent in an AdkApp object
app = agent_engines.AdkApp(
    agent=root_agent,
    enable_tracing=True,
)


async def run_local_test(app_instance):
    """Runs a local test of the agent."""
    # Store current level and raise it to WARNING to suppress DEBUG logs
    original_level = logging.getLogger().level
    logging.getLogger().setLevel(logging.WARNING) 

    print("--- Starting Local Agent Test ---")
    
    try:
        session = await app_instance.async_create_session(user_id="u_123")
        print(f"Local Session created: {session.id}")

        events = []
        # FIX: Updated query to match the agent's new instruction
        query_message = "https://httpbin.org/get"
        print(f"\nQuery: {query_message}")
        
        async for event in app_instance.async_stream_query(
            user_id="u_123",
            session_id=session.id,
            message=query_message,
        ):
            events.append(event)

        print("\n--- Full Local Event Stream ---")
        for event in events:
            print(event)

    except Exception as e:
        print(f"\nERROR during local test: {e}", file=sys.stderr)

    finally:
        # Restore the logging level
        logging.getLogger().setLevel(original_level) 
        print("--- Local Test Finished ---")


def build_psc_config():
    """Builds the PSC configuration from environment variables."""
    psc_config = {
        "network_attachment": AGENT_NETWORK_ATTACHMENT
    }
    
    # Dynamically add DNS peering if all variables are set
    if AGENT_PEER_DOMAIN and AGENT_PEER_PROJECT and AGENT_PEER_NETWORK:
        dns_config = {
            "domain": AGENT_PEER_DOMAIN,
            "target_project": AGENT_PEER_PROJECT,
            "target_network": AGENT_PEER_NETWORK
        }
        psc_config["dns_peering_configs"] = [dns_config]
        print(f"Attaching DNS Peering for domain: {AGENT_PEER_DOMAIN}")
    
    return psc_config


if __name__ == "__main__":
    
    # 1. Check for local test flag
    if "--include-local-test" in sys.argv:
        print("Local test flag found. Running local network diagnostic...")
        asyncio.run(run_local_test(app))

    # 2. Build deployment configuration
    print("\n--- Starting Remote Deployment ---")
    
    psc_interface_config = build_psc_config()
    
    # 3. Deployment
    remote_app = agent_engines.create(
        agent_engine=app,
        requirements=AGENT_REQUIREMENTS,
        extra_packages=["network_diag_agent.py"],
        psc_interface_config=psc_interface_config,
    )

    print(f"Deployment finished!")
    print(f"Resource Name: {remote_app.resource_name}")
    print(f"\n💡 To use this agent, run the following command:")
    print(f"export AGENT_RESOURCE_NAME=\"{remote_app.resource_name}\"")
