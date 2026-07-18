"""Face-embedding comparison against Semantic Movie Knowledge reference records."""
import math

from PIL import Image

from config import Settings
from models.face_embedding_extractor import FaceEmbeddingExtractor
from schemas.face_verification import DetectedFace, FaceVerification, FaceVerificationResponse
from schemas.knowledge import FaceReference, SemanticMovieKnowledge


class FaceVerificationService:
    """Verifies an enrolled character reference conservatively; it never creates identities."""

    def __init__(self, extractor: FaceEmbeddingExtractor, settings: Settings):
        self._extractor = extractor
        self._threshold = settings.face_verification_threshold

    def verify(self, image: Image.Image, knowledge: SemanticMovieKnowledge) -> FaceVerificationResponse:
        observations, detector_model, embedding_model = self._extractor.extract(image)
        character_ids = {character.id for character in knowledge.characters}
        references = [reference for reference in knowledge.face_references if reference.character_id in character_ids]
        faces = [self._verify_observation(box, detection_confidence, embedding, references) for box, detection_confidence, embedding in observations]
        return FaceVerificationResponse(faces=faces, detector_model=detector_model, embedding_model=embedding_model)

    def _verify_observation(
        self,
        bbox: list[float],
        detection_confidence: float,
        embedding: list[float],
        references: list[FaceReference],
    ) -> FaceVerification:
        face = DetectedFace(bbox=bbox, detection_confidence=detection_confidence)
        candidates: dict[str, tuple[float, float]] = {}
        for reference in references:
            if not _compatible(embedding, reference.embedding):
                continue
            score = _cosine_similarity(embedding, reference.embedding)
            if score >= self._threshold:
                existing = candidates.get(reference.character_id)
                if existing is None or score > existing[0]:
                    candidates[reference.character_id] = (score, reference.confidence)
        if len(candidates) != 1:
            return FaceVerification(face=face, verified=False, evidence=["no_unique_enrolled_face_match"])
        character_id, (score, reference_confidence) = next(iter(candidates.items()))
        return FaceVerification(
            face=face,
            verified=True,
            verified_character_id=character_id,
            confidence=min(score, detection_confidence, reference_confidence),
            evidence=["face_embedding_similarity", "unique_enrolled_character_match"],
        )


def _compatible(left: list[float], right: list[float]) -> bool:
    return bool(left) and len(left) == len(right)


def _cosine_similarity(left: list[float], right: list[float]) -> float:
    numerator = sum(a * b for a, b in zip(left, right, strict=True))
    left_norm = math.sqrt(sum(value * value for value in left))
    right_norm = math.sqrt(sum(value * value for value in right))
    if left_norm == 0 or right_norm == 0:
        return -1.0
    return numerator / (left_norm * right_norm)
