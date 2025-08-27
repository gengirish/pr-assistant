"""Analytics and metrics engine for Sprint 2."""

import asyncio
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Any, Tuple
import logging
from dataclasses import dataclass, asdict
from collections import defaultdict
import statistics

from config.config import config
from ai_engine.scoring_engine import ScoringResult
from integrations.jira_client import JiraTicket

logger = logging.getLogger(__name__)


@dataclass
class PRMetrics:
    """Data model for PR metrics."""
    pr_id: str
    repository: str
    author: str
    created_at: datetime
    analyzed_at: datetime
    score: float
    rating: str
    breakdown: Dict[str, float]
    file_count: int
    has_tests: bool
    has_jira_link: bool
    review_time_hours: Optional[float] = None
    merge_time_hours: Optional[float] = None
    comment_count: int = 0
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for JSON serialization."""
        data = asdict(self)
        # Convert datetime objects to ISO strings
        data['created_at'] = self.created_at.isoformat()
        data['analyzed_at'] = self.analyzed_at.isoformat()
        return data


@dataclass
class TeamMetrics:
    """Data model for team-level metrics."""
    team_name: str
    period_start: datetime
    period_end: datetime
    total_prs: int
    average_score: float
    score_distribution: Dict[str, int]  # excellent, good, needs-improvement, poor
    average_review_time_hours: float
    average_file_count: float
    test_coverage_percentage: float
    jira_link_compliance: float
    top_contributors: List[Dict[str, Any]]
    improvement_trends: Dict[str, float]
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for JSON serialization."""
        data = asdict(self)
        data['period_start'] = self.period_start.isoformat()
        data['period_end'] = self.period_end.isoformat()
        return data


@dataclass
class DeveloperMetrics:
    """Data model for individual developer metrics."""
    developer_name: str
    period_start: datetime
    period_end: datetime
    total_prs: int
    average_score: float
    score_trend: List[Tuple[datetime, float]]
    strengths: List[str]
    improvement_areas: List[str]
    productivity_score: float
    quality_score: float
    collaboration_score: float
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for JSON serialization."""
        data = asdict(self)
        data['period_start'] = self.period_start.isoformat()
        data['period_end'] = self.period_end.isoformat()
        # Convert datetime tuples in score_trend
        data['score_trend'] = [(dt.isoformat(), score) for dt, score in self.score_trend]
        return data


class MetricsEngine:
    """Analytics and metrics engine for PR analysis."""
    
    def __init__(self):
        """Initialize the metrics engine."""
        # In-memory storage for MVP (would use database in production)
        self.pr_metrics: List[PRMetrics] = []
        self.analysis_cache: Dict[str, Any] = {}
    
    def record_pr_analysis(
        self,
        pr_id: str,
        repository: str,
        author: str,
        created_at: datetime,
        scoring_result: ScoringResult,
        file_count: int,
        has_tests: bool,
        has_jira_link: bool,
        comment_count: int = 0
    ) -> PRMetrics:
        """
        Record PR analysis results for metrics tracking.
        
        Args:
            pr_id: Pull request ID
            repository: Repository name
            author: PR author
            created_at: PR creation timestamp
            scoring_result: Analysis results
            file_count: Number of files changed
            has_tests: Whether PR includes tests
            has_jira_link: Whether PR is linked to Jira
            comment_count: Number of comments on PR
            
        Returns:
            PRMetrics object
        """
        try:
            metrics = PRMetrics(
                pr_id=pr_id,
                repository=repository,
                author=author,
                created_at=created_at,
                analyzed_at=datetime.utcnow(),
                score=scoring_result.total_score,
                rating=scoring_result.rating,
                breakdown=scoring_result.breakdown,
                file_count=file_count,
                has_tests=has_tests,
                has_jira_link=has_jira_link,
                comment_count=comment_count
            )
            
            self.pr_metrics.append(metrics)
            
            # Clear cache to force recalculation
            self.analysis_cache.clear()
            
            logger.info(f"Recorded metrics for PR {pr_id}")
            
            return metrics
            
        except Exception as e:
            logger.error(f"Error recording PR metrics: {str(e)}")
            raise
    
    def get_team_metrics(
        self,
        team_name: str,
        period_days: int = 30,
        repository_filter: Optional[str] = None
    ) -> TeamMetrics:
        """
        Calculate team-level metrics for a given period.
        
        Args:
            team_name: Team identifier
            period_days: Number of days to analyze
            repository_filter: Optional repository filter
            
        Returns:
            TeamMetrics object
        """
        try:
            cache_key = f"team_{team_name}_{period_days}_{repository_filter}"
            
            if cache_key in self.analysis_cache:
                return self.analysis_cache[cache_key]
            
            end_date = datetime.utcnow()
            start_date = end_date - timedelta(days=period_days)
            
            # Filter PRs for the period and repository
            filtered_prs = [
                pr for pr in self.pr_metrics
                if start_date <= pr.analyzed_at <= end_date
                and (not repository_filter or pr.repository == repository_filter)
            ]
            
            if not filtered_prs:
                # Return empty metrics
                return TeamMetrics(
                    team_name=team_name,
                    period_start=start_date,
                    period_end=end_date,
                    total_prs=0,
                    average_score=0.0,
                    score_distribution={"excellent": 0, "good": 0, "needs-improvement": 0, "poor": 0},
                    average_review_time_hours=0.0,
                    average_file_count=0.0,
                    test_coverage_percentage=0.0,
                    jira_link_compliance=0.0,
                    top_contributors=[],
                    improvement_trends={}
                )
            
            # Calculate metrics
            total_prs = len(filtered_prs)
            average_score = statistics.mean([pr.score for pr in filtered_prs])
            
            # Score distribution
            score_distribution = {"excellent": 0, "good": 0, "needs-improvement": 0, "poor": 0}
            for pr in filtered_prs:
                score_distribution[pr.rating] += 1
            
            # Review time (mock data for MVP)
            review_times = [pr.review_time_hours for pr in filtered_prs if pr.review_time_hours]
            average_review_time = statistics.mean(review_times) if review_times else 24.0
            
            # File count
            average_file_count = statistics.mean([pr.file_count for pr in filtered_prs])
            
            # Test coverage
            prs_with_tests = sum(1 for pr in filtered_prs if pr.has_tests)
            test_coverage_percentage = (prs_with_tests / total_prs) * 100
            
            # Jira compliance
            prs_with_jira = sum(1 for pr in filtered_prs if pr.has_jira_link)
            jira_link_compliance = (prs_with_jira / total_prs) * 100
            
            # Top contributors
            contributor_stats = defaultdict(lambda: {"count": 0, "total_score": 0.0})
            for pr in filtered_prs:
                contributor_stats[pr.author]["count"] += 1
                contributor_stats[pr.author]["total_score"] += pr.score
            
            top_contributors = []
            for author, stats in contributor_stats.items():
                avg_score = stats["total_score"] / stats["count"]
                top_contributors.append({
                    "name": author,
                    "pr_count": stats["count"],
                    "average_score": round(avg_score, 1)
                })
            
            top_contributors.sort(key=lambda x: x["average_score"], reverse=True)
            top_contributors = top_contributors[:5]  # Top 5
            
            # Improvement trends (compare with previous period)
            prev_start = start_date - timedelta(days=period_days)
            prev_prs = [
                pr for pr in self.pr_metrics
                if prev_start <= pr.analyzed_at < start_date
                and (not repository_filter or pr.repository == repository_filter)
            ]
            
            improvement_trends = {}
            if prev_prs:
                prev_avg_score = statistics.mean([pr.score for pr in prev_prs])
                improvement_trends["score_change"] = average_score - prev_avg_score
                
                prev_test_coverage = (sum(1 for pr in prev_prs if pr.has_tests) / len(prev_prs)) * 100
                improvement_trends["test_coverage_change"] = test_coverage_percentage - prev_test_coverage
            
            metrics = TeamMetrics(
                team_name=team_name,
                period_start=start_date,
                period_end=end_date,
                total_prs=total_prs,
                average_score=round(average_score, 1),
                score_distribution=score_distribution,
                average_review_time_hours=round(average_review_time, 1),
                average_file_count=round(average_file_count, 1),
                test_coverage_percentage=round(test_coverage_percentage, 1),
                jira_link_compliance=round(jira_link_compliance, 1),
                top_contributors=top_contributors,
                improvement_trends=improvement_trends
            )
            
            # Cache the result
            self.analysis_cache[cache_key] = metrics
            
            logger.info(f"Calculated team metrics for {team_name}")
            
            return metrics
            
        except Exception as e:
            logger.error(f"Error calculating team metrics: {str(e)}")
            raise
    
    def get_developer_metrics(
        self,
        developer_name: str,
        period_days: int = 30
    ) -> DeveloperMetrics:
        """
        Calculate individual developer metrics.
        
        Args:
            developer_name: Developer identifier
            period_days: Number of days to analyze
            
        Returns:
            DeveloperMetrics object
        """
        try:
            cache_key = f"dev_{developer_name}_{period_days}"
            
            if cache_key in self.analysis_cache:
                return self.analysis_cache[cache_key]
            
            end_date = datetime.utcnow()
            start_date = end_date - timedelta(days=period_days)
            
            # Filter PRs for the developer and period
            dev_prs = [
                pr for pr in self.pr_metrics
                if pr.author == developer_name
                and start_date <= pr.analyzed_at <= end_date
            ]
            
            if not dev_prs:
                # Return empty metrics
                return DeveloperMetrics(
                    developer_name=developer_name,
                    period_start=start_date,
                    period_end=end_date,
                    total_prs=0,
                    average_score=0.0,
                    score_trend=[],
                    strengths=[],
                    improvement_areas=[],
                    productivity_score=0.0,
                    quality_score=0.0,
                    collaboration_score=0.0
                )
            
            # Calculate basic metrics
            total_prs = len(dev_prs)
            average_score = statistics.mean([pr.score for pr in dev_prs])
            
            # Score trend (weekly averages)
            score_trend = []
            current_date = start_date
            while current_date < end_date:
                week_end = current_date + timedelta(days=7)
                week_prs = [
                    pr for pr in dev_prs
                    if current_date <= pr.analyzed_at < week_end
                ]
                if week_prs:
                    week_avg = statistics.mean([pr.score for pr in week_prs])
                    score_trend.append((current_date, round(week_avg, 1)))
                current_date = week_end
            
            # Analyze strengths and improvement areas
            breakdown_averages = defaultdict(list)
            for pr in dev_prs:
                for category, score in pr.breakdown.items():
                    breakdown_averages[category].append(score)
            
            category_scores = {
                category: statistics.mean(scores)
                for category, scores in breakdown_averages.items()
            }
            
            strengths = [
                category for category, score in category_scores.items()
                if score >= 8.0
            ]
            
            improvement_areas = [
                category for category, score in category_scores.items()
                if score < 6.0
            ]
            
            # Calculate composite scores
            productivity_score = min(10.0, (total_prs / period_days) * 30 * 10)  # PRs per month * 10
            quality_score = average_score
            
            # Collaboration score (based on PR size, comments, etc.)
            avg_file_count = statistics.mean([pr.file_count for pr in dev_prs])
            avg_comments = statistics.mean([pr.comment_count for pr in dev_prs])
            collaboration_score = min(10.0, (10 - avg_file_count * 0.2) + (avg_comments * 0.5))
            collaboration_score = max(0.0, collaboration_score)
            
            metrics = DeveloperMetrics(
                developer_name=developer_name,
                period_start=start_date,
                period_end=end_date,
                total_prs=total_prs,
                average_score=round(average_score, 1),
                score_trend=score_trend,
                strengths=strengths,
                improvement_areas=improvement_areas,
                productivity_score=round(productivity_score, 1),
                quality_score=round(quality_score, 1),
                collaboration_score=round(collaboration_score, 1)
            )
            
            # Cache the result
            self.analysis_cache[cache_key] = metrics
            
            logger.info(f"Calculated developer metrics for {developer_name}")
            
            return metrics
            
        except Exception as e:
            logger.error(f"Error calculating developer metrics: {str(e)}")
            raise
    
    def get_repository_insights(
        self,
        repository: str,
        period_days: int = 30
    ) -> Dict[str, Any]:
        """
        Get insights for a specific repository.
        
        Args:
            repository: Repository name
            period_days: Number of days to analyze
            
        Returns:
            Dictionary with repository insights
        """
        try:
            end_date = datetime.utcnow()
            start_date = end_date - timedelta(days=period_days)
            
            repo_prs = [
                pr for pr in self.pr_metrics
                if pr.repository == repository
                and start_date <= pr.analyzed_at <= end_date
            ]
            
            if not repo_prs:
                return {
                    "repository": repository,
                    "period_days": period_days,
                    "total_prs": 0,
                    "insights": []
                }
            
            insights = []
            
            # Quality trends
            scores = [pr.score for pr in repo_prs]
            avg_score = statistics.mean(scores)
            
            if avg_score >= 8.0:
                insights.append({
                    "type": "positive",
                    "title": "High Quality Standards",
                    "description": f"Repository maintains excellent code quality with average score of {avg_score:.1f}"
                })
            elif avg_score < 6.0:
                insights.append({
                    "type": "warning",
                    "title": "Quality Concerns",
                    "description": f"Repository has below-average quality scores ({avg_score:.1f}). Consider code review improvements."
                })
            
            # Test coverage insights
            test_coverage = (sum(1 for pr in repo_prs if pr.has_tests) / len(repo_prs)) * 100
            
            if test_coverage < 50:
                insights.append({
                    "type": "warning",
                    "title": "Low Test Coverage",
                    "description": f"Only {test_coverage:.1f}% of PRs include tests. Consider improving test practices."
                })
            elif test_coverage >= 80:
                insights.append({
                    "type": "positive",
                    "title": "Excellent Test Coverage",
                    "description": f"Repository has strong test coverage with {test_coverage:.1f}% of PRs including tests."
                })
            
            # PR size insights
            avg_file_count = statistics.mean([pr.file_count for pr in repo_prs])
            
            if avg_file_count > 15:
                insights.append({
                    "type": "info",
                    "title": "Large PR Size",
                    "description": f"Average PR touches {avg_file_count:.1f} files. Consider breaking down large changes."
                })
            
            # Jira compliance
            jira_compliance = (sum(1 for pr in repo_prs if pr.has_jira_link) / len(repo_prs)) * 100
            
            if jira_compliance < 70:
                insights.append({
                    "type": "warning",
                    "title": "Low Jira Compliance",
                    "description": f"Only {jira_compliance:.1f}% of PRs are linked to Jira tickets."
                })
            
            return {
                "repository": repository,
                "period_days": period_days,
                "total_prs": len(repo_prs),
                "average_score": round(avg_score, 1),
                "test_coverage": round(test_coverage, 1),
                "jira_compliance": round(jira_compliance, 1),
                "average_file_count": round(avg_file_count, 1),
                "insights": insights
            }
            
        except Exception as e:
            logger.error(f"Error generating repository insights: {str(e)}")
            raise
    
    def get_quality_trends(self, period_days: int = 90) -> Dict[str, Any]:
        """
        Get overall quality trends across all repositories.
        
        Args:
            period_days: Number of days to analyze
            
        Returns:
            Dictionary with quality trend data
        """
        try:
            end_date = datetime.utcnow()
            start_date = end_date - timedelta(days=period_days)
            
            # Get all PRs in the period
            period_prs = [
                pr for pr in self.pr_metrics
                if start_date <= pr.analyzed_at <= end_date
            ]
            
            if not period_prs:
                return {"trends": [], "summary": {}}
            
            # Calculate weekly trends
            trends = []
            current_date = start_date
            
            while current_date < end_date:
                week_end = current_date + timedelta(days=7)
                week_prs = [
                    pr for pr in period_prs
                    if current_date <= pr.analyzed_at < week_end
                ]
                
                if week_prs:
                    avg_score = statistics.mean([pr.score for pr in week_prs])
                    test_coverage = (sum(1 for pr in week_prs if pr.has_tests) / len(week_prs)) * 100
                    jira_compliance = (sum(1 for pr in week_prs if pr.has_jira_link) / len(week_prs)) * 100
                    
                    trends.append({
                        "week_start": current_date.isoformat(),
                        "pr_count": len(week_prs),
                        "average_score": round(avg_score, 1),
                        "test_coverage": round(test_coverage, 1),
                        "jira_compliance": round(jira_compliance, 1)
                    })
                
                current_date = week_end
            
            # Calculate summary
            overall_avg = statistics.mean([pr.score for pr in period_prs])
            overall_test_coverage = (sum(1 for pr in period_prs if pr.has_tests) / len(period_prs)) * 100
            overall_jira_compliance = (sum(1 for pr in period_prs if pr.has_jira_link) / len(period_prs)) * 100
            
            summary = {
                "total_prs": len(period_prs),
                "average_score": round(overall_avg, 1),
                "test_coverage": round(overall_test_coverage, 1),
                "jira_compliance": round(overall_jira_compliance, 1),
                "period_days": period_days
            }
            
            return {
                "trends": trends,
                "summary": summary
            }
            
        except Exception as e:
            logger.error(f"Error calculating quality trends: {str(e)}")
            raise


# Factory function
def create_metrics_engine() -> MetricsEngine:
    """Create and return a new metrics engine instance."""
    return MetricsEngine()
