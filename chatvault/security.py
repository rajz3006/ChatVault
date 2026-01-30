"""Security utilities for ChatVault — Phase 6 hardening.

Provides standalone security checks that other modules can call.
Does not modify any existing files or modules.
"""
from __future__ import annotations

import platform
import re
import subprocess
from pathlib import Path
from urllib.parse import urlparse


# ---------------------------------------------------------------------------
# Cloud sync detection
# ---------------------------------------------------------------------------

CLOUD_SYNC_MARKERS: dict[str, str] = {
    "iCloud": "Library/Mobile Documents",
    "Dropbox": "Dropbox",
    "Google Drive": "Google Drive",
    "OneDrive": "OneDrive",
}


def check_cloud_sync(project_dir: Path) -> list[str]:
    """Check if project directory is inside a cloud sync folder.

    Returns list of warnings (empty if safe).
    """
    warnings: list[str] = []
    resolved = str(project_dir.resolve())
    for service, marker in CLOUD_SYNC_MARKERS.items():
        if marker in resolved:
            warnings.append(
                f"Project directory appears to be inside {service} "
                f"(matched '{marker}' in path). Your chat data may be "
                f"synced to the cloud. Consider moving to a local-only directory."
            )
    return warnings


# ---------------------------------------------------------------------------
# Ollama binding check
# ---------------------------------------------------------------------------

def check_ollama_binding(host: str = "http://localhost:11434") -> list[str]:
    """Verify Ollama is bound to localhost only.

    Returns list of warnings (empty if safe).
    """
    warnings: list[str] = []
    parsed = urlparse(host)
    hostname = parsed.hostname or ""
    safe_hosts = {"localhost", "127.0.0.1", "::1"}
    if hostname not in safe_hosts:
        warnings.append(
            f"Ollama host '{hostname}' is not localhost. "
            f"Binding to a non-loopback address exposes your LLM to the network. "
            f"Set OLLAMA_HOST to http://localhost:11434 for local-only access."
        )
    return warnings


# ---------------------------------------------------------------------------
# API key safety
# ---------------------------------------------------------------------------

_API_KEY_PATTERN = re.compile(
    r"""(?:ANTHROPIC_API_KEY|OPENAI_API_KEY)\s*=\s*['"]?sk-[A-Za-z0-9_-]{10,}""",
)


def check_api_key_safety(project_dir: Path) -> list[str]:
    """Check that no API keys are hardcoded in config files.

    Returns list of warnings (empty if safe).
    """
    warnings: list[str] = []
    resolved = project_dir.resolve()

    # Check .env exists
    env_file = resolved / ".env"
    if env_file.exists():
        gitignore = resolved / ".gitignore"
        if gitignore.exists():
            content = gitignore.read_text(encoding="utf-8", errors="replace")
            if ".env" not in content:
                warnings.append(
                    ".env file exists but is not listed in .gitignore. "
                    "API keys could be committed to version control."
                )
        else:
            warnings.append(
                ".env file exists but no .gitignore found. "
                "API keys could be committed to version control."
            )

    # Scan source files for hardcoded keys
    for ext in ("*.py", "*.yaml", "*.yml", "*.toml", "*.cfg", "*.ini"):
        for filepath in resolved.rglob(ext):
            # Skip virtualenvs and hidden dirs
            parts = filepath.parts
            if any(p.startswith(".") or p in ("venv", ".venv", "node_modules", "__pycache__") for p in parts):
                continue
            try:
                text = filepath.read_text(encoding="utf-8", errors="replace")
            except OSError:
                continue
            if _API_KEY_PATTERN.search(text):
                rel = filepath.relative_to(resolved)
                warnings.append(
                    f"Possible hardcoded API key found in {rel}. "
                    f"Use environment variables instead."
                )
    return warnings


# ---------------------------------------------------------------------------
# Disk encryption check (macOS)
# ---------------------------------------------------------------------------

def check_disk_encryption() -> list[str]:
    """Check if FileVault is enabled on macOS.

    Returns list of warnings (empty if safe). On non-macOS platforms,
    returns an informational note.
    """
    warnings: list[str] = []
    if platform.system() != "Darwin":
        warnings.append(
            "Disk encryption check is only supported on macOS. "
            "Please verify your disk encryption manually."
        )
        return warnings

    try:
        result = subprocess.run(
            ["fdesetup", "status"],
            capture_output=True,
            text=True,
            timeout=10,
        )
        output = result.stdout.strip()
        if "FileVault is Off" in output:
            warnings.append(
                "FileVault is OFF. Your chat data is stored unencrypted on disk. "
                "Enable FileVault in System Settings > Privacy & Security."
            )
        elif "FileVault is On" not in output:
            warnings.append(
                f"Could not determine FileVault status. Output: {output}"
            )
    except (subprocess.TimeoutExpired, FileNotFoundError, OSError) as exc:
        warnings.append(f"Could not check FileVault status: {exc}")
    return warnings


# ---------------------------------------------------------------------------
# Raw export cleanup suggestion
# ---------------------------------------------------------------------------

def suggest_cleanup(data_dir: Path) -> list[str]:
    """After ingestion, suggest secure deletion of raw export files.

    Returns list of suggestions (empty if nothing to clean).
    """
    suggestions: list[str] = []
    resolved = data_dir.resolve()
    if not resolved.exists():
        return suggestions

    json_files = list(resolved.rglob("*.json"))
    if json_files:
        suggestions.append(
            f"Found {len(json_files)} JSON export file(s) in {resolved}. "
            f"After verifying your import, consider securely deleting raw exports:"
        )
        for f in json_files[:20]:  # Cap listing at 20
            rel = f.relative_to(resolved)
            suggestions.append(f"  - {rel}")
        if len(json_files) > 20:
            suggestions.append(f"  ... and {len(json_files) - 20} more.")
        suggestions.append(
            "On macOS, use 'rm -P <file>' for secure deletion. "
            "On Linux, use 'shred -u <file>'."
        )
    return suggestions


# ---------------------------------------------------------------------------
# Full security audit
# ---------------------------------------------------------------------------

def run_security_audit(project_dir: Path) -> dict[str, list[str]]:
    """Run all security checks.

    Returns a dict mapping check names to lists of warnings/suggestions.
    An empty list means the check passed with no issues.
    """
    data_dir = project_dir / "data"
    return {
        "cloud_sync": check_cloud_sync(project_dir),
        "ollama_binding": check_ollama_binding(),
        "api_key_safety": check_api_key_safety(project_dir),
        "disk_encryption": check_disk_encryption(),
        "raw_export_cleanup": suggest_cleanup(data_dir),
    }


# ---------------------------------------------------------------------------
# CLI entry point
# ---------------------------------------------------------------------------

def _print_audit() -> None:
    """Run a full security audit and print results to stdout."""
    project_dir = Path(__file__).resolve().parent.parent
    print(f"ChatVault Security Audit")
    print(f"Project directory: {project_dir}")
    print("=" * 60)

    results = run_security_audit(project_dir)

    all_clear = True
    for check_name, warnings in results.items():
        label = check_name.replace("_", " ").title()
        if warnings:
            all_clear = False
            print(f"\n[!] {label}:")
            for w in warnings:
                print(f"    {w}")
        else:
            print(f"\n[OK] {label}: No issues found.")

    print("\n" + "=" * 60)
    if all_clear:
        print("All checks passed.")
    else:
        print("Some checks returned warnings. Review the items above.")


if __name__ == "__main__":
    _print_audit()
