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
    Класс для обнаружения хмурости на лице с использованием MediaPipe Tasks FaceLandmarker.
    Вычисляет расстояние между бровями и расстояние от бровей до глаз,
    нормализует их и преобразует в интуитивный уровень хмурости (0-100%).
    """
    
    # Ключевые индексы ориентиров MediaPipe Face Mesh:
    RIGHT_EYEBROW_INNER = 107
    LEFT_EYEBROW_INNER = 336
    RIGHT_EYE_INNER = 133
    LEFT_EYE_INNER = 362
    
    def __init__(self, model_path: str = "face_landmarker.task") -> None:
        # Если запущено из скомпилированного бинарного файла PyInstaller
        if getattr(sys, "frozen", False) and hasattr(sys, "_MEIPASS"):
            model_path = os.path.join(sys._MEIPASS, "face_landmarker.task")
            
        # Проверяем наличие файла модели
        if not os.path.exists(model_path):
            raise FileNotFoundError(
                f"Файл модели MediaPipe '{model_path}' не найден. "
                "Убедитесь, что он скачан и находится в корневом каталоге проекта."
            )
            
        # Настройка параметров MediaPipe Tasks FaceLandmarker
        base_options = python.BaseOptions(model_asset_path=model_path)
        options = vision.FaceLandmarkerOptions(
            base_options=base_options,
            running_mode=vision.RunningMode.IMAGE,
            num_faces=1,
            output_face_blendshapes=True
        )
        self.landmarker = vision.FaceLandmarker.create_from_options(options)
        
        # Калибровочные значения по умолчанию
        self.relaxed_score: float = 1.20
        self.frowned_score: float = 0.85
        self.sensitivity: float = 50.0  # Процент чувствительности (0 - 100)
        
    def calculate_3d_distance(self, p1: Any, p2: Any) -> float:
        """Вычисляет Евклидово расстояние между двумя 3D-точками."""
        return math.sqrt(
            (p1.x - p2.x) ** 2 + 
            (p1.y - p2.y) ** 2 + 
            (p1.z - p2.z) ** 2
        )

    def extract_metrics(self, landmarks: Any) -> Optional[Tuple[float, float, float]]:
        """
        Извлекает ключевые метрики лица:
        - sep_ratio: расстояние между бровями, нормализованное по расстоянию между глазами.
        - height_ratio: среднее расстояние от бровей до глаз, нормализованное по расстоянию между глазами.
        - combined_score: взвешенная сумма метрик (чем больше значение, тем более расслаблено лицо).
        """
        try:
            # Получаем ориентиры
            r_eyebrow = landmarks[self.RIGHT_EYEBROW_INNER]
            l_eyebrow = landmarks[self.LEFT_EYEBROW_INNER]
            r_eye = landmarks[self.RIGHT_EYE_INNER]
            l_eye = landmarks[self.LEFT_EYE_INNER]
            
            # Базовое расстояние между внутренними уголками глаз (для нормализации)
            eye_dist = self.calculate_3d_distance(r_eye, l_eye)
            if eye_dist < 1e-5:
                return None
                
            # Сведение бровей (расстояние между внутренними краями бровей)
            brow_sep = self.calculate_3d_distance(r_eyebrow, l_eyebrow)
            sep_ratio = brow_sep / eye_dist
            
            # Высота бровей (расстояние от внутренних краев бровей до внутренних уголков глаз)
            r_height = self.calculate_3d_distance(r_eyebrow, r_eye)
            l_height = self.calculate_3d_distance(l_eyebrow, l_eye)
            height_ratio = (r_height + l_height) / (2.0 * eye_dist)
            
            # Комбинированная метрика хмурости.
            # Больше вес дается сведению бровей (0.65), так как при хмурости брови сближаются.
            # Опускание бровей имеет вес (0.35).
            combined_score = (sep_ratio * 0.65) + (height_ratio * 0.35)
            
            return sep_ratio, height_ratio, combined_score
            
        except Exception as e:
            print(f"Ошибка при вычислении метрик лица: {e}")
            return None

    def process_frame(self, frame_rgb: np.ndarray) -> Tuple[Optional[Dict[str, Any]], Optional[Any]]:
        """
        Обрабатывает кадр изображения и возвращает словарь с метриками и объект landmarks.
        """
        # Преобразуем кадр в формат MediaPipe Image
        mp_image = mp.Image(image_format=mp.ImageFormat.SRGB, data=frame_rgb)
        
        results = self.landmarker.detect(mp_image)
        
        if not results.face_landmarks:
            return None, None
            
        landmarks = results.face_landmarks[0]
        
        # 1. Попытка использовать помехоустойчивые блендшейпы (не зависящие от поворота головы)
        combined_score = None
        if results.face_blendshapes:
            try:
                # Превращаем список категорий в удобный словарь
                blendshapes = {c.category_name: c.score for c in results.face_blendshapes[0]}
                
                # Интенсивность хмурости (сведение бровей вместе и опускание)
                frown_val = (blendshapes.get('browDownLeft', 0.0) + blendshapes.get('browDownRight', 0.0)) / 2.0
                
                # Интенсивность удивления / морщин на лбу (подъем бровей вверх)
                raise_val = (blendshapes.get('browOuterUpLeft', 0.0) + blendshapes.get('browOuterUpRight', 0.0)) / 2.0
                
                # Общая активность мимики лба/бровей.
                # Берем максимум между классической хмуростью и наморщиванием лба.
                activity = max(frown_val, raise_val)
                
                # Переводим в шкалу: 1.20 (полностью расслаблен) - 0.60 (напряжен)
                # Это сохраняет обратную совместимость с нашими геометрическими калибровками
                combined_score = 1.20 - (activity * 0.60)
            except Exception as e:
                print(f"Ошибка извлечения блендшейпов: {e}")
                
        # 2. Резервный геометрический расчет (если блендшейпы по какой-то причине недоступны)
        metrics = self.extract_metrics(landmarks)
        if metrics is None and combined_score is None:
            return None, landmarks
            
        sep_ratio, height_ratio, geom_score = metrics if metrics else (1.0, 0.5, 1.0)
        
        if combined_score is None:
            combined_score = geom_score
            
        # Рассчитываем уровень хмурости в процентах (0% - спокойное лицо, 100% - нахмуренное)
        # Если текущий score близок к relaxed_score, frown_level -> 0
        # Если текущий score близок к frowned_score, frown_level -> 100%
        denominator = self.relaxed_score - self.frowned_score
        if abs(denominator) < 1e-5:
            denominator = 0.1
            
        raw_frown_level = (self.relaxed_score - combined_score) / denominator
        # Ограничиваем значение от 0.0 до 1.0 (т.е. от 0% до 100%)
        frown_level_pct = max(0.0, min(1.0, raw_frown_level)) * 100.0
        
        # Определяем порог срабатывания на основе чувствительности.
        # При чувствительности 50% порог находится ровно посередине между relaxed и frowned.
        # Чем выше чувствительность, тем меньшего изменения мимики достаточно для срабатывания.
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
        """Устанавливает калибровочные значения вручную или после калибровки."""
        # Для безопасности гарантируем, что расслабленное лицо всегда имеет больший балл, чем нахмуренное
        if relaxed_score > frowned_score:
            self.relaxed_score = relaxed_score
            self.frowned_score = frowned_score
        else:
            # Если значения перепутаны или одинаковы, задаем дефолтные разумные рамки вокруг них
            self.relaxed_score = max(relaxed_score, frowned_score) + 0.1
            self.frowned_score = min(relaxed_score, frowned_score) - 0.1

    def close(self) -> None:
        """Освобождает ресурсы MediaPipe."""
        try:
            self.landmarker.close()
        except Exception:
            pass
