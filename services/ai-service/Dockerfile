FROM python:3.11-slim

WORKDIR /app

# 安装系统依赖
RUN apt-get update && apt-get install -y --no-install-recommends \
    libnss3 libnspr4 libdbus-1-3 libatk1.0-0 libatk-bridge2.0-0 \
    libcups2 libdrm2 libxkbcommon0 libatspi2.0-0 libxcomposite1 \
    libxdamage1 libxfixes3 libxrandr2 libgbm1 libpango-1.0-0 \
    libcairo2 libasound2 \
    && rm -rf /var/lib/apt/lists/*

# 配置 pip 使用国内镜像源
RUN pip config set global.index-url https://pypi.tuna.tsinghua.edu.cn/simple

# 安装依赖（先复制 pyproject.toml + 最小包结构，利用 Docker 缓存）
COPY pyproject.toml .
RUN mkdir -p src && touch src/__init__.py && \
    pip install --no-cache-dir . && \
    rm -rf src

# 复制源码
COPY src/ ./src/

EXPOSE 8086

CMD ["python", "-m", "src.main"]
