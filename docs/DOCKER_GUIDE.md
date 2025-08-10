# Docker Deployment Guide for Inbox MCP

This guide explains how to run Inbox MCP using Docker for easy deployment and scaling.

## Table of Contents
- [Prerequisites](#prerequisites)
- [Quick Start](#quick-start)
- [Building the Docker Image](#building-the-docker-image)
- [Running with Docker](#running-with-docker)
- [Using Docker Compose](#using-docker-compose)
- [Configuration](#configuration)
- [Production Deployment](#production-deployment)
- [Troubleshooting](#troubleshooting)

## Prerequisites

- Docker Engine 20.10+ installed
- Docker Compose 2.0+ (optional, for easier management)
- OpenAI API key

## Quick Start

1. Clone the repository:
```bash
git clone https://github.com/yourusername/inbox-mcp.git
cd inbox-mcp
```

2. Create a `.env` file:
```bash
cp .env.example .env
# Edit .env and add your OpenAI API key
```

3. Run with Docker Compose:
```bash
docker-compose up -d
```

The server will be available at `http://localhost:3000`

## Building the Docker Image

### Build locally:
```bash
docker build -t inbox-mcp:latest .
```

### Build with specific version tag:
```bash
docker build -t inbox-mcp:v1.0.0 .
```

### Multi-platform build (for ARM64 and AMD64):
```bash
docker buildx build --platform linux/amd64,linux/arm64 -t inbox-mcp:latest .
```

## Running with Docker

### Basic run:
```bash
docker run -d \
  --name inbox-mcp \
  -p 3000:3000 \
  -e OPENAI_API_KEY="your_openai_key_here" \
  inbox-mcp:latest
```

### Run with environment file:
```bash
docker run -d \
  --name inbox-mcp \
  -p 3000:3000 \
  --env-file .env \
  inbox-mcp:latest
```

### Run with custom port:
```bash
docker run -d \
  --name inbox-mcp \
  -p 8080:3000 \
  -e PORT=3000 \
  -e OPENAI_API_KEY="your_openai_key_here" \
  inbox-mcp:latest
```

### Run with volume for logs (if needed):
```bash
docker run -d \
  --name inbox-mcp \
  -p 3000:3000 \
  -v $(pwd)/logs:/app/logs \
  --env-file .env \
  inbox-mcp:latest
```

## Using Docker Compose

### Start the service:
```bash
docker-compose up -d
```

### View logs:
```bash
docker-compose logs -f
```

### Stop the service:
```bash
docker-compose down
```

### Rebuild and restart:
```bash
docker-compose up -d --build
```

### Scale the service (for load balancing):
```bash
docker-compose up -d --scale inbox-mcp=3
```

## Configuration

### Environment Variables

| Variable | Description | Default |
|----------|-------------|---------|
| `OPENAI_API_KEY` | Your OpenAI API key (required) | - |
| `PORT` | Port the server listens on | 3000 |
| `NODE_ENV` | Environment (development/production) | production |

### Docker Compose Configuration

The `docker-compose.yml` file includes:
- Automatic container restart
- Health checks
- Log rotation
- Resource limits (can be added)

### Adding Resource Limits

Update `docker-compose.yml` to add resource constraints:

```yaml
services:
  inbox-mcp:
    # ... other configuration ...
    deploy:
      resources:
        limits:
          cpus: '1.0'
          memory: 512M
        reservations:
          cpus: '0.5'
          memory: 256M
```

## Production Deployment

### 1. Use a Reverse Proxy

Add Nginx configuration for HTTPS and load balancing:

```nginx
upstream inbox_mcp {
    server inbox-mcp:3000;
}

server {
    listen 80;
    server_name api.yourdomain.com;
    return 301 https://$server_name$request_uri;
}

server {
    listen 443 ssl http2;
    server_name api.yourdomain.com;
    
    ssl_certificate /etc/nginx/certs/cert.pem;
    ssl_certificate_key /etc/nginx/certs/key.pem;
    
    location / {
        proxy_pass http://inbox_mcp;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
    }
}
```

### 2. Use Docker Secrets for API Keys

Instead of environment variables, use Docker secrets:

```bash
# Create secret
echo "your_openai_key" | docker secret create openai_api_key -

# Update docker-compose.yml
services:
  inbox-mcp:
    secrets:
      - openai_api_key
    environment:
      - OPENAI_API_KEY_FILE=/run/secrets/openai_api_key

secrets:
  openai_api_key:
    external: true
```

### 3. Enable Monitoring

Add Prometheus metrics endpoint or use Docker's built-in monitoring:

```bash
docker stats inbox-mcp
```

### 4. Set Up Logging

Configure centralized logging with ELK stack or CloudWatch:

```yaml
services:
  inbox-mcp:
    logging:
      driver: "awslogs"
      options:
        awslogs-group: "inbox-mcp"
        awslogs-region: "us-east-1"
        awslogs-stream-prefix: "server"
```

## Troubleshooting

### Check container status:
```bash
docker ps -a | grep inbox-mcp
```

### View container logs:
```bash
docker logs inbox-mcp
```

### Access container shell:
```bash
docker exec -it inbox-mcp sh
```

### Test health endpoint:
```bash
curl http://localhost:3000/health
```

### Common Issues

1. **Container exits immediately**
   - Check logs: `docker logs inbox-mcp`
   - Verify environment variables are set correctly
   - Ensure OpenAI API key is valid

2. **Cannot connect to server**
   - Verify port mapping: `docker port inbox-mcp`
   - Check firewall rules
   - Ensure container is running: `docker ps`

3. **Permission denied errors**
   - The container runs as non-root user (nodejs)
   - Ensure mounted volumes have correct permissions

4. **High memory usage**
   - Add resource limits in docker-compose.yml
   - Monitor with `docker stats`

### Debugging Build Issues

```bash
# Build with no cache
docker build --no-cache -t inbox-mcp:latest .

# Build with verbose output
docker build --progress=plain -t inbox-mcp:latest .

# Check image layers
docker history inbox-mcp:latest
```

## Security Best Practices

1. **Run as non-root user** (already configured)
2. **Use secrets management** for sensitive data
3. **Enable security scanning**:
   ```bash
   docker scan inbox-mcp:latest
   ```
4. **Keep base images updated**:
   ```bash
   docker pull node:20-alpine
   docker build --pull -t inbox-mcp:latest .
   ```
5. **Use read-only filesystem** where possible:
   ```yaml
   services:
     inbox-mcp:
       read_only: true
       tmpfs:
         - /tmp
   ```

## Backup and Recovery

### Backup configuration:
```bash
# Backup environment configuration
cp .env .env.backup

# Export container configuration
docker inspect inbox-mcp > inbox-mcp-config.json
```

### Restore from backup:
```bash
# Restore environment
cp .env.backup .env

# Recreate container with same configuration
docker-compose up -d
```

## Integration with CI/CD

### GitHub Actions example:
```yaml
name: Build and Push Docker Image

on:
  push:
    branches: [main]

jobs:
  build:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v3
      
      - name: Set up Docker Buildx
        uses: docker/setup-buildx-action@v2
      
      - name: Login to Docker Hub
        uses: docker/login-action@v2
        with:
          username: ${{ secrets.DOCKER_USERNAME }}
          password: ${{ secrets.DOCKER_TOKEN }}
      
      - name: Build and push
        uses: docker/build-push-action@v4
        with:
          push: true
          tags: yourusername/inbox-mcp:latest
          platforms: linux/amd64,linux/arm64
```

## Performance Optimization

1. **Use multi-stage builds** (already implemented)
2. **Enable BuildKit** for faster builds:
   ```bash
   DOCKER_BUILDKIT=1 docker build -t inbox-mcp:latest .
   ```
3. **Cache npm dependencies** (already optimized in Dockerfile)
4. **Use Alpine Linux** for smaller image size (already used)

## Monitoring and Observability

### Add health check endpoint monitoring:
```bash
# Simple monitoring script
while true; do
  if ! curl -f http://localhost:3000/health > /dev/null 2>&1; then
    echo "Health check failed at $(date)"
    # Send alert or restart container
  fi
  sleep 30
done
```

### Container metrics:
```bash
# Real-time stats
docker stats inbox-mcp

# Export metrics to file
docker stats --no-stream --format "table {{.Container}}\t{{.CPUPerc}}\t{{.MemUsage}}" > metrics.txt
```

## Conclusion

Docker provides a consistent and scalable way to deploy Inbox MCP. This guide covers basic usage through production deployment strategies. For additional help, refer to the main README or open an issue on GitHub.