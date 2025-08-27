"""Admin dashboard for Sprint 2."""

from typing import Dict, List, Optional, Any
import logging
from datetime import datetime, timedelta

from fastapi import APIRouter, Request, Depends, HTTPException
from fastapi.templating import Jinja2Templates
from fastapi.responses import HTMLResponse
from pydantic import BaseModel

from analytics.metrics_engine import MetricsEngine, create_metrics_engine
from ai_engine.enhanced_suggestions import EnhancedSuggestionsEngine, create_enhanced_suggestions_engine
from utils.security import SecurityManager
from config.config import config

logger = logging.getLogger(__name__)

# Initialize templates
templates = Jinja2Templates(directory="dashboard/templates")

# Create router
router = APIRouter(prefix="/admin", tags=["admin"])

# Global instances (would be dependency injected in production)
metrics_engine: Optional[MetricsEngine] = None
suggestions_engine: Optional[EnhancedSuggestionsEngine] = None


class DashboardData(BaseModel):
    """Data model for dashboard information."""
    overview: Dict[str, Any]
    recent_prs: List[Dict[str, Any]]
    team_metrics: Dict[str, Any]
    quality_trends: Dict[str, Any]
    alerts: List[Dict[str, Any]]


def init_dashboard_components():
    """Initialize dashboard components."""
    global metrics_engine, suggestions_engine
    if not metrics_engine:
        metrics_engine = create_metrics_engine()
    if not suggestions_engine:
        suggestions_engine = create_enhanced_suggestions_engine()


@router.get("/", response_class=HTMLResponse)
async def dashboard_home(request: Request):
    """Main dashboard page."""
    try:
        init_dashboard_components()
        
        # Get overview data
        overview_data = await get_dashboard_overview()
        
        return templates.TemplateResponse("dashboard.html", {
            "request": request,
            "title": "PR Assistant Admin Dashboard",
            "overview": overview_data.overview,
            "recent_prs": overview_data.recent_prs,
            "team_metrics": overview_data.team_metrics,
            "quality_trends": overview_data.quality_trends,
            "alerts": overview_data.alerts
        })
        
    except Exception as e:
        logger.error(f"Error loading dashboard: {str(e)}")
        raise HTTPException(status_code=500, detail="Dashboard loading failed")


@router.get("/api/overview")
async def get_dashboard_overview() -> DashboardData:
    """Get dashboard overview data."""
    try:
        init_dashboard_components()
        
        # Calculate overview metrics
        end_date = datetime.utcnow()
        start_date = end_date - timedelta(days=30)
        
        # Get recent PRs (mock data for MVP)
        recent_prs = [
            {
                "id": "PR-001",
                "title": "feat: Add user authentication",
                "author": "john.doe",
                "repository": "main-app",
                "score": 8.5,
                "rating": "excellent",
                "created_at": (datetime.utcnow() - timedelta(hours=2)).isoformat(),
                "status": "open"
            },
            {
                "id": "PR-002", 
                "title": "fix: Resolve login bug",
                "author": "jane.smith",
                "repository": "main-app",
                "score": 7.2,
                "rating": "good",
                "created_at": (datetime.utcnow() - timedelta(hours=5)).isoformat(),
                "status": "merged"
            },
            {
                "id": "PR-003",
                "title": "Update documentation",
                "author": "bob.wilson",
                "repository": "docs",
                "score": 6.8,
                "rating": "good",
                "created_at": (datetime.utcnow() - timedelta(hours=8)).isoformat(),
                "status": "open"
            }
        ]
        
        # Overview statistics
        overview = {
            "total_prs_analyzed": len(recent_prs),
            "average_score": 7.5,
            "score_trend": "+0.3",
            "active_repositories": 3,
            "team_members": 12,
            "compliance_rate": 85.2,
            "test_coverage": 78.5,
            "jira_compliance": 92.1
        }
        
        # Team metrics (mock data)
        team_metrics = {
            "top_performers": [
                {"name": "jane.smith", "score": 8.7, "prs": 15},
                {"name": "john.doe", "score": 8.2, "prs": 12},
                {"name": "alice.brown", "score": 7.9, "prs": 18}
            ],
            "improvement_needed": [
                {"name": "bob.wilson", "score": 6.1, "prs": 8},
                {"name": "charlie.davis", "score": 5.8, "prs": 6}
            ]
        }
        
        # Quality trends (mock data)
        quality_trends = {
            "weekly_scores": [
                {"week": "2024-01-01", "score": 7.2},
                {"week": "2024-01-08", "score": 7.4},
                {"week": "2024-01-15", "score": 7.6},
                {"week": "2024-01-22", "score": 7.5}
            ],
            "category_breakdown": {
                "clarity": 7.8,
                "context": 7.2,
                "completeness": 7.6,
                "jira_link": 8.1
            }
        }
        
        # Generate alerts
        alerts = []
        
        if overview["compliance_rate"] < 90:
            alerts.append({
                "type": "warning",
                "title": "Compliance Rate Below Target",
                "message": f"Current compliance rate is {overview['compliance_rate']}%. Target is 90%.",
                "action": "Review compliance policies and team training."
            })
        
        if overview["test_coverage"] < 80:
            alerts.append({
                "type": "warning", 
                "title": "Test Coverage Below Target",
                "message": f"Current test coverage is {overview['test_coverage']}%. Target is 80%.",
                "action": "Encourage developers to add more tests to PRs."
            })
        
        if not alerts:
            alerts.append({
                "type": "success",
                "title": "All Systems Healthy",
                "message": "All metrics are within target ranges.",
                "action": "Continue monitoring trends."
            })
        
        return DashboardData(
            overview=overview,
            recent_prs=recent_prs,
            team_metrics=team_metrics,
            quality_trends=quality_trends,
            alerts=alerts
        )
        
    except Exception as e:
        logger.error(f"Error getting dashboard overview: {str(e)}")
        raise HTTPException(status_code=500, detail="Failed to load dashboard data")


@router.get("/team/{team_name}")
async def get_team_dashboard(team_name: str, period_days: int = 30):
    """Get team-specific dashboard data."""
    try:
        init_dashboard_components()
        
        team_metrics = metrics_engine.get_team_metrics(team_name, period_days)
        
        return {
            "team_metrics": team_metrics.to_dict(),
            "insights": [
                {
                    "type": "info",
                    "title": "Team Performance",
                    "message": f"Team {team_name} has analyzed {team_metrics.total_prs} PRs with an average score of {team_metrics.average_score}"
                }
            ]
        }
        
    except Exception as e:
        logger.error(f"Error getting team dashboard: {str(e)}")
        raise HTTPException(status_code=500, detail="Failed to load team data")


@router.get("/developer/{developer_name}")
async def get_developer_dashboard(developer_name: str, period_days: int = 30):
    """Get developer-specific dashboard data."""
    try:
        init_dashboard_components()
        
        dev_metrics = metrics_engine.get_developer_metrics(developer_name, period_days)
        
        return {
            "developer_metrics": dev_metrics.to_dict(),
            "recommendations": [
                f"Focus on improving: {', '.join(dev_metrics.improvement_areas)}" if dev_metrics.improvement_areas else "Keep up the excellent work!",
                f"Strengths: {', '.join(dev_metrics.strengths)}" if dev_metrics.strengths else "Continue developing your skills"
            ]
        }
        
    except Exception as e:
        logger.error(f"Error getting developer dashboard: {str(e)}")
        raise HTTPException(status_code=500, detail="Failed to load developer data")


@router.get("/repository/{repository_name}")
async def get_repository_dashboard(repository_name: str, period_days: int = 30):
    """Get repository-specific dashboard data."""
    try:
        init_dashboard_components()
        
        repo_insights = metrics_engine.get_repository_insights(repository_name, period_days)
        
        return repo_insights
        
    except Exception as e:
        logger.error(f"Error getting repository dashboard: {str(e)}")
        raise HTTPException(status_code=500, detail="Failed to load repository data")


@router.get("/settings", response_class=HTMLResponse)
async def dashboard_settings(request: Request):
    """Dashboard settings page."""
    try:
        current_config = {
            "scoring_weights": config.scoring.weights,
            "scoring_thresholds": config.scoring.thresholds,
            "features": {
                "ai_suggestions": config.features.ai_suggestions,
                "jira_auto_link": config.features.jira_auto_link,
                "compliance_check": config.features.compliance_check,
                "analytics": config.features.analytics
            }
        }
        
        return templates.TemplateResponse("settings.html", {
            "request": request,
            "title": "Dashboard Settings",
            "config": current_config
        })
        
    except Exception as e:
        logger.error(f"Error loading settings: {str(e)}")
        raise HTTPException(status_code=500, detail="Settings loading failed")


@router.get("/reports", response_class=HTMLResponse)
async def dashboard_reports(request: Request):
    """Dashboard reports page."""
    try:
        init_dashboard_components()
        
        # Get quality trends for reports
        quality_trends = metrics_engine.get_quality_trends(period_days=90)
        
        return templates.TemplateResponse("reports.html", {
            "request": request,
            "title": "Analytics Reports",
            "trends": quality_trends
        })
        
    except Exception as e:
        logger.error(f"Error loading reports: {str(e)}")
        raise HTTPException(status_code=500, detail="Reports loading failed")


# Initialize components when module is imported
def setup_dashboard():
    """Setup dashboard components."""
    init_dashboard_components()
    logger.info("Admin dashboard initialized")
