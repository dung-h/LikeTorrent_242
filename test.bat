@echo off
setlocal EnableDelayedExpansion
set BASE_DIR=C:\Users\HAD\OneDrive\Computer\Networking\LikeTorrent
cd %BASE_DIR%
echo Cleaning...
del /Q torrent.db
rd /S /Q test_peers
timeout /t 3 /nobreak
mkdir test_peers\seeder1 test_peers\seeder2 test_peers\seeder3 test_peers\leecher3 test_peers\leecher4
mkdir test_peers\seeder1\downloads test_peers\seeder2\downloads test_peers\seeder3\downloads test_peers\leecher3\downloads test_peers\leecher4\downloads
echo Copying files...
for %%p in (seeder1 seeder2 seeder3 leecher3 leecher4) do (
    copy client.py test_peers\%%p\ >nul
    copy config.py test_peers\%%p\ >nul
    copy peer.py test_peers\%%p\ >nul
    copy piece_manager.py test_peers\%%p\ >nul
    copy metainfo.py test_peers\%%p\ >nul
    copy tracker.py test_peers\%%p\ >nul
    copy testing.torrent test_peers\%%p\ >nul
    timeout /t 1 /nobreak
)
echo Copying testing.mp4...
copy downloads\testing.mp4 test_peers\seeder1\downloads\ >nul
copy downloads\testing.mp4 test_peers\seeder2\downloads\ >nul
copy downloads\testing.mp4 test_peers\seeder3\downloads\ >nul
timeout /t 3 /nobreak
echo Killing old processes...
taskkill /IM python.exe /F >nul 2>&1
timeout /t 3 /nobreak
echo Starting tracker...
start "Tracker" cmd /k "cd %BASE_DIR% && python tracker.py > tracker.log 2>&1 && echo Tracker stopped"
timeout /t 10 /nobreak
echo Starting seeders...
start "Seeder1" cmd /k "cd %BASE_DIR%\test_peers\seeder1 && python client.py testing.torrent --port 6881 > seeder1.log 2>&1"
start "Seeder2" cmd /k "cd %BASE_DIR%\test_peers\seeder2 && python client.py testing.torrent --port 6882 > seeder2.log 2>&1"
timeout /t 5 /nobreak
echo Starting leecher3...
start "Leecher3" cmd /k "cd %BASE_DIR%\test_peers\leecher3 && python client.py testing.torrent --port 6885 --download > leecher3_initial.log 2>&1"
timeout /t 30 /nobreak
echo Starting seeder3...
start "Seeder3" cmd /k "cd %BASE_DIR%\test_peers\seeder3 && python client.py testing.torrent --port 6887 > seeder3.log 2>&1"
echo Starting leecher4...
start "Leecher4" cmd /k "cd %BASE_DIR%\test_peers\leecher4 && python client.py testing.torrent --port 6886 --download > leecher4.log 2>&1"
echo Waiting...
timeout /t 600 /nobreak
echo Checking sizes...
dir %BASE_DIR%\test_peers\leecher3\downloads\testing.mp4
dir %BASE_DIR%\test_peers\leecher4\downloads\testing.mp4
echo Check logs:
echo %BASE_DIR%\tracker.log
echo %BASE_DIR%\test_peers\seeder*\*.log
echo %BASE_DIR%\test_peers\leecher*\*.log
pause