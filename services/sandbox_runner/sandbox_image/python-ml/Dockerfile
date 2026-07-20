# GPU-capable ML/DL environment: the official PyTorch image already bundles a CUDA +
# cuDNN runtime and a matching torch build, so the same image runs accelerated on a host
# with a GPU (and nvidia-container-toolkit) and transparently falls back to CPU everywhere
# else -- torch.cuda.is_available() just reports False, no separate image needed.
FROM pytorch/pytorch:2.5.1-cuda12.4-cudnn9-runtime
RUN pip install --no-cache-dir \
  numpy==2.* \
  pandas==2.* \
  scipy==1.* \
  scikit-learn==1.* \
  matplotlib==3.* \
  seaborn==0.13.* \
  torchvision==0.20.* \
  pytest==8.* \
  pytest-timeout==2.*
WORKDIR /workspace
