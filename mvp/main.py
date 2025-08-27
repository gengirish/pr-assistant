"""Main FastAPI application for the Intelligent PR Assistant MVP."""

import asyncio
import logging
from contextlib import asynccontextmanager
from typing import Dict, Any, Optional

from fastapi import FastAPI, HTTPException, Depends, BackgroundTasks, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from pydantic import BaseModel, Field

from config.config import config
from ai_engine.scoring_engine import ScoringEngine, PRData, create_scoring_engine
from integrations.jira_client import JiraClient, create_jira_client
from integrations.bitbucket_client import BitbucketClient, create_bitbucket_client
from utils.logger import setup_logging
from utils.security import SecurityManager, create_security_manager

# Setup logging
setup_logging()
logger = logging.getLogger(__name__)

# Global instances
scoring_engine: Optional[ScoringEngine] = None
jira_client: Optional[JiraClient] = None
bitbucket_client: Optional[BitbucketClient] = None
security_manager: Optional[SecurityManager] = None


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan manager."""
    global scoring_engine, jira_client, bitbucket_client, security_manager
    
    # Startup
    logger.info("Starting PR Assistant MVP...")
    
    # Initialize components
    scoring_engine = create_scoring_engine()
    jira_client = create_jira_client()
    bitbucket_client = create_bitbucket_client()
    security_manager = create_security_manager()
    
    logger.info("PR Assistant MVP started successfully")
    
    yield
    
    # Shutdown
    logger.info("Shutting down PR Assistant MVP...")
    
    # Cleanup
    if jira_client:
        await jira_client.close()
    if bitbucket_client:
        await bitbucket_client.close()
    
    logger.info("PR Assistant MVP shutdown complete")


# Create FastAPI app
app = FastAPI(
    title="Intelligent PR Assistant MVP",
    description="AI-powered pull request analysis and scoring for Atlassian ecosystem",
    version=config.version,
    lifespan=lifespan
)

# Add CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Configure appropriately for production
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Security
security = HTTPBearer()


# Pydantic models
class PRAnalysisRequest(BaseModel):
    """Request model for PR analysis."""
    pr_id: str = Field(..., description="Pull request ID")
    title: str = Field(..., description="Pull request title")
    description: str = Field(default="", description="Pull request description")
    workspace: Optional[str] = Field(None, description="Bitbucket workspace")
    repository: Optional[str] = Field(None, description="Repository name")
    files: Optional[list] = Field(default=[], description="Changed files")
    include_jira: bool = Field(default=True, description="Include Jira analysis")


class PRAnalysisResponse(BaseModel):
    """Response model for PR analysis."""
    pr_id: str
    total_score: float
    rating: str
    breakdown: Dict[str, float]
    suggestions: list
    jira_context: Optional[Dict[str, Any]] = None
    timestamp: str


class WebhookPayload(BaseModel):
    """Generic webhook payload model."""
    event_type: str
    data: Dict[str, Any]


class HealthResponse(BaseModel):
    """Health check response model."""
    status: str
    version: str
    environment: str
    components: Dict[str, str]


# Dependency functions
async def get_current_user(credentials: HTTPAuthorizationCredentials = Depends(security)):
    """Get current authenticated user."""
    if not security_manager:
        raise HTTPException(status_code=500, detail="Security manager not initialized")
    
    try:
        payload = security_manager.verify_jwt_token(credentials.credentials)
        return payload
    except Exception as e:
        logger.error(f"Authentication failed: {str(e)}")
        raise HTTPException(status_code=401, detail="Invalid authentication credentials")


# API Routes
@app.get("/", response_model=Dict[str, str])
async def root():
    """Root endpoint."""
    return {
        "message": "Intelligent PR Assistant MVP",
        "version": config.version,
        "docs": "/docs"
    }


@app.get("/health", response_model=HealthResponse)
async def health_check():
    """Health check endpoint."""
    components = {
        "scoring_engine": "healthy" if scoring_engine else "unavailable",
        "jira_client": "healthy" if jira_client else "unavailable",
        "bitbucket_client": "healthy" if bitbucket_client else "unavailable",
        "security_manager": "healthy" if security_manager else "unavailable"
    }
    
    return HealthResponse(
        status="healthy",
        version=config.version,
        environment=config.environment,
        components=components
    )


@app.post("/api/v1/analyze-pr", response_model=PRAnalysisResponse)
async def analyze_pull_request(
    request: PRAnalysisRequest,
    background_tasks: BackgroundTasks,
    current_user: Dict[str, Any] = Depends(get_current_user)
):
    """Analyze a pull request and return scoring results."""
    try:
        logger.info(f"Analyzing PR {request.pr_id} for user {current_user.get('sub', 'unknown')}")
        
        if not scoring_engine:
            raise HTTPException(status_code=500, detail="Scoring engine not available")
        
        # Extract Jira context if requested
        jira_context = None
        if request.include_jira and jira_client:
            try:
                # Extract ticket keys from title and description
                text = f"{request.title} {request.description}"
                tickets = await jira_client.get_tickets_from_text(text)
                
                if tickets:
                    # Use the first ticket found
                    jira_context = tickets[0].to_dict()
                    logger.info(f"Found Jira context for PR {request.pr_id}: {jira_context.get('ticket_id')}")
            except Exception as e:
                logger.warning(f"Failed to get Jira context: {str(e)}")
        
        # Create PR data object
        pr_data = PRData(
            pr_id=request.pr_id,
            title=request.title,
            description=request.description,
            files=request.files,
            jira_context=jira_context
        )
        
        # Calculate score
        result = await scoring_engine.calculate_score(pr_data)
        
        # Schedule background tasks
        if request.workspace and request.repository and bitbucket_client:
            background_tasks.add_task(
                post_pr_comment,
                request.workspace,
                request.repository,
                int(request.pr_id),
                result
            )
        
        return PRAnalysisResponse(
            pr_id=request.pr_id,
            total_score=result.total_score,
            rating=result.rating,
            breakdown=result.breakdown,
            suggestions=result.suggestions,
            jira_context=jira_context,
            timestamp=result.timestamp
        )
        
    except Exception as e:
        logger.error(f"Error analyzing PR {request.pr_id}: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Analysis failed: {str(e)}")


@app.post("/api/v1/webhook/bitbucket")
async def bitbucket_webhook(
    request: Request,
    background_tasks: BackgroundTasks
):
    """Handle Bitbucket webhook events."""
    try:
        # Get raw payload for signature verification
        payload = await request.body()
        signature = request.headers.get('X-Hub-Signature-256', '')
        
        if not bitbucket_client:
            raise HTTPException(status_code=500, detail="Bitbucket client not available")
        
        # Verify webhook signature
        if not bitbucket_client.verify_webhook_signature(payload, signature):
            logger.warning("Invalid webhook signature")
            raise HTTPException(status_code=401, detail="Invalid signature")
        
        # Parse JSON payload
        import json
        webhook_data = json.loads(payload.decode('utf-8'))
        
        # Parse webhook payload
        parsed_data = bitbucket_client.parse_webhook_payload(webhook_data)
        
        if not parsed_data:
            logger.info("Unhandled webhook event")
            return {"status": "ignored"}
        
        # Handle PR events
        if parsed_data['event'] in ['pr_created', 'pr_updated']:
            pr = parsed_data['pull_request']
            
            # Schedule PR analysis
            background_tasks.add_task(
                analyze_pr_from_webhook,
                pr.to_dict(),
                parsed_data['repository']
            )
        
        return {"status": "processed"}
        
    except Exception as e:
        logger.error(f"Error processing webhook: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Webhook processing failed: {str(e)}")


@app.get("/api/v1/jira/ticket/{ticket_key}")
async def get_jira_ticket(
    ticket_key: str,
    current_user: Dict[str, Any] = Depends(get_current_user)
):
    """Get Jira ticket information."""
    try:
        if not jira_client:
            raise HTTPException(status_code=500, detail="Jira client not available")
        
        ticket = await jira_client.get_ticket(ticket_key)
        
        if not ticket:
            raise HTTPException(status_code=404, detail="Ticket not found")
        
        return ticket.to_dict()
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error retrieving Jira ticket {ticket_key}: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Failed to retrieve ticket: {str(e)}")


@app.get("/api/v1/config")
async def get_configuration(
    current_user: Dict[str, Any] = Depends(get_current_user)
):
    """Get application configuration (sanitized)."""
    return {
        "app": {
            "name": config.name,
            "version": config.version,
            "environment": config.environment
        },
        "features": {
            "ai_suggestions": config.features.ai_suggestions,
            "jira_auto_link": config.features.jira_auto_link,
            "compliance_check": config.features.compliance_check,
            "analytics": config.features.analytics
        },
        "scoring": {
            "weights": config.scoring.weights,
            "thresholds": config.scoring.thresholds
        }
    }


# Background task functions
async def post_pr_comment(workspace: str, repository: str, pr_id: int, result):
    """Post analysis results as PR comment."""
    try:
        if not bitbucket_client:
            return
        
        # Format comment content
        comment = f"""
## 🤖 PR Assistant Analysis

**Overall Score: {result.total_score}/10** ({result.rating.replace('-', ' ').title()})

### Breakdown:
- **Clarity**: {result.breakdown['clarity']}/10
- **Context**: {result.breakdown['context']}/10  
- **Completeness**: {result.breakdown['completeness']}/10
- **Jira Link**: {result.breakdown['jira_link']}/10

### Suggestions:
{chr(10).join(f'- {suggestion}' for suggestion in result.suggestions)}

---
*Powered by Intelligent PR Assistant*
        """.strip()
        
        await bitbucket_client.add_pull_request_comment(
            workspace, repository, pr_id, comment
        )
        
        logger.info(f"Posted analysis comment to PR {pr_id}")
        
    except Exception as e:
        logger.error(f"Failed to post PR comment: {str(e)}")


async def analyze_pr_from_webhook(pr_data: Dict[str, Any], repo_data: Dict[str, Any]):
    """Analyze PR from webhook event."""
    try:
        if not scoring_engine:
            return
        
        # Create PR data object
        pr = PRData(
            pr_id=str(pr_data['id']),
            title=pr_data['title'],
            description=pr_data['description'],
            files=[],  # Would need to fetch from API
            jira_context=None
        )
        
        # Get Jira context
        if jira_client:
            text = f"{pr_data['title']} {pr_data['description']}"
            tickets = await jira_client.get_tickets_from_text(text)
            if tickets:
                pr.jira_context = tickets[0].to_dict()
        
        # Calculate score
        result = await scoring_engine.calculate_score(pr)
        
        logger.info(f"Webhook analysis complete for PR {pr_data['id']}: {result.total_score}")
        
    except Exception as e:
        logger.error(f"Failed to analyze PR from webhook: {str(e)}")


if __name__ == "__main__":
    import uvicorn
    
    uvicorn.run(
        "main:app",
        host=config.host,
        port=config.port,
        reload=config.debug,
        log_level=config.logging.level.lower()
    )
