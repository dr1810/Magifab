"""Load Grounding DINO once and run a small bundled-image grounding request."""
from pathlib import Path
import sys
import time

sys.path.insert(0, str(Path(__file__).parents[1]))

import psutil
from PIL import Image

from adapters.grounding_dino_adapter import GroundingDINOAdapter
from config import get_settings

image = Image.open(Path(__file__).parents[2] / "public/posters/big-buck-bunny.jpg").convert("RGB")
started = time.perf_counter()
adapter = GroundingDINOAdapter(get_settings())
print("Loading Grounding DINO...", flush=True)
adapter.preload()
print(f"Finished Grounding DINO load in {time.perf_counter() - started:.2f}s; rss={psutil.Process().memory_info().rss / 1024 / 1024:.1f}MiB; device={adapter._device()}", flush=True)
started = time.perf_counter()
matches, _ = adapter.locate(image, ["rabbit"])
print(f"Grounding DINO inference succeeded in {time.perf_counter() - started:.2f}s; matches={len(matches)}", flush=True)
