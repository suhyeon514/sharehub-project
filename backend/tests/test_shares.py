"""Run with: python -m unittest discover -s tests -v"""
import secrets
import unittest
from datetime import datetime, timedelta, timezone

from app import create_app
from app.extensions import db
from app.models import Department, Document, DocumentShare, Session, User
from app.services.document_permissions import can_manage_shares


class ShareListTests(unittest.TestCase):
    def setUp(self):
        self.app = create_app({
            "TESTING": True,
            "SQLALCHEMY_DATABASE_URI": "sqlite:///:memory:",
        })
        with self.app.app_context():
            db.create_all()
            department = Department(name="Test team")
            db.session.add(department)
            db.session.flush()
            users = {}
            self.tokens = {}
            self.user_ids = {}
            for name in ("owner", "admin", "viewer", "editor", "unrelated", "no_dept"):
                user = User(
                    username=name, password_hash="unused-test-value",
                    role="admin" if name == "admin" else "user",
                    department_id=None if name == "no_dept" else department.id,
                )
                db.session.add(user)
                db.session.flush()
                users[name] = user
                self.user_ids[name] = user.id
                token = secrets.token_urlsafe(32)
                self.tokens[name] = token
                db.session.add(Session(
                    user_id=user.id, session_token=token,
                    expires_at=datetime.now(timezone.utc) + timedelta(hours=1),
                    is_active=True,
                ))
            document = Document(
                title="Test shared document", owner_id=users["owner"].id,
                department_id=department.id, visibility="shared",
                file_path="not-a-real-file", original_filename="test.txt",
            )
            empty = Document(
                title="Empty", owner_id=users["owner"].id,
                visibility="private", file_path="not-a-real-file",
                original_filename="empty.txt",
            )
            db.session.add_all([document, empty])
            db.session.flush()
            self.document_id, self.empty_id = document.id, empty.id
            for name, permission in (("viewer", "view"), ("editor", "edit")):
                db.session.add(DocumentShare(
                    document_id=document.id, shared_by_id=users["owner"].id,
                    shared_with_id=users[name].id, permission=permission,
                ))
            db.session.commit()
        self.client = self.app.test_client()

    def tearDown(self):
        with self.app.app_context():
            db.session.remove()
            db.engine.dispose()

    def get_list(self, user="owner", document_id=None, query_string=None):
        document_id = self.document_id if document_id is None else document_id
        headers = {"Authorization": f"Bearer {self.tokens[user]}"} if user else {}
        return self.client.get(
            f"/api/documents/{document_id}/shares",
            headers=headers, query_string=query_string,
        )

    def test_owner_and_admin_receive_only_contract_fields(self):
        for user in ("owner", "admin"):
            with self.subTest(user=user):
                response = self.get_list(user)
                self.assertEqual(response.status_code, 200)
                data = response.get_json()
                self.assertEqual(set(data), {"document", "shares"})
                self.assertEqual(data["document"], {
                    "id": self.document_id, "title": "Test shared document",
                })
                self.assertEqual(
                    [(s["shared_with"]["username"], s["permission"]) for s in data["shares"]],
                    [("viewer", "view"), ("editor", "edit")],
                )
                for share in data["shares"]:
                    self.assertEqual(set(share), {"id", "shared_with", "permission"})
                    self.assertEqual(set(share["shared_with"]), {"id", "username"})

    def test_non_managers_cannot_read_or_spoof_owner(self):
        for user in ("viewer", "editor", "unrelated", "no_dept"):
            with self.subTest(user=user):
                response = self.get_list(user, query_string={
                    "user_id": self.user_ids["owner"], "role": "admin",
                })
                self.assertEqual(response.status_code, 403)
                self.assertEqual(set(response.get_json()), {"message"})

    def test_empty_list_is_success(self):
        for user in ("owner", "admin"):
            response = self.get_list(user, self.empty_id)
            self.assertEqual(response.status_code, 200)
            self.assertEqual(response.get_json()["shares"], [])

    def test_missing_document(self):
        response = self.get_list(document_id=99999)
        self.assertEqual(response.status_code, 404)
        self.assertEqual(set(response.get_json()), {"message"})

    def test_missing_and_invalid_tokens(self):
        self.assertEqual(self.get_list(user=None).status_code, 401)
        self.tokens["owner"] = secrets.token_urlsafe(32)
        self.assertEqual(self.get_list().status_code, 401)

    def test_expired_and_inactive_sessions(self):
        for state in ("expired", "inactive"):
            with self.subTest(state=state):
                with self.app.app_context():
                    session = db.session.execute(db.select(Session).where(
                        Session.user_id == self.user_ids["owner"],
                    )).scalar_one()
                    session.is_active = state != "inactive"
                    session.expires_at = datetime.now(timezone.utc) + timedelta(
                        hours=-1 if state == "expired" else 1,
                    )
                    db.session.commit()
                self.assertEqual(self.get_list().status_code, 401)

    def test_role_change_applies_to_existing_session(self):
        self.assertEqual(self.get_list("admin").status_code, 200)
        with self.app.app_context():
            db.session.get(User, self.user_ids["admin"]).role = "user"
            db.session.commit()
        self.assertEqual(self.get_list("admin").status_code, 403)

    def test_management_is_independent_of_visibility(self):
        for visibility in ("private", "team", "shared"):
            with self.subTest(visibility=visibility):
                with self.app.app_context():
                    document = db.session.get(Document, self.document_id)
                    document.visibility = visibility
                    db.session.commit()
                    for name, user_id in self.user_ids.items():
                        self.assertEqual(
                            can_manage_shares(db.session.get(User, user_id), document),
                            name in ("owner", "admin"),
                        )
                self.assertEqual(self.get_list().status_code, 200)
                self.assertEqual(self.get_list("editor").status_code, 403)


    def post_share(self, user="owner", payload=None, document_id=None):
        return self.client.post(
            f"/api/documents/{document_id or self.document_id}/shares",
            headers={"Authorization": f"Bearer {self.tokens[user]}"},
            json=payload if payload is not None else {
                "shared_with_id": self.user_ids["unrelated"], "permission": "download",
                "shared_by_id": self.user_ids["admin"],
            },
        )

    def test_create_persists_actor_permission_and_log(self):
        import json
        from app.models import ActivityLog
        response = self.post_share()
        self.assertEqual(response.status_code, 201)
        self.assertEqual(len(self.get_list().get_json()["shares"]), 3)
        with self.app.app_context():
            share = db.session.get(DocumentShare, response.get_json()["share"]["id"])
            self.assertEqual(share.shared_by_id, self.user_ids["owner"])
            self.assertEqual(share.permission, "download")
            log = db.session.execute(db.select(ActivityLog)).scalar_one()
            self.assertEqual(log.user_id, self.user_ids["owner"])
            self.assertEqual(log.action_type, "DOCUMENT_SHARE")
            self.assertEqual(json.loads(log.detail)["after_permission"], "download")
            self.assertEqual(db.session.get(Document, self.document_id).visibility, "shared")
        self.assertEqual(self.post_share().status_code, 409)
        with self.app.app_context():
            self.assertEqual(db.session.query(ActivityLog).count(), 1)

    def test_admin_can_create_and_non_managers_cannot(self):
        for name in ("viewer", "editor", "unrelated", "no_dept"):
            self.assertEqual(self.post_share(name).status_code, 403)
        self.assertEqual(self.post_share("admin").status_code, 201)
        self.assertEqual(self.post_share(document_id=99999).status_code, 404)
        self.assertEqual(self.client.post(f"/api/documents/{self.document_id}/shares", json={}).status_code, 401)

    def test_creation_rejects_bad_input(self):
        for payload in ([], {}, {"shared_with_id": True, "permission": "view"},
                        {"shared_with_id": "4", "permission": "view"},
                        {"shared_with_id": 99999, "permission": "view"},
                        {"shared_with_id": self.user_ids["owner"], "permission": "view"},
                        {"shared_with_id": self.user_ids["unrelated"], "permission": []},
                        {"shared_with_id": self.user_ids["unrelated"], "permission": "admin"}):
            with self.subTest(payload=payload):
                self.assertEqual(self.post_share(payload=payload).status_code, 400)
        self.assertEqual(len(self.get_list().get_json()["shares"]), 2)

    def test_log_failure_rolls_back_share(self):
        from unittest.mock import patch
        from sqlalchemy.exc import SQLAlchemyError
        from app.models import ActivityLog
        original_add = db.session.add
        def add(instance, *args, **kwargs):
            if isinstance(instance, ActivityLog):
                raise SQLAlchemyError("simulated log failure")
            return original_add(instance, *args, **kwargs)
        with patch.object(db.session, "add", side_effect=add):
            with self.assertRaises(SQLAlchemyError):
                self.post_share()
        self.assertEqual(len(self.get_list().get_json()["shares"]), 2)

    def test_user_search_auth_minimal_fields_and_literal_wildcards(self):
        self.assertEqual(self.client.get("/api/users?q=owner").status_code, 401)
        headers = {"Authorization": f"Bearer {self.tokens['owner']}"}
        result = self.client.get("/api/users?q=edit", headers=headers)
        self.assertEqual(result.get_json(), {"users": [{"id": self.user_ids["editor"], "username": "editor"}]})
        for query in ("", "%", "' OR 1=1 --"):
            self.assertEqual(self.client.get("/api/users", query_string={"q": query}, headers=headers).get_json(), {"users": []})
        self.assertEqual(self.client.get("/api/users", query_string={"q": "x" * 51}, headers=headers).status_code, 400)


    def mutate_share(self, method, user="owner", document_id=None, share_id=None, payload=None):
        if share_id is None:
            share_id = self.get_list().get_json()["shares"][0]["id"]
        return self.client.open(
            f"/api/documents/{document_id or self.document_id}/shares/{share_id}",
            method=method,
            headers={"Authorization": f"Bearer {self.tokens[user]}"} if user else {},
            json=payload if payload is not None else {"permission": "download"},
        )

    def test_update_delete_persist_and_record_before_after(self):
        import json
        from app.models import ActivityLog
        share_id = self.get_list().get_json()["shares"][0]["id"]
        response = self.mutate_share("PATCH", share_id=share_id)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.get_json()["share"]["permission"], "download")
        self.assertEqual(self.get_list().get_json()["shares"][0]["permission"], "download")
        self.assertEqual(self.mutate_share("PATCH", share_id=share_id).status_code, 200)
        self.assertEqual(self.mutate_share("DELETE", user="admin", share_id=share_id).get_json(), {"deleted_share_id": share_id})
        self.assertEqual(len(self.get_list().get_json()["shares"]), 1)
        self.assertEqual(self.mutate_share("DELETE", share_id=share_id).status_code, 404)
        with self.app.app_context():
            logs = db.session.execute(db.select(ActivityLog).order_by(ActivityLog.id)).scalars().all()
            self.assertEqual(len(logs), 2)
            self.assertEqual([log.user_id for log in logs], [self.user_ids["owner"], self.user_ids["admin"]])
            details = [json.loads(log.detail) for log in logs]
            self.assertEqual([(d["operation"], d["before_permission"], d["after_permission"]) for d in details],
                             [("update", "view", "download"), ("delete", "download", None)])
            self.assertTrue(all(log.action_type == "DOCUMENT_SHARE" for log in logs))
            self.assertTrue(all(d["share_id"] == share_id and d["document_id"] == self.document_id for d in details))
            self.assertEqual(db.session.get(Document, self.document_id).visibility, "shared")

    def test_mutations_reject_non_managers_wrong_document_and_missing_rows(self):
        for method in ("PATCH", "DELETE"):
            for user in ("viewer", "editor", "unrelated", "no_dept"):
                self.assertEqual(self.mutate_share(method, user=user).status_code, 403)
            self.assertEqual(self.mutate_share(method, user=None).status_code, 401)
            self.assertEqual(self.mutate_share(method, document_id=self.empty_id).status_code, 404)
            self.assertEqual(self.mutate_share(method, document_id=99999).status_code, 404)
            self.assertEqual(self.mutate_share(method, share_id=99999).status_code, 404)
        self.assertEqual(len(self.get_list().get_json()["shares"]), 2)

    def test_patch_validation_and_admin_edit(self):
        from app.models import ActivityLog
        for payload in ([], {}, {"permission": []}, {"permission": "owner"},
                        {"permission": "edit", "shared_with_id": self.user_ids["unrelated"]}):
            self.assertEqual(self.mutate_share("PATCH", payload=payload).status_code, 400)
        with self.app.app_context():
            self.assertEqual(db.session.query(ActivityLog).count(), 0)
        response = self.mutate_share("PATCH", user="admin", payload={"permission": "edit"})
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.get_json()["share"]["permission"], "edit")

    def test_mutation_commit_failure_rolls_back_share_and_log(self):
        from unittest.mock import patch
        from sqlalchemy.exc import SQLAlchemyError
        from app.models import ActivityLog
        for method in ("PATCH", "DELETE"):
            with patch.object(db.session, "commit", side_effect=SQLAlchemyError("commit failed")):
                with self.assertRaises(SQLAlchemyError):
                    self.mutate_share(method)
            shares = self.get_list().get_json()["shares"]
            self.assertEqual(len(shares), 2)
            self.assertEqual(shares[0]["permission"], "view")
            with self.app.app_context():
                self.assertEqual(db.session.query(ActivityLog).count(), 0)

    def test_delete_preserves_team_metadata_and_allows_reshare(self):
        with self.app.app_context():
            document = db.session.get(Document, self.document_id)
            document.visibility = "team"
            department_id = document.department_id
            db.session.commit()
        share = self.get_list().get_json()["shares"][0]
        self.assertEqual(self.mutate_share("DELETE", share_id=share["id"]).status_code, 200)
        with self.app.app_context():
            document = db.session.get(Document, self.document_id)
            self.assertEqual(document.visibility, "team")
            self.assertEqual(document.department_id, department_id)
        self.assertEqual(self.post_share(payload={"shared_with_id": share["shared_with"]["id"], "permission": "view"}).status_code, 201)


    def received(self, user="viewer", **query):
        return self.client.get("/api/documents/shared", query_string=query,
            headers={"Authorization": f"Bearer {self.tokens[user]}"})

    def test_received_filters_pagination_and_session_scope(self):
        self.assertEqual(self.client.get("/api/documents/shared").status_code, 401)
        data = self.received(user_id=self.user_ids["editor"]).get_json()
        self.assertEqual(data["pagination"]["total"], 1)
        self.assertEqual(set(data["items"][0]), {"share_id", "document", "shared_by", "permission", "shared_at"})
        self.assertEqual(data["items"][0]["permission"], "view")
        self.assertEqual(self.received("unrelated").content_type, "application/json")
        self.assertEqual(self.received("unrelated").get_json()["pagination"]["total"], 0)
        for params in ({"q": "missing"}, {"sharer": "missing"}, {"permission": "edit"}, {"q": "%"}, {"q": "' OR 1=1 --"}):
            self.assertEqual(self.received(**params).get_json()["pagination"]["total"], 0)
        self.assertEqual(self.received(q="shared", sharer="owner", permission="view").get_json()["pagination"]["total"], 1)
        for params in ({"page": "x"}, {"page": 0}, {"per_page": 101}, {"permission": "admin"}):
            self.assertEqual(self.received(**params).status_code, 400)
        self.post_share(document_id=self.empty_id, payload={"shared_with_id": self.user_ids["viewer"], "permission": "download"})
        first = self.received(per_page=1).get_json()
        second = self.received(per_page=1, page=2).get_json()
        self.assertEqual(first["pagination"], {"page": 1, "per_page": 1, "total": 2, "pages": 2})
        self.assertNotEqual(first["items"][0]["share_id"], second["items"][0]["share_id"])
        self.assertEqual(self.received(page=99).get_json()["items"], [])

    def test_share_create_update_delete_reflected_in_received_list(self):
        self.assertEqual(self.received("unrelated").get_json()["items"], [])
        share_id = self.post_share().get_json()["share"]["id"]
        self.assertEqual(self.received("unrelated").get_json()["items"][0]["permission"], "download")
        self.mutate_share("PATCH", share_id=share_id, payload={"permission": "view"})
        self.assertEqual(self.received("unrelated").get_json()["items"][0]["permission"], "view")
        self.mutate_share("DELETE", share_id=share_id)
        self.assertEqual(self.received("unrelated").get_json()["pagination"]["total"], 0)

    def test_common_view_condition_matches_single_document_checks(self):
        from app.services.document_permissions import document_view_condition, can_view_document
        with self.app.app_context():
            document = db.session.get(Document, self.document_id)
            other = Department(name="Other")
            db.session.add(other)
            db.session.flush()
            db.session.get(User, self.user_ids["editor"]).department_id = other.id
            for visibility in ("private", "team", "shared"):
                document.visibility = visibility
                db.session.commit()
                for name, user_id in self.user_ids.items():
                    user = db.session.get(User, user_id)
                    expected = name in ("owner", "viewer", "editor") or (visibility == "team" and name in ("admin", "unrelated"))
                    ids = db.session.execute(db.select(Document.id).where(document_view_condition(user))).scalars().all()
                    self.assertEqual(self.document_id in ids, expected)
                    self.assertEqual(can_view_document(user, document), expected)
            document.visibility = "team"
            document.department_id = None
            db.session.commit()
            self.assertFalse(can_view_document(db.session.get(User, self.user_ids["no_dept"]), document))
        # private/team/shared 모두 개별 공유 수신자 목록에 포함한다.
        for visibility in ("private", "team", "shared"):
            with self.app.app_context():
                db.session.get(Document, self.document_id).visibility = visibility
                db.session.commit()
            self.assertEqual(self.received().get_json()["pagination"]["total"], 1)

    def test_revocation_keeps_only_remaining_team_view(self):
        from app.services.document_permissions import can_view_document
        share_id = self.get_list().get_json()["shares"][0]["id"]
        with self.app.app_context():
            db.session.get(Document, self.document_id).visibility = "team"
            db.session.commit()
        self.mutate_share("DELETE", share_id=share_id)
        self.assertEqual(self.received().get_json()["items"], [])
        with self.app.app_context():
            user = db.session.get(User, self.user_ids["viewer"])
            document = db.session.get(Document, self.document_id)
            self.assertTrue(can_view_document(user, document))
            document.visibility = "private"
            db.session.commit()
            self.assertFalse(can_view_document(user, document))


    def team_list(self, user="viewer", **query):
        return self.client.get("/api/documents/team", query_string=query,
            headers={"Authorization": f"Bearer {self.tokens[user]}"})

    def test_team_scope_search_pagination_and_department_spoof(self):
        with self.app.app_context():
            original = db.session.get(Document, self.document_id)
            original.visibility = "team"
            other = Department(name="Outside")
            db.session.add(other)
            db.session.flush()
            extra = Document(title="Second team", owner_id=self.user_ids["owner"],
                department_id=original.department_id, visibility="team", file_path="unused", original_filename="test.txt")
            outside = Document(title="Outside secret", owner_id=self.user_ids["owner"],
                department_id=other.id, visibility="team", file_path="unused", original_filename="test.txt")
            null_team = Document(title="No department", owner_id=self.user_ids["no_dept"],
                visibility="team", file_path="unused", original_filename="test.txt")
            db.session.add_all([extra, outside, null_team])
            db.session.flush()
            db.session.add(DocumentShare(document_id=outside.id, shared_by_id=self.user_ids["owner"],
                shared_with_id=self.user_ids["viewer"], permission="edit"))
            outside_id = other.id
            db.session.commit()
        for user in ("owner", "viewer", "admin"):
            data = self.team_list(user, department_id=outside_id, department=outside_id).get_json()
            self.assertEqual(data["pagination"]["total"], 2)
            self.assertEqual(data["department"]["name"], "Test team")
            self.assertEqual({item["title"] for item in data["items"]}, {"Second team", "Test shared document"})
            self.assertEqual(set(data["items"][0]), {"id", "title", "owner", "updated_at"})
        self.assertEqual(self.team_list(q="Outside").get_json()["pagination"]["total"], 0)
        self.assertEqual(self.team_list(q="Second").get_json()["pagination"]["total"], 1)
        self.assertEqual(self.team_list(q="%").get_json()["pagination"]["total"], 0)
        first = self.team_list(per_page=1).get_json()
        second = self.team_list(per_page=1, page=2).get_json()
        self.assertEqual(first["pagination"]["pages"], 2)
        self.assertNotEqual(first["items"][0]["id"], second["items"][0]["id"])
        self.assertEqual(self.team_list(page=99).get_json()["items"], [])
        self.assertEqual(self.team_list("no_dept").get_json(), {
            "department": None, "items": [],
            "pagination": {"page": 1, "per_page": 10, "total": 0, "pages": 0},
        })

    def test_team_auth_empty_and_invalid_filters(self):
        self.assertEqual(self.client.get("/api/documents/team").status_code, 401)
        self.assertEqual(self.team_list().get_json()["items"], [])
        for query in ({"page": "bad"}, {"page": 0}, {"per_page": 0}, {"per_page": 101}, {"q": "x" * 256}):
            self.assertEqual(self.team_list(**query).status_code, 400)
        with self.app.app_context():
            db.session.get(Document, self.document_id).visibility = "team"
            db.session.commit()
        self.assertEqual(self.team_list().get_json()["pagination"]["total"], 1)
        with self.app.app_context():
            db.session.get(User, self.user_ids["viewer"]).department_id = None
            db.session.commit()
        self.assertEqual(self.team_list().get_json()["pagination"]["total"], 0)


    def search_list(self, user="viewer", **query):
        return self.client.get("/api/search", query_string=query,
            headers={"Authorization": f"Bearer {self.tokens[user]}"})

    def test_search_scope_counts_filters_and_duplicate_prevention(self):
        with self.app.app_context():
            hidden_dept = Department(name="Hidden department")
            db.session.add(hidden_dept)
            db.session.flush()
            hidden_owner = User(username="hidden_owner", password_hash="unused", role="user", department_id=hidden_dept.id)
            db.session.add(hidden_owner)
            db.session.flush()
            hidden = Document(title="Hidden needle", owner_id=hidden_owner.id, department_id=hidden_dept.id,
                visibility="private", file_path="hidden-path", original_filename="hidden.txt")
            db.session.add(hidden)
            db.session.get(Document, self.document_id).visibility = "team"
            dept_id, owner_id = hidden_dept.id, hidden_owner.id
            db.session.commit()
        data = self.search_list(user_id=owner_id).get_json()
        self.assertEqual(data["pagination"]["total"], 1)
        self.assertEqual(len(data["items"]), 1)  # 팀 접근과 여러 공유가 있어도 문서는 한 건
        self.assertEqual(set(data["items"][0]), {"id", "title", "owner", "department", "updated_at"})
        self.assertNotIn(dept_id, [item["id"] for item in data["filters"]["departments"]])
        self.assertNotIn(owner_id, [item["id"] for item in data["filters"]["owners"]])
        for query in ({"q": "Hidden"}, {"department_id": dept_id}, {"owner_id": owner_id}, {"q": "%"}, {"q": "' OR 1=1 --"}):
            result = self.search_list(**query).get_json()
            self.assertEqual(result["items"], [])
            self.assertEqual(result["pagination"]["total"], 0)
        self.assertEqual(self.search_list("no_dept").get_json()["filters"], {"departments": [], "owners": []})
        self.assertEqual(self.search_list("admin", q="Hidden").get_json()["pagination"]["total"], 0)

    def test_search_owner_team_receiver_no_department_and_revoke(self):
        self.assertEqual(self.search_list("owner").get_json()["pagination"]["total"], 2)
        for visibility in ("private", "shared", "team"):
            with self.app.app_context():
                db.session.get(Document, self.document_id).visibility = visibility
                db.session.commit()
            self.assertEqual(self.search_list("viewer").get_json()["pagination"]["total"], 1)
            self.assertEqual(self.search_list("unrelated").get_json()["pagination"]["total"], int(visibility == "team"))
        with self.app.app_context():
            db.session.get(Document, self.document_id).visibility = "private"
            db.session.commit()
        share_id = self.post_share().get_json()["share"]["id"]
        self.assertEqual(self.search_list("unrelated").get_json()["pagination"]["total"], 1)
        self.mutate_share("DELETE", share_id=share_id)
        self.assertEqual(self.search_list("unrelated").get_json()["pagination"]["total"], 0)
        self.assertEqual(self.search_list("unrelated").get_json()["filters"]["owners"], [])

    def test_search_validation_sort_and_pagination(self):
        self.assertEqual(self.client.get("/api/search").status_code, 401)
        for query in ({"sort": "sql"}, {"page": 0}, {"per_page": 101}, {"owner_id": "abc"}, {"department_id": -1}, {"q": "x" * 256}):
            self.assertEqual(self.search_list(**query).status_code, 400)
        first = self.search_list("owner", sort="title_asc", per_page=1).get_json()
        second = self.search_list("owner", sort="title_asc", per_page=1, page=2).get_json()
        self.assertEqual(first["items"][0]["title"], "Empty")
        self.assertEqual(first["pagination"]["pages"], 2)
        self.assertNotEqual(first["items"][0]["id"], second["items"][0]["id"])
        self.assertEqual(self.search_list("owner", page=99).get_json()["items"], [])
        self.assertEqual(self.search_list("owner", owner_id=self.user_ids["owner"], q="Empty").get_json()["pagination"]["total"], 1)


    def admin_get(self, resource, user="admin", **query):
        return self.client.get(f"/api/admin/{resource}", query_string=query,
            headers={"Authorization": f"Bearer {self.tokens[user]}"})

    def test_admin_lists_reject_users_and_revoked_role(self):
        for resource in ("users", "documents", "activity-logs"):
            self.assertEqual(self.client.get(f"/api/admin/{resource}").status_code, 401)
            for user in ("owner", "viewer", "editor", "unrelated", "no_dept"):
                self.assertEqual(self.admin_get(resource, user, role="admin").status_code, 403)
            self.assertEqual(self.admin_get(resource).status_code, 200)
        with self.app.app_context():
            db.session.get(User, self.user_ids["admin"]).role = "user"
            db.session.commit()
        for resource in ("users", "documents", "activity-logs"):
            self.assertEqual(self.admin_get(resource).status_code, 403)

    def test_admin_contract_pagination_search_and_safe_logs(self):
        import json
        from app.models import ActivityLog
        users = self.admin_get("users", per_page=1).get_json()
        self.assertEqual(users["pagination"]["total"], 6)
        self.assertEqual(len(users["items"]), 1)
        self.assertEqual(set(users["items"][0]), {"id", "username", "role", "department", "created_at"})
        self.assertNotEqual(users["items"][0]["id"], self.admin_get("users", per_page=1, page=2).get_json()["items"][0]["id"])
        self.assertEqual(self.admin_get("users", q="owner").get_json()["pagination"]["total"], 1)
        documents = self.admin_get("documents", q="Empty").get_json()
        self.assertEqual(documents["items"][0]["visibility"], "private")
        self.assertEqual(set(documents["items"][0]), {"id", "title", "owner", "department", "visibility", "updated_at"})
        self.post_share()
        with self.app.app_context():
            db.session.add(ActivityLog(action_type="ADMIN_ACTION", detail=json.dumps({
                "session_token": "secret", "file_path": "secret", "password_hash": "secret",
                "document_id": 12, "operation": "create", "before_permission": "secret",
            })))
            db.session.add(ActivityLog(action_type="ADMIN_ACTION", detail="secret raw text"))
            db.session.commit()
        logs = self.admin_get("activity-logs").get_json()
        self.assertNotIn("secret", json.dumps(logs))
        self.assertEqual(logs["pagination"]["total"], 3)
        self.assertEqual(self.admin_get("activity-logs", q="DOCUMENT_SHARE").get_json()["pagination"]["total"], 1)
        for resource in ("users", "documents", "activity-logs"):
            self.assertEqual(self.admin_get(resource, q="%").get_json()["items"], [])
            for query in ({"page": 0}, {"page": "bad"}, {"per_page": 101}, {"q": "x" * 256}):
                self.assertEqual(self.admin_get(resource, **query).status_code, 400)


if __name__ == "__main__":
    unittest.main()
