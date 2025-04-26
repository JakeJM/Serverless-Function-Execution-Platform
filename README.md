# Serverless Function Management System

A complete system for deploying, managing, and monitoring serverless functions.

## Components

1. **Backend API (FastAPI)**
   - Create, update, delete and execute serverless functions
   - Store and retrieve metrics data
   - Manage Docker containers for function execution

2. **Frontend Dashboard (Streamlit)**
   - Intuitive web interface for function management
   - Visualize metrics and monitor performance
   - Execute functions with custom payloads

## Getting Started

### Run with Docker Compose (Recommended)

The easiest way to run the complete system is with Docker Compose:

```bash
# Run the backend services
docker-compose up -d

# Run the frontend along with the backend
docker-compose -f docker-compose.frontend.yml up -d
```

Then visit:
- Backend API: http://localhost:80
- Frontend Dashboard: http://localhost:8501

### Run Locally

If you prefer to run the services directly on your machine:

1. **Backend**
   ```bash
   pip install -r requirements.txt
   uvicorn app.main:app --host 0.0.0.0 --port 80
   ```

2. **Frontend**
   ```bash
   # On Linux/macOS
   ./run_frontend.sh
   
   # On Windows
   .\run_frontend.ps1
   ```

## Usage

### Functions Management

1. Create new functions with custom code
2. Update existing functions
3. Execute functions with custom payloads
4. Delete functions when no longer needed

### Metrics & Monitoring

1. View individual function metrics
2. Track execution time, success rate, and resource usage
3. Analyze historical performance
4. Monitor system-wide statistics

## Development

- **Backend**: Built with FastAPI, SQLAlchemy, and Docker
- **Frontend**: Built with Streamlit and Plotly for data visualization

## Directory Structure

```
├── app/               # Backend API code
├── frontend/          # Streamlit frontend application
├── functions/         # Function code storage
├── execution/         # Function execution environment
├── docker-compose.yml # Backend services configuration
└── requirements.txt   # Python dependencies
```

## License

This project is licensed under the MIT License - see the LICENSE file for details. 