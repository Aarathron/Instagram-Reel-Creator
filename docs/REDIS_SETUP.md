# Redis Setup Guide

Redis is required for the async job queue system. Here are detailed setup instructions for different environments.

## Option 1: Docker Compose (Recommended)

The easiest way is to use the provided `docker-compose.yml` which includes Redis:

```bash
# This automatically starts Redis + API + Worker
docker-compose up --build
```

**What this includes:**
- Redis server on port 6379
- Persistent data storage
- Automatic startup with other services

## Option 2: Local Redis Installation

### Ubuntu/Debian
```bash
# Install Redis
sudo apt update
sudo apt install redis-server

# Start Redis service
sudo systemctl start redis-server
sudo systemctl enable redis-server

# Test Redis is working
redis-cli ping
# Should return: PONG
```

### macOS
```bash
# Install via Homebrew
brew install redis

# Start Redis service
brew services start redis

# Test Redis is working
redis-cli ping
# Should return: PONG
```

### Windows
```bash
# Option 1: Docker Desktop
docker run -d -p 6379:6379 redis:7-alpine

# Option 2: WSL2 with Ubuntu (then follow Ubuntu instructions)
```

## Option 3: Cloud Redis Services

### Redis Cloud (Recommended for Production)
1. Go to [redis.com](https://redis.com)
2. Create free account (30MB free tier)
3. Create new database
4. Get connection string: `redis://username:password@host:port`

```bash
export REDIS_URL="redis://username:password@redis-12345.cloud.redislabs.com:12345"
```

### AWS ElastiCache
```bash
# After creating ElastiCache instance
export REDIS_URL="redis://your-cluster.cache.amazonaws.com:6379"
```

### Google Cloud Memorystore
```bash
# After creating Memorystore instance
export REDIS_URL="redis://10.x.x.x:6379"
```

## Redis Configuration

### Basic Configuration
The default Redis configuration works well for development. For production, consider these settings:

**redis.conf optimizations:**
```bash
# Memory optimization
maxmemory 256mb
maxmemory-policy allkeys-lru

# Persistence (for job queue reliability)
save 900 1
save 300 10
save 60 10000

# Networking
bind 127.0.0.1
port 6379
timeout 300

# Security (if exposed)
requirepass your_strong_password
```

### Docker Redis with Custom Config
```yaml
# Add to docker-compose.yml
redis:
  image: redis:7-alpine
  ports:
    - "6379:6379"
  command: redis-server --appendonly yes --requirepass yourpassword
  volumes:
    - redis_data:/data
    - ./redis.conf:/etc/redis/redis.conf
```

## Environment Variables

### Local Development
```bash
# Default (Redis on localhost)
export REDIS_URL="redis://localhost:6379"

# With password
export REDIS_URL="redis://:yourpassword@localhost:6379"

# Custom host/port
export REDIS_URL="redis://192.168.1.100:6380"
```

### Production
```bash
# Cloud Redis with authentication
export REDIS_URL="redis://username:password@host:port/database"

# With SSL (some cloud providers)
export REDIS_URL="rediss://username:password@host:port/database"
```

## Testing Redis Connection

### Manual Test
```bash
# Test basic connectivity
redis-cli ping

# Test with custom host/port
redis-cli -h your-redis-host -p 6379 ping

# Test with password
redis-cli -h localhost -p 6379 -a yourpassword ping
```

### Python Test Script
```python
# test_redis.py
import redis
import os

def test_redis_connection():
    redis_url = os.environ.get("REDIS_URL", "redis://localhost:6379")
    
    try:
        client = redis.from_url(redis_url, decode_responses=True)
        
        # Test basic operations
        client.ping()
        print("✅ Redis connection successful")
        
        # Test job queue operations
        client.lpush("test_queue", "test_job")
        job = client.brpop("test_queue", timeout=1)
        
        if job and job[1] == "test_job":
            print("✅ Redis queue operations working")
        else:
            print("❌ Redis queue operations failed")
            
        return True
        
    except Exception as e:
        print(f"❌ Redis connection failed: {e}")
        return False

if __name__ == "__main__":
    test_redis_connection()
```

```bash
python test_redis.py
```

## Monitoring Redis

### Command Line Monitoring
```bash
# Monitor all Redis commands in real-time
redis-cli monitor

# Check memory usage
redis-cli info memory

# Check connected clients
redis-cli info clients

# List all keys (development only)
redis-cli keys "*"

# Check queue length
redis-cli llen video_jobs
```

### Web Interface (Optional)
```bash
# Install Redis Commander
npm install -g redis-commander

# Start web interface
redis-commander --redis-host localhost --redis-port 6379

# Access at http://localhost:8081
```

## Job Queue Management

### Manual Queue Operations
```bash
# Check queue length
redis-cli llen video_jobs

# Peek at next job (without removing)
redis-cli lindex video_jobs -1

# Clear all jobs (emergency)
redis-cli del video_jobs

# List all job-related keys
redis-cli keys "*job*"
```

### Backup Job Queue
```bash
# Backup queue to file
redis-cli lrange video_jobs 0 -1 > jobs_backup.txt

# Restore queue from backup
while read job; do redis-cli lpush video_jobs "$job"; done < jobs_backup.txt
```

## Troubleshooting

### Common Issues

**1. Connection Refused**
```bash
# Check if Redis is running
sudo systemctl status redis-server

# Check if port is open
netstat -tulpn | grep 6379

# Check firewall
sudo ufw status
```

**2. Memory Issues**
```bash
# Check Redis memory usage
redis-cli info memory

# Clear all data (if safe)
redis-cli flushall

# Set memory limit
redis-cli config set maxmemory 256mb
```

**3. Permission Denied**
```bash
# Check Redis logs
sudo tail -f /var/log/redis/redis-server.log

# Fix ownership (Ubuntu)
sudo chown redis:redis /var/lib/redis
```

**4. Jobs Not Processing**
```bash
# Check if worker is running
docker-compose logs worker

# Check queue length
redis-cli llen video_jobs

# Manually add test job
redis-cli lpush video_jobs '{"job_id":"test","test":true}'
```

### Performance Tuning

**For High Job Volume:**
```bash
# Increase worker connections
redis-cli config set maxclients 1000

# Optimize persistence
redis-cli config set save "900 1 300 10 60 10000"

# Disable slow operations in production
redis-cli config set slowlog-log-slower-than 10000
```

## Security Best Practices

### Authentication
```bash
# Set password
redis-cli config set requirepass your_strong_password

# Test authentication
redis-cli -a your_strong_password ping
```

### Network Security
```bash
# Bind to specific interface only
redis-cli config set bind "127.0.0.1"

# Disable dangerous commands
redis-cli config set rename-command "FLUSHDB" "SECRET_FLUSHDB"
redis-cli config set rename-command "FLUSHALL" ""
```

### Firewall Rules
```bash
# Allow only specific IPs (Ubuntu)
sudo ufw allow from 192.168.1.0/24 to any port 6379
sudo ufw deny 6379
```

## Docker Compose Integration

Your current `docker-compose.yml` includes this Redis configuration:

```yaml
redis:
  image: redis:7-alpine
  ports:
    - "6379:6379"
  command: redis-server --appendonly yes
  volumes:
    - redis_data:/data
```

**Key Points:**
- **Port 6379**: Standard Redis port, exposed to host
- **Persistence**: `--appendonly yes` ensures jobs survive restarts
- **Volume**: `redis_data` persists data between container restarts
- **Alpine**: Lightweight Redis image

## Environment-Specific Settings

### Development
```bash
# Simple local setup
export REDIS_URL="redis://localhost:6379"
```

### Staging
```bash
# Cloud Redis with basic auth
export REDIS_URL="redis://:password@staging-redis:6379"
```

### Production
```bash
# Secure cloud Redis with SSL
export REDIS_URL="rediss://user:pass@prod-redis:6380/0"
```

The async job system will automatically use these Redis settings for job queuing and status tracking.