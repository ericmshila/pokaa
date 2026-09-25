# Deploying Kadi to the public internet

This puts the app on Render's free tier — one link, no VPN, no "find
my LAN IP" — instead of the LAN/Hamachi/Tailscale setup described in
`../backend/README.md`. Two free Render services: a **static site**
for the frontend and a **web service** for the backend, both defined
in `../render.yaml` so Render creates them together from one file.

**Cost:** $0/month. **Trade-off:** the backend spins down after ~15
minutes with no traffic and takes 30-50 seconds to wake back up on the
next connection — fine for casual games with friends, not instant.

**Also worth knowing going in:** Render's free web services don't get
a persistent disk. Every time the backend spins down and back up (or
you push a new deploy), it starts from a clean slate — every room and
the win scoreboard reset, same as a local restart already does today
(see the "Known limitations" section of `../backend/README.md`). This
isn't a new limitation from deploying, just one that now happens more
often, since the free tier spins down on its own after idle time,
where a machine you're running locally only restarts when you tell it
to.

---

## Step 0: Get the code onto GitHub

Render deploys from a connected GitHub (or GitLab/Bitbucket)
repository — there's no drag-and-drop upload for a Blueprint deploy.

1. **Create a GitHub account** if you don't have one: [github.com/signup](https://github.com/signup).
   Free.

2. **Create a new, empty repository** on GitHub (no README, no
   .gitignore, no license — leave all three boxes unchecked; this
   project already has its own):
   [github.com/new](https://github.com/new). Name it whatever you
   like, e.g. `kenyan-poker`.

3. GitHub will show you a remote URL after creating it, something like
   `https://github.com/<your-username>/kenyan-poker.git`. Open a
   terminal **in the project folder** and run:

   ```
   git remote add origin https://github.com/<your-username>/kenyan-poker.git
   git branch -M main
   git push -u origin main
   ```

   (The repo itself — `git init` and the first commit — is already
   done for you; this just points it at GitHub and pushes.) The first
   push will likely open a browser window asking you to sign in to
   GitHub — that's normal.

---

## Step 1: Deploy the Blueprint on Render

1. **Create a Render account**: [render.com](https://render.com) —
   free, easiest via "Sign up with GitHub" since you'll be connecting
   them anyway.

2. From the Render dashboard: **New** → **Blueprint**.

3. Connect your GitHub account if prompted, then select the
   `kenyan-poker` repo you just pushed.

4. Render reads `render.yaml` from the repo root and shows you two
   services it's about to create: `kadi-backend` (a web service) and
   `kadi-frontend` (a static site). Click **Apply** / **Create**.

5. Wait for both to finish their first build (a few minutes — the
   backend installs Python packages, the frontend runs `npm install`
   and `npm run build`). You'll end up with two URLs, something like:

   - Backend: `https://kadi-backend.onrender.com`
   - Frontend: `https://kadi-frontend.onrender.com`

   (If either name was already taken by someone else on Render,
   yours will have a random suffix instead, like
   `kadi-backend-a1b2.onrender.com` — just use whatever URL actually
   shows in your dashboard from here on.)

---

## Step 2: Point the frontend at the real backend URL

`render.yaml` ships with a **placeholder** backend URL
(`https://kadi-backend.onrender.com`) baked in as the frontend's
`VITE_API_BASE_URL`. If your actual backend URL came out different
(see the note above), the frontend is currently pointed at the wrong
place and needs correcting:

1. In the Render dashboard, open the `kadi-frontend` service →
   **Environment**.
2. Set `VITE_API_BASE_URL` to your actual backend URL from Step 1
   (no trailing slash), e.g. `https://kadi-backend.onrender.com`.
3. Save, then trigger **Manual Deploy** → **Deploy latest commit**.
   This step matters: Vite bakes environment variables into the built
   files at *build* time, so just restarting the service without
   rebuilding won't pick up the change.

The WebSocket URL doesn't need its own setting — the frontend derives
it from `VITE_API_BASE_URL` automatically (`https://` → `wss://`).

---

## Step 3 (optional but recommended): Lock the backend's CORS down

Right now the backend accepts requests from any origin
(`ALLOWED_ORIGINS=*`, set in `render.yaml`) — fine to get started, but
worth tightening once you know the frontend's real URL:

1. In the Render dashboard, open the `kadi-backend` service →
   **Environment**.
2. Set `ALLOWED_ORIGINS` to your frontend's exact URL from Step 1,
   e.g. `https://kadi-frontend.onrender.com` (no trailing slash).
3. Save — Render redeploys the backend automatically on an env var
   change (no rebuild-from-source-needed step here, unlike the
   frontend; this is just a runtime setting).

---

## You're done

Send friends the **frontend** URL (`https://kadi-frontend.onrender.com`
or whatever yours is). The first person to connect after 15 minutes of
quiet will see a ~30-50 second delay while the backend wakes up — the
page doesn't currently show a "waking up" message for that, it'll just
look like a slow connection.

## Updating the deployed app later

Once this is set up, shipping a change is just:

```
git add -A
git commit -m "..."
git push
```

Render watches the GitHub repo and redeploys both services
automatically on every push to `main`.
