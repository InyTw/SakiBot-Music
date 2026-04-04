#!/bin/bash

# 1. 環境準備（靜默升級，不干擾視覺）
pip install --upgrade pip -q && pip install -r requirements.txt -q

# 2. 清理畫面，開始儀式
clear
sleep 0.5

# 產生空行（替代大量的 echo）
printf "\n%.0s" {1..8}

echo "          小祥音樂已啟動！"
echo " "
echo "    Ave Musica…奇跡を日常に(Fortuna)"
sleep 0.4
echo "    Ave Musica…慈悲を与えましょう(Lacrima)"
sleep 0.4
echo "    この右手あなたが掴むなら(果てなき)"
sleep 0.4
echo "    漆黒の(魅惑に)悦楽の(虜に)"
sleep 0.4
echo "    O…宿命は産声を上げる"
sleep 1.2

# 3. 進入核心
python3 main.py