"""Cron: the clock starts work with no request. Daily scan + weekly report, in-process via APScheduler."""
import logging

from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.cron import CronTrigger

from . import config, reports, scans

log = logging.getLogger("shelfwatch.cron")


def scheduled_scan() -> None:
    scan_id = scans.create_scan(config.SCAN_PAGES, triggered_by="cron")
    log.info("cron: starting scan %s", scan_id)
    scans.run_scan(scan_id)


def scheduled_report() -> None:
    row, created = reports.generate(triggered_by="cron")
    log.info("cron: weekly report %s (%s)", row["id"], "new" if created else "already existed today")


def start() -> BackgroundScheduler | None:
    if not config.SCHEDULER_ENABLED:
        return None
    sched = BackgroundScheduler(timezone=config.SCHEDULER_TZ)
    # max_instances=1 + coalesce: if the server was asleep and missed several runs, run once, never pile up.
    sched.add_job(scheduled_scan, CronTrigger.from_crontab(config.SCAN_CRON, timezone=config.SCHEDULER_TZ),
                  id="daily-scan", max_instances=1, coalesce=True, misfire_grace_time=3600)
    sched.add_job(scheduled_report, CronTrigger.from_crontab(config.REPORT_CRON, timezone=config.SCHEDULER_TZ),
                  id="weekly-report", max_instances=1, coalesce=True, misfire_grace_time=3600)
    sched.start()
    for job in sched.get_jobs():
        log.info("cron: %s next run at %s", job.id, job.next_run_time)
    return sched
