"""
Convenience entry point: `python run.py` instead of remembering the
full uvicorn command and flags.

Binds to 0.0.0.0 (all network interfaces) rather than uvicorn's
default of 127.0.0.1, so the API is reachable from other devices —
over your LAN, or over a virtual LAN like Hamachi/Tailscale — not
just from this machine. See ../frontend/README.md for how the
frontend finds this automatically.
"""

import uvicorn

if __name__ == "__main__":
    uvicorn.run("app.main:app", host="0.0.0.0", port=8000, reload=True)
