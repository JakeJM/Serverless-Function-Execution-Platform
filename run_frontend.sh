#!/bin/bash

# Check if frontend directory exists, create if not
if [ ! -d "frontend" ]; then
    echo "Creating frontend directory..."
    mkdir -p frontend
fi

# Check if app.py exists in frontend directory
if [ ! -f "frontend/app.py" ]; then
    echo "Error: frontend/app.py not found. Make sure the file exists."
    exit 1
fi

# Install required packages
echo "Installing required packages..."
pip install -r requirements.txt

# Run the Streamlit app
echo "Starting the Streamlit app..."
cd frontend && streamlit run app.py

echo "Streamlit app stopped." 