from __future__ import annotations

import os
import signal
import time


def sigterm_self_after_delay(delay_sec: float = 0.35) -> None:
    """Oprește procesul curent cu SIGTERM după un scurt delay.

    Folosit după trimiterea răspunsului HTTP (ex. BackgroundTasks). Cu politica Docker
    ``restart: unless-stopped``, oprirea procesului principal repornește containerul.
    """
    time.sleep(delay_sec)
    os.kill(os.getpid(), signal.SIGTERM)
