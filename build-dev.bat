@echo off
REM Build Docker image for development
docker build -t supercron-dev:latest -f docker/development/Dockerfile .
pause