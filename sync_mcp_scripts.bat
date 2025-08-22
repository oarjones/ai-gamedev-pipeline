@echo off
setlocal ENABLEEXTENSIONS

REM === Sync MCP Editor scripts between projects ===
REM Run this file from: D:\ai-gamedev-pipeline

set "SRC=D:\TestUnityMCP\Assets\Editor\MCP"
set "DST=D:\ai-gamedev-pipeline\unity_project\Assets\Editor\MCP"

echo.
echo Source:      "%SRC%"
echo Destination: "%DST%"
echo.

REM Ensure destination exists
if not exist "%DST%" (
  echo Creating destination folder...
  mkdir "%DST%"
)

REM --- Copy everything (recommended: preserves .meta GUIDs in Unity) ---
REM If you really want only C# scripts, replace "*.*" below by "*.cs *.meta *.asmdef *.asmref *.json"
REM Note: copying .meta files keeps GUIDs stable across projects.
robocopy "%SRC%" "%DST%" *.* /E /COPY:DAT /DCOPY:T /R:2 /W:2 /XO /NFL /NDL /NP
set "RC=%ERRORLEVEL%"

echo.
if %RC% LSS 8 (
  echo Copy completed. robocopy exit code: %RC%
  exit /b 0
) else (
  echo ERROR: robocopy failed with exit code %RC%
  exit /b %RC%
)
