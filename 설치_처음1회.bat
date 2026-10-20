@echo off
chcp 65001 >nul
cd /d "%~dp0"
echo [처음 1회만] 필요한 프로그램을 설치합니다...
python -m pip install -r requirements.txt
python -m playwright install chromium
echo 설치 완료. 이제 실행.bat 을 더블클릭하세요.
pause
