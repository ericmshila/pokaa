# Kenyan Poker (Kadi)

A multiplayer Kadi (Kenyan card game) app — FastAPI/WebSocket backend,
React/TypeScript/Vite frontend. See `backend/README.md` and
`frontend/README.md` for how each half works and the full manual
setup/run instructions (including playing with others over LAN or a
virtual LAN like Hamachi/Tailscale).

## Quick start (Windows)

Once you've done the one-time setup below, day-to-day you just need:

```
dev.bat
```

(double-click it in File Explorer, or run it from any terminal). It
opens the backend and frontend each in their own window — no need to
remember `python run.py` in one terminal and `npm run dev` in another.
Close a window (or Ctrl+C inside it) to stop that server; the two are
independent.

- Backend: http://localhost:8000
- Frontend: http://localhost:5173 (Vite will confirm the exact port in
  its window)

### One-time setup

```
python -m venv .venv
.venv\Scripts\pip install -r backend\requirements.txt

cd frontend
npm install
```

`dev.bat` checks for both and tells you which one's missing if you
skip this.

## Playing with others

- **Same machine, or LAN/Hamachi/Tailscale:** see
  `backend/README.md#playing-with-others` — no setup beyond what's
  above, just a different URL to share.
- **Anywhere on the internet, no VPN:** see `docs/deploy.md` — deploys
  the app for free on Render so you can just send a link.
