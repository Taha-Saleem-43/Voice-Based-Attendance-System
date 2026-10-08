"""Load frozen model and optionally infer a real local sample."""
import sys
import argparse
import time
import tempfile
from unittest.mock import patch
from pathlib import Path
import numpy as np
ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0,str(ROOT))
from backend.audio_processor import AudioProcessor
from backend.speaker_model import SpeakerModel

parser = argparse.ArgumentParser()
parser.add_argument('--cold', action='store_true', help='Download public model into a temporary directory, as a new cloud app would.')
args = parser.parse_args()
started=time.perf_counter()
if args.cold:
    temporary = tempfile.TemporaryDirectory()
    with patch('backend.speaker_model.MODEL_PATH', Path(temporary.name)/'model'):
        model = SpeakerModel()
else:
    model = SpeakerModel()
print(f"Model loaded in {time.perf_counter()-started:.2f}s")
assert not any(p.requires_grad for p in model.model.parameters())
samples = sorted((ROOT.parent/'Voices/cleaned_voices').glob('*/*.wav'))
if samples:
    audio = AudioProcessor().process_file(samples[0])
    started=time.perf_counter()
    embedding = model.generate_embedding(audio)
    print(f"Embedding inference: {time.perf_counter()-started:.2f}s")
    assert embedding.shape == (192,) and np.isfinite(embedding).all()
    assert abs(float(np.linalg.norm(embedding))-1) < 1e-5
    assert model.compute_similarity(embedding,embedding) > .999
    print('Model load and real-recording embedding passed (192 dimensions).')
else:
    print('Model load passed. No local recording found; real-audio inference skipped.')

if args.cold:
    temporary.cleanup()
