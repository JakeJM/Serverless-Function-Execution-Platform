import os
import json
import time

# Get the payload from environment variable
payload = json.loads(os.getenv("PAYLOAD", "{}"))

# Log some basic stats for testing metrics
start_time = time.time()
for i in range(1000000):  # Create some CPU load
    pass
execution_time = time.time() - start_time

# Format response with metrics info
response = {
    "message": "Function executed successfully",
    "received_payload": payload,
    "execution_info": {
        "execution_time_sec": execution_time,
        "timestamp": time.time(),
    }
}

# Return response as JSON string
print(json.dumps(response)) 