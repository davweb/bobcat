DATE=$(date +'%Y-%m-%d')
IMAGE="ghcr.io/davweb/bobcat"
docker buildx build --platform linux/amd64,linux/arm64 -t "${IMAGE}:${DATE}" -t "${IMAGE}:latest" --push .
