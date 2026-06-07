"""Async, non-blocking wrappers over the in-memory Bytes API.

These offload the CPU-bound :func:`process_image` pipeline to a worker
thread so it never blocks an asyncio event loop (e.g. FastAPI routes).
Pillow/OpenCV release the GIL during encode/decode/resize, so threads
keep the loop responsive and allow real concurrency.

The work itself stays CPU-bound: these helpers change *where* it runs,
not its nature. They run on the event loop's default thread pool
(``asyncio.to_thread``), which has a bounded worker count managed by the
loop. ``process_images_async`` schedules all sources at once via ``gather``,
but the executor runs them at that bounded concurrency.

Cancelling the awaiting task (``task.cancel()``) abandons the *await*; the
underlying thread keeps running until ``process_image`` returns — standard
``asyncio.to_thread`` behavior.
"""

import asyncio
from typing import List, Optional, Sequence

from imgtools_m8.image_process import process_image
from imgtools_m8.results import VariantResult

__all__ = ["process_image_async", "process_images_async"]


async def process_image_async(
    source: bytes,
    output_options: List[dict],
    model_conf: Optional[dict] = None,
) -> List[VariantResult]:
    """Async, non-blocking counterpart of :func:`process_image`.

    Runs the synchronous pipeline in the loop's default ``ThreadPoolExecutor``
    via ``asyncio.to_thread`` so the calling event loop stays free. The
    processing remains CPU-bound — only its execution location changes.
    Same args, return value, and exceptions as :func:`process_image`.
    """
    return await asyncio.to_thread(process_image, source, output_options, model_conf)


async def process_images_async(
    sources: Sequence[bytes],
    output_options: List[dict],
    model_conf: Optional[dict] = None,
) -> List[List[VariantResult]]:
    """Process multiple source images concurrently.

    Applies the same ``output_options``/``model_conf`` to each source and
    fans the work out across worker threads with ``asyncio.gather``.
    Results preserve input order: one ``List[VariantResult]`` per source.
    All sources are scheduled together; if any fails, the first exception
    encountered by ``asyncio.gather`` is propagated to the caller (other
    threads may already be running and are not actively stopped).
    """
    if not sources:
        return []
    return await asyncio.gather(
        *(process_image_async(src, output_options, model_conf) for src in sources)
    )
