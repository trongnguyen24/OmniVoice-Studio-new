<script>
  import { generateTts, generateVoiceClone } from '../lib/api.js';

  let { selectedEngine = 'omnivoice' } = $props();

  let text = $state('Xin chao, day la OmniVoice local server.');
  let language = $state('vi');
  let speed = $state(1);
  let loading = $state(false);
  let error = $state('');
  let result = $state(null);
  let audioUrl = $state('');
  let cloneText = $state('Xin chao, day la ban sao giong noi tu mau tham chieu.');
  let cloneLanguage = $state('vi');
  let cloneSpeed = $state(1);
  let cloneRefText = $state('');
  let cloneInstruct = $state('');
  let cloneFile = $state(null);
  let cloneLoading = $state(false);
  let cloneError = $state('');
  let cloneResult = $state(null);
  let cloneAudioUrl = $state('');

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

  function selectCloneFile(event) {
    cloneFile = event.currentTarget.files?.[0] ?? null;
  }

  async function submitClone() {
    if (!cloneFile) {
      cloneError = 'Upload a reference voice clip first.';
      return;
    }

    cloneLoading = true;
    cloneError = '';
    try {
      const formData = new FormData();
      formData.append('engine', selectedEngine);
      formData.append('text', cloneText);
      formData.append('language', cloneLanguage || 'Auto');
      formData.append('speed', String(cloneSpeed));
      formData.append('ref_audio', cloneFile);
      if (cloneRefText.trim()) formData.append('ref_text', cloneRefText.trim());
      if (cloneInstruct.trim()) formData.append('instruct', cloneInstruct.trim());

      const response = await generateVoiceClone(formData);
      if (cloneAudioUrl) URL.revokeObjectURL(cloneAudioUrl);
      cloneAudioUrl = URL.createObjectURL(response.blob);
      cloneResult = response;
    } catch (err) {
      cloneError = err.message;
    } finally {
      cloneLoading = false;
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

  <div class="clone-divider"></div>

  <div>
    <p class="eyebrow">Voice clone</p>
    <h2>Clone From Reference</h2>
    <p class="muted">Use only voices you own or have permission to clone. A clean 5-15 second WAV works best.</p>
  </div>

  <label>
    Reference voice clip
    <input accept="audio/*" onchange={selectCloneFile} type="file" />
    {#if cloneFile}
      <small>{cloneFile.name}</small>
    {/if}
  </label>

  <label>
    Reference transcript (recommended)
    <textarea bind:value={cloneRefText} placeholder="What is spoken in the reference clip" rows="3"></textarea>
  </label>

  <label>
    Text to synthesize
    <textarea bind:value={cloneText} rows="5"></textarea>
  </label>

  <div class="form-grid">
    <label>
      Language
      <input bind:value={cloneLanguage} placeholder="vi" />
    </label>
    <label>
      Speed
      <input bind:value={cloneSpeed} min="0.5" max="2" step="0.05" type="number" />
    </label>
  </div>

  <label>
    Style instruction (optional)
    <input bind:value={cloneInstruct} placeholder="warm, calm, young adult" />
  </label>

  <button onclick={submitClone} disabled={cloneLoading || !cloneText.trim() || !cloneFile}>
    {cloneLoading ? 'Cloning...' : 'Clone Voice WAV'}
  </button>

  {#if cloneError}
    <p class="error-text">{cloneError}</p>
  {/if}

  {#if cloneAudioUrl}
    <div class="audio-result">
      <audio controls src={cloneAudioUrl}></audio>
      <small>Engine {cloneResult.engine}; generation {cloneResult.genTime ?? '?'}s; duration {cloneResult.duration ?? '?'}s</small>
    </div>
  {/if}
</section>
