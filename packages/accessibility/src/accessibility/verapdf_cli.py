"""Invoke veraPDF CLI (local binary or ``verapdf/cli`` Docker image)."""

from __future__ import annotations

import json
import os
import subprocess
import xml.etree.ElementTree as ET
from pathlib import Path
from typing import Any, Dict, Optional, Tuple


def _verapdf_use_docker() -> bool:
    return (os.getenv("VERAPDF_USE_DOCKER") or "true").strip().lower() not in (
        "0",
        "false",
        "no",
    )


def _docker_image() -> str:
    return (os.getenv("VERAPDF_DOCKER_IMAGE") or "verapdf/cli:v1.30.1").strip()


def _verapdf_bin() -> str:
    return (os.getenv("VERAPDF_BIN") or "verapdf").strip()


def _build_cmd(pdf_path: Path, flavour: str) -> list[str]:
    flavour = flavour.strip() or "ua1"
    extra: list[str] = []
    max_fail = (os.getenv("VERAPDF_MAX_FAILURES_DISPLAYED") or "").strip()
    if max_fail:
        extra.extend(["--maxfailuresdisplayed", max_fail])

    if _verapdf_use_docker():
        mount = pdf_path.parent.resolve()
        in_container = f"/pdfs/{pdf_path.name}"
        return [
            "docker",
            "run",
            "--rm",
            "-v",
            f"{mount}:/pdfs:ro",
            _docker_image(),
            "-f",
            flavour,
            "--format",
            "json",
            "--disableerrormessages",
            *extra,
            in_container,
        ]
    return [
        _verapdf_bin(),
        "-f",
        flavour,
        "--format",
        "json",
        "--disableerrormessages",
        *extra,
        str(pdf_path.resolve()),
    ]


def _parse_xml_report(text: str) -> Dict[str, Any]:
    root = ET.fromstring(text)
    job = root.find(".//job")
    if job is None:
        return {}
    vr = job.find("validationReport")
    if vr is None:
        return {}
    details = vr.find("details")
    out: Dict[str, Any] = {
        "isCompliant": (vr.get("isCompliant") or "").lower() == "true",
        "profileName": vr.get("profileName"),
        "statement": vr.get("statement"),
    }
    if details is not None:
        out["details"] = {
            "passedRules": int(details.get("passedRules") or 0),
            "failedRules": int(details.get("failedRules") or 0),
            "passedChecks": int(details.get("passedChecks") or 0),
            "failedChecks": int(details.get("failedChecks") or 0),
        }
    return {"validationReport": out}


def _extract_validation_report(payload: Any) -> Dict[str, Any]:
    if not isinstance(payload, dict):
        return {}
    if "validationReport" in payload and isinstance(payload["validationReport"], dict):
        return payload["validationReport"]
    report = payload.get("report")
    if isinstance(report, dict):
        jobs = report.get("jobs")
        if isinstance(jobs, list) and jobs:
            job = jobs[0]
            if isinstance(job, dict):
                vr = job.get("validationReport")
                if isinstance(vr, dict):
                    return vr
    jobs = payload.get("jobs")
    if isinstance(jobs, list) and jobs and isinstance(jobs[0], dict):
        vr = jobs[0].get("validationReport")
        if isinstance(vr, dict):
            return vr
    return {}


def parse_verapdf_output(stdout: str) -> Dict[str, Any]:
    text = (stdout or "").strip()
    if not text:
        return {}
    if text.startswith("{"):
        try:
            data = json.loads(text)
            vr = _extract_validation_report(data)
            if vr:
                return vr
            return data
        except json.JSONDecodeError:
            pass
    if text.startswith("<"):
        try:
            parsed = _parse_xml_report(text)
            vr = parsed.get("validationReport")
            return vr if isinstance(vr, dict) else parsed
        except ET.ParseError:
            return {}
    return {}


def summarize_validation_report(vr: Dict[str, Any]) -> Dict[str, Any]:
    details = vr.get("details") if isinstance(vr.get("details"), dict) else {}
    compliant = vr.get("isCompliant")
    if compliant is None:
        compliant = vr.get("iscompliant")
    if isinstance(compliant, str):
        compliant = compliant.lower() == "true"
    return {
        "is_compliant": compliant,
        "profile_name": vr.get("profileName") or vr.get("profile_name"),
        "statement": vr.get("statement"),
        "failed_rules": int(details.get("failedRules") or details.get("failed_rules") or 0),
        "failed_checks": int(details.get("failedChecks") or details.get("failed_checks") or 0),
        "passed_rules": int(details.get("passedRules") or details.get("passed_rules") or 0),
        "passed_checks": int(details.get("passedChecks") or details.get("passed_checks") or 0),
    }


def run_verapdf(pdf_path: Path, flavour: str) -> Tuple[Dict[str, Any], Optional[str]]:
    """
    Validate ``pdf_path`` with veraPDF. Returns (parsed_validation_report, error_message).
    """
    if not pdf_path.is_file():
        return {}, f"file not found: {pdf_path}"
    cmd = _build_cmd(pdf_path, flavour)
    try:
        proc = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=int(os.getenv("VERAPDF_TIMEOUT_SEC") or "120"),
            check=False,
        )
    except subprocess.TimeoutExpired:
        return {}, "verapdf timeout"
    except FileNotFoundError as exc:
        return {}, f"verapdf not available: {exc}"

    if proc.returncode not in (0, 1):
        err = (proc.stderr or proc.stdout or "").strip()[:2000]
        return {}, err or f"verapdf exit {proc.returncode}"

    vr = parse_verapdf_output(proc.stdout)
    if not vr:
        err = (proc.stderr or "").strip()[:2000]
        return {}, err or "empty verapdf report"
    return vr, None
