@echo off
chcp 65001 >nul
title J.A.R.V.I.S.
cd /d "%~dp0"

rem ---- Uygun Python surumunu sec (3.13/3.12/3.11/3.10). Cok yeni surumlerde (3.14+)
rem ---- bazi paketlerin hazir kurulumu henuz yok, bu yuzden once bunlar denenir.
set "PY="
for %%V in (3.13 3.12 3.11 3.10) do (
  if not defined PY (
    py -%%V -c "import sys" >nul 2>nul && set "PY=py -%%V"
  )
)
if not defined PY (
  where py >nul 2>nul
  if not errorlevel 1 (
    echo [*] Uyumlu Python 3.13 kuruluyor ^(bir kez, 1-2 dk^)...
    py install 3.13
    py -3.13 -c "import sys" >nul 2>nul && set "PY=py -3.13"
  )
)
if not defined PY (
  where python >nul 2>nul
  if not errorlevel 1 set "PY=python"
)
if not defined PY (
  echo [!] Python bulunamadi. https://www.python.org/downloads/ adresinden Python kur.
  pause
  exit /b 1
)
echo [*] Kullanilan Python: %PY%

if not exist ".venv\Scripts\python.exe" (
  echo [*] Ilk kurulum yapiliyor, bu bir kez olur...
  %PY% -m venv .venv
  if errorlevel 1 (
    echo [!] Sanal ortam olusturulamadi.
    pause
    exit /b 1
  )
  ".venv\Scripts\python.exe" -m pip install --upgrade pip >nul
)

rem Surum degistiyse paketleri guncelle
if not exist ".venv\kurulum_v4.ok" (
  echo [*] Gerekli paketler kuruluyor...
  ".venv\Scripts\python.exe" -m pip install -r requirements.txt
  if errorlevel 1 (
    echo [!] Gerekli paketler kurulamadi. Internet baglantisini kontrol et ve start.bat'i yeniden calistir.
    pause
    exit /b 1
  )
  echo [*] Ek paketler tek tek kuruluyor ^(biri kurulamazsa digerleri yine kurulur^)...
  for /f "usebackq eol=# tokens=1 delims=; " %%P in ("requirements-extra.txt") do (
    ".venv\Scripts\python.exe" -m pip install "%%P" || echo [i] %%P kurulamadi, o ozellik devre disi kalir.
  )
  echo ok> ".venv\kurulum_v4.ok"
)

if not exist ".env" copy ".env.example" ".env" >nul

where ffmpeg >nul 2>nul
if errorlevel 1 (
  echo [i] ffmpeg yok: video duzenleme/analiz icin bir kez "winget install Gyan.FFmpeg" calistir
  echo     ^(ya da JARVIS'e "ffmpeg kur" de^). Diger her sey ffmpeg olmadan da calisir.
)

".venv\Scripts\python.exe" run.py %*
pause
