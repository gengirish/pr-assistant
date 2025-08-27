"""Configuration management for PR Assistant MVP."""

import os
import json
from typing import Dict, Any, Optional
from pydantic_settings import BaseSettings
from pydantic import Field
from dotenv import load_dotenv

# Load environment variables
load_dotenv()


class AWSConfig(BaseSettings):
    """AWS configuration settings."""
    
    region: str = Field(default="us-east-1", env="AWS_REGION")
    dynamodb_table_name: str = Field(default="pr-assistant-data", env="AWS_DYNAMODB_TABLE")
    dynamodb_endpoint: Optional[str] = Field(default=None, env="AWS_DYNAMODB_ENDPOINT")
    lambda_function_name: str = Field(default="pr-assistant-processor", env="AWS_LAMBDA_FUNCTION")
    lambda_timeout: int = Field(default=30, env="AWS_LAMBDA_TIMEOUT")
    kms_key_id: Optional[str] = Field(default=None, env="AWS_KMS_KEY_ID")


class AtlassianConfig(BaseSettings):
    """Atlassian configuration settings."""
    
    oauth_client_id: str = Field(env="ATLASSIAN_OAUTH_CLIENT_ID")
    oauth_client_secret: str = Field(env="ATLASSIAN_OAUTH_CLIENT_SECRET")
    oauth_scopes: list = Field(
        default=["read:jira-work", "write:jira-work", "read:bitbucket-repo"],
        env="ATLASSIAN_OAUTH_SCOPES"
    )
    forge_app_id: Optional[str] = Field(default=None, env="ATLASSIAN_FORGE_APP_ID")
    bitbucket_base_url: str = Field(
        default="https://api.bitbucket.org/2.0",
        env="BITBUCKET_BASE_URL"
    )
    bitbucket_webhook_secret: Optional[str] = Field(
        default=None,
        env="BITBUCKET_WEBHOOK_SECRET"
    )
    jira_base_url: str = Field(env="JIRA_BASE_URL")
    jira_api_version: str = Field(default="3", env="JIRA_API_VERSION")


class OpenAIConfig(BaseSettings):
    """OpenAI configuration settings."""
    
    api_key: str = Field(env="OPENAI_API_KEY")
    model: str = Field(default="gpt-4-turbo", env="OPENAI_MODEL")
    max_tokens: int = Field(default=2000, env="OPENAI_MAX_TOKENS")
    temperature: float = Field(default=0.3, env="OPENAI_TEMPERATURE")


class ScoringConfig(BaseSettings):
    """Scoring algorithm configuration."""
    
    clarity_weight: float = Field(default=0.3, env="SCORING_CLARITY_WEIGHT")
    context_weight: float = Field(default=0.25, env="SCORING_CONTEXT_WEIGHT")
    completeness_weight: float = Field(default=0.25, env="SCORING_COMPLETENESS_WEIGHT")
    jira_link_weight: float = Field(default=0.2, env="SCORING_JIRA_WEIGHT")
    
    excellent_threshold: float = Field(default=8.5, env="SCORING_EXCELLENT_THRESHOLD")
    good_threshold: float = Field(default=7.0, env="SCORING_GOOD_THRESHOLD")
    needs_improvement_threshold: float = Field(default=5.0, env="SCORING_NEEDS_IMPROVEMENT_THRESHOLD")
    
    @property
    def weights(self) -> Dict[str, float]:
        """Get scoring weights as dictionary."""
        return {
            "clarity": self.clarity_weight,
            "context": self.context_weight,
            "completeness": self.completeness_weight,
            "jira_link": self.jira_link_weight
        }
    
    @property
    def thresholds(self) -> Dict[str, float]:
        """Get scoring thresholds as dictionary."""
        return {
            "excellent": self.excellent_threshold,
            "good": self.good_threshold,
            "needs_improvement": self.needs_improvement_threshold
        }


class SecurityConfig(BaseSettings):
    """Security configuration settings."""
    
    encryption_algorithm: str = Field(default="AES-256-GCM", env="ENCRYPTION_ALGORITHM")
    key_rotation_days: int = Field(default=90, env="KEY_ROTATION_DAYS")
    jwt_secret: str = Field(env="JWT_SECRET")
    jwt_expires_in: str = Field(default="24h", env="JWT_EXPIRES_IN")
    jwt_algorithm: str = Field(default="HS256", env="JWT_ALGORITHM")


class LoggingConfig(BaseSettings):
    """Logging configuration settings."""
    
    level: str = Field(default="INFO", env="LOG_LEVEL")
    format: str = Field(default="json", env="LOG_FORMAT")
    destinations: list = Field(default=["console"], env="LOG_DESTINATIONS")


class FeatureConfig(BaseSettings):
    """Feature flags configuration."""
    
    ai_suggestions: bool = Field(default=True, env="FEATURE_AI_SUGGESTIONS")
    jira_auto_link: bool = Field(default=True, env="FEATURE_JIRA_AUTO_LINK")
    compliance_check: bool = Field(default=True, env="FEATURE_COMPLIANCE_CHECK")
    analytics: bool = Field(default=False, env="FEATURE_ANALYTICS")


class AppConfig(BaseSettings):
    """Main application configuration."""
    
    name: str = Field(default="Intelligent PR Assistant", env="APP_NAME")
    version: str = Field(default="1.0.0", env="APP_VERSION")
    environment: str = Field(default="development", env="APP_ENVIRONMENT")
    debug: bool = Field(default=False, env="APP_DEBUG")
    host: str = Field(default="0.0.0.0", env="APP_HOST")
    port: int = Field(default=8000, env="APP_PORT")
    
    # Sub-configurations
    aws: AWSConfig = Field(default_factory=AWSConfig)
    atlassian: AtlassianConfig = Field(default_factory=AtlassianConfig)
    openai: OpenAIConfig = Field(default_factory=OpenAIConfig)
    scoring: ScoringConfig = Field(default_factory=ScoringConfig)
    security: SecurityConfig = Field(default_factory=SecurityConfig)
    logging: LoggingConfig = Field(default_factory=LoggingConfig)
    features: FeatureConfig = Field(default_factory=FeatureConfig)
    
    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"
        case_sensitive = False


def load_config() -> AppConfig:
    """Load and return application configuration."""
    return AppConfig()


def load_config_from_file(config_path: str) -> Dict[str, Any]:
    """Load configuration from JSON file."""
    try:
        with open(config_path, 'r', encoding='utf-8') as f:
            return json.load(f)
    except FileNotFoundError:
        raise FileNotFoundError(f"Configuration file not found: {config_path}")
    except json.JSONDecodeError as e:
        raise ValueError(f"Invalid JSON in configuration file: {e}")


# Global configuration instance
config = load_config()
