// Shared helpers for all MVP pages.
(function () {
  const TOKEN_KEY = 'access_token';
  const USER_KEY = 'user_info';

  window.App = {
    getToken() { return localStorage.getItem(TOKEN_KEY); },
    getUser() {
      const raw = localStorage.getItem(USER_KEY);
      return raw ? JSON.parse(raw) : null;
    },
    logout() {
      localStorage.removeItem(TOKEN_KEY);
      localStorage.removeItem(USER_KEY);
      document.cookie = 'access_token=; Path=/; Max-Age=0';
      window.location.href = '/static/login.html';
    },

    /** fetch wrapper: 自动附 Authorization、处理 401。 */
    async api(path, options = {}) {
      const token = this.getToken();
      const headers = Object.assign(
        { 'Content-Type': 'application/json' },
        options.headers || {}
      );
      if (token) headers['Authorization'] = 'Bearer ' + token;
      if (options.body && typeof options.body === 'object' && !(options.body instanceof FormData)) {
        options.body = JSON.stringify(options.body);
      }
      if (options.body instanceof FormData) {
        delete headers['Content-Type'];  // let browser set multipart boundary
      }

      const res = await fetch(path, Object.assign({}, options, { headers }));
      if (res.status === 401) {
        this.logout();
        throw new Error('会话已过期，请重新登录');
      }
      if (!res.ok) {
        let msg = 'HTTP ' + res.status;
        try {
          const body = await res.json();
          msg = body.detail || JSON.stringify(body);
        } catch {}
        throw new Error(msg);
      }
      const ct = res.headers.get('content-type') || '';
      return ct.includes('application/json') ? res.json() : res.text();
    },

    /** Enforce that only tenant_type in `allowed` sees the page; else logout. */
    requireTenantType(...allowed) {
      const u = this.getUser();
      if (!u || !allowed.includes(u.tenant_type)) {
        this.logout();
      }
      return u;
    },

    esc(s) {
      if (s == null) return '';
      return String(s).replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;').replace(/"/g, '&quot;');
    },

    fmtDate(iso) {
      if (!iso) return '—';
      try { return new Date(iso).toLocaleString('zh-CN'); } catch { return iso; }
    },
  };
})();
