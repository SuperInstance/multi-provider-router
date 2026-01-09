# LucidDreamer Multi-Provider Cost-Optimized Router

A sophisticated AI model routing system that intelligently distributes requests across multiple providers (GLM-4, DeepSeek, Claude Haiku, OpenAI, DeepInfra) to minimize costs while maximizing quality.

## 🚀 Key Features

### Cost Optimization
- **GLM-4 as Primary Provider**: Handles 95% of requests at $0.25/1M input tokens
- **Intelligent Cost-Aware Routing**: Balances cost vs quality based on request characteristics
- **Real-time Cost Tracking**: Monitor and control spending with daily budget management
- **Provider Cost Comparison**: Automatic selection of most cost-effective provider for each request

### Provider Support
- **GLM-4**: Ultra-low cost ($0.25/1M input), high quality general purpose model
- **DeepSeek**: Excellent for coding and technical tasks ($0.14/1M input)
- **Claude Haiku 4.5**: Fast conversational AI with strong analysis capabilities
- **OpenAI**: Reliable fallback with structured output support
- **DeepInfra**: Specialty models for heavy lifting (WizardLM, Nemotron, Hermes-3-405B)

### Intelligent Routing
- **Request Type Classification**: Automatically categorizes requests (conversation, coding, analysis, etc.)
- **Provider Specialization**: Routes to providers based on their strengths
- **Fallback Chains**: Automatic failover with multiple backup providers
- **Load Balancing**: Distributes load across providers to prevent overload

### Monitoring & Analytics
- **Real-time Metrics**: Prometheus-compatible metrics export
- **Performance Analytics**: Provider performance tracking and optimization
- **Cost Analysis**: Detailed cost breakdown by provider and time period
- **Health Monitoring**: Continuous health checks with automatic recovery

## 📋 Architecture

```
┌─────────────────┐    ┌──────────────────┐    ┌─────────────────┐
│   Client API    │───▶│  Router Service  │───▶│  GLM-4 (95%)    │
│                 │    │                  │    │                 │
│ - REST API      │    │ - Decision       │    │ - $0.25/1M      │
│ - Streaming     │    │ - Fallback       │    │ - High Quality  │
│ - Health Checks │    │ - Load Balance   │    └─────────────────┘
└─────────────────┘    └──────────────────┘                │
                               │                        │
                               ▼                        │
┌─────────────────┐    ┌──────────────────┐                │
│  Monitoring     │    │   Provider Pool  │                │
│                 │    │                  │                │
│ - Prometheus    │◀───│ - DeepSeek       │                │
│ - Grafana       │    │ - Claude Haiku   │                │
│ - Analytics     │    │ - OpenAI         │                │
│ - Alerts        │    │ - DeepInfra      │                │
└─────────────────┘    └──────────────────┘                │
                                                        │
┌─────────────────┐                                    │
│  Budget & Cost  │                                    │
│                 │                                    ▼
│ - Daily Limits  │    ┌──────────────────┐    ┌─────────────────┐
│ - Real-time     │    │   Cache Layer    │    │  Specialty      │
│ - Alerts        │    │                  │    │  Models         │
│ - Analytics     │    │ - Redis          │    │                 │
└─────────────────┘    │ - Request Cache  │    │ - WizardLM      │
                       │ - Metrics Store  │    │ - Nemotron      │
                       └──────────────────┘    │ - Hermes-3-405B │
                                                └─────────────────┘
```

## 🛠️ Installation

### Prerequisites
- Python 3.10+
- Redis (for caching and rate limiting)
- PostgreSQL (optional, for persistent storage)

### Quick Start

1. **Clone and Setup**
```bash
git clone <repository-url>
cd luciddreamer-router
pip install -r requirements.txt
```

2. **Configure Environment**
```bash
cp .env.example .env
# Edit .env with your API keys and configuration
```

3. **Start Redis**
```bash
docker run -d -p 6379:6379 redis:latest
```

4. **Run the Application**
```bash
python src/main.py
```

### Docker Deployment

```bash
# Build and run with Docker Compose
docker-compose up -d
```

## ⚙️ Configuration

### Environment Variables

```bash
# API Keys
GLM__API_KEY=your-glm-api-key
DEEPSEEK__API_KEY=your-deepseek-api-key
CLAUDE__API_KEY=your-claude-api-key
OPENAI__API_KEY=your-openai-api-key
DEEPINFRA__API_KEY=your-deepinfra-api-key

# Budget Settings
BUDGET__DAILY_BUDGET_USD=100.0
BUDGET__WARNING_THRESHOLD_PERCENTAGE=80.0

# Routing Configuration
ROUTING__GLM_PRIMARY_WEIGHT=0.95
ROUTING__COST_SENSITIVITY_FACTOR=0.7
ROUTING__QUALITY_WEIGHT=0.3

# Monitoring
MONITORING__LOG_LEVEL=INFO
MONITORING__ENABLE_TRACING=true
```

### Provider Configuration

Each provider can be configured with:
- API endpoints and authentication
- Rate limits and timeouts
- Cost per token
- Maximum token limits
- Health check intervals

## 📊 Usage

### Basic Text Generation

```python
import requests

response = requests.post("http://localhost:8000/generate", json={
    "messages": [
        {"role": "user", "content": "Explain quantum computing"}
    ],
    "temperature": 0.7,
    "max_tokens": 500
})

print(response.json())
```

### Streaming Generation

```python
import requests

response = requests.post(
    "http://localhost:8000/generate/stream",
    json={
        "messages": [
            {"role": "user", "content": "Write a story about AI"}
        ],
        "stream": True
    },
    stream=True
)

for line in response.iter_lines():
    if line.startswith(b"data: "):
        content = line[6:].decode('utf-8')
        if content == "[DONE]":
            break
        print(content, end='', flush=True)
```

### Specialty Model Usage

```python
# Force use of DeepInfra specialty model
response = requests.post("http://localhost:8000/generate", json={
    "messages": [
        {"role": "user", "content": "Solve this complex mathematical problem..."}
    ],
    "force_specialty_model": "wizardlm-2-8x22b",
    "priority": "high"
})
```

## 🔍 Monitoring

### Metrics Endpoint

```bash
curl http://localhost:8000/analytics/metrics
```

### Health Check

```bash
curl http://localhost:8000/health
```

### Provider Status

```bash
curl http://localhost:8000/providers
```

### Cost Analytics

```bash
curl "http://localhost:8000/analytics/costs?hours=24"
```

## 📈 Cost Optimization Strategy

### Primary Routing Logic

1. **95% GLM-4**: Default choice for cost efficiency
2. **DeepSeek**: Coding and technical tasks
3. **Claude Haiku**: Conversational and analysis tasks
4. **OpenAI**: Fallback and structured output
5. **DeepInfra**: Complex reasoning and heavy lifting

### Cost Savings Example

| Provider | Cost/1M Input | Use Case | Monthly Cost (100K requests) |
|----------|---------------|----------|------------------------------|
| GLM-4 | $0.25 | General | ~$25 |
| DeepSeek | $0.14 | Coding | ~$14 |
| Claude Haiku | $0.25 | Analysis | ~$25 |
| OpenAI | $0.15 | Fallback | ~$15 |
| **Weighted Average** | **~$0.20** | **Optimized** | **~$20** |

**Savings vs OpenAI-only**: ~50% cost reduction

## 🔧 Advanced Configuration

### Custom Routing Rules

```python
# Configure custom routing weights
ROUTING__PROVIDER_WEIGHTS__GLM=0.6
ROUTING__PROVIDER_WEIGHTS__DEEPSEEK=0.2
ROUTING__PROVIDER_WEIGHTS__CLAUDE=0.15
ROUTING__PROVIDER_WEIGHTS__OPENAI=0.05
```

### Rate Limiting

```python
# Set custom rate limits per user
rate_limiter.set_user_rate_limit("user123", RateLimitRule(
    requests_per_minute=100,
    requests_per_hour=5000
))
```

### Budget Management

```python
# Set daily budget alerts
BUDGET__WARNING_THRESHOLD_PERCENTAGE=75.0
BUDGET__HARD_LIMIT_PERCENTAGE=95.0
```

## 🚨 Troubleshooting

### Common Issues

1. **Provider Timeouts**
   - Check network connectivity
   - Increase timeout settings
   - Verify API key validity

2. **High Error Rates**
   - Check provider health status
   - Review rate limits
   - Examine fallback configuration

3. **Cost Overruns**
   - Monitor usage analytics
   - Adjust routing weights
   - Set stricter budget limits

### Debug Mode

```bash
# Enable debug logging
export MONITORING__LOG_LEVEL=DEBUG
python src/main.py
```

## 📚 API Reference

### Endpoints

- `POST /generate` - Generate text completion
- `POST /generate/stream` - Streaming generation
- `GET /health` - System health check
- `GET /providers` - Provider information
- `GET /analytics/costs` - Cost analytics
- `GET /analytics/metrics` - Prometheus metrics

### Request Format

```json
{
    "messages": [
        {"role": "system", "content": "You are a helpful assistant."},
        {"role": "user", "content": "Hello, how are you?"}
    ],
    "temperature": 0.7,
    "max_tokens": 500,
    "top_p": 1.0,
    "user_id": "user123",
    "priority": "normal",
    "preferred_provider": "glm",
    "force_specialty_model": null
}
```

### Response Format

```json
{
    "success": true,
    "data": {
        "request_id": "req-123",
        "content": "Generated response text...",
        "provider_used": "glm",
        "model_used": "glm-4-flash",
        "input_tokens": 25,
        "output_tokens": 150,
        "cost_usd": 0.00005,
        "processing_time_ms": 800,
        "cached": false
    },
    "request_id": "req-123",
    "timestamp": "2025-01-21T10:30:00Z"
}
```

## 🤝 Contributing

1. Fork the repository
2. Create a feature branch
3. Make your changes
4. Add tests
5. Submit a pull request

## 📄 License

This project is licensed under the MIT License - see the LICENSE file for details.

## 🆘 Support

- Create an issue for bug reports
- Check the documentation for common questions
- Review the troubleshooting guide
- Contact the development team for enterprise support

---

**LucidDreamer Router** - Intelligent AI routing for cost-effective, high-quality text generation.