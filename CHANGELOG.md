# Changelog

## 1.0.1 — Cross-platform extractor and portability update

- Added OS-native application-data directories through `platformdirs` for Windows, macOS, and Linux.
- Added Windows Waitress startup and retained Gunicorn for Unix-like systems; yt-dlp now falls back to `python -m yt_dlp` when no executable is on PATH.
- Added Deno/Node runtime detection and explicit UTF-8 subprocess handling for Windows compatibility.
- Expanded Bilibili URL support for BV, av, multi-part `p=` links, and b23.tv short links; added Bilibili request headers and optional configured cookies without assuming Chrome exists.
- Added ordered Vimeo player-page and Rumble embed-page metadata fallbacks when the primary URL fails; the resolved URL is now carried into the download queue.
- Updated video-only format selection to pair video with best available audio, and retained extractor stderr in failed download diagnostics.
- Added platform-specific installation guides and URL-normalization regression tests.
- These fallbacks do not bypass account authentication, IP blocks, Cloudflare challenges, DRM, or other access controls.


## 1.0.0 — UMP security and foundation upgrade

- Added account registration bootstrap, login, logout, password hashing, signed sessions, and CSRF checks.
- Scoped job listing, progress, file retrieval, and deletion to the owning account.
- Persisted job metadata in SQLite and recovered pending jobs after restart.
- Added per-user active-job limits, global queue limits, output-size limits, and retention cleanup.
- Added private/local destination URL checks and documented the need for outbound network firewall rules.
- Repaired SSE event framing and replaced unsafe frontend format/job HTML interpolation with DOM text nodes.
- Added Docker environment configuration, health check, `.env.example`, and setup/security/scaling documentation.
- Added automated API test cases; execution requires installing project dependencies.

This release is a single-instance foundation. It does not yet implement the PostgreSQL/Redis/S3 distributed architecture or prove 5,000-user capacity.


## Bilibili download hotfix

- Added browser-like User-Agent, Bilibili Origin/Referer, and an open-ended Range header to Bilibili download requests.
- Increased Bilibili HTTP/fragment retries with bounded retry delays to tolerate intermittent CDN HTTP 567 responses.
- The Premium-only 1080p60 notice is informational; yt-dlp can still select other available formats.
- HTTP 567 may persist if Bilibili blocks the server/IP or the selected CDN edge is unavailable; this workaround is not guaranteed.
