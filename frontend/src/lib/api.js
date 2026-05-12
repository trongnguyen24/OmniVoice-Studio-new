const API_BASE = 'http://127.0.0.1:3900';

async function request(path, options = {}) {
  const response = await fetch(`${API_BASE}${path}`, {
    headers: {
      Accept: 'application/json',
      ...(options.body instanceof FormData ? {} : { 'Content-Type': 'application/json' }),
      ...options.headers,
    },
    ...options,
  });

  if (!response.ok) {
    let detail = response.statusText;
    try {
      const payload = await response.json();
      detail = payload.detail || detail;
    } catch {
      // Keep the status text when the response is not JSON.
    }
    throw new Error(detail);
  }

  return response.json();
}

export function getSystemInfo() {
  return request('/system/info');
}

export function getModelStatus() {
  return request('/model/status');
}

export function getEngines() {
  return request('/api/ext/engines');
}

export function selectEngine(engine) {
  return request('/api/ext/engines/select', {
    method: 'POST',
    body: JSON.stringify({ engine }),
  });
}

export function preloadEngine(engine) {
  return request(`/api/ext/engines/${engine}/preload`, { method: 'POST' });
}

export function unloadEngine(engine) {
  return request(`/api/ext/engines/${engine}/unload`, { method: 'POST' });
}

export async function generateTts(payload) {
  const response = await fetch(`${API_BASE}/api/ext/generate`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(payload),
  });

  if (!response.ok) {
    let detail = response.statusText;
    try {
      const errorPayload = await response.json();
      detail = errorPayload.detail || detail;
    } catch {
      // The endpoint normally returns JSON errors, but keep a safe fallback.
    }
    throw new Error(detail);
  }

  return {
    blob: await response.blob(),
    engine: response.headers.get('X-TTS-Engine') || payload.engine,
    genTime: response.headers.get('X-Gen-Time'),
    duration: response.headers.get('X-Audio-Duration'),
    audioId: response.headers.get('X-Audio-Id'),
  };
}
