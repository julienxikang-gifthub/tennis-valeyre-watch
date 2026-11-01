"""Read-only helpers for the public availability search on tennis.paris.fr (no login)."""
import datetime as dt
import html
import http.cookiejar
import re
import urllib.parse
import urllib.request

BASE = "https://tennis.paris.fr/tennis/jsp/site/Portal.jsp"
SEARCH_PAGE = f"{BASE}?page=recherche&view=recherche_creneau"
TENNIS = "Valeyre"
COATINGS = ["96", "2095", "94", "1324", "2016", "92"]
UA = {"User-Agent": "Mozilla/5.0"}

PANEL_RE = re.compile(rf'id="collapse{TENNIS}(\d+)h"')
COURT_RE = re.compile(r'<span class="court">\s*([^<]+?)\s*<', re.I)


def new_opener():
    opener = urllib.request.build_opener(urllib.request.HTTPCookieProcessor(http.cookiejar.CookieJar()))
    opener.open(urllib.request.Request(SEARCH_PAGE, headers=UA), timeout=30).read()
    return opener


def search(opener, day: dt.date) -> str:
    data = [("page", "recherche"), ("action", "rechercher_creneau"), ("hourRange", "8-22"),
            ("when", day.strftime("%d/%m/%Y")), ("selWhereTennisName", TENNIS)]
    data += [("selCoating", c) for c in COATINGS] + [("selInOut", "V"), ("selInOut", "F")]
    req = urllib.request.Request(f"{BASE}?page=recherche&action=rechercher_creneau",
                                 data=urllib.parse.urlencode(data).encode(),
                                 headers={**UA, "Content-Type": "application/x-www-form-urlencoded"})
    with opener.open(req, timeout=30) as r:
        raw = r.read()
    try:
        return raw.decode("utf-8")
    except UnicodeDecodeError:
        return raw.decode("iso-8859-1")


def is_closed(page: str, day: dt.date) -> bool:
    """True while the date strip still shows the day as 'Fermé aux réservations'."""
    m = re.search(rf'dateIso="{day:%d/%m/%Y}".{{0,600}}', page, re.S)
    return bool(m and "Fermé aux r" in m.group(0))


def free_slots(page: str, day: dt.date) -> list[dict]:
    """Every free court-hour at the tennis: each free hour is a panel listing its free courts."""
    slots = []
    panels = list(PANEL_RE.finditer(page))
    for i, m in enumerate(panels):
        body = page[m.end(): panels[i + 1].start() if i + 1 < len(panels) else len(page)]
        body = body.split('<div class="map-background"', 1)[0]
        start = dt.datetime.combine(day, dt.time(int(m.group(1))))
        for court in COURT_RE.findall(body):
            court = " ".join(html.unescape(court).split())
            slots.append({"start": start, "court": court, "key": f"{start:%Y-%m-%d %H}|{court}"})
    return slots
