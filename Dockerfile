# 方案 A：基于 npm 包 opencode-ai 构建镜像，并内置 Python 3.12 执行环境
# 用 python:3.12-alpine 同时满足 opencode(node) 运行 + Python 3.12 精确版本
# 使用国内镜像源（Docker Hub 在大陆网络常超时）；如已配镜像加速器可改回 python:3.12-alpine
FROM docker.m.daocloud.io/library/python:3.12-alpine

# opencode 运行需要 ripgrep（官方 Dockerfile 也装它），git 用于读写仓库
# build-base 给 Python 扩展包编译用；py3-pip/py3-virtualenv 提供包与虚拟环境管理
RUN apk add --no-cache \
      ripgrep \
      git \
      ca-certificates \
      curl \
      nodejs \
      npm \
      build-base \
      linux-headers \
      bash

# 安装 opencode CLI（使用国内 npm 镜像加速）
RUN npm config set registry https://registry.npmmirror.com \
 && npm i -g opencode-ai@latest

# 安装 opencli CLI（控制宿主机已登录的浏览器）
# 版本须与宿主机 opencli 一致，否则命令/协议可能不兼容
ARG OPENCLI_VERSION=1.8.6
RUN npm i -g @jackwener/opencli@${OPENCLI_VERSION}

# 补丁：让 opencli 的 daemon 地址可经 OPENCLI_DAEMON_HOST 环境变量覆盖
# 原因：opencli 硬编码连 127.0.0.1:19825，容器里需指向宿主 host.docker.internal
# 不设该变量时回退 127.0.0.1，本地直跑不受影响；opencli 升级后需重新打此补丁
COPY patch-opencli.mjs /tmp/patch-opencli.mjs
RUN node /tmp/patch-opencli.mjs && rm /tmp/patch-opencli.mjs

# 安装常用 Python 包（使用国内 PyPI 镜像加速）
# 可按需增删；如需系统级隔离，建议进容器后用 `python -m venv`
RUN pip install --no-cache-dir --break-system-packages \
      -i https://pypi.tuna.tsinghua.edu.cn/simple \
      requests httpx \
      numpy pandas matplotlib \
      python-dotenv pyyaml \
      rich tqdm \
      python-pptx openpyxl pypdf python-docx

# 构建期校验
RUN opencode --version \
 && opencli --version \
 && python --version \
 && pip --version

WORKDIR /workspace

ENTRYPOINT ["opencode"]
