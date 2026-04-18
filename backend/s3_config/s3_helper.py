import os
import logging
from pathlib import Path
from typing import BinaryIO
from uuid import uuid4

import boto3
from botocore.exceptions import BotoCoreError, ClientError
from dotenv import load_dotenv
from fastapi import HTTPException, UploadFile


load_dotenv()
logger = logging.getLogger(__name__)

AWS_ACCESS_KEY_ID = os.getenv("AWS_ACCESS_KEY_ID")
AWS_SECRET_ACCESS_KEY = os.getenv("AWS_SECRET_ACCESS_KEY")
AWS_REGION = os.getenv("AWS_REGION")
S3_BUCKET_NAME = os.getenv("S3_BUCKET_NAME")


def _ensure_s3_config() -> None:
    missing_values = [
        key
        for key, value in {
            "AWS_ACCESS_KEY_ID": AWS_ACCESS_KEY_ID,
            "AWS_SECRET_ACCESS_KEY": AWS_SECRET_ACCESS_KEY,
            "AWS_REGION": AWS_REGION,
            "S3_BUCKET_NAME": S3_BUCKET_NAME,
        }.items()
        if not value
    ]
    if missing_values:
        raise RuntimeError(
            "Missing S3 configuration: " + ", ".join(missing_values)
        )


def get_s3_client():
    _ensure_s3_config()
    return boto3.client(
        "s3",
        aws_access_key_id=AWS_ACCESS_KEY_ID,
        aws_secret_access_key=AWS_SECRET_ACCESS_KEY,
        region_name=AWS_REGION,
    )


def build_s3_key(file_name: str, folder: str = "resumes") -> str:
    cleaned_name = Path(file_name).name.strip()
    if not cleaned_name:
        raise HTTPException(status_code=400, detail="File name is required.")

    folder_prefix = folder.strip("/").strip()
    unique_name = f"{uuid4().hex}_{cleaned_name}"
    return f"{folder_prefix}/{unique_name}" if folder_prefix else unique_name


def upload_file_to_s3(
    file: UploadFile | BinaryIO,
    file_name: str | None = None,
    folder: str = "resumes",
    content_type: str | None = None,
) -> dict[str, str]:
    s3_client = get_s3_client()

    resolved_file_name = file_name
    resolved_content_type = content_type

    upload_filename = getattr(file, "filename", None)
    upload_content_type = getattr(file, "content_type", None)
    nested_file_obj = getattr(file, "file", None)

    if nested_file_obj is not None:
        resolved_file_name = resolved_file_name or upload_filename
        resolved_content_type = resolved_content_type or upload_content_type
        file_obj = nested_file_obj
    else:
        file_obj = file

    if not resolved_file_name:
        raise HTTPException(status_code=400, detail="File name is required.")

    s3_key = build_s3_key(resolved_file_name, folder=folder)
    upload_kwargs = {}
    if resolved_content_type:
        upload_kwargs["ExtraArgs"] = {"ContentType": resolved_content_type}

    try:
        if hasattr(file_obj, "seek"):
            file_obj.seek(0)
        s3_client.upload_fileobj(
            file_obj,
            S3_BUCKET_NAME,
            s3_key,
            **upload_kwargs,
        )
    except ClientError as exc:
        error = exc.response.get("Error", {})
        error_code = error.get("Code", "UnknownClientError")
        error_message = error.get("Message", "Unknown S3 client error.")
        logger.exception(
            "S3 upload failed for key %s with code %s: %s",
            s3_key,
            error_code,
            error_message,
        )
        raise HTTPException(
            status_code=500,
            detail=f"S3 upload failed: {error_code}.",
        ) from exc
    except (AttributeError, OSError, BotoCoreError) as exc:
        logger.exception("S3 upload failed for key %s.", s3_key)
        raise HTTPException(
            status_code=500,
            detail=f"S3 upload failed: {exc.__class__.__name__}.",
        ) from exc

    return {
        "bucket": S3_BUCKET_NAME or "",
        "key": s3_key,
        "url": f"https://{S3_BUCKET_NAME}.s3.{AWS_REGION}.amazonaws.com/{s3_key}",
    }


def delete_file_from_s3(s3_key: str) -> None:
    if not s3_key:
        return

    s3_client = get_s3_client()
    try:
        s3_client.delete_object(Bucket=S3_BUCKET_NAME, Key=s3_key)
    except (BotoCoreError, ClientError) as exc:
        logger.exception("S3 delete failed for key %s.", s3_key)
        raise HTTPException(
            status_code=500,
            detail="Failed to delete file from S3.",
        ) from exc
