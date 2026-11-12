# Tennis Valeyre watch

Every morning (06:00–10:00 Paris) a GitHub Actions job reads the public slot table of
tennispadel.paris.fr (the site moved from tennis.paris.fr in Nov 2026) for Tennis Valeyre. It:

- logs when the next day to be released (about 12 days ahead) stops showing "Fermé" (`data/release_times.txt`, `data/release_log.csv`);
- sends a push notification (ntfy) when a Friday 18h–20h or Saturday 12h–20h slot is free on one of the
  days listed in `ONLY_DATES` (`.github/workflows/morning.yml`; first date = priority, others = backups).

Read-only: it never logs in or books.
