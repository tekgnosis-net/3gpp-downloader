# 3GPP Downloader

3GPP Downloader automates the discovery and download of official 3GPP specification PDFs with a FastAPI backend and a Chakra UI + React frontend.

## Highlights

- 🚀 High-throughput downloads with aiohttp streaming, resumable selection, and progress telemetry.
- 🕷️ Scrapy pipeline builds JSON manifests (`links.json`, `latest.json`) for both CLI and UI workflows.
- 📑 Filtering keeps the highest version per TS number *per release* so multi-release archives stay accurate.
- 🧭 Server-side pagination via `/api/files` keeps the UI responsive even with large catalogs.
- ✅ Bulk selection helpers and cooperative cancellation (`/api/download/stop`) improve long-running jobs.
- 🪵 Live activity log, download timeline, auto-scroll toggles, and persistent filters for quick context.
- 🧭 Inline help popover keeps onboarding friction low without leaving the dashboard.
- 🐳 Docker image bundles FastAPI, workers, and the production React build.

---

## Architecture

```
frontend/             Chakra UI + Vite SPA
 ├─ src/App.tsx       Dashboard: controls, tables, telemetry
 └─ ...               Hooks, components, theme/infrastructure

src/api/              FastAPI backend
 ├─ server.py         REST API, background jobs, static hosting
 └─ state_manager.py  Thread-safe state + settings persistence

src/tools/            Core engines
 ├─ etsi_spider.py    Scrapy spider producing link manifests
 ├─ json_downloader.py Async downloader with cancellation support
 └─ monitored_pool.py  Connection pool helpers

src/main.py           CLI workflows (scrape/filter/download)
run_web.py            FastAPI + frontend launcher
downloads/, logs/     Data + log volumes (auto-created/mounted)
```

---
## Quick Start

### Docker (recommended)

Prebuilt images are published to GitHub Container Registry; no local build step is required.

```bash
git clone https://github.com/tekgnosis-net/3gpp-downloader.git
cd 3gpp-downloader
docker login ghcr.io -u <github-username>
docker compose pull
docker compose up -d
docker compose logs -f 3gpp-downloader
```

- UI default: `http://<docker-host>:8085` (mapped to container port `32123`).
- API inside the container: `http://localhost:32123`.
- Bind mounts: `./downloads` (PDFs) and `./logs` (runtime logs).
- Update to the newest release with `docker compose pull` followed by `docker compose up -d`.

### Local development

```bash
# Backend
python -m venv .venv
source .venv/bin/activate  # Linux/macOS
.\.venv\Scripts\Activate.ps1  # Windows (PowerShell)
pip install --upgrade pip
pip install -r requirements.txt
uvicorn src.api.server:app --reload --port 32123

# Frontend
cd frontend
npm install
npm run dev -- --host 0.0.0.0 --port 5173
```

- API base URL default: `http://localhost:32123/api` (override via `VITE_API_BASE_URL`).

## Development

- Start work by branching from `main` (or the active integration branch such as `feature/chakra-ui-refactor`) and naming the branch after the change (for example, `feature/ui-progress-bar`).
- Never push directly to `main`; open a pull request from your feature branch instead so reviews and CI can run before merges.
- Keep commits focused and include verification steps (e.g., `python -m pytest`, `npm run build`) in your PR description to document test coverage.

### Versioning & releases

- We use [semantic-release](https://semantic-release.gitbook.io) with the Conventional Commits spec to manage versions, changelog entries, and GitHub releases.
- The first automated release will produce `v1.0.0`; subsequent merges to `main` will bump versions according to commit types (`feat` → minor, `fix` → patch, `BREAKING CHANGE` → major).
- The release workflow (`.github/workflows/release.yml`) also publishes multi-tagged container images to GitHub Container Registry: `${{github.repository}}:<semver>` and `latest`.
- Ensure feature branch commits follow the Conventional Commits format (e.g., `feat(api): add scrape summary endpoint`) so automated version bumps stay accurate.

## Workflows

### Web dashboard

1. **Scrape** – `Start Scraping` triggers `/api/scrape`; Scrapy runs in a background thread and writes `links.json`.
2. **Filter** – Toggle “Latest versions only” to call `/api/filter`; backend keeps the highest version per release in memory.
3. **Explore** – Table uses `/api/files` for search, release/series filters, sorting, and pagination.
  - “Select all X files” targets the entire filtered dataset.
  - Header checkbox toggles the current page selection.
4. **Download** – `Download Selected` posts to `/api/download`; backend writes `selected.json` and streams downloads with progress callbacks.
5. **Stop** – `Stop Download` invokes `/api/download/stop` for cooperative cancellation.
6. **Monitor** – Activity log, download timeline, and progress cards update live; auto-scroll toggles keep long runs readable.

### CLI parity

```bash
python -m src.main scrape            # Scrape ETSI -> downloads/links.json
python -m src.main filter            # Filter -> downloads/latest.json
python -m src.main download          # Download from latest.json / selected.json
python -m src.main scrape download   # One-shot pipeline
```

### REST endpoints (excerpt)

| Method | Path | Purpose |
|--------|------|---------|
| GET    | `/api/state`         | Runtime snapshot (logs, progress, files, settings) |
| POST   | `/api/scrape`        | Start scraping (`force: true` clears cached JSON) |
| POST   | `/api/filter`        | Filter latest versions (`clear: true` reloads all) |
| POST   | `/api/files`         | Server-side pagination, filtering, sorting |
| POST   | `/api/download`      | Begin download batch (`{"urls": [...]}`) |
| POST   | `/api/download/stop` | Request cooperative cancellation |
| POST   | `/api/files/reload`  | Reload manifests from disk |
| POST   | `/api/logs/clear`    | Clear in-memory log buffer |

OpenAPI docs: `http://localhost:32123/docs` (when enabled).

## Configuration

1. Copy `.env.example` ➜ `.env` (root) and adjust credentials/timeouts before launching. The Docker compose file automatically passes through variables declared there.
2. Key environment groups:
  - `MAIN_*`, `JSON_DOWNLOADER_*`, `ETSI_SPIDER_*`, `MONITORED_POOL_*` – logging names, destinations, levels.
  - `SCRAPY_*` – concurrency, delay, user agent for the spider.
  - `HTTP_*`, `DOWNLOAD_*` – aiohttp pooling, timeouts, retry thresholds.
  - `RETRY_*` – exponential backoff defaults.
  - `API_CORS_ORIGINS` – comma-separated list of allowed web origins for the FastAPI CORS middleware.
3. Additional frontend-only overrides (e.g., `VITE_API_BASE_URL`) can live in `frontend/.env` if you are running the SPA separately via `npm run dev`.
4. Frontend preferences persist to `web_settings.json` (thread count, resume mode, organise-by-series, auto-scroll, etc.).
5. Table filters persist in the browser to make reopening the dashboard faster.

## Testing & Tooling

```bash
source .venv/bin/activate
python -m pytest
flake8 src/
mypy src/

cd frontend
npm run lint
npm run build
```

## Troubleshooting

| Symptom | Suggested fix |
|---------|----------------|
| UI unreachable via Docker | Confirm the container pulled successfully (`docker compose pull`) and is healthy (`docker compose ps`). Port `8085` must be free on the host. |
| Cannot pull image (401) | Generate a classic PAT with `read:packages`, log in via `docker login ghcr.io -u <github-username>`, then retry the pull. |
| “Download already in progress” | Wait for completion or click `Stop Download`; button re-enables once the state returns to `idle`. |
| Empty table after filtering | Click “Reload Files” in the UI or call `/api/files/reload`, then re-apply filters. The status banner should mention “Latest versions ready”. |
| Frontend connecting to wrong API host | Set `VITE_API_BASE_URL` before running `npm run dev` or edit `frontend/.env` so the SPA points at the live backend. |
| Python tests missing | Activate the virtualenv and install dev deps: `source .venv/bin/activate && pip install -r requirements.txt`. |

Logs:

```bash
tail -f logs/json_downloader.log
docker compose logs -f 3gpp-downloader
```

## Contributing

1. Create a feature branch from `main` (or from `feature/chakra-ui-refactor` if continuing this refactor) before making changes.
2. Run backend + frontend checks (`python -m pytest`, `npm run lint`).
3. Cover new API/UI behaviour with tests or manual verification steps.
4. Submit a PR summarising changes and test evidence.

## License & Credits

- MIT License (see `LICENSE`).
- Built with FastAPI, Scrapy, aiohttp, Chakra UI, React, and Vite.
