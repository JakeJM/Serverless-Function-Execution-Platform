#!/bin/bash

echo "Starting Function Execution Engine and Dashboard..."
echo "=========================================="

# Make sure Docker is running
echo "Checking Docker status..."
if ! docker info >/dev/null 2>&1; then
  echo "Error: Docker is not running or not installed"
  echo "Please start Docker and try again"
  exit 1
fi

# Start all services together
echo "Starting all services with Docker Compose..."
docker-compose -f docker-compose.frontend.yml up -d

# Check if services started successfully
if [ $? -eq 0 ]; then
  echo ""
  echo "✓ Services started successfully!"
  echo ""
  echo "Access your applications at:"
  echo "- Backend API: http://localhost:80"
  echo "- Frontend Dashboard: http://localhost:8501"
  echo ""
  echo "To view logs:"
  echo "- Backend API: docker-compose -f docker-compose.frontend.yml logs -f web"
  echo "- Frontend: docker-compose -f docker-compose.frontend.yml logs -f frontend" 
  echo ""
  echo "To stop all services:"
  echo "  docker-compose -f docker-compose.frontend.yml down"
else
  echo "There was an error starting the services. Please check the Docker logs."
fi 