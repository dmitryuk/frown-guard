import math
import os
import sys
from typing import Tuple, Dict, Any, Optional
import mediapipe as mp
from mediapipe.tasks import python
from mediapipe.tasks.python import vision
import numpy as np

class FaceFrownDetector:
    """
    Class for detecting frowning on the face using MediaPipe Tasks FaceLandmarker.
    Calculates the distance between the eyebrows and the distance from the eyebrows to the eyes,
    normalizes them, and converts them into an intuitive frown level (0-100%).
    """
    
    # Key landmark indices for MediaPipe Face Mesh:
    RIGHT_EYEBROW_INNER = 107
    LEFT_EYEBROW_INNER = 336
    RIGHT_EYE_INNER = 133
    LEFT_EYE_INNER = 362
    
    def __init__(self, model_path: str = "face_landmarker.task") -> None:
        # If running from a compiled PyInstaller binary
        if getattr(sys, "frozen", False) and hasattr(sys, "_MEIPASS"):
            model_path = os.path.join(sys._MEIPASS, "face_landmarker.task")
            
        # Verify the model file exists
        if not os.path.exists(model_path):
            raise FileNotFoundError(
                f"MediaPipe model file '{model_path}' not found. "
                "Ensure it has been downloaded and is placed in the project root directory."
            )
            
        # Configure MediaPipe Tasks FaceLandmarker options
        base_options = python.BaseOptions(model_asset_path=model_path)
        options = vision.FaceLandmarkerOptions(
            base_options=base_options,
            running_mode=vision.RunningMode.IMAGE,
            num_faces=1,
            output_face_blendshapes=True
        )
        self.landmarker = vision.FaceLandmarker.create_from_options(options)
        
        # Default calibration values
        self.relaxed_score: float = 1.20
        self.frowned_score: float = 0.85
        self.sensitivity: float = 50.0  # Sensitivity percentage (0 - 100)
        
    def calculate_3d_distance(self, p1: Any, p2: Any) -> float:
        """Calculates the Euclidean distance between two 3D points."""
        return math.sqrt(
            (p1.x - p2.x) ** 2 + 
            (p1.y - p2.y) ** 2 + 
            (p1.z - p2.z) ** 2
        )

    def extract_metrics(self, landmarks: Any) -> Optional[Tuple[float, float, float]]:
        """
        Extracts key facial metrics:
        - sep_ratio: distance between eyebrows, normalized by the eye distance.
        - height_ratio: average distance from eyebrows to eyes, normalized by the eye distance.
        - combined_score: weighted sum of the metrics (higher values mean a more relaxed face).
        """
        try:
            # Get landmarks
            r_eyebrow = landmarks[self.RIGHT_EYEBROW_INNER]
            l_eyebrow = landmarks[self.LEFT_EYEBROW_INNER]
            r_eye = landmarks[self.RIGHT_EYE_INNER]
            l_eye = landmarks[self.LEFT_EYE_INNER]
            
            # Base distance between inner corners of the eyes (for normalization)
            eye_dist = self.calculate_3d_distance(r_eye, l_eye)
            if eye_dist < 1e-5:
                return None
                
            # Brow furrowing (distance between inner edges of the eyebrows)
            brow_sep = self.calculate_3d_distance(r_eyebrow, l_eyebrow)
            sep_ratio = brow_sep / eye_dist
            
            # Brow height (distance from inner edges of the eyebrows to inner corners of the eyes)
            r_height = self.calculate_3d_distance(r_eyebrow, r_eye)
            l_height = self.calculate_3d_distance(l_eyebrow, l_eye)
            height_ratio = (r_height + l_height) / (2.0 * eye_dist)
            
            # Combined frown metric.
            # More weight is given to brow furrowing (0.65) since eyebrows get closer when frowning.
            # Brow lowering has a weight of (0.35).
            combined_score = (sep_ratio * 0.65) + (height_ratio * 0.35)
            
            return sep_ratio, height_ratio, combined_score
            
        except Exception as e:
            print(f"Error calculating facial metrics: {e}")
            return None

    def process_frame(self, frame_rgb: np.ndarray) -> Tuple[Optional[Dict[str, Any]], Optional[Any]]:
        """
        Processes an image frame and returns a dictionary with metrics and the landmarks object.
        """
        # Convert frame to MediaPipe Image format
        mp_image = mp.Image(image_format=mp.ImageFormat.SRGB, data=frame_rgb)
        
        results = self.landmarker.detect(mp_image)
        
        if not results.face_landmarks:
            return None, None
            
        landmarks = results.face_landmarks[0]
        
        # 1. Attempt to use rotation-invariant blendshapes
        combined_score = None
        if results.face_blendshapes:
            try:
                # Convert the categories list into a convenient dictionary
                blendshapes = {c.category_name: c.score for c in results.face_blendshapes[0]}
                
                # Furrowing intensity (drawing eyebrows closer and lowering them)
                frown_val = (blendshapes.get('browDownLeft', 0.0) + blendshapes.get('browDownRight', 0.0)) / 2.0
                
                # Surprise / forehead wrinkle intensity (raising eyebrows)
                raise_val = (blendshapes.get('browOuterUpLeft', 0.0) + blendshapes.get('browOuterUpRight', 0.0)) / 2.0
                
                # General forehead/brow expression activity.
                # Take the maximum between classic frowning and forehead raising.
                activity = max(frown_val, raise_val)
                
                # Map to the scale: 1.20 (fully relaxed) - 0.60 (tense)
                # This maintains backward compatibility with our geometric calibrations
                combined_score = 1.20 - (activity * 0.60)
            except Exception as e:
                print(f"Error extracting blendshapes: {e}")
                
        # 2. Fallback geometric calculation (if blendshapes are unavailable for any reason)
        metrics = self.extract_metrics(landmarks)
        if metrics is None and combined_score is None:
            return None, landmarks
            
        sep_ratio, height_ratio, geom_score = metrics if metrics else (1.0, 0.5, 1.0)
        
        if combined_score is None:
            combined_score = geom_score
            
        # Calculate frown level in percent (0% - relaxed face, 100% - frowned)
        # If current score is close to relaxed_score, frown_level -> 0%
        # If current score is close to frowned_score, frown_level -> 100%
        denominator = self.relaxed_score - self.frowned_score
        if abs(denominator) < 1e-5:
            denominator = 0.1
            
        raw_frown_level = (self.relaxed_score - combined_score) / denominator
        # Clamp the value between 0.0 and 1.0 (i.e., 0% to 100%)
        frown_level_pct = max(0.0, min(1.0, raw_frown_level)) * 100.0
        
        # Determine the activation threshold based on sensitivity.
        # At 50% sensitivity, the threshold is exactly halfway between relaxed and frowned.
        # The higher the sensitivity, the less facial movement is needed to trigger the alert.
        threshold_pct = (100.0 - self.sensitivity)
        is_frowning = frown_level_pct >= threshold_pct
        
        return {
            "sep_ratio": sep_ratio,
            "height_ratio": height_ratio,
            "combined_score": combined_score,
            "frown_level_pct": frown_level_pct,
            "threshold_pct": threshold_pct,
            "is_frowning": is_frowning
        }, landmarks

    def set_calibration(self, relaxed_score: float, frowned_score: float) -> None:
        """Sets calibration values manually or after calibration."""
        # For safety, guarantee that relaxed face always has a higher score than frowned
        if relaxed_score > frowned_score:
            self.relaxed_score = relaxed_score
            self.frowned_score = frowned_score
        else:
            # If values are swapped or identical, set reasonable default boundaries around them
            self.relaxed_score = max(relaxed_score, frowned_score) + 0.1
            self.frowned_score = min(relaxed_score, frowned_score) - 0.1

    def close(self) -> None:
        """Releases MediaPipe resources."""
        try:
            self.landmarker.close()
        except Exception:
            pass
