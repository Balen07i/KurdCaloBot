# gemini_queue.py
#
# Optimized for maximum useful throughput under a hard, fixed Gemini
# free-tier quota. Everything here exists to minimize the number of real
# Gemini requests made, in priority order of actual impact:
#
#   1. OPPORTUNISTIC BATCHING (the big one): if multiple photos are
#      ALREADY queued when the worker picks up work, they're analyzed in
#      ONE Gemini request instead of N. RPM limits count requests, not
#      images-per-request, so this is a direct, proportional reduction
#      under real concurrent load. Never adds artificial wait time for
#      the common single-photo case.
#   2. Exact-hash duplicate cache - zero API cost for byte-identical
#      repeats.
#   3. Conservative perceptual-hash (dHash) near-duplicate cache - catches
#      the same photo re-sent after lossy recompression (forwarding,
#      screenshotting), which breaks exact-hash matching. Strict Hamming
#      threshold, deliberately NOT used for "similar-looking food"
#      matching - see README for the accuracy-risk reasoning.
#   4. Local pre-filter (in vision.py, invoked from bot.py before this
#      module even sees the photo) - rejects obviously-invalid images
#      (blank/near-black frames) before they'd cost a request at all.
#   5. Dynamic/escalating per-user cooldown - normal meal-logging pace is
#      unaffected; rapid-fire submission patterns (testing, accidental
#      spam) get progressively throttled.
#   6. Adaptive pacing + circuit breaker - unchanged from the previous
#      round, still the safety net against actual 429s.
#
# bot.py should call submit_photo_job() instead of vision.estimate_calories()
# directly - this is the only supported entry point for actually running
# an analysis. Image optimization is the CALLER's responsibility (do it
# before submitting) so oversized images never sit in the queue.

import asyncio
import hashlib
import logging
import time

from vision import compute_dhash, estimate_calories, estimate_calories_batch, hamming_distance

logger = logging.getLogger(__name__)

# --- Batching ------------------------------------------------------------
#
# Capped low deliberately: a batch's fate is shared (one failed request
# fails every job in it), so a bigger cap means a bigger "blast radius"
# per failure. 3 is a reasonable balance - meaningful savings under real
# load, bounded downside if a batched call fails.
BATCH_SIZE = 3

# --- Adaptive pacing (AIMD) --------------------------------------------
BASE_INTERVAL = 7.0
MIN_INTERVAL = 5.0
MAX_INTERVAL = 30.0
INTERVAL_INCREASE_FACTOR = 1.6
INTERVAL_DECREASE_STEP = 0.25
SUCCESS_STREAK_FOR_DECREASE = 6

# --- Circuit breaker -----------------------------------------------------
CIRCUIT_BREAKER_THRESHOLD = 3
CIRCUIT_BREAKER_COOLDOWN_SECONDS = 60.0
CIRCUIT_BREAKER_MAX_COOLDOWN_SECONDS = 300.0

# --- Perceptual near-duplicate cache --------------------------------------
#
# Hamming distance out of 64 bits. Tested against real generated images:
# the same image re-compressed at very different JPEG quality lands at
# distance ~1; two genuinely different images land at ~31. A threshold of
# 4 leaves a huge safety margin against false positives while still
# catching real recompression-based near-duplicates.
PHASH_HAMMING_THRESHOLD = 4

# --- Dynamic per-user cooldown ---------------------------------------
#
# Normal meal-logging is a handful of photos per DAY, not per minute.
# Escalate the cooldown for users submitting unusually fast in a short
# window - this specifically targets testing/spam patterns without
# touching normal usage at all.
USER_COOLDOWN_SECONDS = 8.0
RAPID_FIRE_WINDOW_SECONDS = 300.0  # 5 minutes
RAPID_FIRE_ESCALATION_STEPS = [
    # (submissions within the window, cooldown to apply)
    (5, 20.0),
    (10, 60.0),
    (20, 180.0),
]

# --- Other tunables --------------------------------------------------
DUPLICATE_CACHE_TTL_SECONDS = 3600
DUPLICATE_CACHE_MAX_ENTRIES = 500
MAX_QUEUE_SIZE = 40
STALE_USER_ENTRY_SECONDS = 3600

RATE_LIMIT_MESSAGE_KURDISH = (
    "🚦 زۆر کەس لەم کاتەدا بۆتەکە بەکاردەهێنن. "
    "تکایە چەند چرکەیەک یان خولەکێک چاوەڕێ بکە و دووبارە هەوڵبدەرەوە."
)
QUEUE_FULL_MESSAGE_KURDISH = (
    "🚦 ئێستا بۆتەکە زۆر قەرەباڵغە. تکایە دەقیقەیەک چاوەڕێ بکە و دووبارە هەوڵبدەرەوە."
)
COOLDOWN_MESSAGE_KURDISH = "⏳ تکایە چەند چرکەیەک چاوەڕێ بکە پێش ناردنی وێنەیەکی تر."
RAPID_FIRE_MESSAGE_KURDISH = (
    "⏳ لەم کاتەدا وێنەی زۆرت ناردووە. تکایە کەمێک وازبهێنە پێش ناردنی وێنەیەکی تر."
)


# --- State (module-level, single-process - fine for one Railway instance) --

_queue: "asyncio.Queue | None" = None
_worker_task: "asyncio.Task | None" = None

# IMPORTANT: all pacing/circuit-breaker state below is PER-MODEL, not
# global. Flash and Flash-Lite are separate quota allocations on Google's
# side - a burst of 429s on one should never slow down or trip the
# breaker for the other, and each model's own pacer should be free to
# fire as soon as ITS interval allows, independent of when the other
# model was last called. This is what makes dual-model pooling actually
# increase combined throughput instead of just adding a fallback path.
_current_interval: dict[str, float] = {}
_consecutive_clean_successes: dict[str, int] = {}
_last_request_monotonic: dict[str, float] = {}

_consecutive_rate_limits: dict[str, int] = {}
_circuit_open_until: dict[str, float] = {}
_circuit_reopen_count: dict[str, int] = {}


def _interval(model: str) -> float:
    return _current_interval.setdefault(model, BASE_INTERVAL)


def _is_circuit_open(model: str) -> bool:
    return time.monotonic() < _circuit_open_until.get(model, 0.0)


def select_available_model(preferred_model: str, fallback_models: list[str] | None = None) -> str:
    """
    Dual-model quota pooling: if the preferred model's circuit is open
    (sustained real rate-limiting), automatically try any fallback model
    whose circuit is closed instead of just queueing/failing. Falls back
    to the preferred model if everything is unhealthy - no worse than
    before, just no longer stuck on ONE model when a second is available
    and healthy.
    """
    if not _is_circuit_open(preferred_model):
        return preferred_model

    for candidate in (fallback_models or []):
        if candidate and candidate != preferred_model and not _is_circuit_open(candidate):
            logger.info(
                "[MODEL_FAILOVER] %s circuit is open, routing to healthy fallback %s instead",
                preferred_model, candidate,
            )
            return candidate

    return preferred_model  # everything unhealthy - no better option, behaves as before

_last_user_request: dict[int, float] = {}
_recent_submission_times: dict[int, list[float]] = {}
_mark_call_count = 0

_result_cache: dict[str, tuple[float, dict]] = {}
_phash_index: dict[str, tuple[int, float]] = {}  # image_hash -> (dhash, inserted_at)

_stats = {
    "total_photos_received": 0,
    "total_submitted": 0,
    "cache_hits": 0,
    "phash_cache_hits": 0,
    "batched_requests_saved": 0,  # extra images that rode along in a batch instead of their own request
    "queue_depth_samples": 0,
    "queue_depth_sum": 0,
    "queue_depth_max": 0,
    "batching_opportunities": 0,
    "queue_full_rejections": 0,
    "cooldown_rejections": 0,
    "daily_limit_blocks": 0,
    "rapid_fire_escalations": 0,
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


def _get_cached_by_phash(dhash_value: int | None) -> dict | None:
    """Conservative near-duplicate lookup - see PHASH_HAMMING_THRESHOLD."""
    if dhash_value is None:
        return None
    now = time.monotonic()
    for image_hash, (stored_hash, inserted_at) in list(_phash_index.items()):
        if now - inserted_at > DUPLICATE_CACHE_TTL_SECONDS:
            del _phash_index[image_hash]
            continue
        if hamming_distance(dhash_value, stored_hash) <= PHASH_HAMMING_THRESHOLD:
            cached = _get_cached(image_hash)
            if cached is not None:
                return cached
    return None


def _store_cache(image_hash: str, result: dict, dhash_value: int | None):
    if len(_result_cache) >= DUPLICATE_CACHE_MAX_ENTRIES:
        oldest_key = min(_result_cache, key=lambda k: _result_cache[k][0])
        del _result_cache[oldest_key]
        _phash_index.pop(oldest_key, None)
    _result_cache[image_hash] = (time.monotonic(), result)
    if dhash_value is not None:
        _phash_index[image_hash] = (dhash_value, time.monotonic())


def check_user_cooldown(user_id: int) -> float:
    """Returns seconds remaining on cooldown (0 if the user can proceed).
    Escalates automatically for rapid-fire submission patterns within
    RAPID_FIRE_WINDOW_SECONDS - normal meal-logging pace never reaches
    the escalation thresholds."""
    last = _last_user_request.get(user_id)
    base_remaining = 0.0
    if last is not None:
        base_remaining = max(USER_COOLDOWN_SECONDS - (time.monotonic() - last), 0.0)

    now = time.monotonic()
    recent = [t for t in _recent_submission_times.get(user_id, []) if now - t <= RAPID_FIRE_WINDOW_SECONDS]
    _recent_submission_times[user_id] = recent

    required_cooldown = USER_COOLDOWN_SECONDS
    for threshold_count, escalated_cooldown in RAPID_FIRE_ESCALATION_STEPS:
        if len(recent) >= threshold_count:
            required_cooldown = escalated_cooldown

    if required_cooldown > USER_COOLDOWN_SECONDS and last is not None:
        escalated_remaining = max(required_cooldown - (now - last), 0.0)
        if escalated_remaining > base_remaining:
            _stats["rapid_fire_escalations"] += 1
            logger.info(
                "[RAPID_FIRE] User has %d submissions in the last %.0fs, "
                "escalating cooldown to %.0fs",
                len(recent), RAPID_FIRE_WINDOW_SECONDS, required_cooldown,
            )
        return escalated_remaining

    return base_remaining


def mark_user_request(user_id: int):
    global _mark_call_count
    now = time.monotonic()
    _last_user_request[user_id] = now
    _recent_submission_times.setdefault(user_id, []).append(now)

    _mark_call_count += 1
    if _mark_call_count % 100 == 0:
        cutoff = now - STALE_USER_ENTRY_SECONDS
        stale = [uid for uid, t in _last_user_request.items() if t < cutoff]
        for uid in stale:
            del _last_user_request[uid]
            _recent_submission_times.pop(uid, None)


def _record_pacing_feedback(result: dict, model: str):
    """Adjusts the adaptive interval and circuit breaker state for THIS
    model based on what actually happened. Only ever called for REAL
    Gemini attempts - synthetic circuit-breaker short-circuits must never
    reach this function, or the circuit can re-justify staying open off
    its own output (a real bug from a previous round, fixed and tested)."""

    is_rate_limited = result.get("status") == "failed" and result.get("reason") == "rate_limited"

    if is_rate_limited:
        _stats["rate_limited_failures"] += 1
        _consecutive_clean_successes[model] = 0
        _consecutive_rate_limits[model] = _consecutive_rate_limits.get(model, 0) + 1
        new_interval = min(_interval(model) * INTERVAL_INCREASE_FACTOR, MAX_INTERVAL)
        _current_interval[model] = new_interval
        logger.warning(
            "[ADAPTIVE_PACING] [%s] Rate limit seen, interval increased to %.1fs (consecutive: %d)",
            model, new_interval, _consecutive_rate_limits[model],
        )
        if (_consecutive_rate_limits[model] >= CIRCUIT_BREAKER_THRESHOLD
                and time.monotonic() >= _circuit_open_until.get(model, 0.0)):
            reopen_count = _circuit_reopen_count.get(model, 0)
            cooldown = min(
                CIRCUIT_BREAKER_COOLDOWN_SECONDS * (2 ** reopen_count),
                CIRCUIT_BREAKER_MAX_COOLDOWN_SECONDS,
            )
            _circuit_open_until[model] = time.monotonic() + cooldown
            _circuit_reopen_count[model] = reopen_count + 1
            _stats["circuit_breaker_trips"] += 1
            logger.error(
                "[CIRCUIT_BREAKER] [%s] Opening circuit for %.0fs after %d consecutive REAL "
                "rate-limit failures (reopen #%d)",
                model, cooldown, _consecutive_rate_limits[model], reopen_count + 1,
            )
    else:
        _consecutive_rate_limits[model] = 0
        _circuit_reopen_count[model] = 0
        if result.get("status") == "ok":
            _stats["successful_analyses"] += 1
        elif result.get("status") == "no_food":
            _stats["no_food_results"] += 1
        else:
            _stats["other_failures"] += 1

        streak = _consecutive_clean_successes.get(model, 0) + 1
        if streak >= SUCCESS_STREAK_FOR_DECREASE:
            _current_interval[model] = max(_interval(model) - INTERVAL_DECREASE_STEP, MIN_INTERVAL)
            streak = 0
            logger.info("[ADAPTIVE_PACING] [%s] Sustained clean streak, interval eased to %.1fs", model, _current_interval[model])
        _consecutive_clean_successes[model] = streak


def _drain_batch(target_model: str) -> list[tuple]:
    """Pulls up to BATCH_SIZE-1 MORE jobs that are ALREADY sitting in the
    queue and match target_model, without waiting for more to arrive.
    Jobs for a DIFFERENT model (from A/B testing) are put back rather
    than combined - a batch is one request, so it can only use one model.
    Returns a list of job tuples, length 0 to BATCH_SIZE-1."""
    matched = []
    requeue = []
    while len(matched) < BATCH_SIZE - 1:
        try:
            job = _queue.get_nowait()
        except asyncio.QueueEmpty:
            break
        if job[3] == target_model:  # job[3] is the model field
            matched.append(job)
        else:
            requeue.append(job)
    for job in requeue:
        _queue.put_nowait(job)
    return matched


async def _worker():
    logger.info("[QUEUE] Gemini request worker started")
    while True:
        try:
            first_job = await _queue.get()
        except Exception:
            logger.critical("[WORKER_CRASH] Failed to read from queue - retrying loop", exc_info=True)
            await asyncio.sleep(1)
            continue

        batch = [first_job]  # safe default in case anything below throws before this is overwritten
        try:
            # Opportunistic batching: grab whatever ELSE is already
            # waiting right now, never wait around hoping for more.
            queue_depth_at_pickup = _queue.qsize()
            _stats["queue_depth_samples"] += 1
            _stats["queue_depth_sum"] += queue_depth_at_pickup
            _stats["queue_depth_max"] = max(_stats["queue_depth_max"], queue_depth_at_pickup)
            if queue_depth_at_pickup > 0:
                _stats["batching_opportunities"] += 1
                logger.info(
                    "[BATCH_DIAG] %d job(s) already queued at pickup - batching opportunity",
                    queue_depth_at_pickup,
                )
            else:
                logger.info("[BATCH_DIAG] Queue was empty when this job was picked up - no batching opportunity existed")

            preferred_model = first_job[3]
            fallback_models = first_job[4]
            more_jobs = _drain_batch(preferred_model)
            batch = [first_job] + more_jobs
            for _ in more_jobs:
                _queue.task_done()  # first_job's task_done() happens in the outer finally

            # Dual-model quota pooling: pick whichever model is actually
            # healthy RIGHT NOW, not just the preferred one - this is what
            # lets a busy Flash quota get bailed out by a healthy
            # Flash-Lite quota (or vice versa) automatically.
            model = select_available_model(preferred_model, fallback_models)

            if _is_circuit_open(model):
                logger.info(
                    "[CIRCUIT_BREAKER] [%s] Circuit open (no healthy fallback either) - "
                    "short-circuiting %d job(s) without calling Gemini",
                    model, len(batch),
                )
                _stats["circuit_breaker_short_circuits"] += len(batch)
                for image_bytes, media_type, corrections, pref_model, fb_models, future in batch:
                    if not future.done():
                        future.set_result({"status": "failed", "reason": "rate_limited"})
            else:
                elapsed = time.monotonic() - _last_request_monotonic.get(model, 0.0)
                wait = _interval(model) - elapsed
                if wait > 0:
                    logger.info("[QUEUE] [%s] Pacing: waiting %.1fs before next Gemini call", model, wait)
                    await asyncio.sleep(wait)

                if len(batch) == 1:
                    image_bytes, media_type, corrections, pref_model, fb_models, future = batch[0]
                    try:
                        result = await asyncio.to_thread(
                            estimate_calories, image_bytes, media_type, corrections, model=model
                        )
                    except Exception:
                        logger.exception("[QUEUE] Unhandled exception from estimate_calories")
                        result = {"status": "failed", "reason": "other"}

                    _last_request_monotonic[model] = time.monotonic()
                    _record_pacing_feedback(result, model)
                    if not future.done():
                        future.set_result(result)
                else:
                    logger.info("[BATCH] Processing %d photos in ONE Gemini request (model: %s)", len(batch), model)
                    _stats["batched_requests_saved"] += len(batch) - 1
                    images = [(img, mt) for img, mt, _, _, _, _ in batch]
                    # All jobs in a batch necessarily share the same corrections
                    # snapshot timing-wise; using the first job's is fine since
                    # corrections change rarely relative to queue throughput.
                    corrections = batch[0][2]
                    try:
                        batch_result = await asyncio.to_thread(
                            estimate_calories_batch, images, corrections, model=model
                        )
                    except Exception:
                        logger.exception("[QUEUE] Unhandled exception from estimate_calories_batch")
                        batch_result = {"status": "failed", "reason": "other"}

                    _last_request_monotonic[model] = time.monotonic()
                    _record_pacing_feedback(batch_result, model)

                    if batch_result["status"] == "ok":
                        for (_, _, _, _, _, future), result in zip(batch, batch_result["results"]):
                            if not future.done():
                                future.set_result(result)
                    else:
                        # Shared fate: the whole batch failed as one request.
                        for _, _, _, _, _, future in batch:
                            if not future.done():
                                future.set_result(batch_result)

        except Exception:
            logger.critical("[WORKER_CRASH] Unexpected error processing batch", exc_info=True)
            try:
                for image_bytes, media_type, corrections, pref_model, fb_models, future in batch:
                    if not future.done():
                        future.set_result({"status": "failed", "reason": "other"})
            except Exception:
                pass
        finally:
            _queue.task_done()  # accounts for first_job


def start_worker():
    """Call once, from inside a running event loop (e.g. PTB's post_init)."""
    global _queue, _worker_task
    if _worker_task is not None:
        return
    _queue = asyncio.Queue()
    _worker_task = asyncio.create_task(_worker())


async def submit_photo_job(
    image_bytes: bytes, media_type: str, corrections: list[dict], model: str,
    fallback_models: list[str] | None = None,
) -> tuple[dict, int, int | None]:
    """
    Enqueues an ALREADY-OPTIMIZED, ALREADY-LOCALLY-VALIDATED photo for
    analysis and waits for the result. `model` is the PREFERRED model
    (decided by the caller, e.g. via vision.pick_model_for_user for A/B
    testing). `fallback_models` are other models to automatically try if
    the preferred one's quota is currently unhealthy (dual-model pooling
    - see select_available_model) - pass e.g. [vision.MODEL_NAME,
    vision.AB_TEST_MODEL] to let Flash and Flash-Lite cover for each
    other's rate limits.
    (bot.py, via vision.pick_model_for_user) - lets A/B testing assign a
    model per user before the photo ever reaches the queue.
    Returns (result_dict, queue_position, dhash_value) - the dhash is
    returned so callers (bot.py, for fingerprint logging) don't need to
    recompute it a second time; it was already computed here for the
    near-duplicate cache lookup.
    """
    _stats["total_submitted"] += 1

    image_hash = _hash_image(image_bytes)
    cached = _get_cached(image_hash)
    if cached is not None:
        logger.info("[CACHE] Exact duplicate image detected, reusing cached result")
        _stats["cache_hits"] += 1
        return cached, 0, None

    dhash_value = compute_dhash(image_bytes)
    near_cached = _get_cached_by_phash(dhash_value)
    if near_cached is not None:
        logger.info("[PHASH] Near-duplicate image detected (Hamming <= %d), reusing cached result", PHASH_HAMMING_THRESHOLD)
        _stats["phash_cache_hits"] += 1
        _store_cache(image_hash, near_cached, dhash_value)  # also index under this exact hash for next time
        return near_cached, 0, dhash_value

    if _queue is None:
        start_worker()

    if _queue.qsize() >= MAX_QUEUE_SIZE:
        logger.warning("[QUEUE] Rejecting submission - queue full (%d items)", _queue.qsize())
        _stats["queue_full_rejections"] += 1
        return {"status": "failed", "reason": "queue_full"}, _queue.qsize(), dhash_value

    queue_position = _queue.qsize()

    future = asyncio.get_running_loop().create_future()
    await _queue.put((image_bytes, media_type, corrections, model, fallback_models or [], future))
    result = await future

    if result.get("status") == "ok":
        _store_cache(image_hash, result, dhash_value)

    return result, queue_position, dhash_value


def record_photo_received():
    _stats["total_photos_received"] += 1


def record_cooldown_block():
    _stats["cooldown_rejections"] += 1


def record_daily_limit_block():
    _stats["daily_limit_blocks"] += 1


def get_stats_summary() -> dict:
    uptime_seconds = time.monotonic() - _stats["started_at"]
    total = _stats["total_submitted"]
    cache_hit_rate = ((_stats["cache_hits"] + _stats["phash_cache_hits"]) / total * 100) if total else 0.0
    avg_queue_depth = (
        _stats["queue_depth_sum"] / _stats["queue_depth_samples"]
        if _stats["queue_depth_samples"] else 0.0
    )
    per_model_health = {
        model: {
            "pacing_interval": round(_interval(model), 1),
            "circuit_open": _is_circuit_open(model),
        }
        for model in set(_current_interval) | set(_circuit_open_until)
    }
    return {
        **_stats,
        "uptime_minutes": round(uptime_seconds / 60, 1),
        "cache_hit_rate_pct": round(cache_hit_rate, 1),
        "queue_depth": _queue.qsize() if _queue else 0,
        "avg_queue_depth_at_pickup": round(avg_queue_depth, 2),
        "per_model_health": per_model_health,
        "cached_entries": len(_result_cache),
        "tracked_users": len(_last_user_request),
    }
