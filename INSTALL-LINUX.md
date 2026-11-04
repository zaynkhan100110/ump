# UMP installation — Linux

UMP is distribution-independent. Install Python, pip/venv, and FFmpeg with your distribution's package manager, then use the same virtual-environment steps.

## Common prerequisites

- Python 3.10+
- `venv` and pip
- FFmpeg
- Optional JavaScript runtime: Deno or Node.js

Examples:

```bash
# Debian / Ubuntu
sudo apt update && sudo apt install -y python3 python3-venv python3-pip ffmpeg

# Fedora
sudo dnf install -y python3 python3-pip ffmpeg

# Arch Linux
sudo pacman -S --needed python python-pip ffmpeg
```

Install and run:

```bash
git clone https://github.com/zaynkhan100110/ump.git
cd ump
python3 -m venv .venv
source .venv/bin/activate
python -m pip install --upgrade pip
python -m pip install -r backend/requirements.txt
python -c 'import secrets; print(secrets.token_urlsafe(48))'
```

Set the generated value as `UMP_SECRET_KEY`. For local HTTP only, set `UMP_COOKIE_SECURE=0`.

```bash
export UMP_SECRET_KEY='paste-your-generated-secret-here'
export UMP_COOKIE_SECURE=0
python backend/app.py
```

Open http://127.0.0.1:5000. For a production deployment, use a single Gunicorn worker behind an HTTPS reverse proxy; see the deployment section in the main README.

## Storage

UMP uses the XDG data directory on Linux (normally `~/.local/share/UMP/`). It keeps the database, metadata cache, temporary workspace, and staged downloads outside the source checkout. Override with `UMP_DATA_DIR` if desired.
