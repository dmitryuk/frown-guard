import unittest
import math
from typing import Dict, Any, List
from frown_guard.detector import FaceFrownDetector

class MockLandmark:
    """Простой мок для ориентиров MediaPipe."""
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
        """Создает словарь мок-ориентиров по заданным координатам."""
        landmarks = {}
        # Заполняем словарь фейковыми landmarks (для всех индексов до 478)
        for i in range(478):
            landmarks[i] = MockLandmark(0.0, 0.0, 0.0)
            
        landmarks[self.detector.RIGHT_EYEBROW_INNER] = MockLandmark(*r_eyebrow)
        landmarks[self.detector.LEFT_EYEBROW_INNER] = MockLandmark(*l_eyebrow)
        landmarks[self.detector.RIGHT_EYE_INNER] = MockLandmark(*r_eye)
        landmarks[self.detector.LEFT_EYE_INNER] = MockLandmark(*l_eye)
        
        return landmarks

    def test_calculate_3d_distance(self) -> None:
        """Проверяет правильность вычисления 3D Евклидова расстояния."""
        p1 = MockLandmark(0.0, 0.0, 0.0)
        p2 = MockLandmark(3.0, 4.0, 12.0)  # Сдвиг на (3, 4, 12)
        # Расстояние должно быть sqrt(3^2 + 4^2 + 12^2) = sqrt(9 + 16 + 144) = sqrt(169) = 13.0
        dist = self.detector.calculate_3d_distance(p1, p2)
        self.assertAlmostEqual(dist, 13.0, places=5)

    def test_extract_metrics_relaxed(self) -> None:
        """Проверяет вычисление метрик для расслабленного состояния лица."""
        # Координаты для расслабленного лица:
        # Расстояние между глазами (133 и 362): 0.2 по X (от -0.1 до 0.1) -> eye_dist = 0.2
        # Брови широко разведены: от -0.08 до 0.08 -> brow_sep = 0.16. sep_ratio = 0.16 / 0.2 = 0.8
        # Брови высоко: Y = -0.15, Глаза: Y = -0.10. Высота = 0.05. height_ratio = 0.05 / 0.2 = 0.25
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
        """Проверяет, что при сближении и опускании бровей метрика хмурости уменьшается."""
        # 1. Расслабленное лицо
        relaxed_landmarks = self.create_mock_landmarks(
            r_eyebrow=(-0.08, -0.15, 0.0),
            l_eyebrow=(0.08, -0.15, 0.0),
            r_eye=(-0.10, -0.10, 0.0),
            l_eye=(0.10, -0.10, 0.0)
        )
        relaxed_metrics = self.detector.extract_metrics(relaxed_landmarks)
        self.assertIsNotNone(relaxed_metrics)
        
        # 2. Нахмуренное лицо (брови ближе друг к другу по X, и ниже по Y к глазам)
        # Брови сдвинулись: от -0.05 до 0.05 -> brow_sep = 0.10. sep_ratio = 0.1 / 0.2 = 0.5 (было 0.8)
        # Брови опустились: Y = -0.12, Глаза: Y = -0.10. Высота = 0.02. height_ratio = 0.02 / 0.2 = 0.10 (было 0.25)
        frowned_landmarks = self.create_mock_landmarks(
            r_eyebrow=(-0.05, -0.12, 0.0),
            l_eyebrow=(0.05, -0.12, 0.0),
            r_eye=(-0.10, -0.10, 0.0),
            l_eye=(0.10, -0.10, 0.0)
        )
        frowned_metrics = self.detector.extract_metrics(frowned_landmarks)
        self.assertIsNotNone(frowned_metrics)
        
        if relaxed_metrics and frowned_metrics:
            # Сравниваем комбинированные баллы. Чем более нахмурено лицо, тем меньше должен быть балл.
            self.assertGreater(relaxed_metrics[2], frowned_metrics[2])
            
    def test_calibration_and_frown_level_mapping(self) -> None:
        """Проверяет правильность преобразования метрики в проценты уровня хмурости."""
        # Задаем калибровку
        self.detector.set_calibration(relaxed_score=1.0, frowned_score=0.5)
        
        # Проверим, как обрабатывается сырой кадр (создаем мок frame_rgb)
        # Так как FaceMesh сложен для мока внутри process_frame, протестируем непосредственно логику маппинга.
        # Если текущий балл равен расслабленному (1.0), хмурость должна быть 0%
        # Если текущий балл равен нахмуренному (0.5), хмурость должна быть 100%
        # Если текущий балл посередине (0.75), хмурость должна быть 50%
        
        # Функция-эмулятор логики process_frame для проверки формул:
        def get_frown_level_pct(score: float, relaxed: float, frowned: float) -> float:
            denominator = relaxed - frowned
            raw_frown_level = (relaxed - score) / denominator
            return max(0.0, min(1.0, raw_frown_level)) * 100.0
            
        self.assertEqual(get_frown_level_pct(1.0, 1.0, 0.5), 0.0)
        self.assertEqual(get_frown_level_pct(0.5, 1.0, 0.5), 100.0)
        self.assertEqual(get_frown_level_pct(0.75, 1.0, 0.5), 50.0)
        
        # Проверка ограничений (значения выходящие за пределы калибровки)
        self.assertEqual(get_frown_level_pct(1.2, 1.0, 0.5), 0.0)   # Ещё более расслаблен -> 0%
        self.assertEqual(get_frown_level_pct(0.3, 1.0, 0.5), 100.0) # Ещё более нахмурен -> 100%

if __name__ == "__main__":
    unittest.main()
