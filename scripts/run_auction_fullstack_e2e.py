"""Start an isolated MySQL + backend + Vite stack and run real Playwright E2E.

This is not the mock frontend suite. Passwords and dumps stay out of JSON.
"""
from __future__ import annotations

import argparse
from datetime import datetime, timedelta
import json
import os
from pathlib import Path
import socket
import subprocess
import sys
import tempfile
import threading
import time
import traceback
from urllib.error import HTTPError, URLError
from urllib.request import urlopen
from zoneinfo import ZoneInfo

from migrate_iteration2 import ROOT, DockerMySQL
from verify_iteration2_database import Verification

EVIDENCE_SOLD = ROOT / "docs/test/evidence/r2-personalized/fullstack"
EVIDENCE_UNSOLD = ROOT / "docs/test/evidence/r2-personalized/fullstack-unsold"
EVIDENCE = EVIDENCE_SOLD


class FullstackRun(Verification):
    def __init__(self, args):
        super().__init__(args)
        self.container = "oxstore-r2-fullstack-" + self.owner[:12]
        self.frontend = None
        self.report["scope"] = "Isolated Docker MySQL + JAR + Vite Playwright full-stack E2E"

    def start_app(self, database, scratch):
        deadline = time.monotonic() + 90
        while True:
            try:
                with socket.socket() as probe:
                    probe.bind(("127.0.0.1", 8080))
                break
            except OSError:
                if time.monotonic() >= deadline:
                    raise RuntimeError("Port 8080 is still in use; previous isolated backend did not release it")
                time.sleep(0.5)
        mapping = self.command(["docker", "port", self.container, "3306/tcp"]).stdout.decode().strip()
        assert mapping.startswith("127.0.0.1:")
        env = os.environ.copy()
        env.update(DB_HOST="127.0.0.1", DB_PORT=mapping.rsplit(":", 1)[1], DB_NAME=database,
                   DB_USERNAME="root", DB_PASSWORD=self.root_password, JWT_SECRET=self.jwt_secret,
                   ADMIN_INITIAL_PASSWORD=self.admin_password, TZ="Asia/Shanghai")
        self.base_url = "http://127.0.0.1:8080"
        self.app_log = []
        self.app = subprocess.Popen(
            [self.args.java, "-jar", str(self.args.jar.resolve()),
             "--server.address=127.0.0.1", "--server.port=8080",
             "--spring.jpa.hibernate.ddl-auto=validate", f"--shop.upload-dir={scratch / 'uploads'}"],
            cwd=ROOT, env=env, stdout=subprocess.PIPE, stderr=subprocess.STDOUT)

        def consume():
            for line in self.app.stdout:
                text = line.decode("utf-8", errors="replace").rstrip()
                if any(value in text for value in (self.root_password, self.admin_password,
                                                   self.customer_password, self.jwt_secret)):
                    text = "[credential-related log omitted]"
                self.app_log.append(text)

        self.reader = threading.Thread(target=consume, daemon=True)
        self.reader.start()
        deadline = time.monotonic() + 90
        while time.monotonic() < deadline:
            if self.app.poll() is not None:
                raise RuntimeError("Application exited: " + "\n".join(self.app_log[-16:]))
            try:
                with urlopen(self.base_url + "/api/categories/tree", timeout=2) as response:
                    if (response.status == 200 and DockerMySQL(self.container, database).query(
                            "SELECT COUNT(*) FROM seller WHERE username='admin'") == "1"):
                        return
            except (URLError, HTTPError, TimeoutError, ConnectionError):
                time.sleep(0.5)
        raise TimeoutError("Backend did not become ready on :8080")

    def start_frontend(self):
        self.frontend_log = []
        self.frontend = subprocess.Popen(
            ["npm", "run", "dev", "--", "--host", "127.0.0.1", "--port", "4174", "--strictPort"],
            cwd=ROOT / "frontend", stdout=subprocess.PIPE, stderr=subprocess.STDOUT)

        def consume():
            for line in self.frontend.stdout:
                self.frontend_log.append(line.decode("utf-8", errors="replace").rstrip())

        threading.Thread(target=consume, daemon=True).start()
        deadline = time.monotonic() + 60
        while time.monotonic() < deadline:
            if self.frontend.poll() is not None:
                raise RuntimeError("Vite exited: " + "\n".join(self.frontend_log[-16:]))
            try:
                with urlopen("http://127.0.0.1:4174/", timeout=2) as response:
                    if response.status == 200:
                        return
            except (URLError, TimeoutError, ConnectionError):
                time.sleep(0.5)
        raise TimeoutError("Frontend did not become ready")

    def stop_frontend(self):
        if self.frontend and self.frontend.poll() is None:
            self.frontend.terminate()
            try:
                self.frontend.wait(timeout=10)
            except subprocess.TimeoutExpired:
                self.frontend.kill()
                self.frontend.wait(timeout=5)

    def seed(self):
        self.seller = self.login("admin", seller=True)
        for name in (self.buyer_a, self.buyer_b):
            self.request("POST", "/api/auth/register",
                         {"username": name, "password": self.customer_password, "phone": "13800000000"},
                         expected=201)
        tree = self.request("GET", "/api/categories/tree")
        leaf = tree[0]["children"][0]["id"]
        ends = datetime.now(ZoneInfo("Asia/Shanghai")).replace(microsecond=0) + timedelta(seconds=90)
        product = self.request(
            "POST", "/api/admin/products",
            {"name": self.product_name, "category2Id": leaf, "sellingMode": "AUCTION",
             "startPrice": "10.00", "minIncrement": "2.00",
             "endsAt": ends.strftime("%Y-%m-%dT%H:%M:%S")},
            self.seller, expected=201, files=())
        self.product_id = product["productId"]
        self.report["seed"] = {
            "productId": self.product_id,
            "productName": self.product_name,
            "endsAt": ends.isoformat(),
        }

    def unsold_db_state(self):
        db = DockerMySQL(self.container, "fresh")
        safe_name = self.product_name.replace("\\", "\\\\").replace("'", "''")
        session = db.query(
            "SELECT a.id, a.product_id, a.status, a.bid_count, "
            "IFNULL(a.winner_intent_id,'NULL'), IFNULL(a.current_price,'NULL'), "
            "p.status, p.selling_mode FROM auction_session a "
            "JOIN product p ON p.id=a.product_id "
            f"WHERE p.name='{safe_name}'")
        if not session:
            return {"found": False}
        auction_id, product_id, status, bid_count, winner, price, product_status, mode = session.split("\t")
        intents = db.query(f"SELECT COUNT(*) FROM purchase_intent WHERE product_id={product_id}")
        bids = db.query(f"SELECT COUNT(*) FROM auction_bid WHERE auction_id={auction_id}")
        notes = db.query(
            "SELECT CONCAT(notification_type, ':', COUNT(*)) FROM auction_notification "
            f"WHERE auction_id={auction_id} GROUP BY notification_type ORDER BY 1")
        note_total = db.query(f"SELECT COUNT(*) FROM auction_notification WHERE auction_id={auction_id}")
        return {
            "found": True,
            "auctionId": int(auction_id),
            "productId": int(product_id),
            "sessionStatus": status,
            "bidCount": int(bid_count),
            "winnerIntentId": None if winner == "NULL" else int(winner),
            "currentPrice": None if price == "NULL" else price,
            "productStatus": product_status,
            "sellingMode": mode,
            "purchaseIntentCount": int(intents),
            "bidRowCount": int(bids),
            "notifications": notes.splitlines() if notes else [],
            "notificationCount": int(note_total),
        }

    def unsold_api_state(self, product_id):
        snapshot = self.request("GET", f"/api/products/{product_id}/auction")
        listing = self.request("GET", "/api/admin/auctions?page=1&size=20", token=self.seller)
        reminders = self.request("GET", "/api/admin/auction-notifications?page=1&size=20", token=self.seller)
        item = next((row for row in listing.get("items", []) if row.get("productId") == product_id), None)
        return {
            "snapshot": {
                "auctionStatus": snapshot.get("auctionStatus"),
                "bidCount": snapshot.get("bidCount"),
                "currentPrice": snapshot.get("currentPrice"),
                "leaderAlias": snapshot.get("leaderAlias"),
            },
            "adminItem": item,
            "sellerNotifications": [
                {"type": n.get("type"), "productId": n.get("productId"), "productName": n.get("productName"),
                 "finalPrice": n.get("finalPrice")}
                for n in reminders.get("items", [])
            ],
        }


def default_java():
    home = os.environ.get("JAVA_HOME")
    if home:
        return str(Path(home) / "bin" / "java")
    return "java"


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--java", default=default_java())
    parser.add_argument("--jar", type=Path, default=ROOT / "backend/target/shop-0.1.0.jar")
    parser.add_argument("--image", default="mysql:8.0.46")
    parser.add_argument("--scenario", choices=("sold", "unsold"), default="sold")
    parser.add_argument(
        "--ends-in-seconds", type=int, default=70,
        help="Unsold scenario only: legal deadline offset. Contract minimum is 60s. "
             "Waits for the real @Scheduled scanner; does not fake ENDED_UNSOLD.")
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    unsold = args.scenario == "unsold"
    evidence = EVIDENCE_UNSOLD if unsold else EVIDENCE_SOLD
    if args.output is None:
        args.output = evidence / ("unsold-results.json" if unsold else "fullstack-results.json")
    run = FullstackRun(args)
    run.buyer_a = "r2_fullstack_a"
    run.buyer_b = "r2_fullstack_b"
    run.product_name = ("R2全栈流拍-" if unsold else "R2全栈拍卖-") + run.owner[:8]
    run.report["scenario"] = args.scenario
    run.report["started_at"] = datetime.now().astimezone().isoformat()
    run.report["tested_sha"] = subprocess.check_output(
        ["git", "rev-parse", "HEAD"], cwd=ROOT, text=True).strip()
    error = None
    try:
        if not args.jar.exists():
            raise FileNotFoundError(f"Missing backend JAR: {args.jar}")
        if unsold and args.ends_in_seconds < 60:
            raise ValueError("ends-in-seconds must be >= 60 to satisfy the publish contract")
        with tempfile.TemporaryDirectory(prefix="oxstore-r2-fullstack-") as temp:
            scratch = Path(temp)
            run.setup_database(("fresh",))
            run.start_app("fresh", scratch)
            env = os.environ.copy()
            env.update(
                OXSTORE_FULLSTACK="1",
                OXSTORE_FULLSTACK_BASE_URL="http://127.0.0.1:4174",
                OXSTORE_ADMIN_USERNAME="admin",
                OXSTORE_ADMIN_PASSWORD=run.admin_password,
                OXSTORE_EVIDENCE_DIR=str(evidence if unsold else ROOT / "docs/test/evidence/r2-personalized"),
            )
            if unsold:
                run.seller = run.login("admin", seller=True)
                config_name = "playwright.fullstack-unsold.config.ts"
                log_name = "playwright-unsold.txt"
            else:
                run.seed()
                env.update(
                    OXSTORE_BUYER_PASSWORD=run.customer_password,
                    OXSTORE_BUYER_A=run.buyer_a,
                    OXSTORE_BUYER_B=run.buyer_b,
                    OXSTORE_AUCTION_NAME=run.product_name,
                    OXSTORE_AUCTION_PRODUCT_ID=str(run.product_id),
                )
                config_name = "playwright.fullstack.config.ts"
                log_name = "playwright-fullstack.txt"
            run.start_frontend()
            if unsold:
                # Compute the legal deadline after MySQL/JAR/Vite are up so the
                # remaining window is still >= 60s when the seller submits.
                ends = datetime.now(ZoneInfo("Asia/Shanghai")).replace(microsecond=0) + timedelta(
                    seconds=args.ends_in_seconds)
                run.report["time_preparation"] = {
                    "kind": "short-but-legal-deadline",
                    "endsInSeconds": args.ends_in_seconds,
                    "endsAt": ends.isoformat(),
                    "scheduler": "@Scheduled(fixedDelay = 5000) scanDueAuctions",
                    "note": "Deadline is set a short legal offset after the stack is ready. "
                            "System clock is not faked; settleOne is not called from the test; "
                            "ENDED_UNSOLD is not written by SQL.",
                }
                env.update(
                    OXSTORE_AUCTION_NAME=run.product_name,
                    OXSTORE_UNSOLD_ENDS_AT=ends.strftime("%Y-%m-%dT%H:%M:%S"),
                    OXSTORE_UNSOLD_ENDS_AT_DISPLAY=ends.strftime("%Y-%m-%d %H:%M:%S"),
                    OXSTORE_UNSOLD="1",
                )
            evidence.mkdir(parents=True, exist_ok=True)
            playwright_bin = ROOT / "frontend/node_modules/.bin/playwright"
            playwright_cmd = (
                [str(playwright_bin), "test", "--config", config_name]
                if playwright_bin.exists()
                else ["npx", "--no-install", "playwright", "test", "--config", config_name]
            )
            playwright = subprocess.run(
                playwright_cmd,
                cwd=ROOT / "frontend", env=env, capture_output=True, text=True)
            (evidence / log_name).write_text(
                playwright.stdout + "\n" + playwright.stderr, encoding="utf-8")
            run.report["playwright_exit"] = playwright.returncode
            if unsold:
                first = run.unsold_db_state()
                run.report["db_after_ui"] = first
                if first.get("found"):
                    run.report["api_after_ui"] = run.unsold_api_state(first["productId"])
                time.sleep(12)
                second = run.unsold_db_state()
                run.report["db_after_repeat_scan"] = second
                expected = (
                    first.get("found") and second.get("found")
                    and first["sessionStatus"] == second["sessionStatus"] == "ENDED_UNSOLD"
                    and first["winnerIntentId"] is None and second["winnerIntentId"] is None
                    and first["purchaseIntentCount"] == second["purchaseIntentCount"] == 0
                    and first["bidRowCount"] == second["bidRowCount"] == 0
                    and first["notificationCount"] == second["notificationCount"] == 1
                    and first["notifications"] == second["notifications"] == ["AUCTION_UNSOLD:1"]
                    and first["productStatus"] == "OFFLINE"
                )
                run.report["repeat_scan_idempotent"] = bool(expected)
            if playwright.returncode:
                raise RuntimeError("fullstack Playwright failed:\n" + (playwright.stdout + playwright.stderr)[-4000:])
            if unsold and not run.report.get("repeat_scan_idempotent"):
                raise AssertionError(
                    "Unsold DB/API corroboration failed: " + json.dumps(
                        {"first": run.report.get("db_after_ui"),
                         "second": run.report.get("db_after_repeat_scan")}, ensure_ascii=False))
    except Exception as exc:
        error = exc
        run.report["error"] = str(exc)
        traceback.print_exc()
    finally:
        try:
            run.stop_frontend()
        except Exception as exc:
            error = error or exc
            run.report["frontend_cleanup_error"] = str(exc)
        try:
            run.finish()
        except Exception as exc:
            error = error or exc
            run.report["cleanup_error"] = str(exc)
        run.report["success"] = error is None
        run.report["finished_at"] = datetime.now().astimezone().isoformat()
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(json.dumps(run.report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        print(args.output)
    return 1 if error else 0


if __name__ == "__main__":
    raise SystemExit(main())
