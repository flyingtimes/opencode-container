---
name: i2i
description: >
  FLUX.2 图生图（image-to-image）技能：基于参考图片，用文字描述进行风格迁移、
  内容变换、元素合成。支持单图变换和多图参考融合。
  当用户要求图生图、风格转换、给图片加效果、图片变形、参考图生成、
  image-to-image、img2img、参考这张图重新画时触发。
  依赖宿主机安装的 flux2cli（基于 Apple MLX，FLUX.2-dev 模型）。
---

# FLUX.2 图生图（Image-to-Image）

基于 [flux2cli](https://github.com/VincentGourbin/flux-2-swift-mlx)（Apple MLX 原生实现），用文字描述变换参考图片。

| | |
|---|---|
| 模型 | FLUX.2-dev (32B, qint8 量化) |
| 引擎 | flux2cli → Apple MLX（宿主机原生运行，非容器） |
| 脚本 | scripts/i2i.py |
| 输出 | PNG → ~/Downloads/（或 $I2I_OUTPUT_DIR） |
| 生成耗时 | 约 3-5 分钟/张（10步，1024×1024，dev qint8） |

## 执行步骤

1. 确认用户提供了**至少一张参考图片**（图生图必须有输入图）
2. 将用户的描述意图转为英文 prompt（英文效果显著优于中文）
3. 用 Bash 调用脚本：
```bash
python3 skills/i2i/scripts/i2i.py "<英文prompt>" -i <参考图路径> [选项]
```
4. 脚本输出格式：`OK:<路径>:<字节数>`
5. 告知用户文件路径

## 命令示例

```bash
# 风格迁移：照片 → 油画
python3 skills/i2i/scripts/i2i.py "transform into an oil painting, thick impressionist brush strokes, Van Gogh style" -i photo.jpg

# 水彩画风格
python3 skills/i2i/scripts/i2i.py "soft watercolor painting, delicate brush strokes, pastel colors" -i photo.jpg

# 多图合成：猫穿这件夹克
python3 skills/i2i/scripts/i2i.py "a cat wearing this jacket" -i cat.jpg -i jacket.jpg

# 指定尺寸 + 可复现
python3 skills/i2i/scripts/i2i.py "cyberpunk neon portrait" -i face.jpg -w 1024 --height 1024 --seed 42

# 提示词增强（用 Mistral 自动补细节）
python3 skills/i2i/scripts/i2i.py "futuristic city" -i sketch.jpg --upsample-prompt
```

## 重要参数

| 参数 | 默认 | 说明 |
|------|------|------|
| `-i/--images` | 必填 | 参考图（可多次指定，最多6张） |
| `-s/--steps` | 28 | 去噪步数（越多质量越高越慢，推荐 10-28） |
| `-g/--guidance` | 4.0 | 引导系数（越高越贴合prompt） |
| `-w/--width` | 跟随参考图 | 输出宽度 |
| `--height` | 跟随参考图 | 输出高度 |
| `--seed` | 随机 | 固定种子可复现结果 |
| `--model` | dev | dev(32B最高质量)/klein-4b(快)/klein-9b |
| `--upsample-prompt` | 关 | 用 Mistral 自动增强prompt细节 |

## 注意

- flux2 在**宿主机原生运行**（非容器），因为依赖 Apple MLX + Metal GPU
- 脚本内部已配置 `--vae-variant standard`（匹配已下载的 VAE 模型）
- 首次运行加载模型约 30 秒，之后较快
- 英文 prompt 效果显著优于中文
- 输出路径默认 `~/Downloads/`，可用 `-o` 指定或设 `$I2I_OUTPUT_DIR`
- 如遇 `MLX error: metallib`，需确保 `~/bin/mlx-swift_Cmlx.bundle` 存在
