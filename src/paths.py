"""Local path handling for CLI inputs."""

import os
from pathlib import Path
import re


def local_path(value):
    value = str(value).strip().strip('\"').strip("'")
    if os.name != 'nt' and re.match(r'^[A-Za-z]:[\\/]', value):
        value = '/mnt/' + value[0].lower() + '/' + value[3:].replace('\\', '/')
    return Path(value).expanduser()
