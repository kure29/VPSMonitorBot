# VPS监控系统 v1.0 - Docker配置文件
# 作者: kure29
# 网站: https://kure29.com

FROM python:3.11-slim

# 设置工作目录
WORKDIR /app

# 设置环境变量
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1

# 安装系统依赖
RUN apt-get update && apt-get install -y \
    curl \
    jq \
    git \
    && rm -rf /var/lib/apt/lists/*

# 复制requirements文件
COPY requirements.txt .

# 安装Python依赖
RUN pip install --upgrade pip && \
    pip install -r requirements.txt

# 复制项目文件
COPY . .

# 创建必要目录
RUN mkdir -p data logs backup

# 设置权限
RUN chmod +x scripts/*.sh

# 创建非root用户
RUN useradd --create-home --shell /bin/bash vpsmonitor && \
    chown -R vpsmonitor:vpsmonitor /app

# 切换到非root用户
USER vpsmonitor

# 健康检查
HEALTHCHECK --interval=30s --timeout=10s --start-period=5s --retries=3 \
    CMD python3 -c "import requests; requests.get('http://localhost:8000/health', timeout=5)" || exit 1

# 暴露端口（如果有Web界面）
EXPOSE 8000

# 启动命令
CMD ["python3", "src/monitor.py"]
