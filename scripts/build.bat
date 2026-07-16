@echo off
chcp 65001 >nul 2>&1
REM ==========================================
REM  DingTalkMentions — 构建可分发 .exe
REM  在项目根目录运行: scripts\build.bat
REM ==========================================

echo [1/3] 检查 pyinstaller ...
where pyinstaller >nul 2>&1
if %errorlevel% neq 0 (
    echo 未检测到 pyinstaller，正在安装 ...
    pip install pyinstaller -q
    if %errorlevel% neq 0 (
        echo 安装 pyinstaller 失败！请手动运行: pip install pyinstaller
        pause
        exit /b 1
    )
)

echo [2/3] 清理旧产物 ...
if exist dist\DingTalkMentions.exe del /q dist\DingTalkMentions.exe
if exist build\DingTalkMentions rmdir /s /q build\DingTalkMentions

echo [3/3] 打包 ...
pyinstaller --noconfirm DingTalkMentions.spec
if %errorlevel% neq 0 (
    echo.
    echo !! 打包失败，请检查上方错误信息。
    pause
    exit /b 1
)

echo.
echo ===================================
echo  构建成功!
echo  输出: dist\DingTalkMentions.exe
echo ===================================
pause
