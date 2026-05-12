# OmniVoice Studio — Kiến trúc & Logic Tự động hóa

> **Mục đích:** Hiểu rõ cách OmniVoice Studio hoạt động ở mức logic để có thể **clone kiến trúc** và build một app khác với cùng pattern: Python BE + React FE + Tauri desktop, tự động cài đặt dependencies cho người dùng cuối.

---

## Mục lục

1. [Kiến trúc tổng thể — Flow từ mở app đến chạy được](#1-kiến-trúc-tổng-thể)
2. [Phase 1: Tauri Shell khởi động](#2-phase-1-tauri-shell-khởi-động)
3. [Phase 2: Bootstrap — Tự động cài đặt Python environment](#3-phase-2-bootstrap)
4. [Phase 3: Spawn Backend](#4-phase-3-spawn-backend)
5. [Phase 4: Frontend kết nối Backend](#5-phase-4-frontend-kết-nối-backend)
6. [Hệ thống resolve tool chain (uv, ffmpeg)](#6-hệ-thống-resolve-tool-chain)
7. [Region-aware download mirrors](#7-region-aware-download-mirrors)
8. [Backend Architecture (FastAPI)](#8-backend-architecture)
9. [Frontend Architecture (React)](#9-frontend-architecture)
10. [Tauri Config & Bundle](#10-tauri-config--bundle)
11. [Hướng dẫn clone kiến trúc cho app khác](#11-hướng-dẫn-clone-kiến-trúc-cho-app-khác)
12. [File map — đâu là gì](#12-file-map)

---

## 1. Kiến trúc tổng thể

Khi người dùng mở OmniVoice Studio, **không có gì sẵn sàng cả**. App phải tự:
1. Kiểm tra Python environment tồn tại chưa
2. Nếu chưa → tự cài `uv` → tạo venv → cài hàng trăm MB dependencies
3. Spawn backend process
4. Chờ backend healthy
5. Mở UI

```
User double-click app
        │
        ▼
┌───────────────────────────────────────┐
│  Tauri Shell (Rust) — lib.rs::run()  │
│                                       │
│  1. Register IPC commands             │
│  2. Setup plugins (tray, shortcut)    │
│  3. Spawn thread → bootstrap flow     │
│     ┌─────────────────────────────┐   │
│     │ bootstrap::ensure_venv_ready│   │
│     │   ├─ Dev mode? → dùng .venv │   │
│     │   └─ Production? →           │   │
│     │       1. resolve_uv()       │   │
│     │       2. copy resources     │   │
│     │       3. uv venv --python 3.11│  │
│     │       4. uv sync --frozen   │   │
│     └──────────┬──────────────────┘   │
│                │                       │
│     ┌──────────▼──────────────────┐   │
│     │ backend::spawn_backend()    │   │
│     │   python -m uvicorn main:app│   │
│     └──────────┬──────────────────┘   │
│                │                       │
│     ┌──────────▼──────────────────┐   │
│     │ Poll /system/info until 200 │   │
│     │ Set stage = Ready           │   │
│     └─────────────────────────────┘   │
│                                       │
│  4. WebView loads frontend/dist/      │
└───────────────────────────────────────┘
        │
        ▼
┌───────────────────────────────────────┐
│  React Frontend                       │
│  ┌─ BootstrapSplash.jsx ────────────┐ │
│  │  Poll bootstrap_status mỗi 1s    │ │
│  │  Listen bootstrap-log events     │ │
│  │  Hiển thị progress + logs        │ │
│  │  Khi stage=ready → chuyển sang   │ │
│  │  SetupWizard hoặc main app       │ │
│  └──────────────────────────────────┘ │
└───────────────────────────────────────┘
```

**Key insight:** Tauri shell **không chờ** bootstrap hoàn thành. Nó spawn một thread riêng, rồi cho WebView load ngay. Frontend tự poll trạng thái và quyết định hiển thị splash hay app.

---

## 2. Phase 1: Tauri Shell khởi động

**File:** `frontend/src-tauri/src/lib.rs`

```rust
pub fn run() {
    // 1. Xây Tauri app với tất cả plugins
    let app = tauri::Builder::default()
        .plugin(tauri_plugin_single_instance::init(...))  // chống mở nhiều cửa sổ
        .plugin(tauri_plugin_dialog::init())
        .plugin(tauri_plugin_updater::Builder::new().build())
        .plugin(tauri_plugin_global_shortcut::Builder::new()...)  // phím tắt toàn cục
        .invoke_handler(tauri::generate_handler![
            bootstrap::bootstrap_status,     // FE hỏi: đang ở stage nào?
            bootstrap::get_bootstrap_logs,   // FE hỏi: logs ra sao?
            bootstrap::retry_bootstrap,      // FE yêu cầu: thử lại
            bootstrap::clean_and_retry_bootstrap, // FE yêu cầu: xóa + thử lại
            commands::get_sysinfo,           // FE hỏi: CPU/RAM/disk
            // ... nhiều commands khác
        ])
        .setup(move |app| {
            // 2. Manage shared state
            app.manage(BackendState { process: Mutex::new(None) });
            app.manage(BootstrapState { stage, logs });
            
            // 3. Register global shortcut (Cmd+Shift+Space)
            // 4. Setup system tray
            // 5. Spawn bootstrap thread ← ĐÂY LÀ CHÍNH
            std::thread::spawn(move || {
                // Kiểm tra backend có sẵn không?
                if backend::backend_healthy(port) { return; }
                // Kill orphan nếu port bị chiếm
                // Spawn backend
                // Poll health trong 300s
            });
        })
}
```

### Shared State pattern

```rust
// Backend process được quản lý qua Mutex
pub struct BackendState {
    pub process: Mutex<Option<Child>>,
}

// Bootstrap stage được share giữa Rust thread và frontend
pub struct BootstrapState {
    pub stage: Arc<Mutex<BootstrapStage>>,
    pub logs: Arc<Mutex<Vec<LogPayload>>>,
}
```

Frontend gọi `invoke('bootstrap_status')` → Rust trả về stage hiện tại.
Rust emit event `bootstrap-log` → Frontend listen và hiển thị real-time.

---

## 3. Phase 2: Bootstrap

**File:** `frontend/src-tauri/src/bootstrap.rs`

Đây là **logic quan trọng nhất** — tự động tạo Python environment từ đầu.

### Flow chi tiết:

```
ensure_venv_ready(app, progress)
        │
        ├─ 1. Dev mode? (có ../../backend/main.py?)
        │     → Dùng .venv/ có sẵn, return ngay
        │
        ├─ 2. Production mode
        │     ├─ Kiểm tra app_local_data/project/.venv/
        │     │   ├─ Có + uvicorn importable? → Return ngay
        │     │   └─ Có + uvicorn hỏng? → Repair: uv sync lại
        │     │
        │     └─ Chưa có? → FIRST-RUN BOOTSTRAP:
        │
        ├─ 3. Copy resources từ Tauri bundle
        │     ├─ pyproject.toml → project/
        │     ├─ uv.lock → project/
        │     ├─ README.md → project/  (hatchling cần)
        │     ├─ omnivoice/ → project/omnivoice/
        │     └─ backend/ → project/backend/
        │
        ├─ 4. resolve_uv() → lấy uv binary
        │     ├─ Bundled sidecar? (bundle.externalBin)
        │     ├─ System PATH?
        │     └─ Download từ astral.sh
        │
        ├─ 5. uv venv --python 3.11 --managed-python
        │     → Tạo .venv/ trong project/
        │
        └─ 6. uv sync --frozen --no-dev --verbose
              → Cài TẤT CẢ dependencies từ pyproject.toml
              → Lần đầu: 5-10 phút (torch ~2GB, whisperx, demucs...)
              → Stream stdout/stderr → frontend hiển thị progress
```

### Bootstrap stages (state machine)

```rust
pub enum BootstrapStage {
    Checking,           // Đang kiểm tra
    DownloadingUv { percent: Option<u8> },  // Đang tải uv
    CreatingVenv,       // Đang tạo venv
    InstallingDeps,     // Đang cài dependencies (lâu nhất)
    StartingBackend,    // Đang khởi động backend
    Ready,              // Sẵn sàng!
    Failed { message: String },  // Lỗi
}
```

### Tại sao cần copy resources?

Tauri bundle (.dmg/.msi/.AppImage) chứa các file Python source được đóng gói
qua `tauri.conf.json → bundle.resources`:

```json
{
  "bundle": {
    "resources": [
      "../../pyproject.toml",
      "../../uv.lock",
      "../../README.md",
      "../../omnivoice",
      "../../backend"
    ]
  }
}
```

Khi app cài đặt, Tauri giải nén các file này vào `resource_dir/`.
Bootstrap copy chúng vào `app_local_data_dir/project/` rồi chạy `uv sync`
tại đó → tạo venv hoàn toàn độc lập, không cần system Python.

---

## 4. Phase 3: Spawn Backend

**File:** `frontend/src-tauri/src/backend.rs`

```
spawn_backend(app, progress)
        │
        ├─ 1. ensure_venv_ready() → (python_path, backend_dir)
        │
        ├─ 2. Set environment variables:
        │     PYTHONUNBUFFERED=1        (log real-time)
        │     FFMPEG_PATH=...           (từ resolve_ffmpeg)
        │     HF_ENDPOINT=...          (mirror nếu region=china)
        │     TORCHDYNAMO_DISABLE=1    (Windows only)
        │
        ├─ 3. Spawn process:
        │     python -m uvicorn main:app
        │       --app-dir backend/
        │       --host 127.0.0.1
        │       --port 3900
        │
        ├─ 4. Pipe stdout → log file + emit events
        │     Pipe stderr → error log + emit events
        │
        └─ 5. Poll health check:
              GET http://127.0.0.1:3900/system/info
              → Kiểm tra response chứa "model_checkpoint" hoặc "data_dir"
              → Timeout: 300 giây
              → Nếu process chết sớm → read_error_log_tail() → báo lỗi
```

### Health check logic

```rust
pub fn backend_healthy(port: u16) -> bool {
    let url = format!("http://127.0.0.1:{}/system/info", port);
    match ureq_get_with_timeout(&url, Duration::from_millis(500)) {
        Ok(body) => body.contains("\"model_checkpoint\"") || body.contains("\"data_dir\""),
        Err(_) => false,
    }
}
```

Không chỉ kiểm tra port open — phải verify response body chứa field đặc trưng
của OmniVoice backend. Tránh nhầm lẫn với app khác cùng port.

---

## 5. Phase 4: Frontend kết nối Backend

**File:** `frontend/src/api/client.ts`

```typescript
// Backend URL — configurable qua env vars
const _port = import.meta.env.VITE_API_PORT || '3900';
export const API = import.meta.env.VITE_API_URL || `http://127.0.0.1:${_port}`;

// Base fetch wrapper — tất cả API calls đi qua đây
export async function apiFetch(path: string, opts: RequestInit = {}): Promise<Response> {
  const res = await fetch(apiUrl(path), opts);
  if (!res.ok) {
    const detail = await readError(res);
    throw new ApiError(`${res.status}: ${detail}`, { status: res.status, detail });
  }
  return res;
}
```

**File:** `frontend/src/api/hooks.ts`

Dùng TanStack React Query để quản lý server state:

```typescript
// Query keys — centralized, tránh typo
export const queryKeys = {
  sysinfo: ['sysinfo'] as const,
  setupStatus: ['setup-status'] as const,
  // ...
};

// Hook với auto-polling
export function useSysinfo(enabled = true) {
  return useQuery({
    queryKey: queryKeys.sysinfo,
    queryFn: systemApi.sysinfo,
    refetchInterval: 5_000,  // poll mỗi 5s
    retry: Infinity,         // retry vô hạn nếu fail
    retryDelay: 1_500,
    enabled,
  });
}
```

### Bootstrap ↔ Frontend communication

```
┌─────────────┐    Tauri IPC (invoke)     ┌──────────────────┐
│   Rust       │ ◄─────────────────────── │  React Frontend  │
│   Bootstrap  │                           │                  │
│              │  bootstrap_status         │  useBootstrapStage│
│              │  get_bootstrap_logs       │  (poll mỗi 1s)   │
│              │  retry_bootstrap          │                  │
│              │  clean_and_retry_bootstrap│                  │
│              │                           │                  │
│              │  ──── Events ───────────► │                  │
│              │  "bootstrap-log"          │  listen()        │
│              │  "bootstrap-progress"     │  hiển thị logs   │
└─────────────┘                           └──────────────────┘
```

---

## 6. Hệ thống Resolve Tool Chain

**File:** `frontend/src-tauri/src/tools.rs`

OmniVoice cần `uv`, `ffmpeg`, `ffprobe`. Mỗi tool dùng cùng 1 pattern resolve:

```
Priority cascade:
  1. Bundled sidecar (đóng gói cùng app)
  2. Cached download (trong app_data/tools/)
  3. System PATH
  4. Auto-download từ internet
```

### uv resolution

```rust
pub fn resolve_uv(app, app_data, progress) -> Result<PathBuf, String> {
    // 1. Bundled sidecar? (Tauri bundle.externalBin)
    if let Some(p) = find_bundled_uv() { return Ok(p); }
    
    // 2. System PATH?
    if Command::new("uv").arg("--version").output().is_ok() {
        return Ok(PathBuf::from("uv"));
    }
    
    // 3. Download via official Astral installer
    set_stage(progress, DownloadingUv { percent: None });
    install_uv_standalone(&app_data.join("tools"), region)
}

fn install_uv_standalone(dest: &Path, region: &str) -> io::Result<PathBuf> {
    // Unix: curl -LsSf https://astral.sh/uv/{version}/install.sh | sh
    // Windows: powershell -c "irm https://astral.sh/uv/{version}/install.ps1 | iex"
    // UV_INSTALL_DIR=dest để control nơi cài
}
```

### ffmpeg resolution

```rust
pub fn resolve_ffmpeg(app, app_data) -> Option<PathBuf> {
    // 1. Bundled sidecar?
    if let Some(p) = find_bundled_ffmpeg() { return Some(p); }
    
    // 2. Cached trong app_data/tools/?
    let cached = app_data.join("tools/ffmpeg");
    if cached.is_file() { return Some(cached); }
    
    // 3. System PATH?
    if Command::new("ffmpeg").arg("-version").status().is_ok() {
        return Some(PathBuf::from("ffmpeg"));
    }
    
    // 4. Auto-download
    install_ffmpeg_standalone(&tools_dir, region)
    //   macOS: brew install ffmpeg (nếu có Homebrew)
    //          hoặc download từ evermeet.cx
    //   Linux: download từ BtbN/FFmpeg-Builds (.tar.xz)
    //   Windows: download từ BtbN/FFmpeg-Builds (.zip)
}
```

### Bundled sidecar detection

```rust
pub fn find_bundled_sidecar(name: &str) -> Option<PathBuf> {
    let exe = std::env::current_exe().ok()?;
    let dir = exe.parent()?;
    let triple = match (OS, ARCH) {
        ("macos", "aarch64") => "aarch64-apple-darwin",
        ("macos", "x86_64") => "x86_64-apple-darwin",
        ("linux", "x86_64") => "x86_64-unknown-linux-gnu",
        ("windows", "x86_64") => "x86_64-pc-windows-msvc",
        _ => return None,
    };
    let candidate = dir.join(format!("{}-{}{}", name, triple, ext));
    // Reject placeholder files (< 1024 bytes) from cargo check
    if metadata.len() < 1024 { return None; }
    Some(candidate)
}
```

---

## 7. Region-aware Download Mirrors

**File:** `frontend/src-tauri/src/config.rs`

Tự động detect người dùng ở đâu để chọn mirror phù hợp:

```rust
pub fn auto_detect_region() -> String {
    // Probe github.com với timeout 4s
    match agent.request("HEAD", "https://github.com").call() {
        Ok(resp) if resp.status() < 400 => "global".to_string(),
        _ => "restricted".to_string(),  // dùng ghproxy.net
    }
}

pub fn resolve_github_url(raw_url: &str, region: &str) -> String {
    match region {
        "china" | "russia" | "restricted" => 
            format!("https://ghproxy.net/{}", raw_url),
        _ => raw_url.to_string(),
    }
}
```

| Region | GitHub | PyPI | HuggingFace |
|---|---|---|---|
| `global` | direct | direct | direct |
| `china` | ghproxy.net | mirrors.aliyun.com | hf-mirror.com |
| `russia` | ghproxy.net | direct | direct |
| `restricted` | ghproxy.net | direct | direct |

User có thể override trong UI (BootstrapSplash có dropdown chọn region).

---

## 8. Backend Architecture (FastAPI)

### Entry point

**File:** `backend/main.py`

```python
# Đảm bảo backend/ trên sys.path
_backend_dir = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, _backend_dir)

# Load .env + user config
dotenv.load_dotenv()
dotenv.load_dotenv(os.path.expanduser("~/.config/omnivoice/env"), override=False)

# cuDNN 8 compat preload (PyTorch 2.8+ có cuDNN 9, CTranslate2 cần cuDNN 8)
# → ctypes.CDLL("libcudnn*.so.8") trước khi import bất kỳ thứ gì

# HF cache dir routing
if os.environ.get("OMNIVOICE_CACHE_DIR"):
    os.environ["HF_HOME"] = cache_dir
    os.environ["TORCH_HOME"] = cache_dir
```

### Router structure

```
backend/api/routers/
├── generation.py      # POST /generate     — TTS inference
├── dub_core.py        # POST /dub          — Video dubbing core
├── dub_translate.py   # POST /dub/translate — Translation
├── dub_export.py      # POST /dub/export   — Export dubbed video
├── batch.py           # POST /batch        — Batch queue
├── capture.py         # POST /capture      — Dictation widget
├── engines.py         # GET/POST /engines  — TTS engine management
├── profiles.py        # GET/POST /profiles — Voice profiles
├── projects.py        # GET/POST /projects — Project management
├── gallery.py         # GET /gallery       — Voice gallery
├── marketplace.py     # GET /marketplace   — Voice marketplace
├── watermark.py       # POST /watermark    — AudioSeal watermark
├── openai_compat.py   # POST /v1/audio/speech — OpenAI-compatible API
├── tools.py           # POST /tools        — Audio tools
├── system.py          # GET /system/info   — System info
├── events.py          # WebSocket /events  — Real-time events
└── setup/
    ├── models.py      # GET/POST /setup/models — Model management
    ├── download.py    # POST /setup/download   — Model downloads
    └── wizard.py      # GET /setup/preflight   — System preflight
```

### Service layer

```
backend/services/
├── tts_backend.py       # Abstract TTS engine interface
├── asr_backend.py       # ASR (Whisper/WhisperX/faster-whisper)
├── dub_pipeline.py      # Full dubbing pipeline orchestrator
├── translation_engines.py # Translation backends (multiple)
├── model_manager.py     # Model download, cache, preload
├── audio_dsp.py         # Audio processing (pedalboard)
├── watermark.py         # AudioSeal watermarking
├── rvc.py               # Voice conversion
├── speaker_clone.py     # Speaker cloning
├── ffmpeg_utils.py      # FFmpeg wrapper
├── batched_tts.py       # Batch TTS processing
├── llm_backend.py       # LLM integration (for translation)
├── plugin_sdk.py        # Plugin system
└── ...
```

### Key patterns

```python
# FastAPI dependency injection
from fastapi import Depends

def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

@router.post("/generate")
async def generate(request: GenerateRequest, db = Depends(get_db)):
    ...
```

```python
# Event bus cho real-time updates
class EventBus:
    async def emit(self, event: str, data: dict):
        # Push to all connected WebSocket clients
        ...

# WebSocket endpoint
@router.websocket("/events")
async def events_ws(websocket: WebSocket):
    await websocket.accept()
    event_bus.subscribe(websocket)
    ...
```

---

## 9. Frontend Architecture (React)

### State management

```
frontend/src/store/
├── index.ts           # Root store
├── generateSlice.ts   # TTS generation state
├── dubSlice.ts        # Dubbing state
├── glossarySlice.ts   # Glossary state
├── pillSlice.ts       # Floating pill state
├── prefsSlice.ts      # User preferences
└── uiSlice.ts         # UI state (sidebar, tabs)
```

Dùng **Zustand** — nhẹ, không cần Provider, mỗi slice independent:

```typescript
// store/generateSlice.ts
import { create } from 'zustand';

export const useGenerateStore = create((set, get) => ({
  text: '',
  engine: 'omnivoice',
  voiceId: null,
  setText: (text) => set({ text }),
  generate: async () => {
    const { text, engine, voiceId } = get();
    const result = await apiPost('/generate', { text, engine, voice_id: voiceId });
    set({ lastResult: result });
  },
}));
```

### API layer pattern

```
frontend/src/api/
├── client.ts          # Base HTTP client (apiFetch, apiPost, apiJson)
├── hooks.ts           # TanStack Query hooks (useSysinfo, useModelStatus...)
├── types.ts           # TypeScript types
├── generate.ts        # TTS generation API
├── dub.ts             # Dubbing API
├── batch.ts           # Batch API
├── engines.ts         # Engine management API
├── profiles.ts        # Voice profiles API
├── projects.ts         # Projects API
├── gallery.ts         # Gallery API
├── setup.ts           # Setup/prelight API
├── system.ts          # System info API
├── exports.ts         # Export API
├── glossary.ts        # Glossary API
└── external.ts        # External API calls
```

**Pattern:** Mỗi module export các function gọi API, `hooks.ts` wrap chúng thành
React Query hooks với caching, retry, polling.

### Page structure

```
frontend/src/pages/
├── Launchpad.jsx        # Home/dashboard
├── CloneDesignTab.jsx   # Voice cloning + voice design
├── DubTab.jsx           # Video dubbing
├── BatchQueue.jsx       # Batch processing
├── VoiceGallery.jsx     # Voice library
├── VoiceProfile.jsx     # Voice profiles
├── Settings.jsx         # App settings
├── SetupWizard.jsx      # First-run wizard (4 steps)
├── ToolsPage.jsx        # Audio tools
├── Transcriptions.jsx   # Transcription viewer
├── Projects.jsx         # Project management
├── DonatePage.jsx       # Donate page
└── EnterprisePage.jsx   # Enterprise page
```

### UI primitives

```
frontend/src/ui/
├── Button.jsx + Button.css
├── Dialog.jsx + Dialog.css
├── Input.jsx + Input.css
├── Slider.jsx + Slider.css
├── Tabs.jsx + Tabs.css
├── Table.jsx + Table.css
├── Panel.jsx + Panel.css
├── Progress.jsx + Progress.css
├── Badge.jsx + Badge.css
├── Menu.jsx + Menu.css
├── Segmented.jsx + Segmented.css
├── Tooltip.jsx + Tooltip.css
├── tokens.css           # Design tokens (colors, spacing)
├── themes.css           # Light/dark theme
├── motion.js            # Animation helpers
└── index.js             # Re-exports
```

---

## 10. Tauri Config & Bundle

**File:** `frontend/src-tauri/tauri.conf.json`

```jsonc
{
  "productName": "OmniVoice Studio",
  "version": "0.2.7",
  "identifier": "com.debpalash.omnivoice-studio",
  
  "build": {
    "frontendDist": "../dist",           // Vite build output
    "devUrl": "http://localhost:3901",   // Vite dev server
    "beforeDevCommand": "bun run dev",   // Chạy khi `tauri dev`
    "beforeBuildCommand": "bun run build" // Chạy khi `tauri build`
  },
  
  "app": {
    "windows": [
      {
        "title": "OmniVoice Studio",
        "width": 1920, "height": 1080,
        "minWidth": 900, "minHeight": 600
      },
      {
        "label": "widget",              // Dictation widget (ẩn mặc định)
        "transparent": true,
        "decorations": false,
        "alwaysOnTop": true,
        "visible": false
      }
    ]
  },
  
  "bundle": {
    "resources": [                      // Files đóng gói cùng app
      "../../pyproject.toml",
      "../../uv.lock",
      "../../README.md",
      "../../omnivoice",
      "../../backend"
    ],
    "externalBin": [                    // Sidecar binaries
      "binaries/uv",
      "binaries/ffmpeg",
      "binaries/ffprobe"
    ]
  }
}
```

---

## 11. Hướng dẫn clone kiến trúc cho app khác

Nếu bạn muốn build một app khác (ví dụ: image processing, video editor, audio tool)
với cùng pattern **Python BE + React FE + Tauri desktop + auto-install**:

### Bước 1: Tạo project mới từ template

```bash
# Clone OmniVoice Studio
git clone https://github.com/debpalash/OmniVoice-Studio.git my-app
cd my-app

# Xóa các file không cần thiết
rm -rf omnivoice/ research/ examples/ docs/ design/
rm -rf backend/services/tts_backend.py backend/services/asr_backend.py  # ... các service đặc thù
rm -rf frontend/src/pages/CloneDesignTab.jsx frontend/src/pages/DubTab.jsx  # ... các page đặc thù
```

### Bước 2: Giữ nguyên infrastructure

**KHÔNG XÓA** các file này — đây là xương sống:

```
frontend/src-tauri/
├── src/lib.rs              # Tauri entry + bootstrap orchestration
├── src/bootstrap.rs        # Auto-create Python venv
├── src/backend.rs          # Spawn & manage backend process
├── src/tools.rs            # Resolve uv, ffmpeg
├── src/config.rs           # Region detection, mirror routing
├── src/commands.rs         # IPC commands
├── Cargo.toml              # Rust deps (giữ nguyên, chỉ đổi tên)
└── tauri.conf.json         # Bundle config (sửa resources, identifier)

frontend/src/
├── api/client.ts           # Base HTTP client
├── api/hooks.ts            # React Query hooks (sửa query keys)
├── components/BootstrapSplash.jsx  # Splash screen (giữ nguyên)
├── store/                  # Zustand (xóa slices cũ, thêm mới)
└── ui/                     # Design system (giữ nguyên)

scripts/
├── install.sh              # Universal installer (sửa tên app)
└── run.sh                  # Universal launcher

deploy/
├── Dockerfile              # Multi-stage Docker (sửa Python deps)
└── docker-compose.yml      # Compose config
```

### Bước 3: Thay đổi Python backend

```python
# backend/main.py — sửa import và app setup
# Giữ nguyên: sys.path setup, dotenv loading, cuDNN compat

# backend/api/routers/ — thay thế bằng routers của bạn
# Ví dụ: image processing app
# routers/process_image.py, routers/filters.py, etc.

# pyproject.toml — thay dependencies
# Giữ nguyên: build-system, uv config
# Thay: dependencies list (bỏ torch, whisperx; thêm Pillow, opencv, etc.)
```

### Bước 4: Thay đổi React frontend

```typescript
// frontend/src/pages/ — thay thế bằng pages của bạn
// frontend/src/api/ — thay thế API calls
// frontend/src/store/ — thay thế Zustand slices

// GIỮ NGUYÊN:
// - api/client.ts (base HTTP client)
// - components/BootstrapSplash.jsx (splash screen)
// - ui/ (design system)
// - hooks/useRealtimeEvents.js (WebSocket hook)
```

### Bước 5: Cấu hình Tauri

```jsonc
// frontend/src-tauri/tauri.conf.json
{
  "productName": "My App",                    // ← Đổi tên
  "identifier": "com.myname.myapp",           // ← Đổi identifier
  "bundle": {
    "resources": [
      "../../pyproject.toml",                 // ← Giữ nguyên
      "../../uv.lock",                        // ← Giữ nguyên
      "../../README.md",                      // ← Giữ nguyên
      "../../backend"                         // ← Giữ nguyên
      // Bỏ "../../omnivoice" nếu không cần
    ]
  }
}
```

### Bước 6: Sửa bootstrap resources

Trong `bootstrap.rs`, sửa phần resource copy:

```rust
// Thay "omnivoice" bằng package name mới (nếu có)
let resource_omnivoice = ...;  // → đổi thành package của bạn
// Hoặc bỏ hoàn toàn nếu BE không cần package riêng
```

### Bước 7: Sửa install.sh

```bash
# scripts/install.sh — thay tên app
# Tìm-replace "OmniVoice" → "My App"
# Tìm-replace "omnivoice" → "myapp"
# Thay đổi Python dependencies nếu cần (uv sync tự đọc pyproject.toml)
```

### Checklist khi clone

| File | Cần sửa? | Ghi chú |
|---|---|---|
| `pyproject.toml` | ✅ | Đổi name, dependencies, scripts |
| `frontend/package.json` | ✅ | Đổi name |
| `frontend/src-tauri/Cargo.toml` | ✅ | Đổi name, description |
| `frontend/src-tauri/tauri.conf.json` | ✅ | Đổi productName, identifier, windows |
| `backend/main.py` | ✅ | Giữ infrastructure, sửa app logic |
| `backend/api/routers/` | ✅ | Thay thế hoàn toàn |
| `backend/services/` | ✅ | Thay thế hoàn toàn |
| `frontend/src/pages/` | ✅ | Thay thế hoàn toàn |
| `frontend/src/api/` | ✅ | Thay thế API calls, giữ client.ts |
| `frontend/src/store/` | ✅ | Thay thế Zustand slices |
| `frontend/src-tauri/src/lib.rs` | ⚠️ | Giữ nguyên 90%, sửa IPC commands |
| `frontend/src-tauri/src/bootstrap.rs` | ⚠️ | Giữ nguyên 90%, sửa resource names |
| `frontend/src-tauri/src/backend.rs` | ⚠️ | Giữ nguyên 90%, sửa health check |
| `frontend/src-tauri/src/tools.rs` | ❌ | Giữ nguyên (uv, ffmpeg resolve) |
| `frontend/src-tauri/src/config.rs` | ❌ | Giữ nguyên (region detection) |
| `frontend/src/components/BootstrapSplash.jsx` | ❌ | Giữ nguyên |
| `frontend/src/ui/` | ❌ | Giữ nguyên (design system) |
| `scripts/install.sh` | ⚠️ | Đổi tên app |
| `scripts/run.sh` | ⚠️ | Đổi tên app |
| `deploy/Dockerfile` | ⚠️ | Đổi tên, sửa deps nếu cần |
| `deploy/docker-compose.yml` | ⚠️ | Đổi tên |

---

## 12. File Map

### Auto-install system (BẮT BUỘC hiểu khi clone)

| File | Vai trò |
|---|---|
| `frontend/src-tauri/src/bootstrap.rs` | **Core**: Tạo Python venv, copy resources, run uv sync |
| `frontend/src-tauri/src/backend.rs` | Spawn backend process, health check, log management |
| `frontend/src-tauri/src/tools.rs` | Resolve uv/ffmpeg — bundled → cached → PATH → download |
| `frontend/src-tauri/src/config.rs` | Region detection, mirror routing, app config |
| `frontend/src-tauri/src/lib.rs` | Orchestration: setup → bootstrap → spawn → ready |
| `frontend/src/components/BootstrapSplash.jsx` | Splash UI: progress, logs, retry, region selector |

### Backend skeleton (GIỮ NGUYÊN pattern khi clone)

| File | Vai trò |
|---|---|
| `backend/main.py` | App entrypoint, sys.path setup, env loading |
| `backend/core/config.py` | App configuration |
| `backend/core/db.py` | Database (SQLite + Alembic) |
| `backend/core/event_bus.py` | Real-time event system |
| `backend/core/job_queue.py` | Async job queue |
| `backend/api/routers/system.py` | System info endpoint (health check target) |

### Frontend skeleton (GIỮ NGUYÊN pattern khi clone)

| File | Vai trò |
|---|---|
| `frontend/src/api/client.ts` | Base HTTP client (apiFetch, apiPost, apiJson) |
| `frontend/src/api/hooks.ts` | React Query hooks pattern |
| `frontend/src/ui/` | Design system components |
| `frontend/src/components/BootstrapSplash.jsx` | Bootstrap splash screen |
| `frontend/vite.config.js` | Vite config |
| `frontend/package.json` | Frontend deps |

### Build & deploy (GIỮ NGUYÊN pattern khi clone)

| File | Vai trò |
|---|---|
| `pyproject.toml` | Python project manifest (uv/hatch) |
| `uv.lock` | Python lockfile |
| `scripts/install.sh` | Universal installer |
| `scripts/run.sh` | Universal launcher |
| `deploy/Dockerfile` | Multi-stage Docker build |
| `deploy/docker-compose.yml` | Docker Compose config |
| `.github/workflows/release.yml` | CI/CD release pipeline |
