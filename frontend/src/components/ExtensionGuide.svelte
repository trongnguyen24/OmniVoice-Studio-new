<section class="panel endpoint-panel">
  <p class="eyebrow">Extension endpoint</p>
  <h2>Local API</h2>
  <code>POST http://127.0.0.1:3900/api/ext/generate</code>
  <pre>{`fetch('http://127.0.0.1:3900/api/ext/generate', {
  method: 'POST',
  headers: { 'Content-Type': 'application/json' },
  body: JSON.stringify({
    engine: 'omnivoice',
    text: selectionText,
    language: 'vi',
    speed: 1
  })
})`}</pre>
  <p class="muted">Allowed origins are controlled by <code>OMNIVOICE_ALLOWED_ORIGINS</code>. Extension origins are supported through the backend CORS regex.</p>
</section>
