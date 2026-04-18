OSI STRESS ASSESSMENT — PostgreSQL + Render/Supabase Deployment Guide
======================================================================

WHAT CHANGED (CSV → PostgreSQL)
  - app.py now uses psycopg2 instead of CSV files
  - All data is stored in a PostgreSQL database (persistent across deploys)
  - 3 tables: users, demographics, stress_results
  - Tables are auto-created on first startup via init_db()

LOCAL DEVELOPMENT
─────────────────
1. Install dependencies:
     pip install -r requirements.txt

2. Set environment variables (or create a .env file):
     export DATABASE_URL="postgresql://postgres:yourpassword@localhost:5432/osi"
     export GEMINI_API_KEY="your_gemini_key_here"
     export SECRET_KEY="any_random_string"

3. Create local DB:
     psql -U postgres -c "CREATE DATABASE osi;"

4. Run the app:
     python app.py
     → Open http://localhost:5050


OPTION A — DEPLOY ON RENDER (recommended, easiest)
────────────────────────────────────────────────────
1. Push your project to a GitHub repo. Required files:
     app.py
     requirements.txt
     render.yaml
     model_top3_subscales.pkl
     templates/  (all .html files)

2. Go to https://render.com → New → Web Service → Connect your GitHub repo

3. Render will auto-detect render.yaml and:
   - Create a free PostgreSQL database called "osi-db"
   - Set DATABASE_URL automatically
   - Deploy the Flask app

4. Add your Gemini API key manually:
   - Render Dashboard → Your Service → Environment → Add Variable
   - Key: GEMINI_API_KEY
   - Value: your key from aistudio.google.com

5. Your app will be live at: https://osi-stress-app.onrender.com
   (free tier spins down after 15 min inactivity — first load may be slow)

NOTE: Render free PostgreSQL databases expire after 90 days.
      Upgrade to paid ($7/mo) or use Supabase (free forever) — see Option B.


OPTION B — DEPLOY ON RENDER + SUPABASE (free forever DB)
──────────────────────────────────────────────────────────
1. Create a free Supabase project at https://supabase.com
   - New Project → choose a region → set a DB password

2. Get your connection string:
   - Supabase Dashboard → Settings → Database → Connection string → URI
   - Looks like: postgresql://postgres:[password]@db.[ref].supabase.co:5432/postgres

3. Deploy to Render (same as Option A, steps 1-2)
   - Do NOT use render.yaml databases section
   - Instead, manually add environment variable in Render:
     DATABASE_URL = (your Supabase URI from step 2)

4. Add GEMINI_API_KEY as well (same as Option A step 4)

5. Done — Supabase stores data permanently, Render runs your Flask app.


GITHUB REPO STRUCTURE
──────────────────────
  osi-stress-app/
  ├── app.py
  ├── requirements.txt
  ├── render.yaml
  ├── model_top3_subscales.pkl
  └── templates/
        ├── login.html
        ├── register.html
        ├── home.html
        ├── basic.html
        ├── advanced.html
        └── result.html

  ⚠ Do NOT commit .env files or any file containing passwords/API keys.
    Add to .gitignore:
      .env
      __pycache__/
      *.pyc


ENVIRONMENT VARIABLES SUMMARY
───────────────────────────────
  DATABASE_URL   → PostgreSQL connection string (required)
  SECRET_KEY     → Flask session secret (auto-generated on Render)
  GEMINI_API_KEY → Your Gemini API key (optional, falls back to keyword bot)


TROUBLESHOOTING
───────────────
  "DATABASE_URL not set" error
    → Make sure the env variable is set before running. Check Render dashboard.

  Tables not created
    → init_db() runs at startup. Check Render logs for "[OSI] Database tables ensured."

  "SSL connection required" error on Supabase
    → Add ?sslmode=require to your DATABASE_URL:
      postgresql://...@db.xxx.supabase.co:5432/postgres?sslmode=require

  psycopg2 install fails locally on Mac/Linux
    → Use: pip install psycopg2-binary
