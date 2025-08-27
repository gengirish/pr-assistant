# Intelligent PR Assistant MVP

A modular Python implementation of the Intelligent PR Assistant for Atlassian, focusing on core functionality for Sprint 1 deliverables.

## Architecture Overview

```
┌─────────────────┐    ┌─────────────────┐    ┌─────────────────┐
│   FastAPI       │    │    AI Engine    │    │   Integrations  │
│   Backend       │◄──►│   (OpenAI)      │◄──►│ Jira/Bitbucket  │
└─────────────────┘    └─────────────────┘    └─────────────────┘
         │                       │                       │
         ▼                       ▼                       ▼
┌─────────────────┐    ┌─────────────────┐    ┌─────────────────┐
│   Security      │    │   Logging       │    │   Configuration │
│   Layer         │    │   System        │    │   Management    │
└─────────────────┘    └─────────────────┘    └─────────────────┘
```

## MVP Components

### Core Modules

- **AI Scoring Engine** - GPT-4 powered PR quality assessment
- **Jira Integration** - Automatic ticket linking and validation
- **Bitbucket Integration** - Webhook handling and API interactions
- **Security Layer** - JWT authentication, encryption, and rate limiting
- **FastAPI Backend** - RESTful API with async support
- **Logging System** - Structured logging with performance monitoring

### Sprint 1 Features

- ✅ AI-powered PR scoring (clarity, context, completeness, Jira linking)
- ✅ Jira ticket auto-detection and linking
- ✅ Bitbucket webhook integration
- ✅ JWT-based authentication and security
- ✅ Comprehensive logging and monitoring
- ✅ Async API with background task processing

## Quick Start

1. **Prerequisites**

   ```bash
   python >= 3.9
   pip >= 21.0
   OpenAI API key
   Atlassian OAuth credentials
   ```

2. **Installation**

   ```bash
   git clone https://github.com/gengirish/pr-assistant.git
   cd pr-assistant/mvp
   pip install -r requirements.txt
   ```

3. **Configuration**

   ```bash
   cp config/config.example.json config/config.json
   # Edit config.json with your settings

   # Or use environment variables
   cp .env.example .env
   # Edit .env with your configuration
   ```

4. **Run Development Server**

   ```bash
   python main.py
   # Or using uvicorn directly
   uvicorn main:app --reload --host 0.0.0.0 --port 8000
   ```

5. **Run Tests**

   ```bash
   pytest tests/ -v
   ```

## Module Structure

```
mvp/
├── ai_engine/              # AI scoring engine
│   └── scoring_engine.py   # Core scoring logic
├── integrations/           # External service integrations
│   ├── jira_client.py      # Jira API client
│   └── bitbucket_client.py # Bitbucket API client
├── utils/                  # Utility modules
│   ├── security.py         # Security and authentication
│   └── logger.py           # Logging utilities
├── config/                 # Configuration management
│   ├── config.py           # Configuration classes
│   └── config.example.json # Example configuration
├── tests/                  # Test suite
│   └── test_scoring_engine.py # Scoring engine tests
├── main.py                 # FastAPI application
├── requirements.txt        # Python dependencies
└── README.md              # This file
```

## API Endpoints

### Core Endpoints

- `GET /` - Root endpoint with basic info
- `GET /health` - Health check with component status
- `GET /docs` - Interactive API documentation (Swagger UI)

### Analysis Endpoints

- `POST /api/v1/analyze-pr` - Analyze a pull request
- `GET /api/v1/jira/ticket/{ticket_key}` - Get Jira ticket information
- `GET /api/v1/config` - Get application configuration

### Webhook Endpoints

- `POST /api/v1/webhook/bitbucket` - Handle Bitbucket webhooks

## Configuration

The application uses a hierarchical configuration system with environment variables and JSON files:

### Environment Variables

```bash
# Application
APP_NAME="Intelligent PR Assistant"
APP_VERSION="1.0.0"
APP_ENVIRONMENT="development"

# OpenAI
OPENAI_API_KEY="your-openai-api-key"
OPENAI_MODEL="gpt-4-turbo"

# Atlassian
ATLASSIAN_OAUTH_CLIENT_ID="your-client-id"
ATLASSIAN_OAUTH_CLIENT_SECRET="your-client-secret"
JIRA_BASE_URL="https://your-domain.atlassian.net"

# Security
JWT_SECRET="your-jwt-secret"

# Logging
LOG_LEVEL="INFO"
LOG_FORMAT="json"
```

### Scoring Configuration

The scoring algorithm uses weighted components:

- **Clarity** (30%): AI-powered analysis of PR title and description
- **Context** (25%): Analysis of description detail and file scope
- **Completeness** (25%): Presence of tests, documentation, and proper structure
- **Jira Link** (20%): Integration with Jira tickets

## Development Workflow

1. **Local Development**

   ```bash
   # Install dependencies
   pip install -r requirements.txt

   # Run with auto-reload
   python main.py

   # Or with uvicorn
   uvicorn main:app --reload
   ```

2. **Testing**

   ```bash
   # Run all tests
   pytest

   # Run with coverage
   pytest --cov=. --cov-report=html

   # Run specific test file
   pytest tests/test_scoring_engine.py -v
   ```

3. **Code Quality**

   ```bash
   # Format code
   black .

   # Lint code
   flake8 .

   # Type checking
   mypy .
   ```

4. **Deployment**

   ```bash
   # Build for production
   pip install -r requirements.txt --no-dev

   # Run production server
   uvicorn main:app --host 0.0.0.0 --port 8000 --workers 4
   ```

## Security Features

- **JWT Authentication**: Secure token-based authentication
- **Rate Limiting**: Configurable request rate limiting
- **Input Sanitization**: Automatic sanitization of user inputs
- **Webhook Signature Verification**: HMAC-based webhook security
- **Data Encryption**: AES-256-GCM encryption for sensitive data
- **Password Hashing**: PBKDF2 with SHA-256 for secure password storage

## Monitoring and Logging

- **Structured Logging**: JSON-formatted logs with contextual information
- **Performance Monitoring**: Request timing and performance metrics
- **Security Event Logging**: Authentication and security event tracking
- **Integration Monitoring**: External API call success/failure tracking
- **Health Checks**: Component health monitoring and reporting

## Example Usage

### Analyze a Pull Request

```python
import httpx

# Analyze PR
response = httpx.post("http://localhost:8000/api/v1/analyze-pr",
    headers={"Authorization": "Bearer your-jwt-token"},
    json={
        "pr_id": "123",
        "title": "feat: Add user authentication",
        "description": "This PR implements OAuth 2.0 authentication for users",
        "workspace": "myworkspace",
        "repository": "myrepo",
        "files": [
            {"filename": "auth.py", "status": "added"},
            {"filename": "test_auth.py", "status": "added"}
        ],
        "include_jira": True
    }
)

result = response.json()
print(f"Score: {result['total_score']}/10 ({result['rating']})")
print(f"Suggestions: {result['suggestions']}")
```

### Response Format

```json
{
  "pr_id": "123",
  "total_score": 8.2,
  "rating": "good",
  "breakdown": {
    "clarity": 8.5,
    "context": 7.8,
    "completeness": 8.0,
    "jira_link": 9.0
  },
  "suggestions": ["Great job! This PR meets all quality standards."],
  "jira_context": {
    "ticket_id": "AUTH-123",
    "ticket_status": "In Progress",
    "ticket_type": "Story",
    "priority": "High"
  },
  "timestamp": "2024-01-01T12:00:00Z"
}
```

## Next Steps (Sprint 2)

- **Enhanced AI Suggestions**: More detailed and actionable feedback
- **Advanced Analytics**: PR metrics and team performance insights
- **Compliance Checking**: Automated policy and compliance validation
- **Integration Expansion**: Support for additional tools and platforms
- **Performance Optimization**: Caching and response time improvements
- **Admin Dashboard**: Web-based configuration and monitoring interface

## Contributing

1. Fork the repository
2. Create a feature branch (`git checkout -b feature/amazing-feature`)
3. Commit your changes (`git commit -m 'Add amazing feature'`)
4. Push to the branch (`git push origin feature/amazing-feature`)
5. Open a Pull Request

## License

This project is licensed under the MIT License - see the LICENSE file for details.
