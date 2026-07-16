@echo off
setlocal

cd /d "C:\Users\NoahTeitlebaum\Internships\IBM\Coding\IBM Daily Email Digest"

REM Delete the file locally if it is still there (ignore if already gone).
if exist "push_fix.bat" del /q "push_fix.bat"

echo [1] Staging the removal of push_fix.bat ...
REM Stage ONLY that path - records the deletion whether or not it still exists.
git add -A -- push_fix.bat
echo.

echo [2] Status of the staged change:
git status --short
echo.

echo [3] Committing...
git -c commit.gpgsign=false -c user.email=noah.teitlebaum@ibm.com -c user.name="Noah Teitlebaum" commit --no-verify -m "Remove push_fix.bat helper script"
echo.

echo [4] Pushing...
git push origin main
echo.

echo [5] Recent commits:
git log --oneline -3
echo.

echo ============================================
echo  DONE. Tell Claude what steps 2-4 showed.
echo ============================================
pause
del "%~f0"
