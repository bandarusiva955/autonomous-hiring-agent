# Deploying to Render (free, about 5 minutes)

The repo includes `render.yaml`, so Render can create the service for you.

## Steps

1. Push this repo to GitHub (it already is: `bandarusiva955/autonomous-hiring-agent`).
2. Go to <https://render.com>, sign up with GitHub, and allow access to the repo.
3. Click **New +** then **Blueprint**, pick the repo, and click **Apply**.
4. Wait for the first build (a few minutes). Your app will be at `https://ai-hiring-agent-xxxx.onrender.com` (Render shows the exact address on the service page).
5. Open `/health`. It should show `{"status": "healthy"}`. Then try `/`, `/bulk` and `/roadmaps`.

Optional: in the Render dashboard open the service, go to **Environment**, and add `ANTHROPIC_API_KEY` to let the chatbot answer open-ended questions with Claude. Without it the chatbot still works with built-in answers.

## What the free plan means

From Render's [free plan docs](https://render.com/docs/free):
- The service **sleeps after 15 minutes without traffic** and takes about a minute to wake up. Open the link yourself before sharing it in an application.
- The **filesystem is ephemeral and persistent disks are not available**, so saved HR batches disappear when the service restarts or sleeps. That is fine for a demo (download the CSV when you need to keep results) but not for real customers.
- 750 free instance hours per month.

## Settings in `render.yaml`

| Variable | Why |
|---|---|
| `FLASK_ENV=production` | debug off, production config |
| `SECRET_KEY` (generated) | signs session cookies; stays the same across restarts |
| `TRUST_PROXY=1` | read the real visitor IP from Render's proxy so rate limits are per visitor, not shared by everyone |
| `COOKIE_SECURE=1` | cookies only over HTTPS |
| `WEB_CONCURRENCY=1` | one worker keeps memory low on the small free instance |
| `BULK_MAX_FILES=100` | smaller batch limit for a public demo |
| `ANTHROPIC_API_KEY` | optional, enables LLM chatbot answers |

Only set `TRUST_PROXY=1` when a trusted proxy is really in front of the app. On other hosts, set the same variables yourself.

## After it is live

- Put the live URL at the top of the README and on your resume next to the GitHub link.
- Chrome extension: open its **Settings**, enter the Render address, and approve the permission prompt.
- Check the chatbot cost if you add an API key: the app limits each visitor to 20 messages a minute, but also set a monthly spend limit in the Anthropic console.

## Before real HR customers use it

The public demo has no accounts: anyone with a batch link (a long random address) can open that batch, and anyone can upload. Before promoting it to recruiters:
1. Add sign-in, so each recruiter sees only their own batches.
2. Move storage to a managed database (Render Postgres) or a paid plan with a persistent disk.
3. Publish a privacy policy that says what is stored (name, email, skills, scores), for how long (30 days), and how to delete it (the Delete batch button).
4. Add plans and payments (for example a free tier of 25 resumes a month and a paid HR plan).

## Run the same container locally

```bash
docker build -t hiring-agent .
docker run -p 8000:8000 -e SECRET_KEY=change-me -v hiring-data:/app/instance hiring-agent
```
