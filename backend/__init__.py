# __init__.py - Backend initialization with torchaudio and huggingface compatibility

import os
import sys
import warnings

# Suppress torchaudio backend warnings globally
os.environ['TORCHAUDIO_USE_SOX_EFFECTS'] = '0'
os.environ['HF_HUB_DISABLE_SYMLINKS_WARNING'] = '1'

# Load Hugging Face token from env/secrets if available.
if not os.getenv('HF_TOKEN') and not os.getenv('HUGGINGFACE_HUB_TOKEN'):
    try:
        import streamlit as st
        hf_token = st.secrets.get('HF_TOKEN')
        if hf_token:
            os.environ['HF_TOKEN'] = hf_token
            os.environ['HUGGINGFACE_HUB_TOKEN'] = hf_token
    except Exception:
        pass

warnings.filterwarnings('ignore', message='.*torchaudio.*')
warnings.filterwarnings('ignore', message='.*sox.*')
warnings.filterwarnings('ignore', category=UserWarning)
warnings.filterwarnings('ignore', category=DeprecationWarning)

# ============================================================
# FIX 1: torchaudio compatibility (newer versions)
# ============================================================
try:
    import torchaudio
    if not hasattr(torchaudio, 'list_audio_backends'):
        # Mock the function for compatibility with newer torchaudio versions
        def _mock_list_audio_backends():
            return ['sox', 'soundfile']
        
        torchaudio.list_audio_backends = _mock_list_audio_backends
        torchaudio.set_audio_backend = lambda x: None
except ImportError:
    pass

# ============================================================
# FIX 2: huggingface_hub compatibility (speechbrain issue)
# ============================================================
# Monkey-patch huggingface_hub.hf_hub_download to accept use_auth_token
# This fixes the issue where speechbrain uses the old API

try:
    from huggingface_hub import hf_hub_download as original_hf_hub_download
    
    def patched_hf_hub_download(*args, **kwargs):
        """
        Wrapper for hf_hub_download that converts use_auth_token to token
        for backward compatibility with older libraries like speechbrain
        """
        # Convert old parameter name to new one
        if 'use_auth_token' in kwargs:
            kwargs['token'] = kwargs.pop('use_auth_token')

        # Fall back to environment token for private/gated model access.
        if not kwargs.get('token'):
            env_token = os.getenv('HF_TOKEN') or os.getenv('HUGGINGFACE_HUB_TOKEN')
            if env_token:
                kwargs['token'] = env_token
        
        return original_hf_hub_download(*args, **kwargs)
    
    # Replace the function in the module
    import huggingface_hub
    huggingface_hub.hf_hub_download = patched_hf_hub_download
    
    # Also patch it in sys.modules to catch late imports
    if 'huggingface_hub.file_download' in sys.modules:
        sys.modules['huggingface_hub.file_download'].hf_hub_download = patched_hf_hub_download
        
except Exception as e:
    warnings.warn(f"Could not apply huggingface_hub patch: {e}")


