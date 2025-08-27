"""Logging utilities for the Intelligent PR Assistant MVP."""

import logging
import logging.config
import sys
from datetime import datetime
from typing import Dict, Any, Optional
import json
import os

import structlog
from pythonjsonlogger import jsonlogger

from config.config import config


class JSONFormatter(jsonlogger.JsonFormatter):
    """Custom JSON formatter for structured logging."""
    
    def add_fields(self, log_record: Dict[str, Any], record: logging.LogRecord, message_dict: Dict[str, Any]):
        """Add custom fields to log record."""
        super().add_fields(log_record, record, message_dict)
        
        # Add timestamp
        if not log_record.get('timestamp'):
            log_record['timestamp'] = datetime.utcnow().isoformat()
        
        # Add service information
        log_record['service'] = config.name
        log_record['version'] = config.version
        log_record['environment'] = config.environment
        
        # Add level name
        if log_record.get('level'):
            log_record['level'] = log_record['level'].upper()
        else:
            log_record['level'] = record.levelname


class ContextFilter(logging.Filter):
    """Filter to add contextual information to log records."""
    
    def filter(self, record: logging.LogRecord) -> bool:
        """Add context to log record."""
        # Add process and thread info
        record.process_id = os.getpid()
        record.thread_id = record.thread
        
        # Add module path
        if hasattr(record, 'pathname'):
            # Convert absolute path to relative path
            try:
                record.module_path = os.path.relpath(record.pathname)
            except ValueError:
                record.module_path = record.pathname
        
        return True


class PRAssistantLogger:
    """Custom logger for PR Assistant with structured logging."""
    
    def __init__(self, name: str):
        """Initialize logger with name."""
        self.name = name
        self.logger = logging.getLogger(name)
        self._setup_structlog()
    
    def _setup_structlog(self):
        """Setup structlog for structured logging."""
        structlog.configure(
            processors=[
                structlog.stdlib.filter_by_level,
                structlog.stdlib.add_logger_name,
                structlog.stdlib.add_log_level,
                structlog.stdlib.PositionalArgumentsFormatter(),
                structlog.processors.TimeStamper(fmt="iso"),
                structlog.processors.StackInfoRenderer(),
                structlog.processors.format_exc_info,
                structlog.processors.UnicodeDecoder(),
                structlog.processors.JSONRenderer()
            ],
            context_class=dict,
            logger_factory=structlog.stdlib.LoggerFactory(),
            wrapper_class=structlog.stdlib.BoundLogger,
            cache_logger_on_first_use=True,
        )
        
        self.struct_logger = structlog.get_logger(self.name)
    
    def debug(self, message: str, **kwargs):
        """Log debug message with context."""
        self.struct_logger.debug(message, **kwargs)
    
    def info(self, message: str, **kwargs):
        """Log info message with context."""
        self.struct_logger.info(message, **kwargs)
    
    def warning(self, message: str, **kwargs):
        """Log warning message with context."""
        self.struct_logger.warning(message, **kwargs)
    
    def error(self, message: str, **kwargs):
        """Log error message with context."""
        self.struct_logger.error(message, **kwargs)
    
    def critical(self, message: str, **kwargs):
        """Log critical message with context."""
        self.struct_logger.critical(message, **kwargs)
    
    def log_pr_analysis(self, pr_id: str, score: float, rating: str, duration_ms: float):
        """Log PR analysis event."""
        self.struct_logger.info(
            "PR analysis completed",
            event_type="pr_analysis",
            pr_id=pr_id,
            score=score,
            rating=rating,
            duration_ms=duration_ms
        )
    
    def log_api_request(self, method: str, path: str, status_code: int, duration_ms: float, user_id: Optional[str] = None):
        """Log API request event."""
        self.struct_logger.info(
            "API request processed",
            event_type="api_request",
            method=method,
            path=path,
            status_code=status_code,
            duration_ms=duration_ms,
            user_id=user_id
        )
    
    def log_integration_call(self, service: str, operation: str, success: bool, duration_ms: float, error: Optional[str] = None):
        """Log external integration call."""
        level = "info" if success else "error"
        getattr(self.struct_logger, level)(
            f"{service} integration call",
            event_type="integration_call",
            service=service,
            operation=operation,
            success=success,
            duration_ms=duration_ms,
            error=error
        )
    
    def log_security_event(self, event_type: str, user_id: Optional[str] = None, ip_address: Optional[str] = None, details: Optional[Dict[str, Any]] = None):
        """Log security-related event."""
        self.struct_logger.warning(
            f"Security event: {event_type}",
            event_type="security_event",
            security_event_type=event_type,
            user_id=user_id,
            ip_address=ip_address,
            details=details or {}
        )


def setup_logging():
    """Setup application logging configuration."""
    
    # Get logging configuration
    log_level = getattr(logging, config.logging.level.upper(), logging.INFO)
    log_format = config.logging.format
    log_destinations = config.logging.destinations
    
    # Create formatters
    if log_format.lower() == 'json':
        formatter = JSONFormatter(
            '%(timestamp)s %(level)s %(name)s %(message)s',
            datefmt='%Y-%m-%dT%H:%M:%S'
        )
    else:
        formatter = logging.Formatter(
            '%(asctime)s - %(name)s - %(levelname)s - %(message)s',
            datefmt='%Y-%m-%d %H:%M:%S'
        )
    
    # Setup handlers
    handlers = []
    
    if 'console' in log_destinations:
        console_handler = logging.StreamHandler(sys.stdout)
        console_handler.setFormatter(formatter)
        console_handler.addFilter(ContextFilter())
        handlers.append(console_handler)
    
    if 'file' in log_destinations:
        # Create logs directory if it doesn't exist
        os.makedirs('logs', exist_ok=True)
        
        file_handler = logging.FileHandler('logs/pr_assistant.log')
        file_handler.setFormatter(formatter)
        file_handler.addFilter(ContextFilter())
        handlers.append(file_handler)
    
    # Configure root logger
    logging.basicConfig(
        level=log_level,
        handlers=handlers,
        force=True
    )
    
    # Configure specific loggers
    loggers_config = {
        'uvicorn': {'level': 'INFO'},
        'uvicorn.access': {'level': 'INFO'},
        'fastapi': {'level': 'INFO'},
        'httpx': {'level': 'WARNING'},
        'openai': {'level': 'WARNING'},
        'boto3': {'level': 'WARNING'},
        'botocore': {'level': 'WARNING'},
        'urllib3': {'level': 'WARNING'},
    }
    
    for logger_name, logger_config in loggers_config.items():
        logger = logging.getLogger(logger_name)
        logger.setLevel(getattr(logging, logger_config['level']))
    
    # Log startup message
    logger = logging.getLogger(__name__)
    logger.info(f"Logging configured - Level: {config.logging.level}, Format: {log_format}, Destinations: {log_destinations}")


def get_logger(name: str) -> PRAssistantLogger:
    """Get a configured logger instance."""
    return PRAssistantLogger(name)


class LoggingMiddleware:
    """FastAPI middleware for request/response logging."""
    
    def __init__(self, app):
        self.app = app
        self.logger = get_logger("middleware")
    
    async def __call__(self, scope, receive, send):
        """Process request with logging."""
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return
        
        start_time = datetime.utcnow()
        
        # Extract request info
        method = scope["method"]
        path = scope["path"]
        client_ip = None
        
        if scope.get("client"):
            client_ip = scope["client"][0]
        
        # Process request
        status_code = 500  # Default to error
        
        async def send_wrapper(message):
            nonlocal status_code
            if message["type"] == "http.response.start":
                status_code = message["status"]
            await send(message)
        
        try:
            await self.app(scope, receive, send_wrapper)
        except Exception as e:
            self.logger.error(f"Request processing error: {str(e)}", 
                            method=method, path=path, client_ip=client_ip)
            raise
        finally:
            # Calculate duration
            end_time = datetime.utcnow()
            duration_ms = (end_time - start_time).total_seconds() * 1000
            
            # Log request
            self.logger.log_api_request(
                method=method,
                path=path,
                status_code=status_code,
                duration_ms=duration_ms
            )


class PerformanceTimer:
    """Context manager for timing operations."""
    
    def __init__(self, logger: PRAssistantLogger, operation: str, **context):
        self.logger = logger
        self.operation = operation
        self.context = context
        self.start_time = None
    
    def __enter__(self):
        self.start_time = datetime.utcnow()
        return self
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        if self.start_time:
            duration_ms = (datetime.utcnow() - self.start_time).total_seconds() * 1000
            
            if exc_type is None:
                self.logger.info(f"{self.operation} completed", 
                               duration_ms=duration_ms, **self.context)
            else:
                self.logger.error(f"{self.operation} failed", 
                                duration_ms=duration_ms, 
                                error=str(exc_val), 
                                **self.context)


# Utility functions
def mask_sensitive_data(data: Dict[str, Any], sensitive_keys: list = None) -> Dict[str, Any]:
    """Mask sensitive data in log records."""
    if sensitive_keys is None:
        sensitive_keys = [
            'password', 'token', 'secret', 'key', 'authorization',
            'api_key', 'access_token', 'refresh_token', 'jwt'
        ]
    
    masked_data = {}
    
    for key, value in data.items():
        if any(sensitive_key in key.lower() for sensitive_key in sensitive_keys):
            if isinstance(value, str) and len(value) > 8:
                masked_data[key] = f"{value[:4]}***{value[-4:]}"
            else:
                masked_data[key] = "***"
        elif isinstance(value, dict):
            masked_data[key] = mask_sensitive_data(value, sensitive_keys)
        elif isinstance(value, list):
            masked_data[key] = [
                mask_sensitive_data(item, sensitive_keys) if isinstance(item, dict) else item
                for item in value
            ]
        else:
            masked_data[key] = value
    
    return masked_data


def log_function_call(logger: PRAssistantLogger):
    """Decorator to log function calls."""
    def decorator(func):
        def wrapper(*args, **kwargs):
            func_name = f"{func.__module__}.{func.__name__}"
            
            with PerformanceTimer(logger, f"Function call: {func_name}"):
                try:
                    result = func(*args, **kwargs)
                    return result
                except Exception as e:
                    logger.error(f"Function {func_name} failed", error=str(e))
                    raise
        
        return wrapper
    return decorator


# Export main functions
__all__ = [
    'setup_logging',
    'get_logger',
    'PRAssistantLogger',
    'LoggingMiddleware',
    'PerformanceTimer',
    'mask_sensitive_data',
    'log_function_call'
]
