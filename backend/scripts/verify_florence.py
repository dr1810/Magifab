"""Load Florence-2 once and run inference on a bundled image."""
from pathlib import Path
import sys
import time

sys.path.insert(0, str(Path(__file__).parents[1]))

import psutil
from PIL import Image

from adapters.florence_adapter import FlorenceAdapter
from config import get_settings

image = Image.open(Path(__file__).parents[2] / "public/posters/big-buck-bunny.jpg").convert("RGB")
started = time.perf_counter()
adapter = FlorenceAdapter(get_settings())
print("Loading Florence-2...", flush=True)
adapter.preload()
print(f"Finished Florence-2 load in {time.perf_counter() - started:.2f}s; rss={psutil.Process().memory_info().rss / 1024 / 1024:.1f}MiB; device={adapter._device()}", flush=True)
started = time.perf_counter()
result, _ = adapter.understand(image)
print(f"Florence-2 inference succeeded in {time.perf_counter() - started:.2f}s; caption={result.scene_description!r}", flush=True)
