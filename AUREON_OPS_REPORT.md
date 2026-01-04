========================================================
# AUREON SYSTEM DIAGNOSTIC REPORT
Generated: Sat Jan  3 18:49:22 IST 2026
========================================================

## 1️⃣ PROCESS CONTROL
```
$ ps aux | grep uvicorn
pratiktayade     39748   0.0  0.3 435557344  46000 s011  S+    6:48PM   0:01.46 /Library/Frameworks/Python.framework/Versions/3.14/Resources/Python.app/Contents/MacOS/Python /Volumes/work/aureon-deepseek/venv/bin/uvicorn backend.main:app --port 8000

$ lsof -i :8000
COMMAND     PID         USER   FD   TYPE             DEVICE SIZE/OFF NODE NAME
Google    33501 pratiktayade   24u  IPv6 0x369080d49663f6cc      0t0  TCP localhost:55961->localhost:irdmi (ESTABLISHED)
Google    33501 pratiktayade   31u  IPv6 0x48b0b0c458d869fc      0t0  TCP localhost:56104->localhost:irdmi (ESTABLISHED)
Google    33501 pratiktayade   46u  IPv6 0x22ff6f4eab758201      0t0  TCP localhost:56111->localhost:irdmi (ESTABLISHED)
Google    33501 pratiktayade   47u  IPv6 0xf04db28023e1940c      0t0  TCP localhost:56021->localhost:irdmi (ESTABLISHED)
```

## 2️⃣ DATABASE (POSTGRES)
```sql
