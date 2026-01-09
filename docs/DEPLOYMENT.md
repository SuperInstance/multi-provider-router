# LucidDreamer Router Deployment Guide

This comprehensive guide covers deploying the LucidDreamer Multi-Provider Cost-Optimized Router in various environments.

## 🚀 Quick Start (Development)

### Prerequisites
- Python 3.10+
- Redis
- Git

### Local Development Setup

1. **Clone and Setup**
```bash
git clone <repository-url>
cd luciddreamer-router
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate
pip install -r requirements.txt
```

2. **Start Redis**
```bash
# Using Docker
docker run -d -p 6379:6379 redis:latest

# Or install locally
# Ubuntu/Debian: sudo apt-get install redis-server
# macOS: brew install redis
# Start with: redis-server
```

3. **Configure Environment**
```bash
cp .env.example .env
# Edit .env with your API keys
```

4. **Run the Application**
```bash
python src/main.py
```

The service will be available at `http://localhost:8000`

## 🐳 Docker Deployment

### Using Docker Compose (Recommended)

1. **Configure Environment**
```bash
cp .env.example .env
# Edit .env with your configuration
```

2. **Start Services**
```bash
docker-compose up -d
```

3. **Verify Deployment**
```bash
# Check health
curl http://localhost:8000/health

# Check logs
docker-compose logs -f luciddreamer-router

# Check all services
docker-compose ps
```

### Individual Docker Deployment

1. **Build Image**
```bash
docker build -t luciddreamer-router .
```

2. **Run with Dependencies**
```bash
# Start Redis
docker run -d --name redis -p 6379:6379 redis:latest

# Start Router
docker run -d \
  --name luciddreamer-router \
  -p 8000:8000 \
  --env-file .env \
  --link redis:redis \
  luciddreamer-router
```

## ☁️ Cloud Deployment

### AWS ECS Deployment

1. **Create ECR Repository**
```bash
aws ecr create-repository --repository-name luciddreamer-router
```

2. **Push Image**
```bash
# Login to ECR
aws ecr get-login-password --region us-west-2 | docker login --username AWS --password-stdin <account-id>.dkr.ecr.us-west-2.amazonaws.com

# Tag and push
docker tag luciddreamer-router:latest <account-id>.dkr.ecr.us-west-2.amazonaws.com/luciddreamer-router:latest
docker push <account-id>.dkr.ecr.us-west-2.amazonaws.com/luciddreamer-router:latest
```

3. **Create ECS Task Definition**
```json
{
  "family": "luciddreamer-router",
  "networkMode": "awsvpc",
  "requiresCompatibilities": ["FARGATE"],
  "cpu": "256",
  "memory": "512",
  "executionRoleArn": "arn:aws:iam::<account-id>:role/ecsTaskExecutionRole",
  "taskRoleArn": "arn:aws:iam::<account-id>:role/ecsTaskRole",
  "containerDefinitions": [
    {
      "name": "luciddreamer-router",
      "image": "<account-id>.dkr.ecr.us-west-2.amazonaws.com/luciddreamer-router:latest",
      "portMappings": [
        {
          "containerPort": 8000,
          "protocol": "tcp"
        }
      ],
      "environment": [
        {
          "name": "ENVIRONMENT",
          "value": "production"
        }
      ],
      "secrets": [
        {
          "name": "GLM__API_KEY",
          "valueFrom": "arn:aws:secretsmanager:us-west-2:<account-id>:secret:luciddreamer/api-keys"
        }
      ],
      "logConfiguration": {
        "logDriver": "awslogs",
        "options": {
          "awslogs-group": "/ecs/luciddreamer-router",
          "awslogs-region": "us-west-2",
          "awslogs-stream-prefix": "ecs"
        }
      },
      "healthCheck": {
        "command": ["CMD-SHELL", "curl -f http://localhost:8000/health || exit 1"],
        "interval": 30,
        "timeout": 5,
        "retries": 3
      }
    }
  ]
}
```

### Google Cloud Run Deployment

1. **Build and Push to GCR**
```bash
# Configure gcloud
gcloud config set project your-project-id
gcloud auth configure-docker

# Build and push
docker build -t gcr.io/your-project-id/luciddreamer-router .
docker push gcr.io/your-project-id/luciddreamer-router
```

2. **Deploy to Cloud Run**
```bash
gcloud run deploy luciddreamer-router \
  --image gcr.io/your-project-id/luciddreamer-router \
  --platform managed \
  --region us-central1 \
  --allow-unauthenticated \
  --memory 512Mi \
  --cpu 1 \
  --max-instances 10 \
  --set-env-vars ENVIRONMENT=production \
  --set-secrets GLM__API_KEY=glm-api-key:latest
```

### Azure Container Instances

1. **Create Container Instance**
```bash
az container create \
  --resource-group luciddreamer-rg \
  --name luciddreamer-router \
  --image luciddreamer-router:latest \
  --cpu 1 \
  --memory 1 \
  --ports 8000 \
  --environment-variables ENVIRONMENT=production \
  --secure-environment-variables GLM__API_KEY=$GLM_API_KEY \
  --dns-name-label luciddreamer-router-unique
```

## 🏗️ Production Configuration

### Environment Variables

```bash
# Production Settings
ENVIRONMENT=production
DEBUG=false

# Security
SECRET_KEY=your-very-secure-secret-key

# API Configuration
API_HOST=0.0.0.0
API_PORT=8000

# Redis Configuration
REDIS__URL=redis://redis:6379/0
REDIS__MAX_CONNECTIONS=20

# Database (if using PostgreSQL)
DATABASE__URL=postgresql://user:pass@postgres:5432/luciddreamer_router

# Budget Management
BUDGET__DAILY_BUDGET_USD=500.0
BUDGET__WARNING_THRESHOLD_PERCENTAGE=75.0
BUDGET__HARD_LIMIT_PERCENTAGE=95.0

# Routing Configuration
ROUTING__GLM_PRIMARY_WEIGHT=0.95
ROUTING__COST_SENSITIVITY_FACTOR=0.7
ROUTING__QUALITY_WEIGHT=0.3

# Monitoring
MONITORING__LOG_LEVEL=INFO
MONITORING__ENABLE_TRACING=true
MONITORING__PERFORMANCE_TRACKING_ENABLED=true
```

### Kubernetes Deployment

1. **Create ConfigMap**
```yaml
# configmap.yaml
apiVersion: v1
kind: ConfigMap
metadata:
  name: luciddreamer-config
data:
  ENVIRONMENT: "production"
  REDIS__URL: "redis://redis-service:6379/0"
  BUDGET__DAILY_BUDGET_USD: "500.0"
  ROUTING__GLM_PRIMARY_WEIGHT: "0.95"
```

2. **Create Secret**
```yaml
# secret.yaml
apiVersion: v1
kind: Secret
metadata:
  name: luciddreamer-secrets
type: Opaque
data:
  GLM__API_KEY: <base64-encoded-key>
  DEEPSEEK__API_KEY: <base64-encoded-key>
  CLAUDE__API_KEY: <base64-encoded-key>
  OPENAI__API_KEY: <base64-encoded-key>
  DEEPINFRA__API_KEY: <base64-encoded-key>
```

3. **Deployment YAML**
```yaml
# deployment.yaml
apiVersion: apps/v1
kind: Deployment
metadata:
  name: luciddreamer-router
spec:
  replicas: 3
  selector:
    matchLabels:
      app: luciddreamer-router
  template:
    metadata:
      labels:
        app: luciddreamer-router
    spec:
      containers:
      - name: luciddreamer-router
        image: luciddreamer-router:latest
        ports:
        - containerPort: 8000
        envFrom:
        - configMapRef:
            name: luciddreamer-config
        - secretRef:
            name: luciddreamer-secrets
        resources:
          requests:
            memory: "512Mi"
            cpu: "500m"
          limits:
            memory: "1Gi"
            cpu: "1000m"
        livenessProbe:
          httpGet:
            path: /health
            port: 8000
          initialDelaySeconds: 30
          periodSeconds: 10
        readinessProbe:
          httpGet:
            path: /health
            port: 8000
          initialDelaySeconds: 5
          periodSeconds: 5
---
apiVersion: v1
kind: Service
metadata:
  name: luciddreamer-service
spec:
  selector:
    app: luciddreamer-router
  ports:
  - port: 80
    targetPort: 8000
  type: LoadBalancer
```

4. **Redis Deployment**
```yaml
# redis.yaml
apiVersion: apps/v1
kind: Deployment
metadata:
  name: redis
spec:
  replicas: 1
  selector:
    matchLabels:
      app: redis
  template:
    metadata:
      labels:
        app: redis
    spec:
      containers:
      - name: redis
        image: redis:7-alpine
        ports:
        - containerPort: 6379
        resources:
          requests:
            memory: "256Mi"
            cpu: "250m"
          limits:
            memory: "512Mi"
            cpu: "500m"
---
apiVersion: v1
kind: Service
metadata:
  name: redis-service
spec:
  selector:
    app: redis
  ports:
  - port: 6379
    targetPort: 6379
```

## 🔧 Monitoring Setup

### Prometheus Configuration

```yaml
# monitoring/prometheus.yml
global:
  scrape_interval: 15s

scrape_configs:
  - job_name: 'luciddreamer-router'
    static_configs:
      - targets: ['luciddreamer-router:8000']
    metrics_path: '/analytics/metrics'
    scrape_interval: 30s
```

### Grafana Dashboard

1. **Add Prometheus Data Source**
   - URL: `http://prometheus:9090`
   - Access: Direct

2. **Import Dashboard**
   - Use the provided dashboard JSON
   - Or create custom panels for:
     - Request rates by provider
     - Cost tracking
     - Response times
     - Error rates
     - Health status

### Alerting Rules

```yaml
# monitoring/alerts.yml
groups:
- name: luciddreamer-alerts
  rules:
  - alert: HighErrorRate
    expr: rate(luciddreamer_requests_total{status="error"}[5m]) > 0.1
    for: 2m
    labels:
      severity: warning
    annotations:
      summary: "High error rate detected"

  - alert: BudgetWarning
    expr: luciddreamer_budget_usage_percentage > 80
    for: 1m
    labels:
      severity: warning
    annotations:
      summary: "Budget usage warning"

  - alert: ProviderDown
    expr: luciddreamer_provider_health < 0.5
    for: 1m
    labels:
      severity: critical
    annotations:
      summary: "Provider health degraded"
```

## 🔒 Security Considerations

### API Key Management
- Use environment variables or secret management
- Rotate keys regularly
- Monitor for key abuse
- Use least privilege access

### Network Security
- Use HTTPS in production
- Implement rate limiting
- Add authentication for admin endpoints
- Consider VPN for internal access

### Data Protection
- Don't log sensitive data
- Implement request/response size limits
- Use secure Redis configuration
- Regular security updates

## 📊 Scaling Guidelines

### Horizontal Scaling
- Load balance across multiple instances
- Use Redis for shared state
- Monitor queue lengths
- Implement circuit breakers

### Vertical Scaling
- Monitor resource usage
- Adjust memory/CPU limits
- Profile application performance
- Optimize database queries

### Performance Optimization
- Enable caching
- Use connection pooling
- Implement request deduplication
- Monitor and optimize bottlenecks

## 🔍 Troubleshooting

### Common Issues

1. **High Memory Usage**
   ```bash
   # Check container stats
   docker stats luciddreamer-router

   # Monitor Redis memory
   redis-cli info memory
   ```

2. **Provider Timeouts**
   ```bash
   # Check logs
   docker-compose logs luciddreamer-router

   # Test provider connectivity
   curl -X POST "https://api.openai.com/v1/models" \
     -H "Authorization: Bearer $OPENAI_API_KEY"
   ```

3. **Rate Limiting Issues**
   ```bash
   # Check Redis rate limits
   redis-cli keys "rate_limit:*"

   # Monitor metrics
   curl http://localhost:8000/analytics/metrics
   ```

### Health Checks

```bash
# System health
curl http://localhost:8000/health

# Provider status
curl http://localhost:8000/providers

# Load balancer stats
curl http://localhost:8000/admin/load-balancer/stats
```

## 🚀 Performance Tuning

### Application Optimization
- Use async/await properly
- Implement request timeouts
- Optimize JSON serialization
- Use connection pooling

### Infrastructure Optimization
- Choose appropriate instance sizes
- Use SSD storage
- Optimize network configuration
- Implement CDN for static content

### Database Optimization
- Index frequently queried fields
- Use read replicas
- Implement connection pooling
- Monitor query performance

## 📋 Maintenance

### Regular Tasks
- Update dependencies
- Rotate API keys
- Review and update alerts
- Backup configuration

### Monitoring Checklist
- Check error rates
- Monitor cost trends
- Verify provider health
- Review performance metrics

### Backup Strategy
- Backup configuration files
- Export metrics data
- Document custom configurations
- Test recovery procedures

---

For additional support or questions, refer to the main README or create an issue in the repository.