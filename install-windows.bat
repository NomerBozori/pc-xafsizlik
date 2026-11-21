@echo off
rem ===========================================================================
rem  PC Xavfsizlik - Windows uchun ornatuvchi
rem  MUHIM: "Run as administrator" bilan ishga tushiring!
rem ===========================================================================
setlocal EnableDelayedExpansion
chcp 65001 >nul

set "INSTALL_DIR=%ProgramData%\PCXavfsizlik"
set "TASK_NAME=PCXavfsizlik"
set "SRC_DIR=%~dp0"

echo.
echo  ==============================================
echo   PC Xavfsizlik - Windows ornatuvchi
echo  ==============================================
echo.

rem ---------------------------------------------------- admin tekshiruvi
net session >nul 2>&1
if errorlevel 1 (
  echo  [X] Administrator huquqi kerak!
  echo      Faylga o'ng tugma - "Run as administrator"
  pause
  exit /b 1
)

rem --------------------------------------------------------------- python
where python >nul 2>&1
if errorlevel 1 (
  echo  [X] Python topilmadi. python.org dan ornating ^(Add to PATH ni belgilang^).
  pause
  exit /b 1
)
for /f "tokens=2" %%v in ('python --version 2^>^&1') do set "PYVER=%%v"
echo  [v] Python !PYVER!

rem ------------------------------------------------------------- fayllar
if not exist "%INSTALL_DIR%" mkdir "%INSTALL_DIR%"
for %%d in (templates static xavfsizlik demo_assets) do (
  if exist "%SRC_DIR%%%d" xcopy /E /I /Y /Q "%SRC_DIR%%%d" "%INSTALL_DIR%\%%d" >nul
)
for %%f in (app.py requirements.txt README.md) do (
  if exist "%SRC_DIR%%%f" copy /Y /Q "%SRC_DIR%%%f" "%INSTALL_DIR%\" >nul
)
echo  [v] Fayllar: %INSTALL_DIR%

rem --------------------------------------------------------------- venv
if not exist "%INSTALL_DIR%\.venv" (
  echo  [.] Virtual muhit yaratilmoqda...
  python -m venv "%INSTALL_DIR%\.venv"
)
call "%INSTALL_DIR%\.venv\Scripts\activate.bat"
python -m pip install --quiet --upgrade pip
python -m pip install --quiet -r "%INSTALL_DIR%\requirements.txt"
echo  [v] Kutubxonalar ornatildi (flask, pillow)

echo  [.] Kamera kutubxonasi ornatilmoqda (opencv-python)...
python -m pip install --quiet opencv-python 2>nul
if errorlevel 1 (
  echo  [!] OpenCV ornatilmadi. Internet aloqasini tekshiring.
) else (
  echo  [v] OpenCV tayyor
)

rem -------------------------------------------------------------- config
if not exist "%INSTALL_DIR%\config.json" (
  python "%INSTALL_DIR%\app.py" --init-config >nul
  echo  [v] config.json yaratildi
)

rem ------------------------------------------------------- boot vazifasi
echo  [.] Avtomatik ishga tushish sozlanmoqda...
schtasks /delete /tn "%TASK_NAME%" /f >nul 2>&1
schtasks /create /tn "%TASK_NAME%" /tr "\"%INSTALL_DIR%\.venv\Scripts\pythonw.exe\" \"%INSTALL_DIR%\app.py\" --arm --host 127.0.0.1" /sc onstart /ru SYSTEM /rl HIGHEST /f >nul 2>&1
if errorlevel 1 (
  echo  [!] Vazifa yaratilmadi - qolda ishga tushiring: run.bat
) else (
  echo  [v] Kompyuter yonganda avtomatik ishga tushadi
  schtasks /run /tn "%TASK_NAME%" >nul 2>&1
)

rem ------------------------------------------------------------------ test
echo.
echo  [.] Diagnostika...
python "%INSTALL_DIR%\app.py" --doctor

echo.
echo  ==============================================
echo   Ornatish tugadi!
echo   Dashboard:  http://127.0.0.1:8000
echo   Rasmlar:    %INSTALL_DIR%\snapshots\
echo   Sozlama:    %INSTALL_DIR%\config.json
echo   Vazifa:     schtasks /query /tn %TASK_NAME%
echo  ==============================================
pause
