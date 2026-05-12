<script>
  import { compact } from '../lib/format.js';
  let { systemInfo, modelStatus, online } = $props();
</script>

<section class="panel hero-panel">
  <div>
    <p class="eyebrow">Server status</p>
    <h1>Browser Extension TTS Gateway</h1>
    <p class="muted">Local FastAPI endpoint for generating WAV audio from extension requests.</p>
  </div>
  <div class="status-grid">
    <div class="metric">
      <span>Backend</span>
      <strong class:good={online} class:bad={!online}>{online ? 'Online' : 'Offline'}</strong>
    </div>
    <div class="metric">
      <span>Device</span>
      <strong>{compact(systemInfo?.device)}</strong>
    </div>
    <div class="metric">
      <span>Model</span>
      <strong>{compact(modelStatus?.status, 'idle')}</strong>
    </div>
    <div class="metric">
      <span>Data dir</span>
      <strong title={systemInfo?.data_dir}>{compact(systemInfo?.data_dir)}</strong>
    </div>
  </div>
</section>
