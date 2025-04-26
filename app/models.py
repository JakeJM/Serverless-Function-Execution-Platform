from sqlalchemy import Column, Integer, String, DateTime, Float, ForeignKey, JSON
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import relationship
from datetime import datetime

Base = declarative_base()

class Function(Base):
    __tablename__ = "functions"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String, unique=True, index=True)
    route = Column(String, unique=True, index=True)
    language = Column(String)
    timeout = Column(Integer)
    created_at = Column(DateTime, default=datetime.utcnow)
    code = Column(String)
    image_name = Column(String)
    
    # Relationship with metrics
    metrics = relationship("Metric", back_populates="function", cascade="all, delete-orphan")

class Metric(Base):
    __tablename__ = "metrics"
    
    id = Column(Integer, primary_key=True, index=True)
    function_id = Column(Integer, ForeignKey("functions.id"), index=True)
    timestamp = Column(DateTime, default=datetime.utcnow, index=True)
    
    # Performance metrics
    execution_time_ms = Column(Float, index=True)
    memory_usage_mb = Column(Float, nullable=True)
    cpu_usage_percent = Column(Float, nullable=True)
    
    # Status information
    status_code = Column(Integer)
    error = Column(String, nullable=True)
    container_id = Column(String, nullable=True)
    
    # Request information
    payload_size = Column(Integer, nullable=True)
    
    # Additional metadata
    additional_data = Column(JSON, nullable=True)
    
    # Relationship with function
    function = relationship("Function", back_populates="metrics") 
