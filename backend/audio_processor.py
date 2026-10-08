"""Bounded audio loading and validation before speaker embedding inference."""
import numpy as np
import soundfile as sf
import librosa
from backend.config import AUDIO_SAMPLE_RATE, AUDIO_MIN_LENGTH, AUDIO_MAX_SECONDS

class AudioProcessor:
    def __init__(self, sample_rate=AUDIO_SAMPLE_RATE):
        self.sample_rate = sample_rate

    def load_audio(self, file_input):
        if hasattr(file_input, 'seek'):
            file_input.seek(0)
        try:
            with sf.SoundFile(file_input) as handle:
                if handle.samplerate < 8000 or handle.samplerate > 192000:
                    raise ValueError('Unsupported audio sample rate.')
                if handle.channels > 2:
                    raise ValueError('Use mono or stereo audio.')
                duration = len(handle) / handle.samplerate
                if duration > AUDIO_MAX_SECONDS:
                    raise ValueError(f'Recordings must be at most {AUDIO_MAX_SECONDS} seconds.')
                if duration < AUDIO_MIN_LENGTH / self.sample_rate:
                    raise ValueError('Speak for at least 2 seconds.')
                sr = handle.samplerate
                audio = handle.read(dtype='float32')
        except (RuntimeError, sf.LibsndfileError) as exc:
            raise ValueError('Cannot read this audio. Please provide a valid WAV recording.') from exc
        if audio.ndim > 1:
            audio = audio.mean(axis=1)
        if not np.isfinite(audio).all():
            raise ValueError('Audio contains invalid samples.')
        if sr != self.sample_rate:
            audio = librosa.resample(audio, orig_sr=sr, target_sr=self.sample_rate)
        return audio

    def normalize_audio(self, audio):
        audio = np.asarray(audio, dtype=np.float32)
        if not audio.size or not np.isfinite(audio).all():
            raise ValueError('Audio is empty or invalid.')
        audio = audio - audio.mean()
        deviation = float(audio.std())
        if deviation < 1e-4:
            raise ValueError('Recording is silent or too quiet. Move closer to the microphone.')
        return audio / deviation

    def process_file(self, file_input):
        audio = self.load_audio(file_input)
        if float(audio.std()) < 1e-4:
            raise ValueError('Recording is silent or too quiet.')
        audio, _ = librosa.effects.trim(audio, top_db=20)
        if len(audio) < AUDIO_MIN_LENGTH:
            raise ValueError('Record at least 2 seconds of speech, excluding leading/trailing silence.')
        return self.normalize_audio(audio)
