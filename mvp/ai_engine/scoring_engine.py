"""AI-powered PR scoring engine for the Intelligent PR Assistant."""

import asyncio
import json
import re
from datetime import datetime
from typing import Dict, List, Optional, Any
import logging

import openai
from openai import AsyncOpenAI

from config.config import config

logger = logging.getLogger(__name__)


class PRData:
    """Data model for pull request information."""
    
    def __init__(
        self,
        pr_id: str,
        title: str,
        description: str,
        files: List[Dict[str, Any]] = None,
        tests: List[Dict[str, Any]] = None,
        jira_context: Optional[Dict[str, Any]] = None
    ):
        self.id = pr_id
        self.title = title
        self.description = description
        self.files = files or []
        self.tests = tests or []
        self.jira_context = jira_context


class ScoringResult:
    """Data model for scoring results."""
    
    def __init__(
        self,
        total_score: float,
        breakdown: Dict[str, float],
        rating: str,
        suggestions: List[str],
        timestamp: str
    ):
        self.total_score = total_score
        self.breakdown = breakdown
        self.rating = rating
        self.suggestions = suggestions
        self.timestamp = timestamp
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for JSON serialization."""
        return {
            "total_score": self.total_score,
            "breakdown": self.breakdown,
            "rating": self.rating,
            "suggestions": self.suggestions,
            "timestamp": self.timestamp
        }


class ScoringEngine:
    """AI-powered scoring engine for pull requests."""
    
    def __init__(self):
        """Initialize the scoring engine with OpenAI client and configuration."""
        self.client = AsyncOpenAI(api_key=config.openai.api_key)
        self.weights = config.scoring.weights
        self.thresholds = config.scoring.thresholds
        
        # Context keywords for scoring
        self.context_keywords = [
            "because", "fixes", "addresses", "implements", 
            "refactor", "resolves", "closes", "updates"
        ]
        
        # Conventional commit prefixes
        self.commit_prefixes = [
            "feat:", "fix:", "docs:", "style:", "refactor:", 
            "test:", "chore:", "perf:", "ci:", "build:"
        ]
    
    async def calculate_score(self, pr_data: PRData) -> ScoringResult:
        """
        Calculate comprehensive PR score with AI analysis.
        
        Args:
            pr_data: Pull request data to analyze
            
        Returns:
            ScoringResult with detailed breakdown and suggestions
        """
        try:
            logger.info(f"Calculating score for PR {pr_data.id}")
            
            # Calculate individual scores
            clarity_score = await self._analyze_clarity_score(pr_data.title, pr_data.description)
            context_score = self._analyze_context_score(pr_data.description, pr_data.files)
            completeness_score = self._analyze_completeness_score(pr_data)
            jira_link_score = self._analyze_jira_link_score(pr_data.jira_context)
            
            # Calculate weighted total score
            total_score = (
                clarity_score * self.weights["clarity"] +
                context_score * self.weights["context"] +
                completeness_score * self.weights["completeness"] +
                jira_link_score * self.weights["jira_link"]
            )
            
            breakdown = {
                "clarity": round(clarity_score, 1),
                "context": round(context_score, 1),
                "completeness": round(completeness_score, 1),
                "jira_link": round(jira_link_score, 1)
            }
            
            rating = self._get_rating(total_score)
            suggestions = await self._generate_suggestions(pr_data, breakdown)
            
            result = ScoringResult(
                total_score=round(total_score, 1),
                breakdown=breakdown,
                rating=rating,
                suggestions=suggestions,
                timestamp=datetime.utcnow().isoformat()
            )
            
            logger.info(
                f"PR {pr_data.id} scored {result.total_score} ({result.rating})",
                extra={"pr_id": pr_data.id, "score": result.total_score, "rating": result.rating}
            )
            
            return result
            
        except Exception as e:
            logger.error(f"Error calculating PR score: {str(e)}", exc_info=True)
            raise Exception(f"Failed to calculate PR score: {str(e)}")
    
    async def _analyze_clarity_score(self, title: str, description: str) -> float:
        """Analyze clarity using AI with fallback to rule-based scoring."""
        try:
            prompt = f"""
            Analyze the clarity of this pull request:
            
            Title: {title}
            Description: {description}
            
            Rate the clarity on a scale of 1-10 based on:
            - Clear, descriptive title
            - Well-structured description
            - Proper grammar and spelling
            - Easy to understand intent
            
            Respond with only a number between 1-10.
            """
            
            response = await self.client.chat.completions.create(
                model=config.openai.model,
                messages=[{"role": "user", "content": prompt}],
                max_tokens=10,
                temperature=config.openai.temperature
            )
            
            score_text = response.choices[0].message.content.strip()
            score = float(score_text)
            
            # Validate score range
            if not (1 <= score <= 10):
                raise ValueError(f"Score {score} out of valid range")
                
            return score
            
        except Exception as e:
            logger.warning(f"AI clarity analysis failed, using fallback: {str(e)}")
            return self._fallback_clarity_score(title, description)
    
    def _analyze_context_score(self, description: str, files: List[Dict[str, Any]]) -> float:
        """Analyze context score based on description and file changes."""
        score = 5.0  # Base score
        
        if not description:
            return 2.0
        
        # Check description length and detail
        if len(description) > 100:
            score += 1.5
        if len(description) > 300:
            score += 1.0
        
        # Check for context keywords
        description_lower = description.lower()
        has_context = any(keyword in description_lower for keyword in self.context_keywords)
        if has_context:
            score += 1.5
        
        # Check file changes scope
        if files:
            file_count = len(files)
            if file_count <= 5:  # Focused changes
                score += 1.0
            elif file_count > 10:  # Too broad
                score -= 1.0
        
        # Check for meaningful commit patterns
        if any(prefix in description_lower for prefix in self.commit_prefixes):
            score += 0.5
        
        return max(1.0, min(10.0, score))
    
    def _analyze_completeness_score(self, pr_data: PRData) -> float:
        """Analyze completeness score based on PR content."""
        score = 5.0  # Base score
        
        # Check basic completeness
        if pr_data.title and len(pr_data.title) > 10:
            score += 1.0
        if pr_data.description and len(pr_data.description) > 50:
            score += 1.0
        if pr_data.files:
            score += 1.0
        
        # Check for tests
        if pr_data.tests:
            score += 2.0
        else:
            # Check if test files are in the changed files
            test_patterns = [r'test_.*\.py$', r'.*_test\.py$', r'.*/tests/.*\.py$']
            has_test_files = any(
                any(re.search(pattern, file.get('filename', '')) for pattern in test_patterns)
                for file in pr_data.files
            )
            if has_test_files:
                score += 1.5
        
        # Check for documentation updates
        doc_patterns = [r'readme', r'\.md$', r'docs/', r'documentation']
        has_doc_updates = any(
            any(pattern.lower() in file.get('filename', '').lower() for pattern in doc_patterns)
            for file in pr_data.files
        )
        if has_doc_updates:
            score += 1.0
        
        return max(1.0, min(10.0, score))
    
    def _analyze_jira_link_score(self, jira_context: Optional[Dict[str, Any]]) -> float:
        """Analyze Jira link score based on ticket context."""
        if not jira_context:
            return 0.0
        
        score = 5.0  # Base score for having Jira context
        
        # Check if ticket is properly linked
        if jira_context.get('ticket_id'):
            score += 2.0
        if jira_context.get('ticket_status') == 'In Progress':
            score += 1.0
        if jira_context.get('ticket_type'):
            score += 1.0
        if jira_context.get('priority'):
            score += 1.0
        
        return max(0.0, min(10.0, score))
    
    async def _generate_suggestions(self, pr_data: PRData, scores: Dict[str, float]) -> List[str]:
        """Generate AI-powered improvement suggestions."""
        try:
            low_score_areas = [area for area, score in scores.items() if score < 7.0]
            
            if not low_score_areas:
                return ["Great job! This PR meets all quality standards."]
            
            prompt = f"""
            Generate 2-3 specific improvement suggestions for a pull request with low scores in: {', '.join(low_score_areas)}.
            
            PR Title: {pr_data.title}
            PR Description: {pr_data.description}
            
            Focus on actionable improvements. Keep suggestions concise and helpful.
            Return as a JSON array of strings.
            """
            
            response = await self.client.chat.completions.create(
                model=config.openai.model,
                messages=[{"role": "user", "content": prompt}],
                max_tokens=300,
                temperature=0.7
            )
            
            suggestions_text = response.choices[0].message.content.strip()
            suggestions = json.loads(suggestions_text)
            
            if isinstance(suggestions, list):
                return suggestions
            else:
                return self._get_fallback_suggestions(low_score_areas)
                
        except Exception as e:
            logger.warning(f"AI suggestion generation failed, using fallback: {str(e)}")
            return self._get_fallback_suggestions(low_score_areas)
    
    def _get_rating(self, score: float) -> str:
        """Get rating based on score thresholds."""
        if score >= self.thresholds["excellent"]:
            return "excellent"
        elif score >= self.thresholds["good"]:
            return "good"
        elif score >= self.thresholds["needs_improvement"]:
            return "needs-improvement"
        else:
            return "poor"
    
    def _fallback_clarity_score(self, title: str, description: str) -> float:
        """Fallback clarity scoring without AI."""
        score = 5.0
        
        if title:
            if 10 < len(title) < 100:
                score += 2.0
            # Check for conventional commit format
            if any(title.lower().startswith(prefix) for prefix in self.commit_prefixes):
                score += 1.0
        
        if description and len(description) > 50:
            score += 2.0
        
        return max(1.0, min(10.0, score))
    
    def _get_fallback_suggestions(self, low_score_areas: List[str]) -> List[str]:
        """Get fallback suggestions for low-scoring areas."""
        suggestion_map = {
            "clarity": "Consider adding a more descriptive title and detailed description",
            "context": "Provide more context about why this change is needed",
            "completeness": "Add tests and update documentation if needed",
            "jira_link": "Link this PR to the relevant Jira ticket"
        }
        
        return [suggestion_map.get(area, f"Improve {area} score") for area in low_score_areas]


# Factory function for easy instantiation
def create_scoring_engine() -> ScoringEngine:
    """Create and return a new scoring engine instance."""
    return ScoringEngine()
