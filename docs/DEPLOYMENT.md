# Putting HealthMate AI online (GitHub, then Render)

The whole app (API and web pages) runs as **one service**, so you only need to host one thing.
The included `Dockerfile` builds the frontend and starts the backend. `render.yaml` tells Render how to run it.

> Never put passwords or API keys in files you upload. Secrets go into the host's "Environment" settings.
> The `.gitignore` already keeps `backend/.env` and the local database out of GitHub.

## Step 1: Put the code on GitHub

Create the repository first: https://github.com/new
Name `healthmate-ai`, choose Public or Private, and **do not** tick "Add a README".

### Option A: No Git needed (website upload)
1. In the project folder, right-click `make-upload-folder.ps1` and choose **Run with PowerShell**
   (or run `powershell -ExecutionPolicy Bypass -File .\make-upload-folder.ps1`).
   This creates a clean folder `HealthMateAI-upload` next to the project (about 76 files, no secrets, no `node_modules`).
2. On your new repository page click **uploading an existing file**.
3. Open `HealthMateAI-upload`, press Ctrl+A, and drag everything into the browser. Wait for it to finish, then click **Commit changes**.
   If GitHub says there are too many files, upload the folders (`backend`, `frontend`, `docs`, `e2e`, `sample_data`) one at a time.

### Option B: With Git (best for later updates)
1. Install Git: `winget install --id Git.Git -e`, then open a new terminal.
2. In the project folder:
```powershell
git init -b main
git add .
git commit -m "HealthMate AI"
git remote add origin https://github.com/<your-username>/healthmate-ai.git
git push -u origin main
```
3. A browser window opens for you to sign in to GitHub. If the terminal asks for a password, use a **Personal Access Token**
   (GitHub > Settings > Developer settings > Personal access tokens), not your account password.

## Step 2: Deploy on Render (free)
1. Go to https://render.com and sign up with **Sign in with GitHub**.
2. **New > Blueprint**, pick the `healthmate-ai` repository, then **Apply**. Render reads `render.yaml`.
3. When asked, you may paste a `GEMINI_API_KEY` (optional; leave blank for demo mode).
4. Wait about 5 to 10 minutes for the first build. Your address will look like `https://healthmate-ai.onrender.com`.
5. Check `https://<your-address>/api/status`. It should show `{"mode":"demo",...}`. Then open the address and log in with the demo account.

Later changes: push to GitHub and Render redeploys automatically.

## Quick alternative: share your laptop for a day (no GitHub)
```powershell
winget install --id Cloudflare.cloudflared -e
cd backend; python -m uvicorn app.main:app --port 8000      # in one terminal
cloudflared tunnel --url http://localhost:8000              # in another: prints a public https link
```
The link works only while your computer and both commands are running.

## Things to know before sharing the link
* **Free hosting sleeps** after idle time (the first visit takes about 30 to 60 seconds) and **data resets** on every restart,
  because the SQLite file lives on temporary storage. That is fine for a demo, and the demo account is re-created each time.
  For permanent data you would add a paid disk or move to PostgreSQL.
* **Do not let people enter real medical data** on this public demo. The demo login is shared, so anyone can see and edit its data.
  Say "synthetic data only" when you share the link. For a real launch set `SEED_DEMO=false`.
* The app sends HTTPS traffic through the host's certificate, but it is a student project and has **not had a security audit**.
* Live AI needs `GEMINI_API_KEY` in Render > Environment. Without it the app clearly runs in demo mode.
* The `Dockerfile` was written but **could not be test-built on this computer** (Docker is not installed here).
  If the first Render build fails, open the build log and send me the error.
