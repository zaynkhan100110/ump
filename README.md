# UMP — Universal Media Downloader

Repository: https://github.com/zaynkhan100110/ump

UMP is a self-hostable web application built around [yt-dlp](https://github.com/yt-dlp/yt-dlp). It inspects public media URLs, lists available formats, queues downloads, streams progress, and lets authenticated users retrieve their own files.

> **Responsible use:** Download only content you own, have permission to download, or are legally allowed to save. Respect copyright, privacy, website terms, and local law. UMP is not intended to bypass DRM, paywalls, authentication, or other access controls.

## Current implementation and capacity statement

This release adds account authentication, per-user job ownership, CSRF protection, persistent SQLite job records, bounded download and metadata worker pools, a persistent size-limited metadata cache, configurable timeouts, optional yt-dlp cookie support, URL paste normalization, automatic retention cleanup, and a redesigned responsive interface.

**Important capacity boundary:** This is a hardened single-instance foundation, SQLite and the in-process worker pool are suitable for a modest single-node deployment. The project has not yet been load-tested for large simultaneous-download workloads. Do not run multiple UMP replicas against the same SQLite database and assume they form a distributed queue. A later scale-out phase should migrate job/account state to PostgreSQL, use Redis plus Celery/RQ for distributed workers, and use shared S3-compatible object storage. The 5,000+ target remains a design goal until that work and realistic load testing are complete.

## Features

- yt-dlp extractor catalogue for supported public media sites.
- Format listing and download selection.
- Downloaded files are temporarily staged on the server outside the source repository, removed after successful browser delivery by default, and otherwise expire with job retention.
- Account registration/login and session-based authentication.
- User-scoped job listing, progress, file access, and deletion.
- SQLite-persisted job metadata and extraction cache; pending jobs are re-submitted on startup.
- Metadata cache is independent from downloaded media and has configurable TTL and entry limits. Successful metadata is cached; video files are not cached for reuse.
- Database, temporary workspace, and downloaded files default outside the source checkout using each OS's application-data convention (Windows Local AppData, macOS Application Support, Linux XDG data directory).
- Configurable worker concurrency, queue capacity, per-user active-job cap, file-size cap, and retention.
- Server-Sent Events (SSE) progress updates.
- Docker deployment with persistent data volume and health check.
- Rumble, Bilibili, YouTube, Reddit, and other sources supported when yt-dlp supports them; availability changes by site, extractor version, network, and IP reputation.
- Rumble metadata extraction tries a configurable ordered list of browser impersonation profiles after HTTP 400/403 responses. Download requests use the first configured profile. Impersonation does not bypass access controls or guarantee that a site will allow the request.
- Bundled UMP SVG brand mark and browser-tab favicon.

## Supported operating systems

UMP is designed to run natively on **Windows 10/11, macOS (Intel and Apple Silicon), and Linux**. Docker Desktop is also supported on Windows and macOS; Docker Engine/Compose is supported on Linux. The web interface is accessed through a browser and does not require a platform-specific client.

The application uses `pathlib` and `platformdirs` for OS-native paths, detects yt-dlp on `PATH` (or falls back to the active Python interpreter's `-m yt_dlp` module), and detects Deno or Node.js for yt-dlp JavaScript challenges. FFmpeg is recommended for merging separate audio/video streams.

### Platform-specific installation guides

- [Windows 10/11](INSTALL-WINDOWS.md)
- [macOS](INSTALL-MACOS.md)
- [Linux](INSTALL-LINUX.md)
- [Docker / Docker Desktop](INSTALL-DOCKER.md)

## Requirements

### Docker (recommended)

- 64-bit Linux server or desktop (Docker Desktop works on Windows/macOS).
- Docker Engine and Docker Compose v2 (`docker compose`).
- Persistent storage with enough free space for downloaded files and the SQLite database. Manual installs use the OS-specific application-data directory; Docker uses its `/data` volume.
- A reverse proxy such as Caddy or Nginx for public HTTPS deployments.

### Manual installation

- Python 3.10 or newer.
- pip and venv.
- FFmpeg (recommended; required for many merge/conversion operations).
- yt-dlp is installed from `backend/requirements.txt`.
- Internet access and sufficient storage.

## Quick start with Docker

1. Clone the repository:

   ```bash
   git clone https://github.com/zaynkhan100110/ump.git
   cd ump
   ```

2. Create your environment file and generate a strong session secret:

   ```bash
   cp .env.example .env
   python -c "import secrets; print(secrets.token_urlsafe(48))"
   ```

   Copy the generated value into `.env` as `UMP_SECRET_KEY`. Do not commit `.env` or share the secret.

3. Start UMP:

   ```bash
   docker compose up -d --build
   docker compose logs -f
   ```

4. Open `http://127.0.0.1:5000` on the server. For remote use, configure a reverse proxy and HTTPS first, then access the public HTTPS hostname.

5. On a new installation, choose **Create first account / register**. The first account bootstraps the instance. After it exists, registration is closed by default. To allow open registration, set `UMP_ALLOW_REGISTRATION=1` in the Compose environment and recreate the service. For a public service, prefer controlled account provisioning rather than unrestricted registration.

Stop UMP:

```bash
docker compose down
```

Back up the `ump-data` volume before upgrades or maintenance. `docker compose down -v` permanently deletes the database and downloads.

## Manual installation

### Native installation

Use the dedicated platform guides above for Windows, macOS, or Linux. The same Python requirements are installed on each platform.

### Production server notes

- **Linux/macOS:** Run one Gunicorn worker for this single-instance architecture, with threads for HTTP requests, behind an HTTPS reverse proxy:

  ```bash
  gunicorn --chdir backend --workers 1 --threads 16 --timeout 180 --bind 127.0.0.1:5000 app:app
  ```

- **Windows:** The requirements install Waitress instead of Gunicorn. After setting `UMP_SECRET_KEY` and production cookie settings, run `python backend\server.py`.
- **All platforms:** Do not run multiple application replicas against the same SQLite database. The current queue and worker state are single-instance only.

## Configuration

| Variable | Default | Purpose |
|---|---:|---|
| `UMP_SECRET_KEY` | Required | Random secret of at least 32 characters for signing sessions. |
| `UMP_COOKIE_SECURE` | `1` | Secure cookies; set `0` only for local plain-HTTP development. |
| `UMP_TRUST_PROXY` | `0` | Enable only behind a trusted reverse proxy that overwrites forwarded headers. |
| `UMP_ALLOW_REGISTRATION` | `0` | Allow new registrations after the first account exists. |
| `UMP_MAX_CONCURRENT` | `3` | Number of worker threads in this instance (1–32). |
| `UMP_MAX_QUEUED_JOBS` | `100` | Maximum pending + downloading jobs across this instance. |
| `UMP_MAX_USER_ACTIVE` | `3` | Maximum active jobs per account. |
| `UMP_MAX_DOWNLOAD_BYTES` | 5 GiB | Maximum accepted output file size. |
| `UMP_JOB_TTL_SECONDS` | `3600` | Retention time for completed/failed jobs and staged media files (minimum 60 seconds). |
| `UMP_DELETE_AFTER_DOWNLOAD` | `1` | Delete the server-side staged file after the browser finishes retrieving it. Set `0` to allow repeat retrieval until job expiry. |
| `UMP_DATA_DIR` | OS-specific application-data directory via `platformdirs` | Application data root, outside the source checkout. |
| `UMP_DOWNLOAD_DIR` | `<data dir>/downloads` | Completed media staging directory, separate from database/cache. |
| `UMP_TEMP_DIR` | `<data dir>/tmp` | Temporary working directory; stale temporary files are cleaned. |
| `UMP_DATABASE_PATH` | `<data dir>/ump.sqlite3` | SQLite users, jobs and metadata-cache database. |
| `UMP_METADATA_TIMEOUT` | `150` | Maximum metadata extraction duration in seconds. |
| `UMP_RUMBLE_IMPERSONATE_PROFILES` | Safari/Chrome profile list | Ordered comma-separated yt-dlp curl-cffi profiles for Rumble metadata fallback and the first profile for downloads.\n| `UMP_SOCKET_TIMEOUT` | `30` | yt-dlp network socket timeout in seconds. |
| `UMP_METADATA_CACHE_TTL` | `900` | Metadata cache lifetime in seconds; set `0` to disable. |
| `UMP_METADATA_CACHE_MAX_ENTRIES` | `500` | Maximum number of metadata cache entries. |
| `UMP_COOKIES_FILE` | unset | Optional Netscape-format cookies file for yt-dlp. Keep it private. |
| `UMP_COOKIES_FROM_BROWSER` | unset | Optional local browser profile name for yt-dlp (manual installs; container profiles must be mounted). |
| `UMP_MAX_REQUEST_BYTES` | `16384` | Maximum request body size in bytes. |
| `YTDLP_PATH` | auto-detected | Optional explicit yt-dlp executable path. |
| `LOG_LEVEL` | `INFO` | Logging level. |

Tune concurrency cautiously. Every download consumes bandwidth, CPU, memory, disk I/O, and upstream-site capacity. The configured worker count is not a promise of a specific throughput.

## API overview

All endpoints except health and authentication bootstrap endpoints require a signed-in session where indicated.

| Method | Endpoint | Description |
|---|---|---|
| `GET` | `/api/health` | Basic health and queue counts. |
| `POST` | `/api/auth/register` | Create the first account; later registrations require `UMP_ALLOW_REGISTRATION=1`. |
| `POST` | `/api/auth/login` | Sign in. |
| `GET` | `/api/auth/me` | Current session and CSRF token. |
| `POST` | `/api/auth/logout` | Sign out. |
| `POST` | `/api/info` | Inspect a URL and list formats. |
| `POST` | `/api/download` | Queue a selected format. |
| `GET` | `/api/jobs` | List the signed-in user's latest jobs. |
| `GET` | `/api/progress/<job_id>` | SSE progress stream for an owned job. |
| `GET` | `/api/file/<job_id>` | Retrieve an owned completed file. |
| `DELETE` | `/api/delete/<job_id>` | Delete an owned job and its output. |

Browser requests that change state use the CSRF token returned by `/api/auth/me` in the `X-CSRF-Token` header. Do not expose job IDs as authorization; ownership is checked server-side.

## Security and deployment guidance

- Put UMP behind HTTPS (Caddy/Nginx/Traefik) before exposing it to the internet. The Compose port binds to loopback by default.
- Keep `UMP_SECRET_KEY` private and stable across restarts. Rotate it deliberately because rotation invalidates existing sessions.
- Keep open registration disabled unless you intentionally want public signups.
- Run the container as its unprivileged `ump` user; do not mount sensitive host directories.
- URL validation rejects localhost and private/reserved IP destinations. This is a defense-in-depth check, not a complete SSRF boundary: yt-dlp may follow redirects or contact additional hosts. Apply outbound firewall/network policies at the host/container layer, and do not run UMP in a network with sensitive internal services reachable.
- Set CPU, memory, disk, bandwidth, and per-user quotas appropriate to your host. Monitor the data volume; retention is not a substitute for disk quotas or backups.
- Keep dependencies updated and review yt-dlp releases before production upgrades.
- Do not disable TLS verification or use yt-dlp options that bypass access controls.

## Scaling roadmap for the 5,000+ user goal

The current code is deliberately single-instance. Before claiming support for thousands of users, implement and verify:

1. PostgreSQL for users, durable job state, quotas, and transactions.
2. Redis + Celery/RQ (or equivalent) for distributed queues, worker autoscaling, retries, and cancellation.
3. S3-compatible object storage with per-user ownership, lifecycle rules, and signed/authorized downloads.
4. API rate limiting, account verification/recovery, admin account management, audit logs, and abuse controls.
5. Reverse-proxy/load-balancer configuration, metrics, structured logs, alerting, and backups.
6. Load and soak tests with representative source URLs, file sizes, network limits, and failure scenarios.

A 5,000-account target and 5,000 simultaneous downloads are very different capacity requirements. Define expected active-user percentage, concurrent downloads, average file size, retention, and bandwidth before sizing infrastructure.

## Troubleshooting

- **Secret-key startup error:** Set `UMP_SECRET_KEY` to a random value of at least 32 characters.
- **Secure cookie/login loop on local HTTP:** Set `UMP_COOKIE_SECURE=0` for local development only.
- **Registration closed:** The first account can bootstrap a fresh instance. For subsequent registrations set `UMP_ALLOW_REGISTRATION=1`, or use a controlled admin provisioning process.
- **No formats:** Update yt-dlp, check the URL is publicly accessible, and try again later. Some websites block datacenter IPs or require permitted cookies/login. UMP tries a limited Vimeo player-URL fallback and a Rumble embed-URL fallback when it can confidently identify the media ID; these cannot bypass server-side blocks.
- **Merge/audio failure:** Install FFmpeg and ensure `ffmpeg` is available on `PATH` (inside Docker it is installed in the image).
- **Progress freezes behind Nginx:** Disable proxy buffering for `/api/progress/` and allow long read timeouts.
- **Queue does not scale across replicas:** This release uses a single-instance SQLite database and in-process worker pool. Do not run multiple replicas; use the planned PostgreSQL/Redis worker architecture first.
- **Disk full:** Reduce `UMP_JOB_TTL_SECONDS`, delete old jobs, or expand the data volume. Back up before manual cleanup.
- **Reddit/Bilibili or other login-required sources:** Configure `UMP_COOKIES_FILE` with a private Netscape-format cookie export, or `UMP_COOKIES_FROM_BROWSER` for a local installation with access to that browser profile. Do not commit cookies or expose them to other users. Reddit may require authentication; Bilibili may restrict quality or playback by region/account.
- **Repeated metadata lookups:** UMP caches successful metadata separately from video files for 15 minutes by default. Set `UMP_METADATA_CACHE_TTL=0` to disable it.

## Development checks

From the repository root:

```bash
python -m compileall -q backend
python -m unittest discover -s tests -v
```

Run these commands from the repository root on Windows PowerShell, macOS, or Linux after installing the backend requirements.

These checks do not replace end-to-end tests against real sites or load tests on production-like infrastructure.

## License / project terms

Do not remove attribution or redistribute it in a way that violates the owner's terms.


## Branding and browser icon

The application brand artwork is in `frontend/logo.svg`; the browser-tab icon is
`frontend/favicon.svg`. Both are vector SVG files and are served by Flask from
the frontend static directory. The HTML page links the favicon and Apple touch icon.

## Release validation

The release archive is source-tested in the build environment with Python bytecode
compilation and the URL-normalization test suite. Full Flask API tests and live
platform downloads must also be run in the target deployment environment with
`backend/requirements.txt` installed. External platform behavior (including Rumble
403 responses and Bilibili CDN errors) cannot be guaranteed by a local unit test.

## Scaling and operational boundary

This build is a single-instance deployment: SQLite is the system of record and
the worker queue lives in the application process. Keep one application instance
per data directory/database. For a multi-node public service or a verified
5,000+ user workload, use a separately engineered PostgreSQL-backed account/job
store, Redis-backed distributed queue, shared object storage, per-user/IP
quotas, metrics, centralized logs, and load tests. Do not increase Gunicorn
worker count or run replicas against the same SQLite file as a scaling shortcut.
