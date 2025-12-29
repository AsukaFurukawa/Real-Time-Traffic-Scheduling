@echo off
echo ========================================
echo BMTC Transit Control Center
echo Professional Dashboard
echo ========================================
echo.
echo Starting control center on http://localhost:8505
echo Press Ctrl+C to stop
echo.

cd /d "%~dp0"
streamlit run dashboard/control_center.py --server.port 8505

