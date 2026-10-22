FROM python:3.11-slim-bookworm

# Install system dependencies for OpenCascade + headless rendering + cairo + VTK
RUN apt-get update && apt-get install -y --no-install-recommends \
    libgl1 \
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
    fonts-dejavu-extra \
    pkg-config \
    # VTK/headless rendering dependencies
    xvfb \
    libosmesa6 \
    libosmesa6-dev \
    libglu1-mesa \
    libgomp1 \
    libegl1 \
    && rm -rf /var/lib/apt/lists/*

# Set environment for headless rendering
ENV MPLBACKEND=Agg
ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1
# UTF-8 text I/O regardless of locale (lib3mf resets the process locale to C on 3MF write)
ENV PYTHONUTF8=1
# VTK offscreen rendering with Xvfb
ENV DISPLAY=:99

WORKDIR /app

# Install Python dependencies (OCP wheel is ~60MB, cache this layer)
COPY requirements.txt .
RUN pip install --no-cache-dir --upgrade pip && \
    pip install --no-cache-dir -r requirements.txt

# Copy application code
COPY src/ ./src/
COPY tests/ ./tests/
COPY examples/ ./examples/
COPY entrypoint.sh .
RUN chmod +x entrypoint.sh

# Working directories, owned by an unprivileged user (model code runs via exec())
RUN useradd --uid 1000 --create-home --shell /usr/sbin/nologin cad && \
    mkdir -p /workspace /renders && \
    chown -R cad:cad /workspace /renders /app

USER cad

EXPOSE 8123

ENTRYPOINT ["./entrypoint.sh"]
CMD ["serve"]
