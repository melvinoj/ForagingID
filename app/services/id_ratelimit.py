"""
Shared iNaturalist rate-limit primitives and the low-confidence threshold.

Extracted from the former app/services/identification.py (deleted) so that
scan.py's identification path and any other caller share the SAME semaphore
object — the single live iNaturalist request queue.

Importing ``_INAT_SEMAPHORE`` from here binds the one module-level Semaphore
(Python caches the module in ``sys.modules``), so every concurrent iNat call
across the app serialises through one gate, exactly as before the extraction.
Do not redefine these per-importer.
"""

import asyncio

# Results at or above this score are auto-approved onto the map immediately.
# Below this score (but PlantNet returned candidates): sent to review queue.
LOW_CONFIDENCE_THRESHOLD = 0.70

# iNaturalist vision rate-limit control. Sequential (1) + a short gap keeps
# batch bursts from tripping HTTP 429. Must remain a single shared object so
# scan and any re-identification share one queue.
_INAT_SEMAPHORE = asyncio.Semaphore(1)
INAT_DELAY_S = 1.0
