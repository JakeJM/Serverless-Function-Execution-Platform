from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func, and_, case
from sqlalchemy.sql import text
from . import models, schemas
from typing import List, Optional, Dict, Any, Tuple
from datetime import datetime, timedelta

async def create_function(db: AsyncSession, function: schemas.FunctionCreate):
    db_function = models.Function(**function.dict())
    db.add(db_function)
    await db.commit()
    await db.refresh(db_function)
    return db_function

async def get_function(db: AsyncSession, function_id: int):
    return await db.get(models.Function, function_id)

async def get_all_functions(db: AsyncSession):
    result = await db.execute(select(models.Function))
    return result.scalars().all()

async def update_function(db: AsyncSession, function_id: int, function: schemas.FunctionCreate):
    db_function = await get_function(db, function_id)
    if db_function:
        for key, value in function.dict().items():
            setattr(db_function, key, value)
        await db.commit()
        await db.refresh(db_function)
    return db_function

async def delete_function(db: AsyncSession, function_id: int):
    db_function = await get_function(db, function_id)
    if db_function:
        await db.delete(db_function)
        await db.commit()
    return db_function

# Metrics CRUD operations
async def create_metric(db: AsyncSession, metric: schemas.MetricCreate):
    db_metric = models.Metric(**metric.dict())
    db.add(db_metric)
    await db.commit()
    await db.refresh(db_metric)
    return db_metric

async def get_function_metrics(db: AsyncSession, function_id: int, limit: int = 100, skip: int = 0):
    result = await db.execute(
        select(models.Metric)
        .filter(models.Metric.function_id == function_id)
        .order_by(models.Metric.timestamp.desc())
        .offset(skip)
        .limit(limit)
    )
    return result.scalars().all()

async def get_metric_summary(db: AsyncSession, function_id: int, 
                             time_range: Optional[Tuple[datetime, datetime]] = None):
    """Get summary statistics for a function's metrics within optional time range."""
    # First check if the function exists
    function = await get_function(db, function_id)
    if not function:
        return None  # Function not found
    
    # Check if any metrics exist for this function
    metrics_exist_query = select(func.count()).select_from(models.Metric).filter(models.Metric.function_id == function_id)
    metrics_count_result = await db.execute(metrics_exist_query)
    metrics_count = metrics_count_result.scalar_one()
    
    if metrics_count == 0:
        # No metrics exist for this function
        return {
            "function_id": function_id,
            "function_name": function.name,
            "avg_execution_time_ms": 0.0,
            "min_execution_time_ms": 0.0,
            "max_execution_time_ms": 0.0,
            "error_count": 0,
            "success_count": 0,
            "total_executions": 0,
            "avg_memory_usage_mb": None,
            "avg_cpu_usage_percent": None
        }
    
    # Metrics exist, get the summary
    query = select(
        models.Function.id,
        models.Function.name,
        func.avg(models.Metric.execution_time_ms).label("avg_execution_time_ms"),
        func.min(models.Metric.execution_time_ms).label("min_execution_time_ms"),
        func.max(models.Metric.execution_time_ms).label("max_execution_time_ms"),
        func.sum(case((models.Metric.status_code >= 400, 1), else_=0)).label("error_count"),
        func.sum(case((models.Metric.status_code < 400, 1), else_=0)).label("success_count"),
        func.count().label("total_executions"),
        func.avg(models.Metric.memory_usage_mb).label("avg_memory_usage_mb"),
        func.avg(models.Metric.cpu_usage_percent).label("avg_cpu_usage_percent")
    ).join(
        models.Function, models.Metric.function_id == models.Function.id
    ).filter(
        models.Metric.function_id == function_id
    )
    
    # Apply time range filter if provided
    if time_range:
        start_time, end_time = time_range
        query = query.filter(
            models.Metric.timestamp >= start_time,
            models.Metric.timestamp <= end_time
        )
    
    query = query.group_by(models.Function.id, models.Function.name)
    
    try:
        result = await db.execute(query)
        row = result.first()
        
        if row:
            return dict(row._mapping)
        else:
            # This should not happen if we've checked metrics_count > 0, but just in case
            return {
                "function_id": function_id,
                "function_name": function.name,
                "avg_execution_time_ms": 0.0,
                "min_execution_time_ms": 0.0,
                "max_execution_time_ms": 0.0,
                "error_count": 0,
                "success_count": 0,
                "total_executions": 0,
                "avg_memory_usage_mb": None,
                "avg_cpu_usage_percent": None
            }
    except Exception as e:
        # Log the error and return a default response
        print(f"Error in get_metric_summary: {e}")
        return {
            "function_id": function_id,
            "function_name": function.name,
            "avg_execution_time_ms": 0.0,
            "min_execution_time_ms": 0.0,
            "max_execution_time_ms": 0.0,
            "error_count": 0,
            "success_count": 0,
            "total_executions": metrics_count,
            "avg_memory_usage_mb": None,
            "avg_cpu_usage_percent": None
        }

async def get_all_metrics_summary(db: AsyncSession):
    """Get summary statistics for all functions."""
    try:
        query = select(
            models.Function.id,
            models.Function.name,
            func.avg(models.Metric.execution_time_ms).label("avg_execution_time_ms"),
            func.min(models.Metric.execution_time_ms).label("min_execution_time_ms"),
            func.max(models.Metric.execution_time_ms).label("max_execution_time_ms"),
            func.sum(case((models.Metric.status_code >= 400, 1), else_=0)).label("error_count"),
            func.sum(case((models.Metric.status_code < 400, 1), else_=0)).label("success_count"),
            func.count().label("total_executions"),
            func.avg(models.Metric.memory_usage_mb).label("avg_memory_usage_mb"),
            func.avg(models.Metric.cpu_usage_percent).label("avg_cpu_usage_percent")
        ).join(
            models.Function, models.Metric.function_id == models.Function.id
        ).group_by(
            models.Function.id, models.Function.name
        )
        
        result = await db.execute(query)
        rows = result.all()
        
        return [dict(row._mapping) for row in rows]
    except Exception as e:
        print(f"Error in get_all_metrics_summary: {e}")
        # Return empty list on error
        return []

async def get_metrics_by_time_period(db: AsyncSession, function_id: int, period: str):
    """
    Get metrics aggregated by time period.
    period can be 'hourly', 'daily', or 'weekly'
    """
    # First check if the function exists
    function = await get_function(db, function_id)
    if not function:
        return []  # Function not found, return empty list
        
    time_format = (
        "YYYY-MM-DD HH24:00:00" if period == 'hourly' else
        "YYYY-MM-DD" if period == 'daily' else
        "YYYY-WW"  # weekly
    )
    
    try:
        query = text(f"""
            SELECT 
                TO_CHAR(timestamp, :time_format) as time_period,
                AVG(execution_time_ms) as avg_execution_time_ms,
                COUNT(*) as invocation_count,
                SUM(CASE WHEN status_code >= 400 THEN 1 ELSE 0 END) as error_count
            FROM metrics
            WHERE function_id = :function_id
            GROUP BY time_period
            ORDER BY time_period
        """)
        
        result = await db.execute(
            query, 
            {"function_id": function_id, "time_format": time_format}
        )
        
        return [dict(row._mapping) for row in result]
    except Exception as e:
        print(f"Error in get_metrics_by_time_period: {e}")
        return []  # Return empty list on error
