---
name: draw
description: >
  Ollama 多媒体技能：x/z-image-turbo 图片生成 + Qwen3.6 Vision 图片分析。
  当用户要求画画、生成图片、AI绘图、绘制插图、做配图、批量生成文章配图，
  或要求分析图片内容、描述图片、看图说话、识别图中文字时触发。
  依赖宿主机运行的 Ollama（通过 host.docker.internal 访问）。
---

# AI 图片生成（Ollama x/z-image-turbo）

| | |
|---|---|
| 模型 | x/z-image-turbo:bf16 (32GB) |
| Ollama 地址 | host.docker.internal:11434（可用环境变量 OLLAMA_HOST 覆盖） |
| 输出 | PNG → /workspace/output/ |
| 脚本 | .opencode/skills/draw/scripts/draw.py |

## 执行步骤

1. 用用户的描述构建英文 prompt（英文生成效果显著优于中文）
2. 用 `Bash` 工具调用脚本（工作目录为 /workspace，用相对路径）：
```bash
python3 .opencode/skills/draw/scripts/draw.py "<英文prompt>"
```
3. 脚本输出格式：`OK:<路径>:<字节数>`
4. 生成的图片在 /workspace/output/ 下（宿主对应 <项目目录>/output/），用相对路径告知用户

## 提示词建议

- 英文 > 中文，描述越具体效果越好
- 推荐包含：主体 + 风格 + 细节 + 氛围
- 示例：`a serene Japanese garden in autumn, koi pond, golden maple leaves, watercolor style, warm lighting`

## 注意

- 首次调用需加载模型（~20s），后续较快
- 需要 `raw: true` 才能获取图片而非文本
- 脚本通过 host.docker.internal 访问宿主 Ollama；若连接失败，提示用户确认宿主 Ollama 已启动且监听 0.0.0.0:11434
- 指定输出路径可用 `-o`：`python3 .../draw.py "prompt" -o /workspace/output/xxx.png`

---

## § 文章配图

draw 不仅用于 PPT，也适用于科普文章/博客配图。批量生成到子目录，用 markdown 相对路径嵌入。
详见 `references/article-illustration.md`（含批量脚本模板、prompt 要点、文件组织方式）。

> 注：批量脚本模板里的 DRAW 路径在容器中为 `.opencode/skills/draw/scripts/draw.py`（相对 /workspace）。

## § 图片分析 (Qwen3.6 Vision)

使用 Ollama `qwen3.6:latest`（36B MoE）分析图片内容。

### 脚本
`scripts/vision.py` — 读取图片、校验格式、调用 Ollama API、输出结果。

```bash
python3 .opencode/skills/draw/scripts/vision.py <图片路径或URL> [-p "提示词"] [-m qwen3.6:latest]
```

| 参数 | 说明 | 默认值 |
|------|------|--------|
| `image` | 本地路径或URL | 必填 |
| `-p, --prompt` | 分析提示词 | 请仔细描述这张图片中的所有内容… |
| `-m, --model` | Ollama模型名 | qwen3.6:latest |
| `--no-compress` | 禁用自动压缩 | false |

### 注意事项
- URL下载不走代理（`--noproxy '*'`），避免被拦截返回HTML
- 超过800px的图片自动用 **Pillow** 压缩（容器内已预装）以加速推理
- Ollama 通过 host.docker.internal 访问，须在宿主启动并监听 0.0.0.0
