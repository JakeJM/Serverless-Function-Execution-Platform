from pydantic import BaseModel
from datetime import datetime
from typing import Optional, Dict, List, Any

class FunctionBase(BaseModel):
    name: str
    route: str
    language: str
    timeout: int
    code: str
    image_name: str

class FunctionCreate(FunctionBase):
    pass

class MetricBase(BaseModel):
    function_id: int
    execution_time_ms: float
    status_code: int
    container_id: Optional[str] = None
    memory_usage_mb: Optional[float] = None
    cpu_usage_percent: Optional[float] = None
    error: Optional[str] = None
    payload_size: Optional[int] = None
    additional_data: Optional[Dict[str, Any]] = None

class MetricCreate(MetricBase):
    pass

class Metric(MetricBase):
    id: int
    timestamp: datetime

    class Config:
        from_attributes = True

class Function(FunctionBase):
    id: int
    created_at: datetime

    class Config:
        from_attributes = True

class FunctionWithMetrics(Function):
    metrics: List[Metric] = []

class MetricSummary(BaseModel):
    function_id: int
    function_name: str
    avg_execution_time_ms: float
    min_execution_time_ms: float
    max_execution_time_ms: float
    error_count: int
    success_count: int
    total_executions: int
    avg_memory_usage_mb: Optional[float] = None
    avg_cpu_usage_percent: Optional[float] = None

class InvokeRequest(BaseModel):
    payload: Optional[Dict] = None

class InvokeResponse(BaseModel):
    status: int
    output: str
    error: Optional[str] = None
