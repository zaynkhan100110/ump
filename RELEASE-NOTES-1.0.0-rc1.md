# UMP 1.0.0-rc1 release notes

- Added matching SVG application logo and browser favicon.
- Added configurable Rumble impersonation profile ordering.
- Metadata extraction retries configured Rumble profiles after HTTP 400/403 responses.
- Download requests use the first configured Rumble profile.
- Retained Bilibili Origin/Referer/User-Agent/Range headers and extended HTTP/fragment retries.
- Expanded README with branding, release validation, and scaling boundaries.

## Validation

- `python -m compileall -q backend tests`: passed.
- `python -m unittest discover -s tests -p 'test_url_utils.py' -v`: 8 passed.
- Full API test suite: not run; Flask and other requirements were not installed in the isolated build environment and package installation was blocked by unavailable network access.
- Live Bilibili/Rumble downloads: not run in this build environment.
