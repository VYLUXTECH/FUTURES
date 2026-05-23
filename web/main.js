(function(){
'use strict';

let SUPABASE_URL = '';
let SUPABASE_ANON_KEY = '';
const API_BASE = '/api';

const $ = (s, p) => (p || document).querySelector(s);
const $$ = (s, p) => [...(p || document).querySelectorAll(s)];

// ── Supabase Client (no hardcoded secrets) ───────────────
let _supabaseClient = null;
async function getSupabase() {
  if (_supabaseClient) return _supabaseClient;

  // Fetch config from backend (credentials never hardcoded)
  if (!SUPABASE_URL && !SUPABASE_ANON_KEY) {
    try {
      const res = await fetch(`${API_BASE}/config`);
      const cfg = await res.json();
      SUPABASE_URL = cfg.supabase_url;
      SUPABASE_ANON_KEY = cfg.supabase_key;
    } catch (e) {
      console.warn('Failed to fetch config from API:', e);
    }
  }

  const storage = {
    getItem: k => Promise.resolve(localStorage.getItem(k)),
    setItem: (k, v) => Promise.resolve(localStorage.setItem(k, v)),
    removeItem: k => Promise.resolve(localStorage.removeItem(k)),
  };

  const { createClient } = window.__SUPABASE__ || {};
  if (createClient && SUPABASE_URL && SUPABASE_ANON_KEY) {
    _supabaseClient = createClient(SUPABASE_URL, SUPABASE_ANON_KEY, {
      auth: { storage, autoRefreshToken: true, persistSession: true, detectSessionInUrl: true },
    });
    return _supabaseClient;
  }

  // Fallback fetch-based auth (no Supabase CDN or no keys configured)
  _supabaseClient = {
    auth: {
      getSession: async () => {
        const tok = localStorage.getItem('futures_token');
        return { data: { session: tok ? { access_token: tok, user: JSON.parse(localStorage.getItem('futures_user') || 'null') } : null } };
      },
      signInWithPassword: async ({ email, password }) => {
        const res = await fetch(`${API_BASE}/auth/login`, { method:'POST', headers:{'Content-Type':'application/json'}, body:JSON.stringify({ email, password }) });
        const data = await res.json();
        if (!res.ok) throw new Error(data.detail || 'Login failed');
        localStorage.setItem('futures_token', data.access_token);
        localStorage.setItem('futures_user', JSON.stringify(data.user));
        return { data: { session: { access_token: data.access_token, user: data.user } } };
      },
      signUp: async ({ email, password }) => {
        const res = await fetch(`${API_BASE}/auth/signup`, { method:'POST', headers:{'Content-Type':'application/json'}, body:JSON.stringify({ email, password }) });
        const data = await res.json();
        if (!res.ok) throw new Error(data.detail || 'Signup failed');
        return data;
      },
      signOut: async () => {
        localStorage.removeItem('futures_token');
        localStorage.removeItem('futures_user');
      },
      resetPasswordForEmail: async email => {
        const res = await fetch(`${API_BASE}/auth/forgot-password`, { method:'POST', headers:{'Content-Type':'application/json'}, body:JSON.stringify({ email }) });
        if (!res.ok) throw new Error('Failed to send reset email');
      },
      updateUser: async ({ password }) => {
        const res = await fetch(`${API_BASE}/settings/change-password`, { method:'PUT', headers:{'Content-Type':'application/json', Authorization:`Bearer ${localStorage.getItem('futures_token')}`}, body:JSON.stringify({ password }) });
        if (!res.ok) throw new Error('Failed to update password');
      },
      signInWithOAuth: async ({ provider }) => {
        window.location.href = `${API_BASE}/auth/oauth/${provider}`;
      },
      onAuthStateChange: () => ({ data: { subscription: { unsubscribe: ()=>{} } } }),
    },
    from: table => ({
      select: cols => ({
        eq: (col, val) => ({
          single: async () => {
            const res = await fetch(`${API_BASE}/public/${table}?${col}=${encodeURIComponent(val)}&select=${encodeURIComponent(cols)}`, { headers:{ Authorization:`Bearer ${localStorage.getItem('futures_token')}` } });
            const data = await res.json();
            if (!res.ok) throw new Error(data.detail || 'DB query failed');
            return { data, error: null };
          }
        }),
      }),
      update: data => ({ eq: (col, val) => {} }),
    }),
  };
  return _supabaseClient;
}

// ── API Client ──────────────────────────────────────────
async function getToken() { return localStorage.getItem('futures_token'); }
async function apiRequest(endpoint, opts = {}) {
  const token = await getToken();
  const headers = { 'Content-Type': 'application/json', ...(opts.headers || {}) };
  if (token) headers['Authorization'] = `Bearer ${token}`;
  const controller = new AbortController();
  const tId = setTimeout(() => controller.abort(), 15000);
  try {
    const res = await fetch(`${API_BASE}${endpoint}`, { ...opts, headers, signal: controller.signal });
    if (!res.ok) {
      let msg = `HTTP ${res.status}`;
      try { const e = await res.json(); msg = e.detail || msg; } catch {}
      throw new Error(msg);
    }
    if (res.status === 204) return null;
    return res.json();
  } finally { clearTimeout(tId); }
}
const api = {
  get: e => apiRequest(e),
  post: (e, b) => apiRequest(e, { method:'POST', body: b ? JSON.stringify(b) : undefined }),
  put: (e, b) => apiRequest(e, { method:'PUT', body: b ? JSON.stringify(b) : undefined }),
};

// ── Toast ────────────────────────────────────────────────
function showToast(msg, type = 'success') {
  const t = document.getElementById('toast');
  const el = document.createElement('div');
  el.className = `toast-item ${type}`;
  el.textContent = msg;
  t.appendChild(el);
  setTimeout(() => { el.style.opacity='0'; el.style.transition='opacity .3s'; setTimeout(()=>el.remove(),300); }, 3000);
}

// ── Theme ────────────────────────────────────────────────
const html = document.documentElement;
let theme = localStorage.getItem('futures_theme') || 'dark';
html.setAttribute('data-theme', theme);
function toggleTheme() {
  theme = theme === 'dark' ? 'light' : 'dark';
  html.setAttribute('data-theme', theme);
  localStorage.setItem('futures_theme', theme);
  updateThemeUI();
}
function updateThemeUI() {
  const tb = document.getElementById('theme-btn');
  if (tb) tb.textContent = theme === 'dark' ? '☀️' : '🌙';
  const ts = document.getElementById('theme-switch');
  if (ts) ts.checked = theme === 'dark';
}

// ── Auth State ──────────────────────────────────────────
let currentUser = null;
let authTab = 'login';

async function initAuth() {
  const tok = localStorage.getItem('futures_token');
  if (tok) {
    try {
      const user = JSON.parse(localStorage.getItem('futures_user') || '{}');
      currentUser = user;
      return true;
    } catch {}
  }
  // Try supabase session
  const sb = await getSupabase();
  const { data: { session } } = await sb.auth.getSession();
  if (session?.access_token) {
    localStorage.setItem('futures_token', session.access_token);
    localStorage.setItem('futures_user', JSON.stringify(session.user || {}));
    currentUser = session.user;
    return true;
  }
  return false;
}

// ── Routing ──────────────────────────────────────────────
let currentPage = 'dashboard';

function showPage(name) {
  currentPage = name;
  $$('.page-content').forEach(p => p.classList.add('hidden'));
  const el = document.getElementById(`page-${name}`);
  if (el) el.classList.remove('hidden');
  $$('.nav-item').forEach(n => {
    n.classList.toggle('active', n.dataset.page === name);
  });
  if (name === 'dashboard') loadDashboard();
  if (name === 'accountability') loadTrades();
}

function showApp(show) {
  document.getElementById('page-auth').style.display = show ? 'none' : '';
  document.getElementById('app').classList.toggle('app-hidden', !show);
}

// ── Auth Handlers ────────────────────────────────────────
function setupAuth() {
  const tabs = $$('#auth-tabs .pill-tab');
  tabs.forEach(t => t.addEventListener('click', () => {
    tabs.forEach(tt => tt.classList.remove('active'));
    t.classList.add('active');
    authTab = t.dataset.tab;
    const isLogin = authTab === 'login';
    document.getElementById('auth-name-field').classList.toggle('field-hidden', isLogin);
    document.getElementById('auth-confirm-field').classList.toggle('field-hidden', isLogin);
    document.getElementById('auth-agreement').classList.toggle('field-hidden', isLogin);
    document.getElementById('auth-submit').textContent = isLogin ? 'Log In' : 'Create Account';
    document.getElementById('auth-forgot').style.display = isLogin ? '' : 'none';
  }));

  document.getElementById('auth-form').addEventListener('submit', async e => {
    e.preventDefault();
    const email = document.getElementById('auth-email').value.trim();
    const password = document.getElementById('auth-password').value;
    const errEl = document.getElementById('auth-error');
    errEl.style.display = 'none';
    if (!email || !password) { showToast('Please fill in all fields', 'error'); return; }

    const sb = await getSupabase();
    if (authTab === 'login') {
      try {
        const { data, error } = await sb.auth.signInWithPassword({ email, password });
        if (error) throw error;
        localStorage.setItem('futures_token', data.session.access_token);
        localStorage.setItem('futures_user', JSON.stringify(data.session.user || {}));
        currentUser = data.session.user;
        showToast('Welcome back!', 'success');
        afterLogin();
      } catch (e) { showToast(e.message || 'Login failed', 'error'); }
    } else {
      const name = document.getElementById('auth-name').value.trim();
      const confirm = document.getElementById('auth-confirm').value;
      const terms = document.getElementById('auth-terms').checked;
      if (!name) { showToast('Please enter your name', 'error'); return; }
      if (password !== confirm) { showToast('Passwords do not match', 'error'); return; }
      if (!terms) { showToast('You must agree to the Terms & Conditions', 'error'); return; }
      try {
        const { data, error } = await sb.auth.signUp({ email, password });
        if (error) throw error;
        // Save display name
        if (data?.user) {
          try {
            await sb.from('profiles').update({ display_name: name }).eq('id', data.user.id);
          } catch {}
        }
        showToast('Account created! Check your email for verification.', 'success');
        document.getElementById('auth-email').value = '';
        document.getElementById('auth-password').value = '';
        document.getElementById('auth-name').value = '';
        document.getElementById('auth-confirm').value = '';
        document.getElementById('auth-terms').checked = false;
        // Switch to login tab
        $$('#auth-tabs .pill-tab').forEach(t => {
          t.classList.toggle('active', t.dataset.tab === 'login');
        });
        authTab = 'login';
        document.getElementById('auth-name-field').classList.add('field-hidden');
        document.getElementById('auth-confirm-field').classList.add('field-hidden');
        document.getElementById('auth-agreement').classList.add('field-hidden');
        document.getElementById('auth-submit').textContent = 'Log In';
        document.getElementById('auth-forgot').style.display = '';
      } catch (e) { showToast(e.message || 'Sign up failed', 'error'); }
    }
  });

  document.getElementById('auth-google').addEventListener('click', async () => {
    const sb = await getSupabase();
    sb.auth.signInWithOAuth({ provider: 'google' });
  });

  document.getElementById('auth-forgot').addEventListener('click', async () => {
    const email = document.getElementById('auth-email').value.trim();
    if (!email) { showToast('Enter your email address first', 'error'); return; }
    try {
      const sb = await getSupabase();
      await sb.auth.resetPasswordForEmail(email);
      showToast('Password reset email sent!', 'success');
    } catch (e) { showToast(e.message || 'Failed to send reset email', 'error'); }
  });

  document.getElementById('logout-btn').addEventListener('click', () => {
    if (!confirm('Are you sure you want to logout?')) return;
    logout();
  });
}

async function logout() {
  const sb = await getSupabase();
  await sb.auth.signOut();
  localStorage.removeItem('futures_token');
  localStorage.removeItem('futures_user');
  currentUser = null;
  showApp(false);
  document.getElementById('page-auth').style.display = 'flex';
}

async function afterLogin() {
  // Check broker verification
  let brokerVerified = false;
  try {
    const sb = await getSupabase();
    const { data } = await sb.from('profiles').select('broker_verified').eq('id', currentUser?.id).single();
    brokerVerified = data?.broker_verified || false;
  } catch {}
  if (!brokerVerified) {
    showBrokerConnect();
    return;
  }
  showApp(true);
  showPage('dashboard');
}

// ── Splash ──────────────────────────────────────────────
async function runSplash() {
  const splash = document.getElementById('splash');
  const sound = document.getElementById('cashout-sound');
  try { sound.volume = 0.65; sound.play(); } catch {}
  await new Promise(r => setTimeout(r, 2500));
  splash.style.transition = 'opacity .6s';
  splash.style.opacity = '0';
  await new Promise(r => setTimeout(r, 600));
  splash.style.display = 'none';
  const authed = await initAuth();
  if (authed) {
    currentUser = JSON.parse(localStorage.getItem('futures_user') || '{}');
    afterLogin();
  } else {
    showApp(false);
  }
}

// ── Broker Connect ──────────────────────────────────────
let brokerFlowStep = 'intro';
function showBrokerConnect() {
  document.getElementById('page-auth').style.display = 'none';
  const overlay = document.getElementById('modal-overlay');
  const content = document.getElementById('modal-content');
  overlay.classList.remove('hidden');
  renderBrokerFlow();
}
function renderBrokerFlow() {
  const content = document.getElementById('modal-content');
  const overlay = document.getElementById('modal-overlay');
  if (brokerFlowStep === 'intro') {
    content.innerHTML = `
      <div style="text-align:center;margin-bottom:16px"><h2 style="font-size:48px;font-weight:700">FUTURES</h2><p style="font-size:11px;letter-spacing:2.5px;color:var(--text-muted);text-transform:uppercase">ACTIVATE YOUR ACCOUNT</p></div>
      <div class="radio-option" style="margin-bottom:8px"><span style="width:40px;height:40px;border-radius:50%;background:var(--primary);color:var(--primary-fg);display:flex;align-items:center;justify-content:center;font-weight:700;flex-shrink:0">1</span><div><strong>Create HFM Account</strong><p style="font-size:12px;color:var(--text-muted)">Open a free account with our partner broker.</p></div></div>
      <div class="radio-option" style="margin-bottom:8px"><span style="width:40px;height:40px;border-radius:50%;background:var(--warning);color:#fff;display:flex;align-items:center;justify-content:center;font-weight:700;flex-shrink:0">2</span><div><strong>Verify Email & Login</strong><p style="font-size:12px;color:var(--text-muted)">Check your email for the verification link.</p></div></div>
      <div class="radio-option" style="margin-bottom:16px"><span style="width:40px;height:40px;border-radius:50%;background:var(--profit);color:#fff;display:flex;align-items:center;justify-content:center;font-weight:700;flex-shrink:0">3</span><div><strong>Enter MT5 Credentials</strong><p style="font-size:12px;color:var(--text-muted)">Enter your MT5 login to activate the bot.</p></div></div>
      <button class="btn btn-primary" id="bc-register" style="width:100%">Create HFM Account</button>
      <p style="font-size:11px;text-align:center;color:var(--text-muted);margin:8px 0">Already registered?</p>
      <button class="btn btn-outline" id="bc-login" style="width:100%">I Already Have an HFM Account</button>
    `;
    document.getElementById('bc-register').addEventListener('click', () => {
      window.open('https://www.hfm.com/sv/en/?refid=30489955', '_blank');
      brokerFlowStep = 'verify-email';
      renderBrokerFlow();
    });
    document.getElementById('bc-login').addEventListener('click', () => {
      window.open('https://my.hfm.com/login', '_blank');
      brokerFlowStep = 'verify-email';
      renderBrokerFlow();
    });
  } else if (brokerFlowStep === 'verify-email') {
    content.innerHTML = `
      <div style="text-align:center;margin-bottom:16px"><h2 style="font-size:48px;font-weight:700">FUTURES</h2><p style="font-size:11px;letter-spacing:2.5px;color:var(--text-muted);text-transform:uppercase">VERIFY YOUR EMAIL</p></div>
      <div class="radio-option" style="margin-bottom:8px;border-color:var(--primary)"><span style="width:40px;height:40px;border-radius:50%;background:var(--primary);color:var(--primary-fg);display:flex;align-items:center;justify-content:center;font-weight:700;flex-shrink:0">✓</span><div><strong>Registration Submitted</strong><p style="font-size:12px;color:var(--text-muted)">HFM sent a verification email. Check your inbox.</p></div></div>
      <div class="radio-option" style="margin-bottom:16px"><span style="width:40px;height:40px;border-radius:50%;background:var(--warning);color:#fff;display:flex;align-items:center;justify-content:center;font-weight:700;flex-shrink:0">2</span><div><strong>Come Back & Login</strong><p style="font-size:12px;color:var(--text-muted)">After verifying, tap below to login.</p></div></div>
      <button class="btn btn-primary" id="bc-verified" style="width:100%">I've Verified — Enter Credentials</button>
      <button class="btn btn-text" id="bc-back" style="width:100%;margin-top:8px">← Start over</button>
    `;
    document.getElementById('bc-verified').addEventListener('click', () => {
      brokerFlowStep = 'credentials';
      renderBrokerFlow();
    });
    document.getElementById('bc-back').addEventListener('click', () => {
      brokerFlowStep = 'intro';
      renderBrokerFlow();
    });
  } else if (brokerFlowStep === 'credentials') {
    content.innerHTML = `
      <div style="text-align:center;margin-bottom:16px"><h2 style="font-size:48px;font-weight:700">FUTURES</h2><p style="font-size:11px;letter-spacing:2.5px;color:var(--text-muted);text-transform:uppercase">ACTIVATE TRADING BOT</p></div>
      <div style="padding:12px;border-radius:12px;border:1px solid var(--profit);background:rgba(34,197,94,0.1);text-align:center;margin-bottom:16px">
        <p style="color:var(--profit);font-weight:600">✓ HFM Account Verified</p>
        <p style="font-size:12px;color:var(--text-muted)">Enter your MT5 login to activate the trading bot.</p>
      </div>
      <p style="font-size:11px;font-weight:500;color:var(--text-muted);margin-bottom:4px">MT5 Login ID</p>
      <input type="text" id="bc-login-id" class="modal-input" placeholder="e.g. 50123456">
      <p style="font-size:11px;font-weight:500;color:var(--text-muted);margin-bottom:4px">MT5 Password</p>
      <input type="password" id="bc-password" class="modal-input" placeholder="Your MT5 password">
      <p style="font-size:11px;font-weight:500;color:var(--text-muted);margin-bottom:4px">Account Type</p>
      <div class="pill-tabs" style="margin-bottom:16px">
        <button class="pill-tab active" data-bc-type="Demo">Demo</button>
        <button class="pill-tab" data-bc-type="Real">Real</button>
      </div>
      <button class="btn btn-primary" id="bc-activate" style="width:100%">Activate Trading Bot</button>
      <button class="btn btn-text" id="bc-back2" style="width:100%;margin-top:8px">← Start over</button>
      <p id="bc-error" class="error-text hidden"></p>
    `;
    $$('#modal-content .pill-tab').forEach(t => t.addEventListener('click', () => {
      $$('#modal-content .pill-tab').forEach(tt => tt.classList.remove('active'));
      t.classList.add('active');
    }));
    document.getElementById('bc-activate').addEventListener('click', activateBot);
    document.getElementById('bc-back2').addEventListener('click', () => {
      brokerFlowStep = 'intro';
      renderBrokerFlow();
    });
  }
}

async function activateBot() {
  const login = document.getElementById('bc-login-id').value.trim();
  const password = document.getElementById('bc-password').value;
  const type = document.querySelector('#modal-content .pill-tab.active')?.dataset.bcType || 'Demo';
  const errEl = document.getElementById('bc-error');
  if (!login || !password) { errEl.textContent = 'Please enter your MT5 Login ID and Password'; errEl.classList.remove('hidden'); return; }
  errEl.classList.add('hidden');
  const btn = document.getElementById('bc-activate');
  btn.disabled = true; btn.textContent = 'Activating...';
  try {
    const sb = await getSupabase();
    await sb.from('mt5_credentials').upsert({
      user_id: currentUser.id,
      login, password,
      server: `HFM.com ${type} MT5`,
      updated_at: new Date().toISOString(),
    });
    await sb.from('profiles').update({ broker_verified: true, broker_name: 'HFM' }).eq('id', currentUser.id);
    showToast('Verified! Redirecting to dashboard...', 'success');
    document.getElementById('modal-overlay').classList.add('hidden');
    setTimeout(() => { showApp(true); showPage('dashboard'); }, 1500);
  } catch (e) {
    errEl.textContent = e.message || 'Verification failed';
    errEl.classList.remove('hidden');
    btn.disabled = false; btn.textContent = 'Activate Trading Bot';
  }
}

// ── Dashboard ────────────────────────────────────────────
let dashData = { balance:0, equity:0, margin:0, dailyPnl:0, botActive:false, mt5Connected:false, riskPercent:5, mode:'long', trades:[], recentTrades:[], health:'green', cooldown:false, maxDailyTrades:5 };
let tradeCount = 1, riskPercent = 5, accType = 'Demo', botMode = 'long';
let dashInterval = null;

function setupDashboard() {
  document.getElementById('btn-start').addEventListener('click', startBot);
  document.getElementById('btn-stop').addEventListener('click', stopBot);
  document.getElementById('tc-dec').addEventListener('click', () => { tradeCount = Math.max(1, tradeCount-1); updateDashUI(); });
  document.getElementById('tc-inc').addEventListener('click', () => { tradeCount = Math.min(5, tradeCount+1); updateDashUI(); });
  document.getElementById('see-all-trades').addEventListener('click', () => showPage('accountability'));
  $$('#risk-labels button').forEach(b => b.addEventListener('click', () => {
    if (dashData.botActive) return;
    riskPercent = parseInt(b.dataset.risk);
    updateDashUI();
  }));
  $$('.mode-btn').forEach(b => b.addEventListener('click', () => {
    if (dashData.botActive) return;
    $$('.mode-btn').forEach(bb => bb.classList.remove('active'));
    b.classList.add('active');
    botMode = b.dataset.mode;
    document.getElementById('trade-count-row').style.display = botMode === 'long' ? '' : 'none';
    document.getElementById('mode-params').querySelector('.short-term-info')?.remove();
    if (botMode === 'short') {
      const info = document.createElement('div');
      info.className = 'auto-stop-info'; info.style.marginBottom = 'var(--space-sm)';
      info.textContent = 'One trade will be executed, then bot stops. Adjust risk as needed.';
      info.classList.add('short-term-info');
      document.getElementById('mode-params').prepend(info);
    }
    updateDashUI();
  }));
  $$('.type-btn').forEach(b => b.addEventListener('click', async () => {
    const next = b.dataset.type;
    if (next === 'Real' && !confirm('You are about to enable live trading with real funds. Are you sure?')) return;
    try {
      const server = next;
      await api.put('/mt5/credentials', { server });
      accType = next;
      $$('.type-btn').forEach(bb => bb.classList.toggle('active', bb.dataset.type === next));
      showToast(`Account set to ${next}`, 'success');
    } catch (e) { showToast(e.message || 'Failed to update account type', 'error'); }
  }));
  $$('#page-settings .type-btn').forEach(b => b.addEventListener('click', () => {
    $$('#page-settings .type-btn').forEach(bb => bb.classList.remove('active'));
    b.classList.add('active');
  }));
  document.getElementById('support-quick').addEventListener('click', showSupportModal);
  document.getElementById('support-btn').addEventListener('click', showSupportModal);
}

async function loadDashboard() {
  try {
    const [status, dashboard, creds, settings] = await Promise.all([
      api.get('/status'),
      api.get('/dashboard'),
      api.get('/mt5/credentials'),
      api.get('/settings'),
    ]);
    const server = creds.server || '';
    const parts = server.split('-');
    const type = parts[1] === 'Real' ? 'Real' : 'Demo';
    accType = type;
    dashData = {
      ...dashData,
      balance: dashboard.balance || 0,
      equity: dashboard.equity || 0,
      margin: dashboard.margin || 0,
      dailyPnl: dashboard.daily_pnl || 0,
      botActive: status.running || false,
      mt5Connected: status.mt5_connected || false,
      riskPercent: status.risk_percent || riskPercent,
      trades: dashboard.open_trades || [],
      recentTrades: dashboard.recent_trades || [],
      health: status.mt5_connected ? 'green' : 'red',
      cooldown: status.cooldown_active || false,
      maxDailyTrades: settings.max_daily_trades || dashData.maxDailyTrades,
    };
    updateDashUI();
  } catch (e) { console.warn('Dashboard load error:', e); }
}

function updateDashUI() {
  const d = dashData;
  document.getElementById('dash-balance').textContent = `$${d.balance.toLocaleString()}`;
  document.getElementById('dash-equity').textContent = `$${d.equity.toLocaleString()}`;
  document.getElementById('dash-margin').textContent = `$${d.margin.toLocaleString()}`;
  document.getElementById('dash-daily-pnl').textContent = `${d.dailyPnl >= 0 ? '+' : ''}$${d.dailyPnl.toFixed(2)}`;
  document.getElementById('dash-daily-pnl').style.color = d.dailyPnl >= 0 ? 'var(--profit)' : 'var(--loss)';
  document.getElementById('risk-pct').textContent = riskPercent;
  document.getElementById('risk-usd').textContent = `$${(d.balance * riskPercent / 100).toFixed(2)}`;
  document.getElementById('risk-fill').style.width = `${(riskPercent / 10) * 100}%`;
  $$('#risk-labels button').forEach(b => b.classList.toggle('active', parseInt(b.dataset.risk) === riskPercent));

  // Daily limit
  const used = d.trades.length;
  const limit = d.maxDailyTrades || 5;
  const pct = Math.min(100, (used / limit) * 100);
  document.getElementById('dash-trade-count').textContent = `∞ | ${used} / ${limit}`;
  document.getElementById('dash-limit-fill').style.width = `${pct}%`;

  // Health
  const hd = document.getElementById('health-dot');
  hd.className = `health-dot ${d.health}`;
  document.getElementById('dash-health-text').textContent = d.botActive ? 'Bot Running' : d.mt5Connected ? 'Bot Active' : 'MT5 Disconnected';

  // Buttons
  document.getElementById('btn-start').disabled = d.botActive || d.cooldown;
  document.getElementById('btn-stop').disabled = !d.botActive;
  document.getElementById('auto-stop-info').classList.toggle('hidden', !d.botActive);

  // Mode selector sync
  $$('.mode-btn').forEach(b => b.classList.toggle('active', b.dataset.mode === botMode));
  document.getElementById('trade-count-row').style.display = botMode === 'long' ? '' : 'none';

  // Recent trades
  const container = document.getElementById('recent-trades');
  let html = '<div class="trade-header"><span>Pair</span><span>Type</span><span>P&L</span><span>Time</span></div>';
  if (d.recentTrades.length === 0) {
    html += '<div class="empty-state">No trades yet</div>';
  } else {
    d.recentTrades.slice(0, 5).forEach(t => {
      const pnl = t.profit || 0;
      html += `<div class="trade-row"><span>${t.pair || '-'}</span><span>${t.direction || '-'}</span><span style="color:${pnl >= 0 ? 'var(--profit)' : 'var(--loss)'};font-weight:600">${pnl >= 0 ? '+' : ''}$${pnl.toFixed(2)}</span><span style="color:var(--text-muted)">${t.close_time ? t.close_time.slice(11,16) : '-'}</span></div>`;
    });
  }
  container.innerHTML = html;

  // Cooldown
  document.getElementById('cooldown-banner').classList.toggle('hidden', !d.cooldown);
  document.getElementById('tc-value').textContent = tradeCount;
}

async function startBot() {
  try {
    await api.post('/user/start', { mode: botMode, trade_count: tradeCount, risk_percent: riskPercent });
    dashData.botActive = true;
    updateDashUI();
    showToast('Bot started', 'success');
  } catch (e) { showToast(e.message || 'Failed to start bot', 'error'); }
}
async function stopBot() {
  try {
    await api.post('/user/stop');
    dashData.botActive = false;
    updateDashUI();
    showToast('Bot stopped', 'success');
  } catch (e) { showToast(e.message || 'Failed to stop bot', 'error'); }
}

// ── Accountability ──────────────────────────────────────
let tradesData = [];
let tradeRange = '30';

function setupAccountability() {
  $$('#range-row .range-btn').forEach(b => b.addEventListener('click', () => {
    $$('#range-row .range-btn').forEach(bb => bb.classList.remove('active'));
    b.classList.add('active');
    tradeRange = b.dataset.range;
    renderTrades();
  }));
  $$('.export-btn').forEach(b => b.addEventListener('click', () => {
    if (b.dataset.format === 'csv') exportCSV();
    else showToast('PDF export coming soon', 'info');
  }));
}

async function loadTrades() {
  try {
    const data = await api.get('/trades');
    tradesData = data.trades || [];
  } catch {
    tradesData = [
      { pair:'GBPUSD', direction:'BUY', lots:0.05, entry_price:1.2750, close_price:1.2815, pnl:12.30, opened_at:'2026-05-06T14:32:00', closed_at:'2026-05-06T15:10:00', status:'CLOSED' },
      { pair:'GBPJPY', direction:'SELL', lots:0.02, entry_price:186.50, close_price:186.10, pnl:-5.20, opened_at:'2026-05-06T13:15:00', closed_at:'2026-05-06T13:45:00', status:'CLOSED' },
      { pair:'GBPUSD', direction:'BUY', lots:0.08, entry_price:1.2680, close_price:1.2720, pnl:8.40, opened_at:'2026-05-06T11:07:00', closed_at:'2026-05-06T11:55:00', status:'CLOSED' },
      { pair:'GBPJPY', direction:'BUY', lots:0.04, entry_price:185.20, close_price:185.50, pnl:2.10, opened_at:'2026-05-05T09:45:00', closed_at:'2026-05-05T10:20:00', status:'CLOSED' },
      { pair:'GBPUSD', direction:'SELL', lots:0.06, entry_price:1.2710, close_price:1.2650, pnl:15.00, opened_at:'2026-05-04T16:20:00', closed_at:'2026-05-04T17:05:00', status:'CLOSED' },
      { pair:'GBPJPY', direction:'SELL', lots:0.03, entry_price:187.00, close_price:187.45, pnl:-8.50, opened_at:'2026-05-04T10:30:00', closed_at:'2026-05-04T11:00:00', status:'CLOSED' },
    ];
  }
  renderTrades();
}

function renderTrades() {
  const filtered = tradesData.filter(t => {
    if (tradeRange === 'all') return true;
    const days = parseInt(tradeRange);
    const tradeDate = new Date(t.opened_at);
    const cutoff = new Date();
    cutoff.setDate(cutoff.getDate() - days);
    return tradeDate >= cutoff;
  });
  const closed = filtered.filter(t => t.status === 'CLOSED');
  const won = closed.filter(t => (t.pnl || 0) > 0);
  const totalPnl = closed.reduce((s, t) => s + (t.pnl || 0), 0);
  const winRate = closed.length > 0 ? Math.round((won.length / closed.length) * 100) : 0;

  document.getElementById('acct-total').textContent = tradesData.length;
  document.getElementById('acct-winrate').textContent = `${winRate}%`;
  document.getElementById('acct-pnl').textContent = `${totalPnl >= 0 ? '+' : ''}$${totalPnl.toFixed(0)}`;
  document.getElementById('acct-pnl').style.color = totalPnl >= 0 ? 'var(--profit)' : 'var(--loss)';

  const table = document.getElementById('trades-table');
  let html = '<div class="table-header"><span>Pair</span><span>Type</span><span>Lots</span><span>Entry</span><span>Exit</span><span>P&L</span><span>Time</span></div>';
  if (filtered.length === 0) {
    html += '<div class="empty-state" id="trades-empty">No trades found</div>';
  } else {
    filtered.forEach(t => {
      const pnl = t.pnl || 0;
      const isJpy = (t.pair || '').includes('JPY');
      const entry = t.entry_price ? t.entry_price.toFixed(isJpy ? 2 : 5) : '-';
      const exit = t.close_price != null ? t.close_price.toFixed(isJpy ? 2 : 5) : '-';
      const time = t.closed_at ? fmtTime(t.closed_at) : fmtTime(t.opened_at);
      html += `<div class="trade-row"><span>${t.pair}</span><span><span class="type-badge ${(t.direction||'').toLowerCase()}">${t.direction}</span></span><span>${t.lots.toFixed(2)}</span><span>${entry}</span><span>${exit}</span><span style="color:${pnl >= 0 ? 'var(--profit)' : 'var(--loss)'};font-weight:600">${pnl >= 0 ? '+' : ''}$${pnl.toFixed(2)}</span><span style="color:var(--text-muted)">${time}</span></div>`;
    });
  }
  table.innerHTML = html;
}
function fmtTime(iso) {
  const d = new Date(iso);
  return `${d.toLocaleDateString('en-US',{month:'short',day:'numeric'})}, ${d.toLocaleTimeString('en-US',{hour:'2-digit',minute:'2-digit',hour12:false})}`;
}
function exportCSV() {
  const filtered = tradesData.filter(t => {
    if (tradeRange === 'all') return true;
    const days = parseInt(tradeRange);
    const d = new Date(t.opened_at);
    const cutoff = new Date(); cutoff.setDate(cutoff.getDate() - days);
    return d >= cutoff;
  });
  if (!filtered.length) { showToast('No trades to export', 'error'); return; }
  const header = 'Pair,Type,Lots,Entry,Exit,P&L,Time\n';
  const rows = filtered.map(t => `${t.pair},${t.direction},${t.lots},${t.entry_price},${t.close_price || ''},${t.pnl || ''},${t.opened_at}`).join('\n');
  const blob = new Blob([header + rows], { type:'text/csv' });
  const url = URL.createObjectURL(blob);
  const a = document.createElement('a');
  a.href = url; a.download = `trades_${tradeRange}d.csv`; a.click();
  URL.revokeObjectURL(url);
  showToast('CSV exported', 'success');
}

// ── Copilot ──────────────────────────────────────────────
let copilotMessages = [];
let copilotPendingConfirm = null;
let copilotLoading = false;

const SUGGESTIONS = [
  { label:'Balance', action:'What is my account balance?' },
  { label:'Trades', action:'Show my open trades' },
  { label:'Last trade', action:'Explain the last trade' },
  { label:'News', action:'Any news affecting the market?' },
  { label:'Chart', action:'Generate a chart for GBPUSD' },
  { label:'Stop', action:'Stop the bot now' },
  { label:'Clear', action:'clear' },
];

function setupCopilot() {
  document.getElementById('chat-send').addEventListener('click', () => sendMessage(document.getElementById('chat-input').value));
  document.getElementById('chat-input').addEventListener('keydown', e => {
    if (e.key === 'Enter') sendMessage(e.target.value);
  });
  document.getElementById('confirm-btn').addEventListener('click', confirmAction);
  $$('.chip').forEach(c => c.addEventListener('click', () => {
    const action = c.dataset.action;
    if (action === 'clear') {
      copilotMessages = [];
      document.getElementById('chat-area').innerHTML = '<div class="chat-msg bot">Chat cleared. How can I help?</div>';
      return;
    }
    sendMessage(action);
  }));
}

async function sendMessage(text) {
  if (!text.trim() || copilotLoading) return;
  document.getElementById('chat-input').value = '';
  copilotMessages.push({ role:'user', text });
  appendMessage('user', text);
  copilotLoading = true;
  copilotPendingConfirm = null;
  document.getElementById('confirm-row').classList.add('hidden');
  showTyping();
  try {
    const res = await api.post('/copilot/chat', { message: text });
    if (res.reply) {
      copilotMessages.push({ role:'bot', text: res.reply, imageUrl: res.image_url });
      appendMessage('bot', res.reply, res.image_url);
    }
    if (res.requires_confirmation && res.confirmation_id) {
      copilotPendingConfirm = res.confirmation_id;
      document.getElementById('confirm-row').classList.remove('hidden');
    }
  } catch (e) {
    appendMessage('bot', `Error: ${e.message}`);
  } finally {
    copilotLoading = false;
    hideTyping();
  }
}

async function confirmAction() {
  if (!copilotPendingConfirm) return;
  copilotLoading = true;
  try {
    const res = await api.post('/copilot/confirm', { confirmation_id: copilotPendingConfirm });
    appendMessage('bot', res.reply);
    copilotPendingConfirm = null;
    document.getElementById('confirm-row').classList.add('hidden');
  } catch (e) { showToast(e.message, 'error'); }
  finally { copilotLoading = false; }
}

function appendMessage(role, text, imageUrl) {
  const area = document.getElementById('chat-area');
  const div = document.createElement('div');
  div.className = `chat-msg ${role}`;
  div.textContent = text;
  if (imageUrl) {
    const img = document.createElement('img');
    img.src = imageUrl;
    img.alt = 'Chart';
    div.appendChild(img);
  }
  area.appendChild(div);
  area.scrollTop = area.scrollHeight;
}

function showTyping() {
  const area = document.getElementById('chat-area');
  const dots = document.createElement('div');
  dots.className = 'typing-dots';
  dots.id = 'typing-indicator';
  dots.innerHTML = '<span></span><span></span><span></span>';
  area.appendChild(dots);
  area.scrollTop = area.scrollHeight;
}
function hideTyping() {
  const el = document.getElementById('typing-indicator');
  if (el) el.remove();
}

// ── Settings ─────────────────────────────────────────────
let settingsData = { riskPercent:5, maxDailyTrades:5, bePolicy:'auto', dryRun:false, autoCompounding:false, notifications:{}, displayName:'Trader' };
let mt5Data = { login:null, server:'', connected:false, broker:'HFM', accountType:'Demo' };
let saveTimer = null;

function setupSettings() {
  document.getElementById('show-pw-modal').addEventListener('click', () => showModal('change-password'));
  $$('.edit-name').forEach(b => b.addEventListener('click', () => showModal('edit-name')));
  document.getElementById('test-mt5').addEventListener('click', testMT5);
  document.getElementById('theme-switch').addEventListener('change', toggleTheme);
  document.getElementById('export-csv').addEventListener('click', () => {
    showPage('accountability');
    setTimeout(() => exportCSV(), 100);
  });
  document.getElementById('clear-cache').addEventListener('click', () => showToast('Chat cache cleared', 'success'));

  // Risk slider
  $$('#set-risk-labels button').forEach(b => b.addEventListener('click', () => {
    settingsData.riskPercent = parseInt(b.dataset.risk);
    updateSettingsUI();
    queueSave();
  }));

  // Stepper
  document.getElementById('mdt-dec').addEventListener('click', () => {
    settingsData.maxDailyTrades = Math.max(1, settingsData.maxDailyTrades - 1);
    updateSettingsUI(); queueSave();
  });
  document.getElementById('mdt-inc').addEventListener('click', () => {
    settingsData.maxDailyTrades = Math.min(25, settingsData.maxDailyTrades + 1);
    updateSettingsUI(); queueSave();
  });

  // Radio groups
  $$('#be-group input').forEach(r => r.addEventListener('change', () => {
    if (r.checked) { settingsData.bePolicy = r.value; queueSave(); }
  }));
  $$('#broker-group input').forEach(r => r.addEventListener('change', () => {
    if (r.checked) { mt5Data.broker = r.value; updateSettingsUI(); }
  }));
  $$('#acct-type-group input').forEach(r => r.addEventListener('change', () => {
    if (r.checked) { mt5Data.accountType = r.value; updateSettingsUI(); }
  }));

  // Toggles
  document.getElementById('set-compound').addEventListener('change', function() {
    settingsData.autoCompounding = this.checked;
    document.getElementById('compound-warning').classList.toggle('hidden', !this.checked);
    queueSave();
  });
  document.getElementById('set-dryrun').addEventListener('change', function() {
    settingsData.dryRun = this.checked; queueSave();
  });

  // Load settings
  loadSettings();
}

async function loadSettings() {
  try {
    const data = await api.get('/settings');
    settingsData.riskPercent = data.risk_percent ?? 5;
    settingsData.maxDailyTrades = data.max_daily_trades ?? 5;
    if (['auto','notify','none'].includes(data.be_policy)) settingsData.bePolicy = data.be_policy;
    settingsData.dryRun = data.dry_run ?? false;
    settingsData.autoCompounding = data.auto_compounding ?? false;
    settingsData.displayName = data.display_name || 'Trader';
    if (data.notifications) settingsData.notifications = { ...settingsData.notifications, ...data.notifications };
    updateSettingsUI();
  } catch {}
  try {
    const data = await api.get('/mt5/credentials');
    mt5Data.login = data.login;
    mt5Data.server = data.server || '';
    mt5Data.connected = data.connected || false;
    const parts = (data.server || '').split('-');
    if (['HFM','Exness'].includes(parts[0])) mt5Data.broker = parts[0];
    if (['Demo','Live','Real'].includes(parts[1])) mt5Data.accountType = parts[1];
    updateSettingsUI();
  } catch {}
}

function updateSettingsUI() {
  document.getElementById('set-name').textContent = settingsData.displayName;
  document.getElementById('set-risk-pct').textContent = settingsData.riskPercent;
  document.getElementById('set-risk-fill').style.width = `${(settingsData.riskPercent / 10) * 100}%`;
  $$('#set-risk-labels button').forEach(b => b.classList.toggle('active', parseInt(b.dataset.risk) === settingsData.riskPercent));
  document.getElementById('mdt-value').textContent = settingsData.maxDailyTrades;
  document.getElementById('set-compound').checked = settingsData.autoCompounding;
  document.getElementById('compound-warning').classList.toggle('hidden', !settingsData.autoCompounding);
  document.getElementById('set-dryrun').checked = settingsData.dryRun;

  const beRadio = document.querySelector(`#be-group input[value="${settingsData.bePolicy}"]`);
  if (beRadio) beRadio.checked = true;

  const brokerRadio = document.querySelector(`#broker-group input[value="${mt5Data.broker}"]`);
  if (brokerRadio) brokerRadio.checked = true;
  const acctRadio = document.querySelector(`#acct-type-group input[value="${mt5Data.accountType}"]`);
  if (acctRadio) acctRadio.checked = true;

  document.getElementById('mt5-login').textContent = mt5Data.login ? `Account ${mt5Data.login}` : 'Not configured';
  document.getElementById('mt5-server').textContent = `${mt5Data.broker}-${mt5Data.accountType}`;
  document.getElementById('mt5-status').textContent = mt5Data.connected ? '✅ Connected' : mt5Data.server ? '⚠️ Not connected' : '⚪ Not configured';

  // Notifications
  const notifList = document.getElementById('notif-list');
  const cats = [
    { key:'trade_execution', label:'Trade Execution' },
    { key:'trade_closed', label:'Trade Closed' },
    { key:'daily_summary', label:'Daily Summary' },
    { key:'loss_cooldown', label:'Loss Cooldown' },
    { key:'maintenance', label:'Maintenance' },
    { key:'package_expiry', label:'Package Expiry' },
    { key:'email_trade', label:'Email Notifications' },
  ];
  notifList.innerHTML = cats.map(c => {
    const checked = settingsData.notifications[c.key] !== false;
    return `<div class="setting-row"><span>${c.label}</span><label class="toggle"><input type="checkbox" class="notif-cb" data-key="${c.key}" ${checked ? 'checked' : ''}><span class="slider"></span></label></div>`;
  }).join('');
  $$('.notif-cb').forEach(cb => cb.addEventListener('change', function() {
    settingsData.notifications[this.dataset.key] = this.checked;
    queueSave();
  }));

  document.getElementById('theme-switch').checked = theme === 'dark';
}

function queueSave() {
  clearTimeout(saveTimer);
  saveTimer = setTimeout(async () => {
    try {
      await api.post('/settings', {
        risk_percent: settingsData.riskPercent,
        max_daily_trades: settingsData.maxDailyTrades,
        be_policy: settingsData.bePolicy,
        dry_run: settingsData.dryRun,
        auto_compounding: settingsData.autoCompounding,
        display_name: settingsData.displayName,
        notifications: settingsData.notifications,
      });
    } catch {}
  }, 500);
}

async function testMT5() {
  if (!mt5Data.login) { showToast('Set up MT5 credentials first', 'error'); return; }
  const btn = document.getElementById('test-mt5');
  btn.disabled = true; btn.textContent = 'Testing...';
  try {
    const server = `${mt5Data.broker}-${mt5Data.accountType}`;
    await api.put('/mt5/credentials', { server });
    mt5Data.server = server;
    const data = await api.post('/mt5/connect', { login: mt5Data.login, password: '', server });
    if (data.status === 'connected_ea_ready') {
      mt5Data.connected = true;
      showToast('✅ Connected — EA Ready', 'success');
    } else if (data.status === 'connected_no_ea') {
      mt5Data.connected = true;
      showToast('⚠️ Connected — Enable Automated Trading in MT5', 'info');
    } else {
      showToast('❌ ' + (data.error || 'Connection failed'), 'error');
    }
  } catch (e) { showToast(e.message || 'Connection test failed', 'error'); }
  finally { btn.disabled = false; btn.textContent = 'Test Connection'; updateSettingsUI(); }
}

// ── Modals ──────────────────────────────────────────────
function showModal(type) {
  const overlay = document.getElementById('modal-overlay');
  const content = document.getElementById('modal-content');
  overlay.classList.remove('hidden');
  if (type === 'edit-name') {
    content.innerHTML = `
      <div class="modal-header"><h2>Edit Display Name</h2><button class="modal-close" id="modal-close">×</button></div>
      <input type="text" id="modal-name-input" class="modal-input" value="${settingsData.displayName}" placeholder="Enter new name" autofocus>
      <button class="btn btn-primary" id="modal-name-save" style="width:100%">Save Changes</button>
    `;
    document.getElementById('modal-close').addEventListener('click', () => overlay.classList.add('hidden'));
    document.getElementById('modal-name-save').addEventListener('click', () => {
      const name = document.getElementById('modal-name-input').value.trim();
      if (!name) { showToast('Name cannot be empty', 'error'); return; }
      settingsData.displayName = name;
      updateSettingsUI(); queueSave();
      overlay.classList.add('hidden');
      showToast('Name updated', 'success');
    });
  } else if (type === 'change-password') {
    content.innerHTML = `
      <div class="modal-header"><h2>Change Password</h2><button class="modal-close" id="modal-close">×</button></div>
      <input type="password" id="modal-cur-pw" class="modal-input" placeholder="Current password" autofocus>
      <input type="password" id="modal-new-pw" class="modal-input" placeholder="New password">
      <input type="password" id="modal-confirm-pw" class="modal-input" placeholder="Confirm new password">
      <button class="btn btn-primary" id="modal-pw-save" style="width:100%">Update Password</button>
    `;
    document.getElementById('modal-close').addEventListener('click', () => overlay.classList.add('hidden'));
    document.getElementById('modal-pw-save').addEventListener('click', async () => {
      const cur = document.getElementById('modal-cur-pw').value;
      const npw = document.getElementById('modal-new-pw').value;
      const cnf = document.getElementById('modal-confirm-pw').value;
      if (!cur || !npw || !cnf) { showToast('Fill all fields', 'error'); return; }
      if (npw !== cnf) { showToast('Passwords do not match', 'error'); return; }
      if (npw.length < 6) { showToast('Password must be at least 6 characters', 'error'); return; }
      const btn = document.getElementById('modal-pw-save');
      btn.disabled = true; btn.textContent = 'Updating...';
      try {
        const sb = await getSupabase();
        const { error: signInError } = await sb.auth.signInWithPassword({
          email: currentUser?.email || '',
          password: cur,
        });
        if (signInError) { showToast('Current password is incorrect', 'error'); btn.disabled = false; btn.textContent = 'Update Password'; return; }
        await sb.auth.updateUser({ password: npw });
        showToast('Password updated', 'success');
        overlay.classList.add('hidden');
      } catch (e) { showToast(e.message || 'Failed to change password', 'error'); }
      finally { btn.disabled = false; btn.textContent = 'Update Password'; }
    });
  } else if (type === 'support') {
    content.innerHTML = `
      <div class="modal-header"><h2>Support</h2><button class="modal-close" id="modal-close">×</button></div>
      <p style="color:var(--text-muted);font-size:var(--font-sm);margin-bottom:16px">Need help? Send us a message and we'll get back to you.</p>
      <input type="text" id="support-subject" class="modal-input" placeholder="Subject">
      <textarea id="support-body" class="modal-input" style="height:120px;padding:12px;resize:none" placeholder="Describe your issue..."></textarea>
      <button class="btn btn-primary" id="support-send" style="width:100%">Send</button>
    `;
    document.getElementById('modal-close').addEventListener('click', () => overlay.classList.add('hidden'));
    document.getElementById('support-send').addEventListener('click', async () => {
      const subject = document.getElementById('support-subject').value.trim();
      const body = document.getElementById('support-body').value.trim();
      if (!subject || !body) { showToast('Please fill in all fields', 'error'); return; }
      try {
        await api.post('/support/tickets', { subject, body });
        showToast('Ticket submitted!', 'success');
        overlay.classList.add('hidden');
      } catch (e) { showToast(e.message || 'Failed to submit ticket', 'error'); }
    });
  }
  overlay.addEventListener('click', e => { if (e.target === overlay) overlay.classList.add('hidden'); });
}

function showSupportModal() {
  showModal('support');
}

// ── Navigation ──────────────────────────────────────────
function setupNavigation() {
  $$('.nav-item').forEach(n => n.addEventListener('click', () => showPage(n.dataset.page)));
  document.getElementById('theme-btn').addEventListener('click', toggleTheme);
}

// ── Init ─────────────────────────────────────────────────
async function init() {
  updateThemeUI();
  setupAuth();
  setupDashboard();
  setupAccountability();
  setupCopilot();
  setupSettings();
  setupNavigation();
  await runSplash();
}

document.addEventListener('DOMContentLoaded', init);

// ── Supabase CDN fallback ───────────────────────────────
if (!window.__SUPABASE__) {
  const script = document.createElement('script');
  script.src = 'https://cdn.jsdelivr.net/npm/@supabase/supabase-js@2';
  script.onload = () => {
    window.__SUPABASE__ = window.supabase;
  };
  document.head.appendChild(script);
}

})();
