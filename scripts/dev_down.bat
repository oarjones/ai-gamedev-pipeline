@echo off
REM AI GameDev Pipeline - Dev Down (Windows)
echo Attempting to close dev windows (Gateway/Webapp)...

REM Close by window titles if they are open
for %%T in ("AGP Gateway","AGP Webapp") do (
  for /f "tokens=2 delims==" %%i in ('tasklist /v /fo list ^| findstr /i %%~T') do (
    set PID=%%i
  )
)

REM Alternatively, kill by common dev ports (optional; commented out)
REM netstat -ano | findstr ":8000" | for /f "tokens=5" %%p in ('more') do taskkill /PID %%p /F
REM netstat -ano | findstr ":5173" | for /f "tokens=5" %%p in ('more') do taskkill /PID %%p /F

echo Done. Manually close any remaining dev shells if needed.
