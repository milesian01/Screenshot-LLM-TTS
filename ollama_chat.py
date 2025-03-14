import requests
import json
import sys

# Ensure UTF-8 output on Windows
sys.stdout.reconfigure(encoding='utf-8')

# Ollama server URL
OLLAMA_URL = "http://192.168.50.250:30068/api/chat"

# Define the request payload
payload = {
    "model": "gemma3:27b-it-q8_0",
    "messages": [
        {"role": "user", "content": "Hello, can you respond?"}
    ]
}

# Send request with streaming enabled
response = requests.post(OLLAMA_URL, json=payload, stream=True)

# Process the streamed JSON response line by line
for line in response.iter_lines():
    if line:
        try:
            data = json.loads(line.decode("utf-8"))
            if "message" in data:
                print(data["message"]["content"], end="", flush=True)
        except json.JSONDecodeError:
            pass  # Ignore incomplete JSON fragments

print()  # Print a newline at the end
