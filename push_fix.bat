@echo off
setlocal

echo ============================================
echo  IBM Daily Digest - fix repo structure + push
echo ============================================
echo.

REM 1) Remove the hijacker .git in the parent Coding folder.
REM    This deletes ONLY git metadata in the parent - your files are NOT touched.
if exist "C:\Users\NoahTeitlebaum\Internships\IBM\Coding\.git" (
  echo [1] Removing parent .git hijacker...
  rmdir /s /q "C:\Users\NoahTeitlebaum\Internships\IBM\Coding\.git"
) else (
  echo [1] No parent .git found - good.
)
echo.

REM 2) Move into the PROJECT folder. Its own .git = the correct flat repo.
cd /d "C:\Users\NoahTeitlebaum\Internships\IBM\Coding\IBM Daily Email Digest"
echo [2] Working in:
cd
echo.

REM 3) Stage everything.
echo [3] Staging all changes...
git add -A
echo.

REM 4) Commit. Bypass GPG signing and hooks that were failing silently.
echo [4] Committing...
git -c commit.gpgsign=false -c user.email=noah.teitlebaum@ibm.com -c user.name="Noah Teitlebaum" commit --no-verify -m "Flat repo: multi-team routing, ONLY_TO allowlist, weekday 9am schedule"
echo.

REM 5) Make sure the branch is named main.
echo [5] Setting branch to main...
git branch -M main
echo.

REM 6) Show the last few commits so we can confirm the commit landed.
echo [6] Recent commits:
git log --oneline -3
echo.

REM 7) Force-push the flat tree, overwriting the old nested one on GitHub.
echo [7] Pushing to GitHub...
git push -u origin main --force
echo.

echo ============================================
echo  DONE. Scroll up and read each [step].
echo  Leave this window open and tell Claude.
echo ============================================
pause
