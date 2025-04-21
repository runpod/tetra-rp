FROM pytorch/pytorch:latest

# Set working directory
WORKDIR /app

# Install system dependencies
RUN apt-get update && apt-get install -y \
    build-essential \
    git \
    wget \
    curl \
    && apt-get clean \
    && rm -rf /var/lib/apt/lists/*

# Copy application code
COPY src/tetra_rp ./tetra_rp
COPY README.md handler.py requirements.txt ./

# Install Python dependencies using pip
RUN pip install --no-cache-dir -r requirements.txt

# Set the entrypoint
CMD ["python", "handler.py"]
