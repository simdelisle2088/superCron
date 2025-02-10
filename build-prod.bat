@echo off
REM Build Docker image for production
docker build -t supercron:latest -f docker/production/Dockerfile .
pause