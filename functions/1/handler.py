import os
import json
payload = json.loads(os.getenv("PAYLOAD", "{}"))
print(f"Hello World, received: {payload}")