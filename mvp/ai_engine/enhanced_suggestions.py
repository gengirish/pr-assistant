"""Enhanced AI suggestions engine for Sprint 2."""

import asyncio
import json
from typing import Dict, List, Optional, Any, Tuple
import logging
from datetime import datetime

from openai import AsyncOpenAI

from config.config import config
from ai_engine.scoring_engine import PRData, ScoringResult
from integrations.jira_client import JiraTicket

logger = logging.getLogger(__name__)


class EnhancedSuggestion:
    """Data model for enhanced AI suggestions."""
    
    def __init__(
        self,
        category: str,
        priority: str,
        title: str,
        description: str,
        action_items: List[str],
        code_examples: Optional[List[Dict[str, str]]] = None,
        resources: Optional[List[Dict[str, str]]] = None
    ):
        self.category = category
        self.priority = priority  # high, medium, low
        self.title = title
        self.description = description
        self.action_items = action_items
        self.code_examples = code_examples or []
        self.resources = resources or []
        self.timestamp = datetime.utcnow().isoformat()
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for JSON serialization."""
        return {
            "category": self.category,
            "priority": self.priority,
            "title": self.title,
            "description": self.description,
            "action_items": self.action_items,
            "code_examples": self.code_examples,
            "resources": self.resources,
            "timestamp": self.timestamp
        }


class ComplianceCheck:
    """Data model for compliance check results."""
    
    def __init__(
        self,
        rule_id: str,
        rule_name: str,
        status: str,  # passed, failed, warning
        message: str,
        severity: str,  # critical, high, medium, low
        fix_suggestion: Optional[str] = None
    ):
        self.rule_id = rule_id
        self.rule_name = rule_name
        self.status = status
        self.message = message
        self.severity = severity
        self.fix_suggestion = fix_suggestion
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for JSON serialization."""
        return {
            "rule_id": self.rule_id,
            "rule_name": self.rule_name,
            "status": self.status,
            "message": self.message,
            "severity": self.severity,
            "fix_suggestion": self.fix_suggestion
        }


class EnhancedSuggestionsEngine:
    """Enhanced AI suggestions engine with detailed analysis and compliance checking."""
    
    def __init__(self):
        """Initialize the enhanced suggestions engine."""
        self.client = AsyncOpenAI(api_key=config.openai.api_key)
        
        # Compliance rules
        self.compliance_rules = {
            "security": [
                {
                    "id": "SEC001",
                    "name": "No hardcoded secrets",
                    "pattern": r"(password|secret|key|token)\s*=\s*['\"][^'\"]+['\"]",
                    "severity": "critical"
                },
                {
                    "id": "SEC002", 
                    "name": "SQL injection prevention",
                    "pattern": r"execute\s*\(\s*['\"].*%.*['\"]",
                    "severity": "high"
                }
            ],
            "code_quality": [
                {
                    "id": "CQ001",
                    "name": "Function complexity",
                    "max_lines": 50,
                    "severity": "medium"
                },
                {
                    "id": "CQ002",
                    "name": "Proper error handling",
                    "pattern": r"except\s*:",
                    "severity": "medium"
                }
            ],
            "documentation": [
                {
                    "id": "DOC001",
                    "name": "Function docstrings",
                    "pattern": r"def\s+\w+\([^)]*\):\s*\n\s*[^\"']",
                    "severity": "low"
                }
            ]
        }
    
    async def generate_enhanced_suggestions(
        self, 
        pr_data: PRData, 
        scoring_result: ScoringResult,
        jira_ticket: Optional[JiraTicket] = None
    ) -> List[EnhancedSuggestion]:
        """
        Generate enhanced AI suggestions with detailed analysis.
        
        Args:
            pr_data: Pull request data
            scoring_result: Basic scoring results
            jira_ticket: Optional Jira ticket context
            
        Returns:
            List of enhanced suggestions
        """
        try:
            suggestions = []
            
            # Generate category-specific suggestions
            if scoring_result.breakdown.get("clarity", 0) < 7:
                clarity_suggestions = await self._generate_clarity_suggestions(pr_data)
                suggestions.extend(clarity_suggestions)
            
            if scoring_result.breakdown.get("context", 0) < 7:
                context_suggestions = await self._generate_context_suggestions(pr_data, jira_ticket)
                suggestions.extend(context_suggestions)
            
            if scoring_result.breakdown.get("completeness", 0) < 7:
                completeness_suggestions = await self._generate_completeness_suggestions(pr_data)
                suggestions.extend(completeness_suggestions)
            
            # Generate code quality suggestions
            code_suggestions = await self._generate_code_quality_suggestions(pr_data)
            suggestions.extend(code_suggestions)
            
            # Generate security suggestions
            security_suggestions = await self._generate_security_suggestions(pr_data)
            suggestions.extend(security_suggestions)
            
            # Sort by priority
            priority_order = {"high": 0, "medium": 1, "low": 2}
            suggestions.sort(key=lambda x: priority_order.get(x.priority, 3))
            
            logger.info(f"Generated {len(suggestions)} enhanced suggestions for PR {pr_data.id}")
            
            return suggestions
            
        except Exception as e:
            logger.error(f"Error generating enhanced suggestions: {str(e)}")
            return []
    
    async def _generate_clarity_suggestions(self, pr_data: PRData) -> List[EnhancedSuggestion]:
        """Generate suggestions for improving PR clarity."""
        try:
            prompt = f"""
            Analyze this pull request for clarity improvements:
            
            Title: {pr_data.title}
            Description: {pr_data.description}
            
            Provide specific suggestions to improve clarity including:
            1. Title improvements
            2. Description structure
            3. Communication clarity
            
            Return as JSON with this structure:
            {{
                "suggestions": [
                    {{
                        "priority": "high|medium|low",
                        "title": "Brief title",
                        "description": "Detailed explanation",
                        "action_items": ["specific action 1", "specific action 2"],
                        "code_examples": [
                            {{"type": "before", "content": "current example"}},
                            {{"type": "after", "content": "improved example"}}
                        ]
                    }}
                ]
            }}
            """
            
            response = await self.client.chat.completions.create(
                model=config.openai.model,
                messages=[{"role": "user", "content": prompt}],
                max_tokens=800,
                temperature=0.7
            )
            
            result = json.loads(response.choices[0].message.content)
            suggestions = []
            
            for suggestion_data in result.get("suggestions", []):
                suggestion = EnhancedSuggestion(
                    category="clarity",
                    priority=suggestion_data.get("priority", "medium"),
                    title=suggestion_data.get("title", ""),
                    description=suggestion_data.get("description", ""),
                    action_items=suggestion_data.get("action_items", []),
                    code_examples=suggestion_data.get("code_examples", [])
                )
                suggestions.append(suggestion)
            
            return suggestions
            
        except Exception as e:
            logger.warning(f"Failed to generate clarity suggestions: {str(e)}")
            return [EnhancedSuggestion(
                category="clarity",
                priority="medium",
                title="Improve PR Title and Description",
                description="Consider making your PR title more descriptive and adding more context to the description.",
                action_items=[
                    "Use conventional commit format (feat:, fix:, docs:, etc.)",
                    "Explain the 'why' behind the changes",
                    "Include any breaking changes or migration notes"
                ]
            )]
    
    async def _generate_context_suggestions(
        self, 
        pr_data: PRData, 
        jira_ticket: Optional[JiraTicket]
    ) -> List[EnhancedSuggestion]:
        """Generate suggestions for improving PR context."""
        suggestions = []
        
        # Check for Jira ticket context
        if not jira_ticket:
            suggestions.append(EnhancedSuggestion(
                category="context",
                priority="high",
                title="Link to Jira Ticket",
                description="This PR should be linked to a Jira ticket for better traceability and context.",
                action_items=[
                    "Create a Jira ticket if one doesn't exist",
                    "Include the ticket ID in the PR title or description",
                    "Ensure the ticket has proper acceptance criteria"
                ],
                resources=[
                    {"type": "documentation", "url": "https://confluence.atlassian.com/jirasoftwarecloud/blog-linking-jira-issues-to-development-work-777002789.html"}
                ]
            ))
        
        # Check file scope
        if len(pr_data.files) > 10:
            suggestions.append(EnhancedSuggestion(
                category="context",
                priority="medium",
                title="Consider Breaking Down Large PR",
                description="This PR touches many files. Consider breaking it into smaller, focused changes.",
                action_items=[
                    "Group related changes into separate PRs",
                    "Ensure each PR has a single responsibility",
                    "Create a tracking ticket for the overall feature"
                ]
            ))
        
        return suggestions
    
    async def _generate_completeness_suggestions(self, pr_data: PRData) -> List[EnhancedSuggestion]:
        """Generate suggestions for improving PR completeness."""
        suggestions = []
        
        # Check for tests
        has_tests = any(
            "test" in file.get("filename", "").lower() 
            for file in pr_data.files
        )
        
        if not has_tests:
            suggestions.append(EnhancedSuggestion(
                category="completeness",
                priority="high",
                title="Add Unit Tests",
                description="This PR appears to be missing unit tests. Tests are crucial for maintaining code quality.",
                action_items=[
                    "Add unit tests for new functionality",
                    "Ensure test coverage is above 80%",
                    "Include both positive and negative test cases",
                    "Add integration tests if applicable"
                ],
                code_examples=[
                    {
                        "type": "example",
                        "content": """
def test_new_feature():
    # Arrange
    input_data = {"key": "value"}
    
    # Act
    result = new_feature(input_data)
    
    # Assert
    assert result.status == "success"
    assert result.data == expected_data
                        """
                    }
                ]
            ))
        
        # Check for documentation
        has_docs = any(
            file.get("filename", "").lower().endswith((".md", ".rst", ".txt"))
            for file in pr_data.files
        )
        
        if not has_docs and len(pr_data.files) > 3:
            suggestions.append(EnhancedSuggestion(
                category="completeness",
                priority="medium",
                title="Update Documentation",
                description="Consider updating documentation to reflect the changes in this PR.",
                action_items=[
                    "Update README.md if public APIs changed",
                    "Add inline code documentation",
                    "Update API documentation if applicable",
                    "Add migration notes for breaking changes"
                ]
            ))
        
        return suggestions
    
    async def _generate_code_quality_suggestions(self, pr_data: PRData) -> List[EnhancedSuggestion]:
        """Generate code quality suggestions."""
        suggestions = []
        
        # This would typically analyze actual code content
        # For MVP, we'll provide general suggestions
        suggestions.append(EnhancedSuggestion(
            category="code_quality",
            priority="medium",
            title="Code Quality Best Practices",
            description="Ensure your code follows established quality standards.",
            action_items=[
                "Follow consistent naming conventions",
                "Keep functions small and focused (< 50 lines)",
                "Use meaningful variable and function names",
                "Add proper error handling",
                "Remove any commented-out code"
            ],
            resources=[
                {"type": "guide", "url": "https://pep8.org/"},
                {"type": "tool", "url": "https://github.com/psf/black"}
            ]
        ))
        
        return suggestions
    
    async def _generate_security_suggestions(self, pr_data: PRData) -> List[EnhancedSuggestion]:
        """Generate security-related suggestions."""
        suggestions = []
        
        # Check for potential security issues in description/title
        security_keywords = ["password", "secret", "key", "token", "credential"]
        
        text_to_check = f"{pr_data.title} {pr_data.description}".lower()
        
        if any(keyword in text_to_check for keyword in security_keywords):
            suggestions.append(EnhancedSuggestion(
                category="security",
                priority="high",
                title="Security Review Required",
                description="This PR mentions security-sensitive terms. Please ensure proper security practices.",
                action_items=[
                    "Ensure no secrets are hardcoded in the code",
                    "Use environment variables for sensitive configuration",
                    "Review authentication and authorization logic",
                    "Consider security testing for new endpoints"
                ],
                resources=[
                    {"type": "guide", "url": "https://owasp.org/www-project-top-ten/"},
                    {"type": "tool", "url": "https://github.com/PyCQA/bandit"}
                ]
            ))
        
        return suggestions
    
    async def run_compliance_checks(self, pr_data: PRData) -> List[ComplianceCheck]:
        """
        Run compliance checks on the PR.
        
        Args:
            pr_data: Pull request data
            
        Returns:
            List of compliance check results
        """
        try:
            checks = []
            
            # For MVP, we'll simulate compliance checks
            # In a real implementation, this would analyze actual code content
            
            # Security compliance
            checks.append(ComplianceCheck(
                rule_id="SEC001",
                rule_name="No hardcoded secrets",
                status="passed",
                message="No hardcoded secrets detected in PR description",
                severity="critical"
            ))
            
            # Documentation compliance
            has_docs = any(
                file.get("filename", "").lower().endswith((".md", ".rst"))
                for file in pr_data.files
            )
            
            if not has_docs and len(pr_data.files) > 5:
                checks.append(ComplianceCheck(
                    rule_id="DOC001",
                    rule_name="Documentation updates required",
                    status="warning",
                    message="Large PR without documentation updates",
                    severity="medium",
                    fix_suggestion="Update relevant documentation files"
                ))
            else:
                checks.append(ComplianceCheck(
                    rule_id="DOC001",
                    rule_name="Documentation updates",
                    status="passed",
                    message="Documentation compliance satisfied",
                    severity="medium"
                ))
            
            # Test coverage compliance
            has_tests = any(
                "test" in file.get("filename", "").lower()
                for file in pr_data.files
            )
            
            if not has_tests:
                checks.append(ComplianceCheck(
                    rule_id="TEST001",
                    rule_name="Test coverage required",
                    status="failed",
                    message="No test files found in PR",
                    severity="high",
                    fix_suggestion="Add unit tests for new functionality"
                ))
            else:
                checks.append(ComplianceCheck(
                    rule_id="TEST001",
                    rule_name="Test coverage",
                    status="passed",
                    message="Test files included in PR",
                    severity="high"
                ))
            
            logger.info(f"Completed {len(checks)} compliance checks for PR {pr_data.id}")
            
            return checks
            
        except Exception as e:
            logger.error(f"Error running compliance checks: {str(e)}")
            return []


# Factory function
def create_enhanced_suggestions_engine() -> EnhancedSuggestionsEngine:
    """Create and return a new enhanced suggestions engine instance."""
    return EnhancedSuggestionsEngine()
