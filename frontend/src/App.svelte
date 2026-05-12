<script>
  import { onMount } from 'svelte';
  import BootstrapSplash from './components/BootstrapSplash.svelte';
  import EngineSelector from './components/EngineSelector.svelte';
  import ExtensionGuide from './components/ExtensionGuide.svelte';
  import LogsPanel from './components/LogsPanel.svelte';
  import ServerStatus from './components/ServerStatus.svelte';
  import TestTTS from './components/TestTTS.svelte';
  import { getEngines, getModelStatus, getSystemInfo, preloadEngine, selectEngine, unloadEngine } from './lib/api.js';

  let bootReady = $state(false);
  let online = $state(false);
  let systemInfo = $state(null);
  let modelStatus = $state(null);
  let engines = $state([]);
  let selectedEngine = $state('omnivoice');
  let error = $state('');

  async function refresh() {
    try {
      const [info, model, enginePayload] = await Promise.all([
        getSystemInfo(),
        getModelStatus(),
        getEngines(),
      ]);
      systemInfo = info;
      modelStatus = model;
      engines = enginePayload.engines ?? [];
      selectedEngine = enginePayload.default_engine ?? selectedEngine;
      online = true;
      error = '';
    } catch (err) {
      online = false;
      error = err.message;
    }
  }

  async function setEngine(engine) {
    selectedEngine = engine;
    await selectEngine(engine);
    await refresh();
  }

  async function withRefresh(action) {
    await action();
    await refresh();
  }

  onMount(() => {
    refresh();
    const interval = setInterval(refresh, 3000);
    return () => clearInterval(interval);
  });
</script>

<main>
  {#if !bootReady}
    <BootstrapSplash onReady={() => (bootReady = true)} />
  {/if}

  <div class:hidden={!bootReady} class="dashboard">
    <ServerStatus {systemInfo} {modelStatus} {online} />

    {#if error}
      <div class="banner">Backend unavailable: {error}</div>
    {/if}

    <div class="two-column">
      <EngineSelector
        {engines}
        {selectedEngine}
        onSelect={setEngine}
        onPreload={(engine) => withRefresh(() => preloadEngine(engine))}
        onUnload={(engine) => withRefresh(() => unloadEngine(engine))}
      />
      <TestTTS {selectedEngine} />
    </div>

    <div class="two-column lower">
      <ExtensionGuide />
      <LogsPanel />
    </div>
  </div>
</main>
