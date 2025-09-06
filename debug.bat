@echo off
echo ========================================
echo  Sonarr-Seedr Debug Mode
echo ========================================
echo.
echo This will run the application and show any error messages.
echo The window will stay open so you can read the errors.
echo.
echo Starting application...
echo.

SonarrSeedr.exe --no-browser --log-level debug

echo.
echo ========================================
echo Application has stopped.
echo.
echo If you saw errors above, common solutions:
echo 1. Install Visual C++ Redistributable
echo 2. Add folder to antivirus exclusions  
echo 3. Run as Administrator
echo 4. Check if port 8000 is available
echo.
pause
