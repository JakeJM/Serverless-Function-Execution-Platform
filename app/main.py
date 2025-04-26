import docker
from fastapi import FastAPI, Depends, HTTPException, Query
from app import schemas, crud, models, database
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from docker import DockerClient
from docker.errors import DockerException
from pathlib import Path
import asyncio
import os
import time
import logging
from typing import Dict, Optional, List, Union
from pydantic import BaseModel
from fastapi.responses import JSONResponse
import json
import sqlalchemy.exc
import shutil
from asyncio import Lock
from datetime import datetime, timedelta
import psutil

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Initialize FastAPI app
app = FastAPI()

# Container pool for warm containers
CONTAINER_POOL: Dict[int, list] = {}  # {function_id: [container1, container2, ...]}
POOL_SIZE = 2  # Number of warm containers per function
WARMUP_INTERVAL = 40  # Seconds between warmup calls (changed from 300 to 40)
POOL_LOCK = Lock()  # Lock for synchronizing pool maintenance

# Hardcoded path as requested
HOST_FUNCTIONS_DIR = "/app/functions"
CONTAINER_FUNCTIONS_DIR = "/functions"

@app.on_event("startup")
async def startup():
    async with database.engine.begin() as conn:
        await conn.run_sync(models.Base.metadata.create_all)
    # Start warmup task
    asyncio.create_task(warmup_containers())

@app.on_event("shutdown")
async def shutdown():
    logger.info("Shutdown handler started")
    # Clean up all containers in the pool
    client = DockerClient()
    for function_id, containers in CONTAINER_POOL.items():
        for container in containers:
            try:
                container.stop()
                container.remove(force=True)
                logger.info(f"Stopped and removed container {container.id} for function {function_id}")
            except Exception as e:
                logger.error(f"Failed to clean up container {container.id}: {e}")
    CONTAINER_POOL.clear()
    # Clean up any stranded function containers
    try:
        for image_name in ["python-function", "javascript-function"]:
            for container in client.containers.list(all=True, filters={"ancestor": image_name}):
                try:
                    container.stop()
                    container.remove(force=True)
                    logger.info(f"Removed stranded container {container.id}")
                except Exception as e:
                    logger.error(f"Failed to clean up stranded container {container.id}: {e}")
    except Exception as e:
        logger.error(f"Failed to list stranded containers: {e}")
    client.close()

async def warmup_containers():
    """Periodically ensure warm containers and make dummy calls."""
    client = DockerClient()
    try:
        while True:
            async with database.async_session() as db:
                functions = await crud.get_all_functions(db)
                for function in functions:
                    # Ensure pool has enough containers
                    await maintain_container_pool(client, function)
                    # Make a dummy call to keep containers warm
                    if function.language == "python":
                        command = f"python {CONTAINER_FUNCTIONS_DIR}/{function.id}/handler.py"
                    else:
                        command = f"node {CONTAINER_FUNCTIONS_DIR}/{function.id}/handler.js"
                    for container in CONTAINER_POOL.get(function.id, []):
                        try:
                            exec_result = container.exec_run(command)
                            logger.info(f"Warmup call for function {function.id} in container {container.id}: exit_code={exec_result.exit_code}, output={exec_result.output.decode()}")
                        except DockerException as e:
                            logger.error(f"Warmup failed for function {function.id}: {e}")
            await asyncio.sleep(WARMUP_INTERVAL)
    except Exception as e:
        logger.error(f"Warmup task failed: {e}")
    finally:
        client.close()

async def maintain_container_pool(client: DockerClient, function: models.Function):
    """Maintain a pool of warm containers for a function."""
    function_id = function.id
    async with POOL_LOCK:
        if function_id not in CONTAINER_POOL:
            CONTAINER_POOL[function_id] = []

        current_containers = CONTAINER_POOL[function_id]
        # Remove stopped containers
        current_containers = [c for c in current_containers if c.status in ["running", "created"]]
        
        # Remove excess containers if we have more than POOL_SIZE
        if len(current_containers) > POOL_SIZE:
            excess_containers = current_containers[POOL_SIZE:]
            current_containers = current_containers[:POOL_SIZE]
            # Clean up excess containers
            for container in excess_containers:
                try:
                    container.stop()
                    container.remove(force=True)
                    logger.info(f"Removed excess container {container.id} for function {function_id}")
                except Exception as e:
                    logger.error(f"Failed to clean up excess container {container.id}: {e}")
        
        logger.info(f"Function {function_id} pool: {len(current_containers)} running containers, {[c.id for c in current_containers]}")

        # Start new containers only if needed
        # Use the absolute path for the volume configuration
        volume_config = {"/functions": {"bind": "/functions", "mode": "ro"}}
        if len(current_containers) < POOL_SIZE:
            logger.info(f"Maintaining pool for function {function_id}: current={len(current_containers)}, needed={POOL_SIZE - len(current_containers)}")
            for _ in range(POOL_SIZE - len(current_containers)):
                try:
                    container = client.containers.run(
                        function.image_name,
                        command="sleep infinity",
                        volumes=volume_config,
                        mem_limit="128m",
                        network_mode="none",
                        detach=True,
                        remove=False
                    )
                    # Wait to ensure filesystem sync
                    time.sleep(1)
                    # Debug: Verify volume contents
                    debug_output = container.exec_run(f"ls -la {CONTAINER_FUNCTIONS_DIR}/{function_id}").output.decode()
                    logger.info(f"Warm container {container.id} for function {function_id} volume contents: {debug_output}")
                    current_containers.append(container)
                    logger.info(f"Started warm container {container.id} for function {function_id}")
                except DockerException as e:
                    logger.error(f"Failed to start warm container for function {function_id}: {e}")
                    break
        CONTAINER_POOL[function_id] = current_containers

        # Clean up stranded containers not in the pool
        try:
            running_containers = client.containers.list(filters={"ancestor": function.image_name})
            pool_container_ids = {c.id for c in current_containers}
            for container in running_containers:
                # Refresh container status
                try:
                    container.reload()
                except:
                    continue
                    
                if container.id not in pool_container_ids:
                    try:
                        # Check if this container is used by other functions before removing
                        is_used_by_other_function = False
                        for f_id, containers in CONTAINER_POOL.items():
                            if f_id != function_id and any(c.id == container.id for c in containers):
                                is_used_by_other_function = True
                                break
                        
                        if not is_used_by_other_function:
                            # Only remove containers that are not in the warm-up process
                            if container.status not in ["created", "running"]:
                                logger.info(f"Skipping cleanup of non-running container {container.id} for function {function_id}")
                                continue
                                
                            container.stop()
                            container.remove(force=True)
                            logger.info(f"Removed stranded container {container.id} for function {function_id}")
                    except Exception as e:
                        logger.error(f"Failed to clean up stranded container {container.id}: {e}")
        except Exception as e:
            logger.error(f"Failed to clean up stranded containers for function {function_id}: {e}")

@app.post("/functions/", response_model=schemas.Function)
async def create_function(
    function: schemas.FunctionCreate,
    db: AsyncSession = Depends(database.get_db)
):
    try:
        db_function = await crud.create_function(db, function)
        # Write the handler file
        temp_dir = f"{HOST_FUNCTIONS_DIR}/{db_function.id}"
        Path(temp_dir).mkdir(parents=True, exist_ok=True)
        ext = "py" if function.language == "python" else "js"
        handler_path = Path(temp_dir) / f"handler.{ext}"
        handler_path.write_text(function.code)
        os.sync()
        time.sleep(1)  # Ensure file is synced
        os.chmod(temp_dir, 0o777)
        handler_path.chmod(0o777)
        logger.info(f"Handler file written to {handler_path}")
        # Debug: Verify file contents
        logger.info(f"File exists: {handler_path.exists()}, Contents: {handler_path.read_text()}")
        # Start warm containers
        client = DockerClient()
        try:
            await maintain_container_pool(client, db_function)
        finally:
            client.close()
        return db_function
    except sqlalchemy.exc.IntegrityError as e:
        logger.error(f"Failed to create function: {str(e)}")
        raise HTTPException(
            status_code=400,
            detail=f"Function with name '{function.name}' already exists"
        )

@app.get("/functions/", response_model=list[schemas.Function])
async def read_functions(
    skip: int = 0,
    limit: int = 100,
    db: AsyncSession = Depends(database.get_db)
):
    return await crud.get_all_functions(db)

@app.get("/functions/{function_id}", response_model=schemas.Function)
async def read_function(
    function_id: int,
    db: AsyncSession = Depends(database.get_db)
):
    function = await crud.get_function(db, function_id)
    if function is None:
        raise HTTPException(status_code=404, detail="Function not found")
    return function

@app.put("/functions/{function_id}", response_model=schemas.Function)
async def update_function(
    function_id: int,
    function: schemas.FunctionCreate,
    db: AsyncSession = Depends(database.get_db)
):
    updated = await crud.update_function(db, function_id, function)
    if not updated:
        raise HTTPException(status_code=404, detail="Function not found")
    # Update the handler file
    temp_dir = f"{HOST_FUNCTIONS_DIR}/{function_id}"
    Path(temp_dir).mkdir(parents=True, exist_ok=True)
    ext = "py" if function.language == "python" else "js"
    handler_path = Path(temp_dir) / f"handler.{ext}"
    handler_path.write_text(function.code)
    os.sync()
    time.sleep(1)  # Ensure file is synced
    os.chmod(temp_dir, 0o777)
    handler_path.chmod(0o777)
    logger.info(f"Handler file updated to {handler_path}")
    return updated

@app.delete("/functions/{function_id}")
async def delete_function(
    function_id: int,
    db: AsyncSession = Depends(database.get_db)
):
    deleted = await crud.delete_function(db, function_id)
    if not deleted:
        raise HTTPException(status_code=404, detail="Function not found")
    # Clean up containers
    if function_id in CONTAINER_POOL:
        for container in CONTAINER_POOL[function_id]:
            try:
                container.stop()
                container.remove(force=True)
                logger.info(f"Stopped and removed container {container.id} for function {function_id}")
            except Exception as e:
                logger.error(f"Failed to clean up container {container.id}: {e}")
        del CONTAINER_POOL[function_id]
    # Remove handler file
    temp_dir = f"/app/functions/{function_id}"
    if Path(temp_dir).exists():
        shutil.rmtree(temp_dir)
    return {"message": "Function deleted"}

async def collect_container_metrics(container):
    """Collect resource usage metrics from a container."""
    try:
        stats = container.stats(stream=False)
        
        # Extract CPU metrics
        cpu_delta = stats['cpu_stats']['cpu_usage']['total_usage'] - stats['precpu_stats']['cpu_usage']['total_usage']
        system_delta = stats['cpu_stats']['system_cpu_usage'] - stats['precpu_stats']['system_cpu_usage']
        num_cpus = len(stats['cpu_stats']['cpu_usage']['percpu_usage'])
        cpu_percent = (cpu_delta / system_delta) * num_cpus * 100.0
        
        # Extract memory metrics
        memory_usage = stats['memory_stats']['usage'] / (1024 * 1024)  # Convert to MB
        
        return {
            "cpu_usage_percent": cpu_percent,
            "memory_usage_mb": memory_usage
        }
    except Exception as e:
        logger.error(f"Failed to collect container metrics: {e}")
        return {
            "cpu_usage_percent": None,
            "memory_usage_mb": None
        }

@app.post("/invoke/{route:path}", response_model=schemas.InvokeResponse)
async def invoke_function(
    route: str,
    request: schemas.InvokeRequest,
    db: AsyncSession = Depends(database.get_db)
):
    """Route requests to the appropriate function based on the route."""
    # Normalize route - ensure it has a leading slash
    if not route.startswith("/"):
        route = "/" + route
        
    result = await db.execute(
        select(models.Function).filter(models.Function.route == route)
    )
    function = result.scalars().first()
    if not function:
        raise HTTPException(status_code=404, detail=f"Function with route {route} not found")

    # Start timing
    start_time = time.time()

    client = DockerClient()
    volume_config = {"/functions": {"bind": "/functions", "mode": "ro"}}
    command = f"python {CONTAINER_FUNCTIONS_DIR}/{function.id}/handler.py" if function.language == "python" else f"node {CONTAINER_FUNCTIONS_DIR}/{function.id}/handler.js"

    # Try to use a warm container from the pool
    container = None
    status = 0
    output = ""
    error = None
    reuse_container = True
    resource_metrics = {}

    async with POOL_LOCK:
        if function.id in CONTAINER_POOL and CONTAINER_POOL[function.id]:
            container = CONTAINER_POOL[function.id].pop(0)  # Take a container
            logger.info(f"Using warm container {container.id} for function {function.id}")
        else:
            logger.info(f"No warm container available for function {function.id}, starting new")
            try:
                container = client.containers.run(
                    function.image_name,
                    command="sleep infinity",
                    volumes=volume_config,
                    mem_limit="128m",
                    network_mode="none",
                    detach=True,
                    remove=False
                )
                logger.info(f"Started new container {container.id} for function {function.id}")
            except DockerException as e:
                # Calculate execution time even for failures
                execution_time_ms = (time.time() - start_time) * 1000
                logger.error(f"Failed to start new container for function {function.id}: {e}")
                status = 500
                error = str(e)
                
                # Save metric for failed container start
                metric_data = schemas.MetricCreate(
                    function_id=function.id,
                    execution_time_ms=execution_time_ms,
                    status_code=status,
                    container_id=None,
                    error=error,
                    payload_size=len(json.dumps(request.payload or {}))
                )
                await crud.create_metric(db, metric_data)
                
                client.close()
                return JSONResponse(
                    status_code=500,
                    content={"status": status, "output": output, "error": error}
                )

    try:
        # Reload container to ensure we have the latest status
        container.reload()
        
        # Ensure container is in a good state
        if container.status not in ["running", "created"]:
            raise DockerException(f"Container in invalid state: {container.status}")
            
        # Debug: Verify volume contents
        debug_output = container.exec_run(f"ls -l {CONTAINER_FUNCTIONS_DIR}/{function.id}").output.decode()
        logger.info(f"Container {container.id} volume contents: {debug_output}")
        
        # Start collecting resource metrics
        pre_exec_metrics = await collect_container_metrics(container)
        
        # Execute function
        env = {"PAYLOAD": json.dumps(request.payload or {})}
        exec_result = container.exec_run(command, environment=env)
        status = exec_result.exit_code
        output = exec_result.output.decode()
        
        # Get post-execution metrics
        post_exec_metrics = await collect_container_metrics(container)
        resource_metrics = post_exec_metrics  # Use the post-execution metrics
        
        if status != 0:
            error = output
            output = ""
            reuse_container = False
    except DockerException as e:
        error = str(e)
        status = 500
        reuse_container = False

    # Calculate execution time
    execution_time_ms = (time.time() - start_time) * 1000
    
    # Save metrics
    try:
        metric_data = schemas.MetricCreate(
            function_id=function.id,
            execution_time_ms=execution_time_ms,
            status_code=status,
            container_id=container.id if container else None,
            memory_usage_mb=resource_metrics.get("memory_usage_mb"),
            cpu_usage_percent=resource_metrics.get("cpu_usage_percent"),
            error=error,
            payload_size=len(json.dumps(request.payload or {}))
        )
        await crud.create_metric(db, metric_data)
    except Exception as e:
        logger.error(f"Failed to save metrics: {e}")

    # Clean up or reuse container
    async with POOL_LOCK:
        logger.info(f"Execution status: {status}, reuse_container: {reuse_container}, container_status: {container.status}")
        # Check if container is in a reusable state (created or running)
        if reuse_container and container.status in ["running", "created"]:
            CONTAINER_POOL.setdefault(function.id, []).append(container)
            logger.info(f"Reusing container {container.id} for function {function.id}")
        else:
            try:
                container.stop()
                container.remove(force=True)
                logger.info(f"Removed container {container.id} for function {function.id}")
            except Exception as e:
                logger.error(f"Failed to clean up container {container.id}: {e}")

    # Don't maintain pool after every execution as it creates too many containers
    # await maintain_container_pool(client, function)
    client.close()

    if error:
        logger.error(f"Function {function.id} failed: {error}")
        return JSONResponse(
            status_code=500 if status >= 500 else 400,
            content={"status": status, "output": output, "error": error}
        )
    return {"status": status, "output": output}

@app.post("/functions/{function_id}/execute", response_model=schemas.InvokeResponse)
async def execute_function(
    function_id: int,
    request: schemas.InvokeRequest,
    db: AsyncSession = Depends(database.get_db)
):
    """Direct execution endpoint for testing."""
    function = await crud.get_function(db, function_id)
    if not function:
        raise HTTPException(status_code=404, detail="Function not found")

    # Start timing
    start_time = time.time()

    client = DockerClient()
    volume_config = {"/functions": {"bind": "/functions", "mode": "ro"}}
    command = f"python {CONTAINER_FUNCTIONS_DIR}/{function_id}/handler.py" if function.language == "python" else f"node {CONTAINER_FUNCTIONS_DIR}/{function_id}/handler.js"

    # Try to use a warm container from the pool
    container = None
    status = 0
    output = ""
    error = None
    reuse_container = True
    resource_metrics = {}

    async with POOL_LOCK:
        logger.info(f"CONTAINER_POOL before pop: {[(fid, [c.id for c in clist]) for fid, clist in CONTAINER_POOL.items()]}")
        if function_id in CONTAINER_POOL and CONTAINER_POOL[function_id]:
            container = CONTAINER_POOL[function_id].pop(0)  # Take a container
            logger.info(f"Using warm container {container.id} for function {function_id}")
        else:
            logger.info(f"No warm container available for function {function_id}, starting new")
            try:
                container = client.containers.run(
                    function.image_name,
                    command="sleep infinity",
                    volumes=volume_config,
                    mem_limit="128m",
                    network_mode="none",
                    detach=True,
                    remove=False
                )
                logger.info(f"Started new container {container.id} for function {function_id}")
            except DockerException as e:
                # Calculate execution time even for failures
                execution_time_ms = (time.time() - start_time) * 1000
                logger.error(f"Failed to start new container for function {function_id}: {e}")
                status = 500
                error = str(e)
                
                # Save metric for failed container start
                metric_data = schemas.MetricCreate(
                    function_id=function_id,
                    execution_time_ms=execution_time_ms,
                    status_code=status,
                    container_id=None,
                    error=error,
                    payload_size=len(json.dumps(request.payload or {}))
                )
                await crud.create_metric(db, metric_data)
                
                client.close()
                return JSONResponse(
                    status_code=500,
                    content={"status": status, "output": output, "error": error}
                )

    try:
        # Reload container to ensure we have the latest status
        container.reload()
        
        # Ensure container is in a good state
        if container.status not in ["running", "created"]:
            raise DockerException(f"Container in invalid state: {container.status}")
            
        # Debug: Verify volume contents
        debug_output = container.exec_run(f"ls -l {CONTAINER_FUNCTIONS_DIR}/{function_id}").output.decode()
        logger.info(f"Container {container.id} volume contents: {debug_output}")
        
        # Start collecting resource metrics
        pre_exec_metrics = await collect_container_metrics(container)
        
        env = {"PAYLOAD": json.dumps(request.payload or {})}
        exec_result = container.exec_run(command, environment=env)
        status = exec_result.exit_code
        output = exec_result.output.decode()
        
        # Get post-execution metrics
        post_exec_metrics = await collect_container_metrics(container)
        resource_metrics = post_exec_metrics  # Use the post-execution metrics
        
        if status != 0:
            error = output
            output = ""
            reuse_container = False
    except DockerException as e:
        error = str(e)
        status = 500
        reuse_container = False

    # Calculate execution time
    execution_time_ms = (time.time() - start_time) * 1000
    
    # Save metrics
    try:
        metric_data = schemas.MetricCreate(
            function_id=function_id,
            execution_time_ms=execution_time_ms,
            status_code=status,
            container_id=container.id if container else None,
            memory_usage_mb=resource_metrics.get("memory_usage_mb"),
            cpu_usage_percent=resource_metrics.get("cpu_usage_percent"),
            error=error,
            payload_size=len(json.dumps(request.payload or {}))
        )
        await crud.create_metric(db, metric_data)
    except Exception as e:
        logger.error(f"Failed to save metrics: {e}")

    # Clean up or reuse container
    async with POOL_LOCK:
        logger.info(f"Execution status: {status}, reuse_container: {reuse_container}, container_status: {container.status}")
        # Check if container is in a reusable state (created or running)
        if reuse_container and container.status in ["running", "created"]:
            CONTAINER_POOL.setdefault(function_id, []).append(container)
            logger.info(f"Reusing container {container.id} for function {function_id}")
        else:
            try:
                container.stop()
                container.remove(force=True)
                logger.info(f"Removed container {container.id} for function {function_id}")
            except Exception as e:
                logger.error(f"Failed to clean up container {container.id}: {e}")
        logger.info(f"CONTAINER_POOL after: {[(fid, [c.id for c in clist]) for fid, clist in CONTAINER_POOL.items()]}")

    # Don't maintain pool after every execution as it creates too many containers
    # await maintain_container_pool(client, function)
    client.close()

    if error:
        logger.error(f"Function {function_id} failed: {error}")
        return JSONResponse(
            status_code=500 if status >= 500 else 400,
            content={"status": status, "output": output, "error": error}
        )
    return {"status": status, "output": output}

# Metrics endpoints
@app.get("/metrics/function/{function_id}", response_model=List[schemas.Metric])
async def get_function_metrics(
    function_id: int,
    skip: int = 0,
    limit: int = 100,
    db: AsyncSession = Depends(database.get_db)
):
    """Get execution metrics for a specific function."""
    metrics = await crud.get_function_metrics(db, function_id, limit, skip)
    if not metrics:
        raise HTTPException(status_code=404, detail="No metrics found for this function")
    return metrics

@app.get("/metrics/function/{function_id}/summary", response_model=schemas.MetricSummary)
async def get_function_metrics_summary(
    function_id: int,
    days: Optional[int] = Query(None, description="Number of days to include in summary"),
    db: AsyncSession = Depends(database.get_db)
):
    """Get summary of execution metrics for a specific function."""
    time_range = None
    if days:
        end_time = datetime.utcnow()
        start_time = end_time - timedelta(days=days)
        time_range = (start_time, end_time)
    
    summary = await crud.get_metric_summary(db, function_id, time_range)
    if summary is None:
        raise HTTPException(status_code=404, detail="Function not found")
    return summary

@app.get("/metrics/summary", response_model=List[schemas.MetricSummary])
async def get_all_metrics_summary(
    db: AsyncSession = Depends(database.get_db)
):
    """Get summary of execution metrics for all functions."""
    summaries = await crud.get_all_metrics_summary(db)
    return summaries

@app.get("/metrics/function/{function_id}/timeseries")
async def get_function_metrics_timeseries(
    function_id: int,
    period: str = Query("hourly", description="Aggregation period: hourly, daily, or weekly"),
    db: AsyncSession = Depends(database.get_db)
):
    """Get time series data for a function's metrics."""
    if period not in ["hourly", "daily", "weekly"]:
        raise HTTPException(status_code=400, detail="Period must be hourly, daily, or weekly")
    
    metrics = await crud.get_metrics_by_time_period(db, function_id, period)
    return metrics

# Debug endpoints
@app.get("/debug/create-test-function")
async def create_test_function(db: AsyncSession = Depends(database.get_db)):
    """Debug endpoint to create a test function for metrics testing."""
    try:
        # Create a test function
        test_function = schemas.FunctionCreate(
            name="metrics-test-function",
            route="/metrics-test",
            language="python",
            timeout=30,
            code="""
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
""",
            image_name="python-function"
        )
        
        # Create the function in the database
        db_function = await crud.create_function(db, test_function)
        
        # Write the handler file
        temp_dir = f"{HOST_FUNCTIONS_DIR}/{db_function.id}"
        Path(temp_dir).mkdir(parents=True, exist_ok=True)
        handler_path = Path(temp_dir) / "handler.py"
        handler_path.write_text(test_function.code)
        os.sync()
        time.sleep(1)  # Ensure file is synced
        os.chmod(temp_dir, 0o777)
        handler_path.chmod(0o777)
        
        # Start warm containers
        client = DockerClient()
        try:
            await maintain_container_pool(client, db_function)
        finally:
            client.close()
            
        return {
            "message": "Test function created successfully",
            "function_id": db_function.id,
            "name": db_function.name,
            "route": db_function.route
        }
    except Exception as e:
        logger.error(f"Failed to create test function: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to create test function: {str(e)}")

@app.get("/debug/register-existing-function/{function_id}")
async def register_existing_function(
    function_id: int, 
    name: str,
    route: str,
    language: str = "python",
    db: AsyncSession = Depends(database.get_db)
):
    """Register an existing function file in the database."""
    try:
        # Check if the handler file exists
        handler_path = Path(f"{HOST_FUNCTIONS_DIR}/{function_id}/handler.py")
        if not handler_path.exists():
            raise HTTPException(status_code=404, detail=f"Handler file not found at {handler_path}")
        
        # Read the code from the existing file
        code = handler_path.read_text()
        
        # Create the function in the database
        function = schemas.FunctionCreate(
            name=name,
            route=route,
            language=language,
            timeout=30,
            code=code,
            image_name="python-function" if language == "python" else "javascript-function"
        )
        
        # Check if function already exists
        existing = await db.execute(
            select(models.Function).filter(models.Function.id == function_id)
        )
        if existing.scalars().first():
            raise HTTPException(status_code=400, detail=f"Function with ID {function_id} already exists")
        
        # Create a new function with the specified ID
        db_function = models.Function(
            id=function_id,
            **function.dict()
        )
        db.add(db_function)
        await db.commit()
        await db.refresh(db_function)
        
        # Start warm containers
        client = DockerClient()
        try:
            await maintain_container_pool(client, db_function)
        finally:
            client.close()
            
        return {
            "message": "Function registered successfully",
            "function_id": db_function.id,
            "name": db_function.name,
            "route": db_function.route
        }
    except HTTPException as e:
        raise e
    except Exception as e:
        logger.error(f"Failed to register function: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to register function: {str(e)}")

@app.get("/debug/test-function/{function_id}")
async def test_function(
    function_id: int, 
    db: AsyncSession = Depends(database.get_db)
):
    """Debug endpoint to test a function and generate metrics."""
    try:
        # Execute the function with a test payload
        result = await execute_function(
            function_id=function_id,
            request=schemas.InvokeRequest(payload={"test": "data", "timestamp": time.time()}),
            db=db
        )
        return {
            "message": "Function executed successfully",
            "function_id": function_id,
            "result": result
        }
    except Exception as e:
        logger.error(f"Failed to test function: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to test function: {str(e)}")
