# Plan Migration: OmniVoice Local TTS Server App

## Mục Tiêu

Chuyển OmniVoice Studio thành desktop app nhẹ hơn dùng cho Browser Extension:

- Giữ engine TTS mặc định là OmniVoice.
- Thêm tùy chọn engine TTS: Kokoro và `g-group-ai-lab/gwen-tts-0.6B`.
- Thay React frontend bằng Svelte 5.
- Giữ Tauri bootstrap để app tự tạo Python venv, cài dependencies, spawn FastAPI backend.
- Backend chạy local tại `127.0.0.1:3900`.
- Extension gọi API local để tạo audio.
- Bỏ các tính năng không cần: dubbing, dictation widget, pill mode, global shortcut, marketplace, gallery, batch queue, watermark, capture, transcription.

## Phạm Vi Giữ Lại

### Tauri/Rust

Giữ phần infrastructure:

- `frontend/src-tauri/src/bootstrap.rs`
- `frontend/src-tauri/src/backend.rs`
- `frontend/src-tauri/src/tools.rs`
- `frontend/src-tauri/src/config.rs`
- `frontend/src-tauri/src/main.rs`

Sửa nhẹ:

- `frontend/src-tauri/src/lib.rs`
- `frontend/src-tauri/src/commands.rs`
- `frontend/src-tauri/tauri.conf.json`
- `frontend/src-tauri/Cargo.toml`

### Backend

Giữ:

- `backend/main.py` nhưng dọn lại.
- `backend/core/config.py`
- `backend/core/db.py`
- `backend/services/model_manager.py`
- `backend/services/tts_backend.py`
- Thêm hoặc refactor `backend/services/engine_registry.py` để quản lý OmniVoice/Kokoro/Gwen.
- `backend/services/audio_dsp.py`
- `backend/api/routers/system.py` nhưng dọn nhẹ.
- `omnivoice/` package.
- `pyproject.toml`, `uv.lock`.

### Frontend

Thay React bằng Svelte 5:

- Giữ lại concept `BootstrapSplash`.
- Tạo UI quản lý local server/model đơn giản.
- Tạo API client Svelte/Vite dùng `fetch`.

## Phạm Vi Loại Bỏ

### Frontend React

Xóa hoặc thay toàn bộ:

- `frontend/src/App.jsx`
- `frontend/src/main.jsx`
- `frontend/src/main-app.jsx`
- `frontend/src/pages/*`
- `frontend/src/components/*` React-specific
- `frontend/src/store/*` Zustand
- `frontend/src/ui/*` React UI primitives
- React dependencies trong `frontend/package.json`

### Tauri Features Không Cần

Loại bỏ khỏi `lib.rs` và `commands.rs`:

- Dictation shortcut
- Widget window
- Pill mode
- Auto-start pill
- Tray menu dictation
- `simulate_paste`
- `set_tray_recording`
- `get_dictation_shortcut`
- `set_dictation_shortcut`
- `enable_pill_autostart`
- `disable_pill_autostart`
- `is_pill_autostart_enabled`

Có thể giữ system tray tối giản:

- Open app
- Restart backend nếu cần
- Quit

### Backend Routers Không Cần

Bỏ khỏi `backend/main.py`:

- `profiles` nếu chưa cần voice profile management
- `exports`
- `dub_core`
- `dub_generate`
- `dub_export`
- `dub_translate`
- `projects`
- `glossary`
- `engines` nếu chưa cần engine picker
- `tools`
- `setup` nếu UI model setup mới thay thế
- `gallery`
- `batch`
- `watermark`
- `events` nếu chưa cần realtime
- `capture`
- `capture_ws`
- `openai_compat` nếu extension dùng `/api/ext/generate`
- `tts_stream`
- `marketplace`

Giữ hoặc viết lại:

- `system`
- `generation` hoặc router mới `extension_tts`

## Multi-Engine TTS Support

App sẽ hỗ trợ 3 engine TTS có thể chọn trong UI và API:

| Engine | ID đề xuất | Vai trò | Ghi chú |
|---|---|---|---|
| OmniVoice | `omnivoice` | Engine mặc định, zero-shot multilingual voice cloning | Giữ package `omnivoice/` và dependency hiện tại |
| Kokoro | `kokoro` | Engine nhẹ/nhanh cho TTS phổ thông | Cần xác định package runtime cụ thể khi triển khai (`kokoro`, ONNX, hoặc wrapper tương thích) |
| Gwen-TTS 0.6B | `gwen` | Voice cloning tiếng Việt tối ưu | Model HF: `g-group-ai-lab/gwen-tts-0.6B`, dựa trên Qwen3-TTS, MIT |

Thiết kế backend:

- Tạo một engine registry thống nhất thay vì hardcode OmniVoice trong router.
- Mỗi engine implement interface chung: `id`, `display_name`, `is_available()`, `load()`, `generate()`, `unload()`.
- Chỉ load engine khi request đầu tiên dùng engine đó hoặc user bấm preload trong UI.
- Khi user đổi engine, unload engine cũ nếu không còn cần để tiết kiệm RAM/VRAM.
- `idle_worker()` phải unload engine đang active sau timeout không dùng.
- Lưu engine mặc định trong app config/user prefs, ví dụ `OMNIVOICE_TTS_ENGINE` hoặc DB/user config.

Interface đề xuất:

```python
class TTSEngine:
    id: str
    display_name: str

    def is_available(self) -> tuple[bool, str]: ...
    async def load(self): ...
    async def unload(self): ...
    async def generate(self, request: TTSRequest) -> tuple[bytes, int, dict]: ...
```

API engine management:

- `GET /api/ext/engines` trả danh sách engines, trạng thái installed/loaded, mô tả, ngôn ngữ hỗ trợ.
- `POST /api/ext/engines/select` chọn engine mặc định.
- `POST /api/ext/engines/{engine_id}/preload` tải model vào RAM/VRAM.
- `POST /api/ext/engines/{engine_id}/unload` unload model.

Request `/api/ext/generate` nên cho phép override engine:

```json
{
  "engine": "omnivoice",
  "text": "Xin chào",
  "language": "vi",
  "voice_id": "default",
  "speed": 1.0
}
```

Nếu `engine` bị bỏ trống, backend dùng engine mặc định trong config.

### Gwen-TTS Notes

Model:

`g-group-ai-lab/gwen-tts-0.6B`

Thông tin từ Hugging Face:

- Pipeline: text-to-speech.
- Library: Transformers/Qwen3-TTS.
- License: MIT.
- Tối ưu cho tiếng Việt, có voice cloning.
- Hỗ trợ: Vietnamese primary, Chinese, English, Japanese, Korean, French, German, Italian, Portuguese, Russian, Spanish.
- Cài runtime theo model card: `pip install -U qwen-tts`.
- Optional performance: `flash-attn`, nhưng không nên bắt buộc vì khó build cross-platform.

Implementation notes:

- Thêm dependency `qwen-tts` vào `pyproject.toml` ở Phase 2 hoặc optional group nếu muốn tránh làm nặng first install.
- Không thêm `flash-attn` mặc định; chỉ document optional cho CUDA Linux.
- Gwen cần `ref_audio` và `ref_text` để voice cloning chất lượng tốt.
- Nên thêm text normalization/chunking cho tiếng Việt trước khi gọi model, vì model card khuyến nghị xử lý số, ký hiệu, viết tắt và chia text dài.
- Default generation config nên expose ở backend config nhưng không cần hiện toàn bộ trong UI giai đoạn đầu.

Config khuyến nghị ban đầu:

```python
GWEN_MODEL_ID = "g-group-ai-lab/gwen-tts-0.6B"
GWEN_GENERATION_CONFIG = {
    "temperature": 0.3,
    "top_k": 20,
    "top_p": 0.9,
    "max_new_tokens": 4096,
    "repetition_penalty": 2.0,
    "subtalker_do_sample": True,
    "subtalker_temperature": 0.1,
    "subtalker_top_k": 20,
    "subtalker_top_p": 1.0,
}
```

### Kokoro Notes

Kokoro nên được dùng như engine nhẹ/nhanh:

- Mục tiêu: phản hồi nhanh cho extension khi không cần clone voice phức tạp.
- Ưu tiên backend CPU/ONNX nếu có package ổn định, để không chiếm VRAM.
- Cần xác định package cụ thể trước khi implement dependency chính thức.
- UI nên ghi rõ Kokoro là engine nhanh/nhẹ, không thay thế hoàn toàn voice cloning của OmniVoice/Gwen.

### Frontend Engine Selection

Svelte UI cần thêm:

- Dropdown chọn engine: OmniVoice, Kokoro, Gwen.
- Badge trạng thái: not installed/loading/ready/loaded/error.
- Nút preload/unload model.
- Cảnh báo tài nguyên cho OmniVoice/Gwen vì có thể dùng GPU/VRAM.
- Gợi ý Gwen tối ưu tiếng Việt.
- Test TTS form có field `engine`, `text`, `language`, `voice/ref_audio/ref_text` nếu engine hỗ trợ.

## Kiến Trúc Sau Migration

```text
Tauri App
  |
  | starts frontend/dist
  | spawns backend sidecar
  v

Svelte 5 Frontend
  |
  | Tauri IPC:
  | - bootstrap_status
  | - get_bootstrap_logs
  | - retry_bootstrap
  | - clean_and_retry_bootstrap
  |
  | HTTP:
  | - GET /system/info
  | - GET /model/status
  | - GET /api/ext/engines
  | - POST /api/ext/engines/select
  | - POST /api/ext/generate
  v

FastAPI Backend
  |
  | loads selected TTS engine lazily
  v

OmniVoice / Kokoro / Gwen TTS Engine
```

## API Cho Extension

Tạo router mới:

`backend/api/routers/extension_tts.py`

Endpoint chính:

`POST /api/ext/generate`

Request JSON:

```json
{
  "engine": "omnivoice",
  "text": "Hello world",
  "language": "en",
  "voice_id": "default",
  "speed": 1.0
}
```

Response:

- `audio/wav`
- trả trực tiếp audio bytes bằng `StreamingResponse`
- headers:
  - `X-TTS-Engine`
  - `X-Gen-Time`
  - `X-Audio-Duration`
  - `X-Audio-Id`

CORS cần cho phép:

- `chrome-extension://<extension-id>`
- `moz-extension://<extension-id>`
- `http://localhost:3901`
- `tauri://localhost`
- `http://tauri.localhost`

Giai đoạn dev có thể cho cấu hình qua env:

`OMNIVOICE_ALLOWED_ORIGINS`

Implementation note:

- Nếu biết extension ID cố định, ưu tiên whitelist origin cụ thể như `chrome-extension://abcdefghijklmnopqrstuvwxyz`.
- Nếu cần hỗ trợ nhiều extension ID, FastAPI `CORSMiddleware.allow_origins` không match wildcard kiểu `chrome-extension://*` theo nghĩa glob. Khi đó dùng `allow_origin_regex` cho `chrome-extension://.*` và `moz-extension://.*`, hoặc tự xử lý origin filter.
- Không nên dùng `Access-Control-Allow-Origin: *` cùng `allow_credentials=True`. Nếu cần wildcard cho extension, tắt credentials hoặc phản hồi dynamic origin hợp lệ.

## Svelte Frontend Structure

Tạo lại frontend:

```text
frontend/
├── package.json
├── vite.config.js
├── index.html
├── src/
│   ├── main.js
│   ├── App.svelte
│   ├── app.css
│   ├── lib/
│   │   ├── api.js
│   │   ├── tauri.js
│   │   └── format.js
│   └── components/
│       ├── BootstrapSplash.svelte
│       ├── ServerStatus.svelte
│       ├── ModelStatus.svelte
│       ├── EngineSelector.svelte
│       ├── ExtensionGuide.svelte
│       ├── TestTTS.svelte
│       └── LogsPanel.svelte
└── src-tauri/
```

UI chính gồm:

- Server status: backend online/offline.
- Bootstrap logs.
- Model/engine status: idle/loading/ready/loaded/error.
- Engine selector: OmniVoice, Kokoro, Gwen.
- Local endpoint card: `http://127.0.0.1:3900/api/ext/generate`.
- Extension CORS note.
- Test TTS form để nhập text và phát audio.
- Settings tối giản: allowed origins, cache dir nếu cần.

### Svelte 5 Bootstrap Pattern

Khi port `BootstrapSplash` từ React sang Svelte, dùng Svelte 5 runes thay vì Zustand/React state.

Mục tiêu:

- Dùng `$state` cho bootstrap stage, logs, progress, retry state.
- Dùng `onMount` để gọi Tauri IPC `invoke` và subscribe event `listen`.
- Poll `bootstrap_status` mỗi 1 giây.
- Backfill logs bằng `get_bootstrap_logs` trước khi listen realtime.
- Cleanup interval và event listeners khi component unmount.
- Dùng `bind:this` cho log container để auto-scroll xuống cuối.

Ví dụ skeleton:

```svelte
<script>
  import { onMount } from 'svelte';

  let stage = $state('checking');
  let message = $state('');
  let logs = $state([]);
  let progress = $state(null);
  let logPanel;

  onMount(async () => {
    const { invoke } = await import('@tauri-apps/api/core');
    const { listen } = await import('@tauri-apps/api/event');

    const current = await invoke('bootstrap_status');
    stage = current.stage;
    message = current.message ?? '';

    const buffered = await invoke('get_bootstrap_logs').catch(() => []);
    if (Array.isArray(buffered)) logs = buffered;

    const unlistenLog = await listen('bootstrap-log', (event) => {
      logs = [...logs, event.payload].slice(-200);
      queueMicrotask(() => {
        if (logPanel) logPanel.scrollTop = logPanel.scrollHeight;
      });
    });

    const unlistenProgress = await listen('bootstrap-progress', (event) => {
      progress = event.payload;
    });

    const interval = setInterval(async () => {
      const s = await invoke('bootstrap_status');
      stage = s.stage;
      message = s.message ?? '';
    }, 1000);

    return () => {
      clearInterval(interval);
      unlistenLog();
      unlistenProgress();
    };
  });
</script>
```

Lưu ý: trong Svelte 5 dùng `onclick`, `onchange`, không dùng cú pháp `on:click` cũ.

## Tauri Config Changes

File:

`frontend/src-tauri/tauri.conf.json`

Đổi:

- `productName`: `Local OmniVoice Server`
- `identifier`: ví dụ `com.local.omnivoice-server`
- `devUrl`: giữ `http://localhost:3901` hoặc đổi `5173`.

Khuyến nghị giữ `3901` để ít sửa backend fallback.

Bỏ window widget:

```json
"windows": [
  {
    "label": "main",
    "title": "Local OmniVoice Server",
    "width": 1100,
    "height": 760,
    "minWidth": 760,
    "minHeight": 520
  }
]
```

Giữ bundle resources:

```json
"resources": [
  "../../pyproject.toml",
  "../../uv.lock",
  "../../README.md",
  "../../omnivoice",
  "../../backend"
]
```

Vì vẫn dùng OmniVoice, không bỏ `../../omnivoice`.

## Rust Changes

### `lib.rs`

Dọn:

- Bỏ pill mode.
- Bỏ widget logic.
- Bỏ global shortcut.
- Bỏ dictation tray items.
- Bỏ mọi label/menu text liên quan `Dictation`, `Pill`, `Start Dictation`, `Open OmniVoice Studio`.
- Giữ bootstrap thread.
- Giữ backend spawn/health poll.
- Giữ single instance.
- Giữ log plugin.
- Giữ updater nếu muốn.

Tray tối giản:

- `Show Server Dashboard`
- `Quit TTS Server`

Khi bấm `Quit TTS Server`, gọi `app.exit(0)` để trigger `RunEvent::ExitRequested`; logic cuối `lib.rs` hiện có sẽ terminate Python backend process.

### `commands.rs`

Giữ:

- `get_sysinfo`
- `read_log_tail`
- `hf_cache_scan`
- `quit_app`

Bỏ:

- paste simulation
- dictation shortcut
- pill autostart
- tray recording icon

### `backend.rs`

Giữ health check `/system/info`.

Có thể đổi comment/log từ OmniVoice Studio sang Local OmniVoice Server.

### `bootstrap.rs`

Giữ copy `omnivoice/` vì vẫn dùng OmniVoice.

Có thể đổi text log từ OmniVoice sang app mới.

## Backend Changes

### `main.py`

Dọn import nặng ở top-level nếu có thể.

Giữ:

- dotenv loading
- cache env setup
- logging
- FastAPI app
- CORS
- `/health`
- static `/audio`
- static `/voice_audio` nếu cần profile audio
- frontend static serving
- `system.router`
- `extension_tts.router`

Cân nhắc:

- Không preload ASR.
- Không preload capture.
- Không start job worker nếu không cần batch/dub.
- Phải giữ `idle_worker()` trong lifespan để tự unload model khỏi RAM/VRAM sau thời gian không dùng.
- Có thể giữ lazy load OmniVoice model khi `/api/ext/generate` được gọi lần đầu.

Yêu cầu quan trọng cho desktop UX:

```python
@asynccontextmanager
async def lifespan(app: FastAPI):
    init_db()
    idle_task = asyncio.create_task(idle_worker())
    try:
        yield
    finally:
        idle_task.cancel()
        ...
```

Lý do: Local server có thể chạy nền nhiều giờ trong khi user chỉ thỉnh thoảng gọi TTS từ extension. Nếu giữ model trên VRAM liên tục, máy sẽ bị chiếm GPU/RAM khi user làm việc khác. `idle_worker()` là cơ chế tự giải phóng model quan trọng, không được xóa khi dọn `main.py`.

### `system.py`

Dọn nhẹ để không phụ thuộc quá nhiều vào routers/services bị xóa.

Giữ:

- `/system/info`
- `/system/logs`
- `/model/status`
- `/model/loaded`
- `/model/unload/{model_id}`
- `/system/flush-memory` nếu cần.

`/model/status` nên trả thêm engine hiện tại:

```json
{
  "status": "ready",
  "active_engine": "omnivoice",
  "loaded_engines": ["omnivoice"],
  "available_engines": ["omnivoice", "kokoro", "gwen"]
}
```

### `extension_tts.py`

Có thể reuse logic từ `generation.py`, nhưng nhận JSON thay vì multipart form.

Luồng:

1. Validate text.
2. Resolve engine từ request hoặc default config.
3. Lazy-load engine qua registry.
4. Apply mastering/normalize.
5. Save file vào `OUTPUTS_DIR`.
6. Return `StreamingResponse(audio/wav)`.

## Dependencies

Vì vẫn giữ OmniVoice và thêm engine mới, `pyproject.toml` chưa nên dọn mạnh ngay.

Giai đoạn 1:

- Giữ dependency hiện tại để tránh phá engine.
- Chỉ bỏ dependency frontend React.
- Implement engine registry với OmniVoice trước, để endpoint/API ổn định.

Giai đoạn 2 sau khi chạy ổn:

- Thêm Kokoro dependency sau khi chọn package runtime cụ thể.
- Thêm Gwen dependency `qwen-tts`.
- Regenerate `uv.lock` bằng `uv lock`/`uv sync` sau khi thêm dependency.
- Không thêm `flash-attn` mặc định vì dễ lỗi build cross-platform.

Giai đoạn 3 sau khi multi-engine chạy ổn:

- Audit backend import thực tế.
- Bỏ dần dependency không còn dùng:
  - `whisperx`
  - `faster-whisper`
  - `pyannote-audio`
  - `demucs`
  - `yt-dlp`
  - `audioseal`
  - `mlx-whisper`
  - các dependency dubbing/capture nếu không còn import.

Lý do: dọn dependency Python quá sớm dễ làm `uv sync --frozen` hoặc runtime OmniVoice hỏng.

## Build/Run Commands Sau Migration

Dev web:

```bash
uv run uvicorn main:app --app-dir backend --host 127.0.0.1 --port 3900 --reload
cd frontend && bun run dev
```

Dev desktop:

```bash
cd frontend
bun run desktop
```

Build frontend:

```bash
cd frontend
bun run build
```

Build desktop:

```bash
cd frontend
bun run tauri build
```

## Verification Checklist

1. `bun install` trong `frontend` thành công.
2. `bun run build` tạo `frontend/dist`.
3. `uv run uvicorn main:app --app-dir backend --host 127.0.0.1 --port 3900` start được.
4. `GET http://127.0.0.1:3900/system/info` trả `data_dir`.
5. `GET http://127.0.0.1:3900/api/ext/engines` trả OmniVoice/Kokoro/Gwen.
6. `POST http://127.0.0.1:3900/api/ext/generate` với `engine=omnivoice` trả audio wav.
7. Sau khi thêm dependency, `POST /api/ext/generate` với `engine=kokoro` trả audio wav.
8. Sau khi thêm dependency/model, `POST /api/ext/generate` với `engine=gwen` trả audio wav tiếng Việt.
9. `cd frontend && bun run desktop` mở app.
10. First-run bootstrap vẫn copy `backend/`, `omnivoice/`, tạo `.venv`, chạy `uv sync`.
11. Svelte `BootstrapSplash` hiển thị progress/logs.
12. Extension origin gọi API không bị CORS.
13. App quit thì backend process được terminate.
14. `idle_worker()` unload engine/model sau timeout không dùng.

## Thứ Tự Thực Hiện

### Phase 1: Svelte Shell

- Backup `frontend/src-tauri`.
- Tạo frontend Svelte 5.
- Khôi phục `src-tauri`.
- Tạo `BootstrapSplash.svelte`.
- Tạo UI quản lý server tối giản.
- Build frontend.

### Phase 2: Tauri Cleanup

- Sửa `tauri.conf.json`.
- Dọn `lib.rs` bỏ widget/dictation/pill.
- Dọn `commands.rs`.
- Sửa app name/log text.
- Kiểm tra `bun run desktop`.

### Phase 3: Backend Extension API

- Dọn `backend/main.py`.
- Tạo `backend/api/routers/extension_tts.py`.
- Tạo engine registry, implement OmniVoice adapter trước.
- Giữ lazy load model/engine.
- Sửa CORS cho extension.
- Test `/system/info` và `/api/ext/generate`.

### Phase 3.5: Multi-Engine Add-ons

- Thêm `GET /api/ext/engines` và endpoint chọn/preload/unload engine.
- Thêm Kokoro adapter sau khi chốt package runtime.
- Thêm Gwen adapter dùng `qwen-tts` và model `g-group-ai-lab/gwen-tts-0.6B`.
- Cập nhật Svelte `EngineSelector.svelte` và `TestTTS.svelte`.
- Test lazy load, unload, idle timeout cho từng engine.

### Phase 4: Polish & Docs

- Cập nhật scripts/docs.
- Cập nhật extension fetch example.
- Sau khi chạy ổn mới tối ưu dependency Python.
