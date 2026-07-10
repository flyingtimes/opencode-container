# OpenCode 容器化部署（智谱 GLM Coding Plan）

在 Docker 容器中运行 [OpenCode](https://opencode.ai)（开源 AI Coding Agent），接入智谱 GLM Coding Plan 套餐，内置 Python 3.12 执行环境与 Office 文档处理能力，通过 `docker-compose` 运行交互式 TUI。

## 功能一览

- **模型**：智谱 GLM Coding Plan（GLM-5.2 / GLM-5-Turbo / GLM-4.7），默认 GLM-5.2
- **Python 3.12 执行环境**：预装数据科学 + Office 文档处理包
- **draw 技能**：Ollama 本地图片生成（x/z-image-turbo）与图片分析（Qwen3.6 Vision）
- **guizang-ppt-skill**：生成横向翻页网页 PPT（单 HTML 文件，电子杂志风 / 瑞士国际主义风）
- **中国大陆网络友好**：内置 daocloud 镜像源、npmmirror、清华 PyPI

## 目录结构

```
opencode-container/
├── Dockerfile              # 镜像构建（python:3.12-alpine + opencode-ai）
├── docker-compose.yml      # 交互式运行配置
├── opencode.json           # 智谱 provider + GLM 模型配置
├── .env                    # API Key（gitignore，需自行填写）
├── .env.example            # 环境变量模板
├── skills/                 # → 容器内 /workspace/.opencode/skills
│   ├── draw/               # draw 技能（Ollama 图片生成/分析）
│   │   ├── SKILL.md
│   │   ├── scripts/{draw,vision}.py
│   │   └── references/
│   └── guizang-ppt-skill/  # 网页 PPT 技能（电子杂志风 / 瑞士风）
│       ├── SKILL.md
│       ├── assets/ (HTML 模板、背景图、motion.js)
│       ├── references/ (主题/布局/组件规范)
│       └── scripts/ (validate-swiss-deck.mjs)
├── output/                 # → 容器内 /workspace/output（生成图片，gitignore）
└── opencode-data/          # → /root/.local/share/opencode（会话/数据库，gitignore）
```

**挂载映射**：

| 宿主路径 | 容器路径 | 作用 |
|----------|----------|------|
| `./opencode.json` | `/workspace/.opencode/opencode.json` | opencode 配置 |
| `./skills` | `/workspace/.opencode/skills` | 技能 |
| `./output` | `/workspace/output` | 生成的文件 |
| `./opencode-data` | `/root/.local/share/opencode` | 会话历史、数据库 |
| `~/.gitconfig` | `/root/.gitconfig` | git 提交身份（只读） |
| `~/.ssh` | `/root/.ssh` | SSH 私钥，拉私有仓库（只读） |

## 快速开始

### 1. 填写 API Key

```bash
cp .env.example .env
# 编辑 .env，填入智谱 Coding Plan 的 ZHIPU_API_KEY
```

> 智谱开放平台 → 个人/团队编程套餐 → 新建 API Key。**Coding Plan 套餐 Key 与普通按量 Key 不通用。**

### 2. 构建镜像

```bash
docker compose build
```

### 3. 运行

```bash
docker compose run --rm opencode
```

> ⚠️ TUI 程序必须交互式运行。**不要用 `docker compose up`**（无 TTY 会卡住）。

## 环境说明

### Python 3.12 执行环境

基础镜像 `python:3.12-alpine`，预装包：

| 类别 | 包 |
|------|------|
| 网络/通用 | requests, httpx, python-dotenv, pyyaml, rich, tqdm |
| 数据科学 | numpy, pandas, matplotlib |
| Office 文档 | python-pptx (PPT), openpyxl (Excel), pypdf (PDF), python-docx (Word) |

如需项目级隔离，进容器后用 `python -m venv`。

### draw 技能（Ollama 图片生成/分析）

技能位于 `skills/draw/`，随挂载进入容器（`/workspace/.opencode/skills/`），opencode 自动加载。

- **图片生成**：调用宿主 Ollama 的 `x/z-image-turbo`，输出到 `/workspace/output/`
- **图片分析**：调用 `qwen3.6:latest`，超过 800px 的图自动用 Pillow 压缩
- **网络**：容器经 `host.docker.internal:11434` 访问宿主 Ollama

**前提**：宿主 Ollama 须监听 `0.0.0.0:11434`（而非仅 `127.0.0.1`）。macOS：
```bash
launchctl setenv OLLAMA_HOST 0.0.0.0:11434
# 退出并重启 Ollama app
```

在 TUI 里对 opencode 说「画一匹马」或「分析这张图」即可触发。

> **注意输出路径**：图片应存到 `/workspace/output/`（宿主对应 `./output/`）。不要用 `~` 或容器外路径——opencode 默认禁止访问工作目录之外的位置。

### guizang-ppt-skill（网页 PPT 生成）

技能位于 `skills/guizang-ppt-skill/`（来源 [op7418/guizang-ppt-skill](https://github.com/op7418/guizang-ppt-skill)），随挂载进入容器，opencode 自动加载。

- 生成**单文件 HTML** 横向翻页网页 PPT，含 WebGL 背景、章节封幕、数据大字报、图片网格等模板
- 两种风格：**电子杂志风**（衬线 + 流体背景） / **瑞士国际主义风**（无衬线 + 网格点阵）
- 无额外依赖（Node 校验脚本仅用内置 `fs`）

在 TUI 里对 opencode 说「帮我做一份瑞士风 PPT，主题是 XX，控制在 7 页」即可触发。生成的 HTML 建议存到 `/workspace/output/`。

### 模型配置

`opencode.json` 用 **openai-compatible provider 直连**智谱 coding 端点（`https://open.bigmodel.cn/api/coding/paas/v4`），API Key 通过环境变量 `ZHIPU_API_KEY` 注入。切换默认模型改 `"model"` 字段。

## 安全注意事项

- **`.env` 含真实 API Key**，已加入 `.gitignore`，切勿提交。
- **`~/.ssh` 只读挂载**进容器：opencode 能读取你的 SSH 私钥（用于拉私有仓库）。如不需要，注释掉 `docker-compose.yml` 中 `${HOME}/.ssh` 行。
- **容器以 root 运行**：当前未设非 root 用户。多租户/不信任场景应考虑加 `user:` 限制。
- **Ollama 监听 0.0.0.0**：开启后同网段设备均可访问你的 Ollama，注意网络环境。

## 故障排查

| 现象 | 原因与解决 |
|------|-----------|
| `Authentication parameter not received` | `.env` 的 `ZHIPU_API_KEY` 错误或非套餐 Key |
| 模型调用 404 | 端点应为 `coding/paas/v4`（已配好），非通用 `paas/v4` |
| TUI 无界面/卡住 | 用 `docker compose run --rm opencode`（带 TTY），勿 `up -d` |
| `~/.gitconfig`/`~/.ssh` 不存在导致启动失败 | 注释掉 compose 里对应挂载行 |
| draw 技能「无法连接 Ollama」 | 宿主 Ollama 未启动或未监听 `0.0.0.0:11434` |
| `permission ... external_directory` 拒绝 | opencode 禁止写工作目录外；用 `/workspace/output/` 而非 `~` |
| 构建时 apt 报 GPG signature 错误 | Docker Desktop on arm64 + Debian 已知问题；本仓库用 alpine 规避 |

## 网络加速（中国大陆）

| 资源 | 加速源 |
|------|--------|
| 基础镜像 | `docker.m.daocloud.io`（daocloud） |
| npm | `registry.npmmirror.com`（淘宝） |
| PyPI | `pypi.tuna.tsinghua.edu.cn`（清华） |

如已自行配置 Docker 镜像加速器，可将 Dockerfile 的 `FROM` 改回 `python:3.12-alpine`。
