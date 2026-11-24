import io
import unittest
import wave
from unittest import mock

import numpy as np

from frown_guard import sounds


class TestAlertSounds(unittest.TestCase):
    def test_builtin_chime_is_offered_first(self) -> None:
        available = sounds.available_sounds()
        self.assertEqual(available[0], sounds.CHIME)
        self.assertEqual(len(available), len(set(available)))

    def test_synth_chime_is_peak_normalized_and_decays(self) -> None:
        chime = sounds.synth_chime()
        self.assertEqual(len(chime), sounds.SAMPLE_RATE)
        self.assertAlmostEqual(float(np.max(np.abs(chime))), 1.0, places=6)
        quarter = len(chime) // 4
        self.assertGreater(np.abs(chime[:quarter]).max(), 10 * np.abs(chime[-quarter:]).max())

    def test_chime_wav_is_valid_mono_16bit(self) -> None:
        with wave.open(io.BytesIO(sounds._chime_wav_bytes())) as w:
            self.assertEqual(w.getnchannels(), 1)
            self.assertEqual(w.getsampwidth(), 2)
            self.assertEqual(w.getframerate(), sounds.SAMPLE_RATE)
            self.assertEqual(w.getnframes(), sounds.SAMPLE_RATE)

    def test_play_clamps_volume_and_never_raises(self) -> None:
        player = sounds.AlertPlayer()
        backend = "_play_mac" if player._mac else "_play_portable"
        with mock.patch.object(player, backend, side_effect=RuntimeError("no audio device")) as play:
            player.play(sounds.CHIME, 5.0)  # must not raise
        self.assertEqual(play.call_args.args[-1], 1.0)


if __name__ == "__main__":
    unittest.main()
