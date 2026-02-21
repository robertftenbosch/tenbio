FROM pytorch/pytorch:2.7.1-cuda12.6-cudnn9-runtime

WORKDIR /app

# Install system dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    curl \
    git \
    && rm -rf /var/lib/apt/lists/*

# Install Python dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Remove deepspeed - not needed for ESMFold inference, and incompatible
# with both PyTorch 2.7 (0.5.9 uses torch._six) and runtime image (>=0.14 needs CUDA_HOME)
RUN pip uninstall -y deepspeed

# Install openfold (required by ESMFold but not in fair-esm extras)
# Use the specific commit compatible with ESMFold v1 (per ESM docs)
# Only copy Python modules - skip C extension build
RUN git clone https://github.com/aqlaboratory/openfold.git /tmp/openfold && \
    cd /tmp/openfold && git checkout 4b41059694619831a7db195b7e0988fc4ff3a307 && \
    pip install --no-cache-dir dm-tree ml-collections modelcif && \
    cp -r /tmp/openfold/openfold /opt/conda/lib/python3.11/site-packages/ && \
    rm -rf /tmp/openfold

# Patch openfold for runtime image (no CUDA toolkit, no deepspeed)
COPY patches/ /tmp/patches/
RUN SITE=/opt/conda/lib/python3.11/site-packages && \
    # 1. Replace CUDA attention kernels with PyTorch-native fallbacks
    cp /tmp/patches/openfold_attention_core.py $SITE/openfold/utils/kernel/attention_core.py && \
    cp /tmp/patches/attn_core_inplace_cuda.py $SITE/attn_core_inplace_cuda.py && \
    # 2. Disable eager __init__.py imports that pull in unnecessary deps
    #    (pytorch_lightning, deepspeed, etc.) - ESMFold uses explicit imports
    echo "" > $SITE/openfold/__init__.py && \
    echo "" > $SITE/openfold/model/__init__.py && \
    echo "" > $SITE/openfold/utils/__init__.py && \
    # 3. Fix Python 3.11 dataclass mutable default errors
    python3 /tmp/patches/fix_trunk_dataclass.py $SITE && \
    rm -rf /tmp/patches

# Copy application code
COPY app/ ./app/

# Default model to preload at startup
ENV PRELOAD_MODEL=esmfold_v1

# Expose the service port
EXPOSE 8002

# Run the FastAPI server
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8002"]
