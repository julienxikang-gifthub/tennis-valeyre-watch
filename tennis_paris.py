"""Read-only helpers for the public slot table on tennispadel.paris.fr (no login).

The site moved from tennis.paris.fr in Nov 2026. Each centre's day table comes from
rest/paristennis/creneaux?idEquipement=<id>&date=YYYY-MM-DD as JSON {"date", "html"}.
Cell classes: "available" + "Libre" = free and bookable; "available" + "Ferme" = not open
for booking (a whole day shows this until it is released); "reserved", "asso", "closed" = taken.
"""
import datetime as dt
import html
import http.cookiejar
import json
import re
import urllib.parse
import urllib.request

BASE = "https://tennispadel.paris.fr/tennispadel"
SEARCH_PAGE = f"{BASE}/jsp/site/Portal.jsp?page=paristennis&sport=1"
API = f"{BASE}/rest/paristennis/creneaux"
TENNIS, EQUIPEMENT = "Valeyre", 330
UA = {"User-Agent": "Mozilla/5.0", "X-Requested-With": "XMLHttpRequest", "Accept": "application/json"}

ROW_RE = re.compile(r'row-title">\s*(\d+)h\s*</div>\s*</th>(.*?)</tr>', re.S)
CELL_RE = re.compile(r'class="cell ([^"]+)"[^>]*>([^<]*)<', re.S)
COURT_RE = re.compile(r'column-title">([^<]*)<', re.S)


def new_opener():
    return urllib.request.build_opener(urllib.request.HTTPCookieProcessor(http.cookiejar.CookieJar()))


def search(opener, day: dt.date) -> str:
    """The day's slot table (HTML) for the centre."""
    q = urllib.parse.urlencode({"idEquipement": EQUIPEMENT, "date": day.isoformat()})
    with opener.open(urllib.request.Request(f"{API}?{q}", headers=UA), timeout=30) as r:
        data = json.loads(r.read().decode("utf-8"))
    if data.get("date") != day.isoformat():
        raise ValueError(f"asked for {day}, site returned {data.get('date')}")
    return data["html"]


def _cells(page: str):
    """Yield (hour, column index, class, text) for every cell in the table."""
    for m in ROW_RE.finditer(page):
        for i, c in enumerate(CELL_RE.finditer(m.group(2))):
            yield int(m.group(1)), i, c.group(1).strip(), html.unescape(c.group(2)).strip()


def _court_names(page: str) -> list[str]:
    names = []
    for raw in COURT_RE.findall(page):
        num = re.search(r"(\d+)\s*$", raw.strip())
        names.append(f"Court {int(num.group(1))}" if num else " ".join(html.unescape(raw).split()))
    return names


def is_closed(page: str, day: dt.date) -> bool:
    """True while the day is not released yet: every cell reads 'Ferme', none is booked or free."""
    cells = list(_cells(page))
    return bool(cells) and all(cls == "available" and txt.lower().startswith("ferm") for _, _, cls, txt in cells)


def free_slots(page: str, day: dt.date) -> list[dict]:
    """Every free, bookable court-hour ('Libre')."""
    courts = _court_names(page)
    slots = []
    for hour, i, cls, txt in _cells(page):
        if cls == "available" and txt.lower() == "libre":
            court = courts[i] if i < len(courts) else f"Court {i + 1}"
            start = dt.datetime.combine(day, dt.time(hour))
            slots.append({"start": start, "court": court, "key": f"{start:%Y-%m-%d %H}|{court}"})
    return slots


def first_closed_day(opener, today: dt.date, look_from: int = 5, look_to: int = 16) -> dt.date | None:
    """The next day still to be released (the first day ahead whose table is all 'Ferme')."""
    for i in range(look_from, look_to + 1):
        d = today + dt.timedelta(i)
        if is_closed(search(opener, d), d):
            return d
    return None
