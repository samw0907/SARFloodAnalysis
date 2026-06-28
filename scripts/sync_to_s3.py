"""
scripts/sync_to_s3.py
Sync pipeline outputs for all three case studies to S3.

Uploads:
  outputs/figures/*.png       → s3://{bucket}/{prefix}/figures/
  data/validation/*.json      → s3://{bucket}/{prefix}/validation/
  data/vectors/*.geojson      → s3://{bucket}/{prefix}/vectors/

Credentials: loaded from {case_study}/config/.env (CDSE_USER etc. ignored;
only AWS_ACCESS_KEY_ID / AWS_SECRET_ACCESS_KEY / AWS_DEFAULT_REGION are used).
Falls back to environment variables / ~/.aws/credentials if .env is absent.

Run from the SARFloodAnalysis root:
    python scripts/sync_to_s3.py
"""

import os
import sys
import yaml
import boto3
from pathlib import Path
from dotenv import load_dotenv

CASE_STUDIES = ["emilia_romagna", "wroclaw", "jacobabad"]

SYNC_TARGETS = [
    ("outputs/figures", "figures", "image/png"),
    ("data/validation", "validation", "application/json"),
    ("data/vectors", "vectors", "application/geo+json"),
]


def load_config(case_study: str) -> dict:
    config_path = Path(case_study) / "config" / "pipeline_config.yaml"
    with open(config_path) as f:
        return yaml.safe_load(f)


def make_s3_client(region: str):
    return boto3.client(
        "s3",
        region_name=region,
        aws_access_key_id=os.environ.get("AWS_ACCESS_KEY_ID"),
        aws_secret_access_key=os.environ.get("AWS_SECRET_ACCESS_KEY"),
    )


def sync_case_study(case_study: str, s3, dry_run: bool = False) -> int:
    env_path = Path(case_study) / "config" / ".env"
    if env_path.exists():
        load_dotenv(env_path, override=False)

    cfg = load_config(case_study)
    bucket = cfg["aws"]["bucket"]
    prefix = cfg["aws"]["prefix"]
    region = cfg["aws"]["region"]

    uploaded = 0
    for local_subdir, s3_subdir, content_type in SYNC_TARGETS:
        local_dir = Path(case_study) / local_subdir
        if not local_dir.exists():
            continue

        files = list(local_dir.iterdir())
        if not files:
            continue

        for fpath in sorted(files):
            if not fpath.is_file():
                continue
            s3_key = f"{prefix}/{s3_subdir}/{fpath.name}"
            print(f"  {'[dry-run] ' if dry_run else ''}s3://{bucket}/{s3_key}")
            if not dry_run:
                s3.upload_file(
                    str(fpath), bucket, s3_key,
                    ExtraArgs={"ContentType": content_type},
                )
            uploaded += 1

    return uploaded


def main():
    dry_run = "--dry-run" in sys.argv

    if dry_run:
        print("DRY RUN — no files will be uploaded\n")

    # Load credentials from first available .env (all three share the same AWS keys)
    for cs in CASE_STUDIES:
        env_path = Path(cs) / "config" / ".env"
        if env_path.exists():
            load_dotenv(env_path, override=False)
            break

    region = os.environ.get("AWS_DEFAULT_REGION", "eu-north-1")
    s3 = make_s3_client(region)

    total = 0
    for case_study in CASE_STUDIES:
        print(f"\n=== {case_study} ===")
        n = sync_case_study(case_study, s3, dry_run=dry_run)
        print(f"  {n} file(s) {'would be ' if dry_run else ''}uploaded")
        total += n

    print(f"\nDone — {total} file(s) total")


if __name__ == "__main__":
    main()
