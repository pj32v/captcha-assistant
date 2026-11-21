@echo off
chcp 65001 >nul
title 验证码助手 - PyInstaller 单文件打包

echo ========================================================
echo          验证码助手 - 自动化编译与打包工具
echo ========================================================
echo.

set PYTHON_CMD=
where py >nul 2>nul
if %errorlevel% equ 0 (
    py -3.14 -V >nul 2>nul
    if %errorlevel% equ 0 (
        set PYTHON_CMD=py -3.14
    ) else (
        set PYTHON_CMD=py
    )
) else (
    where python >nul 2>nul
    if %errorlevel% equ 0 (
        set PYTHON_CMD=python
    )
)

if "%PYTHON_CMD%"=="" (
    echo [错误] 未在系统环境变量中检测到 Python，请先安装 Python 3.14！
    pause
    exit /b 1
)

echo 使用 Python 环境: %PYTHON_CMD%
%PYTHON_CMD% --version
echo.

if not exist "captcha.ico" (
    echo 未发现 captcha.ico，正在自动生成图标...
    %PYTHON_CMD% generate_icon.py
    if %errorlevel% neq 0 (
        echo [错误] 图标生成失败！
        pause
        exit /b 1
    )
)

echo 正在清理旧的构建产物 (build, dist, *.spec)...
if exist "build" rd /s /q "build"
if exist "dist" rd /s /q "dist"
if exist "*.spec" del /q "*.spec"
echo 清理完成。
echo.

echo 正在执行 PyInstaller 单文件打包，请稍候...
%PYTHON_CMD% -m PyInstaller --clean --onefile --noconsole --icon=captcha.ico --add-data "captcha.ico;." --name="验证码助手" main.py

if %errorlevel% neq 0 (
    echo.
    echo ========================================================
    echo [错误] 打包失败！请检查 PyInstaller 输出日志。
    echo ========================================================
    pause
    exit /b 1
)

echo.
echo ========================================================
echo [成功] 打包完成！
echo 独立 EXE 文件已生成于 dist 目录:
echo   dist\验证码助手.exe
echo ========================================================
echo.

if exist "dist\验证码助手.exe" (
    copy /y captcha.ico dist\ >nul 2>nul
    echo 可直接双击运行 dist\验证码助手.exe 开始体验！
)

echo.
pause
