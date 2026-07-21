import argparse
import logging
from pathlib import Path

import boto3

from config import settings

logger = logging.getLogger(__name__)


def _s3_client():
    client_kwargs = {"region_name": settings.AWS_REGION}
    if (
        settings.AWS_ACCESS_KEY_ID
        and settings.AWS_SECRET_ACCESS_KEY
        and not settings.AWS_ACCESS_KEY_ID.startswith("your_")
        and not settings.AWS_SECRET_ACCESS_KEY.startswith("your_")
    ):
        client_kwargs.update(
            aws_access_key_id=settings.AWS_ACCESS_KEY_ID,
            aws_secret_access_key=settings.AWS_SECRET_ACCESS_KEY,
        )
    return boto3.client("s3", **client_kwargs)


def upload_to_s3(local_file: Path, s3_key: str, bucket_name: str) -> str:
    """Upload one file and propagate any failure to the caller."""
    if not local_file.is_file():
        raise FileNotFoundError(f"Arquivo local não encontrado: {local_file}")
    if not s3_key.strip():
        raise ValueError("A chave S3 não pode ser vazia")
    if not bucket_name.strip():
        raise ValueError("O nome do bucket não pode ser vazio")

    _s3_client().upload_file(str(local_file), bucket_name, s3_key)
    return f"s3://{bucket_name}/{s3_key}"


def main() -> int:
    parser = argparse.ArgumentParser(description="Enviar um arquivo local para o S3.")
    parser.add_argument("local_file", type=Path, help="Arquivo local a enviar")
    parser.add_argument("s3_key", help="Chave de destino no S3")
    parser.add_argument(
        "--bucket",
        default=settings.S3_BUCKET_NAME,
        help="Bucket de destino (padrão: configuração S3_BUCKET_NAME)",
    )
    args = parser.parse_args()

    try:
        destination = upload_to_s3(args.local_file, args.s3_key, args.bucket)
    except Exception:
        logger.exception("Falha no upload para o bucket %s", args.bucket)
        return 1

    logger.info("Upload concluído: %s", destination)
    return 0


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")
    raise SystemExit(main())
