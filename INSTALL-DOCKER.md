# UMP installation — Docker

Docker is the same deployment method on Linux, Windows with Docker Desktop, and macOS with Docker Desktop.

1. Install Docker Engine + Compose v2 (Linux) or Docker Desktop (Windows/macOS).
2. Clone the repository and enter it:

   ```bash
   git clone https://github.com/zaynkhan100110/ump.git
   cd ump
   ```

3. Copy `.env.example` to `.env` (PowerShell: `Copy-Item .env.example .env`; macOS/Linux: `cp .env.example .env`). Generate a secret with `python -c "import secrets; print(secrets.token_urlsafe(48))"` and set `UMP_SECRET_KEY` in `.env`.
4. Start it with `docker compose up -d --build`.
5. Open http://127.0.0.1:5000. The Compose port binds to loopback by default.

The named `ump-data` volume stores the SQLite database, cache, temporary files, and transient downloads. Video files are removed after browser delivery by default. Configure HTTPS and a reverse proxy before exposing UMP outside the host. See the main README for security and capacity limitations.
