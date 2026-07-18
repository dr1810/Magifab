"""Load YOLO once and run inference on a bundled image."""
from pathlib import Path
import sys
import time

sys.path.insert(0, str(Path(__file__).parents[1]))

import psutil
from PIL import Image

from adapters.yolo_adapter import YOLOAdapter
from config import get_settings

image = Image.open(Path(__file__).parents[2] / "public/posters/big-buck-bunny.jpg").convert("RGB")
started = time.perf_counter()
adapter = YOLOAdapter(get_settings())
print("Loading YOLO...", flush=True)
adapter.preload()
print(f"Finished YOLO load in {time.perf_counter() - started:.2f}s; rss={psutil.Process().memory_info().rss / 1024 / 1024:.1f}MiB; device={adapter._device()}", flush=True)
started = time.perf_counter()
detections, _ = adapter.detect(image)
print(f"YOLO inference succeeded in {time.perf_counter() - started:.2f}s; detections={len(detections)}", flush=True)
