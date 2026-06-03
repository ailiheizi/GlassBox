# NewArch AI Agent Sandbox
# Debian 13 (trixie) + Xvfb + Chromium + CDP Screencast + Agent Server

FROM debian:trixie

LABEL maintainer="NewArch Team"
LABEL description="AI Agent Sandbox with Chromium CDP and File Management API"

# 避免交互式安装
ENV DEBIAN_FRONTEND=noninteractive

# 基础环境变量
ENV DISPLAY=:1
ENV AGENT_PORT=8000
ENV RESOLUTION=1280x720
ENV USER_ID=""

# 替换为中科大源
RUN printf "%s\n" \
    "deb http://mirrors.ustc.edu.cn/debian trixie main contrib non-free non-free-firmware" \
    "deb http://mirrors.ustc.edu.cn/debian trixie-updates main contrib non-free non-free-firmware" \
    "deb http://mirrors.ustc.edu.cn/debian-security trixie-security main contrib non-free non-free-firmware" \
    > /etc/apt/sources.list

# 安装基础包（无桌面环境、无 VNC、无 noVNC）
RUN apt-get update && apt-get install -y \
    # 虚拟显示（Chromium 非 headless 需要 DISPLAY）
    xvfb \
    # Python
    python3 \
    python3-pip \
    python3-venv \
    python3-dev \
    # Node.js
    nodejs \
    npm \
    # 浏览器 (Debian 原生 Chromium，无 snap)
    chromium \
    # 常用工具
    curl \
    wget \
    git \
    vim \
    nano \
    htop \
    net-tools \
    iputils-ping \
    procps \
    # tmux 用于持久化 shell 会话
    tmux \
    # socat 用于 CDP 端口转发（Chromium 忽略 --remote-debugging-address）
    socat \
    # 中文支持
    fonts-wqy-zenhei \
    fonts-wqy-microhei \
    locales \
    # 清理
    && rm -rf /var/lib/apt/lists/* \
    && apt-get clean

# 创建 chromium-browser 符号链接 (兼容性)
RUN ln -sf /usr/bin/chromium /usr/bin/chromium-browser

# 设置中文 locale
RUN sed -i '/zh_CN.UTF-8/s/^# //g' /etc/locale.gen && locale-gen
ENV LANG=zh_CN.UTF-8
ENV LC_ALL=zh_CN.UTF-8

# 安装 gosu（用于 entrypoint 中从 root 切换到 sandbox 用户）
RUN apt-get update && apt-get install -y --no-install-recommends gosu \
    && rm -rf /var/lib/apt/lists/*

# 创建工作用户（无 sudo 权限）
RUN useradd -m -s /bin/bash sandbox \
    && echo "sandbox:sandbox" | chpasswd

# 创建必要目录
RUN mkdir -p /opt/ai-tools \
    && mkdir -p /home/sandbox/workspace \
    && chown -R sandbox:sandbox /home/sandbox \
    && chown -R sandbox:sandbox /opt/ai-tools

# 复制 AI 工具
COPY tools/ /opt/ai-tools/

# 安装 Python 依赖 (使用 --break-system-packages 因为 Debian 12 默认 PEP 668)
RUN pip3 install --no-cache-dir --break-system-packages --ignore-installed -r /opt/ai-tools/requirements.txt

# 复制启动脚本
COPY entrypoint.sh /entrypoint.sh
RUN chmod +x /entrypoint.sh

# 暴露端口 (Agent, CDP)
ENV CDP_PORT=9222
EXPOSE 8000 9222

# 工作目录
WORKDIR /home/sandbox/workspace

# 启动入口
ENTRYPOINT ["/entrypoint.sh"]
