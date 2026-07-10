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
      linux-headers

# 安装 opencode CLI（使用国内 npm 镜像加速）
RUN npm config set registry https://registry.npmmirror.com \
 && npm i -g opencode-ai@latest

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
 && python --version \
 && pip --version

WORKDIR /workspace

ENTRYPOINT ["opencode"]
