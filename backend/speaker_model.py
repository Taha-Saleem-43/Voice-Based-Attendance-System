import threading
import torch
import numpy as np
from pathlib import Path
from speechbrain.inference.speaker import EncoderClassifier
from speechbrain.utils.fetching import LocalStrategy
from backend.config import SPEAKER_VERIFICATION_THRESHOLD, MODEL_PATH, AUDIO_MIN_LENGTH, setting

class SpeakerModel:
    """Frozen pretrained ECAPA embeddings; no fine-tuning."""
    def __init__(self, device='cpu'):
        torch.set_num_threads(max(1, int(setting('TORCH_NUM_THREADS', '2'))))
        self.device = 'cuda' if device == 'cuda' and torch.cuda.is_available() else 'cpu'
        self._lock = threading.Lock()
        # A failed download can leave an empty folder: test actual required files.
        required = ('hyperparams.yaml', 'embedding_model.ckpt', 'classifier.ckpt', 'mean_var_norm_emb.ckpt')
        complete = all((Path(MODEL_PATH) / name).is_file() for name in required)
        source = str(MODEL_PATH) if complete else 'speechbrain/spkrec-ecapa-voxceleb'
        self.model = EncoderClassifier.from_hparams(
            source=source, savedir=str(MODEL_PATH),
            run_opts={'device': self.device}, local_strategy=LocalStrategy.COPY)
        self.model.eval()
        for parameter in self.model.parameters():
            parameter.requires_grad_(False)

    # =====================================================
    # Generate Speaker Embedding
    # =====================================================
    def generate_embedding(self, audio_numpy):
        """
        Generate normalized embedding from audio numpy array.
        Input:
            audio_numpy -> 1D numpy array (16kHz mono recommended)
        Output:
            normalized 1D numpy embedding vector
        """

        if not isinstance(audio_numpy, np.ndarray):
            raise TypeError("Audio input must be numpy array")

        if audio_numpy.ndim != 1 or not np.isfinite(audio_numpy).all():
            raise ValueError('Audio must be a finite mono waveform.')

        if len(audio_numpy) < AUDIO_MIN_LENGTH:
            raise ValueError("Audio too short. Speak at least 2 seconds.")

        # Convert to tensor
        audio_tensor = torch.tensor(
            audio_numpy,
            dtype=torch.float32
        ).unsqueeze(0)

        # Move to device
        audio_tensor = audio_tensor.to(self.device)

        # SpeechBrain requires relative length tensor
        length_tensor = torch.tensor([1.0]).to(self.device)

        with self._lock, torch.inference_mode():
            embedding = self.model.encode_batch(
                audio_tensor,
                wav_lens=length_tensor
            )

        # Convert to numpy
        embedding = embedding.detach().cpu().numpy().squeeze()

        # L2 Normalize embedding
        norm = np.linalg.norm(embedding) + 1e-9
        embedding = embedding / norm

        return embedding.astype(np.float32)

    # =====================================================
    # Cosine Similarity
    # =====================================================
    def compute_similarity(self, emb1, emb2):
        """
        Compute cosine similarity between embeddings.
        Returns float between -1 and 1.
        """

        emb1 = emb1 / (np.linalg.norm(emb1) + 1e-9)
        emb2 = emb2 / (np.linalg.norm(emb2) + 1e-9)

        similarity = np.dot(emb1, emb2)
        return float(similarity)

    # =====================================================
    # Speaker Verification
    # =====================================================
    def verify_speaker(self, live_emb, stored_emb, threshold=None):
        """
        Verify speaker match using cosine similarity.
        Default threshold is configurable; validate it on independent recordings.
        """
        if threshold is None:
            threshold = SPEAKER_VERIFICATION_THRESHOLD

        similarity = self.compute_similarity(live_emb, stored_emb)
        is_match = similarity >= threshold

        return is_match, similarity
