export async function getTauriApi() {
  if (!('__TAURI_INTERNALS__' in window)) return null;

  const [{ invoke }, { listen }] = await Promise.all([
    import('@tauri-apps/api/core'),
    import('@tauri-apps/api/event'),
  ]);

  return { invoke, listen };
}
