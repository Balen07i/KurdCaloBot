# gemini_queue.py
#
# Everything about NOT overwhelming Gemini's free-tier rate limit lives
# here, separate from vision.py's actual analysis logic:
#
#   1. A single background worker processes photos sequentially, with an
#      ADAPTIVE minimum gap between calls (AIMD-style: backs off hard on
#      real 429 evidence, cautiously speeds up after a sustained clean
#      streak) instead of a fixed guess.
#   2. A circuit breaker: after several consecutive rate-limit failures in
#      a row, stop wasting ~90s per job on doomed retries - fail fast for
#      everyone queued until a cooldown passes.
#   3. A duplicate-image cache (exact hash) - zero API cost for repeats.
#   4. A per-user cooldown, checked before a job is even queued.
#   5. A bounded queue depth - fails fast with a friendly message instead
#      of letting a burst turn into an unbounded wait.
#   6. Lightweight stats counters for real observability (see get_stats).
#
# bot.py should call submit_photo_job() instead of vision.estimate_calories()
# directly - this is the only supported entry point for actually running
# an analysis. Image optimization is the CALLER's responsibility (do it
# before submitting) so oversized images never sit in the queue.

import asyncio
import hashlib
import logging
import time

from vision import estimate_calories

logger = logging.getLogger(__name__)

# --- Adaptive pacing (AIMD) --------------------------------------------
#
# Starts at BASE_INTERVAL. On a real 429, multiply up toward MAX_INTERVAL
# immediately (protect reliability fast). After SUCCESS_STREAK_FOR_DECREASE
# consecutive clean successes, nudge down toward MIN_INTERVAL (cautiously
# use more of the real headroom if it turns out to be looser than our
# starting guess). This is standard rate-limit-adaptive behavior - safer
# than a fixed guess in either direction.
BASE_INTERVAL = 7.0
MIN_INTERVAL = 5.0
MAX_INTERVAL = 30.0
INTERVAL_INCREASE_FACTOR = 1.6
INTERVAL_DECREASE_STEP = 0.25
SUCCESS_STREAK_FOR_DECREASE = 6

# --- Circuit breaker -----------------------------------------------------
#
# After this many consecutive rate-limited failures, stop even trying for
# a cooldown period - every queued job gets an instant honest "busy"
# response instead of each one separately burning ~90s on retries that
# are very likely to fail too, given we just saw N of them fail in a row.
#
# The cooldown itself backs off exponentially on repeated re-trips (60s,
# 120s, 240s, capped at 300s) - a burst-style rate limit usually clears
# within one 60s window, but a genuinely exhausted daily/project quota
# won't clear for a long time, and probing every 60s for hours serves no
# purpose. Resets to the base cooldown the moment a real probe succeeds.
CIRCUIT_BREAKER_THRESHOLD = 3
CIRCUIT_BREAKER_COOLDOWN_SECONDS = 60.0
CIRCUIT_BREAKER_MAX_COOLDOWN_SECONDS = 300.0

# --- Other tunables --------------------------------------------------
USER_COOLDOWN_SECONDS = 8.0
DUPLICATE_CACHE_TTL_SECONDS = 3600
DUPLICATE_CACHE_MAX_ENTRIES = 500
MAX_QUEUE_SIZE = 40  # beyond this, fail fast rather than let waits balloon
STALE_USER_ENTRY_SECONDS = 3600  # cooldown-tracking cleanup horizon

RATE_LIMIT_MESSAGE_KURDISH = (
    "🚦 زۆر کەس لەم کاتەدا بۆتەکە بەکاردەهێنن. "
    "تکایە چەند چرکەیەک یان خولەکێک چاوەڕێ بکە و دووبارە هەوڵبدەرەوە."
)
QUEUE_FULL_MESSAGE_KURDISH = (
    "🚦 ئێستا بۆتەکە زۆر قەرەباڵغە. تکایە دەقیقەیەک چاوەڕێ بکە و دووبارە هەوڵبدەرەوە."
)
COOLDOWN_MESSAGE_KURDISH = "⏳ تکایە چەند چرکەیەک چاوەڕێ بکە پێش ناردنی وێنەیەکی تر."


# --- State (module-level, single-process - fine for one Railway instance) --

_queue: "asyncio.Queue | None" = None
_worker_task: "asyncio.Task | None" = None

_current_interval = BASE_INTERVAL
_consecutive_clean_successes = 0
_last_request_monotonic = 0.0

_consecutive_rate_limits = 0
_circuit_open_until = 0.0
_circuit_reopen_count = 0

_last_user_request: dict[int, float] = {}
_mark_call_count = 0

_result_cache: dict[str, tuple[float, dict]] = {}

_stats = {
    "total_submitted": 0,
    "cache_hits": 0,
    "queue_full_rejections": 0,
    "cooldown_rejections": 0,
    "successful_analyses": 0,
    "no_food_results": 0,
    "rate_limited_failures": 0,
    "other_failures": 0,
    "circuit_breaker_trips": 0,
    "circuit_breaker_short_circuits": 0,
    "started_at": time.monotonic(),
}


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
    global _mark_call_count
    _last_user_request[user_id] = time.monotonic()

    # Cheap opportunistic cleanup instead of a dedicated background task -
    # bounds memory growth from users who only ever send one photo.
    _mark_call_count += 1
    if _mark_call_count % 100 == 0:
        cutoff = time.monotonic() - STALE_USER_ENTRY_SECONDS
        stale = [uid for uid, t in _last_user_request.items() if t < cutoff]
        for uid in stale:
            del _last_user_request[uid]


def _record_pacing_feedback(result: dict):
    """Adjusts the adaptive interval and circuit breaker state based on
    what actually happened - this is the learning loop for both.
    Only ever called for REAL Gemini attempts (see _worker) - synthetic
    circuit-breaker short-circuits must never reach this function, or
    the circuit can re-justify staying open off its own output."""
    global _current_interval, _consecutive_clean_successes
    global _consecutive_rate_limits, _circuit_open_until, _circuit_reopen_count

    is_rate_limited = result.get("status") == "failed" and result.get("reason") == "rate_limited"

    if is_rate_limited:
        _stats["rate_limited_failures"] += 1
        _consecutive_clean_successes = 0
        _consecutive_rate_limits += 1
        _current_interval = min(_current_interval * INTERVAL_INCREASE_FACTOR, MAX_INTERVAL)
        logger.warning(
            "[ADAPTIVE_PACING] Rate limit seen, interval increased to %.1fs (consecutive: %d)",
            _current_interval, _consecutive_rate_limits,
        )
        if _consecutive_rate_limits >= CIRCUIT_BREAKER_THRESHOLD and time.monotonic() >= _circuit_open_until:
            cooldown = min(
                CIRCUIT_BREAKER_COOLDOWN_SECONDS * (2 ** _circuit_reopen_count),
                CIRCUIT_BREAKER_MAX_COOLDOWN_SECONDS,
            )
            _circuit_open_until = time.monotonic() + cooldown
            _circuit_reopen_count += 1
            _stats["circuit_breaker_trips"] += 1
            logger.error(
                "[CIRCUIT_BREAKER] Opening circuit for %.0fs after %d consecutive REAL rate-limit "
                "failures (reopen #%d - this cooldown grows if it keeps failing after reopening)",
                cooldown, _consecutive_rate_limits, _circuit_reopen_count,
            )
    else:
        _consecutive_rate_limits = 0
        _circuit_reopen_count = 0  # a genuine recovery - reset the backoff
        if result.get("status") == "ok":
            _stats["successful_analyses"] += 1
        elif result.get("status") == "no_food":
            _stats["no_food_results"] += 1
        else:
            _stats["other_failures"] += 1

        _consecutive_clean_successes += 1
        if _consecutive_clean_successes >= SUCCESS_STREAK_FOR_DECREASE:
            _current_interval = max(_current_interval - INTERVAL_DECREASE_STEP, MIN_INTERVAL)
            _consecutive_clean_successes = 0
            logger.info("[ADAPTIVE_PACING] Sustained clean streak, interval eased to %.1fs", _current_interval)


async def _worker():
    global _last_request_monotonic
    logger.info("[QUEUE] Gemini request worker started")
    while True:
        try:
            image_bytes, media_type, corrections, future = await _queue.get()
        except Exception:
            logger.critical("[WORKER_CRASH] Failed to read from queue - retrying loop", exc_info=True)
            await asyncio.sleep(1)
            continue

        try:
            if time.monotonic() < _circuit_open_until:
                logger.info("[CIRCUIT_BREAKER] Circuit open - short-circuiting without calling Gemini")
                _stats["circuit_breaker_short_circuits"] += 1
                result = {"status": "failed", "reason": "rate_limited"}
                # IMPORTANT: do NOT call _record_pacing_feedback here. This
                # result is synthetic (we never contacted Gemini) - feeding
                # it back into the same stats that decide whether to keep
                # the circuit open was a real bug: every short-circuited
                # request looked like "another confirmed 429", so once
                # tripped, the circuit could re-justify staying open off
                # its own defensive output indefinitely, and /stats'
                # rate_limited_failures counter conflated synthetic
                # short-circuits with genuine Gemini responses.
            else:
                elapsed = time.monotonic() - _last_request_monotonic
                wait = _current_interval - elapsed
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
                _record_pacing_feedback(result)  # only real attempts feed the stats

            if not future.done():
                future.set_result(result)
        except Exception:
            logger.critical("[WORKER_CRASH] Unexpected error processing job", exc_info=True)
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
    Enqueues an ALREADY-OPTIMIZED photo for analysis and waits for the
    result. Returns (result_dict, queue_position_at_submit_time).

    Optimize the image BEFORE calling this - the queue should never hold
    full-size originals, since that's real memory under any backlog.
    """
    _stats["total_submitted"] += 1

    image_hash = _hash_image(image_bytes)
    cached = _get_cached(image_hash)
    if cached is not None:
        logger.info("[CACHE] Duplicate image detected, reusing cached result")
        _stats["cache_hits"] += 1
        return cached, 0

    if _queue is None:
        start_worker()

    if _queue.qsize() >= MAX_QUEUE_SIZE:
        logger.warning("[QUEUE] Rejecting submission - queue full (%d items)", _queue.qsize())
        _stats["queue_full_rejections"] += 1
        return {"status": "failed", "reason": "queue_full"}, _queue.qsize()

    queue_position = _queue.qsize()

    future = asyncio.get_running_loop().create_future()
    await _queue.put((image_bytes, media_type, corrections, future))
    result = await future

    if result.get("status") == "ok":
        _store_cache(image_hash, result)

    return result, queue_position


def get_stats_summary() -> dict:
    """Returns a snapshot of runtime stats - wired to bot.py's /stats command."""
    uptime_seconds = time.monotonic() - _stats["started_at"]
    total = _stats["total_submitted"]
    cache_hit_rate = (_stats["cache_hits"] / total * 100) if total else 0.0
    return {
        **_stats,
        "uptime_minutes": round(uptime_seconds / 60, 1),
        "cache_hit_rate_pct": round(cache_hit_rate, 1),
        "current_pacing_interval": round(_current_interval, 1),
        "queue_depth": _queue.qsize() if _queue else 0,
        "circuit_open": time.monotonic() < _circuit_open_until,
        "cached_entries": len(_result_cache),
        "tracked_users": len(_last_user_request),
    }
