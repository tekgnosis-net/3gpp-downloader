# Copilot Guide – 3GPP Downloader

## General guidelines (copy-friendly)

- **Response style**: End every reply with a concise summary covering completed work and next steps or current status.
- **Editing**: Keep indentation, formatting, and ASCII-only text unless non-ASCII already exists and is justified.
- **Change tracking**: Document structural, dependency, and workflow updates here; perform work on feature branches rather than directly on `main`.
- **Workflow vigilance**: If CI/CD or automation files change, monitor subsequent runs and surface failures quickly.
- **Branch etiquette**: Maintain feature branches per change; never revert user edits unless explicitly requested.
- **UI baseline**: Display the running build/version near the primary title (pulling from an env-driven constant such as `VITE_APP_VERSION`) and include a footer with `© {currentYear} Tekgnosis Pty Ltd`, computing the year at runtime so it stays current.
- **Docker build args**: Plumb an `APP_VERSION` build arg/ENV through container builds so the frontend/banner and metadata stay synchronized with release tags.

## Release & versioning

- **Semantic-release**: Automated releases run from `.github/workflows/release.yml`, using Conventional Commits to calculate the next SemVer version (starting at `v1.0.0`).
- **Version sync**: `scripts/update_version.py` keeps `pyproject.toml` and `frontend/package.json` aligned with the released version during the `prepare` phase.
- **Artifacts**: Successful releases push tags, changelog entries, GitHub releases, and GHCR images tagged with both the computed SemVer and `latest`.
- **Commit hygiene**: Format commit messages as Conventional Commits (`feat`, `fix`, `chore`, etc.) to ensure correct version bumps.

## Project overview

- **Purpose**: Scrape ETSI/3GPP metadata, curate spec lists, and download PDFs via a FastAPI backend (`src/api/server.py`) and Chakra UI frontend (`frontend/`).
- **Repo map**: CLI orchestration lives in `src/main.py`; backend endpoints and state are in `src/api/`; async downloads in `src/tools/json_downloader.py`; Scrapy spider in `src/tools/etsi_spider.py`; logging helpers under `src/utils/logging_config.py`.
- **Root path**: Project root is `/home/kumar/develop/3gpp-downloader/`; verify with `git rev-parse --show-toplevel` when in doubt.

## Data & backend pipeline

- **Stages**: CLI supports `scrape`, `filter`, `download`, and `scrape download`, producing JSON manifests (`links.json`, `latest.json`, `selected.json`).
- **Downloader**: `download_from_json` streams with aiohttp, maintains retry logic, and emits `(filename, status, percent)` progress tuples.
- **State management**: Long-running jobs run in background threads; mutate shared state only via `src/api/state_manager.py` helpers to preserve counters and timestamps.
- **Logging**: Initialize loggers through `setup_logger` with env-driven levels (`WEB_APP_*`, `MAIN_*`) so Docker and local runs stay consistent.
- **CLI extensions**: When adding argparse options, propagate them through `download_data_with_config` / `scrape_data_with_config` and mirror defaults in the UI settings.
- **Scraper tuning**: Adjust Scrapy behaviour within `tools/etsi_spider.py` (`ITEM_PIPELINES`, `custom_settings`) instead of the CLI layer.

## Frontend & UX

- **Chakra refactor**: Active development targets `feature/chakra-ui-refactor`, powered by React 18 + Chakra UI + Vite in `frontend/`.
- **Styling**: Favor shared Chakra theme tokens from `frontend/src/theme.ts`; custom CSS should be a last resort.
- **Progress UX**: Reserve 10% for init, 80% for transfers, 10% for completion; keep `app_state.current_operation` aligned with progress cards.
- **Settings persistence**: Frontend reads/writes `web_settings.json`; update `load_saved_settings` and `save_settings` together when adding preferences.
- **File discovery**: `load_available_files` consumes scraper JSON; keep structures (`series`, `release`, `url`, etc.) consistent.
- **Frontend workflow**: Install deps with `npm install`, run dev server via `npm run dev`, build with `npm run build`; ignore `dist/` and `.vite/` outputs.

## Operations & testing

- **Docker**: Use `docker compose up --build -d` (port `8081→32123`); containers mount `downloads/` and `logs/`.
- **Local dev**: Run `python run_web.py` or `uvicorn src.api.server:app --host 0.0.0.0 --port 32123`; CLI pipeline via `python -m src.main scrape download`.
- **Testing**: No dedicated suite; run `pytest` for backend, `npm run lint` and `npm run build` for frontend. Place new tests under `tests/`.
- **Error surfacing**: Backend should raise/log descriptive errors so the UI can display them through `show_error_notification`.

## Collaboration notes

- **Context hand-off**: Summarise outstanding tasks for the Chakra UI rewrite (new components, API wiring) at session end.
- **Copilot file**: Keep this guide off `main`, but copy it to new feature branches to retain context.
