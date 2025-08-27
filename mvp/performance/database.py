"""Database integration layer with SQLAlchemy and async support."""

import logging
from typing import Optional, Dict, Any, List
from datetime import datetime
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine, async_sessionmaker
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column
from sqlalchemy import String, Integer, Float, DateTime, Text, JSON, Boolean, Index
from sqlalchemy.dialects.postgresql import UUID
import uuid

from config.config import config

logger = logging.getLogger(__name__)


class Base(DeclarativeBase):
    """Base class for all database models."""
    pass


class PRAnalysis(Base):
    """PR analysis results storage."""
    
    __tablename__ = "pr_analyses"
    
    id: Mapped[str] = mapped_column(UUID(as_uuid=False), primary_key=True, default=lambda: str(uuid.uuid4()))
    pr_id: Mapped[str] = mapped_column(String(100), nullable=False, index=True)
    repository: Mapped[str] = mapped_column(String(200), nullable=False, index=True)
    workspace: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    title: Mapped[str] = mapped_column(String(500), nullable=False)
    description: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    
    # Scoring results
    total_score: Mapped[float] = mapped_column(Float, nullable=False)
    rating: Mapped[str] = mapped_column(String(50), nullable=False)
    breakdown: Mapped[Dict[str, Any]] = mapped_column(JSON, nullable=False)
    suggestions: Mapped[List[str]] = mapped_column(JSON, nullable=False)
    
    # Jira context
    jira_ticket_key: Mapped[Optional[str]] = mapped_column(String(50), nullable=True, index=True)
    jira_context: Mapped[Optional[Dict[str, Any]]] = mapped_column(JSON, nullable=True)
    
    # Metadata
    analyzed_by: Mapped[str] = mapped_column(String(100), nullable=False)
    analyzed_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, default=datetime.utcnow)
    created_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # Indexes
    __table_args__ = (
        Index('idx_pr_repository', 'pr_id', 'repository'),
        Index('idx_analyzed_at', 'analyzed_at'),
        Index('idx_total_score', 'total_score'),
    )


class JiraTicketCache(Base):
    """Jira ticket information cache."""
    
    __tablename__ = "jira_ticket_cache"
    
    id: Mapped[str] = mapped_column(UUID(as_uuid=False), primary_key=True, default=lambda: str(uuid.uuid4()))
    ticket_key: Mapped[str] = mapped_column(String(50), nullable=False, unique=True, index=True)
    project_key: Mapped[str] = mapped_column(String(20), nullable=False, index=True)
    
    # Ticket data
    summary: Mapped[str] = mapped_column(String(500), nullable=False)
    description: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    status: Mapped[str] = mapped_column(String(50), nullable=False)
    priority: Mapped[str] = mapped_column(String(50), nullable=False)
    assignee: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    reporter: Mapped[str] = mapped_column(String(100), nullable=False)
    
    # Raw ticket data
    raw_data: Mapped[Dict[str, Any]] = mapped_column(JSON, nullable=False)
    
    # Cache metadata
    cached_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, default=datetime.utcnow)
    expires_at: Mapped[datetime] = mapped_column(DateTime, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, default=datetime.utcnow, onupdate=datetime.utcnow)


class TeamMetrics(Base):
    """Team performance metrics storage."""
    
    __tablename__ = "team_metrics"
    
    id: Mapped[str] = mapped_column(UUID(as_uuid=False), primary_key=True, default=lambda: str(uuid.uuid4()))
    team_id: Mapped[str] = mapped_column(String(100), nullable=False, index=True)
    period_start: Mapped[datetime] = mapped_column(DateTime, nullable=False, index=True)
    period_end: Mapped[datetime] = mapped_column(DateTime, nullable=False, index=True)
    
    # Metrics
    total_prs: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    avg_score: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    avg_review_time: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    compliance_rate: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    
    # Detailed metrics
    metrics_data: Mapped[Dict[str, Any]] = mapped_column(JSON, nullable=False)
    
    # Metadata
    calculated_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, default=datetime.utcnow)
    created_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # Indexes
    __table_args__ = (
        Index('idx_team_period', 'team_id', 'period_start', 'period_end'),
    )


class DeveloperMetrics(Base):
    """Developer performance metrics storage."""
    
    __tablename__ = "developer_metrics"
    
    id: Mapped[str] = mapped_column(UUID(as_uuid=False), primary_key=True, default=lambda: str(uuid.uuid4()))
    developer_id: Mapped[str] = mapped_column(String(100), nullable=False, index=True)
    team_id: Mapped[Optional[str]] = mapped_column(String(100), nullable=True, index=True)
    period_start: Mapped[datetime] = mapped_column(DateTime, nullable=False, index=True)
    period_end: Mapped[datetime] = mapped_column(DateTime, nullable=False, index=True)
    
    # Metrics
    total_prs: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    avg_score: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    improvement_trend: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    
    # Detailed metrics
    metrics_data: Mapped[Dict[str, Any]] = mapped_column(JSON, nullable=False)
    
    # Metadata
    calculated_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, default=datetime.utcnow)
    created_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # Indexes
    __table_args__ = (
        Index('idx_developer_period', 'developer_id', 'period_start', 'period_end'),
    )


class SystemMetrics(Base):
    """System performance and usage metrics."""
    
    __tablename__ = "system_metrics"
    
    id: Mapped[str] = mapped_column(UUID(as_uuid=False), primary_key=True, default=lambda: str(uuid.uuid4()))
    metric_type: Mapped[str] = mapped_column(String(50), nullable=False, index=True)
    metric_name: Mapped[str] = mapped_column(String(100), nullable=False, index=True)
    
    # Metric values
    value: Mapped[float] = mapped_column(Float, nullable=False)
    unit: Mapped[str] = mapped_column(String(20), nullable=False)
    
    # Additional data
    labels: Mapped[Optional[Dict[str, Any]]] = mapped_column(JSON, nullable=True)
    metadata: Mapped[Optional[Dict[str, Any]]] = mapped_column(JSON, nullable=True)
    
    # Timestamp
    timestamp: Mapped[datetime] = mapped_column(DateTime, nullable=False, default=datetime.utcnow, index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, default=datetime.utcnow)
    
    # Indexes
    __table_args__ = (
        Index('idx_metric_type_name', 'metric_type', 'metric_name'),
        Index('idx_timestamp', 'timestamp'),
    )


class DatabaseManager:
    """Database connection and session management."""
    
    def __init__(self, database_url: str):
        """Initialize database manager."""
        self.database_url = database_url
        self.engine = None
        self.session_factory = None
        
    async def initialize(self):
        """Initialize database connection and create tables."""
        try:
            # Create async engine
            self.engine = create_async_engine(
                self.database_url,
                echo=config.debug,
                pool_pre_ping=True,
                pool_recycle=3600
            )
            
            # Create session factory
            self.session_factory = async_sessionmaker(
                self.engine,
                class_=AsyncSession,
                expire_on_commit=False
            )
            
            # Create tables
            async with self.engine.begin() as conn:
                await conn.run_sync(Base.metadata.create_all)
            
            logger.info("Database initialized successfully")
            
        except Exception as e:
            logger.error(f"Failed to initialize database: {str(e)}")
            raise
    
    async def close(self):
        """Close database connections."""
        if self.engine:
            await self.engine.dispose()
            logger.info("Database connections closed")
    
    def get_session(self) -> AsyncSession:
        """Get database session."""
        if not self.session_factory:
            raise RuntimeError("Database not initialized")
        return self.session_factory()
    
    async def health_check(self) -> bool:
        """Check database health."""
        try:
            async with self.get_session() as session:
                await session.execute("SELECT 1")
                return True
        except Exception as e:
            logger.error(f"Database health check failed: {str(e)}")
            return False


class PRAnalysisRepository:
    """Repository for PR analysis data operations."""
    
    def __init__(self, db_manager: DatabaseManager):
        """Initialize repository."""
        self.db_manager = db_manager
    
    async def save_analysis(self, analysis_data: Dict[str, Any]) -> str:
        """Save PR analysis to database."""
        async with self.db_manager.get_session() as session:
            analysis = PRAnalysis(
                pr_id=analysis_data['pr_id'],
                repository=analysis_data['repository'],
                workspace=analysis_data.get('workspace'),
                title=analysis_data['title'],
                description=analysis_data.get('description'),
                total_score=analysis_data['total_score'],
                rating=analysis_data['rating'],
                breakdown=analysis_data['breakdown'],
                suggestions=analysis_data['suggestions'],
                jira_ticket_key=analysis_data.get('jira_ticket_key'),
                jira_context=analysis_data.get('jira_context'),
                analyzed_by=analysis_data['analyzed_by']
            )
            
            session.add(analysis)
            await session.commit()
            await session.refresh(analysis)
            
            return analysis.id
    
    async def get_analysis(self, pr_id: str, repository: str) -> Optional[Dict[str, Any]]:
        """Get PR analysis from database."""
        async with self.db_manager.get_session() as session:
            from sqlalchemy import select
            
            stmt = select(PRAnalysis).where(
                PRAnalysis.pr_id == pr_id,
                PRAnalysis.repository == repository
            ).order_by(PRAnalysis.analyzed_at.desc())
            
            result = await session.execute(stmt)
            analysis = result.scalar_one_or_none()
            
            if analysis:
                return {
                    'id': analysis.id,
                    'pr_id': analysis.pr_id,
                    'repository': analysis.repository,
                    'workspace': analysis.workspace,
                    'title': analysis.title,
                    'description': analysis.description,
                    'total_score': analysis.total_score,
                    'rating': analysis.rating,
                    'breakdown': analysis.breakdown,
                    'suggestions': analysis.suggestions,
                    'jira_ticket_key': analysis.jira_ticket_key,
                    'jira_context': analysis.jira_context,
                    'analyzed_by': analysis.analyzed_by,
                    'analyzed_at': analysis.analyzed_at,
                    'created_at': analysis.created_at,
                    'updated_at': analysis.updated_at
                }
            
            return None
    
    async def get_repository_stats(self, repository: str, days: int = 30) -> Dict[str, Any]:
        """Get repository statistics."""
        async with self.db_manager.get_session() as session:
            from sqlalchemy import select, func
            from datetime import datetime, timedelta
            
            cutoff_date = datetime.utcnow() - timedelta(days=days)
            
            # Basic stats
            stmt = select(
                func.count(PRAnalysis.id).label('total_prs'),
                func.avg(PRAnalysis.total_score).label('avg_score'),
                func.min(PRAnalysis.total_score).label('min_score'),
                func.max(PRAnalysis.total_score).label('max_score')
            ).where(
                PRAnalysis.repository == repository,
                PRAnalysis.analyzed_at >= cutoff_date
            )
            
            result = await session.execute(stmt)
            stats = result.first()
            
            return {
                'repository': repository,
                'period_days': days,
                'total_prs': stats.total_prs or 0,
                'avg_score': float(stats.avg_score or 0),
                'min_score': float(stats.min_score or 0),
                'max_score': float(stats.max_score or 0)
            }


# Global database manager instance
db_manager: Optional[DatabaseManager] = None


def create_database_manager() -> DatabaseManager:
    """Create and return database manager instance."""
    global db_manager
    if db_manager is None:
        # Use PostgreSQL for production, SQLite for development
        if config.environment == 'production':
            database_url = getattr(config, 'database_url', 'postgresql+asyncpg://user:pass@localhost/prdb')
        else:
            database_url = 'sqlite+aiosqlite:///./pr_assistant.db'
        
        db_manager = DatabaseManager(database_url)
    return db_manager


async def get_database_manager() -> Optional[DatabaseManager]:
    """Get the global database manager instance."""
    global db_manager
    if db_manager is None:
        db_manager = create_database_manager()
        await db_manager.initialize()
    return db_manager
