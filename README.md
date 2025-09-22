# Vertex AI Network Diagnostics Agent

This project deploys a network diagnostics agent to Vertex AI Agent Engine. The agent is attached to a specific VPC network via Private Service Connect (PSC), allowing you to run network connectivity and DNS resolution tests from *inside* your private Google Cloud environment.

It's a serverless, API-driven way to answer the question: "Can my VPC connect to this internal IP or private DNS name?"

The project consists of three main components:
* `network_diag_agent.py`: The agent code itself. It defines the `get_url_connection_report` tool that performs the actual network test.
* `deploy.py`: The deployment script. It reads configuration from environment variables and deploys the agent to Agent Engine with the specified PSC configuration.
* `query_remote.py`: The client utility. This command-line tool sends one or more URLs to the deployed agent and prints the JSON diagnostic report.

---

## Prerequisites

Before you begin, you must have the following Google Cloud resources set up and available.

1.  **GCP Project:** A Google Cloud project with the **Vertex AI** and **Compute Engine** APIs enabled.
2.  **VPC & Subnet:** A VPC network and a dedicated subnet (e.g., with a `/28` range) in the region where you want to deploy the agent. This subnet will be used exclusively by the PSC Network Attachment.
3.  **Network Attachment:** A Private Service Connect **Network Attachment** configured to use the subnet you just created. The agent will connect to this resource.
4.  **GCS Bucket:** A Google Cloud Storage (GCS) bucket in the same region as your deployment. This is used by Vertex AI for staging the agent code.
5.  **Python:** Python 3.10 or newer with the `venv` module.
6.  **Permissions:** You need IAM roles sufficient to deploy Vertex AI resources and manage Compute Engine network attachments (e.g., `Vertex AI Admin`, `Compute Network Admin`).

---

## Installation and Deployment

Follow these steps to set up your local environment and deploy the agent.

### 1. Clone and Set Up
Clone this repository to your local machine.

```bash
# Clone the repo (replace with your repo URL)
git clone https://your-internal-git-repo/network-diag-agent.git
cd network-diag-agent
```

### 2. Create `requirements.txt`
Create a file named `requirements.txt` with the following content:
```
google-cloud-aiplatform[adk,agent_engines]
pydantic
cloudpickle
requests
```

### 3. Create Python Virtual Environment
Create and activate a Python virtual environment, then install the required libraries.

```bash
# Create the venv
python3 -m venv venv

# Activate the venv
source venv/bin/activate

# Install the requirements
pip install -r requirements.txt
```

### 4. Set Environment Variables
The scripts are configured entirely via environment variables. Set the following in your shell:

**Required:**
```bash
# Your GCP Project ID
export PROJECT_ID="your-project-id"

# The region for deployment (e.g., us-east4)
export LOCATION="us-east4"

# The GCS bucket for staging
export STAGING_BUCKET="gs://your-staging-bucket-name"

# The *full resource path* to your PSC Network Attachment
export AGENT_NETWORK_ATTACHMENT="projects/your-project-id/regions/us-east4/networkAttachments/your-network-attachment-name"
```

**Optional (for DNS Peering):**
If your agent needs to resolve private DNS zones from another VPC, set these variables.
```bash
# The private domain to resolve (e.g., my-internal-zone.com)
export AGENT_PEER_DOMAIN="your.private.domain"

# The project ID of the VPC holding the DNS zone
export AGENT_PEER_PROJECT="dns-host-project-id"

# The network name of the VPC holding the DNS zone
export AGENT_PEER_NETWORK="dns-host-vpc-name"
```

**Optional (Agent Configuration):**
```bash
# Set the requests timeout in seconds (defaults to 5)
export DIAG_TIMEOUT_SECONDS="10"
```

### 5. Deploy the Agent
Run the `deploy.py` script.

```bash
python3 deploy.py
```
You can also run an optional local test before deploying:
```bash
python3 deploy.py --include-local-test
```

### 6. Set the Agent Resource Name
After a successful deployment, the script will output an `export` command. **Copy and run this command** in your terminal. This is required for `query_remote.py` to work.

```bash
# Run the output from the deploy script
export AGENT_RESOURCE_NAME="projects/12345/locations/us-east4/reasoningEngines/67890"
```

---

## How to Use the Agent

Once the agent is deployed and your `AGENT_RESOURCE_NAME` variable is set, you can use `query_remote.py` to run diagnostics.

The script takes one or more URLs (or IPs) as command-line arguments.

### Example 1: Test an internal IP
This will test connectivity to an internal VM or load balancer.

```bash
python3 query_remote.py http://10.150.0.2:8080
```

### Example 2: Test a private DNS name
This will test both private DNS resolution and connectivity.

```bash
python3 query_remote.py http://internal-app.your.private.domain:8080
```

### Example 3: Test a public URL
This will test the agent's egress connectivity.

```bash
python3 query_remote.py https://cloud.google.com
```

### Example 4: Run multiple tests
```bash
python3 query_remote.py http://10.150.0.2:8080 http://internal-app.your.private.domain
```

### Example 5: Debug Mode
To see the full raw event stream from the agent, use the `--debug` flag.

```bash
python3 query_remote.py --debug http://10.150.0.2:8080
```
