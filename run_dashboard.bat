@echo off
echo ========================================
echo BMTC Real-Time Bus Optimization System
echo ========================================
echo.
echo Starting dashboard on http://localhost:8501
echo Press Ctrl+C to stop
echo.

cd /d "%~dp0"
streamlit run dashboard/app.py

