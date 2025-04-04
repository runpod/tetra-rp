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
    protobuf \
    aiohttp \
    # Add common libraries that your functions might need
    numpy \
    pandas \
    pillow \
    matplotlib \
    scikit-learn

# We'll make the handler installable as a package so import paths work correctly
COPY setup.py /app/
COPY tetra/__init__.py /app/tetra/
COPY tetra/remote_execution_pb2.py /app/tetra/
COPY tetra/remote_execution_pb2_grpc.py /app/tetra/

# Install the tetra package
RUN pip install -e .

# Set the entrypoint
CMD ["python", "runpod_handler.py"]