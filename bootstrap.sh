@title Server Guard
@echo off
cls

:start

pip install -r requirements.txt

python base.py
echo Press Ctrl-C to stop the server.
ping -n 1 localhost

goto start