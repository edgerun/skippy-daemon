#!/usr/bin/env bash
#!/bin/bash
VERSION=${1:-0.3}
docker run --rm --privileged multiarch/qemu-user-static:register --reset

docker build -t alexrashed/skippy-daemon:${VERSION}-amd64 -f Dockerfile.amd64 .
docker build -t alexrashed/skippy-daemon:${VERSION}-arm64 -f Dockerfile.arm64 .
docker build -t alexrashed/skippy-daemon:${VERSION}-armhf -f Dockerfile.armhf .

docker push alexrashed/skippy-daemon:${VERSION}-amd64
docker push alexrashed/skippy-daemon:${VERSION}-arm64
docker push alexrashed/skippy-daemon:${VERSION}-armhf

docker manifest create --amend alexrashed/skippy-daemon:${VERSION} alexrashed/skippy-daemon:${VERSION}-amd64 alexrashed/skippy-daemon:${VERSION}-arm64 alexrashed/skippy-daemon:${VERSION}-armhf
docker manifest push alexrashed/skippy-daemon:${VERSION}