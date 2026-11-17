#!/usr/bin/env python3
"""Real HTTP tests of the packaged, unmodified upstream PHP store.

All identities and sessions are created by a CLI-only fixture in temporary
directories. There is deliberately no test-login endpoint or test auth mode.
"""
import argparse
import base64
import fcntl
from concurrent.futures import ThreadPoolExecutor, TimeoutError as FutureTimeout
import hashlib
import http.client
import importlib.util
import io
import json
import os
from pathlib import Path
import socket
import subprocess
import tempfile
import time
import unittest
from urllib.parse import urlencode
import zipfile

ROOT = Path(__file__).resolve().parents[1]
parser = argparse.ArgumentParser(description=__doc__)
parser.add_argument("--php", required=True)
parser.add_argument("--layerling", type=Path, required=True)
OPTIONS, remaining = parser.parse_known_args()
spec = importlib.util.spec_from_file_location("package", ROOT / "scripts/package-prototype.py")
packager = importlib.util.module_from_spec(spec)
spec.loader.exec_module(packager)

A = "a" * 32
B = "b" * 32
PNG = base64.b64decode("iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mP8/x8AAwMCAO+a7x8AAAAASUVORK5CYII=")


def project(marker):
    stream = io.BytesIO()
    with zipfile.ZipFile(stream, "w", compression=zipfile.ZIP_STORED) as archive:
        # Stable ZIP metadata: byte comparisons must not depend on the wall clock.
        archive.writestr(zipfile.ZipInfo("project.json", date_time=(2026, 1, 1, 0, 0, 0)),
                         json.dumps({"marker": marker}))
    return stream.getvalue()


class StorageHTTPTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.tmp = tempfile.TemporaryDirectory(prefix="sso-layerling-http-")
        cls.addClassCleanup(cls.tmp.cleanup)
        with socket.socket() as sock:
            sock.bind(("127.0.0.1", 0))
            cls.port = sock.getsockname()[1]
        cls.origin = f"http://127.0.0.1:{cls.port}"
        cls.runtime = packager.package(OPTIONS.layerling, Path(cls.tmp.name) / "runtime", cls.origin)
        cls.private = cls.runtime / "private"
        config_path = cls.private / "config.json"
        config = json.loads(config_path.read_text())
        config["groupIds"] = {"makerspace": "test-makerspace-id", "admins": "test-admins-id"}
        config_path.write_text(json.dumps(config))
        cls.log = open(Path(cls.tmp.name) / "server.log", "w+")
        cls.addClassCleanup(cls.log.close)
        env = dict(os.environ)
        env.pop("PHP_CLI_SERVER_WORKERS", None)
        # Poison inherited upstream configuration to prove the gateway replaces it.
        env.update(LAYERLING_USER_HEADER="X-Forwarded-Email", LAYERLING_SHARED_PROJECTS_DIR=cls.tmp.name,
                   LAYERLING_ALLOWED_ORIGINS="https://foreign.invalid")
        cls.server = subprocess.Popen([
            OPTIONS.php, "-d", "display_errors=0", "-d", "log_errors=1",
            "-S", f"127.0.0.1:{cls.port}", "-t", str(cls.runtime / "public"),
        ], stdout=cls.log, stderr=cls.log, env=env)
        cls.addClassCleanup(cls.stop_server)
        for _ in range(100):
            if cls.server.poll() is not None:
                raise RuntimeError("Local PHP server exited; no test credentials logged")
            try:
                with socket.create_connection(("127.0.0.1", cls.port), timeout=0.1):
                    return
            except OSError:
                time.sleep(0.03)
        raise RuntimeError("Local PHP server did not start")

    @classmethod
    def stop_server(cls):
        cls.server.terminate()
        try:
            cls.server.wait(timeout=5)
        except subprocess.TimeoutExpired:
            cls.server.kill()
            cls.server.wait()

    def setUp(self):
        # Each test starts with two independent sessions and personal roots.
        import shutil
        for entry in (self.private / "projects").iterdir():
            if entry.is_symlink() or entry.is_file():
                entry.unlink()
            else:
                shutil.rmtree(entry)
        (self.private / "principals.json").write_text("{}\n")
        (self.private / "audit.jsonl").write_text("")
        self.a = self.issue(A)
        self.b = self.issue(B)

    def principal(self, user, **changes):
        # Simulates the future trusted issuer/refresh writer, never an HTTP input.
        # Writers take this exclusive lock; requests keep a shared snapshot lock.
        with open(self.private / "authorization.lock", "rb") as lock:
            fcntl.flock(lock, fcntl.LOCK_EX)
            path = self.private / "principals.json"
            records = json.loads(path.read_text())
            record = dict(enabled=True, checkedAt=int(time.time()), roles=[], groups=[])
            record.update(records.get(user, {}))
            record.update(changes)
            records[user] = record
            pending = self.private / "principals.pending.json"
            pending.write_text(json.dumps(records))
            pending.chmod(0o600)
            pending.replace(path)

    def issue(self, user, **overrides):
        now = int(time.time())
        if isinstance(user, str) and len(user) == 32 and all(c in "abcdef0123456789" for c in user):
            records = json.loads((self.private / "principals.json").read_text())
            if user not in records:
                self.principal(user)
        data = dict(userId=user, authorized=True, issuedAt=now, lastSeen=now)
        data.update(overrides)
        # This code never enters the package or an HTTP response. No live SSO.
        fixture = r'''
        ini_set('session.use_strict_mode', '0');
        session_save_path($argv[1]);
        session_name('SSO_LAYERLING_SESSION');
        session_id(bin2hex(random_bytes(32)));
        session_start();
        $_SESSION = json_decode($argv[2], true, 16, JSON_THROW_ON_ERROR);
        $_SESSION['csrf'] = bin2hex(random_bytes(32));
        echo json_encode(['id'=>session_id(), 'csrf'=>$_SESSION['csrf']]);
        session_write_close();
        '''
        result = subprocess.run([OPTIONS.php, "-r", fixture, str(self.private / "sessions"), json.dumps(data)],
                                check=True, capture_output=True, text=True)
        return json.loads(result.stdout)

    def request(self, method="GET", query=None, body=None, client=None, headers=None, path="/store.php", protect=True):
        actual = {}
        if client:
            actual["Cookie"] = "SSO_LAYERLING_SESSION=" + client["id"]
        if protect and method not in ["GET", "HEAD", "OPTIONS"]:
            actual["Origin"] = self.origin
            if client:
                actual["X-SSO-CSRF"] = client["csrf"]
        actual.update(headers or {})
        target = path + ("?" + urlencode(query) if query else "")
        connection = http.client.HTTPConnection("127.0.0.1", self.port, timeout=5)
        try:
            connection.request(method, target, body=body, headers=actual)
            response = connection.getresponse()
            return response.status, dict((k.lower(), v) for k, v in response.getheaders()), response.read()
        finally:
            connection.close()

    def json_response(self, response, status=200):
        self.assertEqual(response[0], status, response[2][:300])
        self.assertEqual(response[1].get("cache-control"), "private, no-store")
        return json.loads(response[2])

    def upload(self, client, name="same.lyl", marker="A", folder="", thumbnail=False, headers=None, owner=None):
        data = project(marker)
        actual = dict(headers or {})
        if thumbnail:
            boundary = "sso-test-boundary-" + hashlib.sha256(data).hexdigest()
            body = b""
            for field, filename, content_type, content in [
                ("project", name, "application/vnd.layerling.project+zip", data),
                ("thumbnail", name + ".png", "image/png", PNG),
            ]:
                body += (f'--{boundary}\r\nContent-Disposition: form-data; name="{field}"; filename="{filename}"\r\n'
                         f'Content-Type: {content_type}\r\n\r\n').encode() + content + b"\r\n"
            body += f"--{boundary}--\r\n".encode()
            actual["Content-Type"] = f"multipart/form-data; boundary={boundary}"
        else:
            body = data
            actual["Content-Type"] = "application/vnd.layerling.project+zip"
        query = {"fileName": name, "path": folder}
        if owner is not None:
            query["_sso_owner"] = owner
        return self.request("POST", query, body, client, actual)

    def test_01_package_boundary_and_upstream_integrity(self):
        lock = json.loads((ROOT / "upstream.lock.json").read_text())
        original = (self.private / "upstream/store.php").read_bytes()
        self.assertEqual(hashlib.sha256(original).hexdigest(), lock["sha256"])
        self.assertEqual({p.name for p in (self.runtime / "public").iterdir()}, {"store.php", "session.php"})
        for path in ["/private/upstream/store.php", "/../private/config.json", "/upstream/store.php",
                     "/tests/login.php", "/login.php", "/.git/config", "/src/Gateway.php"]:
            with self.subTest(path=path):
                self.assertEqual(self.request(path=path)[0], 404)
        with self.assertRaises(ValueError):
            packager.package(OPTIONS.layerling, self.runtime, self.origin)
        with self.assertRaises(ValueError):
            packager.package(OPTIONS.layerling, Path(self.tmp.name) / "rejected", "https://cad.example.invalid")
        # Altered upstream bytes are refused before execution.
        file = self.private / "upstream/store.php"
        try:
            file.write_bytes(original + b"\n// synthetic integrity test\n")
            self.json_response(self.request(client=self.a), 503)
        finally:
            file.write_bytes(original)

    def test_02_unauthenticated_all_operations_denied(self):
        cases = [("GET", {}), ("GET", {"fileName": "same.lyl"}),
                 ("GET", {"fileName": "same.lyl", "thumbnail": "1"}), ("GET", {"all": "1"}),
                 ("GET", {"search": "secret"}), ("GET", {"settings": "default"}),
                 ("POST", {"fileName": "same.lyl"}), ("POST", {"folder": "new"}),
                 ("POST", {"settings": "default"}), ("DELETE", {"fileName": "same.lyl"})]
        for method, query in cases:
            with self.subTest(method=method, query=query):
                self.json_response(self.request(method, query, body=b"test" if method == "POST" else None), 401)

    def test_03_invalid_expired_and_unauthorized_sessions(self):
        now = int(time.time())
        cases = [dict(userId=None), dict(userId="../" + B), dict(authorized=False),
                 dict(issuedAt=now - 3601, lastSeen=now),
                 dict(issuedAt=now - 1000, lastSeen=now - 901), dict(issuedAt=now + 100)]
        for fields in cases:
            with self.subTest(fields=fields):
                user = fields.get("userId", A)
                overrides = {key: value for key, value in fields.items() if key != "userId"}
                cookie = self.issue(user, **overrides)
                self.json_response(self.request(client=cookie), 401)
                record = self.private / "sessions" / ("sess_" + cookie["id"])
                self.assertEqual(record.read_bytes() if record.exists() else b"", b"")
                self.json_response(self.request(client=cookie), 401)
        self.json_response(self.request(client={"id": "f" * 64, "csrf": "f" * 64}), 401)
        self.assertFalse((self.private / "sessions" / ("sess_" + "f" * 64)).exists())
        self.json_response(self.request(query={"SSO_LAYERLING_SESSION": self.a["id"]}), 401)

    def test_04_personal_project_lists_downloads_and_header_spoofing(self):
        self.json_response(self.upload(self.a, marker="A-private"), 201)
        self.json_response(self.upload(self.b, marker="B-private-and-different"), 201)
        for client, marker in [(self.a, "A-private"), (self.b, "B-private-and-different")]:
            listing = self.json_response(self.request(client=client))
            self.assertEqual([p["fileName"] for p in listing["projects"]], ["same.lyl"])
            download = self.request(query={"fileName": "same.lyl"}, client=client)
            self.assertEqual(download[2], project(marker))
        spoof = {"X-Forwarded-Email": B, "Remote-User": B, "X-Forwarded-User": B,
                 "LAYERLING-USER-HEADER": "X-Forwarded-Email", "X-Sso-User": B}
        self.assertEqual(self.request(query={"fileName": "same.lyl"}, client=self.a, headers=spoof)[2], project("A-private"))
        self.json_response(self.upload(self.b, "only-b.lyl", "B-secret"), 201)
        self.json_response(self.request(query={"fileName": "only-b.lyl"}, client=self.a), 404)
        self.assertTrue((self.private / "projects" / A / "same.lyl").is_file())
        self.assertTrue((self.private / "projects" / B / "same.lyl").is_file())

    def test_05_csrf_and_origin_checks(self):
        for method, query in [("POST", {"folder": "bad"}), ("DELETE", {"fileName": "same.lyl"})]:
            for headers in [{}, {"Origin": self.origin}, {"X-SSO-CSRF": self.a["csrf"]},
                            {"Origin": "null", "X-SSO-CSRF": self.a["csrf"]},
                            {"Origin": self.origin, "X-SSO-CSRF": self.b["csrf"]},
                            {"Origin": "https://foreign.invalid", "X-SSO-CSRF": self.a["csrf"],
                             "X-Forwarded-Host": "foreign.invalid", "X-Forwarded-Proto": "https"}]:
                with self.subTest(method=method, headers=list(headers)):
                    self.json_response(self.request(method, query, client=self.a, headers=headers, protect=False), 403)
        self.json_response(self.request(client=self.a, headers={"Sec-Fetch-Site": "cross-site"}), 403)
        self.json_response(self.request(client=self.a, headers={"Origin": "https://foreign.invalid"}), 403)
        self.json_response(self.request(client=self.a, headers={"Host": "attacker.invalid"}), 400)
        # Forged proxy headers do not affect a legitimate configured origin.
        self.json_response(self.request("POST", {"folder": "good"}, client=self.a,
                                       headers={"X-Forwarded-Host": "attacker.invalid", "X-Forwarded-Proto": "https"}), 201)

    def test_06_thumbnail_never_publicly_cached(self):
        record = self.json_response(self.upload(self.a, thumbnail=True), 201)["project"]
        query = {"fileName": "same.lyl", "thumbnail": "1", "v": record["revision"]}
        image = self.request(query=query, client=self.a)
        self.assertEqual(image[0], 200)
        self.assertEqual(image[2], PNG)
        self.assertEqual(image[1]["cache-control"], "private, no-store")
        self.assertEqual(image[1]["cross-origin-resource-policy"], "same-origin")
        self.assertEqual(image[1]["x-content-type-options"], "nosniff")
        self.json_response(self.request(query=query, client=self.b), 404)
        self.json_response(self.request(query=query), 401)

    def test_07_folders_search_all_and_settings_are_personal(self):
        self.json_response(self.request("POST", {"folder": "A-folder"}, client=self.a), 201)
        self.json_response(self.upload(self.a, "alpha.lyl", "alpha", folder="A-folder"), 201)
        self.json_response(self.upload(self.b, "beta.lyl", "beta"), 201)
        search = self.json_response(self.request(query={"search": "alpha"}, client=self.b))
        self.assertEqual(search["projects"], [])
        all_a = self.json_response(self.request(query={"all": "1"}, client=self.a))
        self.assertIn(b"alpha.lyl", json.dumps(all_a).encode())
        self.assertNotIn(b"beta.lyl", json.dumps(all_a).encode())
        self.json_response(self.request("POST", {"settings": "default"}, b'{"owner":"A"}', self.a), 200)
        self.assertEqual(self.json_response(self.request(query={"settings": "default"}, client=self.a))["settings"], {"owner": "A"})
        self.assertIsNone(self.json_response(self.request(query={"settings": "default"}, client=self.b))["settings"])
        self.json_response(self.request(query={"path": "A-folder"}, client=self.b), 404)

    def test_08_copy_rename_move_and_delete_do_not_reach_other_users(self):
        record = self.json_response(self.upload(self.a, "source.lyl", "A-source"), 201)["project"]
        rev = {"If-Match": '"' + record["revision"] + '"'}
        self.json_response(self.request("POST", {"fileName": "source.lyl", "copyTo": "copy.lyl"}, client=self.b, headers=rev), 404)
        copied = self.json_response(self.request("POST", {"fileName": "source.lyl", "copyTo": "copy.lyl"}, client=self.a, headers=rev), 201)["project"]
        copy_rev = {"If-Match": '"' + copied["revision"] + '"'}
        renamed = self.json_response(self.request("POST", {"fileName": "copy.lyl", "renameFileTo": "renamed.lyl"}, client=self.a, headers=copy_rev))["project"]
        self.json_response(self.request("POST", {"folder": "target"}, client=self.a), 201)
        moved = self.json_response(self.request("POST", {"fileName": "renamed.lyl", "moveTo": "target"}, client=self.a,
                                               headers={"If-Match": '"' + renamed["revision"] + '"'}))["project"]
        self.json_response(self.request("DELETE", {"fileName": "source.lyl"}, client=self.b, headers=rev), 404)
        self.assertEqual(self.request(query={"fileName": "source.lyl"}, client=self.a)[2], project("A-source"))
        self.json_response(self.request("DELETE", {"path": "target", "fileName": "renamed.lyl"}, client=self.a,
                                       headers={"If-Match": '"' + moved["revision"] + '"'}))
        self.json_response(self.request(query={"fileName": "renamed.lyl", "path": "target"}, client=self.a), 404)
        self.json_response(self.request("POST", {"path": "target", "renameTo": "renamed-folder"}, client=self.a))
        self.json_response(self.request("DELETE", {"path": "renamed-folder", "deleteFolder": "1"}, client=self.a))

    def test_09_overwrite_revision_conflict_preserves_bytes(self):
        self.json_response(self.upload(self.a, marker="original"), 201)
        self.json_response(self.upload(self.a, marker="wrong-revision", headers={"If-Match": '"stale"'}), 409)
        self.assertEqual(self.request(query={"fileName": "same.lyl"}, client=self.a)[2], project("original"))

    def test_10_path_traversal_and_symlinks(self):
        self.json_response(self.upload(self.b, "private.lyl", "B-private"), 201)
        for path in ["../" + B, ".users/" + B, "/../" + B, "..\\" + B]:
            with self.subTest(path=path):
                self.json_response(self.request(query={"path": path, "fileName": "private.lyl"}, client=self.a), 400)
        root = self.private / "projects" / A
        (root / "link").symlink_to(self.private / "projects" / B, target_is_directory=True)
        self.json_response(self.request(query={"path": "link", "fileName": "private.lyl"}, client=self.a), 400)
        (root / "link").unlink()

    def test_11_logout_revokes_cookie_and_csrf_and_keeps_projects(self):
        self.json_response(self.upload(self.a, marker="persist"), 201)
        session = self.request(client=self.a, path="/session.php")
        self.assertEqual(self.json_response(session)["csrfToken"], self.a["csrf"])
        self.assertNotIn("domain=", session[1].get("set-cookie", "").lower())
        self.json_response(self.request("POST", path="/session.php", client=self.a, protect=False), 403)
        logout = self.request("POST", path="/session.php", client=self.a)
        self.assertEqual(logout[0], 204)
        self.assertIn("httponly", logout[1]["set-cookie"].lower())
        self.assertIn("samesite=lax", logout[1]["set-cookie"].lower())
        self.assertEqual((self.private / "sessions" / ("sess_" + self.a["id"])).read_bytes(), b"")
        self.json_response(self.upload(self.a, marker="late-autosave"), 401)
        self.json_response(self.request(query={"fileName": "same.lyl", "thumbnail": "1"}, client=self.a), 401)
        again = self.issue(A)
        self.assertEqual(self.request(query={"fileName": "same.lyl"}, client=again)[2], project("persist"))

    def test_12_export_validation_and_storage_scope(self):
        self.json_response(self.request("POST", {"exportFile": "shape.stl"}, b"solid test\nendsolid test\n", self.a), 201)
        self.assertTrue((self.private / "projects" / A / "shape.stl").is_file())
        self.assertFalse((self.private / "projects" / B / "shape.stl").exists())
        self.json_response(self.request("POST", {"exportFile": "payload.svg"}, b'<svg><script>alert(1)</script></svg>', self.a), 400)
        self.json_response(self.request("POST", {"fileName": "bad.lyl"}, b"not a project", self.a), 400)

    def test_13_user_root_symlink_is_rejected(self):
        (self.private / "projects" / A).symlink_to(self.private / "projects" / B, target_is_directory=True)
        self.json_response(self.request(client=self.a), 503)

    def test_14_unknown_methods_are_not_dispatched(self):
        for method in ["PUT", "PATCH", "OPTIONS", "HEAD"]:
            with self.subTest(method=method):
                response = self.request(method, client=self.a)
                self.assertEqual(response[0], 405)
                self.assertEqual(response[1]["allow"], "GET, POST, DELETE")

    def test_15_same_filename_update_and_delete_leave_other_owner_unchanged(self):
        self.json_response(self.upload(self.a, marker="A-preserve"), 201)
        record = self.json_response(self.upload(self.b, marker="B-initial-different-size"), 201)["project"]
        updated = self.json_response(self.upload(self.b, marker="B-updated-and-longer-content",
                                                headers={"If-Match": '"' + record["revision"] + '"'}))["project"]
        self.assertEqual(self.request(query={"fileName": "same.lyl"}, client=self.a)[2], project("A-preserve"))
        self.assertEqual(self.request(query={"fileName": "same.lyl"}, client=self.b)[2], project("B-updated-and-longer-content"))
        self.json_response(self.request("DELETE", {"fileName": "same.lyl"}, client=self.b,
                                       headers={"If-Match": '"' + updated["revision"] + '"'}))
        self.json_response(self.request(query={"fileName": "same.lyl"}, client=self.b), 404)
        self.assertEqual(self.request(query={"fileName": "same.lyl"}, client=self.a)[2], project("A-preserve"))


    def test_16_waiting_upload_is_rejected_after_session_revocation(self):
        # A CLI fixture holds the real native session lock, then destroys the
        # session. A simultaneous HTTP upload must wait and then fail closed.
        ready = Path(self.tmp.name) / "lock-ready"
        release = Path(self.tmp.name) / "lock-release"
        fixture = r'''
        require $argv[5];
        session_save_path($argv[1]);
        session_name('SSO_LAYERLING_SESSION');
        session_id($argv[2]);
        session_start();
        file_put_contents($argv[3], 'ready');
        $deadline = microtime(true) + 5;
        while (!is_file($argv[4]) && microtime(true) < $deadline) {
            usleep(10000);
            clearstatcache();
        }
        \Sso\Layerling\SessionRevocation::revoke();
        '''
        process = subprocess.Popen([OPTIONS.php, "-r", fixture, str(self.private / "sessions"),
                                    self.a["id"], str(ready), str(release),
                                    str(self.private / "src/SessionRevocation.php")],
                                   stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        try:
            for _ in range(100):
                if ready.exists():
                    break
                if process.poll() is not None:
                    self.fail("Session-lock fixture exited early")
                time.sleep(0.01)
            self.assertTrue(ready.exists())
            with ThreadPoolExecutor(max_workers=1) as executor:
                future = executor.submit(self.upload, self.a, "after-revocation.lyl", "denied")
                try:
                    with self.assertRaises(FutureTimeout):
                        future.result(timeout=0.15)
                finally:
                    release.write_text("release")
                self.json_response(future.result(timeout=5), 401)
            self.assertFalse((self.private / "projects" / A / "after-revocation.lyl").exists())
        finally:
            release.write_text("release")
            try:
                process.wait(timeout=5)
            except subprocess.TimeoutExpired:
                process.kill()
                process.wait()

    def privileged(self, kind="makerspace", both=False):
        user = "c" * 32
        client = self.issue(user)
        groups = ["test-makerspace-id", "test-admins-id"] if both else ["test-" + kind + "-id"]
        self.principal(user, roles=["ROLE_TEACHER"], groups=groups)
        return client, user

    def scoped(self, owner, **query):
        return {"_sso_owner": owner, **query}

    def test_17_makerspace_reads_and_edits_two_student_owners(self):
        client, actor = self.privileged()
        for owner, original, marker in [(A, self.a, "student-a"), (B, self.b, "student-b-longer")]:
            self.principal(owner, roles=["ROLE_STUDENT"])
            record = self.json_response(self.upload(original, marker=marker), 201)["project"]
            response = self.request(query=self.scoped(owner, fileName="same.lyl"), client=client)
            self.assertEqual(response[2], project(marker))
            self.json_response(self.upload(client, marker="edited-by-supervisor-" + owner,
                                           headers={"If-Match": '"' + record["revision"] + '"'}, owner=owner))
            self.assertEqual(self.request(query={"fileName": "same.lyl"}, client=original)[2], project("edited-by-supervisor-" + owner))
            record_meta = json.loads((self.private / "principals.json").read_text())[owner]
            self.assertEqual(record_meta["roles"], ["ROLE_STUDENT"])
        self.assertFalse((self.private / "projects" / actor).exists())

    def test_18_makerspace_cannot_delete_files_or_recursive_folders(self):
        client, _ = self.privileged()
        self.principal(A, roles=["ROLE_STUDENT"])
        self.json_response(self.request("POST", {"folder": "student-folder"}, client=self.a), 201)
        record = self.json_response(self.upload(self.a, folder="student-folder", marker="keep"), 201)["project"]
        for query in [self.scoped(A, path="student-folder", fileName="same.lyl"),
                      self.scoped(A, path="student-folder", deleteFolder="1", recursive="1")]:
            self.json_response(self.request("DELETE", query, client=client,
                                           headers={"If-Match": '"' + record["revision"] + '"'}), 403)
        self.json_response(self.request("POST", self.scoped(A, fileName="same.lyl", _method="DELETE"), client=client), 400)
        self.json_response(self.request("POST", self.scoped(A, fileName="same.lyl", deleteFolder="1"), client=client), 400)
        self.assertEqual(self.request(query={"path": "student-folder", "fileName": "same.lyl"}, client=self.a)[2], project("keep"))

    def test_19_makerspace_denied_nonstudents_unknown_and_ambiguous_roles(self):
        client, _ = self.privileged()
        self.json_response(self.upload(self.b, marker="nonstudent-private"), 201)
        for roles in [["ROLE_TEACHER"], [], None, ["ROLE_STUDENT", "ROLE_TEACHER"], ["student"], "ROLE_STUDENT"]:
            self.principal(B, roles=roles)
            self.json_response(self.request(query=self.scoped(B, fileName="same.lyl"), client=client), 403)
        self.json_response(self.request(query=self.scoped("f" * 32), client=client), 403)
        self.assertFalse((self.private / "projects" / ("f" * 32)).exists())

    def test_20_admin_reads_edits_and_deletes_student_and_nonstudent_files(self):
        client, _ = self.privileged("admins")
        for owner, original, roles in [(A, self.a, ["ROLE_STUDENT"]), (B, self.b, ["ROLE_TEACHER"])]:
            self.principal(owner, roles=roles)
            record = self.json_response(self.upload(original, marker="original-" + owner), 201)["project"]
            self.assertEqual(self.request(query=self.scoped(owner, fileName="same.lyl"), client=client)[2], project("original-" + owner))
            edited = self.json_response(self.upload(client, marker="admin-change-" + owner, owner=owner,
                                                    headers={"If-Match": '"' + record["revision"] + '"'}))["project"]
            self.assertEqual(self.request(query={"fileName": "same.lyl"}, client=original)[2], project("admin-change-" + owner))
            self.json_response(self.request("DELETE", self.scoped(owner, fileName="same.lyl"), client=client,
                                           headers={"If-Match": '"' + edited["revision"] + '"'}))
            self.assertFalse((self.private / "projects" / owner / "same.lyl").exists())

    def test_21_exact_group_ids_and_admin_precedence(self):
        self.principal(A, roles=["ROLE_STUDENT"])
        record = self.json_response(self.upload(self.a), 201)["project"]
        client, actor = self.privileged()
        for groups in [["makerspace-betreuung"], ["Admins"], ["TEST-ADMINS-ID"],
                       ["test-admins-id-extra"], ["test-makerspace-id", 123], "test-admins-id", None]:
            self.principal(actor, groups=groups)
            self.json_response(self.request(query=self.scoped(A), client=client), 403)
        self.principal(actor, groups=["test-makerspace-id", "test-admins-id"])
        self.json_response(self.request("DELETE", self.scoped(A, fileName="same.lyl"), client=client,
                                       headers={"If-Match": '"' + record["revision"] + '"'}))

    def test_22_roles_session_fields_and_headers_do_not_grant_foreign_access(self):
        self.principal(B, roles=["ROLE_STUDENT"])
        self.json_response(self.upload(self.b, marker="private-b"), 201)
        for roles in [["ROLE_ADMIN"], ["ROLE_TEACHER"], ["ROLE_STUDENT"]]:
            self.principal(A, roles=roles)
            client = self.issue(A, groups=["test-admins-id"], roles=["ROLE_ADMIN"], owner=B)
            self.json_response(self.request(query=self.scoped(B, fileName="same.lyl"), client=client,
                                           headers={"X-Sso-Owner": B, "X-Forwarded-Groups": "test-admins-id", "Remote-User": B}), 403)
        self.json_response(self.request(query=self.scoped(B, role="ROLE_ADMIN"), client=self.a), 400)
        for owner in ["../" + B, B.upper(), "", B + "/.."]:
            self.json_response(self.request(query=self.scoped(owner), client=self.a), 400)
        self.json_response(self.request(query={"_sso_owner[]": B}, client=self.a), 400)

    def test_23_group_revocation_and_owner_role_change_affect_existing_session(self):
        client, actor = self.privileged()
        self.principal(B, roles=["ROLE_STUDENT"])
        self.json_response(self.upload(self.b), 201)
        query = self.scoped(B, fileName="same.lyl")
        self.assertEqual(self.request(query=query, client=client)[0], 200)
        self.principal(actor, groups=[])
        self.json_response(self.request(query=query, client=client), 403)
        self.principal(actor, groups=["test-makerspace-id"])
        self.principal(B, roles=["ROLE_TEACHER"])
        self.json_response(self.request(query=query, client=client), 403)
        self.assertEqual(self.json_response(self.request(client=client, path="/session.php"))["csrfToken"], client["csrf"])
        self.principal(B, roles=["ROLE_STUDENT"])
        self.assertEqual(self.request(query=query, client=client)[0], 200)
        self.principal(actor, enabled=False)
        self.json_response(self.request(query=query, client=client), 403)

    def test_24_stale_future_and_missing_evidence_fail_closed(self):
        client, actor = self.privileged()
        self.principal(B, roles=["ROLE_STUDENT"])
        query = self.scoped(B)
        for stamp in [int(time.time()) - 301, int(time.time()) + 100, None, "recent"]:
            self.principal(actor, checkedAt=stamp)
            self.json_response(self.request(query=query, client=client), 403)
        self.principal(actor, checkedAt=int(time.time()))
        self.principal(B, checkedAt=int(time.time()) - 301)
        self.json_response(self.request(query=query, client=client), 403)
        # Admins do not require student status for all registered owners.
        self.principal(actor, groups=["test-admins-id"])
        self.json_response(self.request(query=query, client=client))
        self.principal(B, enabled=False)
        self.json_response(self.request(query=query, client=client))
        self.principal(actor, checkedAt=int(time.time()) - 301)
        self.json_response(self.request(query=query, client=client), 403)
        self.json_response(self.request(client=client))  # no privilege needed for own files

    def test_25_foreign_settings_are_not_file_permissions(self):
        self.json_response(self.request("POST", {"settings": "default"}, b'{"private":"A"}', self.a))
        self.principal(A, roles=["ROLE_STUDENT"])
        for kind in ["makerspace", "admins"]:
            client, _ = self.privileged(kind)
            self.json_response(self.request(query=self.scoped(A, settings="default"), client=client), 403)
            self.json_response(self.request("POST", self.scoped(A, settings="default"), b'{"private":"changed"}', client), 403)
            self.json_response(self.request("POST", self.scoped(A, settings="default", folder="bypass"), b'{}', client), 400)
        self.assertEqual(self.json_response(self.request(query={"settings": "default"}, client=self.a))["settings"], {"private": "A"})

    def test_26_foreign_thumbnail_urls_retain_owner_and_recheck_permissions(self):
        client, actor = self.privileged()
        self.principal(A, roles=["ROLE_STUDENT"])
        self.json_response(self.upload(self.a, thumbnail=True), 201)
        listing = self.json_response(self.request(query=self.scoped(A), client=client))
        link = listing["projects"][0]["thumbnailUrl"]
        self.assertIn("_sso_owner=" + A, link)
        image = self.request(client=client, path="/" + link)
        self.assertEqual(image[0], 200)
        self.assertEqual(image[2], PNG)
        self.assertEqual(image[1]["cache-control"], "private, no-store")
        self.principal(actor, groups=[])
        self.json_response(self.request(client=client, path="/" + link), 403)
        self.json_response(self.request(path="/" + link), 401)

    def test_27_search_all_and_structure_changes_remain_in_selected_owner(self):
        client, _ = self.privileged()
        for owner in [A, B]:
            self.principal(owner, roles=["ROLE_STUDENT"])
        self.json_response(self.upload(self.a, "alpha.lyl", "alpha"), 201)
        self.json_response(self.upload(self.b, "beta.lyl", "beta"), 201)
        for query in [self.scoped(A, search="beta"), self.scoped(A, all="1")]:
            result = self.json_response(self.request(query=query, client=client))
            self.assertNotIn("beta.lyl", json.dumps(result))
        original = self.json_response(self.request(query=self.scoped(A), client=client))["projects"][0]
        copied = self.json_response(self.request("POST", self.scoped(A, fileName="alpha.lyl", copyTo="copied.lyl"), client=client,
                                                headers={"If-Match": '"' + original["revision"] + '"'}), 201)["project"]
        renamed = self.json_response(self.request("POST", self.scoped(A, fileName="copied.lyl", renameFileTo="renamed.lyl"), client=client,
                                                 headers={"If-Match": '"' + copied["revision"] + '"'}))["project"]
        self.json_response(self.request("POST", self.scoped(A, folder="help"), client=client), 201)
        self.json_response(self.request("POST", self.scoped(A, fileName="renamed.lyl", moveTo="help"), client=client,
                                       headers={"If-Match": '"' + renamed["revision"] + '"'}))
        self.assertTrue((self.private / "projects" / A / "help/renamed.lyl").exists())
        self.assertFalse((self.private / "projects" / B / "help").exists())
        self.json_response(self.request("POST", self.scoped(A, fileName="alpha.lyl", targetOwner=B), client=client), 400)
        self.json_response(self.request("POST", self.scoped(A, exportFile="shape.stl"), b"solid test\nendsolid test\n", client), 201)
        self.assertTrue((self.private / "projects" / A / "shape.stl").exists())
        self.assertFalse((self.private / "projects" / B / "shape.stl").exists())

    def test_28_admin_recursive_delete_and_revision_conflict(self):
        client, _ = self.privileged("admins")
        self.json_response(self.request("POST", {"folder": "archive"}, client=self.a), 201)
        self.json_response(self.upload(self.a, folder="archive", marker="keep-until-delete"), 201)
        self.json_response(self.upload(self.b, marker="other-owner-kept"), 201)
        self.json_response(self.upload(client, folder="archive", marker="wrong-revision", owner=A,
                                       headers={"If-Match": '"stale"'}), 409)
        self.json_response(self.request("DELETE", self.scoped(A, path="archive", deleteFolder="1", recursive="1"), client=client))
        self.assertFalse((self.private / "projects" / A / "archive").exists())
        self.assertEqual(self.request(query={"fileName": "same.lyl"}, client=self.b)[2], project("other-owner-kept"))

    def test_29_registry_and_policy_configuration_fail_closed(self):
        client, _ = self.privileged("admins")
        path = self.private / "principals.json"
        original = path.read_bytes()
        try:
            path.write_text("{broken")
            self.json_response(self.request(client=client), 503)
            path.write_text("{}")
            self.json_response(self.request(client=client), 403)
        finally:
            path.write_bytes(original)
        config_path = self.private / "config.json"
        original_config = config_path.read_bytes()
        try:
            config = json.loads(original_config)
            config["groupIds"] = {"makerspace": None, "admins": None}
            config_path.write_text(json.dumps(config))
            self.json_response(self.request(query=self.scoped(A), client=client), 403)
            config["groupIds"] = {"makerspace": "same-id", "admins": "same-id"}
            config_path.write_text(json.dumps(config))
            self.json_response(self.request(query=self.scoped(A), client=client), 503)
        finally:
            config_path.write_bytes(original_config)
        for url in ["/principals.json", "/authorization.lock", "/audit.jsonl"]:
            self.assertEqual(self.request(path=url)[0], 404)

    def test_30_audit_is_minimal_and_required_before_foreign_mutation(self):
        client, actor = self.privileged()
        self.principal(A, roles=["ROLE_STUDENT"])
        self.json_response(self.upload(client, marker="sensitive-project-marker", owner=A), 201)
        self.json_response(self.request("DELETE", self.scoped(A, fileName="same.lyl"), client=client), 403)
        audit = self.private / "audit.jsonl"
        text = audit.read_text()
        rows = [json.loads(line) for line in text.splitlines()]
        self.assertEqual([r["phase"] for r in rows], ["begin", "end", "begin", "end"])
        self.assertEqual([r["status"] for r in rows if r["phase"] == "end"], [201, 403])
        for row in rows:
            self.assertEqual(set(row), {"request", "actor", "owner", "operation", "phase", "at"} | ({"status"} if row["phase"] == "end" else set()))
            self.assertEqual((row["actor"], row["owner"]), (actor, A))
        for secret in ["sensitive-project-marker", client["id"], client["csrf"], "same.lyl"]:
            self.assertNotIn(secret, text)
        canary = Path(self.tmp.name) / "audit-canary"
        canary.write_text("unchanged")
        original_audit = audit.read_bytes()
        audit.unlink()
        audit.symlink_to(canary)
        try:
            self.json_response(self.upload(client, name="not-created.lyl", owner=A), 503)
            self.assertFalse((self.private / "projects" / A / "not-created.lyl").exists())
            self.assertEqual(canary.read_text(), "unchanged")
        finally:
            audit.unlink()
            audit.write_bytes(original_audit)

    def test_31_waiting_foreign_write_observes_group_revocation(self):
        client, actor = self.privileged()
        self.principal(A, roles=["ROLE_STUDENT"])
        record = self.json_response(self.upload(self.a, marker="preserved"), 201)["project"]
        with open(self.private / "authorization.lock", "rb") as lock:
            fcntl.flock(lock, fcntl.LOCK_EX)
            with ThreadPoolExecutor(max_workers=1) as executor:
                future = executor.submit(self.upload, client, "same.lyl", "denied-after-revocation", "", False,
                                         {"If-Match": '"' + record["revision"] + '"'}, A)
                try:
                    with self.assertRaises(FutureTimeout):
                        future.result(timeout=0.15)
                    path = self.private / "principals.json"
                    records = json.loads(path.read_text())
                    records[actor]["groups"] = []
                    pending = self.private / "revoked.pending.json"
                    pending.write_text(json.dumps(records))
                    pending.replace(path)
                finally:
                    fcntl.flock(lock, fcntl.LOCK_UN)
                self.json_response(future.result(timeout=5), 403)
        self.assertEqual(self.request(query={"fileName": "same.lyl"}, client=self.a)[2], project("preserved"))

    def test_32_privileged_requests_keep_csrf_logout_and_path_guards(self):
        client, _ = self.privileged("admins")
        self.json_response(self.upload(self.a), 201)
        self.json_response(self.request("DELETE", self.scoped(A, fileName="same.lyl"), client=client, protect=False), 403)
        self.json_response(self.request(query=self.scoped(A, path="../" + B, fileName="same.lyl"), client=client), 400)
        self.assertEqual(self.request("POST", path="/session.php", client=client)[0], 204)
        self.json_response(self.request(query=self.scoped(A, fileName="same.lyl"), client=client), 401)

    def test_33_revoked_actor_can_logout_without_valid_registry(self):
        client, actor = self.privileged("admins")
        self.principal(actor, enabled=False)
        self.json_response(self.request(client=client), 403)
        self.json_response(self.request(client=client, path="/session.php"), 403)
        path = self.private / "principals.json"
        original = path.read_bytes()
        try:
            path.write_text("{broken")
            self.assertEqual(self.request("POST", path="/session.php", client=client)[0], 204)
        finally:
            path.write_bytes(original)
        self.json_response(self.request(query=self.scoped(A), client=client), 401)


    def test_34_saved_exports_obey_read_write_delete_permissions(self):
        self.principal(A, roles=["ROLE_STUDENT"])
        maker, actor = self.privileged()
        body = b"solid student\nendsolid student\n"
        self.json_response(self.request("POST", {"exportFile": "shape.stl"}, body, self.a), 201)
        query = self.scoped(A, exportFile="shape.stl")
        download = self.request(query=query, client=maker)
        self.assertEqual(download[0], 200)
        self.assertEqual(download[2], body)
        self.assertEqual(download[1]["cache-control"], "private, no-store")
        self.assertIn("attachment;", download[1]["content-disposition"])
        self.json_response(self.request(query=query, client=self.b), 403)
        self.json_response(self.request(query=query), 401)
        self.json_response(self.request("DELETE", query, client=maker,
                                       headers={"If-Match": download[1]["etag"]}), 403)
        changed = b"solid changed\nendsolid changed\n"
        self.json_response(self.request("POST", self.scoped(A, exportFile="shape.stl", overwrite="1"), changed, maker))
        self.principal(actor, groups=["test-admins-id"])
        self.json_response(self.request("DELETE", query, client=maker,
                                       headers={"If-Match": download[1]["etag"]}), 409)
        current = self.request(query=query, client=maker)
        self.assertEqual(current[2], changed)
        self.json_response(self.request("DELETE", query, client=maker), 428)
        self.json_response(self.request("DELETE", query, client=maker,
                                       headers={"If-Match": current[1]["etag"]}))
        self.json_response(self.request(query=query, client=maker), 404)

    def test_35_export_adapter_rejects_private_paths_and_symlinks(self):
        client, _ = self.privileged("admins")
        self.json_response(self.request("POST", {"exportFile": "shape.stl"}, b"solid x\nendsolid x\n", self.a), 201)
        for name in ["../shape.stl", "config.json", ".secret.pdf", "src/Gateway.php", "bad\\shape.stl"]:
            self.json_response(self.request(query=self.scoped(A, exportFile=name), client=client), 400)
        for folder in ["../" + B, ".settings", "..\\" + B]:
            self.json_response(self.request(query=self.scoped(A, path=folder, exportFile="shape.stl"), client=client), 400)
        link = self.private / "projects" / A / "link.pdf"
        link.symlink_to(self.private / "config.json")
        self.json_response(self.request(query=self.scoped(A, exportFile="link.pdf"), client=client), 404)
        self.json_response(self.request("DELETE", self.scoped(A, exportFile="link.pdf"), client=client,
                                       headers={"If-Match": '\"ignored\"'}), 404)
        self.json_response(self.request(query=self.scoped(A, exportFile="shape.stl", fileName="same.lyl"), client=client), 400)



if __name__ == "__main__":
    unittest.main(argv=[__file__, *remaining], verbosity=2)
