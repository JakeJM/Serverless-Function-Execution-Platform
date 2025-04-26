#!/bin/bash

# Get the absolute path to the current directory
CURRENT_DIR=$(pwd)

# Stop any running containers
echo "Stopping existing containers..."
docker-compose down

# Update the Docker Compose file to use absolute paths
echo "Updating Docker Compose file with absolute paths..."
sed -i "s|- ./functions:/functions|- ${CURRENT_DIR}/functions:/functions|g" docker-compose.yml

# Update the main.py file to use the correct absolute path
echo "Updating main.py with absolute path..."
sed -i "s|volume_config = {\"/functions\"|volume_config = {\"${CURRENT_DIR}/functions\"|g" app/main.py

# Create function directory
echo "Creating function directory structure..."
mkdir -p functions/6
cat > functions/6/handler.py << 'EOL'
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
EOL

# Make the handler executable
chmod 755 functions/6/handler.py

# Start the containers
echo "Starting containers..."
docker-compose up -d

# Wait for the service to start
echo "Waiting for service to start..."
sleep 10

# Check if the file is accessible
echo "Checking file accessibility..."
docker-compose exec web ls -la /functions/6/
docker-compose exec web cat /functions/6/handler.py

# Register function 6
echo "Registering function 6..."
curl "http://localhost:80/debug/register-existing-function/6?name=test-function-6&route=/test-function-6"

# Execute function 6
echo -e "\nExecuting function 6..."
curl -X POST "http://localhost:80/functions/6/execute" -H "Content-Type: application/json" -d '{"payload":{"test":"data"}}'

# Check metrics
echo -e "\nChecking metrics..."
curl "http://localhost:80/metrics/function/6"

echo -e "\nSetup complete!" 