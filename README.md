# Tennis Valeyre watch

Every morning (06:00–10:00 Paris) a GitHub Actions job searches the public availability page of
tennis.paris.fr for Tennis Valeyre. It:

- logs when day D+6 stops showing "Fermé aux réservations" (`data/release_times.txt`, `data/release_log.csv`);
- sends a push notification (ntfy) when a Friday 18h or Saturday 12h–20h slot is free in the next 7 days.

Read-only: it never logs in or books. To skip days, edit `SKIP_DATES` in `.github/workflows/morning.yml`.
