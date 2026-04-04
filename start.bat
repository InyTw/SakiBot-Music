@echo off
title Saki-Music Launcher
chcp 65001 >nul
cls
cls

echo Updating pip...
python -m pip install --upgrade pip -q

echo Installing dependencies...
pip install -r requirements.txt -q

echo.
echo Starting Saki-Music, please wait...
timeout /t 1 >nul
echo 3...
timeout /t 1 >nul
echo 2...
timeout /t 1 >nul
echo 1...

cls

echo.
echo.
echo.
echo.
echo.
echo.
echo.
echo.
echo.
echo.
echo           小祥音樂已啟動！
echo.
echo     Ave Musica…奇跡を日常に(Fortuna)
timeout /t 1 >nul
echo     Ave Musica…慈悲を与えましょう(Lacrima)
timeout /t 1 >nul
echo     この右手あなたが掴むなら(果てなき)
timeout /t 1 >nul
echo     漆黒の(魅惑に)悦楽の(虜に)
timeout /t 1 >nul
echo     O…宿命は産声を上げる
echo.
echo.

python main.py
