# Kenyan Poker (Kadi) — backend

FastAPI + WebSocket rules engine and room server. See `../frontend`
for the React client.

## Running it

```bash
pip install -r requirements.txt
python run.py
```

This binds to `0.0.0.0:8000` — reachable from other devices, not just
this machine (see "Playing with others" below). It's equivalent to:

```bash
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

If you only ever want to play solo across two tabs on this one
machine, either command works the same; the `--host 0.0.0.0` part
only matters once someone else needs to reach it.

## Playing with others

The frontend (see `../frontend/README.md`) auto-detects the backend
at whatever host the browser used to load the page, on port 8000. So
once the backend is bound to `0.0.0.0` as above, the same setup works
for all of these — no code or config changes between them:

- **Just you, two browser tabs:** open `http://localhost:5173`.
- **Same WiFi/LAN as a friend:** find this machine's LAN IP
  (`ipconfig` on Windows, look for IPv4 Address) and have them open
  `http://<that-ip>:5173`.
- **Different networks, no port forwarding:** put both machines on a
  virtual LAN with [Hamachi](https://vpn.net/) or
  [Tailscale](https://tailscale.com/) (Tailscale is usually easier to
  set up and free for personal use). Find this machine's virtual IP
  from the Hamachi/Tailscale app, and have your friend open
  `http://<that-virtual-ip>:5173`.

In every case: this machine runs both the backend (`python run.py`)
and the frontend dev server (`npm run dev`, from `../frontend`), and
whoever's joining just needs a browser and the right address.

**Windows Firewall:** the first time you run this with someone
connecting from outside your machine, Windows will likely prompt to
allow Python/Node through the firewall — allow it for the network
you're using (Private for LAN, or whatever profile Hamachi/Tailscale
registers as). If a friend can't connect, this is the first thing to
check.

## Known limitations (see also ../frontend/README.md)

- All game state is in memory — a server restart loses every room.
  Not yet persisted (planned for a future version).
- No authentication — anyone with the room code (and, if playing
  remotely, network access) can join. Fine among people you trust,
  not suitable for a public/untrusted link.
- CORS is wide open (`allow_origins=["*"]`) for local/LAN convenience.
  Tighten this before ever deploying somewhere publicly reachable.
