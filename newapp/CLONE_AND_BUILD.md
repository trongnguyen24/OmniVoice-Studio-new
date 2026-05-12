# OmniVoice Studio — Clone & Build Guide

> Tài liệu này dành cho developer muốn **clone repo và chạy OmniVoice Studio từ source** trên bất kỳ IDE nào (VS Code, Cursor, JetBrains, Zed, v.v...).
>
> OmniVoice Studio là ứng dụng desktop AI voice cloning, bao gồm: **Python backend** (FastAPI), **React frontend** (Vite + Tailwind), và **Rust desktop shell** (Tauri 2).

---

## Mục lục

1. [Tổng quan kiến trúc](#1-tổng-quan-kiến-trúc)
2. [Yêu cầu hệ thống](#2-yêu-cầu-hệ-thống)
3. [Clone & cài đặt nhanh (script tự động)](#3-cài-đặt-nhanh-script-tự-động)
4. [Cài đặt thủ công (từng bước)](#4-cài-đặt-thủ-công-từng-bước)
5. [Chạy ở các chế độ khác nhau](#5-chạy-ở-các-chế-độ-khác-nhau)
6. [Cấu trúc thư mục](#6-cấu-trúc-thư-mục)
7. [Tech Stack chi tiết](#7-tech-stack-chi-tiết)
8. [Cấu hình IDE](#8-cấu-hình-ide)
9. [Testing](#9-testing)
10. [Docker](#10-docker)
11. [Troubleshooting](#11-troubleshooting)

---

## 1. Tổng quan kiến trúc

```
┌─────────────────────────────────────────────────────────────┐
│                    Tauri 2 Desktop Shell (Rust)              │
│  ┌───────────────────────────────────────────────────────┐  │
│  │              React 19 Frontend (Vite)                  │  │
│  │   Pages · Components · Zustand Store · API Clients    │  │
│  └──────────────────────┬────────────────────────────────┘  │
│                         │ HTTP / WebSocket                   │
│  ┌──────────────────────▼────────────────────────────────┐  │
│  │              FastAPI Backend (Python 3.11+)            │  │
│  │   Routers · Services · Job Queue · Model Manager      │  │
│  └──────────────────────┬────────────────────────────────┘  │
│                         │                                    │
│  ┌──────────────────────▼────────────────────────────────┐  │
│  │              OmniVoice TTS Engine                      │  │
│  │   Zero-shot cloning · 646 languages · Diffusion LM    │  │
│  └───────────────────────────────────────────────────────┘  │
└─────────────────────────────────────────────────────────────┘
```

**3 phần chính:**

| Phần | Thư mục | Ngôn ngữ | Vai trò |
|---|---|---|---|
| **Backend** | `backend/` | Python 3.11+ | FastAPI server, business logic, model management |
| **Frontend** | `frontend/` | React 19 + TypeScript/JSX | UI, Zustand state, API clients |
| **Desktop Shell** | `frontend/src-tauri/` | Rust | Tauri wrapper, sidecar management, system integration |
| **TTS Engine** | `omnivoice/` | Python | Core model (zero-shot TTS, training, eval) |

**Port:** Backend chạy trên `http://127.0.0.1:3900`

---

## 2. Yêu cầu hệ thống

### Phần cứng

| | Tối thiểu | Khuyến nghị |
|---|---|---|
| **RAM** | 8 GB | 16 GB+ |
| **Disk** | 10 GB (code + models) | 20 GB+ (models ~5 GB khi chạy lần đầu) |
| **GPU** | Không bắt buộc (CPU được) | NVIDIA GPU (CUDA 12.x) hoặc Apple Silicon (MPS) |

### Phần mềm bắt buộc

| Tool | Phiên bản | Ghi chú |
|---|---|---|
| **Python** | ≥ 3.11 | `.python-version` file hiện tại: `3.11` |
| **Node.js** | ≥ 18 | Hoặc dùng **Bun** (khuyến nghị) |
| **Bun** | ≥ 1.0 | JS runtime + package manager (thay npm/yarn) |
| **uv** | ≥ 0.7.0 | Python package manager của Astral (thay pip) |
| **Rust** | ≥ 1.77.2 | Cần cho Tauri desktop build |
| **ffmpeg** | bất kỳ | Xử lý audio/video |
| **git** | bất kỳ | Clone repo |

### Platform hỗ trợ

| Platform | Desktop (Tauri) | Web-only | Docker |
|---|---|---|---|
| macOS Apple Silicon (arm64) | ✅ Primary target | ✅ | ✅ |
| macOS Intel (x64) | ✅ | ✅ | ✅ |
| Windows x64 | ✅ | ✅ | ✅ (WSL2) |
| Linux x64 (Debian/Fedora/Arch) | ✅ | ✅ | ✅ |

---

## 3. Cài đặt nhanh (Script tự động)

Repo có sẵn script `install.sh` tự động cài đặt tất cả dependencies:

```bash
# Clone repo
git clone https://github.com/debpalash/OmniVoice-Studio.git
cd OmniVoice-Studio

# Chạy installer (cài: ffmpeg, uv, bun, Python venv, frontend deps)
sh scripts/install.sh

# Hoặc chỉ định Python version khác
sh scripts/install.sh --python 3.12

# Sau đó chạy app
sh scripts/run.sh
```

Script `install.sh` sẽ tự động:
1. Cài Homebrew (macOS) hoặc system packages (Linux)
2. Cài `ffmpeg`
3. Cài `uv` (Python package manager)
4. Cài `bun` (JS runtime)
5. Tạo Python venv + `uv sync` (tất cả Python deps)
6. `bun install` + `bun run build` (frontend)

---

## 4. Cài đặt thủ công (từng bước)

Nếu bạn muốn kiểm soát từng bước, hoặc script tự động gặp lỗi:

### Bước 1: Clone repo

```bash
git clone https://github.com/debpalash/OmniVoice-Studio.git
cd OmniVoice-Studio
```

### Bước 2: Cài system dependencies

**macOS:**
```bash
# Xcode Command Line Tools
xcode-select --install

# Homebrew + ffmpeg
/bin/bash -c "$(curl -fsSL https://raw.githubusercontent.com/Homebrew/install/HEAD/install.sh)"
brew install ffmpeg
```

**Ubuntu/Debian:**
```bash
sudo apt-get update
sudo apt-get install -y ffmpeg libsndfile1 curl
```

**Fedora:**
```bash
sudo dnf install -y ffmpeg-free
```

**Arch:**
```bash
sudo pacman -S ffmpeg
```

**Windows:**
- Cài ffmpeg từ https://ffmpeg.org/download.html (thêm vào PATH)
- Hoặc dùng `winget install ffmpeg`

### Bước 3: Cài uv (Python package manager)

```bash
# macOS / Linux
curl -LsSf https://astral.sh/uv/install.sh | sh
source ~/.local/bin/env  # hoặc restart terminal

# Windows (PowerShell)
powershell -ExecutionPolicy ByPass -c "irm https://astral.sh/uv/install.ps1 | iex"

# Verify
uv --version  # cần ≥ 0.7.0
```

### Bước 4: Tạo Python venv + install dependencies

```bash
# Tạo venv với Python 3.11
uv venv --python 3.11

# Sync tất cả dependencies từ pyproject.toml + uv.lock
# (lần đầu tiên sẽ mất 5-10 phút, download torch + whisperx + demucs...)
uv sync

# Kích hoạt venv (nếu không dùng `uv run`)
source .venv/bin/activate   # macOS/Linux
# .venv\Scripts\activate    # Windows
```

### Bước 5: Cài Bun (JS runtime + package manager)

```bash
# macOS / Linux
curl -fsSL https://bun.sh/install | sh

# Windows
powershell -Command "irm bun.sh/install.ps1 | iex"

# Verify
bun --version
```

### Bước 6: Cài frontend dependencies

```bash
cd frontend
bun install
cd ..
```

### Bước 7: Build frontend (cho production / desktop mode)

```bash
cd frontend
bun run build    # Output → frontend/dist/
cd ..
```

---

## 5. Chạy ở các chế độ khác nhau

### Chế độ 1: Web mode (nhanh nhất để dev)

Chạy backend + frontend dev server riêng biệt:

```bash
# Terminal 1 — Backend (FastAPI)
uv run uvicorn main:app --app-dir backend --host 127.0.0.1 --port 3900

# Terminal 2 — Frontend dev server (Vite HMR)
cd frontend && bun run dev
# → http://localhost:3901 (Vite dev server, proxy API → :3900)
```

### Chế độ 2: Production web mode (dùng build output)

```bash
# Build frontend trước
cd frontend && bun run build && cd ..

# Chạy backend serve cả API + static frontend
uv run uvicorn main:app --app-dir backend --host 127.0.0.1 --port 3900
# → http://localhost:3900 (serve frontend/dist/ luôn)
```

Hoặc dùng script:
```bash
sh scripts/run.sh
# Tự động start backend, chờ healthy, mở browser
```

### Chế độ 3: Desktop mode (Tauri)

```bash
cd frontend

# Dev mode (hot-reload cả React + Rust)
bun run desktop    # = `tauri dev`

# Production build (tạo .dmg / .msi / .AppImage / .deb)
bun run tauri build
```

**Lưu ý:** Tauri desktop mode tự động quản lý backend sidecar (không cần start backend thủ công).

### Chế độ 4: Docker

```bash
# CPU mode
docker compose -f deploy/docker-compose.yml up

# GPU mode (cần NVIDIA GPU + nvidia-docker)
docker compose -f deploy/docker-compose.yml --profile gpu up

# → http://localhost:3900
```

### Chế độ 5: CLI (không cần UI)

```bash
# TTS inference
uv run omnivoice-infer --text "Hello world" --output output.wav

# Batch inference
uv run omnivoice-infer-batch --input texts.txt --output-dir outputs/

# Video dubbing
uv run omnivoice-dub --input video.mp4 --target-lang es --output dubbed.mp4
```

---

## 6. Cấu trúc thư mục

```
OmniVoice-Studio/
│
├── README.md                    # User-facing overview
├── CLONE_AND_BUILD.md           # ← Bạn đang đọc file này
├── CHANGELOG.md                 # Release history
├── LICENSE                      # FSL-1.1-ALv2
│
├── pyproject.toml               # Python project manifest (uv/hatch)
├── uv.lock                      # Python lockfile
├── .python-version              # Python version: 3.11
├── package.json                 # Monorepo root (Bun workspaces + Turborepo)
├── bun.lock                     # JS lockfile
├── turbo.json                   # Turborepo pipeline config
├── alembic.ini                  # DB migration config
│
├── backend/                     # ── FastAPI Server ──
│   ├── main.py                  # App entrypoint (uvicorn)
│   ├── mcp_server.py            # MCP server (Claude/Cursor integration)
│   ├── api/
│   │   ├── routers/             # HTTP endpoints
│   │   │   ├── generation.py    # TTS generation
│   │   │   ├── dub_core.py      # Video dubbing
│   │   │   ├── dub_translate.py # Translation for dubbing
│   │   │   ├── dub_export.py    # Export dubbed video
│   │   │   ├── batch.py         # Batch queue
│   │   │   ├── capture.py       # Dictation widget
│   │   │   ├── engines.py       # TTS engine management
│   │   │   ├── profiles.py      # Voice profiles
│   │   │   ├── projects.py      # Project management
│   │   │   ├── gallery.py       # Voice gallery
│   │   │   ├── marketplace.py   # Voice marketplace
│   │   │   ├── watermark.py     # AI watermark (AudioSeal)
│   │   │   ├── openai_compat.py # OpenAI-compatible API
│   │   │   └── setup/           # First-run wizard
│   │   └── schemas.py           # Pydantic models
│   ├── core/
│   │   ├── config.py            # App configuration
│   │   ├── db.py                # Database (SQLite + Alembic)
│   │   ├── event_bus.py         # Event system
│   │   ├── job_queue.py         # Async job queue
│   │   ├── job_store.py         # Job persistence
│   │   └── prefs.py             # User preferences
│   ├── services/
│   │   ├── tts_backend.py       # TTS engine abstraction
│   │   ├── asr_backend.py       # ASR (Whisper/WhisperX)
│   │   ├── dub_pipeline.py      # Video dubbing pipeline
│   │   ├── translation_engines.py # Translation backends
│   │   ├── model_manager.py     # Model download/management
│   │   ├── audio_dsp.py         # Audio processing
│   │   ├── watermark.py         # AudioSeal watermarking
│   │   ├── rvc.py               # Voice conversion (RVC)
│   │   ├── speaker_clone.py     # Speaker cloning
│   │   ├── ffmpeg_utils.py      # FFmpeg utilities
│   │   └── plugin_sdk.py        # Plugin system
│   ├── config/
│   │   └── models.yaml          # Model registry
│   ├── migrations/              # Alembic DB migrations
│   ├── hooks/                   # PyInstaller runtime hooks
│   └── tests/                   # Backend-specific tests
│
├── frontend/                    # ── React + Tauri ──
│   ├── package.json             # Frontend deps & scripts
│   ├── vite.config.js           # Vite config
│   ├── index.html               # HTML entry
│   ├── src/
│   │   ├── App.jsx              # Root component
│   │   ├── main.jsx             # React entry
│   │   ├── main-app.jsx         # Main app logic
│   │   ├── pages/               # Top-level views
│   │   │   ├── Launchpad.jsx    # Home/dashboard
│   │   │   ├── CloneDesignTab.jsx  # Voice cloning + design
│   │   │   ├── DubTab.jsx       # Video dubbing
│   │   │   ├── BatchQueue.jsx   # Batch processing
│   │   │   ├── VoiceGallery.jsx # Voice library
│   │   │   ├── VoiceProfile.jsx # Voice profiles
│   │   │   ├── Settings.jsx     # App settings
│   │   │   ├── SetupWizard.jsx  # First-run wizard
│   │   │   ├── ToolsPage.jsx    # Audio tools
│   │   │   └── Transcriptions.jsx # Transcription viewer
│   │   ├── components/          # Reusable UI components
│   │   ├── api/                 # Typed API clients (fetch wrappers)
│   │   │   ├── client.ts        # Base HTTP client
│   │   │   ├── generate.ts      # TTS generation API
│   │   │   ├── dub.ts           # Dubbing API
│   │   │   ├── batch.ts         # Batch API
│   │   │   ├── engines.ts       # Engine management API
│   │   │   └── hooks.ts         # React Query hooks
│   │   ├── store/               # Zustand state slices
│   │   ├── hooks/               # Custom React hooks
│   │   ├── ui/                  # Design system (Button, Dialog, etc.)
│   │   ├── i18n/                # Internationalization
│   │   └── utils/               # Utility functions
│   └── src-tauri/               # ── Rust/Tauri Desktop Shell ──
│       ├── Cargo.toml           # Rust dependencies
│       ├── tauri.conf.json      # Tauri config (windows, bundling, security)
│       ├── src/
│       │   ├── main.rs          # Rust entrypoint
│       │   ├── lib.rs           # Tauri setup + sidecar management
│       │   ├── backend.rs       # Backend sidecar launcher
│       │   ├── bootstrap.rs     # First-run bootstrap (install uv, venv)
│       │   ├── commands.rs      # IPC commands (sysinfo, etc.)
│       │   ├── config.rs        # Config file management
│       │   └── tools.rs         # System tool detection
│       └── icons/               # App icons (all platforms)
│
├── omnivoice/                   # ── Core TTS Model Package ──
│   ├── models/
│   │   └── omnivoice.py         # Main TTS model
│   ├── cli/                     # CLI entry points
│   │   ├── infer.py             # Single inference
│   │   ├── infer_batch.py       # Batch inference
│   │   ├── dub.py               # CLI dubbing
│   │   └── train.py             # Training CLI
│   ├── data/                    # Data processing
│   ├── training/                # Training pipeline
│   ├── eval/                    # Evaluation (WER, MOS, speaker sim)
│   ├── utils/                   # Audio, text, language utilities
│   └── scripts/                 # Utility scripts
│
├── tests/                       # All tests (backend + frontend)
│   ├── conftest.py              # Pytest fixtures
│   ├── test_api.py              # API integration tests
│   ├── test_dub_*.py            # Dubbing pipeline tests
│   ├── test_job_queue.py        # Job queue tests
│   └── frontend/                # JS/TS tests (Node test runner)
│
├── scripts/                     # Dev / build / release scripts
│   ├── install.sh               # Universal installer
│   ├── run.sh                   # Universal launcher
│   ├── smoke-test.sh            # E2E validation
│   ├── desktop-prod.sh          # Production desktop build
│   └── setup_cudnn.py           # cuDNN 8 compat setup
│
├── deploy/                      # Docker deployment
│   ├── Dockerfile               # Multi-stage (bun build → pytorch runtime)
│   └── docker-compose.yml       # CPU + GPU profiles
│
├── docs/                        # Developer docs
│   ├── STRUCTURE.md             # Project structure guide
│   ├── ROADMAP.md               # Feature roadmap
│   ├── mcp.json                 # MCP config template
│   ├── languages.md             # Supported languages
│   ├── training.md              # Training guide
│   └── voice-design.md          # Voice design docs
│
├── design/                      # UX mockups (ASCII)
│   └── 00-08-*.md               # Per-feature specs
│
├── examples/                    # Sample configs + demo scripts
│   └── config/                  # Training data configs
│
└── research/                    # Reference material, legacy code
    └── legacy_gradio/           # Archived Gradio UI
```

---

## 7. Tech Stack chi tiết

### Backend (Python)

| Component | Technology | Version |
|---|---|---|
| **Web framework** | FastAPI + Uvicorn | latest |
| **Package manager** | uv (Astral) | ≥ 0.7.0 |
| **Build system** | Hatchling | latest |
| **TTS engine** | OmniVoice (custom diffusion LM) | 0.2.7 |
| **ASR** | WhisperX + faster-whisper | ≥ 3.1.0 / ≥ 1.0.0 |
| **ASR (macOS ARM)** | mlx-whisper | ≥ 0.2.1 |
| **Voice conversion** | RVC (Retrieval-based Voice Conversion) | - |
| **Speaker diarization** | pyannote-audio | ≥ 3.3.2, < 4.0 |
| **Vocal isolation** | Demucs | ≥ 4.0.1 |
| **Audio watermark** | AudioSeal (Meta) | ≥ 0.1.3 |
| **Video download** | yt-dlp | ≥ 2024.12.13 |
| **Audio processing** | pedalboard, pydub, soundfile | - |
| **Deep Learning** | PyTorch + torchaudio | ≥ 2.8.0 |
| **Transformers** | HuggingFace transformers | ≥ 5.3.0 |
| **Database** | SQLite + Alembic migrations | - |
| **MLX engines (macOS)** | mlx-audio | ≥ 0.3.0 |
| **Fast English TTS** | KittenTTS (ONNX) | 0.8.1 |
| **OpenAI-compat API** | Built-in | - |
| **MCP Server** | mcp SDK | - |

### Frontend (JavaScript/TypeScript)

| Component | Technology | Version |
|---|---|---|
| **UI framework** | React | 19.x |
| **Build tool** | Vite | 8.x |
| **JS runtime** | Bun | ≥ 1.0 |
| **Styling** | Tailwind CSS | 4.x |
| **State management** | Zustand | 5.x |
| **Data fetching** | TanStack React Query | 5.x |
| **UI primitives** | Radix UI (Dialog, Select, Slider, etc.) | latest |
| **Audio visualization** | wavesurfer.js | 7.x |
| **i18n** | i18next + react-i18next | 26.x / 17.x |
| **Icons** | Lucide React | latest |
| **Tables** | TanStack React Table | 8.x |
| **Virtualization** | TanStack React Virtual + react-window | latest |

### Desktop Shell (Rust)

| Component | Technology | Version |
|---|---|---|
| **Desktop framework** | Tauri | 2.11.0 |
| **Rust edition** | - | 2021 |
| **Min Rust version** | - | 1.77.2 |
| **Keyboard sim** | enigo | 0.3 |
| **HTTP client** | ureq | 2 |
| **System info** | sysinfo | 0.33 |
| **File walking** | walkdir | 2 |
| **Plugins** | dialog, updater, process, global-shortcut, single-instance | v2 |

### GPU Support

| Backend | Detection | Ghi chú |
|---|---|---|
| **NVIDIA CUDA** | auto (cu128) | PyTorch 2.8 + CUDA 12.8 |
| **Apple MPS** | auto (arm64) | Metal Performance Shaders |
| **AMD ROCm** | auto | Nếu `rocminfo` available |
| **CPU** | fallback | Tự động nếu không có GPU |

---

## 8. Cấu hình IDE

### VS Code / Cursor

Tạo `.vscode/settings.json`:

```json
{
  "python.defaultInterpreterPath": "${workspaceFolder}/.venv/bin/python",
  "python.terminal.activateEnvironment": true,
  "typescript.tsdk": "frontend/node_modules/typescript/lib",
  "eslint.workingDirectories": ["frontend"],
  "editor.formatOnSave": true,
  "[python]": {
    "editor.defaultFormatter": "ms-python.black-formatter",
    "editor.formatOnSave": true
  },
  "[javascript]": {
    "editor.defaultFormatter": "esbenp.prettier-vscode"
  },
  "[typescript]": {
    "editor.defaultFormatter": "esbenp.prettier-vscode"
  }
}
```

Tạo `.vscode/launch.json` cho debug:

```json
{
  "version": "0.2.0",
  "configurations": [
    {
      "name": "Python: Backend",
      "type": "debugpy",
      "request": "launch",
      "module": "uvicorn",
      "args": ["main:app", "--app-dir", "backend", "--host", "127.0.0.1", "--port", "3900"],
      "cwd": "${workspaceFolder}",
      "python": "${workspaceFolder}/.venv/bin/python",
      "env": {
        "PYTHONPATH": "${workspaceFolder}/backend"
      }
    },
    {
      "name": "Frontend: Vite Dev",
      "type": "node",
      "request": "launch",
      "runtimeExecutable": "bun",
      "args": ["run", "dev"],
      "cwd": "${workspaceFolder}/frontend",
      "console": "integratedTerminal"
    }
  ]
}
```

Extensions khuyến nghị:
- Python (ms-python)
- Pylance
- ESLint
- Tailwind CSS IntelliSense
- rust-analyzer (cho Tauri/Rust)
- Tauri (tauri-apps.tauri-vscode)

### JetBrains (WebStorm / IntelliJ / PyCharm)

1. **Python interpreter:** Settings → Python Interpreter → Add → Existing → `.venv/bin/python`
2. **Node.js:** Settings → Node.js → Bun runtime (hoặc Node.js path)
3. **Rust:** Cài Rust plugin → Cargo.toml auto-detect
4. **Run configs:**
   - Python: Module `uvicorn`, args `main:app --app-dir backend --port 3900`
   - Bun: Script `dev` trong `frontend/package.json`

### Zed

Zed tự detect Rust (rust-analyzer) và TypeScript. Cần manual setup Python:
- `zed: settings` → `terminal.env.PATH` → thêm `.venv/bin`

---

## 9. Testing

```bash
# Chạy tất cả tests
uv run pytest tests/ -v

# Backend tests only
uv run pytest tests/test_api.py tests/test_job_queue.py -v

# Dubbing pipeline tests
uv run pytest tests/test_dub_*.py -v

# Frontend tests (Node.js test runner)
cd frontend && bun run test

# Smoke test (E2E, cần backend đang chạy)
sh scripts/smoke-test.sh
```

---

## 10. Docker

### Build từ source

```bash
# Build image
docker build -f deploy/Dockerfile -t omnivoice-studio .

# Run
docker run -p 127.0.0.1:3900:3900 omnivoice-studio
```

### Docker Compose

```bash
# CPU mode
docker compose -f deploy/docker-compose.yml up

# GPU mode (NVIDIA)
docker compose -f deploy/docker-compose.yml --profile gpu up

# Với custom HF token (cho private models)
HF_TOKEN=hf_xxx docker compose -f deploy/docker-compose.yml up
```

### Volume mounts

| Volume | Chứa |
|---|---|
| `omnivoice-data` | SQLite DB, HuggingFace cache, voice profiles |

---

## 11. Troubleshooting

### Lỗi phổ biến

**`uv sync` fails với torch/CUDA errors:**
```bash
# Kiểm tra CUDA version
nvidia-smi

# Nếu CUDA < 12.8, sửa pyproject.toml:
# [[tool.uv.index]]
# url = "https://download.pytorch.org/whl/cu124"  # đổi cu128 → cu124
```

**`bun install` fails:**
```bash
# Xóa lockfile và thử lại
rm bun.lock
bun install
```

**Backend không start (port 3900 bị chiếm):**
```bash
# Tìm process đang dùng port
lsof -i :3900
# Kill nó
kill -9 <PID>
```

**Tauri build lỗi trên Linux:**
```bash
# Cài webkit2gtk
sudo apt-get install -y libwebkit2gtk-4.1-dev libappindicator3-dev \
  librsvg2-dev patchelf libssl-dev libgtk-3-dev
```

**cuDNN errors (CTranslate2/WhisperX):**
```bash
# Setup cuDNN 8 compat
uv run python scripts/setup_cudnn.py
```

**Models download chậm:**
```bash
# Set HF mirror (Trung Quốc)
export HF_ENDPOINT=https://hf-mirror.com

# Hoặc set custom cache dir
export OMNIVOICE_CACHE_DIR=/path/to/cache
```

**Frontend không kết nối backend:**
- Đảm bảo backend đang chạy trên port 3900
- Check CORS settings trong `backend/main.py`
- Vite dev server proxy: xem `frontend/vite.config.js`

### Logs

| Platform | Log location |
|---|---|
| macOS | `~/Library/Application Support/OmniVoice/omnivoice.log` |
| Linux | `~/.local/share/OmniVoice/omnivoice.log` |
| Windows | `%APPDATA%\OmniVoice\omnivoice.log` |
| Docker | `docker logs omnivoice-studio` |

---

## Quick Reference — Các lệnh thường dùng

```bash
# ── Setup ──
sh scripts/install.sh                    # Cài đặt tự động

# ── Run ──
sh scripts/run.sh                        # Chạy production web mode
cd frontend && bun run desktop           # Chạy desktop mode (Tauri dev)
docker compose -f deploy/docker-compose.yml up  # Chạy Docker

# ── Dev ──
uv run uvicorn main:app --app-dir backend --port 3900 --reload  # Backend hot-reload
cd frontend && bun run dev               # Frontend HMR (Vite)
cd frontend && bun run build             # Build frontend
cd frontend && bun run tauri build       # Build desktop app

# ── Test ──
uv run pytest tests/ -v                  # Python tests
cd frontend && bun run test              # JS tests
sh scripts/smoke-test.sh                 # E2E smoke test

# ── CLI ──
uv run omnivoice-infer --text "..." --output out.wav  # TTS inference
uv run omnivoice-dub --input video.mp4 --target-lang es  # Dubbing

# ── MCP Server ──
uv run python -m backend.mcp_server      # stdio (Claude Desktop)
uv run python -m backend.mcp_server --sse  # SSE (remote agents)
```
