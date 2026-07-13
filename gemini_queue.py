# gemini_queue.py
#
# Everything about NOT overwhelming Gemini's free-tier rate limit lives
# here, separate from vision.py's actual analysis logic:
#
#   1. A single background worker processes photos sequentially (never in
#      parallel), with an enforced minimum gap between calls - this is
#      what actually prevents bursts of 429s when multiple users upload
#      at once, regardless of how many photos arrive simultaneously.
#   2. A duplicate-image cache (by content hash) skips calling Gemini
#      entirely for a photo that was already analyzed recently - zero
#      API cost for repeats.
#   3. A per-user cooldown, checked before a job is even queued, so one
#      spammy user can't hog the shared queue.
#
# bot.py should call submit_photo_job() instead of vision.estimate_calories()
# directly - this is the only supported entry point.

import asyncio
import hashlib
import logging
import time

from vision import estimate_calories

logger = logging.getLogger(__name__)

# --- Tunables --------------------------------------------------------
#
# MIN_SECONDS_BETWEEN_REQUESTS is the single most important knob for
# staying under Gemini's free-tier RPM limit. Google has cut free-tier
# limits before without much notice - if you start seeing "rate_limited"
# failures in the logs even with the queue in place, raise this number.
# Check your actual current limit at https://ai.google.dev/gemini-api/docs/rate-limits
MIN_SECONDS_BETWEEN_REQUESTS = 7.0  # ≈ 8-9 requests/minute, conservative

USER_COOLDOWN_SECONDS = 8.0  # one scan per user per this many seconds

DUPLICATE_CACHE_TTL_SECONDS = 3600  # reuse a result for the same photo for 1 hour
DUPLICATE_CACHE_MAX_ENTRIES = 200   # bounded memory - oldest entries evicted first

RATE_LIMIT_MESSAGE_KURDISH = (
    "🚦 زۆر کەس لەم کاتەدا بۆتەکە بەکاردەهێنن. "
    "تکایە چەند چرکەیەک یان خولەکێک چاوەڕێ بکە و دووبارە هەوڵبدەرەوە."
)

COOLDOWN_MESSAGE_KURDISH = "⏳ تکایە چەند چرکەیەک چاوەڕێ بکە پێش ناردنی وێنەیەکی تر."


# --- State (module-level, single-process - fine for one Railway instance) --

_queue: "asyncio.Queue | None" = None
_worker_task: "asyncio.Task | None" = None
_last_request_monotonic: float = 0.0
_last_request_lock: "asyncio.Lock | None" = None

_last_user_request: dict[int, float] = {}

# cache: hash -> (inserted_at_monotonic, result_dict)
_result_cache: dict[str, tuple[float, dict]] = {}


def _hash_image(image_bytes: bytes) -> str:
    return hashlib.sha256(image_bytes).hexdigest()


def _get_cached(image_hash: str) -> dict | None:
    entry = _result_cache.get(image_hash)
    if entry is None:
        return None
    inserted_at, result = entry
    if time.monotonic() - inserted_at > DUPLICATE_CACHE_TTL_SECONDS:
        del _result_cache[image_hash]
        return None
    return result


def _store_cache(image_hash: str, result: dict):
    if len(_result_cache) >= DUPLICATE_CACHE_MAX_ENTRIES:
        oldest_key = min(_result_cache, key=lambda k: _result_cache[k][0])
        del _result_cache[oldest_key]
    _result_cache[image_hash] = (time.monotonic(), result)


def check_user_cooldown(user_id: int) -> float:
    """Returns seconds remaining on cooldown (0 if the user can proceed)."""
    last = _last_user_request.get(user_id)
    if last is None:
        return 0.0
    remaining = USER_COOLDOWN_SECONDS - (time.monotonic() - last)
    return max(remaining, 0.0)


def mark_user_request(user_id: int):
    _last_user_request[user_id] = time.monotonic()


async def _worker():
    global _last_request_monotonic
    logger.info("[QUEUE] Gemini request worker started")
    while True:
        image_bytes, media_type, corrections, future = await _queue.get()
        try:
            elapsed = time.monotonic() - _last_request_monotonic
            wait = MIN_SECONDS_BETWEEN_REQUESTS - elapsed
            if wait > 0:
                logger.info("[QUEUE] Pacing: waiting %.1fs before next Gemini call", wait)
                await asyncio.sleep(wait)

            try:
                result = await asyncio.to_thread(
                    estimate_calories, image_bytes, media_type, corrections
                )
            except Exception:
                logger.exception("[QUEUE] Unhandled exception from estimate_calories")
                result = {"status": "failed", "reason": "other"}

            _last_request_monotonic = time.monotonic()

            if not future.done():
                future.set_result(result)
        except Exception:
            logger.exception("[QUEUE] Worker loop error")
            if not future.done():
                future.set_result({"status": "failed", "reason": "other"})
        finally:
            _queue.task_done()


def start_worker():
    """Call once, from inside a running event loop (e.g. PTB's post_init)."""
    global _queue, _worker_task
    if _worker_task is not None:
        return  # already running
    _queue = asyncio.Queue()
    _worker_task = asyncio.create_task(_worker())


async def submit_photo_job(
    image_bytes: bytes, media_type: str, corrections: list[dict]
) -> tuple[dict, int]:
    """
    Enqueues a photo for analysis and waits for the result.
    Returns (result_dict, queue_position_at_submit_time).

    result_dict either comes from the duplicate cache (instant, zero API
    cost) or from the paced worker queue.
    """
    image_hash = _hash_image(image_bytes)
    cached = _get_cached(image_hash)
    if cached is not None:
        logger.info("[CACHE] Duplicate image detected, reusing cached result")
        return cached, 0

    if _queue is None:
        start_worker()

    queue_position = _queue.qsize()

    future = asyncio.get_running_loop().create_future()
    await _queue.put((image_bytes, media_type, corrections, future))
    result = await future

    if result.get("status") == "ok":
        _store_cache(image_hash, result)

    return result, queue_position
