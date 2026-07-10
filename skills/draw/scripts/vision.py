#!/usr/bin/env python3
"""Ollama Qwen3.6 Vision 图片分析工具（容器化版，Pillow 压缩）"""

import argparse
import base64
import json
import os
import subprocess
import sys
import time

MODEL = "qwen3.6:latest"
# 容器内通过 host.docker.internal 访问宿主 Ollama；本地直跑则用 localhost。
# 可用环境变量 OLLAMA_HOST 覆盖（如 OLLAMA_HOST=192.168.1.5）。
_OLLAMA_HOST = os.environ.get("OLLAMA_HOST", "host.docker.internal")
API_URL = f"http://{_OLLAMA_HOST}:11434/api/chat"
TAGS_URL = f"http://{_OLLAMA_HOST}:11434/api/tags"
DEFAULT_PROMPT = "请仔细描述这张图片中的所有内容，包括文字、布局、颜色等细节。"
MAX_DIM = 800  # 超过此尺寸自动压缩

MAGIC = {
    b"\xff\xd8": "JPEG",
    b"\x89PNG": "PNG",
    b"GIF8": "GIF",
    b"RIFF": "WEBP",
    b"II*\x00": "TIFF",
    b"MM\x00*": "TIFF",
}


def resolve_path(path: str) -> str:
    return os.path.expanduser(path)


def download_image(url: str, dest: str = "/tmp/vision_input.jpg") -> str:
    """下载远程图片（不走代理）"""
    try:
        subprocess.run(
            ["curl", "-s", "-L", "-o", dest, "--noproxy", "*", url],
            timeout=30, check=True,
        )
    except subprocess.CalledProcessError:
        print(f"错误: 下载失败 {url}", file=sys.stderr)
        sys.exit(1)
    if not os.path.exists(dest) or os.path.getsize(dest) < 100:
        print(f"错误: 下载的文件无效（可能返回了 HTML 而非图片）", file=sys.stderr)
        sys.exit(1)
    return dest


def compress_image(path: str) -> str:
    """超过 MAX_DIM 时用 Pillow 按比例缩放压缩（跨平台）"""
    try:
        from PIL import Image
        with Image.open(path) as im:
            w, h = im.size
            if max(w, h) > MAX_DIM:
                # 等比缩放，长边不超过 MAX_DIM
                scale = MAX_DIM / float(max(w, h))
                new_size = (max(1, int(w * scale)), max(1, int(h * scale)))
                # TIFF 等格式不支持 RGBA 直接存 JPEG，统一按原格式或转 PNG
                save_kwargs = {}
                fmt = im.format or "PNG"
                im_resized = im.resize(new_size, Image.LANCZOS)
                im_resized.save(path, format=fmt, **save_kwargs)
                print(f"[info] 图片已压缩: {w}x{h} -> {new_size[0]}x{new_size[1]}px", file=sys.stderr)
    except Exception as e:
        print(f"[info] 压缩跳过: {e}", file=sys.stderr)
    return path
    return path


def validate_image(path: str) -> str:
    """校验文件是否为有效图片"""
    if not os.path.exists(path):
        print(f"错误: 文件不存在 {path}", file=sys.stderr)
        sys.exit(1)
    with open(path, "rb") as f:
        header = f.read(8)
    fmt = None
    for magic, name in MAGIC.items():
        if header.startswith(magic):
            fmt = name
            break
    if fmt is None:
        print(f"错误: 不支持的图片格式（文件头: {header[:4].hex()}）", file=sys.stderr)
        sys.exit(1)
    return fmt


def check_ollama() -> bool:
    # 用 curl 探测：本机 urllib3 2.x 的 hface(HTTP/2) backend 与 Ollama 握手异常，
    # urllib 探测会误报未运行；curl 走 HTTP/1.1 稳定。
    try:
        r = subprocess.run(
            ["curl", "-s", "-m", "3", "-o", "/dev/null", "-w", "%{http_code}", TAGS_URL],
            capture_output=True, text=True, timeout=5,
        )
        return r.stdout.strip() == "200"
    except Exception:
        return False


def analyze(img_path: str, prompt: str, model: str) -> dict:
    """调用 Ollama API 分析图片"""
    with open(img_path, "rb") as f:
        img_b64 = base64.b64encode(f.read()).decode()

    payload = json.dumps({
        "model": model,
        "messages": [{"role": "user", "content": prompt, "images": [img_b64]}],
        "stream": False,
    })

    t0 = time.time()
    try:
        r = subprocess.run(
            ["curl", "-s", "-m", "180", "-w", "\n%{http_code}",
             "-X", "POST", API_URL,
             "-H", "Content-Type: application/json",
             "-d", payload],
            capture_output=True, text=True, timeout=200,
        )
    except FileNotFoundError:
        print("错误: 未找到 curl，请安装 curl 后重试", file=sys.stderr)
        sys.exit(1)

    out = r.stdout
    idx = out.rfind("\n")
    body, code = (out[:idx], out[idx + 1:]) if idx != -1 else (out, "000")
    elapsed = time.time() - t0

    if code != "200" or not body:
        print(f"错误: Ollama API 返回 HTTP {code}", file=sys.stderr)
        if body:
            print(f"响应: {body[:200]}", file=sys.stderr)
        sys.exit(1)

    try:
        data = json.loads(body)
    except json.JSONDecodeError:
        print(f"错误: 响应不是合法 JSON（前 200 字符: {body[:200]}）", file=sys.stderr)
        sys.exit(1)

    return {
        "content": data["message"]["content"],
        "model": data.get("model", model),
        "total_duration": data.get("total_duration", 0) / 1e9,
        "load_duration": data.get("load_duration", 0) / 1e9,
        "prompt_tokens": data.get("prompt_eval_count", 0),
        "gen_tokens": data.get("eval_count", 0),
        "elapsed": round(elapsed, 2),
    }


def main():
    parser = argparse.ArgumentParser(description="Ollama Vision 图片分析")
    parser.add_argument("image", help="图片路径或 URL")
    parser.add_argument("-p", "--prompt", default=DEFAULT_PROMPT, help="分析提示词")
    parser.add_argument("-m", "--model", default=MODEL, help="模型名称")
    parser.add_argument("--no-compress", action="store_true", help="禁用自动压缩")
    parser.add_argument("--json", action="store_true", help="输出 JSON 格式")
    args = parser.parse_args()

    if not check_ollama():
        print(f"错误: Ollama 不可达 ({_OLLAMA_HOST}:11434)，请确认宿主 Ollama 已启动且监听 0.0.0.0", file=sys.stderr)
        sys.exit(1)

    # 1. 获取图片本地路径
    input_str = args.image
    if input_str.startswith(("http://", "https://")):
        img_path = download_image(input_str)
        print(f"[info] 已下载: {img_path}", file=sys.stderr)
    else:
        img_path = resolve_path(input_str)

    # 2. 校验格式
    fmt = validate_image(img_path)
    print(f"[info] 格式: {fmt}, 大小: {os.path.getsize(img_path)} bytes", file=sys.stderr)

    # 3. 压缩
    if not args.no_compress:
        compress_image(img_path)

    # 4. 分析
    print(f"[info] 模型: {args.model}, 提示: {args.prompt[:30]}...", file=sys.stderr)
    result = analyze(img_path, args.prompt, args.model)

    # 5. 输出
    if args.json:
        print(json.dumps(result, ensure_ascii=False, indent=2))
    else:
        print()
        print(result["content"])
        print()
        print(f"--- 性能 ---")
        print(f"模型: {result['model']}")
        print(f"耗时: {result['elapsed']}s (推理 {result['total_duration']:.2f}s)")
        print(f"prompt tokens: {result['prompt_tokens']}, 生成 tokens: {result['gen_tokens']}")


if __name__ == "__main__":
    main()
