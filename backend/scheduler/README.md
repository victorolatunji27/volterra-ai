# Scheduler

The in-process APScheduler (started from `main.py`'s lifespan handler) runs
four jobs, all in UTC:

| Time (UTC) | Job | What it does |
|---|---|---|
| 06:30 Mon–Fri | `run_daily_scan` | Fetch flow + price + news, store scans, generate AI summaries |
| 06:45 Mon–Fri | `compose_and_send_digest` | Email the top-5 morning brief via Resend |
| 07:15 Mon–Fri | `match_alerts` | Record an `alert_log` row per user whose strategy tags match today's setups, and email the matched setups to each user (send is best-effort; the row is kept even if email fails) |
| 08:00 Sun | `run_weekly_reviews` | Generate and cache the Claude weekly performance recap for every user with 3+ resolved trades this week (pre-warms `GET /api/analytics/weekly-review`) |

## Changing the schedule

Edit the `CronTrigger(...)` arguments in `initialize_scheduler()` in
`daily_scan.py`. For example, to scan at 7:00 UTC instead:
`CronTrigger(day_of_week="mon-fri", hour=7, minute=0)`.

Set `ENABLE_SCHEDULER=false` in the environment to run the API without any
scheduled jobs (useful for local API work and test runs).

## Manually triggering a scan

From the `backend/` directory with the venv active:

```bash
python scheduler/daily_scan.py
# or:
python -c "import asyncio; from scheduler.daily_scan import run_daily_scan; asyncio.run(run_daily_scan())"
```

To manually send the digest:

```bash
python -c "import asyncio; from scheduler.daily_scan import compose_and_send_digest; asyncio.run(compose_and_send_digest())"
```

## What happens if a job fails

Every ticker in the scan is wrapped in its own try/except, so one bad ticker
never kills the run. If a whole job raises, APScheduler logs the exception
and the next scheduled run still fires; Sentry captures the traceback when
`SENTRY_DSN` is configured.

## Railway deployment note

For Railway, replace APScheduler with Railway Cron Jobs invoking
`python scheduler/daily_scan.py`. Railway Cron Jobs survive redeploys;
an in-process APScheduler loses any job that is mid-flight when the
process restarts, and a redeploy at the scheduled minute skips the run.
