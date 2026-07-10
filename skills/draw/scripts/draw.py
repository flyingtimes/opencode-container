#!/usr/bin/env python3
"""Ollama x/z-image-turbo 图片生成工具"""

import argparse
import base64
import json
import os
import subprocess
import sys

MODEL = "x/z-image-turbo:bf16"
# 容器内通过 host.docker.internal 访问宿主 Ollama；本地直跑则用 localhost。
# 可用环境变量 OLLAMA_HOST 覆盖（如 OLLAMA_HOST=192.168.1.5）。
_OLLAMA_HOST = os.environ.get("OLLAMA_HOST", "host.docker.internal")
API_URL = f"http://{_OLLAMA_HOST}:11434/api/generate"
DEFAULT_OUTPUT_DIR = os.path.expanduser(os.environ.get("DRAW_OUTPUT_DIR", "/workspace/output"))


def generate(prompt: str, output: str = None) -> str:
    """调用 Ollama 生成图片，返回保存路径"""
    if not output:
        ts = __import__("time").strftime("%Y%m%d_%H%M%S")
        output = os.path.join(DEFAULT_OUTPUT_DIR, f"draw_{ts}.png")

    payload = json.dumps({
        "model": MODEL,
        "prompt": prompt,
        "stream": False,
        "raw": True,
    })

    # 用 curl 而非 urllib/requests：本机 urllib3 2.x 的 hface(HTTP/2) backend
    # 与 Ollama GIN 在 raw 图片生成端点握手异常会重置连接；curl 走 HTTP/1.1 稳定。
    try:
        r = subprocess.run(
            ["curl", "-s", "-m", "300", "-w", "\n%{http_code}",
             "-X", "POST", API_URL,
             "-H", "Content-Type: application/json",
             "-d", payload],
            capture_output=True, text=True, timeout=320,
        )
    except FileNotFoundError:
        print("错误: 未找到 curl，请安装 curl 后重试", file=sys.stderr)
        sys.exit(1)

    out = r.stdout
    idx = out.rfind("\n")
    body, code = (out[:idx], out[idx + 1:]) if idx != -1 else (out, "000")
    if code != "200" or not body:
        if code == "000":
            print(f"错误: 无法连接 Ollama ({_OLLAMA_HOST}:11434)，请确认宿主 Ollama 已启动且监听 0.0.0.0", file=sys.stderr)
        else:
            print(f"错误: Ollama 返回 HTTP {code}", file=sys.stderr)
            if body:
                print(f"响应: {body[:200]}", file=sys.stderr)
        sys.exit(1)

    try:
        data = json.loads(body)
    except json.JSONDecodeError:
        print(f"错误: 响应不是合法 JSON（前 200 字符: {body[:200]}）", file=sys.stderr)
        sys.exit(1)

    if "image" not in data:
        print(f"错误: 模型未返回图片，响应 keys: {list(data.keys())}", file=sys.stderr)
        if data.get("response"):
            print(f"文本响应: {data['response'][:200]}", file=sys.stderr)
        sys.exit(1)

    os.makedirs(os.path.dirname(output) or ".", exist_ok=True)
    img_bytes = base64.b64decode(data["image"])
    with open(output, "wb") as f:
        f.write(img_bytes)

    print(f"OK:{output}:{len(img_bytes)}")
    return output


def main():
    global MODEL
    p = argparse.ArgumentParser(description="Ollama 图片生成")
    p.add_argument("prompt", help="图片描述（英文效果更好）")
    p.add_argument("-o", "--output", help="输出路径（默认 ~/Downloads/draw_时间戳.png）")
    p.add_argument("-m", "--model", default=MODEL, help="Ollama 模型")
    args = p.parse_args()

    if args.model != MODEL:
        MODEL = args.model
    generate(args.prompt, args.output)


if __name__ == "__main__":
    main()
