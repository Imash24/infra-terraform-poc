#!/usr/bin/env python3
"""Fetch artifacts from GitHub Actions -> Save locally -> Send to FinOps API.

Usage:
    export GITHUB_TOKEN=ghp_your_token_here
    python3 scripts/fetch_and_ingest.py --repo Imash24/infra-terraform-poc

    # Save only (don't send to API):
    python3 scripts/fetch_and_ingest.py --repo Imash24/infra-terraform-poc --save-only

Output saved to: ./output/{timestamp}/
"""

import argparse
import io
import json
import os
import sys
import zipfile
from datetime import datetime

import httpx

GITHUB_API = "https://api.github.com"


def _headers(token: str) -> dict:
    return {
        "Authorization": f"Bearer {token}",
        "Accept": "application/vnd.github+json",
    }


def list_artifacts(repo: str, token: str) -> list:
    """List all non-expired artifacts."""
    url = f"{GITHUB_API}/repos/{repo}/actions/artifacts"
    print(f"  GET {url}")
    resp = httpx.get(url, headers=_headers(token), params={"per_page": 20})
    resp.raise_for_status()
    artifacts = resp.json().get("artifacts", [])
    print(f"  Found {len(artifacts)} artifact(s)")
    return artifacts


def download_artifact(artifact: dict, token: str) -> bytes:
    """Download artifact ZIP bytes."""
    url = artifact["archive_download_url"]
    print(f"  Downloading: {artifact['name']} (id={artifact['id']})")
    resp = httpx.get(url, headers=_headers(token), follow_redirects=True)
    resp.raise_for_status()
    print(f"  Size: {len(resp.content)} bytes")
    return resp.content


def extract_json(zip_bytes: bytes) -> dict | None:
    """Extract first JSON file from ZIP."""
    with zipfile.ZipFile(io.BytesIO(zip_bytes)) as zf:
        for name in zf.namelist():
            if name.endswith(".json"):
                return json.loads(zf.read(name))
    return None


def save(filename: str, data, output_dir: str) -> str:
    """Save JSON to local file."""
    os.makedirs(output_dir, exist_ok=True)
    path = os.path.join(output_dir, filename)
    with open(path, "w") as f:
        json.dump(data, f, indent=2, default=str)
    print(f"  >> Saved: {path}")
    return path


def send_to_api(payload: dict, api_url: str, api_key: str) -> dict:
    """POST payload to FinOps API."""
    url = f"{api_url}/api/v1/infracost-runs"
    print(f"  POST {url}")
    resp = httpx.post(
        url,
        json=payload,
        headers={"Content-Type": "application/json", "X-API-Key": api_key},
        timeout=30,
    )
    resp.raise_for_status()
    return resp.json()


def main():
    parser = argparse.ArgumentParser(
        description="Fetch GitHub Actions artifacts, save locally, send to API",
    )
    parser.add_argument("--repo", required=True, help="owner/repo")
    parser.add_argument("--api-url", default="http://localhost:8000")
    parser.add_argument("--api-key", default=None)
    parser.add_argument("--output-dir", default="./output")
    parser.add_argument(
        "--save-only", action="store_true",
        help="Save locally without sending to the API",
    )
    args = parser.parse_args()

    github_token = os.environ.get("GITHUB_TOKEN")
    if not github_token:
        print("ERROR: set GITHUB_TOKEN env var")
        print("  https://github.com/settings/tokens -> repo scope")
        sys.exit(1)

    api_key = (
        args.api_key
        or os.environ.get("FINOPS_API_KEY", "poc-api-key-change-in-production")
    )

    # ── 1. List artifacts ──
    print("\n=== 1. Fetching artifact list ===")
    artifacts = list_artifacts(args.repo, github_token)

    payload_art = None
    infracost_art = None
    for a in artifacts:
        if a["expired"]:
            continue
        if a["name"] == "finops-payload" and payload_art is None:
            payload_art = a
        if a["name"] == "infracost-output" and infracost_art is None:
            infracost_art = a

    if not payload_art:
        print("\nERROR: 'finops-payload' artifact not found.")
        print("Available:")
        for a in artifacts:
            tag = "expired" if a["expired"] else "active"
            print(f"  - {a['name']} ({tag}, {a['created_at']})")
        print(f"\nCheck: https://github.com/{args.repo}/actions")
        sys.exit(1)

    # ── 2. Download & save locally ──
    print("\n=== 2. Downloading & saving locally ===")
    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    out = os.path.join(args.output_dir, ts)

    payload_data = extract_json(download_artifact(payload_art, github_token))
    if not payload_data:
        print("ERROR: no JSON in finops-payload artifact")
        sys.exit(1)
    save("finops-payload.json", payload_data, out)

    if infracost_art:
        raw_data = extract_json(download_artifact(infracost_art, github_token))
        if raw_data:
            save("infracost-raw-output.json", raw_data, out)

    save("summary.json", {
        "fetched_at": datetime.now().isoformat(),
        "repo": args.repo,
        "commit_sha": payload_data.get("commit_sha", ""),
        "author": payload_data.get("author", ""),
        "pr_number": payload_data.get("pr_number"),
        "branch": payload_data.get("branch"),
        "cost_before": payload_data.get("cost_before_monthly_usd"),
        "cost_after": payload_data.get("cost_after_monthly_usd"),
        "cost_delta": payload_data.get("cost_delta_monthly_usd"),
        "num_resources": len(payload_data.get("resources", [])),
    }, out)

    print("\n=== Payload Preview ===")
    print(json.dumps(payload_data, indent=2))

    # ── 3. Send to API ──
    if args.save_only:
        print(f"\n=== --save-only: skipped API call ===")
        print(f"Files saved to: {out}/")
        return

    print("\n=== 3. Sending to FinOps API ===")
    print(f"  repo:   {payload_data.get('repo')}")
    print(f"  author: {payload_data.get('author')}")
    print(f"  PR:     #{payload_data.get('pr_number')}")
    print(f"  delta:  ${payload_data.get('cost_delta_monthly_usd')}/mo")

    try:
        result = send_to_api(payload_data, args.api_url, api_key)
        save("api-response.json", result, out)
        print(f"\nSUCCESS: {json.dumps(result, indent=2)}")
        print(f"All files: {out}/")
    except httpx.HTTPStatusError as exc:
        print(f"\nAPI error {exc.response.status_code}: {exc.response.text}")
        save("api-error.json", {
            "status": exc.response.status_code,
            "detail": exc.response.text,
        }, out)
        sys.exit(1)
    except httpx.ConnectError:
        print(f"\nCannot connect to {args.api_url}")
        print("Is Docker stack running? Run: docker compose up -d")
        sys.exit(1)


if __name__ == "__main__":
    main()
