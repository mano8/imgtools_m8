"""
ImgTools_m8 multiprocessing class with system resource monitoring.
"""

import logging
import multiprocessing
import os
import signal
import time
from os.path import join
from typing import List, Optional, Tuple

from imgtools_m8.helpers.scan_dir import ScanDir
from imgtools_m8.image_process import ImageProcessing

__author__ = "Eli Serra"
__copyright__ = "Copyright 2020, Eli Serra"
__deprecated__ = False
__license__ = "Apache Software License"
__status__ = "Production"
__version__ = "2.0.0"

try:
    import psutil

    PSUTIL_AVAILABLE = True
except ImportError:  # pragma: no cover
    PSUTIL_AVAILABLE = False
    psutil = None  # type: ignore[assignment]

try:
    from tqdm import tqdm

    TQDM_AVAILABLE = True
except ImportError:  # pragma: no cover
    TQDM_AVAILABLE = False
    tqdm = None  # type: ignore[assignment, misc]

logger = logging.getLogger("imgTools_m8")

_worker_processor: Optional[ImageProcessing] = None


def _init_worker(conf_dict: dict, model_conf_dict: Optional[dict]) -> None:
    """Initialize per-worker ImageProcessing instance; suppress SIGINT."""
    global _worker_processor
    _worker_processor = ImageProcessing(conf=conf_dict, model_conf=model_conf_dict)
    signal.signal(signal.SIGINT, signal.SIG_IGN)


def _process_one_file(source_path: str, file_data: dict) -> bool:
    """Process a single image file inside a worker process."""
    if _worker_processor is None:
        return False
    try:
        return _worker_processor.process_file(source_path=source_path, info=file_data)
    except Exception as exc:
        logging.getLogger("imgTools_m8").exception(
            "Worker error on %s: %s", source_path, exc
        )
        return False


class MultiProcessImage:
    """
    Multiprocessing image processor with resource monitoring and batching.
    """

    def __init__(
        self,
        conf: dict,
        model_conf: Optional[dict] = None,
        max_cpu_percent: int = 75,
        max_mem_percent: int = 80,
        max_disk_percent: int = 90,
        sleep_on_throttle: float = 1.0,
        user_cpu_percent: int = 50,
        use_progress: bool = True,
        batch_size: int = 32,
        num_processes: Optional[int] = None,
    ):
        """
        Initialize with processing config and system resource thresholds.

        Args:
            conf (dict): Processing configuration (ImageProcessingSchema).
            model_conf (Optional[dict]): DNN upscaling model config.
            max_cpu_percent (int): Throttle when CPU usage exceeds this.
            max_mem_percent (int): Throttle when RAM usage exceeds this.
            max_disk_percent (int): Throttle when disk usage exceeds this.
            sleep_on_throttle (float): Seconds to wait when throttling.
            user_cpu_percent (int): Target CPU share for worker processes.
            use_progress (bool): Show tqdm progress bar if available.
            batch_size (int): Number of images per pool batch.
            num_processes (Optional[int]): Override worker count directly.
        """
        self.conf_dict = conf
        self.model_conf_dict = model_conf
        self._processor = ImageProcessing(conf=conf, model_conf=model_conf)

        self.max_cpu_percent = max_cpu_percent
        self.max_mem_percent = max_mem_percent
        self.max_disk_percent = max_disk_percent
        self.sleep_on_throttle = sleep_on_throttle
        self.use_progress = use_progress and TQDM_AVAILABLE
        self.batch_size = batch_size
        self.interrupted = multiprocessing.Event()

        cpu_total = multiprocessing.cpu_count()
        safe_max = max(1, cpu_total - 1)  # always leave one core for the OS
        if num_processes is not None:
            if num_processes > safe_max:
                logger.warning(
                    "Requested %d workers exceeds safe limit (%d); clamping.",
                    num_processes,
                    safe_max,
                )
            self.num_processes = min(max(1, num_processes), safe_max)
        else:
            self.num_processes = max(1, int(cpu_total * (user_cpu_percent / 100.0)))

        signal.signal(signal.SIGINT, self._handle_signal)
        try:
            signal.signal(signal.SIGTERM, self._handle_signal)
        except (AttributeError, OSError):  # pragma: no cover
            pass  # SIGTERM unavailable on Windows

    def _handle_signal(self, signum, frame) -> None:
        """Mark interrupted state on SIGINT/SIGTERM."""
        logger.warning("Received signal %s. Shutting down...", signum)
        self.interrupted.set()

    def _system_resource_ok(self) -> bool:
        """Return False if CPU, RAM, or disk usage exceeds configured limits."""
        if not PSUTIL_AVAILABLE:  # pragma: no cover
            return True  # pragma: no cover
        if psutil.cpu_percent(interval=0.3) > self.max_cpu_percent:
            return False  # pragma: no cover
        if psutil.virtual_memory().percent > self.max_mem_percent:
            return False  # pragma: no cover
        try:
            disk = psutil.disk_usage(self._processor.conf.output_path)
            if disk.percent > self.max_disk_percent:
                return False  # pragma: no cover
        except OSError as exc:  # pragma: no cover
            logger.warning("Disk check failed: %s", exc)  # pragma: no cover
        return True

    def _collect_file_tasks(self) -> List[Tuple[str, dict]]:
        """Return (full_path, file_data) pairs for all valid source images."""
        if not self._processor.has_input_dir():
            return []
        ordered = ScanDir.get_ordered_files(
            source_path=self._processor.conf.source_path,
            include_subdirs=self._processor.conf.include_subdirs or False,
            byte_size=True,
            image_size=True,
        )
        if not isinstance(ordered, dict):  # pragma: no cover
            return []  # pragma: no cover
        tasks: List[Tuple[str, dict]] = []
        for _fmt, group in ordered.items():
            raw_root = group.get("root_dir")
            root_dir: str = (
                raw_root
                if isinstance(raw_root, str)
                else self._processor.conf.source_path
            )
            raw_files = group.get("files")
            files_iter = raw_files if isinstance(raw_files, list) else []
            for file_data in files_iter:
                if not isinstance(file_data, dict):  # pragma: no cover
                    continue  # pragma: no cover
                name = file_data.get("name", "")
                sub_dirs = file_data.get("sub_dirs")
                full_path = (
                    join(root_dir, *sub_dirs, name)
                    if isinstance(sub_dirs, list) and sub_dirs
                    else join(root_dir, name)
                )
                tasks.append((full_path, file_data))
        return tasks

    def run_multiple(self) -> bool:
        """
        Run batch image processing with multiprocessing and resource checks.

        Returns:
            bool: True if all images processed successfully, False otherwise.
        """
        if not self._processor.has_conf():  # pragma: no cover
            return False  # pragma: no cover
        os.makedirs(self._processor.conf.output_path, exist_ok=True)
        tasks = self._collect_file_tasks()
        if not tasks:
            logger.warning("No image files found.")
            return False

        total = len(tasks)
        result = True
        bar = (
            tqdm(total=total, desc="Processing", unit="img")
            if self.use_progress
            else None
        )

        try:
            with multiprocessing.Pool(
                processes=self.num_processes,
                initializer=_init_worker,
                initargs=(self.conf_dict, self.model_conf_dict),
            ) as pool:
                for i in range(0, total, self.batch_size):
                    if self.interrupted.is_set():
                        pool.terminate()
                        return False
                    while not self._system_resource_ok():
                        time.sleep(self.sleep_on_throttle)  # pragma: no cover
                    batch = tasks[i : i + self.batch_size]
                    if not all(pool.starmap(_process_one_file, batch)):
                        result = False
                    if bar:
                        bar.update(len(batch))
        except Exception as exc:
            logger.exception("Multiprocessing error: %s", exc)
            return False
        finally:
            if bar:
                bar.close()
        return result
