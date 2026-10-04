"""在专用 MySQL 容器中验证 R5 数据库交付；仅依赖 Python 标准库。

运行前在 backend 执行 mvn test package。本脚本不连接现有业务库，
测试凭据仅保存在进程内存，退出时停止应用并删除本次专用容器。
"""

from __future__ import annotations

import argparse
import base64
import json
import os
from pathlib import Path
import secrets
import socket
import subprocess
import tempfile
import threading
import time
from datetime import datetime
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen
import uuid


ROOT = Path(__file__).resolve().parents[1]
DB_DIR = ROOT / "backend/src/main/resources/db"
TABLES = {"seller", "product", "purchase_intent", "trade_attempt", "product_status_event"}


class Verification:
    def __init__(self, args: argparse.Namespace):
        self.args = args
        self.container = "oxstore-r5-" + uuid.uuid4().hex[:12]
        self.created = False
        self.app: subprocess.Popen | None = None
        self.app_log: list[str] = []
        self.password = secrets.token_hex(24)
        self.admin_password = "R5!" + secrets.token_hex(12)
        self.jwt = ""
        self.base_url = ""
        self.report = {
            "run_at": datetime.now().astimezone().isoformat(),
            "source_base": "8db4228",
            "scope": "独立 MySQL / HTTP / 迁移 / 重启验证；不连接现有业务库",
            "checks": [],
        }

    def command(self, args: list[str], *, sql: str | None = None, env=None,
                check=True, timeout=90) -> subprocess.CompletedProcess:
        result = subprocess.run(args, input=sql.encode("utf-8") if sql else None,
                                stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                                env=env, timeout=timeout)
        if check and result.returncode:
            raise RuntimeError(result.stderr.decode("utf-8", errors="replace")[-1500:])
        return result

    def sql(self, statement: str, database="shop", *, check=True):
        if database not in {"shop", "legacy", "schema_checks"}:
            raise ValueError("Only isolated test databases are permitted")
        args = ["docker", "exec", "-i", self.container, "sh", "-c",
                'MYSQL_PWD="$MYSQL_ROOT_PASSWORD" exec mysql -uroot '
                f"--default-character-set=utf8mb4 --batch --skip-column-names {database}"]
        return self.command(args, sql="SET NAMES utf8mb4;\n" + statement, check=check)

    def query(self, statement: str, database="shop") -> str:
        return self.sql(statement, database).stdout.decode("utf-8").strip()

    def verify(self, name: str, condition: bool, detail: str):
        self.report["checks"].append({"name": name, "status": "PASS" if condition else "FAIL", "detail": detail})
        print(f"{'PASS' if condition else 'FAIL'} {name}: {detail}", flush=True)
        if not condition:
            raise AssertionError(name)

    def request(self, method: str, path: str, data=None, *, admin=False,
                raw: bytes | None = None, content_type=None, expected=200):
        headers = {"Content-Type": content_type or "application/json"}
        if admin:
            headers["Authorization"] = "Bearer " + self.jwt
        body = raw if raw is not None else (json.dumps(data).encode("utf-8") if data is not None else None)
        request = Request(self.base_url + path, data=body, headers=headers, method=method)
        try:
            with urlopen(request, timeout=20) as response:
                status, payload = response.status, response.read()
        except HTTPError as error:
            status, payload = error.code, error.read()
        result = json.loads(payload)
        if status != expected:
            # 仅报告状态，避免把包含口令/JWT 的完整响应写入证据。
            raise AssertionError(f"{method} {path.split('/intents/')[0]}: HTTP {status}, expected {expected}")
        if expected == 200 and result.get("code") != 0:
            raise AssertionError("Unexpected business response code")
        return result.get("data")

    def start_app(self, scratch: Path):
        with socket.socket() as probe:
            probe.bind(("127.0.0.1", 0))
            app_port = probe.getsockname()[1]
        env = os.environ.copy()
        env.update(DB_HOST="127.0.0.1", DB_PORT=str(self.db_port), DB_NAME="shop",
                   DB_USERNAME="root", DB_PASSWORD=self.password,
                   JWT_SECRET=self.jwt_secret, TOKEN_LOOKUP_KEY=self.lookup_key,
                   ADMIN_INITIAL_PASSWORD=self.admin_password, TZ="Asia/Shanghai")
        self.base_url = f"http://127.0.0.1:{app_port}"
        self.app = subprocess.Popen(
            [self.args.java, "-jar", str(Path(self.args.jar).resolve()),
             "--server.address=127.0.0.1", f"--server.port={app_port}",
             "--spring.jpa.hibernate.ddl-auto=validate", f"--shop.upload-dir={scratch / 'uploads'}"],
            cwd=ROOT, env=env, stdout=subprocess.PIPE, stderr=subprocess.STDOUT)

        def consume_log():
            for line in self.app.stdout:
                text = line.decode("utf-8", errors="replace").rstrip()
                if "password" in text.lower() or "secret" in text.lower():
                    text = "[credential-related log omitted]"
                self.app_log.append(text)

        threading.Thread(target=consume_log, daemon=True).start()
        deadline = time.monotonic() + 90
        while time.monotonic() < deadline:
            if self.app.poll() is not None:
                raise RuntimeError("Application exited: " + "\n".join(self.app_log[-15:]))
            try:
                with urlopen(self.base_url + "/api/products/current", timeout=2):
                    pass
                return
            except HTTPError as error:
                if error.code == 404:
                    return
                time.sleep(0.5)
            except (URLError, TimeoutError, ConnectionError):
                time.sleep(0.5)
        raise TimeoutError("Application did not become ready")

    def stop_app(self):
        if self.app and self.app.poll() is None:
            self.app.terminate()
            try:
                self.app.wait(timeout=15)
            except subprocess.TimeoutExpired:
                self.app.kill()
                self.app.wait(timeout=10)

    def publish(self, name: str):
        boundary = "r5-" + uuid.uuid4().hex
        parts = []
        for key, value in {"name": name, "description": "中文数据库验证：保留历史记录", "price": "19.90"}.items():
            parts.append(f'--{boundary}\r\nContent-Disposition: form-data; name="{key}"\r\n\r\n{value}\r\n'.encode("utf-8"))
        png = base64.b64decode("iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mP8/x8AAwMCAO+aX1cAAAAASUVORK5CYII=")
        parts.append(f'--{boundary}\r\nContent-Disposition: form-data; name="image"; filename="sample.png"\r\nContent-Type: image/png\r\n\r\n'.encode() + png + b"\r\n")
        parts.append(f"--{boundary}--\r\n".encode())
        return self.request("POST", "/api/admin/products", admin=True,
                            raw=b"".join(parts), content_type="multipart/form-data; boundary=" + boundary)

    def queue(self):
        return self.request("GET", "/api/admin/intents", admin=True)

    def current_trade(self):
        return next(i for i in self.queue() if i["status"] == "IN_TRANSACTION")

    def schema_and_constraints(self):
        self.sql(DB_DIR.joinpath("schema.sql").read_text(encoding="utf-8"))
        actual = set(self.query("SHOW TABLES;").splitlines())
        self.verify("DB-01 五表建库", actual == TABLES, ", ".join(sorted(actual)))
        snapshot = self.query("SELECT TABLE_NAME,COLUMN_NAME,COLUMN_TYPE,IS_NULLABLE,EXTRA FROM information_schema.columns WHERE TABLE_SCHEMA='shop' ORDER BY TABLE_NAME,ORDINAL_POSITION;")
        self.report["columns_tsv"] = snapshot
        self.sql("CREATE DATABASE schema_checks CHARACTER SET utf8mb4;")
        self.sql(DB_DIR.joinpath("schema.sql").read_text(encoding="utf-8"), "schema_checks")
        self.sql("INSERT INTO product(name,description,image_path,price,status,published_at) VALUES('商品','说明','/test.png',1,'ONLINE',NOW(6)); INSERT INTO purchase_intent(product_id,buyer_name,buyer_phone,status,submitted_at,queue_seq) VALUES(1,'甲','00000000000','IN_TRANSACTION',NOW(6),1); INSERT INTO trade_attempt(intent_id,started_at) VALUES(1,NOW(6));", "schema_checks")
        invalid = {
            "第二件活跃商品": "INSERT INTO product(name,description,image_path,price,status,published_at) VALUES('重复','说明','/test.png',1,'ONLINE',NOW(6));",
            "非正价格": "INSERT INTO product(name,description,image_path,price,status,published_at) VALUES('非法','说明','/test.png',0,'SOLD',NOW(6));",
            "第二条交易中意向": "INSERT INTO purchase_intent(product_id,buyer_name,buyer_phone,status,submitted_at,queue_seq) VALUES(1,'乙','00000000000','IN_TRANSACTION',NOW(6),2);",
            "重复队列序号": "INSERT INTO purchase_intent(product_id,buyer_name,buyer_phone,status,submitted_at,queue_seq) VALUES(1,'乙','00000000000','QUEUING',NOW(6),1);",
            "不存在的商品外键": "INSERT INTO purchase_intent(product_id,buyer_name,buyer_phone,status,submitted_at,queue_seq) VALUES(999,'乙','00000000000','QUEUING',NOW(6),2);",
            "重复未结束交易尝试": "INSERT INTO trade_attempt(intent_id,started_at) VALUES(1,NOW(6));",
            "结束交易缺少结果": "INSERT INTO trade_attempt(intent_id,started_at,finished_at) VALUES(1,NOW(6),NOW(6));",
        }
        for label, statement in invalid.items():
            rejected = self.sql(statement, "schema_checks", check=False)
            error = rejected.stderr.decode("utf-8", errors="replace")
            self.verify("DB-02 " + label, rejected.returncode != 0 and any(code in error for code in ("1062", "3819", "1452")), "MySQL 约束拒绝非法记录")

    def migration(self):
        # 原三表结构由当前 DDL 去除新增字段/索引得到，仅用于隔离夹具。
        schema = DB_DIR.joinpath("schema.sql").read_text(encoding="utf-8").split("CREATE TABLE IF NOT EXISTS trade_attempt")[0]
        additions = ("token_lookup", "queue_seq", "uk_intent_product_seq", "uk_intent_token_lookup", "idx_intent_product_status_seq")
        schema = "\n".join(line for line in schema.splitlines() if not any(item in line for item in additions)).replace("DATETIME(6)", "DATETIME")
        self.sql("CREATE DATABASE legacy CHARACTER SET utf8mb4;")
        self.sql(schema, "legacy")
        self.sql("INSERT INTO product(name,description,image_path,price,status,published_at) VALUES('迁移中文','说明','/legacy.png',1,'ONLINE','2026-10-01 10:00:00'); INSERT INTO purchase_intent(product_id,buyer_name,buyer_phone,status,submitted_at) VALUES(1,'迁移甲','00000000000','QUEUING','2026-10-01 10:01:00'),(1,'迁移乙','00000000001','QUEUING','2026-10-01 10:01:00');", "legacy")
        v2 = DB_DIR.joinpath("migrations/V2__queue_history.sql").read_text(encoding="utf-8")
        self.sql("UPDATE purchase_intent SET status='IN_TRANSACTION' WHERE id=1;", "legacy")
        blocked = self.sql(v2, "legacy", check=False)
        unchanged = self.query("SELECT COUNT(*) FROM information_schema.columns WHERE TABLE_SCHEMA='legacy' AND COLUMN_NAME='queue_seq';", "legacy")
        self.verify("DB-03 迁移前置拦截", blocked.returncode != 0 and unchanged == "0", "有交易中意向时拒绝迁移，表未变更")
        self.sql("UPDATE purchase_intent SET status='QUEUING' WHERE id=1;", "legacy")
        before = self.query("SELECT id,buyer_name,buyer_phone,status,DATE_FORMAT(submitted_at,'%Y-%m-%d %H:%i:%s') FROM purchase_intent ORDER BY id;", "legacy")
        self.sql(v2, "legacy")
        after = self.query("SELECT id,buyer_name,buyer_phone,status,DATE_FORMAT(submitted_at,'%Y-%m-%d %H:%i:%s') FROM purchase_intent ORDER BY id;", "legacy")
        self.verify("DB-04 V2升级与数据保留", before == after and self.query("SELECT GROUP_CONCAT(queue_seq ORDER BY id) FROM purchase_intent;", "legacy") == "1,2", "两条旧意向、中文和原时间保留，序号按时间与ID回填")
        self.verify("DB-05 禁止重复迁移", self.sql(v2, "legacy", check=False).returncode != 0, "已存在queue_seq时拒绝重跑")
        # 已执行旧版V2的实例：人为退回旧CHECK，再验证V3收紧约束。
        self.sql("""ALTER TABLE trade_attempt DROP CHECK chk_attempt_completion,
            ADD CONSTRAINT chk_attempt_completion CHECK (
                (finished_at IS NULL AND result IS NULL AND fail_action IS NULL)
                OR (finished_at IS NOT NULL AND finished_at >= started_at AND
                    ((result='SUCCESS' AND fail_action IS NULL) OR
                     (result='FAILED' AND fail_action IN ('REQUEUE','DISCARD'))))
            );
            INSERT INTO trade_attempt(intent_id,started_at,finished_at) VALUES(1,NOW(6),NOW(6));""", "legacy")
        v3 = DB_DIR.joinpath("migrations/V3__trade_attempt_completion_check.sql").read_text(encoding="utf-8")
        self.verify("DB-06 V3不伪造旧结果", self.sql(v3, "legacy", check=False).returncode != 0, "不完整旧结果阻止约束升级")
        self.sql("UPDATE trade_attempt SET result='SUCCESS' WHERE id=1;", "legacy")
        self.sql(v3, "legacy")
        self.verify("DB-07 V3约束升级", self.sql("INSERT INTO trade_attempt(intent_id,started_at,finished_at) VALUES(1,NOW(6),NOW(6));", "legacy", check=False).returncode != 0, "核实旧结果后升级，结束但无结果的记录被拒绝")

    def business(self, scratch: Path):
        self.start_app(scratch)
        self.jwt = self.request("POST", "/api/admin/auth/login", {"username": "admin", "password": self.admin_password})["token"]
        self.verify("DB-08 JPA映射", True, "Java 17 应用以ddl-auto=validate成功启动并登录")
        product = self.publish("R5中文验证商品")
        self.verify("DB-09 中文商品", product["name"] == "R5中文验证商品", "HTTP写入/读取中文正确")
        codes = []
        for name in ("测试甲", "测试乙", "测试丙"):
            codes.append(self.request("POST", "/api/intents", {"buyerName": name, "buyerPhone": "13800000000"})["code"])
        original = self.query("SELECT submitted_at,token_hash,token_lookup FROM purchase_intent WHERE buyer_name='测试甲';")
        first = self.queue()[0]
        self.request("POST", f"/api/admin/intents/{first['id']}/start", admin=True)
        current = self.current_trade()
        self.request("POST", f"/api/admin/intents/{current['id']}/fail", {"action": "REQUEUE", "tradeAttemptId": current["currentTradeAttemptId"]}, admin=True)
        q = self.queue()
        self.verify("DB-10 失败递补与队尾", [i["buyerName"] for i in q] == ["测试乙", "测试丙", "测试甲"], "乙交易中；丙第1位，甲第2位")
        self.verify("DB-11 重排保留时间及口令", original == self.query("SELECT submitted_at,token_hash,token_lookup FROM purchase_intent WHERE buyer_name='测试甲';"), "首次时间、BCrypt哈希与HMAC索引均保持")
        own = self.request("GET", "/api/intents/" + codes[0])
        modified = self.request("PUT", "/api/intents/" + codes[0], {"buyerName": "测试甲修改"})
        self.verify("DB-12 原口令查询修改", own["position"] == 2 and modified["position"] == 2, "重排后原码可用，修改姓名不改变位次")
        self.request("DELETE", "/api/intents/" + codes[0])
        self.request("GET", "/api/intents/" + codes[0], expected=403)
        self.verify("DB-13 撤销使口令失效", self.query("SELECT token_hash IS NULL AND token_lookup IS NULL FROM purchase_intent WHERE id=" + str(first["id"])) == "1", "撤销退出队列，两项口令字段置NULL")
        current = self.current_trade()
        self.request("POST", f"/api/admin/intents/{current['id']}/fail", {"action": "DISCARD", "tradeAttemptId": current["currentTradeAttemptId"]}, admin=True)
        self.request("GET", "/api/intents/" + codes[1], expected=403)
        self.verify("DB-14 作废使口令失效", True, "乙作废后原码返回403，丙自动进入交易")
        current = self.current_trade()
        self.request("POST", f"/api/admin/intents/{current['id']}/success", {"tradeAttemptId": current["currentTradeAttemptId"]}, admin=True)
        for code in codes:
            self.request("GET", "/api/intents/" + code, expected=403)
        records = self.request("GET", f"/api/admin/products/{product['id']}/records", admin=True)
        self.report["sample_records"] = records
        self.verify("DB-15 历史完整保留", len(records["intents"]) == 3 and len(records["tradeAttempts"]) == 3 and len(records["statusEvents"]) == 7, "保留3条意向、2次失败+1次成功及7个状态事件")
        self.verify("DB-16 售出失效", self.query("SELECT COUNT(*) FROM purchase_intent WHERE token_hash IS NOT NULL OR token_lookup IS NOT NULL;") == "0", "商品SOLD，全部旧码返回403")
        self.stop_app()
        self.start_app(scratch)
        self.jwt = self.request("POST", "/api/admin/auth/login", {"username": "admin", "password": self.admin_password})["token"]
        reloaded = self.request("GET", f"/api/admin/products/{product['id']}/records", admin=True)
        self.verify("DB-17 应用重启持久化", reloaded == records, "商品、意向、交易尝试和事件记录保持一致")
        self.stop_app()
        before = self.query("SELECT (SELECT COUNT(*) FROM product),(SELECT COUNT(*) FROM purchase_intent),(SELECT COUNT(*) FROM trade_attempt),(SELECT COUNT(*) FROM product_status_event);")
        self.command(["docker", "restart", self.container])
        self.wait_database()
        after = self.query("SELECT (SELECT COUNT(*) FROM product),(SELECT COUNT(*) FROM purchase_intent),(SELECT COUNT(*) FROM trade_attempt),(SELECT COUNT(*) FROM product_status_event);")
        self.verify("DB-18 MySQL重启持久化", before == after, "保留容器数据卷重启后行数一致: " + after)

    def wait_database(self):
        deadline = time.monotonic() + 120
        while time.monotonic() < deadline:
            if self.sql("SELECT 1;", check=False).returncode == 0:
                return
            time.sleep(1)
        raise TimeoutError("MySQL did not become ready")

    def run(self):
        self.command(["docker", "info", "--format", "{{.ServerVersion}}"], timeout=20)
        env = os.environ.copy()
        env["MYSQL_ROOT_PASSWORD"] = self.password
        self.command(["docker", "run", "-d", "--name", self.container,
                      "--env", "MYSQL_ROOT_PASSWORD", "--env", "MYSQL_DATABASE=shop",
                      "--env", "TZ=Asia/Shanghai", "-p", "127.0.0.1::3306", self.args.image], env=env, timeout=300)
        self.created = True
        port = self.command(["docker", "port", self.container, "3306/tcp"]).stdout.decode().strip()
        self.db_port = int(port.rsplit(":", 1)[1])
        self.jwt_secret, self.lookup_key = secrets.token_hex(32), secrets.token_hex(32)
        self.wait_database()
        self.report["mysql_version"] = self.query("SELECT VERSION();")
        self.schema_and_constraints()
        self.migration()
        with tempfile.TemporaryDirectory(prefix="oxstore-r5-") as scratch:
            self.business(Path(scratch))

    def cleanup(self):
        self.stop_app()
        if self.created:
            self.command(["docker", "rm", "-f", "-v", self.container], check=False)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--java", default="java")
    parser.add_argument("--jar", default=str(ROOT / "backend/target/shop-0.1.0.jar"))
    parser.add_argument("--image", default="mysql:8.0")
    parser.add_argument("--output", type=Path, default=ROOT / "docs/test/evidence/r5-db-results.json")
    args = parser.parse_args()
    check = Verification(args)
    try:
        check.run()
        check.report["status"] = "PASS"
    except Exception as error:
        check.report["status"] = "FAIL"
        check.report["error"] = str(error)
        raise
    finally:
        check.cleanup()
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(json.dumps(check.report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


if __name__ == "__main__":
    main()
