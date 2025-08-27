"""Redis-based caching manager for performance optimization."""

import json
import logging
from typing import Any, Optional, Dict, List
from datetime import datetime, timedelta
import aioredis
from aioredis import Redis

from config.config import config

logger = logging.getLogger(__name__)


class CacheManager:
    """Redis-based cache manager with TTL support."""
    
    def __init__(self, redis_url: str = "redis://localhost:6379"):
        """Initialize cache manager."""
        self.redis_url = redis_url
        self.redis: Optional[Redis] = None
        self.default_ttl = 3600  # 1 hour default TTL
        
    async def connect(self):
        """Connect to Redis."""
        try:
            self.redis = await aioredis.from_url(
                self.redis_url,
                encoding="utf-8",
                decode_responses=True
            )
            await self.redis.ping()
            logger.info("Connected to Redis cache")
        except Exception as e:
            logger.error(f"Failed to connect to Redis: {str(e)}")
            self.redis = None
    
    async def disconnect(self):
        """Disconnect from Redis."""
        if self.redis:
            await self.redis.close()
            logger.info("Disconnected from Redis cache")
    
    async def get(self, key: str) -> Optional[Any]:
        """Get value from cache."""
        if not self.redis:
            return None
        
        try:
            value = await self.redis.get(key)
            if value:
                return json.loads(value)
            return None
        except Exception as e:
            logger.error(f"Cache get error for key {key}: {str(e)}")
            return None
    
    async def set(self, key: str, value: Any, ttl: Optional[int] = None) -> bool:
        """Set value in cache with TTL."""
        if not self.redis:
            return False
        
        try:
            ttl = ttl or self.default_ttl
            serialized_value = json.dumps(value, default=str)
            await self.redis.setex(key, ttl, serialized_value)
            return True
        except Exception as e:
            logger.error(f"Cache set error for key {key}: {str(e)}")
            return False
    
    async def delete(self, key: str) -> bool:
        """Delete key from cache."""
        if not self.redis:
            return False
        
        try:
            await self.redis.delete(key)
            return True
        except Exception as e:
            logger.error(f"Cache delete error for key {key}: {str(e)}")
            return False
    
    async def exists(self, key: str) -> bool:
        """Check if key exists in cache."""
        if not self.redis:
            return False
        
        try:
            return bool(await self.redis.exists(key))
        except Exception as e:
            logger.error(f"Cache exists error for key {key}: {str(e)}")
            return False
    
    async def get_many(self, keys: List[str]) -> Dict[str, Any]:
        """Get multiple values from cache."""
        if not self.redis or not keys:
            return {}
        
        try:
            values = await self.redis.mget(keys)
            result = {}
            for key, value in zip(keys, values):
                if value:
                    try:
                        result[key] = json.loads(value)
                    except json.JSONDecodeError:
                        logger.warning(f"Failed to decode cached value for key {key}")
            return result
        except Exception as e:
            logger.error(f"Cache get_many error: {str(e)}")
            return {}
    
    async def set_many(self, data: Dict[str, Any], ttl: Optional[int] = None) -> bool:
        """Set multiple values in cache."""
        if not self.redis or not data:
            return False
        
        try:
            ttl = ttl or self.default_ttl
            pipe = self.redis.pipeline()
            
            for key, value in data.items():
                serialized_value = json.dumps(value, default=str)
                pipe.setex(key, ttl, serialized_value)
            
            await pipe.execute()
            return True
        except Exception as e:
            logger.error(f"Cache set_many error: {str(e)}")
            return False
    
    async def increment(self, key: str, amount: int = 1) -> Optional[int]:
        """Increment a counter in cache."""
        if not self.redis:
            return None
        
        try:
            return await self.redis.incrby(key, amount)
        except Exception as e:
            logger.error(f"Cache increment error for key {key}: {str(e)}")
            return None
    
    async def expire(self, key: str, ttl: int) -> bool:
        """Set expiration time for a key."""
        if not self.redis:
            return False
        
        try:
            return bool(await self.redis.expire(key, ttl))
        except Exception as e:
            logger.error(f"Cache expire error for key {key}: {str(e)}")
            return False
    
    async def clear_pattern(self, pattern: str) -> int:
        """Clear all keys matching a pattern."""
        if not self.redis:
            return 0
        
        try:
            keys = await self.redis.keys(pattern)
            if keys:
                return await self.redis.delete(*keys)
            return 0
        except Exception as e:
            logger.error(f"Cache clear_pattern error for pattern {pattern}: {str(e)}")
            return 0
    
    async def get_stats(self) -> Dict[str, Any]:
        """Get cache statistics."""
        if not self.redis:
            return {}
        
        try:
            info = await self.redis.info()
            return {
                "connected_clients": info.get("connected_clients", 0),
                "used_memory": info.get("used_memory", 0),
                "used_memory_human": info.get("used_memory_human", "0B"),
                "keyspace_hits": info.get("keyspace_hits", 0),
                "keyspace_misses": info.get("keyspace_misses", 0),
                "total_commands_processed": info.get("total_commands_processed", 0)
            }
        except Exception as e:
            logger.error(f"Cache stats error: {str(e)}")
            return {}


class CacheKeys:
    """Cache key constants and generators."""
    
    # PR Analysis Cache
    PR_ANALYSIS = "pr_analysis:{pr_id}"
    PR_SUGGESTIONS = "pr_suggestions:{pr_id}"
    PR_JIRA_CONTEXT = "pr_jira:{pr_id}"
    
    # Jira Cache
    JIRA_TICKET = "jira_ticket:{ticket_key}"
    JIRA_PROJECT = "jira_project:{project_key}"
    JIRA_USER = "jira_user:{user_id}"
    
    # Analytics Cache
    TEAM_METRICS = "team_metrics:{team_id}:{days}"
    DEVELOPER_METRICS = "developer_metrics:{developer_id}:{days}"
    REPOSITORY_METRICS = "repository_metrics:{repository_id}:{days}"
    
    # System Cache
    SYSTEM_CONFIG = "system_config"
    HEALTH_STATUS = "health_status"
    
    @staticmethod
    def pr_analysis(pr_id: str) -> str:
        """Generate PR analysis cache key."""
        return CacheKeys.PR_ANALYSIS.format(pr_id=pr_id)
    
    @staticmethod
    def pr_suggestions(pr_id: str) -> str:
        """Generate PR suggestions cache key."""
        return CacheKeys.PR_SUGGESTIONS.format(pr_id=pr_id)
    
    @staticmethod
    def jira_ticket(ticket_key: str) -> str:
        """Generate Jira ticket cache key."""
        return CacheKeys.JIRA_TICKET.format(ticket_key=ticket_key)
    
    @staticmethod
    def team_metrics(team_id: str, days: int) -> str:
        """Generate team metrics cache key."""
        return CacheKeys.TEAM_METRICS.format(team_id=team_id, days=days)
    
    @staticmethod
    def developer_metrics(developer_id: str, days: int) -> str:
        """Generate developer metrics cache key."""
        return CacheKeys.DEVELOPER_METRICS.format(developer_id=developer_id, days=days)
    
    @staticmethod
    def repository_metrics(repository_id: str, days: int) -> str:
        """Generate repository metrics cache key."""
        return CacheKeys.REPOSITORY_METRICS.format(repository_id=repository_id, days=days)


# Global cache manager instance
cache_manager: Optional[CacheManager] = None


def create_cache_manager() -> CacheManager:
    """Create and return cache manager instance."""
    global cache_manager
    if cache_manager is None:
        redis_url = getattr(config, 'redis_url', 'redis://localhost:6379')
        cache_manager = CacheManager(redis_url)
    return cache_manager


async def get_cache_manager() -> Optional[CacheManager]:
    """Get the global cache manager instance."""
    global cache_manager
    if cache_manager is None:
        cache_manager = create_cache_manager()
        await cache_manager.connect()
    return cache_manager
