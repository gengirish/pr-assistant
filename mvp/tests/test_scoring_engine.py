"""Tests for the AI scoring engine."""

import pytest
import asyncio
from unittest.mock import Mock, AsyncMock, patch

from ai_engine.scoring_engine import ScoringEngine, PRData, ScoringResult


class TestScoringEngine:
    """Test cases for the ScoringEngine class."""
    
    @pytest.fixture
    def scoring_engine(self):
        """Create a scoring engine instance for testing."""
        with patch('ai_engine.scoring_engine.config') as mock_config:
            mock_config.openai.api_key = "test-key"
            mock_config.scoring.weights = {
                "clarity": 0.3,
                "context": 0.25,
                "completeness": 0.25,
                "jira_link": 0.2
            }
            mock_config.scoring.thresholds = {
                "excellent": 8.5,
                "good": 7.0,
                "needs_improvement": 5.0
            }
            return ScoringEngine()
    
    @pytest.fixture
    def sample_pr_data(self):
        """Create sample PR data for testing."""
        return PRData(
            pr_id="123",
            title="feat: Add new user authentication feature",
            description="This PR implements OAuth 2.0 authentication for users. It includes login, logout, and token refresh functionality.",
            files=[
                {"filename": "auth.py", "status": "added"},
                {"filename": "test_auth.py", "status": "added"},
                {"filename": "README.md", "status": "modified"}
            ],
            tests=[
                {"filename": "test_auth.py", "status": "added"}
            ],
            jira_context={
                "ticket_id": "AUTH-123",
                "ticket_status": "In Progress",
                "ticket_type": "Story",
                "priority": "High"
            }
        )
    
    def test_pr_data_initialization(self):
        """Test PRData initialization."""
        pr_data = PRData(
            pr_id="test-123",
            title="Test PR",
            description="Test description"
        )
        
        assert pr_data.id == "test-123"
        assert pr_data.title == "Test PR"
        assert pr_data.description == "Test description"
        assert pr_data.files == []
        assert pr_data.tests == []
        assert pr_data.jira_context is None
    
    def test_scoring_result_to_dict(self):
        """Test ScoringResult to_dict method."""
        result = ScoringResult(
            total_score=8.5,
            breakdown={"clarity": 9.0, "context": 8.0, "completeness": 8.5, "jira_link": 9.0},
            rating="excellent",
            suggestions=["Great job!"],
            timestamp="2024-01-01T00:00:00"
        )
        
        result_dict = result.to_dict()
        
        assert result_dict["total_score"] == 8.5
        assert result_dict["rating"] == "excellent"
        assert result_dict["suggestions"] == ["Great job!"]
        assert "breakdown" in result_dict
        assert "timestamp" in result_dict
    
    def test_analyze_context_score(self, scoring_engine):
        """Test context score analysis."""
        # Test with good context
        description = "This PR fixes the authentication bug because the token validation was incorrect"
        files = [{"filename": "auth.py"}]
        
        score = scoring_engine._analyze_context_score(description, files)
        assert score > 5.0
        
        # Test with poor context
        description = "Fix"
        files = []
        
        score = scoring_engine._analyze_context_score(description, files)
        assert score <= 5.0
    
    def test_analyze_completeness_score(self, scoring_engine, sample_pr_data):
        """Test completeness score analysis."""
        score = scoring_engine._analyze_completeness_score(sample_pr_data)
        
        # Should have good score due to title, description, files, and tests
        assert score > 7.0
    
    def test_analyze_jira_link_score(self, scoring_engine):
        """Test Jira link score analysis."""
        # Test with good Jira context
        jira_context = {
            "ticket_id": "AUTH-123",
            "ticket_status": "In Progress",
            "ticket_type": "Story",
            "priority": "High"
        }
        
        score = scoring_engine._analyze_jira_link_score(jira_context)
        assert score > 8.0
        
        # Test with no Jira context
        score = scoring_engine._analyze_jira_link_score(None)
        assert score == 0.0
    
    def test_get_rating(self, scoring_engine):
        """Test rating determination."""
        assert scoring_engine._get_rating(9.0) == "excellent"
        assert scoring_engine._get_rating(7.5) == "good"
        assert scoring_engine._get_rating(6.0) == "needs-improvement"
        assert scoring_engine._get_rating(3.0) == "poor"
    
    def test_fallback_clarity_score(self, scoring_engine):
        """Test fallback clarity scoring."""
        # Test with good title and description
        title = "feat: Add user authentication with OAuth 2.0"
        description = "This PR implements comprehensive OAuth 2.0 authentication system with proper error handling and security measures."
        
        score = scoring_engine._fallback_clarity_score(title, description)
        assert score > 7.0
        
        # Test with poor title and description
        title = "fix"
        description = ""
        
        score = scoring_engine._fallback_clarity_score(title, description)
        assert score <= 6.0
    
    def test_get_fallback_suggestions(self, scoring_engine):
        """Test fallback suggestions generation."""
        low_areas = ["clarity", "context"]
        suggestions = scoring_engine._get_fallback_suggestions(low_areas)
        
        assert len(suggestions) == 2
        assert any("descriptive title" in suggestion for suggestion in suggestions)
        assert any("context" in suggestion for suggestion in suggestions)
    
    @pytest.mark.asyncio
    async def test_calculate_score_with_mock_ai(self, scoring_engine, sample_pr_data):
        """Test score calculation with mocked AI response."""
        with patch.object(scoring_engine, '_analyze_clarity_score', return_value=8.0), \
             patch.object(scoring_engine, '_generate_suggestions', return_value=["Great job!"]):
            
            result = await scoring_engine.calculate_score(sample_pr_data)
            
            assert isinstance(result, ScoringResult)
            assert result.total_score > 0
            assert result.rating in ["excellent", "good", "needs-improvement", "poor"]
            assert len(result.suggestions) > 0
            assert result.timestamp is not None
    
    @pytest.mark.asyncio
    async def test_analyze_clarity_score_fallback(self, scoring_engine):
        """Test clarity score analysis with AI failure fallback."""
        with patch.object(scoring_engine.client.chat.completions, 'create', side_effect=Exception("API Error")):
            score = await scoring_engine._analyze_clarity_score(
                "feat: Add authentication",
                "This PR adds OAuth 2.0 authentication"
            )
            
            # Should fallback to rule-based scoring
            assert isinstance(score, float)
            assert 1.0 <= score <= 10.0
    
    @pytest.mark.asyncio
    async def test_generate_suggestions_fallback(self, scoring_engine, sample_pr_data):
        """Test suggestions generation with AI failure fallback."""
        scores = {"clarity": 6.0, "context": 5.0, "completeness": 8.0, "jira_link": 9.0}
        
        with patch.object(scoring_engine.client.chat.completions, 'create', side_effect=Exception("API Error")):
            suggestions = await scoring_engine._generate_suggestions(sample_pr_data, scores)
            
            # Should fallback to predefined suggestions
            assert isinstance(suggestions, list)
            assert len(suggestions) > 0


class TestPRData:
    """Test cases for the PRData class."""
    
    def test_pr_data_with_all_fields(self):
        """Test PRData with all fields provided."""
        files = [{"filename": "test.py", "status": "added"}]
        tests = [{"filename": "test_test.py", "status": "added"}]
        jira_context = {"ticket_id": "TEST-123"}
        
        pr_data = PRData(
            pr_id="123",
            title="Test PR",
            description="Test description",
            files=files,
            tests=tests,
            jira_context=jira_context
        )
        
        assert pr_data.id == "123"
        assert pr_data.title == "Test PR"
        assert pr_data.description == "Test description"
        assert pr_data.files == files
        assert pr_data.tests == tests
        assert pr_data.jira_context == jira_context
    
    def test_pr_data_with_minimal_fields(self):
        """Test PRData with minimal required fields."""
        pr_data = PRData(
            pr_id="456",
            title="Minimal PR",
            description="Minimal description"
        )
        
        assert pr_data.id == "456"
        assert pr_data.title == "Minimal PR"
        assert pr_data.description == "Minimal description"
        assert pr_data.files == []
        assert pr_data.tests == []
        assert pr_data.jira_context is None


@pytest.mark.asyncio
async def test_create_scoring_engine():
    """Test scoring engine factory function."""
    with patch('ai_engine.scoring_engine.config') as mock_config:
        mock_config.openai.api_key = "test-key"
        mock_config.scoring.weights = {"clarity": 0.3, "context": 0.25, "completeness": 0.25, "jira_link": 0.2}
        mock_config.scoring.thresholds = {"excellent": 8.5, "good": 7.0, "needs_improvement": 5.0}
        
        from ai_engine.scoring_engine import create_scoring_engine
        
        engine = create_scoring_engine()
        assert isinstance(engine, ScoringEngine)
        assert engine.weights == mock_config.scoring.weights
        assert engine.thresholds == mock_config.scoring.thresholds


if __name__ == "__main__":
    pytest.main([__file__])
