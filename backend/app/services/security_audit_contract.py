"""Security Audit Event v1.0 contract validation."""

from datetime import datetime, timedelta
from uuid import UUID


REASON_CODES = frozenset({
    "NO_DOCUMENT_ACCESS",
    "DIRECT_SHARE_VIEW",
    "DIRECT_SHARE_DOWNLOAD",
    "DIRECT_SHARE_EDIT",
    "TEAM_DEPARTMENT_VIEW",
    "INSUFFICIENT_DOCUMENT_PERMISSION",
    "DOCUMENT_OWNER_REQUIRED",
    "DOCUMENT_OWNER_ACCESS",
    "DOCUMENT_ACCESS_BLOCKED",
    "AUTHENTICATION_REQUIRED",
    "DOCUMENT_NOT_FOUND",
})

ALLOW_CODES = {
    ("owner", "edit"): "DOCUMENT_OWNER_ACCESS",
    ("team", "view"): "TEAM_DEPARTMENT_VIEW",
    ("share", "view"): "DIRECT_SHARE_VIEW",
    ("share", "download"): "DIRECT_SHARE_DOWNLOAD",
    ("share", "edit"): "DIRECT_SHARE_EDIT",
}

FIELDS = {
    "": {
        "schema_version", "timestamp", "request_id",
        "event_type", "actor", "resource", "action",
        "authorization", "result",
    },
    "actor": {"user_id"},
    "resource": {"type", "id"},
    "authorization": {
        "evaluated", "required_permission", "access_source",
        "effective_permission", "decision", "reason_code",
    },
    "result": {"outcome", "http_status"},
}


class AuditContractError(ValueError):
    """The event violates Security Audit Event v1.0."""


def validate_event(event):
    """Validate a document-detail audit event; raise on violations."""

    def require(condition, message):
        if not condition:
            raise AuditContractError(message)

    require(type(event) is dict, "event must be an object")

    for path, keys in FIELDS.items():
        obj = event if not path else event.get(path)
        require(type(obj) is dict, f"{path or 'event'} must be an object")
        require(set(obj) == keys, f"{path or 'event'} has invalid keys")

    a = event["authorization"]
    r = event["result"]
    actor = event["actor"]
    resource = event["resource"]

    require(type(event["schema_version"]) is int
            and event["schema_version"] == 1, "invalid schema_version")

    timestamp = event["timestamp"]
    require(type(timestamp) is str and timestamp.endswith("Z"),
            "timestamp must be UTC ISO 8601 with Z")
    try:
        parsed = datetime.fromisoformat(timestamp.replace("Z", "+00:00"))
        require(parsed.utcoffset() == timedelta(0), "timestamp must be UTC")
    except (ValueError, TypeError) as exc:
        raise AuditContractError("invalid timestamp") from exc

    request_id = event["request_id"]
    require(type(request_id) is str, "request_id must be a string")
    try:
        parsed_uuid = UUID(request_id)
        require(parsed_uuid.version == 4 and str(parsed_uuid) == request_id,
                "request_id must be canonical UUIDv4")
    except (ValueError, AttributeError) as exc:
        raise AuditContractError("invalid request_id") from exc

    require(event["event_type"] in {
        "document.authorization", "authentication", "document.lookup",
    } and type(event["event_type"]) is str, "invalid event_type")

    require(event["action"] == "view", "invalid detail action")
    require(resource["type"] == "document", "invalid resource type")
    require(type(resource["id"]) is int and resource["id"] > 0,
            "invalid document id")
    require(actor["user_id"] is None or
            (type(actor["user_id"]) is int and actor["user_id"] > 0),
            "invalid actor user_id")

    require(type(a["evaluated"]) is bool, "evaluated must be boolean")
    require(a["required_permission"] == "view",
            "invalid required_permission")
    require(a["access_source"] is None or
            (type(a["access_source"]) is str and
             a["access_source"] in {"owner", "team", "share"}),
            "invalid access_source")
    require(a["effective_permission"] is None or
            (type(a["effective_permission"]) is str and
             a["effective_permission"] in {"view", "download", "edit"}),
            "invalid effective_permission")
    require(type(a["decision"]) is str and
            a["decision"] in {"allow", "deny", "not_evaluated"},
            "invalid decision")
    require(type(a["reason_code"]) is str and
            a["reason_code"] in REASON_CODES,
            "invalid reason_code")

    require(type(r["http_status"]) is int and
            100 <= r["http_status"] <= 599, "invalid http_status")
    require(type(r["outcome"]) is str and
            r["outcome"] in {"success", "failure"}, "invalid outcome")
    require(r["outcome"] == (
        "success" if r["http_status"] < 400 else "failure"
    ), "outcome/http_status mismatch")

    source = a["access_source"]
    permission = a["effective_permission"]
    decision = a["decision"]
    reason = a["reason_code"]
    status = r["http_status"]

    if not a["evaluated"]:
        require(decision == "not_evaluated", "unevaluated decision mismatch")
        require(source is None and permission is None,
                "unevaluated access must be null")
        require(
            (event["event_type"] == "authentication"
             and reason == "AUTHENTICATION_REQUIRED"
             and actor["user_id"] is None and status == 401)
            or
            (event["event_type"] == "document.lookup"
             and reason == "DOCUMENT_NOT_FOUND"
             and actor["user_id"] is not None and status == 404),
            "invalid unevaluated event combination",
        )
    else:
        require(event["event_type"] == "document.authorization",
                "evaluated event_type mismatch")
        require(actor["user_id"] is not None, "evaluated actor missing")
        require(decision in {"allow", "deny"},
                "evaluated decision mismatch")

        if decision == "allow":
            require((source, permission) in ALLOW_CODES,
                    "invalid allowed access")
            require(reason == ALLOW_CODES[(source, permission)],
                    "allow reason_code mismatch")
        else:
            if reason == "NO_DOCUMENT_ACCESS":
                require(source is None and permission is None and status == 404,
                        "invalid no-access denial")
            elif reason == "DOCUMENT_ACCESS_BLOCKED":
                require((source, permission) in ALLOW_CODES and status == 403,
                        "invalid blocked denial")
            else:
                raise AuditContractError(
                    "reason_code not applicable to detail denial"
                )

    return True
