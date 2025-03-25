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

# Copy handler code
COPY tetra/runpod_handler.py /app/handler.py

# Install Python dependencies
RUN pip install --no-cache-dir --upgrade pip
RUN pip install --no-cache-dir \
    runpod \
    cloudpickle \
    grpcio \
    grpcio-tools \
    "protobuf>=5.26.1,<6.0" \
    python-dotenv \
    numpy \
    pillow \
    scikit-learn

# Copy the package files
COPY tetra/__init__.py /app/tetra/
COPY tetra/remote_execution_pb2.py /app/tetra/
COPY tetra/remote_execution_pb2_grpc.py /app/tetra/

# Set the entrypoint
CMD ["python", "handler.py"]