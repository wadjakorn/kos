---
description: Launch the KOS web UI (scripts/serve.py) and open it in the browser
argument-hint: "[port]"
allowed-tools: Bash(python3 scripts/serve.py:*), Bash(lsof:*), Bash(open:*), Bash(curl:*)
---

Launch the KOS web UI.

1. Port: use `$1` if provided, else `8000`. If that port is already in use
   (`lsof -ti tcp:<port>`), pick the next free port and report which one.
2. Start the server in the background: `python3 scripts/serve.py --port <port>`.
   Run it as a background process so this command returns immediately.
3. Wait ~1s, then confirm it is up with `curl -s http://127.0.0.1:<port>/api/stats`.
   If the curl fails, report the server log and stop.
4. Open it in the default browser: `open http://127.0.0.1:<port>/`.
5. Report the URL and remind the user the server keeps running in the background
   until they stop it (Ctrl-C in its process, or kill the background task).

Do not modify any files — this command only starts the server.
