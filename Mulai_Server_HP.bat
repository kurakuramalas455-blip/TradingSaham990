@echo off
title IDX Bot Mobile Server
color 0B

echo ===================================================
echo     IDX TRADING BOT - MOBILE SERVER STARTUP
echo ===================================================
echo.

:: Get local IPv4 address dynamically for Windows
for /f "tokens=14" %%a in ('ipconfig ^| findstr IPv4') do set _IP=%%a

echo [OK] Server diatur untuk jaringan lokal.
echo.
echo ===================================================
echo 📱 BUKA ALAMAT INI DI BROWSER HP ANDA:
echo http://%_IP%:8000
echo ===================================================
echo.
echo Catatan: 
echo - Pastikan HP dan komputer terhubung ke WiFi yang sama.
echo - Jangan tutup jendela ini selama ingin mengakses dari HP.
echo.

python api.py
pause
