"""Configuration shared by local runs and cloud deployments."""
import os
from pathlib import Path
from datetime import datetime
from zoneinfo import ZoneInfo

ROOT = Path(__file__).resolve().parent.parent

def setting(name, default=None):
    value = os.environ.get(name)
    if value is not None:
        return value
    import tomllib
    secrets_path = ROOT / '.streamlit' / 'secrets.toml'
    if secrets_path.is_file():
        with secrets_path.open('rb') as handle:
            return tomllib.load(handle).get(name, default)
    # Community Cloud may provide secrets through Streamlit's global location.
    try:
        from streamlit.runtime.scriptrunner import get_script_run_ctx
        if get_script_run_ctx(suppress_warning=True) is not None:
            import streamlit as st
            return st.secrets.get(name, default)
    except (ImportError, FileNotFoundError):
        pass
    return default

SPEAKER_VERIFICATION_THRESHOLD = float(setting('SPEAKER_VERIFICATION_THRESHOLD', '0.5962'))
if not -1 <= SPEAKER_VERIFICATION_THRESHOLD <= 1:
    raise ValueError('SPEAKER_VERIFICATION_THRESHOLD must be between -1 and 1.')
AUDIO_SAMPLE_RATE = 16000
AUDIO_MIN_LENGTH = 32000
AUDIO_MAX_SECONDS = 30
DB_PATH = ROOT / 'database' / 'attendance.db'
MODEL_PATH = ROOT / 'pretrained_models' / 'spkrec-ecapa-voxceleb'
DEVICE = 'cpu'

def local_now():
    return datetime.now(ZoneInfo(setting('ATTENDANCE_TIMEZONE', 'Asia/Karachi')))
