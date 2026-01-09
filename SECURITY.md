# Security Policy

## Supported Versions

| Version | Supported          |
| ------- | ------------------ |
| 1.0.x   | :white_check_mark: Yes |

## Reporting a Vulnerability

If you discover a security vulnerability, please report it responsibly.

### How to Report

**Do NOT** open a public issue.

Instead, send an email to: **security@multi-provider-router.dev**

Please include:
- Description of the vulnerability
- Steps to reproduce
- Potential impact
- Suggested fix (if known)

### What Happens Next

1. **Confirmation**: We'll acknowledge receipt within 48 hours
2. **Investigation**: We'll investigate and assess the severity
3. **Resolution**: We'll develop a fix
4. **Disclosure**: We'll coordinate disclosure with you

### Response Time

- **Critical**: Fix within 48 hours
- **High**: Fix within 1 week
- **Medium**: Fix within 2 weeks
- **Low**: Fix in next release

## Security Best Practices

### API Keys

- **Never commit API keys** to version control
- Use environment variables for sensitive data
- Rotate API keys regularly
- Use `.env.example` as a template (don't include real keys)

### Dependencies

```bash
# Check for vulnerabilities
pip install safety
safety check

# Update dependencies regularly
pip install --upgrade multi-provider-router
```

### Deployment

- Use HTTPS in production
- Enable authentication
- Set up firewalls
- Regular security audits
- Monitor access logs

### Rate Limiting

Configure rate limits to prevent abuse:

```python
# In .env
ROUTING__RATE_LIMIT_PER_MINUTE=60
ROUTING__RATE_LIMIT_PER_HOUR=1000
```

### Budget Management

Set budget limits to prevent cost overruns:

```python
# In .env
BUDGET__DAILY_BUDGET_USD=100.0
BUDGET__HARD_LIMIT_PERCENTAGE=95.0
```

## Security Features

### Built-in Protections

1. **Rate Limiting**: Token bucket algorithm prevents abuse
2. **Input Validation**: Pydantic models validate all inputs
3. **Secure Defaults**: Conservative default settings
4. **Circuit Breakers**: Prevent cascade failures
5. **Health Monitoring**: Detect and respond to anomalies

### Recommendations

1. **Environment Variables**: Store sensitive data in `.env`
2. **Reverse Proxy**: Use nginx/caddy for additional security
3. **Monitoring**: Set up alerts for unusual activity
4. **Backups**: Regular database and config backups
5. **Updates**: Keep dependencies updated

## Common Vulnerabilities

### 1. Exposed API Keys

**Problem**: API keys in code or public repos

**Solution**:
```bash
# Use environment variables
export GLM__API_KEY="your-key-here"

# Or .env file (add to .gitignore)
GLM__API_KEY=your-key-here
```

### 2. Unlimited Rate Limits

**Problem**: No rate limiting allows abuse

**Solution**:
```python
# Configure rate limits
rate_limiter.set_user_rate_limit("user123", RateLimitRule(
    requests_per_minute=100,
    requests_per_hour=5000
))
```

### 3. Cost Overruns

**Problem**: Unbounded API usage

**Solution**:
```python
# Set budget limits
BUDGET__DAILY_BUDGET_USD=100.0
BUDGET__HARD_LIMIT_PERCENTAGE=95.0
```

### 4. Outdated Dependencies

**Problem**: Vulnerable dependencies

**Solution**:
```bash
# Regular updates
pip install --upgrade -r requirements.txt

# Check for vulnerabilities
safety check
```

## Security Audits

We conduct regular security audits:
- Code reviews for all changes
- Dependency scanning
- Penetration testing
- Performance monitoring

## Additional Resources

- [OWASP Python Security](https://cheatsheetseries.owasp.org/cheatsheets/Python_Security_Cheat_Sheet.html)
- [FastAPI Security](https://fastapi.tiangolo.com/tutorial/security/)
- [Python Security Best Practices](https://python.readthedocs.io/en/stable/library/security_warnings.html)

## Contact

For security-related questions:
- **Security Email**: security@multi-provider-router.dev
- **Security Issues**: Use email (do NOT use GitHub issues)

---

Thank you for helping keep Multi-Provider Router secure! 🔒
