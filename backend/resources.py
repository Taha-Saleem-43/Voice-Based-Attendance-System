"""One shared model instance for all Streamlit pages."""
import streamlit as st

@st.cache_resource(show_spinner='Loading voice recognition model...')
def load_models():
    from backend.audio_processor import AudioProcessor
    from backend.speaker_model import SpeakerModel
    return AudioProcessor(), SpeakerModel()
