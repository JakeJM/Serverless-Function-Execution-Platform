# Function Management Dashboard

A Streamlit-based frontend for managing serverless functions and visualizing metrics.

## Features

- **Function Management**
  - List, create, update, and delete functions
  - View function details and code
  - Execute functions with custom payloads
  - Test functions to generate metrics

- **Metrics Dashboard**
  - View metrics for individual functions
  - Filter metrics by time period
  - Visualize performance data with interactive charts
  - Track execution time, success rate, and resource usage

- **System Statistics**
  - Overview of system-wide metrics
  - Compare function performance
  - Identify most used and error-prone functions

## Setup

1. Install the required packages:
   ```bash
   pip install -r requirements.txt
   ```

2. Make sure the backend API is running on http://localhost:80

3. Run the Streamlit app:
   ```bash
   cd frontend
   streamlit run app.py
   ```

## Usage

1. Navigate through the application using the sidebar menu.
2. Create new functions or manage existing ones from the Functions page.
3. View detailed metrics for specific functions in the Metrics Dashboard.
4. Get an overview of system performance in the System Statistics page.

## Development

The frontend is built with:
- Streamlit for the UI components
- Plotly for interactive data visualization
- httpx for API communication

The application connects to the FastAPI backend to fetch data and perform operations. 