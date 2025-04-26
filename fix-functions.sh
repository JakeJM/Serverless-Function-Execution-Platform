#!/bin/bash

echo "Stopping containers..."
docker-compose down

echo "Starting containers..."
docker-compose up -d

echo "Waiting for containers to start..."
sleep 10

echo "Checking function 6 directory structure..."
docker-compose exec web ls -la /functions/6/

echo "Registering function 6 (if not already registered)..."
curl "http://localhost:80/debug/register-existing-function/6?name=test-function-6&route=/test-function-6" || true

echo "Testing function 6..."
curl -X POST "http://localhost:80/functions/6/execute" -H "Content-Type: application/json" -d '{"payload":{"test":"data"}}' || true

echo "Checking metrics for function 6..."
curl "http://localhost:80/metrics/function/6" || true

echo "Done." 