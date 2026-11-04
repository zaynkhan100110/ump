"""UMP Flask API: authenticated single-node media downloader.

Completed media is staged outside the source tree. Metadata is cached separately
in SQLite; it never shares the download directory.
"""
from __future__ import annotations
import ipaddress, json, logging, os, re, shutil, socket, sqlite3, subprocess, threading, time, uuid, unicodedata, tempfile, sys
from pathlib import Path
from urllib.parse import urlparse, urlunparse
from concurrent.futures import ThreadPoolExecutor, TimeoutError as FutureTimeout
from flask import Flask, Response, jsonify, request, send_from_directory, session, stream_with_context
from werkzeug.security import generate_password_hash, check_password_hash
from werkzeug.middleware.proxy_fix import ProxyFix
from platform_detector import detect_platform
from utils import normalize_url as normalize_media_url, rumble_fallback_url, vimeo_fallback_url
from platformdirs import user_data_dir

BASE_DIR = Path(__file__).resolve().parent
FRONTEND_DIR = BASE_DIR.parent / 'frontend'
_default_data = Path(user_data_dir('UMP', 'UMP'))
if os.getenv('UMP_DATABASE_PATH') and not os.getenv('UMP_DATA_DIR'):
    _default_data = Path(os.getenv('UMP_DATABASE_PATH')).expanduser().resolve().parent
DATA_DIR = Path(os.getenv('UMP_DATA_DIR', _default_data)).expanduser().resolve()
# Downloads and DB are deliberately separate; neither defaults to the repository.
DOWNLOAD_DIR = Path(os.getenv('UMP_DOWNLOAD_DIR', DATA_DIR / 'downloads')).expanduser().resolve()
TEMP_DIR = Path(os.getenv('UMP_TEMP_DIR', DATA_DIR / 'tmp')).expanduser().resolve()
DB_PATH = Path(os.getenv('UMP_DATABASE_PATH', DATA_DIR / 'ump.sqlite3')).expanduser().resolve()
for directory in (DATA_DIR, DOWNLOAD_DIR, TEMP_DIR, DB_PATH.parent): directory.mkdir(parents=True, exist_ok=True)
MAX_WORKERS = max(1, min(32, int(os.getenv('UMP_MAX_CONCURRENT', '3'))))
MAX_QUEUED_JOBS = max(MAX_WORKERS, int(os.getenv('UMP_MAX_QUEUED_JOBS', '100')))
JOB_TTL = max(60, int(os.getenv('UMP_JOB_TTL_SECONDS', '3600')))
MAX_CONTENT_LENGTH = int(os.getenv('UMP_MAX_REQUEST_BYTES', '16384'))
MAX_DOWNLOAD_BYTES = int(os.getenv('UMP_MAX_DOWNLOAD_BYTES', str(5 * 1024**3)))
MAX_USER_ACTIVE = max(1, int(os.getenv('UMP_MAX_USER_ACTIVE', '3')))
DELETE_AFTER_DOWNLOAD = os.getenv('UMP_DELETE_AFTER_DOWNLOAD', '1') == '1'
METADATA_TIMEOUT = max(20, int(os.getenv('UMP_METADATA_TIMEOUT', '150')))
SOCKET_TIMEOUT = max(5, int(os.getenv('UMP_SOCKET_TIMEOUT', '30')))
CACHE_TTL = max(0, int(os.getenv('UMP_METADATA_CACHE_TTL', '900')))
CACHE_MAX_ENTRIES = max(10, int(os.getenv('UMP_METADATA_CACHE_MAX_ENTRIES', '500')))
_yt_dlp_path = os.getenv('YTDLP_PATH') or shutil.which('yt-dlp')
YTDLP_COMMAND = [_yt_dlp_path] if _yt_dlp_path else [sys.executable, '-m', 'yt_dlp']
YTDLP = _yt_dlp_path or f'{sys.executable} -m yt_dlp'
DENO = shutil.which('deno')
COOKIES_FILE = os.getenv('UMP_COOKIES_FILE', '').strip()
COOKIES_FROM_BROWSER = os.getenv('UMP_COOKIES_FROM_BROWSER', '').strip()
SECRET_KEY = os.getenv('UMP_SECRET_KEY', '')
if not SECRET_KEY and os.getenv('UMP_ALLOW_INSECURE_SECRET', '0') != '1': raise RuntimeError('Set a long random UMP_SECRET_KEY before starting UMP.')
if len(SECRET_KEY) < 32 and os.getenv('UMP_ALLOW_INSECURE_SECRET', '0') != '1': raise RuntimeError('UMP_SECRET_KEY must contain at least 32 characters.')

logging.basicConfig(level=os.getenv('LOG_LEVEL', 'INFO').upper(), format='%(asctime)s %(levelname)s %(name)s: %(message)s')
log = logging.getLogger('ump')
app = Flask(__name__, static_folder=str(FRONTEND_DIR), static_url_path='')
app.config.update(SECRET_KEY=SECRET_KEY or 'development-only-change-me', MAX_CONTENT_LENGTH=MAX_CONTENT_LENGTH,
                  SESSION_COOKIE_HTTPONLY=True, SESSION_COOKIE_SAMESITE='Lax',
                  SESSION_COOKIE_SECURE=os.getenv('UMP_COOKIE_SECURE', '1') == '1', PERMANENT_SESSION_LIFETIME=60*60*24*7)
if os.getenv('UMP_TRUST_PROXY', '0') == '1': app.wsgi_app = ProxyFix(app.wsgi_app, x_for=1, x_proto=1, x_host=1)

lock = threading.RLock()
executor = ThreadPoolExecutor(max_workers=MAX_WORKERS, thread_name_prefix='ump-download')
metadata_executor = ThreadPoolExecutor(max_workers=max(2, min(8, MAX_WORKERS)), thread_name_prefix='ump-metadata')
active_processes: dict[str, subprocess.Popen] = {}


def db():
    conn = sqlite3.connect(DB_PATH, timeout=30)
    conn.row_factory = sqlite3.Row
    conn.execute('PRAGMA journal_mode=WAL')
    conn.execute('PRAGMA synchronous=NORMAL')
    conn.execute('PRAGMA foreign_keys=ON')
    return conn


def init_db():
    with db() as c:
        c.executescript('''
        CREATE TABLE IF NOT EXISTS users(id INTEGER PRIMARY KEY, username TEXT UNIQUE NOT NULL, password_hash TEXT NOT NULL, created REAL NOT NULL);
        CREATE TABLE IF NOT EXISTS jobs(id TEXT PRIMARY KEY, user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
          url TEXT NOT NULL, format_id TEXT NOT NULL, status TEXT NOT NULL, progress REAL NOT NULL DEFAULT 0,
          error TEXT, filename TEXT, file_path TEXT, created REAL NOT NULL, updated REAL NOT NULL);
        CREATE INDEX IF NOT EXISTS idx_jobs_user_created ON jobs(user_id, created DESC);
        CREATE INDEX IF NOT EXISTS idx_jobs_status ON jobs(status, created);
        CREATE TABLE IF NOT EXISTS metadata_cache(cache_key TEXT PRIMARY KEY, payload TEXT NOT NULL, created REAL NOT NULL, expires REAL NOT NULL);
        CREATE INDEX IF NOT EXISTS idx_metadata_expiry ON metadata_cache(expires);
        ''')
        c.execute("UPDATE jobs SET status='error', error='Server restarted while this job was running.', updated=? WHERE status='downloading'", (time.time(),))

init_db()


def json_error(message, status=400): return jsonify(error=message), status


def current_user():
    uid = session.get('user_id')
    if not uid: return None
    with db() as c: return c.execute('SELECT id, username FROM users WHERE id=?', (uid,)).fetchone()


def login_required(fn):
    from functools import wraps
    @wraps(fn)
    def wrapped(*args, **kwargs):
        if not current_user(): return json_error('Please sign in to continue.', 401)
        return fn(*args, **kwargs)
    return wrapped


def csrf_required():
    token = session.get('csrf_token'); supplied = request.headers.get('X-CSRF-Token', '')
    return bool(token and supplied and token == supplied)

@app.before_request
def protect_mutations():
    if request.method in ('POST', 'PUT', 'PATCH', 'DELETE') and request.endpoint not in ('register', 'login'):
        if session.get('user_id') and not csrf_required(): return json_error('Invalid or missing CSRF token. Refresh the page and try again.', 403)


def normalize_url(value):
    """Normalize pasted links while preserving platform IDs and query parameters."""
    if not isinstance(value, str) or len(value) > 4096:
        raise ValueError('Please provide a valid URL (maximum 4096 characters).')
    value = normalize_media_url(value)
    if not value:
        raise ValueError('Please paste a complete media URL.')
    return value


def validate_url(value):
    value = normalize_url(value); p = urlparse(value)
    if p.scheme.lower() not in ('http', 'https') or not p.hostname: raise ValueError('Only complete http:// or https:// URLs are supported.')
    if p.username or p.password: raise ValueError('URLs containing embedded credentials are not supported.')
    host = p.hostname.rstrip('.').lower()
    if host in ('localhost', 'localhost.localdomain') or host.endswith(('.localhost', '.local')): raise ValueError('Local and private network destinations are not allowed.')
    try:
        addresses = {ipaddress.ip_address(host)} if re.fullmatch(r'[0-9a-fA-F:.]+', host) else {ipaddress.ip_address(x[4][0]) for x in socket.getaddrinfo(host, None)}
    except (ValueError, socket.gaierror, OSError): raise ValueError('The URL host could not be resolved.')
    if not addresses or any(not a.is_global for a in addresses): raise ValueError('URLs resolving to private, loopback, link-local or reserved addresses are not allowed.')
    return value


def metadata_cache_get(url):
    if not CACHE_TTL: return None
    now = time.time()
    with db() as c:
        row = c.execute('SELECT payload,expires FROM metadata_cache WHERE cache_key=?', (url,)).fetchone()
        if not row: return None
        if row['expires'] <= now:
            c.execute('DELETE FROM metadata_cache WHERE cache_key=?', (url,)); return None
        return json.loads(row['payload'])


def metadata_cache_set(url, payload):
    if not CACHE_TTL: return
    now = time.time()
    with db() as c:
        c.execute('INSERT OR REPLACE INTO metadata_cache(cache_key,payload,created,expires) VALUES(?,?,?,?)', (url,json.dumps(payload,separators=(',',':')),now,now+CACHE_TTL))
        c.execute('DELETE FROM metadata_cache WHERE expires<?', (now,))
        c.execute('DELETE FROM metadata_cache WHERE cache_key IN (SELECT cache_key FROM metadata_cache ORDER BY created DESC LIMIT -1 OFFSET ?)', (CACHE_MAX_ENTRIES,))


def _ytdlp_base_command():
    return list(YTDLP_COMMAND)


def _metadata_candidates(url):
    """Return conservative, ordered URL fallbacks; never invent IDs."""
    candidates = [url]
    platform = detect_platform(url)
    fallback = None
    if platform == 'vimeo':
        fallback = vimeo_fallback_url(url)
    elif platform == 'rumble':
        fallback = rumble_fallback_url(url)
    if fallback and fallback not in candidates:
        candidates.append(fallback)
    return candidates


def _run_ytdlp_once(url):
    base = _ytdlp_base_command() + [
        '--no-warnings', '--no-playlist', '--dump-single-json', '--skip-download',
        '--socket-timeout', str(SOCKET_TIMEOUT), '--retries', '1', '--extractor-retries', '1'
    ]
    if DENO:
        base.extend(['--js-runtimes', f'deno:{DENO}'])
    elif shutil.which('node'):
        base.extend(['--js-runtimes', f'node:{shutil.which("node")}'])
    platform = detect_platform(url)
    profiles = ['']
    if platform == 'rumble':
        profiles = [p.strip() for p in os.getenv(
            'UMP_RUMBLE_IMPERSONATE_PROFILES',
            'Safari-18.4:Macos-15,Safari-18.0:Macos-15,Chrome-151:Windows-10,Chrome-152:Windows-10,Chrome-150:Macos-26'
        ).split(',') if p.strip()] or ['']
        base.extend(['--add-headers', 'Origin: https://rumble.com',
                     '--add-headers', 'Referer: https://rumble.com/'])
    elif platform == 'bilibili':
        base.extend(['--add-headers', 'Origin: https://www.bilibili.com',
                     '--add-headers', 'Referer: https://www.bilibili.com/',
                     '--add-headers', 'Accept-Language: en-US,en;q=0.9'])
    if COOKIES_FILE:
        cookie_path = Path(COOKIES_FILE).expanduser().resolve()
        if not cookie_path.is_file():
            raise RuntimeError('UMP_COOKIES_FILE is configured but the cookie file does not exist.')
        base.extend(['--cookies', str(cookie_path)])
    elif COOKIES_FROM_BROWSER:
        base.extend(['--cookies-from-browser', COOKIES_FROM_BROWSER])
    base.append(url)
    last_detail = 'Extractor failed'
    for index, profile in enumerate(profiles, 1):
        cmd = list(base)
        if profile:
            cmd[-1:-1] = ['--impersonate', profile]
        log.info('Metadata extraction started platform=%s host=%s profile=%s attempt=%s/%s',
                 platform, urlparse(url).hostname, profile or 'default', index, len(profiles))
        result = subprocess.run(cmd, capture_output=True, text=True, encoding='utf-8',
                                errors='replace', timeout=METADATA_TIMEOUT,
                                cwd=str(TEMP_DIR), env=os.environ.copy())
        if result.returncode:
            last_detail = (result.stderr or result.stdout or 'Extractor failed').strip()[-1600:]
            if 'authentication is required' in last_detail.lower():
                raise RuntimeError('This source requires authentication. Configure UMP_COOKIES_FILE or UMP_COOKIES_FROM_BROWSER. Details: ' + last_detail[-600:])
            if platform == 'rumble' and index < len(profiles) and any(code in last_detail for code in ('403', '400')):
                log.warning('Rumble rejected impersonation profile=%s; trying next configured profile', profile or 'default')
                continue
            if '403' in last_detail:
                raise RuntimeError('The source refused the extraction request (HTTP 403). It may require cookies or may be blocking this server. ' + last_detail[-600:])
            raise RuntimeError(last_detail)
        try:
            return json.loads(result.stdout)
        except json.JSONDecodeError as exc:
            raise RuntimeError('yt-dlp returned invalid metadata JSON.') from exc
    raise RuntimeError('Rumble rejected all configured impersonation profiles. Network/IP reputation or site-side restrictions may be responsible. ' + last_detail[-600:])


def run_ytdlp_json(url):
    failures = []
    for candidate in _metadata_candidates(url):
        try:
            info = _run_ytdlp_once(candidate)
            info.setdefault('_ump_resolved_url', info.get('webpage_url') or candidate)
            return info
        except subprocess.TimeoutExpired:
            raise
        except Exception as exc:
            failures.append(f'{candidate}: {exc}')
            log.warning('Metadata candidate failed: %s', exc)
    raise RuntimeError('All supported URL attempts failed. ' + ' | '.join(failures)[-1400:])


def simplify_formats(info):
    out=[]
    for item in info.get('formats') or []:
        fid=str(item.get('format_id') or '')
        if not fid or 'storyboard' in fid.lower(): continue
        h=item.get('height')
        if h is not None and h < 100: continue
        vc,ac=item.get('vcodec','none'),item.get('acodec','none')
        selection = f'{fid}+bestaudio/best' if vc not in (None, 'none') and ac in (None, 'none') else fid
        out.append({'format_id':selection,'ext':item.get('ext') or 'unknown','quality':item.get('format_note') or item.get('resolution') or (f'{h}p' if h else fid),
                    'has_video':vc not in (None,'none'),'has_audio':ac not in (None,'none'),'size':item.get('filesize') or item.get('filesize_approx'),
                    'height':h,'width':item.get('width'),'fps':item.get('fps'),'note':item.get('format_note') or ''})
    return out

@app.get('/')
def index(): return send_from_directory(FRONTEND_DIR, 'index.html')

@app.get('/api/health')
def health():
    with db() as c:
        counts={r['status']:r['n'] for r in c.execute('SELECT status, COUNT(*) n FROM jobs GROUP BY status')}
        cache_count=c.execute('SELECT COUNT(*) FROM metadata_cache WHERE expires>?',(time.time(),)).fetchone()[0]
    return jsonify(status='ok', workers=MAX_WORKERS, metadata_workers=metadata_executor._max_workers, metadata_cache_entries=cache_count, jobs=counts)

@app.post('/api/auth/register')
def register():
    data=request.get_json(silent=True) or {}; username=str(data.get('username','')).strip().lower(); password=data.get('password','')
    if not re.fullmatch(r'[a-z0-9_.-]{3,32}', username): return json_error('Username must be 3–32 characters: letters, numbers, dot, underscore or hyphen.')
    if not isinstance(password,str) or len(password)<12 or len(password)>256: return json_error('Password must be between 12 and 256 characters.')
    with db() as c:
        c.execute('BEGIN IMMEDIATE'); count=c.execute('SELECT COUNT(*) FROM users').fetchone()[0]
        if count and os.getenv('UMP_ALLOW_REGISTRATION','0') != '1': return json_error('Registration is closed. Ask the administrator to create or enable an account.', 403)
        try: c.execute('INSERT INTO users(username,password_hash,created) VALUES(?,?,?)',(username,generate_password_hash(password),time.time()))
        except sqlite3.IntegrityError: return json_error('That username is already taken.',409)
        uid=c.execute('SELECT id FROM users WHERE username=?',(username,)).fetchone()['id']
    session.clear(); session['user_id']=uid; session.permanent=True; session['csrf_token']=uuid.uuid4().hex
    return jsonify(username=username, csrf_token=session['csrf_token']),201

@app.post('/api/auth/login')
def login():
    data=request.get_json(silent=True) or {}; username=str(data.get('username','')).strip().lower(); password=data.get('password','')
    with db() as c: user=c.execute('SELECT * FROM users WHERE username=?',(username,)).fetchone()
    if not user or not check_password_hash(user['password_hash'], password if isinstance(password,str) else ''):
        time.sleep(0.4); return json_error('Incorrect username or password.',401)
    session.clear(); session['user_id']=user['id']; session.permanent=True; session['csrf_token']=uuid.uuid4().hex
    return jsonify(username=username,csrf_token=session['csrf_token'])

@app.get('/api/auth/me')
def me():
    user=current_user()
    if not user: return jsonify(authenticated=False)
    if not session.get('csrf_token'): session['csrf_token']=uuid.uuid4().hex
    return jsonify(authenticated=True,username=user['username'],csrf_token=session['csrf_token'])

@app.post('/api/auth/logout')
@login_required
def logout(): session.clear(); return jsonify(success=True)

@app.post('/api/info')
@login_required
def get_info():
    data=request.get_json(silent=True) or {}
    try:
        url=validate_url(data.get('url')); cached=metadata_cache_get(url)
        if cached:
            cached['cache_hit'] = True
            return jsonify(cached)
        future=metadata_executor.submit(run_ytdlp_json,url)
        try: info=future.result(timeout=METADATA_TIMEOUT+5)
        except FutureTimeout: future.cancel(); raise subprocess.TimeoutExpired(YTDLP,METADATA_TIMEOUT)
        formats=simplify_formats(info)
        if not formats: return json_error('No downloadable formats were returned by the source.',404)
        result={'url':info.get('_ump_resolved_url') or info.get('webpage_url') or url,'platform':detect_platform(url),'title':info.get('title') or 'Untitled media','formats':formats,'cache_hit':False}
        metadata_cache_set(url,result)
        return jsonify(result)
    except ValueError as e: return json_error(str(e))
    except subprocess.TimeoutExpired: return json_error(f'The source did not respond within {METADATA_TIMEOUT} seconds. Try again later or configure cookies if the platform requires authentication.',504)
    except Exception as e: log.warning('Metadata extraction failed: %s',e); return json_error(f'Could not read this media. {str(e)[:700]}',502)


def get_job(job_id, user_id):
    with db() as c: return c.execute('SELECT * FROM jobs WHERE id=? AND user_id=?',(job_id,user_id)).fetchone()


def worker(job_id):
    with db() as c:
        job=c.execute('SELECT * FROM jobs WHERE id=?',(job_id,)).fetchone()
        if not job or job['status']!='pending': return
        c.execute("UPDATE jobs SET status='downloading',updated=? WHERE id=?",(time.time(),job_id))
    outtmpl=str(DOWNLOAD_DIR/f'{job_id}.%(ext)s')
    cmd=_ytdlp_base_command()+['--newline','--no-warnings','--no-playlist','--no-part','--progress','--max-filesize',str(MAX_DOWNLOAD_BYTES),'--socket-timeout',str(SOCKET_TIMEOUT),'--retries','5','--fragment-retries','5','--file-access-retries','3']
    if DENO: cmd.extend(['--js-runtimes',f'deno:{DENO}'])
    elif shutil.which('node'): cmd.extend(['--js-runtimes',f'node:{shutil.which("node")}'])
    if detect_platform(job['url']) == 'rumble':
        rumble_profiles = [p.strip() for p in os.getenv(
            'UMP_RUMBLE_IMPERSONATE_PROFILES',
            'Safari-18.4:Macos-15,Safari-18.0:Macos-15,Chrome-151:Windows-10,Chrome-152:Windows-10,Chrome-150:Macos-26'
        ).split(',') if p.strip()]
        if rumble_profiles:
            cmd.extend(['--impersonate', rumble_profiles[0]])
        cmd.extend(['--add-headers','Origin: https://rumble.com','--add-headers','Referer: https://rumble.com/'])
    elif detect_platform(job['url']) == 'bilibili':
        # Bilibili's media CDN may reject default downloader requests with HTTP 567.
        # Browser-like headers and an open-ended Range request are a known workaround.
        cmd.extend([
            '--add-headers', 'Origin: https://www.bilibili.com',
            '--add-headers', 'Referer: https://www.bilibili.com/',
            '--add-headers', 'User-Agent: Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36',
            '--add-headers', 'Range: bytes=0-',
            '--retries', '20', '--fragment-retries', '20',
            '--retry-sleep', 'http:1:5', '--retry-sleep', 'fragment:1:5',
        ])
    if COOKIES_FILE: cmd.extend(['--cookies',str(Path(COOKIES_FILE).expanduser().resolve())])
    elif COOKIES_FROM_BROWSER: cmd.extend(['--cookies-from-browser',COOKIES_FROM_BROWSER])
    cmd.extend(['-f',job['format_id'],'-o',outtmpl,job['url']])
    try:
        proc=subprocess.Popen(cmd,stdout=subprocess.PIPE,stderr=subprocess.STDOUT,text=True,encoding='utf-8',errors='replace',bufsize=1,cwd=str(TEMP_DIR),env=os.environ.copy())
        with lock: active_processes[job_id]=proc
        with db() as c: still_active=c.execute("SELECT 1 FROM jobs WHERE id=? AND status='downloading'",(job_id,)).fetchone()
        if not still_active:
            proc.terminate(); proc.wait(timeout=5)
            with lock: active_processes.pop(job_id,None)
            return
        stderr_tail=[]
        for line in proc.stdout:
            stderr_tail.append(line.rstrip())
            if len(stderr_tail)>30: stderr_tail.pop(0)
            m=re.search(r'\[download\]\s+(\d+(?:\.\d+)?)%',line)
            if m:
                with db() as c: c.execute("UPDATE jobs SET progress=?,updated=? WHERE id=? AND status='downloading'",(min(99.9,float(m.group(1))),time.time(),job_id))
        code=proc.wait()
        with lock: active_processes.pop(job_id,None)
        candidates=[p for p in DOWNLOAD_DIR.glob(f'{job_id}.*') if p.is_file() and not p.name.endswith(('.part','.ytdl'))]
        if code or not candidates:
            detail='\n'.join(stderr_tail)[-1400:]
            raise RuntimeError(f'yt-dlp failed (exit code {code}); the source or selected format may be unavailable. {detail}')
        path=max(candidates,key=lambda p:p.stat().st_mtime)
        if path.stat().st_size<=0 or path.stat().st_size>MAX_DOWNLOAD_BYTES: raise RuntimeError('Downloaded file is empty or exceeds UMP_MAX_DOWNLOAD_BYTES.')
        with db() as c: c.execute("UPDATE jobs SET status='completed',progress=100,filename=?,file_path=?,updated=? WHERE id=?",(path.name,str(path),time.time(),job_id))
    except Exception as e:
        with lock: active_processes.pop(job_id,None)
        for p in DOWNLOAD_DIR.glob(f'{job_id}.*'):
            try: p.unlink(missing_ok=True)
            except OSError: pass
        log.exception('Download job %s failed',job_id)
        with db() as c: c.execute("UPDATE jobs SET status='error',error=?,updated=? WHERE id=?",(str(e)[:800],time.time(),job_id))

@app.post('/api/download')
@login_required
def start_download():
    data=request.get_json(silent=True) or {}; user=current_user()
    try: url=validate_url(data.get('url'))
    except ValueError as e: return json_error(str(e))
    fid=str(data.get('format_id') or '').strip()
    if not fid or len(fid)>100 or not re.fullmatch(r'[A-Za-z0-9_.+/-]+',fid): return json_error('A valid format_id is required.')
    with db() as c:
        active=c.execute("SELECT COUNT(*) FROM jobs WHERE status IN ('pending','downloading')").fetchone()[0]
        user_active=c.execute("SELECT COUNT(*) FROM jobs WHERE user_id=? AND status IN ('pending','downloading')",(user['id'],)).fetchone()[0]
        duplicate=c.execute("SELECT 1 FROM jobs WHERE user_id=? AND url=? AND format_id=? AND status IN ('pending','downloading')",(user['id'],url,fid)).fetchone()
        if duplicate: return json_error('This format is already queued or downloading.',409)
        if active>=MAX_QUEUED_JOBS: return json_error('The download queue is full. Try again later.',503)
        if user_active>=MAX_USER_ACTIVE: return json_error('Your active download limit has been reached.',429)
        jid=uuid.uuid4().hex; now=time.time()
        c.execute("INSERT INTO jobs(id,user_id,url,format_id,status,created,updated) VALUES(?,?,?,?,?,?,?)",(jid,user['id'],url,fid,'pending',now,now))
    executor.submit(worker,jid); return jsonify(job_id=jid),202

@app.get('/api/jobs')
@login_required
def list_jobs():
    user=current_user()
    with db() as c: rows=c.execute('SELECT id,url,format_id,status,progress,error,filename,created FROM jobs WHERE user_id=? ORDER BY created DESC LIMIT 100',(user['id'],)).fetchall()
    return jsonify(jobs=[dict(r) for r in rows],max_concurrent=MAX_WORKERS)

@app.get('/api/progress/<job_id>')
@login_required
def progress_stream(job_id):
    uid=current_user()['id']
    def events():
        while True:
            job=get_job(job_id,uid)
            if not job: payload={'error':'Job not found'}; done=True
            else:
                payload={'progress':job['progress'],'status':job['status'],'error':job['error']}
                if job['status']=='completed': payload.update(complete=True,file_url=f'/api/file/{job_id}')
                done=job['status'] in ('completed','error','cancelled')
            yield f'data: {json.dumps(payload)}\n\n'
            if done: break
            time.sleep(1)
    return Response(stream_with_context(events()),mimetype='text/event-stream',headers={'Cache-Control':'no-cache','X-Accel-Buffering':'no'})

@app.get('/api/file/<job_id>')
@login_required
def download_file(job_id):
    job=get_job(job_id,current_user()['id'])
    if not job or job['status']!='completed' or not job['file_path']: return json_error('The file is not ready or has expired.',404)
    path=Path(job['file_path']).resolve()
    if not path.is_file() or path.parent!=DOWNLOAD_DIR: return json_error('The downloaded file no longer exists.',404)
    response = send_from_directory(path.parent,path.name,as_attachment=True,download_name=path.name,conditional=True)
    if DELETE_AFTER_DOWNLOAD:
        def remove_staged_file():
            try:
                path.unlink(missing_ok=True)
                with db() as c: c.execute('UPDATE jobs SET file_path=NULL, filename=NULL, updated=? WHERE id=? AND user_id=?',(time.time(),job_id,current_user_id))
                log.info('Removed staged download after delivery job=%s', job_id)
            except OSError: log.warning('Could not remove staged download job=%s', job_id)
        current_user_id = current_user()['id']
        response.call_on_close(remove_staged_file)
    return response

@app.delete('/api/delete/<job_id>')
@login_required
def delete_job(job_id):
    uid=current_user()['id']; job=get_job(job_id,uid)
    if not job: return json_error('Job not found.',404)
    with lock: proc=active_processes.pop(job_id,None)
    if proc and proc.poll() is None:
        proc.terminate()
        try: proc.wait(timeout=4)
        except subprocess.TimeoutExpired: proc.kill()
    with db() as c: c.execute('DELETE FROM jobs WHERE id=? AND user_id=?',(job_id,uid))
    for p in DOWNLOAD_DIR.glob(f'{job_id}.*'):
        try: p.unlink(missing_ok=True)
        except OSError: log.warning('Could not remove %s',p)
    return jsonify(success=True)


def cleanup_loop():
    while True:
        time.sleep(300); cutoff=time.time()-JOB_TTL
        with db() as c:
            rows=c.execute("SELECT id FROM jobs WHERE created<? AND status IN ('completed','error','cancelled')",(cutoff,)).fetchall()
            c.executemany('DELETE FROM jobs WHERE id=?',[(r['id'],) for r in rows])
            c.execute('DELETE FROM metadata_cache WHERE expires<?',(time.time(),))
        for r in rows:
            for p in DOWNLOAD_DIR.glob(f"{r['id']}.*"):
                try: p.unlink(missing_ok=True)
                except OSError: log.warning('Cleanup failed for %s',p)
        # Remove orphaned partials and abandoned temp files after one day.
        stale=time.time()-86400
        for folder in (DOWNLOAD_DIR,TEMP_DIR):
            for p in folder.iterdir():
                try:
                    if p.is_file() and p.stat().st_mtime<stale and (p.name.endswith(('.part','.ytdl','.tmp')) or folder==TEMP_DIR): p.unlink(missing_ok=True)
                except OSError: pass

with db() as _c: _pending_ids=[r['id'] for r in _c.execute("SELECT id FROM jobs WHERE status='pending' ORDER BY created")]
for _jid in _pending_ids: executor.submit(worker,_jid)
threading.Thread(target=cleanup_loop,daemon=True,name='ump-cleanup').start()

if __name__=='__main__': app.run(host=os.getenv('HOST','127.0.0.1'),port=int(os.getenv('PORT','5000')),debug=False,threaded=True)
