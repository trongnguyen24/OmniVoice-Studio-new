<script>
  import { getTauriApi } from '../lib/tauri.js';

  let logs = $state([]);
  let path = $state('');
  let loading = $state(false);

  async function loadLogs() {
    loading = true;
    try {
      const api = await getTauriApi();
      if (api) {
        const payload = await api.invoke('read_log_tail', { source: 'backend', tail: 200 });
        logs = payload.lines ?? [];
        path = payload.path ?? '';
      } else {
        const response = await fetch('http://127.0.0.1:3900/system/logs?tail=200');
        const payload = await response.json();
        logs = payload.lines ?? [];
        path = payload.path ?? '';
      }
    } finally {
      loading = false;
    }
  }
</script>

<section class="panel logs-panel">
  <div class="panel-head">
    <div>
      <p class="eyebrow">Diagnostics</p>
      <h2>Backend Logs</h2>
    </div>
    <button class="secondary" onclick={loadLogs} disabled={loading}>{loading ? 'Loading...' : 'Refresh'}</button>
  </div>
  <small>{path}</small>
  <pre>{logs.length ? logs.join('') : 'No logs loaded.'}</pre>
</section>
