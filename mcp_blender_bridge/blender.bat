@echo off
set "BLENDER=D:\blender\blender.exe"
set "LOGDIR=D:\logs"
set "LOG=%LOGDIR%\blender_debug.txt"
if not exist "%LOGDIR%" mkdir "%LOGDIR%"
"%BLENDER%" --factory-startup --debug --debug-python --debug-wm > "%LOG%" 2>&1
