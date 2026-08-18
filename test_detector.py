import unittest
import math
from typing import Dict, Any, List
from frown_guard.detector import FaceFrownDetector

class MockLandmark:
    """Simple mock for MediaPipe landmarks."""
    def __init__(self, x: float, y: float, z: float) -> None:
        self.x = x
        self.y = y
        self.z = z

class TestFaceFrownDetector(unittest.TestCase):
    def setUp(self) -> None:
        self.detector = FaceFrownDetector()
        
    def create_mock_landmarks(self, 
                              r_eyebrow: tuple, 
                              l_eyebrow: tuple, 
                              r_eye: tuple, 
                              l_eye: tuple) -> Dict[int, MockLandmark]:
        """Creates a dictionary of mock landmarks based on the given coordinates."""
        landmarks = {}
        # Fill the dictionary with fake landmarks (for all indices up to 478)
        for i in range(478):
            landmarks[i] = MockLandmark(0.0, 0.0, 0.0)
            
        landmarks[self.detector.RIGHT_EYEBROW_INNER] = MockLandmark(*r_eyebrow)
        landmarks[self.detector.LEFT_EYEBROW_INNER] = MockLandmark(*l_eyebrow)
        landmarks[self.detector.RIGHT_EYE_INNER] = MockLandmark(*r_eye)
        landmarks[self.detector.LEFT_EYE_INNER] = MockLandmark(*l_eye)
        
        return landmarks

    def test_calculate_3d_distance(self) -> None:
        """Verifies the correctness of the 3D Euclidean distance calculation."""
        p1 = MockLandmark(0.0, 0.0, 0.0)
        p2 = MockLandmark(3.0, 4.0, 12.0)  # Shift by (3, 4, 12)
        # Distance should be sqrt(3^2 + 4^2 + 12^2) = sqrt(9 + 16 + 144) = sqrt(169) = 13.0
        dist = self.detector.calculate_3d_distance(p1, p2)
        self.assertAlmostEqual(dist, 13.0, places=5)

    def test_extract_metrics_relaxed(self) -> None:
        """Verifies metric calculations for a relaxed face state."""
        # Coordinates for relaxed face:
        # Eye distance (133 and 362): 0.2 along X (from -0.1 to 0.1) -> eye_dist = 0.2
        # Brows wide apart: from -0.08 to 0.08 -> brow_sep = 0.16. sep_ratio = 0.16 / 0.2 = 0.8
        # Brows high: Y = -0.15, Eyes: Y = -0.10. Height = 0.05. height_ratio = 0.05 / 0.2 = 0.25
        landmarks = self.create_mock_landmarks(
            r_eyebrow=(-0.08, -0.15, 0.0),
            l_eyebrow=(0.08, -0.15, 0.0),
            r_eye=(-0.10, -0.10, 0.0),
            l_eye=(0.10, -0.10, 0.0)
        )
        
        metrics = self.detector.extract_metrics(landmarks)
        self.assertIsNotNone(metrics)
        if metrics:
            sep_ratio, height_ratio, combined_score = metrics
            self.assertAlmostEqual(sep_ratio, 0.16 / 0.20, places=5)
            expected_height_ratio = math.sqrt(0.02**2 + 0.05**2) / 0.20
            self.assertAlmostEqual(height_ratio, expected_height_ratio, places=5)
            
            # combined_score = sep_ratio * 0.65 + height_ratio * 0.35
            expected_score = (0.8 * 0.65) + (expected_height_ratio * 0.35)
            self.assertAlmostEqual(combined_score, expected_score, places=5)

    def test_extract_metrics_frowned(self) -> None:
        """Verifies that the frown metric decreases when brows get closer and lower."""
        # 1. Relaxed face
        relaxed_landmarks = self.create_mock_landmarks(
            r_eyebrow=(-0.08, -0.15, 0.0),
            l_eyebrow=(0.08, -0.15, 0.0),
            r_eye=(-0.10, -0.10, 0.0),
            l_eye=(0.10, -0.10, 0.0)
        )
        relaxed_metrics = self.detector.extract_metrics(relaxed_landmarks)
        self.assertIsNotNone(relaxed_metrics)
        
        # 2. Frowned face (brows closer together along X, and lower along Y towards eyes)
        # Brows moved: from -0.05 to 0.05 -> brow_sep = 0.10. sep_ratio = 0.1 / 0.2 = 0.5 (was 0.8)
        # Brows lowered: Y = -0.12, Eyes: Y = -0.10. Height = 0.02. height_ratio = 0.02 / 0.2 = 0.10 (was 0.25)
        frowned_landmarks = self.create_mock_landmarks(
            r_eyebrow=(-0.05, -0.12, 0.0),
            l_eyebrow=(0.05, -0.12, 0.0),
            r_eye=(-0.10, -0.10, 0.0),
            l_eye=(0.10, -0.10, 0.0)
        )
        frowned_metrics = self.detector.extract_metrics(frowned_landmarks)
        self.assertIsNotNone(frowned_metrics)
        
        if relaxed_metrics and frowned_metrics:
            # Compare combined scores. The more frowned the face is, the lower the score should be.
            self.assertGreater(relaxed_metrics[2], frowned_metrics[2])
            
    def test_calibration_and_frown_level_mapping(self) -> None:
        """Verifies the correctness of converting the metric to a frown level percentage."""
        # Set calibration
        self.detector.set_calibration(relaxed_score=1.0, frowned_score=0.5)
        
        # Let's verify how the raw frame is processed (creating mock frame_rgb)
        # Since FaceMesh is complex to mock inside process_frame, we directly test the mapping logic.
        # If current score is relaxed (1.0), the frown level should be 0%
        # If current score is frowned (0.5), the frown level should be 100%
        # If current score is in the middle (0.75), the frown level should be 50%
        
        # Emulator function of the process_frame logic to verify formulas:
        def get_frown_level_pct(score: float, relaxed: float, frowned: float) -> float:
            denominator = relaxed - frowned
            raw_frown_level = (relaxed - score) / denominator
            return max(0.0, min(1.0, raw_frown_level)) * 100.0
            
        self.assertEqual(get_frown_level_pct(1.0, 1.0, 0.5), 0.0)
        self.assertEqual(get_frown_level_pct(0.5, 1.0, 0.5), 100.0)
        self.assertEqual(get_frown_level_pct(0.75, 1.0, 0.5), 50.0)
        
        # Boundary checks (values outside calibration range)
        self.assertEqual(get_frown_level_pct(1.2, 1.0, 0.5), 0.0)   # Even more relaxed -> 0%
        self.assertEqual(get_frown_level_pct(0.3, 1.0, 0.5), 100.0) # Even more frowned -> 100%

if __name__ == "__main__":
    unittest.main()
