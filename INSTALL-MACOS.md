# UMP installation — macOS

## Prerequisites

- macOS on Intel or Apple Silicon
- Python 3.10+ (`brew install python` or the installer from [python.org](https://www.python.org/downloads/macos/))
- Homebrew (recommended): [brew.sh](https://brew.sh/)
- FFmpeg: `brew install ffmpeg`
- Optional JavaScript runtime: `brew install deno` or `brew install node`

## Install and run

```bash
git clone https://github.com/zaynkhan100110/ump.git
cd ump
python3 -m venv .venv
source .venv/bin/activate
python -m pip install --upgrade pip
python -m pip install -r backend/requirements.txt
python -c 'import secrets; print(secrets.token_urlsafe(48))'
```

Create a local `.env` file and set `UMP_SECRET_KEY` to the generated value. Do not commit `.env`. For local HTTP, set `UMP_COOKIE_SECURE=0`.

```bash
export UMP_SECRET_KEY='paste-your-generated-secret-here'
export UMP_COOKIE_SECURE=0
python backend/app.py
```

Open http://127.0.0.1:5000. Stop with Ctrl+C. For a production deployment, run a single Gunicorn worker behind an HTTPS reverse proxy (see the main README).

## Storage

UMP uses macOS Application Support through `platformdirs` (normally `~/Library/Application Support/UMP/`). Runtime files remain outside the source checkout. Override with `UMP_DATA_DIR` if desired.

## Troubleshooting

- If `python3` is missing, install Python 3 from python.org or Homebrew.
- If FFmpeg is missing, run `brew install ffmpeg`, then verify with `ffmpeg -version`.
- Browser-cookie access depends on macOS Keychain permissions and the browser profile. If it fails, use a private Netscape-format cookie file via `UMP_COOKIES_FILE`.
- Apple Silicon and Intel use the same Python setup steps; install matching native dependencies through Homebrew.
