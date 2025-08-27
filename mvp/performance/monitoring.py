"""Performance monitoring and metrics collection."""

import time
import logging
import asyncio
from typing import Dict, Any, Optional, List
from datetime import datetime, timedelta
from dataclasses import dataclass, field
from prometheus_client import Counter, Histogram, Gauge, CollectorRegistry, generate_latest
import psutil
import threading

from config.config import config

logger = logging.getLogger(__name__)


@dataclass
class MetricPoint:
    """Individual metric data point."""
    name: str
    value: float
    labels: Dict[str, str] = field(default_factory=dict)
    timestamp: datetime = field(default_factory=datetime.utcnow)
    unit: str = "count"


class PerformanceMonitor:
    """System performance monitoring and metrics collection."""
    
    def __init__(self):
        """Initialize performance monitor."""
        self.registry = CollectorRegistry()
        self.metrics = {}
        self.system_metrics = {}
        self.start_time = time.time()
        self._monitoring_active = False
        self._monitoring_task = None
        
        # Initialize Prometheus metrics
        self._init_prometheus_metrics()
        
    def _init_prometheus_metrics(self):
        """Initialize Prometheus metrics."""
        # Request metrics
        self.request_count = Counter(
            'pr_assistant_requests_total',
            'Total number of requests',
            ['method', 'endpoint', 'status'],
            registry=self.registry
        )
        
        self.request_duration = Histogram(
            'pr_assistant_request_duration_seconds',
            'Request duration in seconds',
            ['method', 'endpoint'],
            registry=self.registry
        )
        
        # AI Engine metrics
        self.ai_requests = Counter(
            'pr_assistant_ai_requests_total',
            'Total AI API requests',
            ['model', 'status'],
            registry=self.registry
        )
        
        self.ai_duration = Histogram(
            'pr_assistant_ai_duration_seconds',
            'AI request duration in seconds',
            ['model'],
            registry=self.registry
        )
        
        # Cache metrics
        self.cache_hits = Counter(
            'pr_assistant_cache_hits_total',
            'Total cache hits',
            ['cache_type'],
            registry=self.registry
        )
        
        self.cache_misses = Counter(
            'pr_assistant_cache_misses_total',
            'Total cache misses',
            ['cache_type'],
            registry=self.registry
        )
        
        # Database metrics
        self.db_queries = Counter(
            'pr_assistant_db_queries_total',
            'Total database queries',
            ['operation', 'table'],
            registry=self.registry
        )
        
        self.db_duration = Histogram(
            'pr_assistant_db_duration_seconds',
            'Database query duration in seconds',
            ['operation', 'table'],
            registry=self.registry
        )
        
        # System metrics
        self.system_cpu = Gauge(
            'pr_assistant_system_cpu_percent',
            'System CPU usage percentage',
            registry=self.registry
        )
        
        self.system_memory = Gauge(
            'pr_assistant_system_memory_percent',
            'System memory usage percentage',
            registry=self.registry
        )
        
        self.system_disk = Gauge(
            'pr_assistant_system_disk_percent',
            'System disk usage percentage',
            registry=self.registry
        )
        
        # Application metrics
        self.active_connections = Gauge(
            'pr_assistant_active_connections',
            'Number of active connections',
            registry=self.registry
        )
        
        self.uptime = Gauge(
            'pr_assistant_uptime_seconds',
            'Application uptime in seconds',
            registry=self.registry
        )
    
    async def start_monitoring(self):
        """Start background monitoring."""
        if self._monitoring_active:
            return
        
        self._monitoring_active = True
        self._monitoring_task = asyncio.create_task(self._monitoring_loop())
        logger.info("Performance monitoring started")
    
    async def stop_monitoring(self):
        """Stop background monitoring."""
        self._monitoring_active = False
        if self._monitoring_task:
            self._monitoring_task.cancel()
            try:
                await self._monitoring_task
            except asyncio.CancelledError:
                pass
        logger.info("Performance monitoring stopped")
    
    async def _monitoring_loop(self):
        """Background monitoring loop."""
        while self._monitoring_active:
            try:
                await self._collect_system_metrics()
                await asyncio.sleep(30)  # Collect every 30 seconds
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Error in monitoring loop: {str(e)}")
                await asyncio.sleep(60)  # Wait longer on error
    
    async def _collect_system_metrics(self):
        """Collect system performance metrics."""
        try:
            # CPU usage
            cpu_percent = psutil.cpu_percent(interval=1)
            self.system_cpu.set(cpu_percent)
            
            # Memory usage
            memory = psutil.virtual_memory()
            self.system_memory.set(memory.percent)
            
            # Disk usage
            disk = psutil.disk_usage('/')
            disk_percent = (disk.used / disk.total) * 100
            self.system_disk.set(disk_percent)
            
            # Uptime
            uptime = time.time() - self.start_time
            self.uptime.set(uptime)
            
            # Store for internal use
            self.system_metrics.update({
                'cpu_percent': cpu_percent,
                'memory_percent': memory.percent,
                'memory_available': memory.available,
                'disk_percent': disk_percent,
                'disk_free': disk.free,
                'uptime': uptime,
                'timestamp': datetime.utcnow()
            })
            
        except Exception as e:
            logger.error(f"Error collecting system metrics: {str(e)}")
    
    def record_request(self, method: str, endpoint: str, status_code: int, duration: float):
        """Record HTTP request metrics."""
        self.request_count.labels(
            method=method,
            endpoint=endpoint,
            status=str(status_code)
        ).inc()
        
        self.request_duration.labels(
            method=method,
            endpoint=endpoint
        ).observe(duration)
    
    def record_ai_request(self, model: str, status: str, duration: float):
        """Record AI API request metrics."""
        self.ai_requests.labels(
            model=model,
            status=status
        ).inc()
        
        self.ai_duration.labels(model=model).observe(duration)
    
    def record_cache_hit(self, cache_type: str):
        """Record cache hit."""
        self.cache_hits.labels(cache_type=cache_type).inc()
    
    def record_cache_miss(self, cache_type: str):
        """Record cache miss."""
        self.cache_misses.labels(cache_type=cache_type).inc()
    
    def record_db_query(self, operation: str, table: str, duration: float):
        """Record database query metrics."""
        self.db_queries.labels(
            operation=operation,
            table=table
        ).inc()
        
        self.db_duration.labels(
            operation=operation,
            table=table
        ).observe(duration)
    
    def set_active_connections(self, count: int):
        """Set number of active connections."""
        self.active_connections.set(count)
    
    def get_metrics_summary(self) -> Dict[str, Any]:
        """Get current metrics summary."""
        return {
            'system': self.system_metrics.copy(),
            'uptime': time.time() - self.start_time,
            'timestamp': datetime.utcnow().isoformat()
        }
    
    def get_prometheus_metrics(self) -> str:
        """Get Prometheus formatted metrics."""
        return generate_latest(self.registry).decode('utf-8')


class RequestTimer:
    """Context manager for timing requests."""
    
    def __init__(self, monitor: PerformanceMonitor, method: str, endpoint: str):
        """Initialize request timer."""
        self.monitor = monitor
        self.method = method
        self.endpoint = endpoint
        self.start_time = None
        self.status_code = 200
    
    def __enter__(self):
        """Start timing."""
        self.start_time = time.time()
        return self
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        """End timing and record metrics."""
        if self.start_time:
            duration = time.time() - self.start_time
            if exc_type:
                self.status_code = 500
            self.monitor.record_request(
                self.method,
                self.endpoint,
                self.status_code,
                duration
            )
    
    def set_status(self, status_code: int):
        """Set response status code."""
        self.status_code = status_code


class LoadBalancer:
    """Simple round-robin load balancer for multiple instances."""
    
    def __init__(self, instances: List[str]):
        """Initialize load balancer."""
        self.instances = instances
        self.current_index = 0
        self.health_status = {instance: True for instance in instances}
        self._lock = threading.Lock()
    
    def get_next_instance(self) -> Optional[str]:
        """Get next available instance."""
        with self._lock:
            if not self.instances:
                return None
            
            # Find next healthy instance
            attempts = 0
            while attempts < len(self.instances):
                instance = self.instances[self.current_index]
                self.current_index = (self.current_index + 1) % len(self.instances)
                
                if self.health_status.get(instance, False):
                    return instance
                
                attempts += 1
            
            # No healthy instances found
            return None
    
    def mark_unhealthy(self, instance: str):
        """Mark instance as unhealthy."""
        with self._lock:
            self.health_status[instance] = False
            logger.warning(f"Instance marked unhealthy: {instance}")
    
    def mark_healthy(self, instance: str):
        """Mark instance as healthy."""
        with self._lock:
            self.health_status[instance] = True
            logger.info(f"Instance marked healthy: {instance}")
    
    async def health_check_all(self):
        """Perform health check on all instances."""
        import aiohttp
        
        async with aiohttp.ClientSession() as session:
            for instance in self.instances:
                try:
                    async with session.get(f"{instance}/health", timeout=5) as response:
                        if response.status == 200:
                            self.mark_healthy(instance)
                        else:
                            self.mark_unhealthy(instance)
                except Exception as e:
                    logger.error(f"Health check failed for {instance}: {str(e)}")
                    self.mark_unhealthy(instance)
    
    def get_status(self) -> Dict[str, Any]:
        """Get load balancer status."""
        with self._lock:
            healthy_count = sum(1 for status in self.health_status.values() if status)
            return {
                'total_instances': len(self.instances),
                'healthy_instances': healthy_count,
                'unhealthy_instances': len(self.instances) - healthy_count,
                'instances': [
                    {
                        'url': instance,
                        'healthy': self.health_status.get(instance, False)
                    }
                    for instance in self.instances
                ]
            }


class HealthChecker:
    """Application health checker."""
    
    def __init__(self):
        """Initialize health checker."""
        self.checks = {}
        self.last_check_time = None
        self.last_results = {}
    
    def register_check(self, name: str, check_func):
        """Register a health check function."""
        self.checks[name] = check_func
    
    async def run_checks(self) -> Dict[str, Any]:
        """Run all health checks."""
        results = {}
        overall_healthy = True
        
        for name, check_func in self.checks.items():
            try:
                start_time = time.time()
                result = await check_func() if asyncio.iscoroutinefunction(check_func) else check_func()
                duration = time.time() - start_time
                
                results[name] = {
                    'healthy': bool(result),
                    'duration': duration,
                    'timestamp': datetime.utcnow().isoformat()
                }
                
                if not result:
                    overall_healthy = False
                    
            except Exception as e:
                results[name] = {
                    'healthy': False,
                    'error': str(e),
                    'timestamp': datetime.utcnow().isoformat()
                }
                overall_healthy = False
        
        self.last_check_time = datetime.utcnow()
        self.last_results = results
        
        return {
            'healthy': overall_healthy,
            'checks': results,
            'timestamp': self.last_check_time.isoformat()
        }
    
    def get_last_results(self) -> Dict[str, Any]:
        """Get last health check results."""
        return {
            'healthy': all(check.get('healthy', False) for check in self.last_results.values()),
            'checks': self.last_results,
            'last_check': self.last_check_time.isoformat() if self.last_check_time else None
        }


# Global instances
performance_monitor: Optional[PerformanceMonitor] = None
health_checker: Optional[HealthChecker] = None


def create_performance_monitor() -> PerformanceMonitor:
    """Create and return performance monitor instance."""
    global performance_monitor
    if performance_monitor is None:
        performance_monitor = PerformanceMonitor()
    return performance_monitor


def create_health_checker() -> HealthChecker:
    """Create and return health checker instance."""
    global health_checker
    if health_checker is None:
        health_checker = HealthChecker()
    return health_checker


def get_performance_monitor() -> PerformanceMonitor:
    """Get the global performance monitor instance."""
    global performance_monitor
    if performance_monitor is None:
        performance_monitor = create_performance_monitor()
    return performance_monitor


def get_health_checker() -> HealthChecker:
    """Get the global health checker instance."""
    global health_checker
    if health_checker is None:
        health_checker = create_health_checker()
    return health_checker
