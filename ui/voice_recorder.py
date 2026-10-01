# -*- coding: utf-8 -*-
"""Grabación local de micrófono a WAV para Machine Builder Desktop."""
import io
import threading
import wave

import numpy as np
import sounddevice as sd


class MicrophoneRecorder:
    def __init__(self, samplerate=16000, channels=1):
        self.samplerate = int(samplerate)
        self.channels = int(channels)
        self._stream = None
        self._frames = []
        self._lock = threading.Lock()
        self._recording = False

    @property
    def recording(self):
        return self._recording

    def start(self):
        if self._recording:
            return
        self._frames = []

        def callback(indata, frames, time_info, status):
            if status:
                print("[Voice]", status)
            with self._lock:
                self._frames.append(indata.copy())

        self._stream = sd.InputStream(
            samplerate=self.samplerate,
            channels=self.channels,
            dtype="int16",
            callback=callback,
        )
        self._stream.start()
        self._recording = True

    def stop(self):
        if not self._recording:
            raise RuntimeError("No hay ninguna grabación activa.")
        self._recording = False
        if self._stream is not None:
            self._stream.stop()
            self._stream.close()
            self._stream = None

        with self._lock:
            frames = list(self._frames)
            self._frames = []
        if not frames:
            raise ValueError("No se ha recibido audio del micrófono.")

        audio = np.concatenate(frames, axis=0)
        output = io.BytesIO()
        with wave.open(output, "wb") as wav:
            wav.setnchannels(self.channels)
            wav.setsampwidth(2)
            wav.setframerate(self.samplerate)
            wav.writeframes(audio.tobytes())
        return output.getvalue()

    def cancel(self):
        self._recording = False
        if self._stream is not None:
            try:
                self._stream.stop()
                self._stream.close()
            finally:
                self._stream = None
        with self._lock:
            self._frames = []
