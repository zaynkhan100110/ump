/* UMP session gate. CSRF token is attached to same-origin state-changing requests. */
(() => {
  const originalFetch = window.fetch.bind(window);
  let csrf = '';
  window.fetch = (input, init = {}) => {
    const headers = new Headers(init.headers || {});
    if (csrf && !['GET','HEAD','OPTIONS'].includes((init.method || 'GET').toUpperCase())) headers.set('X-CSRF-Token', csrf);
    return originalFetch(input, {...init, headers, credentials: 'same-origin'});
  };
  const mark = '<span class="brand-mark"><svg viewBox="0 0 48 48" aria-hidden="true"><path d="M8 11h7v18a5 5 0 0 0 10 0V11h7v18a12 12 0 0 1-24 0V11Z" fill="currentColor"/><path d="M35 12h5v25h-5z" fill="#7c8cff"/><path d="m34 7 8 5-8 5" fill="none" stroke="#7c8cff" stroke-width="3" stroke-linecap="round" stroke-linejoin="round"/></svg></span>';
  function showGate() {
    if (document.getElementById('ump-auth-gate')) return;
    const gate = document.createElement('div'); gate.id = 'ump-auth-gate';
    gate.innerHTML = `<section class="auth-card"><div class="auth-brand">${mark}<span><strong>UMP</strong><small>UNIVERSAL MEDIA DOWNLOADER</small></span></div><h2 id="auth-title">Welcome back</h2><p id="auth-message">Sign in to manage your media downloads.</p><form id="auth-form"><label>Username<input name="username" autocomplete="username" required minlength="3" maxlength="32"></label><label>Password<input name="password" type="password" autocomplete="current-password" required minlength="12" maxlength="256"></label><div class="auth-actions"><button class="primary" id="auth-submit" type="submit">Sign in</button><button id="register-mode" type="button">Create account</button></div></form><p class="auth-note" id="auth-note">New here? Create the first account to initialize this UMP instance.</p></section>`;
    document.body.appendChild(gate);
    const form=gate.querySelector('#auth-form'), message=gate.querySelector('#auth-message'), note=gate.querySelector('#auth-note'), title=gate.querySelector('#auth-title'), submit=gate.querySelector('#auth-submit'), toggle=gate.querySelector('#register-mode');
    let registering=false;
    toggle.addEventListener('click',()=>{registering=!registering;title.textContent=registering?'Create your account':'Welcome back';submit.textContent=registering?'Create account':'Sign in';toggle.textContent=registering?'Back to sign in':'Create account';message.textContent=registering?'Choose a username and a password with at least 12 characters.':'Sign in to manage your media downloads.';note.textContent=registering?'The first account is always allowed. Later sign-ups require the administrator to enable registration.':'Your downloads and job history are tied to your account.';form.querySelector('[name=password]').autocomplete=registering?'new-password':'current-password';});
    form.addEventListener('submit',async e=>{e.preventDefault();submit.disabled=true;submit.textContent=registering?'Creating…':'Signing in…';message.classList.remove('auth-error');const data=Object.fromEntries(new FormData(form));try{const r=await originalFetch('/api/auth/'+(registering?'register':'login'),{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(data),credentials:'same-origin'});const result=await r.json();if(!r.ok)throw new Error(result.error||'Authentication failed');csrf=result.csrf_token;gate.remove();location.reload();}catch(err){message.textContent=err.message;message.classList.add('auth-error');}finally{submit.disabled=false;submit.textContent=registering?'Create account':'Sign in';}});
  }
  originalFetch('/api/auth/me',{credentials:'same-origin'}).then(r=>r.json()).then(data=>{if(data.authenticated){csrf=data.csrf_token;const logout=document.getElementById('logout-btn');if(logout)logout.addEventListener('click',async()=>{try{await fetch('/api/auth/logout',{method:'POST'});}finally{location.reload();}});}else showGate();}).catch(showGate);
})();
