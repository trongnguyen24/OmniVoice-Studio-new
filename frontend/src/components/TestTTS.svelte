<script>
  import { generateTts } from '../lib/api.js';

  let { selectedEngine = 'omnivoice' } = $props();

  let text = $state('Xin chao, day la OmniVoice local server.');
  let language = $state('vi');
  let speed = $state(1);
  let loading = $state(false);
  let error = $state('');
  let result = $state(null);
  let audioUrl = $state('');

  async function submit() {
    loading = true;
    error = '';
    try {
      const response = await generateTts({ engine: selectedEngine, text, language, speed });
      if (audioUrl) URL.revokeObjectURL(audioUrl);
      audioUrl = URL.createObjectURL(response.blob);
      result = response;
    } catch (err) {
      error = err.message;
    } finally {
      loading = false;
    }
  }
</script>

<section class="panel test-panel">
  <div>
    <p class="eyebrow">Smoke test</p>
    <h2>Generate Audio</h2>
  </div>

  <label>
    Text
    <textarea bind:value={text} rows="5"></textarea>
  </label>

  <div class="form-grid">
    <label>
      Language
      <input bind:value={language} placeholder="vi" />
    </label>
    <label>
      Speed
      <input bind:value={speed} min="0.5" max="2" step="0.05" type="number" />
    </label>
  </div>

  <button onclick={submit} disabled={loading || !text.trim()}>{loading ? 'Generating...' : 'Generate WAV'}</button>

  {#if error}
    <p class="error-text">{error}</p>
  {/if}

  {#if audioUrl}
    <div class="audio-result">
      <audio controls src={audioUrl}></audio>
      <small>Engine {result.engine}; generation {result.genTime ?? '?'}s; duration {result.duration ?? '?'}s</small>
    </div>
  {/if}
</section>
