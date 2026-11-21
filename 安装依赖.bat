@echo off
chcp 65001 >nul
title 验证码助手 - 安装依赖环境

echo ========================================================
echo          验证码助手 - 自动化依赖安装脚本
echo ========================================================
echo.

REM 优先尝试 py -3.14，其次 py，最后 python
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
    echo [错误] 未在系统环境变量中检测到 Python，请先安装 Python 3.14 或配置环境变量！
    pause
    exit /b 1
)

echo 当前使用的 Python 执行命令: %PYTHON_CMD%
%PYTHON_CMD% --version
echo.

echo 正在通过 pip 安装所需依赖库 (requirements.txt)...
echo 依赖列表: pyperclip, keyboard, pywin32, pystray, Pillow, pyinstaller
echo.

%PYTHON_CMD% -m pip install -r requirements.txt
if %errorlevel% neq 0 (
    echo.
    echo [错误] 依赖安装失败，请检查网络连接或 pip 源配置！
    pause
    exit /b 1
)

echo.
echo ========================================================
echo [成功] 所有依赖已成功安装完成！您可以运行 main.py 或执行 打包.bat！
echo ========================================================
echo.
pause
