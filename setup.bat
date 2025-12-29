@echo off
echo ========================================
echo BMTC Project Setup
echo ========================================
echo.
echo Installing Python dependencies...
echo.

pip install --upgrade pip
pip install -r requirements.txt

echo.
echo ========================================
echo Setup complete!
echo ========================================
echo.
echo To run the dashboard:
echo   run_dashboard.bat
echo.
pause

