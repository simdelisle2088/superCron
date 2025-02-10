@echo off
:: start.bat
setlocal

IF "%1"=="" (
    SET APP_ENV=local
) ELSE (
    SET APP_ENV=%1
)

echo Starting application in %APP_ENV% environment...

:: Validate that the env file exists
IF NOT EXIST ".env.%APP_ENV%" (
    echo Error: Environment file .env.%APP_ENV% not found!
    exit /b 1
)

:: Set PYTHONPATH to match Docker's setup
set PYTHONPATH=%cd%\server

:: Change directory to server folder
cd server

:: Run uvicorn from the server directory
uvicorn main:app --reload

endlocal