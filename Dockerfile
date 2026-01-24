FROM python:3.11-slim-bookworm

# Install system dependencies for OpenCascade + headless rendering + cairo
RUN apt-get update && apt-get install -y --no-install-recommends \
    libgl1-mesa-glx \
    libglib2.0-0 \
    libsm6 \
    libxext6 \
    libxrender1 \
    libfontconfig1 \
    libfreetype6 \
    libcairo2 \
    libcairo2-dev \
    libpango1.0-0 \
    libpangocairo-1.0-0 \
    libgdk-pixbuf-2.0-0 \
    librsvg2-2 \
    fonts-dejavu-core \
    pkg-config \
    && rm -rf /var/lib/apt/lists/*

# Set environment for headless matplotlib
ENV MPLBACKEND=Agg
ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1

WORKDIR /app

# Install Python dependencies (OCP wheel is ~60MB, cache this layer)
COPY requirements.txt .
RUN pip install --no-cache-dir --upgrade pip && \
    pip install --no-cache-dir -r requirements.txt

# Copy application code
COPY src/ ./src/
COPY entrypoint.sh .
RUN chmod +x entrypoint.sh

# Working directories
RUN mkdir -p /workspace /renders

EXPOSE 8123

ENTRYPOINT ["./entrypoint.sh"]
CMD ["serve"]
