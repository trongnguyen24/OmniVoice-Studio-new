<script>
  import { onMount } from 'svelte';
  import { getTauriApi } from '../lib/tauri.js';

  let { onReady } = $props();

  let stage = $state('checking');
  let message = $state('Checking local runtime...');
  let logs = $state([]);
  let progress = $state(null);
  let retrying = $state(false);
  let tauriApi = $state(null);
  let logPanel;

  const ready = $derived(stage === 'ready' || stage === 'running' || stage === 'done');
  const failed = $derived(stage === 'error' || stage === 'failed');

  function appendLog(line) {
    if (!line) return;
    logs = [...logs, String(line)].slice(-200);
    queueMicrotask(() => {
      if (logPanel) logPanel.scrollTop = logPanel.scrollHeight;
    });
  }

  async function retry(clean = false) {
    if (!tauriApi) return;
    retrying = true;
    try {
      await tauriApi.invoke(clean ? 'clean_and_retry_bootstrap' : 'retry_bootstrap');
    } finally {
      retrying = false;
    }
  }

  onMount(async () => {
    const api = await getTauriApi();
    tauriApi = api;

    if (!api) {
      stage = 'ready';
      message = 'Running in browser dev mode.';
      onReady?.();
      return;
    }

    const syncStatus = async () => {
      const current = await api.invoke('bootstrap_status');
      stage = current.stage;
      message = current.message ?? '';
      if (current.stage === 'ready' || current.stage === 'running' || current.stage === 'done') {
        onReady?.();
      }
    };

    await syncStatus().catch((error) => appendLog(error.message));

    const buffered = await api.invoke('get_bootstrap_logs').catch(() => []);
    if (Array.isArray(buffered)) logs = buffered.slice(-200);

    const unlistenLog = await api.listen('bootstrap-log', (event) => appendLog(event.payload));
    const unlistenProgress = await api.listen('bootstrap-progress', (event) => {
      progress = event.payload;
    });

    const interval = setInterval(() => {
      syncStatus().catch((error) => appendLog(error.message));
    }, 1000);

    return () => {
      clearInterval(interval);
      unlistenLog();
      unlistenProgress();
    };
  });
</script>

<section class="bootstrap-card">
  <div>
    <p class="eyebrow">Runtime bootstrap</p>
    <h1>Local OmniVoice Server</h1>
    <p class="muted">{message}</p>
  </div>

  <div class:ok={ready} class:error={failed} class="stage-pill">{stage}</div>

  {#if progress}
    <div class="progress-wrap">
      <div class="progress-label">
        <span>{progress.label ?? 'Installing runtime'}</span>
        <span>{progress.percent ?? 0}%</span>
      </div>
      <div class="progress-track">
        <div class="progress-bar" style={`width:${Math.max(0, Math.min(100, progress.percent ?? 0))}%`}></div>
      </div>
    </div>
  {/if}

  <div bind:this={logPanel} class="log-panel">
    {#if logs.length === 0}
      <span class="muted">No bootstrap logs yet.</span>
    {:else}
      {#each logs as line}
        <div>{line}</div>
      {/each}
    {/if}
  </div>

  {#if failed}
    <div class="actions">
      <button disabled={retrying} onclick={() => retry(false)}>Retry</button>
      <button disabled={retrying} class="secondary" onclick={() => retry(true)}>Clean and retry</button>
    </div>
  {/if}
</section>
