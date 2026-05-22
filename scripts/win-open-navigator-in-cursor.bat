@echo off
REM Copy to Desktop and pin: opens open-navigator in Cursor via WSL.
wsl -d Ubuntu -e bash -lc "cd /home/developer/projects/open-navigator && '/mnt/c/Program Files/cursor/resources/app/bin/cursor' ."
