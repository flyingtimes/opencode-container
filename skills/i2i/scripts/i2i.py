#!/usr/bin/env python3
"""FLUX.2 图生图工具（基于 flux2cli）— 将参考图片按文字描述变换/风格迁移"""

import argparse
import os
import subprocess
import sys
import time
from pathlib import Path

# flux2 CLI 路径：宿主机 ~/bin/flux2 或容器内 flux2
FLUX2 = os.environ.get("FLUX2_CLI", "flux2")
DEFAULT_OUTPUT_DIR = os.path.expanduser(
    os.environ.get("I2I_OUTPUT_DIR", os.path.join(os.path.expanduser("~"), "Downloads"))
)


def transform(
    prompt: str,
    images: list[str],
    output: str | None = None,
    strength: float = 0.7,
    steps: int = 28,
    guidance: float = 4.0,
    width: int | None = None,
    height: int | None = None,
    seed: int | None = None,
    model: str = "dev",
    text_quant: str = "8bit",
    transformer_quant: str = "qint8",
    upsample_prompt: bool = False,
    checkpoint: int | None = None,
    extra_args: list[str] | None = None,
) -> str:
    """调用 flux2 i2i 进行图生图，返回输出文件路径"""

    # 校验输入图片
    for img in images:
        p = Path(img)
        if not p.exists():
            print(f"错误: 参考图片不存在: {img}", file=sys.stderr)
            sys.exit(1)
        if p.stat().st_size < 100:
            print(f"错误: 参考图片无效（过小）: {img}", file=sys.stderr)
            sys.exit(1)

    # 生成默认输出路径
    if not output:
        ts = time.strftime("%Y%m%d_%H%M%S")
        ext = Path(images[0]).suffix or ".png"
        output = os.path.join(DEFAULT_OUTPUT_DIR, f"i2i_{ts}{ext}")

    # 确保输出目录存在
    os.makedirs(os.path.dirname(output) or ".", exist_ok=True)

    # 构造命令
    cmd = [FLUX2, "i2i", prompt]
    for img in images:
        cmd += ["--images", img]
    cmd += ["--output", output]
    cmd += ["--steps", str(steps)]
    cmd += ["--guidance", str(guidance)]
    if width:
        cmd += ["--width", str(width)]
    if height:
        cmd += ["--height", str(height)]
    if seed is not None:
        cmd += ["--seed", str(seed)]
    cmd += ["--model", model]
    cmd += ["--text-quant", text_quant]
    cmd += ["--transformer-quant", transformer_quant]
    # 必须指定 standard VAE（我们下载的是 standard，非 small-decoder）
    cmd += ["--vae-variant", "standard"]
    if upsample_prompt:
        cmd.append("--upsample-prompt")
    if checkpoint:
        cmd += ["--checkpoint", str(checkpoint)]
    if extra_args:
        cmd += extra_args

    print(f"[i2i] 模型: {model} ({text_quant}/{transformer_quant})", file=sys.stderr)
    print(f"[i2i] 参考图: {', '.join(images)}", file=sys.stderr)
    print(f"[i2i] 强度: {strength}, 步数: {steps}, 引导: {guidance}", file=sys.stderr)
    print(f"[i2i] 输出: {output}", file=sys.stderr)
    print(f"[i2i] 命令: {' '.join(cmd)}", file=sys.stderr)
    print(file=sys.stderr)

    # 执行
    try:
        result = subprocess.run(
            cmd, capture_output=False, timeout=7200  # 2小时超时（dev 模型较慢）
        )
    except FileNotFoundError:
        print(f"错误: 未找到 flux2 CLI，请确认 {FLUX2} 已安装", file=sys.stderr)
        sys.exit(1)
    except subprocess.TimeoutExpired:
        print("错误: 生成超时（>2小时）", file=sys.stderr)
        sys.exit(1)

    if result.returncode != 0:
        print(f"错误: flux2 返回非零退出码 {result.returncode}", file=sys.stderr)
        sys.exit(1)

    # 校验输出文件
    if not os.path.exists(output):
        print(f"错误: 输出文件未生成: {output}", file=sys.stderr)
        sys.exit(1)

    size = os.path.getsize(output)
    if size < 1000:
        print(f"错误: 输出文件过小（{size} bytes），可能生成失败", file=sys.stderr)
        sys.exit(1)

    size_h = f"{size / 1024 / 1024:.1f}MB" if size > 1024 * 1024 else f"{size / 1024:.0f}KB"
    print(f"OK:{output}:{size}")


def main():
    p = argparse.ArgumentParser(
        description="FLUX.2 图生图 — 用文字描述变换/风格迁移参考图片",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
示例:
  # 基本图生图（风格迁移）
  python3 i2i.py "transform into a watercolor painting" -i photo.jpg

  # 低强度（保留更多原图结构）
  python3 i2i.py "add autumn colors" -i landscape.jpg --strength 0.3

  # 多图参考（合成元素）
  python3 i2i.py "a cat wearing this jacket" -i cat.jpg -i jacket.jpg --strength 1.0

  # 指定尺寸和种子
  python3 i2i.py "cyberpunk style" -i portrait.jpg -w 1024 -h 1024 --seed 42

强度指南:
  1.0 = 完全重新生成（参考图仅提供视觉提示）
  0.8 = 默认（20%保留原图，80%新生成）
  0.5 = 50/50 混合
  0.3 = 轻微修改（保留70%原图）
        """,
    )
    p.add_argument("prompt", help="描述期望输出的文字（英文效果更好）")
    p.add_argument(
        "-i",
        "--images",
        action="append",
        required=True,
        help="参考图片路径（可多次指定，最多6张）",
    )
    p.add_argument("-o", "--output", help="输出路径（默认 ~/Downloads/i2i_时间戳.png）")
    p.add_argument(
        "--strength", type=float, default=0.7, help="去噪强度 0.0-1.0（默认0.7，越低保留越多原图）"
    )
    p.add_argument("-s", "--steps", type=int, default=28, help="去噪步数（默认28）")
    p.add_argument("-g", "--guidance", type=float, default=4.0, help="引导系数（默认4.0）")
    p.add_argument("-w", "--width", type=int, help="输出宽度（默认跟随参考图）")
    p.add_argument("--height", type=int, help="输出高度（默认跟随参考图）")
    p.add_argument("--seed", type=int, help="随机种子（可复现）")
    p.add_argument("--model", default="dev", choices=["dev", "klein-4b", "klein-9b"], help="模型（默认dev）")
    p.add_argument("--text-quant", default="8bit", choices=["bf16", "8bit", "6bit", "4bit"])
    p.add_argument(
        "--transformer-quant", default="qint8", choices=["bf16", "qint8", "int4", "mxfp8", "mxfp4", "nvfp4"]
    )
    p.add_argument("--upsample-prompt", action="store_true", help="用 Mistral 增强提示词")
    p.add_argument("--checkpoint", type=int, help="每N步保存中间图片")
    args = p.parse_args()

    # 参数范围校验
    if not (0.0 <= args.strength <= 1.0):
        p.error("--strength 必须在 0.0-1.0 之间")
    if len(args.images) > 6:
        p.error("最多支持6张参考图")
    if len(args.images) >= 2 and args.strength < 1.0:
        print("[i2i] 多图参考建议 strength=1.0（多图模式下低强度无意义）", file=sys.stderr)

    transform(
        prompt=args.prompt,
        images=args.images,
        output=args.output,
        strength=args.strength,
        steps=args.steps,
        guidance=args.guidance,
        width=args.width,
        height=args.height,
        seed=args.seed,
        model=args.model,
        text_quant=args.text_quant,
        transformer_quant=args.transformer_quant,
        upsample_prompt=args.upsample_prompt,
        checkpoint=args.checkpoint,
    )


if __name__ == "__main__":
    main()
