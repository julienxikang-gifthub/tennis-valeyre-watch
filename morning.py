"""Morning loop (GitHub Actions): log when the next day opens on tennispadel.paris.fr and push an alert
(ntfy) when a wanted Tennis Valeyre slot is free. Alert-only: booking is done by hand.

The site moved in Nov 2026 and now opens about 12 days ahead (it was D+6), so the day to watch
is found at start: the first day ahead that is still all "Ferme".
Polls every 2 min from START until that day opens, every 1 min for 30 min after, then every 5 min until END.
`--test` does a single poll and sends a test notification.
"""
import csv
import datetime as dt
import json
import os
import sys
import time
import urllib.request
from pathlib import Path

import tennis_paris as tp

START, END = dt.time(6, 0), dt.time(10, 0)
HORIZON = 14  # days ahead to look for wanted slots
WANTED = {4: {18, 19}, 5: set(range(12, 20))}  # weekday -> allowed start hours: Fri 18h-20h, Sat 12h-20h
# dd/mm/YYYY days to alert on, in priority order; later ones are flagged as backups. Empty = alert on nothing.
ONLY_DATES = os.environ.get("ONLY_DATES", "").split()
RELEASE_NOTIFY_UNTIL = os.environ.get("RELEASE_NOTIFY_UNTIL", "")  # YYYY-MM-DD
TOPIC = os.environ.get("NTFY_TOPIC", "")

DATA = Path(__file__).parent / "data"
LOG, RELEASES, SEEN = DATA / "release_log.csv", DATA / "release_times.txt", DATA / "seen.json"


def notify(title: str, msg: str, priority: str = "high") -> None:
    print(f"[notify] {title}: {msg}")
    if TOPIC:
        req = urllib.request.Request(f"https://ntfy.sh/{TOPIC}", data=msg.encode(),
                                     headers={"Title": title, "Priority": priority, "Click": tp.SEARCH_PAGE})
        urllib.request.urlopen(req, timeout=20).read()


def log(row: list) -> None:
    new = not LOG.exists()
    with LOG.open("a", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        if new:
            w.writerow(["polled_at", "target_day", "closed", "valeyre_free_count", "valeyre_free_slots"])
        w.writerow(row)


def wanted_slots(opener, now: dt.datetime) -> list[dict]:
    found = []
    for d in (now.date() + dt.timedelta(i) for i in range(HORIZON + 1)):
        if d.weekday() in WANTED and f"{d:%d/%m/%Y}" in ONLY_DATES:
            found += [s for s in tp.free_slots(tp.search(opener, d), d)
                      if s["start"] > now and s["start"].hour in WANTED[d.weekday()]]
    return found


def poll(now: dt.datetime, target: dt.date, seen: set) -> tuple[bool, list, list]:
    opener = tp.new_opener()
    page = tp.search(opener, target)
    closed, free = tp.is_closed(page, target), tp.free_slots(page, target)
    new = [s for s in wanted_slots(opener, now) if s["key"] not in seen]
    return closed, free, new


def short(slots: list[dict]) -> str:
    def label(s):
        backup = ONLY_DATES and f"{s['start']:%d/%m/%Y}" != ONLY_DATES[0]
        return f"{'BACKUP (only if Fri failed) ' if backup else ''}{s['start']:%a %d/%m %Hh} {s['court'].split(' -')[0]}"
    return ", ".join(label(s) for s in sorted(slots, key=lambda s: s["start"]))


def main() -> None:
    DATA.mkdir(exist_ok=True)
    seen = set(json.loads(SEEN.read_text())) if SEEN.exists() else set()
    today = dt.date.today()
    try:
        target = tp.first_closed_day(tp.new_opener(), today) or today + dt.timedelta(12)
    except Exception:
        target = today + dt.timedelta(12)

    if "--test" in sys.argv:
        now = dt.datetime.now()
        closed, free, new = poll(now, target, seen)
        status = "still closed" if closed else f"open, {len(free)} free Valeyre court-hours"
        notify("Tennis watch: test OK",
               f"Test {now:%H:%M}: {target:%a %d/%m} is {status}. Wanted slots now: {short(new) or 'none'}.",
               "default")
        return

    while dt.datetime.now() < dt.datetime.combine(today, START):
        time.sleep(30)

    end = dt.datetime.combine(today, END)
    opened_at, first_poll = None, True
    while dt.datetime.now() < end:
        now = dt.datetime.now()
        try:
            closed, free, new = poll(now, target, seen)
            log([now.isoformat(timespec="seconds"), target.isoformat(), closed, len(free),
                 " ".join(f"{s['start']:%H}h-{s['court'].split(' -')[0]}" for s in free)])
            if not closed and opened_at is None:
                opened_at = now
                note = " (already open at first poll)" if first_poll else ""
                with RELEASES.open("a", encoding="utf-8") as f:
                    f.write(f"{target:%a %d/%m} first seen open at {now:%H:%M:%S} on {today:%a %d/%m}{note}, "
                            f"{len(free)} free Valeyre court-hours\n")
                if today.isoformat() <= RELEASE_NOTIFY_UNTIL:
                    notify("Tennis: new day released",
                           f"{target:%a %d/%m} opened by {now:%H:%M}{note}. {len(free)} free Valeyre court-hours.",
                           "low")
            if new:
                notify("Tennis Valeyre FREE", f"{short(new)}. Book now on tennispadel.paris.fr")
                seen.update(s["key"] for s in new)
                SEEN.write_text(json.dumps(sorted(seen)))
        except Exception as e:
            log([now.isoformat(timespec="seconds"), target.isoformat(), "error", "", str(e)[:200]])
        first_poll = False
        if opened_at is None:
            gap = 120
        elif now - opened_at < dt.timedelta(minutes=30):
            gap = 60
        else:
            gap = 300
        time.sleep(gap)

    if opened_at is None:
        with RELEASES.open("a", encoding="utf-8") as f:
            f.write(f"{target:%a %d/%m}: still closed at {END:%H:%M} on {today:%a %d/%m}\n")


if __name__ == "__main__":
    main()
