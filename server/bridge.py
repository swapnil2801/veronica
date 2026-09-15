"""Hermes Bridge: maps Veronica's tool calls to real Hermes/system commands.

All actions are allowlisted. Destructive ops require confirm=True (the LLM
is instructed to ask the user aloud first). Every action is logged.
"""
import asyncio
import json
import logging
import subprocess
import time
from datetime import datetime
from pathlib import Path
from threading import Lock

import psutil

from . import config

log = logging.getLogger("veronica.bridge")
ACTION_LOG = config.LOG_DIR / "actions.log"

HOME = Path.home()
PROFILES_DIR = HOME / ".hermes" / "profiles"
HERMES_BIN = next((p for p in (
    HOME / ".local" / "bin" / "hermes",
    HOME / ".hermes" / "hermes-agent" / "venv" / "bin" / "hermes",
) if p.exists()), None)
DEFAULT_SESSION = "veronica-voice"
DEFAULT_AGENT_LOCK = Lock()

# systemd user units Veronica may control. Dashboard & her own service are protected.
CONTROLLABLE_UNITS = {
    "gateway": "hermes-gateway.service",
    "gateway-manager": "hermes-gateway-manager.service",
    "gateway-technologia": "hermes-gateway-technologia.service",
}
PROTECTED_UNITS = {"hermes-dashboard.service", "veronica.service"}
ALL_UNITS = sorted(set(CONTROLLABLE_UNITS.values()) | PROTECTED_UNITS - {"veronica.service"})


def _audit(action: str, detail: str):
    with open(ACTION_LOG, "a") as f:
        f.write(f"{datetime.now().isoformat()} {action} {detail}\n")


def _run(cmd: list[str], timeout: int = 30) -> tuple[int, str]:
    try:
        p = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout)
        return p.returncode, (p.stdout + p.stderr).strip()
    except subprocess.TimeoutExpired:
        return -1, f"command timed out after {timeout}s"


def ask_default_agent(instruction: str, timeout: int = 600) -> dict:
    """Run one turn through the real default Hermes agent with its CLI toolset."""
    if HERMES_BIN is None:
        return {"ok": False, "error": "Hermes CLI not found"}
    if not instruction.strip():
        return {"ok": False, "error": "empty instruction"}
    _audit("default_agent", instruction[:200])
    cmd = [
        str(HERMES_BIN), "-p", "default", "chat",
        "--continue", DEFAULT_SESSION, "--create-if-missing",
        "--query-file", "-", "--quiet", "--source", "voice",
    ]
    try:
        with DEFAULT_AGENT_LOCK:
            p = subprocess.run(cmd, input=instruction, capture_output=True,
                               text=True, timeout=timeout, cwd=str(HOME))
        output = p.stdout.strip()
        # Quiet mode still emits a machine-readable session_id line; do not
        # send that implementation detail to Veronica's spoken response.
        output = "\n".join(
            line for line in output.splitlines()
            if not line.startswith("session_id:")
        ).strip()
        if p.returncode != 0 and p.stderr.strip():
            output = (output + "\n" + p.stderr.strip()).strip()
        return {"ok": p.returncode == 0, "result": output[-12000:], "returncode": p.returncode}
    except subprocess.TimeoutExpired:
        return {"ok": False, "error": f"default Hermes agent timed out after {timeout}s"}

# ---------------------------------------------------------------- tools ----

def list_agents(light: bool = False) -> dict:
    """List all Hermes profiles, gateway services and their live status."""
    units = []
    for unit in sorted(set(CONTROLLABLE_UNITS.values()) | {"hermes-dashboard.service"}):
        rc, out = _run(["systemctl", "--user", "show", unit, "-p", "ActiveState", "-p", "MainPID", "-p", "ActiveEnterTimestamp"])
        info = dict(line.split("=", 1) for line in out.splitlines() if "=" in line)
        entry = {"unit": unit, "status": info.get("ActiveState", "unknown"), "since": info.get("ActiveEnterTimestamp", "")}
        pid = int(info.get("MainPID", 0) or 0)
        if pid and not light:
            try:
                proc = psutil.Process(pid)
                entry["mem_mb"] = round(proc.memory_info().rss / 1e6, 1)
            except psutil.Error:
                pass
        units.append(entry)
    profiles = sorted(p.name for p in PROFILES_DIR.iterdir() if p.is_dir())
    return {"services": units, "profiles": profiles}


def agent_status(name: str) -> dict:
    """Status + recent logs for one service. name: gateway|gateway-manager|gateway-technologia|dashboard."""
    unit = CONTROLLABLE_UNITS.get(name, "hermes-dashboard.service" if name == "dashboard" else None)
    if not unit:
        return {"error": f"unknown agent '{name}'", "known": list(CONTROLLABLE_UNITS) + ["dashboard"]}
    rc, active = _run(["systemctl", "--user", "is-active", unit])
    rc, logs = _run(["journalctl", "--user", "-u", unit, "-n", "15", "--no-pager", "-o", "cat"])
    return {"unit": unit, "status": active, "recent_log": logs[-2000:]}


def control_agent(name: str, action: str, confirm: bool = False) -> dict:
    """Start/stop/restart a gateway service. Destructive ops need confirm=True."""
    if action not in ("start", "stop", "restart"):
        return {"error": "action must be start|stop|restart"}
    unit = CONTROLLABLE_UNITS.get(name)
    if not unit:
        return {"error": f"'{name}' is not controllable", "controllable": list(CONTROLLABLE_UNITS)}
    if action in ("stop", "restart") and not confirm:
        return {"needs_confirmation": True, "message": f"Ask the user to confirm before you {action} {unit}."}
    _audit("control_agent", f"{action} {unit}")
    rc, out = _run(["systemctl", "--user", action, unit], timeout=60)
    rc2, status = _run(["systemctl", "--user", "is-active", unit])
    return {"unit": unit, "action": action, "ok": rc == 0, "status_now": status, "output": out[:500]}


def list_cron_jobs() -> dict:
    """All Hermes cron jobs across profiles, with schedule and last result."""
    jobs = []
    for jf in list(PROFILES_DIR.glob("*/cron/jobs.json")) + [HOME / ".hermes" / "cron" / "jobs.json"]:
        if not jf.exists():
            continue
        profile = jf.parent.parent.name if jf.parent.parent != HOME / ".hermes" else "default"
        try:
            data = json.loads(jf.read_text())
            raw = data.get("jobs", []) if isinstance(data, dict) else data
            if isinstance(raw, dict):
                raw = list(raw.values())
            for j in raw:
                if not isinstance(j, dict):
                    continue
                state = j.get("state") if isinstance(j.get("state"), dict) else {}
                jobs.append({
                    "profile": profile,
                    "id": j.get("id", "")[:12],
                    "name": j.get("name") or (j.get("prompt") or "")[:60],
                    "schedule": j.get("schedule"),
                    "enabled": j.get("enabled", True),
                    "last_status": state.get("last_status") or j.get("last_status"),
                    "last_error": (state.get("last_error") or j.get("last_error") or "")[:200],
                })
        except Exception as e:  # noqa: BLE001
            jobs.append({"profile": profile, "error": f"parse failed: {e}"})
    return {"jobs": jobs, "count": len(jobs)}


def get_errors(minutes: int = 60) -> dict:
    """Warnings/errors from all hermes services in the last N minutes."""
    rc, out = _run([
        "journalctl", "--user", "-u", "hermes-gateway*", "-u", "hermes-dashboard",
        "-p", "warning", "--since", f"-{minutes}m", "--no-pager", "-o", "short",
    ], timeout=30)
    lines = out.splitlines()[-40:]
    return {"minutes": minutes, "count": len(lines), "lines": lines}


def system_health() -> dict:
    """VPS resource snapshot: CPU, RAM, disk, network, load."""
    vm = psutil.virtual_memory()
    du = psutil.disk_usage("/")
    net = psutil.net_io_counters()
    return {
        "cpu_pct": psutil.cpu_percent(interval=None),  # non-blocking, since last call
        "load_avg": [round(x, 2) for x in psutil.getloadavg()],
        "ram": {"used_gb": round(vm.used / 1e9, 2), "total_gb": round(vm.total / 1e9, 2), "pct": vm.percent},
        "disk": {"used_gb": round(du.used / 1e9, 1), "total_gb": round(du.total / 1e9, 1), "pct": du.percent},
        "net_mb": {"sent": round(net.bytes_sent / 1e6, 1), "recv": round(net.bytes_recv / 1e6, 1)},
        "uptime_hours": round((time.time() - psutil.boot_time()) / 3600, 1),
    }


def status_report() -> dict:
    """Composite report: services + cron health + system resources."""
    agents = list_agents()
    cron = list_cron_jobs()
    failing = [j for j in cron["jobs"] if j.get("last_error")]
    return {
        "services": agents["services"],
        "profiles": agents["profiles"],
        "cron_total": cron["count"],
        "cron_failing": failing,
        "system": system_health(),
    }


def send_task(profile: str, instruction: str, confirm: bool = False) -> dict:
    """Send a task to a Hermes profile agent (runs the real Hermes CLI)."""
    profiles = [p.name for p in PROFILES_DIR.iterdir() if p.is_dir()]
    if profile not in profiles:
        return {"error": f"unknown profile '{profile}'", "profiles": profiles}
    if not confirm:
        return {"needs_confirmation": True, "message": f"Confirm with the user: send this task to '{profile}'?"}
    if HERMES_BIN is None:
        return {"error": "Hermes CLI not found", "searched": [
            str(HOME / ".local" / "bin" / "hermes"),
            str(HOME / ".hermes" / "hermes-agent" / "venv" / "bin" / "hermes"),
        ]}
    _audit("send_task", f"{profile}: {instruction[:200]}")
    rc, out = _run([str(HERMES_BIN), "-p", profile, "chat", "-q", instruction], timeout=280)
    return {"profile": profile, "ok": rc == 0, "result": out[-1500:]}


# ------------------------------------------------------------ registry ----

TOOLS = {
    "list_agents": list_agents,
    "agent_status": agent_status,
    "control_agent": control_agent,
    "list_cron_jobs": list_cron_jobs,
    "get_errors": get_errors,
    "system_health": system_health,
    "status_report": status_report,
    "send_task": send_task,
}

TOOL_SPECS = [
    {"type": "function", "function": {"name": "list_agents", "description": "List all Hermes agent services and profiles with live status, CPU and RAM.", "parameters": {"type": "object", "properties": {}}}},
    {"type": "function", "function": {"name": "agent_status", "description": "Detailed status and recent logs for one agent service.", "parameters": {"type": "object", "properties": {"name": {"type": "string", "enum": ["gateway", "gateway-manager", "gateway-technologia", "dashboard"]}}, "required": ["name"]}}},
    {"type": "function", "function": {"name": "control_agent", "description": "Start, stop or restart a Hermes gateway service. stop/restart require confirm=true which you may only set AFTER the user verbally confirmed.", "parameters": {"type": "object", "properties": {"name": {"type": "string", "enum": ["gateway", "gateway-manager", "gateway-technologia"]}, "action": {"type": "string", "enum": ["start", "stop", "restart"]}, "confirm": {"type": "boolean"}}, "required": ["name", "action"]}}},
    {"type": "function", "function": {"name": "list_cron_jobs", "description": "List all scheduled cron jobs across every Hermes profile with schedule and last run result.", "parameters": {"type": "object", "properties": {}}}},
    {"type": "function", "function": {"name": "get_errors", "description": "Fetch warnings and errors from Hermes services in the last N minutes.", "parameters": {"type": "object", "properties": {"minutes": {"type": "integer", "default": 60}}}}},
    {"type": "function", "function": {"name": "system_health", "description": "VPS resource usage: CPU, RAM, disk, network, uptime.", "parameters": {"type": "object", "properties": {}}}},
    {"type": "function", "function": {"name": "status_report", "description": "Comprehensive report: all services, profiles, cron job health, and system resources. Use for 'status report' or 'how is everything'.", "parameters": {"type": "object", "properties": {}}}},
    {"type": "function", "function": {"name": "send_task", "description": "Delegate a task to a named Hermes profile agent. Requires confirm=true set only after the user verbally confirmed. Can take minutes.", "parameters": {"type": "object", "properties": {"profile": {"type": "string"}, "instruction": {"type": "string"}, "confirm": {"type": "boolean"}}, "required": ["profile", "instruction"]}}},
]


async def call_tool(name: str, args: dict) -> dict:
    fn = TOOLS.get(name)
    if not fn:
        return {"error": f"unknown tool {name}"}
    log.info("tool %s(%s)", name, args)
    try:
        return await asyncio.to_thread(fn, **args)
    except Exception as e:  # noqa: BLE001
        log.exception("tool %s failed", name)
        return {"error": str(e)}
