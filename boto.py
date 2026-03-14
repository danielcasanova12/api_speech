import boto3

# CONFIG
BUCKET_NAME = "ermis-datasets"
LOCAL_FILE = "audio_test.wav"
S3_KEY = "akcit_datasets/test_audio.wav"

def upload_to_s3():
    try:
        s3 = boto3.client("s3")

        s3.upload_file(
            LOCAL_FILE,
            BUCKET_NAME,
            S3_KEY
        )

        print("✅ Upload realizado com sucesso!")
        print(f"S3 Path: s3://{BUCKET_NAME}/{S3_KEY}")

    except Exception as e:
        print("❌ Erro no upload:")
        print(e)


if __name__ == "__main__":
    upload_to_s3()
