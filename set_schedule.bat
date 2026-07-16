@echo off
setlocal

cd /d "C:\Users\NoahTeitlebaum\Internships\IBM\Coding\IBM Daily Email Digest"

echo [1] Staging the workflow schedule change...
git add -A -- ".github/workflows/daily-digest.yml"
echo.

echo [2] Staged change:
git status --short
echo.

echo [3] Committing...
git -c commit.gpgsign=false -c user.email=noah.teitlebaum@ibm.com -c user.name="Noah Teitlebaum" commit --no-verify -m "Schedule: target 7am ET (0 11 UTC) to offset GitHub cron delay"
echo.

echo [4] Pushing...
git push origin main
echo.

echo [5] Recent commits:
git log --oneline -3
echo.

echo ============================================
echo  DONE. Schedule now targets 7am ET (11:00 UTC).
echo ============================================
pause
del "%~f0"
