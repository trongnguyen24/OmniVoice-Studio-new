<script>
  let { engines = [], selectedEngine = 'omnivoice', onSelect, onPreload, onUnload } = $props();
</script>

<section class="panel">
  <div class="panel-head">
    <div>
      <p class="eyebrow">TTS engine</p>
      <h2>Engine Selection</h2>
    </div>
    <select value={selectedEngine} onchange={(event) => onSelect?.(event.currentTarget.value)}>
      {#each engines as engine}
        <option value={engine.id}>{engine.display_name}</option>
      {/each}
    </select>
  </div>

  <div class="engine-list">
    {#each engines as engine}
      <article class:selected={engine.id === selectedEngine} class="engine-card">
        <div>
          <div class="engine-title">
            <strong>{engine.display_name}</strong>
            <span class={`badge ${engine.loaded ? 'good' : engine.installed ? 'idle' : 'warn'}`}>
              {engine.loaded ? 'loaded' : engine.installed ? 'ready' : 'not installed'}
            </span>
          </div>
          <p>{engine.description}</p>
          <small>{engine.languages?.join(', ')}</small>
        </div>
        <div class="row-actions">
          <button onclick={() => onPreload?.(engine.id)} disabled={!engine.installed}>Preload</button>
          <button class="secondary" onclick={() => onUnload?.(engine.id)} disabled={!engine.loaded}>Unload</button>
        </div>
      </article>
    {/each}
  </div>
</section>
