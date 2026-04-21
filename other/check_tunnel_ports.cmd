@echo off
echo.
echo ===== Checking local forwarded ports =====
echo.
netstat -ano | findstr :15432
echo.
netstat -ano | findstr :16379
echo.
pause
