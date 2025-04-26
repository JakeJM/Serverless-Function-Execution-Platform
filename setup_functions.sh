#!/bin/bash

# Create function volume directory if it doesn't exist
mkdir -p function_vol

# Ensure we can write to it
chmod 777 function_vol

# Stop the containers
docker-compose down

# Start the containers
docker-compose up -d

# Wait for the web container to start
echo "Waiting for containers to start..."
sleep 5

# Copy function files to the function_vol directory
echo "Copying functions to Docker volume..."
for dir in functions/*/; do
  func_id=$(basename "$dir")
  mkdir -p "function_vol/$func_id"
  cp "$dir"handler.* "function_vol/$func_id/" 2>/dev/null || true
  chmod -R 777 "function_vol/$func_id"
  echo "Copied $dir to function_vol/$func_id"
done

# Register function 6 in the database
echo "Registering function 6..."
sleep 2
curl "http://localhost:80/debug/register-existing-function/6?name=test-function-6&route=/test-function-6"

# Test function 6
echo -e "\nTesting function 6..."
sleep 2
curl -X POST "http://localhost:80/functions/6/execute" -H "Content-Type: application/json" -d '{"payload":{"test":"data"}}'

# Show metrics
echo -e "\nChecking metrics..."
sleep 2
curl "http://localhost:80/metrics/function/6"

echo -e "\nSetup complete!" 