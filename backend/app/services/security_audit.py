"""Security Audit Event v1.0: document-detail only."""
import json
import logging
import sys
from datetime import datetime, timezone
from flask import g

AUDIT_LOGGER = logging.getLogger("sharehub.security_audit")
ERROR_LOGGER = logging.getLogger("sharehub.security_audit.error")
ALLOW_CODES = {
    ("owner", "edit"): "DOCUMENT_OWNER_ACCESS",
    ("team", "view"): "TEAM_DEPARTMENT_VIEW",
    ("share", "view"): "DIRECT_SHARE_VIEW",
    ("share", "download"): "DIRECT_SHARE_DOWNLOAD",
    ("share", "edit"): "DIRECT_SHARE_EDIT",
}

def initialize_detail(document_id):
    g.security_detail = {
        "document_id": document_id,
        "user_id": None,
        "evaluated": False,
        "source": None,
        "permission": None,
        "decision": "not_evaluated",
        "reason": None,
        "event_type": None,
        "emitted": False,
    }


def authentication_failed():
    state = g.get("security_detail")
    if state is not None:
        state["reason"] = "AUTHENTICATION_REQUIRED"
        state["event_type"] = "authentication"


def authenticated(user_id):
    state = g.get("security_detail")
    if state is not None:
        state["user_id"] = user_id


def document_not_found():
    state = g.get("security_detail")
    if state is not None:
        state["reason"] = "DOCUMENT_NOT_FOUND"
        state["event_type"] = "document.lookup"

def evaluated(access, reason, decision):
    state = g.security_detail
    state.update(evaluated=True, source=access["source"],
                 permission=access["permission"], reason=reason,
                 decision=decision, event_type="document.authorization")

def allowed_code(access):
    return ALLOW_CODES[(access["source"], access["permission"])]

def emit_detail(response):
    state = g.get("security_detail")
    if state is None or state["emitted"]:
        return
    state["emitted"] = True
    if (
        state["reason"] is None
        or state["event_type"] is None
    ):
        ERROR_LOGGER.error("audit_incomplete request_id=%s", g.get("request_id"))
        return
    event = {
        "schema_version": 1,
        "timestamp": datetime.now(timezone.utc).isoformat(timespec="microseconds").replace("+00:00", "Z"),
        "request_id": g.request_id,
        "event_type": state["event_type"],
        "actor": {"user_id": state["user_id"]},
        "resource": {"type": "document", "id": state["document_id"]},
        "action": "view",
        "authorization": {
            "evaluated": state["evaluated"], "required_permission": "view",
            "access_source": state["source"],
            "effective_permission": state["permission"],
            "decision": state["decision"], "reason_code": state["reason"],
        },
        "result": {
            "outcome": "success" if response.status_code < 400 else "failure",
            "http_status": response.status_code,
        },
    }
    try:
        AUDIT_LOGGER.info(json.dumps(event, ensure_ascii=False, separators=(",", ":")))
    except Exception as exc:
        try:
            ERROR_LOGGER.error("audit_emit_failed request_id=%s failure_type=%s",
                               g.get("request_id"), type(exc).__name__)
        except Exception:
            pass

def configure_audit_logger():
    """Configure security audit loggers once per process."""
    for logger in (AUDIT_LOGGER, ERROR_LOGGER):
        logger.setLevel(logging.INFO)
        logger.propagate = False

        if not any(
            getattr(handler, "_sharehub_audit_handler", False)
            for handler in logger.handlers
        ):
            handler = logging.StreamHandler(sys.stderr)
            handler.setLevel(logging.INFO)
            handler.setFormatter(logging.Formatter("%(message)s"))
            handler._sharehub_audit_handler = True
            logger.addHandler(handler)