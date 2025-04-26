import streamlit as st
import plotly.express as px
import plotly.graph_objects as go
import pandas as pd
import httpx
import json
import time
import os
from datetime import datetime, timedelta

# Get API URL from environment variable or use default
API_URL = os.environ.get("API_URL", "http://localhost:80")  # The backend FastAPI service URL

# Initialize session state for navigation
if 'page' not in st.session_state:
    st.session_state.page = 'functions'

# Set page config
st.set_page_config(
    page_title="Function Management Dashboard",
    page_icon="⚡",
    layout="wide",
    initial_sidebar_state="expanded",
)

# Create sidebar navigation
st.sidebar.title("Navigation")
page = st.sidebar.radio(
    "Go to",
    ["Functions", "Metrics Dashboard", "System Statistics"],
    key="navigation",
    on_change=lambda: setattr(st.session_state, 'page', st.session_state.navigation.lower().replace(' ', '_'))
)

# Helper functions for API calls
def get_functions():
    try:
        response = httpx.get(f"{API_URL}/functions/")
        if response.status_code == 200:
            return response.json()
        else:
            st.error(f"Error fetching functions: {response.text}")
            return []
    except Exception as e:
        st.error(f"Error connecting to API: {str(e)}")
        return []

def get_function(function_id):
    try:
        response = httpx.get(f"{API_URL}/functions/{function_id}")
        if response.status_code == 200:
            return response.json()
        else:
            st.error(f"Error fetching function: {response.text}")
            return None
    except Exception as e:
        st.error(f"Error connecting to API: {str(e)}")
        return None

def create_function(data):
    try:
        response = httpx.post(f"{API_URL}/functions/", json=data)
        if response.status_code == 200:
            return response.json(), True
        else:
            st.error(f"Error creating function: {response.text}")
            return None, False
    except Exception as e:
        st.error(f"Error connecting to API: {str(e)}")
        return None, False

def update_function(function_id, data):
    try:
        response = httpx.put(f"{API_URL}/functions/{function_id}", json=data)
        if response.status_code == 200:
            return response.json(), True
        else:
            st.error(f"Error updating function: {response.text}")
            return None, False
    except Exception as e:
        st.error(f"Error connecting to API: {str(e)}")
        return None, False

def delete_function(function_id):
    try:
        response = httpx.delete(f"{API_URL}/functions/{function_id}")
        if response.status_code == 200:
            return True
        else:
            st.error(f"Error deleting function: {response.text}")
            return False
    except Exception as e:
        st.error(f"Error connecting to API: {str(e)}")
        return False

def test_function(function_id):
    try:
        response = httpx.get(f"{API_URL}/debug/test-function/{function_id}")
        if response.status_code == 200:
            return response.json()
        else:
            st.error(f"Error testing function: {response.text}")
            return None
    except Exception as e:
        st.error(f"Error connecting to API: {str(e)}")
        return None

def get_function_metrics(function_id):
    try:
        response = httpx.get(f"{API_URL}/metrics/function/{function_id}")
        if response.status_code == 200:
            return response.json()
        else:
            st.warning(f"No metrics found for this function")
            return []
    except Exception as e:
        st.error(f"Error connecting to API: {str(e)}")
        return []

def get_function_metrics_summary(function_id, days=None):
    try:
        url = f"{API_URL}/metrics/function/{function_id}/summary"
        if days:
            url += f"?days={days}"
        response = httpx.get(url)
        if response.status_code == 200:
            return response.json()
        else:
            st.warning(f"No metrics summary found for this function")
            return None
    except Exception as e:
        st.error(f"Error connecting to API: {str(e)}")
        return None

def get_all_metrics_summary():
    try:
        response = httpx.get(f"{API_URL}/metrics/summary")
        if response.status_code == 200:
            return response.json()
        else:
            st.warning(f"No metrics summary found")
            return []
    except Exception as e:
        st.error(f"Error connecting to API: {str(e)}")
        return []

def get_function_timeseries(function_id, period="daily"):
    try:
        response = httpx.get(f"{API_URL}/metrics/function/{function_id}/timeseries?period={period}")
        if response.status_code == 200:
            return response.json()
        else:
            st.warning(f"No timeseries data found for this function")
            return []
    except Exception as e:
        st.error(f"Error connecting to API: {str(e)}")
        return []

def execute_function(function_id, payload=None):
    if payload is None:
        payload = {}
    
    try:
        response = httpx.post(
            f"{API_URL}/functions/{function_id}/execute", 
            json={"payload": payload}
        )
        return response.json()
    except Exception as e:
        st.error(f"Error executing function: {str(e)}")
        return None

# Function page
def show_functions_page():
    st.title("Function Management")
    
    # Create tabs for listing and creating functions
    tab1, tab2 = st.tabs(["Function List", "Create New Function"])
    
    with tab1:
        st.subheader("Available Functions")
        functions = get_functions()
        
        if not functions:
            st.info("No functions found. Create a new function to get started.")
        else:
            # Display functions in a table
            function_data = []
            for func in functions:
                function_data.append({
                    "ID": func["id"],
                    "Name": func["name"],
                    "Route": func["route"],
                    "Language": func["language"],
                    "Created": func["created_at"][:19],  # Truncate to remove milliseconds
                })
            
            df = pd.DataFrame(function_data)
            st.dataframe(df, use_container_width=True)
            
            # Function details and actions
            selected_function_id = st.selectbox(
                "Select a function to view details:",
                options=[func["id"] for func in functions],
                format_func=lambda x: next((f["name"] for f in functions if f["id"] == x), ""),
            )
            
            if selected_function_id:
                function = get_function(selected_function_id)
                if function:
                    col1, col2 = st.columns([2, 1])
                    
                    with col1:
                        st.subheader(f"Function: {function['name']}")
                        st.write(f"**ID:** {function['id']}")
                        st.write(f"**Route:** {function['route']}")
                        st.write(f"**Language:** {function['language']}")
                        st.write(f"**Timeout:** {function['timeout']} seconds")
                        st.write(f"**Created:** {function['created_at'][:19]}")
                        
                        with st.expander("View Code"):
                            st.code(function['code'], language="python" if function['language'] == "python" else "javascript")
                    
                    with col2:
                        st.subheader("Actions")
                        
                        # Test function
                        test_button = st.button("Test Function", key=f"test_{function['id']}")
                        if test_button:
                            with st.spinner("Testing function..."):
                                result = test_function(function['id'])
                                if result:
                                    st.success("Function executed successfully")
                                    st.json(result)
                        
                        # Execute function with custom payload
                        st.subheader("Execute Function")
                        payload_json = st.text_area(
                            "Enter payload (JSON):",
                            value='{"test": "data"}',
                            key=f"payload_{function['id']}"
                        )
                        
                        try:
                            payload = json.loads(payload_json)
                            execute_button = st.button("Execute", key=f"exec_{function['id']}")
                            if execute_button:
                                with st.spinner("Executing function..."):
                                    result = execute_function(function['id'], payload)
                                    if result:
                                        st.success("Function executed successfully")
                                        st.json(result)
                        except json.JSONDecodeError:
                            st.error("Invalid JSON payload")
                        
                        # Delete function
                        st.divider()
                        if st.button("Delete Function", key=f"delete_{function['id']}", type="primary", use_container_width=True):
                            if st.session_state.get(f"confirm_delete_{function['id']}", False):
                                # User has confirmed, perform deletion
                                if delete_function(function['id']):
                                    st.success(f"Function {function['name']} deleted successfully")
                                    st.session_state[f"confirm_delete_{function['id']}"] = False
                                    time.sleep(1)
                                    st.rerun()
                            else:
                                # Ask for confirmation
                                st.session_state[f"confirm_delete_{function['id']}"] = True
                                st.warning(f"Are you sure you want to delete {function['name']}? Click the button again to confirm.")
                        
                        # Update function
                        st.divider()
                        if st.button("Edit Function", key=f"edit_{function['id']}", use_container_width=True):
                            st.session_state.edit_function = function
                            st.rerun()
                        
                        # Show metrics button
                        st.divider()
                        if st.button("View Metrics", key=f"metrics_{function['id']}", use_container_width=True):
                            st.session_state.page = 'metrics_dashboard'
                            st.session_state.selected_function_id = function['id']
                            st.rerun()
                
                # Edit function form (appears when edit button is clicked)
                if hasattr(st.session_state, 'edit_function') and st.session_state.edit_function:
                    function = st.session_state.edit_function
                    st.subheader(f"Edit Function: {function['name']}")
                    
                    with st.form(key=f"edit_form_{function['id']}"):
                        name = st.text_input("Function Name", value=function['name'])
                        route = st.text_input("Route", value=function['route'])
                        language = st.selectbox(
                            "Language", 
                            options=["python", "javascript"],
                            index=0 if function['language'] == "python" else 1
                        )
                        timeout = st.number_input("Timeout (seconds)", value=function['timeout'], min_value=1, max_value=300)
                        code = st.text_area("Code", value=function['code'], height=300)
                        image_name = st.selectbox(
                            "Image", 
                            options=["python-function", "javascript-function"],
                            index=0 if "python" in function['image_name'] else 1
                        )
                        
                        submit_button = st.form_submit_button("Update Function")
                        cancel_button = st.form_submit_button("Cancel")
                        
                        if submit_button:
                            updated_data = {
                                "name": name,
                                "route": route,
                                "language": language,
                                "timeout": timeout,
                                "code": code,
                                "image_name": image_name
                            }
                            
                            updated_function, success = update_function(function['id'], updated_data)
                            if success:
                                st.success(f"Function {name} updated successfully")
                                del st.session_state.edit_function
                                time.sleep(1)
                                st.rerun()
                        
                        if cancel_button:
                            del st.session_state.edit_function
                            st.rerun()
    
    with tab2:
        st.subheader("Create New Function")
        
        with st.form(key="create_function_form"):
            name = st.text_input("Function Name")
            route = st.text_input("Route (e.g., /my-function)")
            language = st.selectbox("Language", options=["python", "javascript"])
            timeout = st.number_input("Timeout (seconds)", value=30, min_value=1, max_value=300)
            
            if language == "python":
                default_code = """import os
import json
import time

# Get the payload from environment variable
payload = json.loads(os.getenv("PAYLOAD", "{}"))

# Your function logic here
result = {
    "message": "Hello from serverless function!",
    "received_data": payload,
    "timestamp": time.time()
}

# Return response as JSON string
print(json.dumps(result))
"""
            else:
                default_code = """const payload = JSON.parse(process.env.PAYLOAD || "{}");

// Your function logic here
const result = {
    message: "Hello from serverless function!",
    received_data: payload,
    timestamp: Date.now() / 1000
};

// Return response as JSON string
console.log(JSON.stringify(result));
"""
            
            code = st.text_area("Code", value=default_code, height=300)
            image_name = f"{language}-function"
            
            submit_button = st.form_submit_button("Create Function")
            
            if submit_button:
                if not name or not route:
                    st.error("Function name and route are required")
                else:
                    # Normalize route (ensure it starts with /)
                    if not route.startswith("/"):
                        route = f"/{route}"
                    
                    new_function_data = {
                        "name": name,
                        "route": route,
                        "language": language,
                        "timeout": timeout,
                        "code": code,
                        "image_name": image_name
                    }
                    
                    new_function, success = create_function(new_function_data)
                    if success:
                        st.success(f"Function {name} created successfully with ID {new_function['id']}")
                        time.sleep(1)
                        st.rerun()

# Metrics Dashboard page
def show_metrics_dashboard():
    st.title("Function Metrics Dashboard")
    
    # Get available functions for the dropdown
    functions = get_functions()
    
    if not functions:
        st.info("No functions available. Create a function first to view metrics.")
        return
    
    # Check if a function was selected from the function page
    selected_id = None
    if hasattr(st.session_state, 'selected_function_id'):
        selected_id = st.session_state.selected_function_id
        del st.session_state.selected_function_id
    
    # Function selector
    selected_function_id = st.selectbox(
        "Select a function to view metrics:",
        options=[func["id"] for func in functions],
        format_func=lambda x: next((f["name"] for f in functions if f["id"] == x), ""),
        index=next((i for i, f in enumerate(functions) if f["id"] == selected_id), 0) if selected_id else 0
    )
    
    if selected_function_id:
        function = get_function(selected_function_id)
        if function:
            st.subheader(f"Detailed Metrics for: {function['name']}")
            
            # Get detailed metrics for the function
            metrics = get_function_metrics(selected_function_id)
            
            if metrics:
                # Convert metrics to DataFrame for easier manipulation
                df = pd.DataFrame(metrics)
                
                # Add human-readable timestamp
                df['formatted_time'] = pd.to_datetime(df['timestamp']).dt.strftime('%Y-%m-%d %H:%M:%S')
                
                # Add status indicator
                df['status'] = df['status_code'].apply(lambda x: "Success" if x < 400 else "Error")
                
                # Display summary metrics at the top
                col1, col2, col3, col4 = st.columns(4)
                
                with col1:
                    st.metric("Total Executions", len(df))
                
                with col2:
                    avg_time = round(df['execution_time_ms'].mean(), 2)
                    st.metric("Avg Execution Time", f"{avg_time} ms")
                
                with col3:
                    success_rate = round((df['status_code'] < 400).mean() * 100, 1)
                    st.metric("Success Rate", f"{success_rate}%")
                
                with col4:
                    if 'memory_usage_mb' in df.columns and not df['memory_usage_mb'].isna().all():
                        memory = round(df['memory_usage_mb'].mean(), 2)
                        st.metric("Avg Memory Usage", f"{memory} MB")
                    else:
                        st.metric("Avg Memory Usage", "N/A")
                
                # Display charts
                col1, col2 = st.columns(2)
                
                with col1:
                    # Success vs Error chart
                    status_counts = df['status'].value_counts()
                    fig = go.Figure(data=[
                        go.Pie(
                            labels=status_counts.index,
                            values=status_counts.values,
                            hole=.3,
                            marker_colors=['#32a852', '#a83232'] if 'Error' in status_counts.index else ['#32a852']
                        )
                    ])
                    fig.update_layout(title="Success vs Error Ratio")
                    st.plotly_chart(fig, use_container_width=True)
                
                with col2:
                    # Execution time distribution
                    fig = px.histogram(
                        df, 
                        x='execution_time_ms',
                        nbins=20,
                        color='status',
                        color_discrete_map={'Success': '#32a852', 'Error': '#a83232'},
                        title="Execution Time Distribution"
                    )
                    st.plotly_chart(fig, use_container_width=True)
                
                # Execution time over time
                fig = px.scatter(
                    df,
                    x='formatted_time',
                    y='execution_time_ms',
                    color='status',
                    color_discrete_map={'Success': '#32a852', 'Error': '#a83232'},
                    size='execution_time_ms',
                    hover_data=['execution_time_ms', 'status_code', 'error'],
                    title="Execution Time Over Time",
                    labels={
                        'formatted_time': 'Timestamp',
                        'execution_time_ms': 'Execution Time (ms)'
                    }
                )
                fig.update_layout(xaxis={'categoryorder': 'category ascending'})
                st.plotly_chart(fig, use_container_width=True)
                
                # Resource usage (if available)
                if 'memory_usage_mb' in df.columns and 'cpu_usage_percent' in df.columns:
                    has_memory = not df['memory_usage_mb'].isna().all()
                    has_cpu = not df['cpu_usage_percent'].isna().all()
                    
                    if has_memory or has_cpu:
                        st.subheader("Resource Usage")
                        
                        col1, col2 = st.columns(2)
                        
                        if has_memory:
                            with col1:
                                fig = px.line(
                                    df.sort_values('formatted_time'),
                                    x='formatted_time',
                                    y='memory_usage_mb',
                                    markers=True,
                                    title="Memory Usage Over Time",
                                    labels={
                                        'formatted_time': 'Timestamp',
                                        'memory_usage_mb': 'Memory Usage (MB)'
                                    }
                                )
                                st.plotly_chart(fig, use_container_width=True)
                        
                        if has_cpu:
                            with col2:
                                fig = px.line(
                                    df.sort_values('formatted_time'),
                                    x='formatted_time',
                                    y='cpu_usage_percent',
                                    markers=True,
                                    title="CPU Usage Over Time",
                                    labels={
                                        'formatted_time': 'Timestamp',
                                        'cpu_usage_percent': 'CPU Usage (%)'
                                    }
                                )
                                st.plotly_chart(fig, use_container_width=True)
                
                # Detailed metrics table
                st.subheader("Detailed Execution Records")
                
                # Filter columns for display
                display_columns = ['formatted_time', 'status', 'execution_time_ms', 'status_code']
                
                if 'memory_usage_mb' in df.columns and not df['memory_usage_mb'].isna().all():
                    display_columns.append('memory_usage_mb')
                
                if 'cpu_usage_percent' in df.columns and not df['cpu_usage_percent'].isna().all():
                    display_columns.append('cpu_usage_percent')
                
                if 'container_id' in df.columns:
                    display_columns.append('container_id')
                
                # Add error column if there are any errors
                if not df['error'].isna().all():
                    display_columns.append('error')
                
                # Show the detailed table with sorting
                st.dataframe(
                    df[display_columns].sort_values('formatted_time', ascending=False),
                    use_container_width=True,
                    column_config={
                        'formatted_time': st.column_config.TextColumn('Timestamp'),
                        'status': st.column_config.TextColumn('Status'),
                        'execution_time_ms': st.column_config.NumberColumn('Execution Time (ms)'),
                        'status_code': st.column_config.NumberColumn('Status Code'),
                        'memory_usage_mb': st.column_config.NumberColumn('Memory (MB)'),
                        'cpu_usage_percent': st.column_config.NumberColumn('CPU (%)'),
                        'container_id': st.column_config.TextColumn('Container ID'),
                        'error': st.column_config.TextColumn('Error Message')
                    }
                )
                
                # Run a test execution 
                if st.button("Run Test Execution"):
                    with st.spinner("Testing function..."):
                        result = test_function(selected_function_id)
                        if result:
                            st.success("Function executed successfully")
                            st.json(result)
                            time.sleep(1)
                            st.rerun()  # Refresh to show new metrics
                
            else:
                st.info("No metrics available for this function. Execute the function to generate metrics.")
                
                # Add a button to test the function
                if st.button("Run Test Execution"):
                    with st.spinner("Testing function..."):
                        result = test_function(selected_function_id)
                        if result:
                            st.success("Function executed successfully")
                            st.json(result)
                            time.sleep(1)
                            st.rerun()  # Refresh to show new metrics

# System Statistics page
def show_system_statistics():
    st.title("System-wide Statistics")
    
    # Get summary of all functions
    summaries = get_all_metrics_summary()
    
    if not summaries:
        st.info("No metrics available. Execute some functions to generate metrics.")
        return
    
    # Convert to DataFrame for easier manipulation
    df = pd.DataFrame(summaries)
    
    # Calculate total metrics
    total_executions = df["total_executions"].sum()
    total_errors = df["error_count"].sum()
    success_rate = 0
    if total_executions > 0:
        success_rate = round(((total_executions - total_errors) / total_executions) * 100, 1)
    
    # System-wide metrics cards
    col1, col2, col3 = st.columns(3)
    
    with col1:
        st.metric("Total Functions", len(df))
    
    with col2:
        st.metric("Total Executions", total_executions)
    
    with col3:
        st.metric("Overall Success Rate", f"{success_rate}%")
    
    # Most used functions
    st.subheader("Most Executed Functions")
    
    # Sort by total executions
    top_functions = df.sort_values("total_executions", ascending=False).head(10)
    
    if not top_functions.empty:
        fig = px.bar(
            top_functions,
            x="function_name",
            y="total_executions",
            title="Top Functions by Execution Count",
            labels={"function_name": "Function Name", "total_executions": "Execution Count"}
        )
        st.plotly_chart(fig, use_container_width=True)
    
    # Functions with highest error rates
    st.subheader("Functions with Highest Error Rates")
    
    # Calculate error rate
    df["error_rate"] = df.apply(
        lambda row: 0 if row["total_executions"] == 0 else (row["error_count"] / row["total_executions"]) * 100,
        axis=1
    )
    
    # Filter to only include functions with executions
    df_with_executions = df[df["total_executions"] > 0]
    
    if not df_with_executions.empty:
        error_functions = df_with_executions.sort_values("error_rate", ascending=False).head(10)
        
        fig = px.bar(
            error_functions,
            x="function_name",
            y="error_rate",
            title="Functions with Highest Error Rates",
            labels={"function_name": "Function Name", "error_rate": "Error Rate (%)"}
        )
        fig.update_layout(yaxis_range=[0, 100])
        st.plotly_chart(fig, use_container_width=True)
    
    # Performance comparison
    st.subheader("Performance Comparison")
    
    col1, col2 = st.columns(2)
    
    with col1:
        # Average execution time comparison
        fig = px.bar(
            df.sort_values("avg_execution_time_ms", ascending=False).head(10),
            x="function_name",
            y="avg_execution_time_ms",
            title="Functions by Average Execution Time",
            labels={"function_name": "Function Name", "avg_execution_time_ms": "Avg Execution Time (ms)"}
        )
        st.plotly_chart(fig, use_container_width=True)
    
    with col2:
        # Memory usage comparison (if available)
        df_with_memory = df[df["avg_memory_usage_mb"].notna()]
        
        if not df_with_memory.empty:
            fig = px.bar(
                df_with_memory.sort_values("avg_memory_usage_mb", ascending=False).head(10),
                x="function_name",
                y="avg_memory_usage_mb",
                title="Functions by Average Memory Usage",
                labels={"function_name": "Function Name", "avg_memory_usage_mb": "Avg Memory Usage (MB)"}
            )
            st.plotly_chart(fig, use_container_width=True)
        else:
            st.info("No memory usage data available")
    
    # Function call distribution
    st.subheader("Function Call Distribution")
    
    if not df.empty:
        fig = px.pie(
            df, 
            values="total_executions", 
            names="function_name",
            title="Distribution of Function Calls"
        )
        fig.update_traces(textposition='inside', textinfo='percent+label')
        st.plotly_chart(fig, use_container_width=True)

# Main app logic
if st.session_state.page == 'functions':
    show_functions_page()
elif st.session_state.page == 'metrics_dashboard':
    show_metrics_dashboard()
elif st.session_state.page == 'system_statistics':
    show_system_statistics() 