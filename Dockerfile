FROM python:3.13-slim

WORKDIR /app

# 安装系统依赖（Pillow和python-magic需要）
RUN apt-get update && apt-get install -y --no-install-recommends \
    libjpeg62-turbo \
    zlib1g \
    libpng16-16 \
    libmagic1 \
    && rm -rf /var/lib/apt/lists/*

# 安装Python依赖
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# 复制应用代码
COPY . .

# 创建必要的目录
RUN mkdir -p static/uploads static/pdfs static/thumbnails

# 设置端口
EXPOSE 5000

# 启动应用
CMD ["python", "app.py"]