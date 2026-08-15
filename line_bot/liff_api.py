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
    get_topics_data, get_profile_data, get_profile_extras,
    get_pulse_data, get_compare_data,
)
from travel.leaderboards import get_all_boards

liff_bp = Blueprint("liff", __name__, url_prefix="/liff")

# token → (user_id, expiry_epoch)
_token_cache: dict[str, tuple[str, float]] = {}

# group_id → (name, expiry_epoch)
_group_name_cache: dict[str, tuple[str, float]] = {}
_GROUP_NAME_TTL = 3600  # 1 hour


def _get_group_name(group_id: str) -> str:
    """Fetch group name from LINE API, cached for 1 hour."""
    import json as _json
    token = os.getenv("LINE_CHANNEL_ACCESS_TOKEN", "")
    if not token or not group_id:
        return group_id

    now = time.time()
    cached = _group_name_cache.get(group_id)
    if cached and cached[1] > now:
        return cached[0]

    try:
        req = urllib.request.Request(
            f"https://api.line.me/v2/bot/group/{group_id}/summary",
            headers={"Authorization": f"Bearer {token}"},
        )
        with urllib.request.urlopen(req, timeout=5) as resp:
            body = _json.loads(resp.read())
        name = body.get("groupName", group_id)
    except Exception:
        name = group_id

    _group_name_cache[group_id] = (name, now + _GROUP_NAME_TTL)
    return name
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


def _resolve_group_id(user_id: str, group_id: str) -> str:
    """For admins: use ?g= override if given, else most active group.
    For regular users: use LIFF group context; if opened outside a group
    (no context), fall back to the user's own most-active group.
    """
    from travel.db import get_conn
    if _is_admin(user_id):
        override = request.args.get("g", "").strip()
        if override:
            return override
        with get_conn() as conn:
            row = conn.execute(
                "SELECT group_id FROM messages GROUP BY group_id ORDER BY COUNT(*) DESC LIMIT 1"
            ).fetchone()
        return row[0] if row else group_id
    # 一般成員：僅在「無群組情境」（group_id 為空，例如 1:1／rich menu 開啟）時
    # 才退回其最活躍群組。若明確帶入某群組，一律採用該值、交由 _require_member 驗證；
    # 非該群成員即回 403，避免以他群 group_id 跨群存取。
    # （前端 auth store 已用 /^C[0-9a-f]{32}$/ 過濾，非群組情境只會送空字串。）
    if user_id and not group_id:
        with get_conn() as conn:
            row = conn.execute(
                """SELECT group_id FROM messages WHERE user_id=?
                   GROUP BY group_id ORDER BY COUNT(*) DESC LIMIT 1""",
                (user_id,),
            ).fetchone()
        if row:
            return row[0]
    return group_id


def _require_member(user_id: str, group_id: str):
    """Return 403 tuple if user is not a member of group_id, else None.

    Admins bypass the check. If group_id is empty (opened outside LINE group
    context), fall back to any group the user has messages in.
    """
    if _is_admin(user_id):
        return None
    if not group_id:
        return _forbid("no_group_context")
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
    group_id = _resolve_group_id(user_id, _get_liff_group_id())
    err = _require_member(user_id, group_id)
    if err:
        return err
    days = int(request.args.get("days", 30))
    period = request.args.get("period", "all")
    data = get_dashboard_data(group_id, days, period)
    data["group_name"] = _get_group_name(group_id)
    return jsonify(data)


@liff_bp.route("/trips")
def trips():
    user_id = _get_liff_user_id()
    group_id = _resolve_group_id(user_id, _get_liff_group_id())
    err = _require_member(user_id, group_id)
    if err:
        return err
    return jsonify(get_trips_list(group_id))


@liff_bp.route("/trips/<trip_id>")
def trip_detail(trip_id):
    user_id = _get_liff_user_id()
    group_id = _resolve_group_id(user_id, _get_liff_group_id())
    err = _require_member(user_id, group_id)
    if err:
        return err
    data = get_trip_detail(trip_id)
    trip = data.get("trip", {})
    if not trip or not trip.get("id"):
        return jsonify({"error": "not_found"}), 404
    # 只能存取「目前瀏覽群組」所屬的 trip；admin 可跨群（?g= 群組切換一致）。
    if not _is_admin(user_id) and trip.get("group_id") != group_id:
        return _forbid("cross_group")
    return jsonify(data)


@liff_bp.route("/badges/<user_id>")
def badges(user_id):
    requester = _get_liff_user_id()
    group_id = _resolve_group_id(requester, _get_liff_group_id())
    if not _is_admin(requester) and requester != user_id:
        return _forbid("not_self_or_admin")
    if not _is_admin(requester) and group_id:
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
    group_id = body.get("group_id") or _resolve_group_id(user_id, _get_liff_group_id())
    start_date = body.get("start_date", 0)
    end_date = body.get("end_date")
    if end_date is not None:
        try:
            end_date = int(end_date)
        except (ValueError, TypeError):
            end_date = None

    trip_id = create_trip(
        group_id=group_id,
        title=body.get("title", ""),
        location=body.get("location", ""),
        start_date=start_date,
        end_date=end_date,
        trip_types=body.get("types", body.get("type")),
        custom_emoji=body.get("custom_emoji"),
        created_by=user_id,
    )
    return jsonify({"trip_id": trip_id, "status": "planning"})


@liff_bp.route("/admin/trips/<trip_id>/update", methods=["POST"])
def admin_update_trip(trip_id):
    user_id = _get_liff_user_id()
    if not _is_admin(user_id):
        return _forbid("not_admin")
    body = request.get_json() or {}
    from travel.trip_crud import update_trip

    start_date_raw = body.get("start_date")
    end_date_raw = body.get("end_date")
    try:
        start_date = int(start_date_raw) if start_date_raw is not None else None
    except (ValueError, TypeError):
        start_date = None
    if end_date_raw is None:
        end_date = None
    else:
        try:
            end_date = int(end_date_raw)
        except (ValueError, TypeError):
            end_date = None

    try:
        result = update_trip(
            trip_id,
            title=body.get("title"),
            location=body.get("location"),
            rarity=body.get("rarity"),
            trip_types=body.get("types", body.get("trip_types")),
            custom_emoji=body.get("custom_emoji"),
            start_date=start_date,
            end_date=end_date,
        )
        return jsonify(result)
    except ValueError as e:
        return jsonify({"error": str(e)}), 400


@liff_bp.route("/admin/trips/<trip_id>/title", methods=["POST"])
def admin_update_trip_title(trip_id):
    user_id = _get_liff_user_id()
    if not _is_admin(user_id):
        return _forbid("not_admin")
    body = request.get_json() or {}
    new_title = body.get("title", "")
    if not new_title:
        return jsonify({"error": "empty_title"}), 400
    from travel.trip_crud import update_trip_title
    result = update_trip_title(trip_id, new_title)
    return jsonify(result)


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


@liff_bp.route("/admin/analyze-topics", methods=["POST"])
def admin_analyze_topics():
    user_id = _get_liff_user_id()
    if not _is_admin(user_id):
        return _forbid("not_admin")
    from travel.llm_analyzer import run_monthly_analysis
    updated = run_monthly_analysis()
    return jsonify({"updated": updated, "success": True})


@liff_bp.route("/admin/groups")
def admin_groups():
    user_id = _get_liff_user_id()
    if not _is_admin(user_id):
        return _forbid("not_admin")
    from travel.db import get_conn
    with get_conn() as conn:
        rows = conn.execute(
            "SELECT group_id, COUNT(*) AS msg_count FROM messages GROUP BY group_id ORDER BY msg_count DESC"
        ).fetchall()
    groups = [{"group_id": r["group_id"], "msg_count": r["msg_count"],
               "name": _get_group_name(r["group_id"])} for r in rows]
    return jsonify(groups)


@liff_bp.route("/admin/members")
def admin_members():
    """回傳群組成員名單（seed 過的 members 表 + 尚未入表的 messages 送信者）。"""
    user_id = _get_liff_user_id()
    if not _is_admin(user_id):
        return _forbid("not_admin")
    group_id = _resolve_group_id(user_id, _get_liff_group_id())
    from travel.db import get_conn
    with get_conn() as conn:
        rows = conn.execute(
            """SELECT user_id, display_name, source, resolved
               FROM members WHERE group_id=?""",
            (group_id,),
        ).fetchall()
        members = [dict(r) for r in rows]
        known = {m["user_id"] for m in members}
        # 安全網：把已說話但不在 members 表的送信者補進來。
        senders = conn.execute(
            """SELECT user_id, user_name, COUNT(*) AS msg_count
               FROM messages WHERE group_id=? AND user_name IS NOT NULL
               GROUP BY user_id ORDER BY msg_count DESC""",
            (group_id,),
        ).fetchall()
    for s in senders:
        if s["user_id"] not in known:
            members.append({
                "user_id": s["user_id"],
                "display_name": s["user_name"],
                "source": "auto",
                "resolved": 1,
            })
    members.sort(key=lambda m: m["display_name"] or "")
    return jsonify(members)


@liff_bp.route("/periods")
def periods():
    """回傳目前 group 有資料的年 / 年月清單，供前端時間篩選。"""
    user_id = _get_liff_user_id()
    group_id = _resolve_group_id(user_id, _get_liff_group_id())
    err = _require_member(user_id, group_id)
    if err:
        return err
    from travel.db import get_conn
    with get_conn() as conn:
        year_rows = conn.execute(
            """SELECT DISTINCT strftime('%Y', timestamp/1000,'unixepoch') AS y
               FROM messages WHERE group_id=? ORDER BY y DESC""",
            (group_id,),
        ).fetchall()
        month_rows = conn.execute(
            """SELECT DISTINCT strftime('%Y-%m', timestamp/1000,'unixepoch') AS m
               FROM messages WHERE group_id=? ORDER BY m DESC""",
            (group_id,),
        ).fetchall()
    return jsonify({
        "years": [r["y"] for r in year_rows if r["y"]],
        "months": [r["m"] for r in month_rows if r["m"]],
    })


# ── Phase 3 分析 endpoints ───────────────────────────────────────────────────

@liff_bp.route("/leaderboard")
def leaderboard():
    user_id = _get_liff_user_id()
    group_id = _resolve_group_id(user_id, _get_liff_group_id())
    err = _require_member(user_id, group_id)
    if err:
        return err
    return jsonify(get_leaderboard_data(group_id, request.args.get("period", "all")))


@liff_bp.route("/leaderboards")
def leaderboards():
    """資料驅動排行榜（15 種）。與舊 /leaderboard 並存。"""
    user_id = _get_liff_user_id()
    group_id = _resolve_group_id(user_id, _get_liff_group_id())
    err = _require_member(user_id, group_id)
    if err:
        return err
    return jsonify(get_all_boards(group_id, request.args.get("period", "all")))


@liff_bp.route("/interactions")
def interactions():
    user_id = _get_liff_user_id()
    group_id = _resolve_group_id(user_id, _get_liff_group_id())
    err = _require_member(user_id, group_id)
    if err:
        return err
    return jsonify(get_interaction_data(group_id, request.args.get("period", "all")))


@liff_bp.route("/topics")
def topics():
    user_id = _get_liff_user_id()
    group_id = _resolve_group_id(user_id, _get_liff_group_id())
    err = _require_member(user_id, group_id)
    if err:
        return err
    return jsonify(get_topics_data(group_id, request.args.get("period", "all")))


@liff_bp.route("/profile/<target_user_id>")
def profile(target_user_id: str):
    requester = _get_liff_user_id()
    group_id = _resolve_group_id(requester, _get_liff_group_id())
    if not _is_admin(requester) and requester != target_user_id:
        return _forbid("not_self_or_admin")
    period = request.args.get("period", "all")
    return jsonify({
        **get_profile_data(target_user_id, group_id, period),
        **get_profile_extras(target_user_id, group_id, period),
    })


@liff_bp.route("/pulse")
def pulse():
    user_id = _get_liff_user_id()
    group_id = _resolve_group_id(user_id, _get_liff_group_id())
    err = _require_member(user_id, group_id)
    if err:
        return err
    return jsonify(get_pulse_data(group_id, request.args.get("period", "all")))


@liff_bp.route("/compare")
def compare():
    user_id = _get_liff_user_id()
    group_id = _resolve_group_id(user_id, _get_liff_group_id())
    err = _require_member(user_id, group_id)
    if err:
        return err
    a = request.args.get("a", "").strip()
    b = request.args.get("b", "").strip()
    if not a or not b:
        return jsonify({"error": "missing_users", "reason": "需要 a 與 b 兩個 user_id"}), 400
    return jsonify(get_compare_data(group_id, a, b, request.args.get("period", "all")))
