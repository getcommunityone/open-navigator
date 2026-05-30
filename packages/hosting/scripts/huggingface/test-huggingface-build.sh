#!/bin/bash

# Comprehensive Docker build test for Hugging Face deployment
# This script validates the build before pushing to HF Spaces
#
# Usage:
#   ./test-huggingface-build.sh          # Run test and cleanup
#   ./test-huggingface-build.sh --keep   # Run test and keep container running

set -e

# Parse arguments
KEEP_RUNNING=false
if [[ "$1" == "--keep" ]]; then
    KEEP_RUNNING=true
fi

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

IMAGE_NAME="open-navigator-hf-test"
CONTAINER_NAME="open-navigator-test-container"
TEST_PORT=7860

echo -e "${BLUE}🔨 Testing Hugging Face Docker Build${NC}"
echo "==========================================="
echo ""

# Clean up old test artifacts BEFORE build to prevent disk space issues
echo -e "${BLUE}🧹 Cleaning up old test artifacts...${NC}"
docker stop $CONTAINER_NAME 2>/dev/null || true
docker rm $CONTAINER_NAME 2>/dev/null || true
docker rmi $IMAGE_NAME 2>/dev/null || true
echo -e "${GREEN}✅ Old test artifacts removed${NC}"
echo ""

# Cleanup function
cleanup() {
    if [ "$KEEP_RUNNING" = true ]; then
        echo -e "${GREEN}🎉 Container is still running!${NC}"
        echo ""
        echo "Access the application at:"
        echo "  - Main App:        http://localhost:$TEST_PORT/"
        echo "  - Documentation:   http://localhost:$TEST_PORT/docs"
        echo "  - API Docs:        http://localhost:$TEST_PORT/api/docs"
        echo "  - API Health:      http://localhost:$TEST_PORT/api/health"
        echo ""
        echo "To view logs:"
        echo "  docker logs -f $CONTAINER_NAME"
        echo ""
        echo "To stop and remove:"
        echo "  docker stop $CONTAINER_NAME && docker rm $CONTAINER_NAME && docker rmi $IMAGE_NAME"
    else
        echo -e "${YELLOW}🧹 Cleaning up...${NC}"
        docker stop $CONTAINER_NAME 2>/dev/null || true
        docker rm $CONTAINER_NAME 2>/dev/null || true
        docker rmi $IMAGE_NAME 2>/dev/null || true
        
        # Clean up dangling images and build cache to prevent disk space issues
        echo -e "${BLUE}🧹 Cleaning up Docker build cache...${NC}"
        docker builder prune -f --filter "until=24h" > /dev/null 2>&1 || true
        echo -e "${GREEN}✅ Build cache cleaned${NC}"
    fi
}

# Trap errors and cleanup
trap cleanup EXIT

# Step 1: Build the Docker image
echo -e "${BLUE}📦 Step 1/5: Building Docker image...${NC}"
if docker build -f Dockerfile.huggingface -t $IMAGE_NAME . --progress=plain; then
    echo -e "${GREEN}✅ Docker build successful${NC}"
else
    echo -e "${RED}❌ Docker build failed${NC}"
    exit 1
fi

echo ""

# Step 2: Check image size
echo -e "${BLUE}📏 Step 2/5: Checking image size...${NC}"
IMAGE_SIZE=$(docker images $IMAGE_NAME --format "{{.Size}}")
echo "Image size: $IMAGE_SIZE"
echo -e "${YELLOW}⚠️  Note: HuggingFace has a 50GB limit${NC}"
echo ""

# Step 3: Start the container
echo -e "${BLUE}🚀 Step 3/5: Starting container on port $TEST_PORT...${NC}"
if docker run -d \
    -p $TEST_PORT:7860 \
    --name $CONTAINER_NAME \
    -e HF_SPACES=1 \
    -e LOG_LEVEL=INFO \
    $IMAGE_NAME; then
    echo -e "${GREEN}✅ Container started${NC}"
else
    echo -e "${RED}❌ Failed to start container${NC}"
    docker logs $CONTAINER_NAME
    exit 1
fi

echo ""

# Step 4: Wait for services to be ready
echo -e "${BLUE}⏳ Step 4/5: Waiting for services to start (max 90s)...${NC}"
SECONDS=0
MAX_WAIT=90
READY=false

while [ $SECONDS -lt $MAX_WAIT ]; do
    # Check if main app is responding
    if curl -s -f http://localhost:$TEST_PORT/ > /dev/null 2>&1; then
        # Give API a few more seconds to initialize
        sleep 3
        # Check if API health endpoint is responding
        if curl -s http://localhost:$TEST_PORT/api/health > /dev/null 2>&1; then
            READY=true
            break
        fi
    fi
    echo -n "."
    sleep 2
done

echo ""

if [ "$READY" = false ]; then
    echo -e "${RED}❌ Services did not start within ${MAX_WAIT}s${NC}"
    echo ""
    echo "Container logs:"
    docker logs $CONTAINER_NAME
    exit 1
fi

echo -e "${GREEN}✅ Services ready after ${SECONDS}s${NC}"
echo ""

# Step 5: Test endpoints
echo -e "${BLUE}🧪 Step 5/5: Testing endpoints...${NC}"

test_endpoint() {
    local url=$1
    local name=$2
    
    local status_code=$(curl -s -o /dev/null -w "%{http_code}" "$url")
    
    if echo "$status_code" | grep -q "200\|301\|302"; then
        echo -e "${GREEN}✅ $name${NC} - $url (HTTP $status_code)"
        return 0
    else
        echo -e "${RED}❌ $name${NC} - $url (HTTP $status_code)"
        return 1
    fi
}

FAILURES=0

# Test in order of dependency
test_endpoint "http://localhost:$TEST_PORT/" "Main App" || ((FAILURES++))
test_endpoint "http://localhost:$TEST_PORT/api/health" "API Health" || ((FAILURES++))
test_endpoint "http://localhost:$TEST_PORT/docs" "Documentation" || ((FAILURES++))
test_endpoint "http://localhost:$TEST_PORT/api/docs" "API Docs" || ((FAILURES++))

echo ""

# Show container logs (last 50 lines)
echo -e "${BLUE}📋 Container logs (last 50 lines):${NC}"
docker logs --tail 50 $CONTAINER_NAME
echo ""

# Summary
echo "==========================================="
if [ $FAILURES -eq 0 ]; then
    echo -e "${GREEN}🎉 All tests passed!${NC}"
    echo ""
    if [ "$KEEP_RUNNING" = false ]; then
        echo -e "${GREEN}✅ Docker build is ready for Hugging Face deployment${NC}"
        echo ""
        echo "To deploy to Hugging Face, run:"
        echo "  ./deploy-huggingface.sh"
    fi
    echo ""
    EXIT_CODE=0
else
    echo -e "${RED}❌ $FAILURES test(s) failed${NC}"
    echo ""
    if [ "$KEEP_RUNNING" = false ]; then
        echo "Please fix the issues before deploying to Hugging Face"
    else
        echo "Container is still running for debugging"
    fi
    echo ""
    EXIT_CODE=1
fi
echo "==========================================="

exit $EXIT_CODE

