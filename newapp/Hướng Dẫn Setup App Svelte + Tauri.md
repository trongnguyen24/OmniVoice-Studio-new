# Hướng dẫn Xây dựng App TTS cho Extension (Svelte + Tauri + FastAPI)

Tài liệu này hướng dẫn cách "độ" lại bộ khung của [OmniVoice Studio](https://github.com/debpalash/OmniVoice-Studio) để tạo ra một Local API Server chạy ngầm, phục vụ việc tạo giọng nói (TTS) cho Browser Extension.

Chúng ta sẽ thay thế React bằng **Svelte 5** (siêu nhẹ) và dọn dẹp các module thừa của FastAPI.

## Bước 1: Clone Repo & Dọn dẹp phần thừa

Đầu tiên, clone bản gốc về để lấy cái "xương sống" Tauri và Bootstrap cực ngon của họ.

```
git clone [https://github.com/debpalash/OmniVoice-Studio.git](https://github.com/debpalash/OmniVoice-Studio.git) tts-local-server
cd tts-local-server

# Xóa các thư mục không cần thiết của OmniVoice
rm -rf omnivoice/ research/ examples/ docs/ design/

```

Xóa luôn thư mục frontend cũ (React) nhưng **phải giữ lại thư mục tauri**:

```
mv frontend/src-tauri ./src-tauri-backup
rm -rf frontend/

```

## Bước 2: Khởi tạo Svelte 5

Khởi tạo project Svelte mới bằng Vite (chọn template `svelte` hoặc `svelte-ts` tùy bác, ở đây tôi dùng JS thuần cho nhanh gọn).

```
bun create vite frontend --template svelte
cd frontend
bun install

# Cài thêm TailwindCSS v4 nếu bác cần làm UI quản lý giọng nói
bun add -D tailwindcss @tailwindcss/vite

```

Đưa thư mục `src-tauri` về lại vị trí cũ bên trong `frontend`:

```
mv ../src-tauri-backup ./src-tauri

```

## Bước 3: Cấu hình Tauri cho Svelte

Mở file `frontend/src-tauri/tauri.conf.json` lên. Thực ra cấu hình Vite của Svelte build ra thư mục `dist` y hệt React, nên bác gần như không phải sửa gì phần build, chỉ cần đổi tên App.

```
{
  "productName": "Local TTS Server",
  "identifier": "com.yourname.ttsserver",
  "build": {
    "frontendDist": "../dist",
    "devUrl": "http://localhost:5173",  // Đổi cổng này theo cổng dev của Vite Svelte (thường là 5173)
    "beforeDevCommand": "bun run dev",
    "beforeBuildCommand": "bun run build"
  },
  "bundle": {
    "resources": [
      "../../pyproject.toml",
      "../../uv.lock",
      "../../backend"
      // LƯU Ý: Xóa dòng "../../omnivoice" đi vì mình đã xóa thư mục này
    ]
  }
}

```

Mở `frontend/src-tauri/src/bootstrap.rs` và xóa dòng copy thư mục `omnivoice/` ở hàm `ensure_venv_ready()`.

## Bước 4: Chỉnh sửa Backend (FastAPI) & Sửa CORS cho Extension

Đây là bước quan trọng nhất. Trình duyệt sẽ chặn extension của bác gọi xuống `localhost:3900` nếu không có CORS hợp lệ.

Mở file `backend/main.py`.

**1. Thêm Origin của Extension vào biến `_allowed`:**

```
# Cấu hình danh sách các domain được phép gọi API (CORS)
_allowed = os.environ.get(
    "OMNIVOICE_ALLOWED_ORIGINS",
    "http://localhost:5173,tauri://localhost,[http://tauri.localhost](http://tauri.localhost),chrome-extension://*,moz-extension://*"
).split(",")

# Chú ý: Dấu * trong chrome-extension://* có thể bị một số trình duyệt chặn. 
# Cách an toàn nhất là fix cứng ID extension của bác, ví dụ:
# "chrome-extension://abcdefghijklmnopqrstuvwxyz123456"

```

**2. Xóa các Router thừa:**
Bác cuộn xuống chỗ `app.include_router(...)`. Xóa hết các router như `gallery`, `profiles`, `capture`, `watermark`... Chỉ giữ lại router của TTS và System.

## Bước 5: Viết API tạo TTS cho Extension

Tạo một file mới: `backend/api/routers/extension_tts.py`.

```
from fastapi import APIRouter, Request, HTTPException
from fastapi.responses import FileResponse
from pydantic import BaseModel
import os
import time

router = APIRouter(prefix="/api/ext", tags=["Extension API"])

class TTSRequest(BaseModel):
    text: str
    voice_id: str = "default"

@router.post("/generate")
async def generate_tts(req: TTSRequest):
    try:
        # 1. Gọi model TTS của bác ở đây (ví dụ: Kokoro, VITS, XTTS...)
        # output_path = my_tts_engine.synthesize(req.text, req.voice_id)
        
        # Mô phỏng file xuất ra
        output_path = os.path.join("outputs", f"tts_{time.time()}.wav")
        
        # 2. Trả về file âm thanh
        return FileResponse(
            path=output_path, 
            media_type="audio/wav", 
            filename="output.wav"
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

```

Nhớ import và add router này vào `backend/main.py`:

```
from api.routers import extension_tts
app.include_router(extension_tts.router)

```

## Bước 6: Gọi API từ Extension

Ở phía code Browser Extension (ví dụ trong `background.js` hoặc `content.js`), bác gọi xuống app nội bộ như sau:

```
async function fetchTTS(textToRead) {
  try {
    const response = await fetch("[http://127.0.0.1:3900/api/ext/generate](http://127.0.0.1:3900/api/ext/generate)", {
      method: "POST",
      headers: {
        "Content-Type": "application/json"
      },
      body: JSON.stringify({
        text: textToRead,
        voice_id: "my_cloned_voice"
      })
    });

    if (!response.ok) throw new Error("Local TTS Server error");

    // Lấy file audio dưới dạng Blob và phát
    const blob = await response.blob();
    const audioUrl = URL.createObjectURL(blob);
    const audio = new Audio(audioUrl);
    audio.play();

  } catch (err) {
    console.error("Lỗi khi gọi Local TTS App. Chắc app chưa bật?", err);
  }
}

```

## Tổng kết

Với cấu trúc này:

1. **Desktop App (Tauri + Svelte):** Dùng để người dùng cài đặt model (model checkpoint tải 1 lần lưu trên máy), clone giọng, chọn cấu hình.
1. **Backend (Python):** Chạy ngầm mô hình AI (PyTorch/ONNX), lắng nghe ở cổng `3900`.
1. **Extension:** Chỉ việc bắt text từ webpage và ném xuống cổng `3900`, lấy audio lên phát. Trình duyệt không bao giờ bị giật lag vì mô hình đã chạy ở process riêng của App.