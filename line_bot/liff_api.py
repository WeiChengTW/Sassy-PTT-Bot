"""Flask Blueprint — LIFF API endpoints（一般 + 管理員）。"""
import os
import time
import urllib.parse
import urllib.request

from flask import Blueprint, request, jsonify

from travel.stats import get_dashboard_data, get_trips_list, get_trip_detail, get_user_badges
from travel.trip_crud import create_trip, add_participants, end_trip
from travel.badges import award_badges_for_trip
from travel.stats_extended import (
    get_leaderboard_data, get_interaction_data,
    get_topics_data, get_profile_data,
)

liff_bp = Blueprint("liff", __name__, url_prefix="/liff")

# token → (user_id, expiry_epoch)
_token_cache: dict[str, tuple[str, float]] = {}
_TOKEN_TTL = 300  # seconds


def _verify_liff_token(token: str) -> str | None:
    """Verify a LINE LIFF ID token via LINE's oauth2 verify endpoint.

    Returns user_id (sub) on success, None on failure.
    Falls back to None if LIFF_CHANNEL_ID is not configured.
    """
    channel_id = os.getenv("LIFF_CHANNEL_ID", "")
    if not channel_id:
        return None

    now = time.time()
    cached = _token_cache.get(token)
    if cached and cached[1] > now:
        return cached[0]

    try:
        import json as _json
        data = urllib.parse.urlencode({"id_token": token, "client_id": channel_id}).encode()
        req = urllib.request.Request(
            "https://api.line.me/oauth2/v2.1/verify",
            data=data,
            headers={"Content-Type": "application/x-www-form-urlencoded"},
            method="POST",
        )
        with urllib.request.urlopen(req, timeout=5) as resp:
            body = _json.loads(resp.read())
        user_id = body.get("sub", "")
        if user_id:
            _token_cache[token] = (user_id, now + _TOKEN_TTL)
            return user_id
    except Exception:
        pass
    return None


def _get_liff_user_id() -> str:
    """Extract verified user_id from Authorization header or fall back to X-LIFF-UserId.

    When LIFF_CHANNEL_ID is set, the Authorization: Bearer <id_token> header is
    required and verified. Without the env var (local dev), the plain header is accepted.
    """
    auth = request.headers.get("Authorization", "")
    if auth.startswith("Bearer "):
        token = auth[7:]
        verified = _verify_liff_token(token)
        if verified:
            return verified
        # Token present but verification failed → reject (empty string → 403 downstream)
        if os.getenv("LIFF_CHANNEL_ID"):
            return ""
    return request.headers.get("X-LIFF-UserId", "")


def _get_liff_group_id() -> str:
    return request.headers.get("X-LIFF-GroupId", request.args.get("group_id", ""))


def _admin_user_ids() -> set[str]:
    raw = os.getenv("ADMIN_USER_IDS", "")
    return {uid.strip() for uid in raw.split(",") if uid.strip()}


def _is_admin(user_id: str) -> bool:
    return user_id in _admin_user_ids()


def _is_member(user_id: str, group_id: str) -> bool:
    """True if user has any message in the group."""
    from travel.db import get_conn
    with get_conn() as conn:
        row = conn.execute(
            "SELECT 1 FROM messages WHERE user_id=? AND group_id=? LIMIT 1",
            (user_id, group_id),
        ).fetchone()
    return row is not None


def _forbid(reason: str):
    return jsonify({"error": "forbidden", "reason": reason}), 403


def _require_member(user_id: str, group_id: str):
    """Return 403 tuple if user is not a member of group_id, else None."""
    if not _is_member(user_id, group_id):
        return _forbid("not_member")
    return None


# ── 一般 endpoints ──────────────────────────────────────────────────────────

@liff_bp.route("/me")
def me():
    user_id = _get_liff_user_id()
    group_id = _get_liff_group_id()
    role = "admin" if _is_admin(user_id) else "member"
    return jsonify({"user_id": user_id, "role": role, "group_id": group_id})


@liff_bp.route("/dashboard")
def dashboard():
    user_id = _get_liff_user_id()
    group_id = _get_liff_group_id()
    err = _require_member(user_id, group_id)
    if err:
        return err
    days = int(request.args.get("days", 30))
    data = get_dashboard_data(group_id, days)
    return jsonify(data)


@liff_bp.route("/trips")
def trips():
    user_id = _get_liff_user_id()
    group_id = _get_liff_group_id()
    err = _require_member(user_id, group_id)
    if err:
        return err
    return jsonify(get_trips_list(group_id))


@liff_bp.route("/trips/<trip_id>")
def trip_detail(trip_id):
    user_id = _get_liff_user_id()
    group_id = _get_liff_group_id()
    data = get_trip_detail(trip_id)
    trip_group_id = data.get("trip", {}).get("group_id")
    if trip_group_id != group_id:
        return _forbid("cross_group")
    err = _require_member(user_id, trip_group_id)
    if err:
        return err
    return jsonify(data)


@liff_bp.route("/badges/<user_id>")
def badges(user_id):
    requester = _get_liff_user_id()
    group_id = _get_liff_group_id()
    if not _is_admin(requester) and requester != user_id:
        return _forbid("not_self_or_admin")
    if not _is_admin(requester):
        err = _require_member(requester, group_id)
        if err:
            return err
    return jsonify(get_user_badges(user_id, group_id))


# ── 管理員 endpoints ─────────────────────────────────────────────────────────

@liff_bp.route("/admin/trips", methods=["POST"])
def admin_create_trip():
    user_id = _get_liff_user_id()
    if not _is_admin(user_id):
        return _forbid("not_admin")
    body = request.get_json() or {}
    trip_id = create_trip(
        group_id=body.get("group_id") or _get_liff_group_id(),
        title=body.get("title", ""),
        location=body.get("location", ""),
        start_date=body.get("start_date", 0),
        trip_type=body.get("type"),
        created_by=user_id,
    )
    return jsonify({"trip_id": trip_id, "status": "planning"})


@liff_bp.route("/admin/trips/<trip_id>/participants", methods=["POST"])
def admin_add_participants(trip_id):
    user_id = _get_liff_user_id()
    if not _is_admin(user_id):
        return _forbid("not_admin")
    body = request.get_json() or {}
    result = add_participants(trip_id, body.get("user_ids", []))
    return jsonify(result)


@liff_bp.route("/admin/trips/<trip_id>/end", methods=["POST"])
def admin_end_trip(trip_id):
    user_id = _get_liff_user_id()
    if not _is_admin(user_id):
        return _forbid("not_admin")
    result = end_trip(trip_id)
    return jsonify(result)


@liff_bp.route("/admin/trips/<trip_id>/award-badges", methods=["POST"])
def admin_award_badges(trip_id):
    user_id = _get_liff_user_id()
    if not _is_admin(user_id):
        return _forbid("not_admin")
    awarded = award_badges_for_trip(trip_id)
    return jsonify({"awarded": awarded})


# ── Phase 3 分析 endpoints ───────────────────────────────────────────────────

@liff_bp.route("/leaderboard")
def leaderboard():
    user_id = _get_liff_user_id()
    group_id = _get_liff_group_id()
    err = _require_member(user_id, group_id)
    if err:
        return err
    return jsonify(get_leaderboard_data(group_id))


@liff_bp.route("/interactions")
def interactions():
    user_id = _get_liff_user_id()
    group_id = _get_liff_group_id()
    err = _require_member(user_id, group_id)
    if err:
        return err
    return jsonify(get_interaction_data(group_id))


@liff_bp.route("/topics")
def topics():
    user_id = _get_liff_user_id()
    group_id = _get_liff_group_id()
    err = _require_member(user_id, group_id)
    if err:
        return err
    return jsonify(get_topics_data(group_id))


@liff_bp.route("/profile/<target_user_id>")
def profile(target_user_id: str):
    requester = _get_liff_user_id()
    group_id = _get_liff_group_id()
    if not _is_admin(requester) and requester != target_user_id:
        return _forbid("not_self_or_admin")
    return jsonify(get_profile_data(target_user_id, group_id))
