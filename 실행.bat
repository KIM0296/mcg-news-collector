@echo off
chcp 65001 >nul
cd /d "%~dp0"
echo MCG 주간 원자력 기사 수집을 시작합니다...
python collect.py --out "%~dp0결과"
echo.
echo 끝났습니다. "결과" 폴더의 엑셀을 GPT에 첨부하세요.
pause
