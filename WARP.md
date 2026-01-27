# WARP.md

This file provides guidance to WARP (warp.dev) when working with code in this repository.

Project overview
- Minimal Flask app serving a jewellery storefront with a simple cart/checkout flow, in-memory order tracking, and optional email/SMS notifications.
- Frontend is vanilla HTML/CSS/JS (Jinja templates + static assets). Product catalog is a JSON file loaded at startup.

Setup and run
- Create a virtual environment and install deps:
  - PowerShell (Windows):
    ```powershell
    python -m venv .venv
    .\.venv\Scripts\Activate.ps1
    pip install -r requirements.txt
    Copy-Item .env.example .env
    ```
  - Bash (macOS/Linux):
    ```bash
    python3 -m venv .venv
    source .venv/bin/activate
    pip install -r requirements.txt
    cp .env.example .env
    ```
- Start the app (debug server with auto-reload):
  ```bash
  python app.py
  ```
- Smoke test endpoints once running:
  ```bash
  curl http://localhost:5000/api/products
  ```

Build, lint, tests
- Build: none required (pure Flask + static assets).
- Lint: no linter is configured in this repo.
- Tests: no test suite is present in this repo.

Environment and configuration
- Copy `.env.example` to `.env` to set `SECRET_KEY` and optional mail/Twilio vars.
- Email (Flask-Mail) and SMS (Twilio) are best-effort and only used if corresponding environment variables are set; otherwise they are skipped silently.

High-level architecture
- Backend (`app.py`)
  - Initializes Flask app and loads `products.json` at startup into memory.
  - In-memory order store `ORDERS = {}` (demo-only; data resets on process restart).
  - Optional integrations:
    - Email via Flask-Mail when `MAIL_*` env vars are present.
    - SMS via Twilio when `TWILIO_ACCOUNT_SID`, `TWILIO_AUTH_TOKEN`, and `TWILIO_FROM_NUMBER` are present.
  - Routes:
    - GET `/` → render `templates/index.html` with products.
    - GET `/api/products` → JSON product catalog from `products.json`.
    - POST `/api/order` → create order; returns `{ order_id, track_url }`. Tries to send email/SMS notifications if configured.
    - GET `/order/<order_id>` → order confirmation page.
    - GET `/track` → tracking page (accepts `?order_id=` query).
    - GET `/api/order/<order_id>/status` → JSON status for polling.
    - POST `/api/order/<order_id>/mark_delivered` → demo endpoint to mutate status.
    - GET `/try-on` → virtual try-on page.
    - POST `/api/chat` → very simple keyword-based reply bot.
- Data (`products.json`)
  - Flat array of product objects with `audience`, `type`, `metal`, `grams`, and `base_price`. Changes require app restart to take effect.
- Templates (`templates/`)
  - `layout.html`: shared shell (header/footer) and script includes.
  - `index.html`: storefront grid, filters, and cart drawer markup.
  - `order_confirmed.html`, `track.html`, `try_on.html`: respective pages.
- Frontend scripts (`static/js/`)
  - `main.js`: fetches products, renders cards, manages cart in `localStorage`, performs checkout via `/api/order`, and polls tracking APIs. Also wires UI events and a simple toast.
  - `tryon.js`: webcam overlay for “virtual try-on” with draggable/sizable overlay.
  - `chatbot.js`: floating assistant that calls `/api/chat`.
- Styles (`static/css/styles.css`)
  - Modern dark theme with basic layout, grid, cart drawer, and try-on overlay styles.

Operational notes
- Because orders are held in-memory, use is limited to demos. For persistence, replace `ORDERS` with a database and move mail/SMS to background jobs.
- If you modify `products.json`, restart the dev server to reload the catalog.
