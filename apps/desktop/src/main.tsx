import React from 'react';
import ReactDOM from 'react-dom/client';
import App from './App';
import './index.css';

// ── API token bootstrap (security hardening) ─────────────────────────────────
// The backend requires X-Johnny-Token on all /api/v1/* endpoints except
// /health and the bootstrap endpoint itself. This wrapper transparently
// obtains the token once (from the origin-checked bootstrap endpoint) and
// attaches it to every fetch. Tauri/Vite origins are the only callers allowed
// to bootstrap, so a webpage in the user's browser can never read the token.
let _tokenPromise: Promise<string | null> | null = null;

function getApiToken(): Promise<string | null> {
  if (!_tokenPromise) {
    _tokenPromise = window.__origFetch('http://127.0.0.1:8000/api/v1/auth/token') // bypass wrapper (no recursion)
      .then((res) => (res.ok ? res.json() : null))
      .then((data) => (data?.token as string) ?? null)
      .catch(() => null);
  }
  return _tokenPromise;
}

declare global {
  interface Window {
    __origFetch: typeof window.fetch;
  }
}

window.__origFetch = window.fetch.bind(window);

window.fetch = (async (input: RequestInfo | URL, init?: RequestInit) => {
  const urlStr = typeof input === 'string' ? input : input instanceof URL ? input.href : input.url;
  if (!urlStr.includes('/api/v1')) return window.__origFetch(input, init);
  // Merge token header into existing headers (avoid clobbering Content-Type)
  const existingHeaders = new Headers(init?.headers || (typeof input !== 'string' && !(input instanceof URL) ? input.headers : undefined));
  if (!existingHeaders.has('X-Johnny-Token')) {
    const token = await getApiToken();
    if (token) existingHeaders.set('X-Johnny-Token', token);
  }
  return window.__origFetch(input, { ...init, headers: existingHeaders });
}) as typeof window.fetch;

ReactDOM.createRoot(document.getElementById('root') as HTMLElement).render(
  <React.StrictMode>
    <App />
  </React.StrictMode>
);
