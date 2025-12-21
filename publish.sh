DATE=$(date +'%Y-%m-%d')
docker buildx build --platform linux/amd64,linux/arm64 -t "davweb/bobcat:${DATE}" -t "davweb/bobcat:latest" --push .