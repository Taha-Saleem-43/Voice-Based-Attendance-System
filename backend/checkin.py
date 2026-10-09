from backend.errors import ValidationError
"""Supervised identification: only staff sessions or an unlocked kiosk may scan."""
import numpy as np
from backend.config import SPEAKER_VERIFICATION_THRESHOLD

class VoiceCheckinService:
    def __init__(self, db, audio_processor, model):
        from backend.attendance_handler import AttendanceHandler
        self.db,self.processor,self.model=db,audio_processor,model
        self.attendance=AttendanceHandler(db)

    def identify(self,audio_file,supervisor_id=None,kiosk_authorized=False,claimed_username=None):
        if supervisor_id is not None:
            actor=self.db.execute("SELECT 1 FROM users WHERE user_id=? AND is_active=1 AND role IN ('chairman','teacher','faculty')",(supervisor_id,),fetchone=True)
            if not actor:
                raise ValidationError('An active staff account is required to supervise check-in.')
        elif not kiosk_authorized:
            raise ValidationError('Ask a staff member to unlock this check-in station.')
        if claimed_username is not None:
            claimed_username=claimed_username.strip()
            if not claimed_username or len(claimed_username)>100:
                raise ValidationError('Enter the enrolled person’s campus username.')
        profiles=self.attendance.get_active_voice_profiles(claimed_username)
        if len(profiles)> (10 if claimed_username is not None else 1000):
            raise ValidationError('Use username-based verification. Ask the administrator to review the enrolled samples.')
        if not profiles:
            raise ValidationError('No active voice profile is available for this check-in.')
        live=self.model.generate_embedding(self.processor.process_file(audio_file))
        grouped={}
        identities={}
        for profile in profiles:
            try:
                vector=np.frombuffer(profile['embedding_vector'],dtype=np.float32)
            except ValueError:
                continue
            if vector.shape != (192,) or not np.isfinite(vector).all() or np.linalg.norm(vector)<1e-8:
                continue
            grouped.setdefault(profile['user_id'],[]).append(vector)
            identities[profile['user_id']]=profile
        best_id,score=None,-1.0
        for uid,vectors in grouped.items():
            similarity=self.model.compute_similarity(live,np.mean(vectors,axis=0))
            if similarity>score:
                best_id,score=uid,similarity
        if best_id is None or score<SPEAKER_VERIFICATION_THRESHOLD:
            return {'status':False,'matched':False,'message':'Voice not recognized. Try again in a quieter space or contact your faculty.'}
        result=self.attendance.mark_attendance(best_id,confidence=float(score),supervisor_id=supervisor_id)
        return {**result,'matched':True,'username':identities[best_id]['username'],'role':identities[best_id]['role'],'similarity':score}
