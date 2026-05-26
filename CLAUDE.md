# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project overview

A Flask web app for a couple (双双 & 塔塔) to track their relationship. Displays days together, birthday countdowns, anniversary countdowns, a shared timeline, photo wall, and message board. Single-file backend with SQLite storage and server-rendered Jinja2 templates. No build step, no frontend framework, no tests.

## Development

```bash
# Install
pip install -r requirements.txt

# Run (creates DB tables on first startup, serves on 0.0.0.0:5000)
python app.py
```

## Architecture

**Backend** — [app.py](app.py) is the entire server. Flask routes are organized in four groups:

- `/`, `/login`, `/logout` — public pages
- `/settings` — user profile edits (nickname, password, avatar upload)
- `/admin`, `/admin/*/add`, `/admin/*/delete/<id>` — CRUD for anniversaries, timeline events, and photo upload/delete
- `/message/send` — post a message to the message board

**Auth** — session-based via `session['user_id']`. The `login_required` decorator gates protected routes. Two seed users are inserted on init: `boy` and `girl` (both password `abc123`). `get_current_user()` fetches the logged-in user row.

**Database** — SQLite via raw `sqlite3` (no ORM). `get_db()` returns a connection with `row_factory = sqlite3.Row`. `init_db()` creates tables and seeds data on every startup (uses `CREATE TABLE IF NOT EXISTS` / `INSERT OR IGNORE` so it's idempotent).

Tables: `users`, `anniversaries`, `timeline`, `photos`, `messages`.

**Hardcoded couple data** — the `COUPLE` dict at the top of `app.py` holds names, birthdays, zodiac signs, and the "together since" date. Birthday countdown and zodiac sign logic reference this.

**Frontend** — Jinja2 templates in [templates/](templates/):
- [index.html](templates/index.html) — main page: hero with day counter, birthday/anniversary countdowns, timeline list, photo postcard grid, message board with inline chat form. Contains a large inline `<script>` block implementing a canvas-based heart particle animation (parametric heart curve, glow/flow/rising particles).
- [admin.html](templates/admin.html) — three-section admin panel: anniversaries, timeline, photos. All CRUD via inline forms.
- [login.html](templates/login.html) — simple login form with error display.
- [settings.html](templates/settings.html) — nickname, password, avatar upload with client-side preview.

**Static files** — [static/css/style.css](static/css/style.css) contains all styling (single large CSS file, ~30KB). [static/js/](static/js/) exists but is empty. [static/uploads/](static/uploads/) holds user-uploaded avatars and photos.
