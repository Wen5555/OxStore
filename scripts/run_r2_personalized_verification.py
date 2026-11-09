"""R2 P-A12～P-A16 automated verification runner.

Records exit codes, environment, time and the tested SHA. Does not connect to
business or production databases. Old reports are not reused as this run's result.
"""
from __future__ import annotations

import hashlib
import json
import os
from datetime import datetime
from pathlib import Path
import shutil
import subprocess
import sys
import xml.etree.ElementTree as ET

ROOT = Path(__file__).resolve().parents[1]
EVIDENCE = ROOT / "docs/test/evidence/r2-personalized"
JAVA_HOME = os.environ.get("JAVA_HOME") or "/usr/lib/jvm/java-17-openjdk-amd64"
MVN = os.environ.get("MVN") or "/opt/apache-maven-3.9.9/bin/mvn"
JAVA = str(Path(JAVA_HOME) / "bin" / "java")


def command_env():
    env = os.environ.copy()
    env["JAVA_HOME"] = JAVA_HOME
    env["PATH"] = str(Path(JAVA_HOME) / "bin") + os.pathsep + env.get("PATH", "")
    env["TZ"] = "Asia/Shanghai"
    # Lockfile records npmmirror tarballs; always rewrite the host to the official registry.
    env["npm_config_registry"] = "https://registry.npmjs.org/"
    env["npm_config_replace_registry_host"] = "always"
    env["NPM_CONFIG_REGISTRY"] = "https://registry.npmjs.org/"
    return env


def run_step(name, args, cwd=ROOT, timeout=3600, extra_env=None):
    env = command_env()
    if extra_env:
        env.update(extra_env)
    started = datetime.now().astimezone()
    print(f"==> {name}: {' '.join(args)}", flush=True)
    result = subprocess.run(args, cwd=cwd, env=env, capture_output=True, text=True, timeout=timeout)
    finished = datetime.now().astimezone()
    log_path = EVIDENCE / "logs" / f"{name}.txt"
    log_path.parent.mkdir(parents=True, exist_ok=True)
    log_path.write_text(
        f"$ {' '.join(args)}\ncwd={cwd}\nexit={result.returncode}\n"
        f"started={started.isoformat()}\nfinished={finished.isoformat()}\n\n"
        + result.stdout + "\n" + result.stderr,
        encoding="utf-8")
    status = "PASS" if result.returncode == 0 else "FAIL"
    print(f"<== {name} {status} exit={result.returncode}", flush=True)
    return {
        "name": name,
        "command": args,
        "cwd": str(cwd),
        "exitCode": result.returncode,
        "startedAt": started.isoformat(),
        "finishedAt": finished.isoformat(),
        "log": str(log_path.relative_to(ROOT)),
        "status": status,
    }


def surefire_summary():
    tests = []
    for xml in sorted((ROOT / "backend/target/surefire-reports").glob("TEST-*.xml")):
        suite = ET.parse(xml).getroot()
        for case in suite.findall("testcase"):
            status = "PASS"
            if case.find("failure") is not None or case.find("error") is not None:
                status = "FAIL"
            elif case.find("skipped") is not None:
                status = "SKIP"
            tests.append({
                "class": case.attrib.get("classname"),
                "name": case.attrib.get("name"),
                "status": status,
            })
    dest = EVIDENCE / "shared" / "surefire"
    dest.mkdir(parents=True, exist_ok=True)
    for xml in (ROOT / "backend/target/surefire-reports").glob("TEST-*.xml"):
        shutil.copy2(xml, dest / xml.name)
    return {
        "total": len(tests),
        "passed": sum(t["status"] == "PASS" for t in tests),
        "failed": sum(t["status"] == "FAIL" for t in tests),
        "skipped": sum(t["status"] == "SKIP" for t in tests),
        "tests": tests,
    }


def environment():
    def capture(args):
        result = subprocess.run(args, capture_output=True, text=True)
        return (result.stdout or result.stderr).strip()

    docker = subprocess.run(["docker", "info"], capture_output=True, text=True)
    return {
        "os": capture(["uname", "-a"]),
        "java": capture([JAVA, "-version"]),
        "maven": capture([MVN, "-version"]),
        "python": capture([sys.executable, "--version"]),
        "node": capture(["node", "--version"]),
        "npm": capture(["npm", "--version"]),
        "dockerClient": capture(["docker", "version", "--format", "{{.Client.Version}}"]),
        "dockerServer": "available" if docker.returncode == 0 else docker.stderr.strip()[-500:],
        "javaHome": JAVA_HOME,
        "tz": "Asia/Shanghai",
    }


def prerequisites(sha):
    required = {
        "P-A01/P-A02": [
            "backend/src/main/resources/db/migrations/V6__auction_mode.sql",
            "scripts/verify_auction_database.py",
            "backend/src/main/java/com/team/shop/entity/AuctionSession.java",
        ],
        "P-A03-P-A07": [
            "backend/src/main/java/com/team/shop/service/AuctionServiceImpl.java",
            "backend/src/main/java/com/team/shop/service/AuctionSettlementService.java",
            "backend/src/main/java/com/team/shop/controller/buyer/AuctionController.java",
            "backend/src/main/java/com/team/shop/service/AuctionEventHub.java",
        ],
        "P-A08-P-A11": [
            "frontend/src/pages/admin/PublishProductPage.tsx",
            "frontend/src/pages/buyer/ProductDetailPage.tsx",
            "frontend/src/hooks/useAuctionEvents.ts",
            "frontend/src/pages/admin/AdminAuctionsPage.tsx",
            "frontend/src/pages/admin/SellerAuctionNotificationsPage.tsx",
        ],
    }
    files = {}
    missing = []
    for group, paths in required.items():
        files[group] = {}
        for rel in paths:
            path = ROOT / rel
            if path.is_file():
                files[group][rel] = hashlib.sha256(path.read_bytes()).hexdigest()
            else:
                missing.append(rel)
    return {"sha": sha, "files": files, "missing": missing, "complete": not missing}


def render_surefire_html(summary, dest):
    rows = "".join(
        f"<tr><td>{t['class']}</td><td>{t['name']}</td><td>{t['status']}</td></tr>"
        for t in summary["tests"])
    dest.write_text(
        "<html><body><h1>Surefire P-A12～P-A16 本轮结果</h1>"
        f"<p>total={summary['total']} passed={summary['passed']} "
        f"failed={summary['failed']} skipped={summary['skipped']}</p>"
        f"<table border='1' cellpadding='6'><tr><th>class</th><th>name</th><th>status</th></tr>{rows}</table>"
        "</body></html>",
        encoding="utf-8")


def screenshot_html(html, png):
    chrome = shutil.which("google-chrome") or shutil.which("chromium-browser") or shutil.which("chromium")
    if not chrome:
        return None
    profile = Path("/tmp/oxstore-chrome-shot")
    if profile.exists():
        shutil.rmtree(profile, ignore_errors=True)
    try:
        subprocess.run(
            [chrome, "--headless=new", "--disable-gpu", "--no-sandbox",
             "--disable-extensions", "--disable-background-networking",
             f"--user-data-dir={profile}",
             "--virtual-time-budget=2000", "--timeout=8000",
             f"--window-size=1280,900",
             f"--screenshot={png}", f"file://{html}"],
            capture_output=True, text=True, timeout=12)
    except subprocess.TimeoutExpired:
        pass
    return png if Path(png).exists() else None


def main():
    EVIDENCE.mkdir(parents=True, exist_ok=True)
    sha = subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=ROOT, text=True).strip()
    branch = subprocess.check_output(["git", "rev-parse", "--abbrev-ref", "HEAD"], cwd=ROOT, text=True).strip()
    started = datetime.now().astimezone()
    report = {
        "runAt": started.isoformat(),
        "testedSha": sha,
        "branch": branch,
        "environment": environment(),
        "prerequisites": prerequisites(sha),
        "steps": [],
        "note": "Fresh execution. Previous evidence directories are reference only.",
    }
    (EVIDENCE / "prerequisite-baseline.json").write_text(
        json.dumps(report["prerequisites"], ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    if report["prerequisites"]["missing"]:
        report["blocked"] = "missing prerequisite source files"
        (EVIDENCE / "INDEX.json").write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        return 1

    report["steps"].append(run_step(
        "mvn-clean-verify",
        [MVN, "-B", "-ntp", "-f", "backend/pom.xml", "clean", "verify"],
        timeout=1800))
    jar = ROOT / "backend/target/shop-0.1.0.jar"
    if not jar.exists():
        packaged = run_step(
            "mvn-package-skip-tests-for-isolated-db",
            [MVN, "-B", "-ntp", "-f", "backend/pom.xml", "package", "-DskipTests"],
            timeout=900)
        packaged["note"] = "Only used to obtain a JAR for isolated MySQL scripts after verify failed; this is not a test pass."
        report["steps"].append(packaged)
    report["junit"] = surefire_summary()
    html = EVIDENCE / "shared" / "surefire-summary.html"
    render_surefire_html(report["junit"], html)
    shot = screenshot_html(html, EVIDENCE / "shared" / "surefire-summary.png")
    report["junit"]["screenshot"] = str(shot.relative_to(ROOT)) if shot else None

    docker_ok = subprocess.run(["docker", "info"], capture_output=True).returncode == 0
    jar = ROOT / "backend/target/shop-0.1.0.jar"
    if docker_ok and jar.exists():
        report["steps"].append(run_step(
            "verify-auction-database",
            [sys.executable, "-X", "utf8", "scripts/verify_auction_database.py",
             "--java", JAVA, "--jar", str(jar),
             "--output", str(EVIDENCE / "p-a12" / "auction-mysql-results.json")],
            timeout=1800))
        report["steps"].append(run_step(
            "verify-iteration2-database",
            [sys.executable, "-X", "utf8", "scripts/verify_iteration2_database.py",
             "--java", JAVA, "--jar", str(jar),
             "--output", str(EVIDENCE / "p-a12" / "iteration2-mysql-results.json")],
            timeout=1800))
    else:
        report["steps"].append({
            "name": "verify-auction-database",
            "status": "BLOCKED",
            "reason": "Docker engine or backend JAR unavailable",
            "docker": docker_ok,
            "jar": jar.exists(),
        })

    report["steps"].append(run_step(
        "frontend-npm-ci",
        ["npm", "ci", "--no-audit", "--no-fund"],
        cwd=ROOT / "frontend", timeout=900))
    local_playwright = ROOT / "frontend/node_modules/.bin/playwright"
    playwright = (
        [str(local_playwright)] if local_playwright.exists()
        else ["npx", "--no-install", "playwright"]
    )
    report["steps"].append(run_step(
        "playwright-install-chrome",
        playwright + ["install", "chrome"],
        cwd=ROOT / "frontend", timeout=900))
    report["steps"].append(run_step(
        "frontend-build",
        ["npm", "run", "build"],
        cwd=ROOT / "frontend", timeout=600))
    report["steps"].append(run_step(
        "playwright-mock-e2e",
        playwright + ["test"],
        cwd=ROOT / "frontend",
        extra_env={"OXSTORE_EVIDENCE_DIR": str(EVIDENCE)},
        timeout=600))

    fullstack_step = {
        "name": "playwright-fullstack-e2e",
        "kind": "real-stack",
        "note": "Mock Playwright passing is not full-chain passing.",
    }
    if docker_ok and jar.exists():
        fullstack_step.update(run_step(
            "playwright-fullstack-e2e",
            [sys.executable, "-X", "utf8", "scripts/run_auction_fullstack_e2e.py",
             "--java", JAVA, "--jar", str(jar)],
            timeout=1800))
        fullstack_step["kind"] = "real-stack"
    else:
        fullstack_step.update({
            "status": "BLOCKED",
            "reason": "Requires isolated Docker MySQL and a backend JAR from mvn verify",
        })
    report["steps"].append(fullstack_step)

    report["finishedAt"] = datetime.now().astimezone().isoformat()
    report["success"] = all(step.get("status") == "PASS" for step in report["steps"] if step.get("status") != "BLOCKED")
    (EVIDENCE / "INDEX.json").write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"testedSha": sha, "success": report["success"], "steps": [
        {"name": s["name"], "status": s.get("status"), "exitCode": s.get("exitCode")} for s in report["steps"]
    ]}, ensure_ascii=False, indent=2))
    return 0 if report["success"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
