@echo off
chcp 65001 >nul
title Logos - HSI/SVS Index Size

cd /d "%~dp0"
cd ..\..

python scripts\KSFS工具\measure_index_size.py

pause