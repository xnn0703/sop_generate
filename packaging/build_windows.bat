@echo off
REM ============================================================
REM  sop_generate · Windows 一键打包脚本
REM  产出：dist\sop_generate-win\  (整个目录拷给客户即可)
REM
REM  环境要求：
REM    - Windows 10 / 11
REM    - Python 3.9+（从 python.org 安装，勾选 "Add to PATH"）
REM    - 客户机器需装 Microsoft Edge 或 Google Chrome（PDF 导出用）
REM
REM  使用方法：
REM    1) 把整个项目目录拷到 Windows 机器
REM    2) 双击本文件，或在项目根 cmd 里运行 packaging\build_windows.bat
REM ============================================================

setlocal enabledelayedexpansion
cd /d %~dp0..

echo.
echo === [1/5] 检测 Python ===
where python >nul 2>nul
if errorlevel 1 (
    echo [ERROR] 未找到 python，请先从 https://www.python.org/downloads/ 安装 Python 3.9+
    pause
    exit /b 1
)
python --version

echo.
echo === [2/5] 创建/激活 venv ===
if not exist .venv (
    python -m venv .venv
)
call .venv\Scripts\activate.bat

echo.
echo === [3/5] 安装依赖 ===
python -m pip install --upgrade pip
pip install -r requirements.txt
pip install -r packaging\requirements-build.txt

echo.
echo === [4/5] 调 PyInstaller ===
if exist build rmdir /s /q build
if exist dist rmdir /s /q dist
pyinstaller packaging\build.spec --clean --noconfirm
if errorlevel 1 (
    echo [ERROR] 打包失败
    pause
    exit /b 1
)

echo.
echo === [5/5] 整理发布目录 ===
set RELEASE=dist\sop_generate-win
if exist %RELEASE% rmdir /s /q %RELEASE%

REM PyInstaller onedir 产物在 dist\sop_generate\，整体改名为 sop_generate-win
move dist\sop_generate %RELEASE% >nul

REM 数据目录
mkdir %RELEASE%\products
mkdir %RELEASE%\assets\images
mkdir %RELEASE%\output
xcopy /e /i /y products %RELEASE%\products >nul
xcopy /e /i /y assets\images %RELEASE%\assets\images >nul

REM 使用说明
(
echo sop_generate · 作业指导书生成器
echo ================================
echo.
echo 【启动】
echo     双击 sop_generate.exe
echo.
echo 【首次运行】
echo     Windows Defender 可能提示"未识别的应用"，点"更多信息" → "仍要运行"
echo.
echo 【数据目录说明】
echo     products\        各产品的 YAML（可在 GUI 里新建/编辑）
echo     assets\images\   产品图片（每个产品一个子目录）
echo     output\          生成的 HTML / PDF
echo.
echo 【导出 PDF 的前置条件】
echo     本机需装 Microsoft Edge 或 Google Chrome（任一即可）。
echo     若未装，仅 HTML 仍可正常生成，再用浏览器手动 Ctrl+P。
echo.
echo 【注意】
echo     _internal\ 文件夹是运行时库，不可删除。
) > %RELEASE%\使用说明.txt

echo.
echo ============================================================
echo  [OK] 打包完成
echo  发布目录：%CD%\%RELEASE%\
echo    sop_generate.exe
echo    _internal\
echo    products\
echo    assets\images\
echo    output\
echo    使用说明.txt
echo.
echo  分发：把整个 %RELEASE% 文件夹打 zip 发给客户即可
echo ============================================================
pause
