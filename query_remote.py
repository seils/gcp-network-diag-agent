import sys
import os 
import asyncio
import vertexai
import json 
from vertexai import agent_engines

# --- Configuration ---
try:
    PROJECT_ID = os.environ["PROJECT_ID"]
    LOCATION = os.environ["LOCATION"]
    AGENT_RESOURCE_NAME = os.environ["AGENT_RESOURCE_NAME"] 
except KeyError as e:
    print(f"ERROR: Required environment variable {e} is not set.", file=sys.stderr)
    print("Please set: PROJECT_ID, LOCATION, AGENT_RESOURCE_NAME", file=sys.stderr)
    sys.exit(1)

# Check for --debug flag
DEBUG_MODE = "--debug" in sys.argv

# --- Parse URLs from command line ---
urls_to_test = [arg for arg in sys.argv[1:] if not arg.startswith('--')]

if not urls_to_test:
    print("Usage: python3 query_remote.py [--debug] <url1> [url2] ...", file=sys.stderr)
    sys.exit(1)

print(f"Configuration: PROJECT_ID={PROJECT_ID}, LOCATION={LOCATION}")
print(f"Agent Resource Name: {AGENT_RESOURCE_NAME}")
if DEBUG_MODE:
    print("\n--- DEBUG MODE ENABLED ---")
    print("The full, raw event stream will be printed for each query.")
# --- End Configuration ---


# Initialize the Vertex AI SDK
vertexai.init(
    project=PROJECT_ID,
    location=LOCATION,
)

# 1. Get a reference to the deployed agent
try:
    remote_app = agent_engines.get(AGENT_RESOURCE_NAME)
except Exception as e:
    print(f"Error getting remote agent: {e}", file=sys.stderr)
    print("Ensure AGENT_RESOURCE_NAME is correct and the agent is deployed.", file=sys.stderr)
    sys.exit(1)


async def main():
    # 2. Create a new session
    session = await remote_app.async_create_session(user_id="u_remote_user")
    session_id = session['id'] 
    
    print("--- Starting Network Diagnostic Queries ---")
    print(f"Session ID: {session_id}") 
    print(f"URLs to test: {len(urls_to_test)}\n")

    # 3. Loop through the list of URLs and stream the query for each
    for url in urls_to_test:
        print(f"--- QUERYING: {url} ---")
        
        # We send *only* the URL, matching the agent instruction.
        query_message = url
        
        events = []
        try:
            async for event in remote_app.async_stream_query(
                user_id="u_remote_user",
                session_id=session_id,
                message=query_message,
            ):
                events.append(event)
        except Exception as e:
            print(f"An error occurred during query stream for {url}: {e}", file=sys.stderr)
            print("-" * 30 + "\n")
            continue

        if DEBUG_MODE:
            print("\n--- [DEBUG] RAW AGENT EVENT STREAM ---")
            try:
                print(json.dumps(events, indent=2))
            except TypeError as te:
                print(f"Could not JSON-serialize events, printing raw list: {te}", file=sys.stderr)
                print(events)
            print("--- [DEBUG] END RAW EVENT STREAM ---\n")

        # Find the final text response from the model
        final_text_responses = [
            e for e in events
            if e.get("content", {}).get("parts", [{}])[0].get("text")
            and not e.get("content", {}).get("parts", [{}])[0].get("function_call")
        ]
        
        if final_text_responses:
            response_text = final_text_responses[0]["content"]["parts"][0]["text"].strip()
            
            try:
                # Remove Markdown code fences
                if response_text.startswith("```"):
                    lines = response_text.split('\n')
                    clean_text = '\n'.join(lines[1:-1]).strip()
                else:
                    clean_text = response_text

                response_json = json.loads(clean_text)
                
                # Extract the inner dictionary, handling the LLM's single-key wrapper
                if isinstance(response_json, dict) and len(response_json) == 1:
                    final_report = next(iter(response_json.values()))
                else:
                    final_report = response_json

                # Remove the 'content_preview' key
                if isinstance(final_report, dict):
                    if "content_preview" in final_report: 
                        del final_report["content_preview"]
                
                # Print the final, cleaned JSON
                print(json.dumps(final_report, indent=2))
                
            except (json.JSONDecodeError, KeyError, TypeError) as e:
                print(f"Error parsing agent response as JSON: {e}", file=sys.stderr)
                print(f"Raw Text (for error context): {response_text}", file=sys.stderr)
                
        else:
            if not DEBUG_MODE:
                print("No final text response found in the event stream.")
            
        print("-" * 30 + "\n") # Separator for clarity

if __name__ == "__main__":
    asyncio.run(main())
