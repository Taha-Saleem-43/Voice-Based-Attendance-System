"""Backend package. Expensive audio libraries load only for voice processing."""
import os
from pathlib import Path
os.environ.setdefault("HF_HUB_DISABLE_SYMLINKS_WARNING","1")
os.environ.setdefault('HF_HOME',str(Path(__file__).resolve().parent.parent/'.cache'/'huggingface'))
