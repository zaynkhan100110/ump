# UMP installation — Windows 10/11

## Prerequisites

- Windows 10 or 11, 64-bit
- Python 3.10+ from [python.org](https://www.python.org/downloads/windows/) (enable **Add Python to PATH**)
- FFmpeg (recommended): `winget install Gyan.FFmpeg` or install from [ffmpeg.org](https://ffmpeg.org/)
- Optional JavaScript runtime for some YouTube challenges: `winget install DenoLand.Deno` or install Node.js LTS

Open a new PowerShell window after installing tools so PATH changes are applied.

## Install and run

```powershell
git clone https://github.com/zaynkhan100110/ump.git
cd ump
py -3 -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
python -m pip install -r backend\requirements.txt
python -c "import secrets; print(secrets.token_urlsafe(48))"
```

Copy the generated secret into a local `.env` file as `UMP_SECRET_KEY=...`. Do not commit `.env`. For local HTTP use, set `UMP_COOKIE_SECURE=0`. Set `UMP_ALLOW_REGISTRATION=1` only while creating additional accounts; the first account can bootstrap a fresh database.

Start the server:

```powershell
$env:UMP_SECRET_KEY="paste-your-generated-secret-here"
$env:UMP_COOKIE_SECURE="0"
python backend\server.py
```

Open http://127.0.0.1:5000. Stop with Ctrl+C. The Windows guide uses Waitress rather than Gunicorn, which is not supported natively on Windows.

## Storage

By default UMP stores runtime data under `%LOCALAPPDATA%\UMP\UMP\` (the exact path is determined by `platformdirs`). It does not put downloads or its database in the repository. Override with `UMP_DATA_DIR` if desired.

## Troubleshooting

- If script activation is blocked, run `Set-ExecutionPolicy -Scope Process -ExecutionPolicy Bypass` in that PowerShell window, then activate again.
- If `python` is not found, use `py -3` and confirm Python was added to PATH.
- If FFmpeg is not found, reopen PowerShell after installation and run `ffmpeg -version`.
- For browser-cookie extraction, use a browser profile readable by the same Windows account running UMP. Alternatively export a private Netscape-format cookies file and set `UMP_COOKIES_FILE`.
- If `yt-dlp` is not on PATH, UMP attempts `python -m yt_dlp` using the active Python environment.
