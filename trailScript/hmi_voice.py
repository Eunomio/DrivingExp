import os

import pygame


class HmiVoiceController:
    def __init__(self, base_dir, critical_sound_name, warning_threshold=18.0, critical_threshold=10.0):
        self.base_dir = base_dir
        self.warning_threshold = warning_threshold
        self.critical_threshold = critical_threshold
        self.warning_played = False
        self.critical_played = False
        self._init_failed = False

        if not pygame.get_init():
            pygame.init()

        try:
            if not pygame.mixer.get_init():
                pygame.mixer.init()
            if pygame.mixer.get_num_channels() < 8:
                pygame.mixer.set_num_channels(8)
        except Exception as exc:
            self._init_failed = True
            print(f"[HMI Voice] mixer init failed: {exc}")

        self.warning_sound = self._load_sound("warning.mp3")
        self.critical_sound = self._load_sound(critical_sound_name)

    def _load_sound(self, sound_name):
        if self._init_failed:
            return None

        sound_path = os.path.join(self.base_dir, sound_name)
        try:
            return pygame.mixer.Sound(sound_path)
        except Exception as exc:
            print(f"[HMI Voice] load failed for {sound_name}: {exc}")
            return None

    def _play_sound(self, sound, label, soc_pct):
        if sound is None:
            return

        try:
            channel = pygame.mixer.find_channel(True)
            if channel is not None:
                channel.play(sound)
            else:
                sound.play()
            print(f"[HMI Voice] played {label} at SOC={soc_pct:.3f}%")
        except Exception as exc:
            print(f"[HMI Voice] play failed for {label}: {exc}")

    def update(self, soc_pct):
        if soc_pct is None or self._init_failed:
            return

        if soc_pct <= self.warning_threshold and not self.warning_played:
            self.warning_played = True
            self._play_sound(self.warning_sound, "warning", soc_pct)

        if soc_pct <= self.critical_threshold and not self.critical_played:
            self.critical_played = True
            self._play_sound(self.critical_sound, "critical", soc_pct)