import os
import subprocess
import uuid
import modal
from pydantic import BaseModel
app = modal.App("file-to-s3")

image = (
    modal.Image.debian_slim(python_version="3.11")
    .apt_install("curl")
    .pip_install_from_requirements("file-to-s3/requirements.txt")
)

class FileImportRequest(BaseModel):
    video_url: str

class FileImportResponse(BaseModel):
    s3_key: str

s3_secrets = modal.Secret.from_name("Voxara-AWS")


@app.cls(image=image, secrets=[s3_secrets], volumes={
    "/s3-mount": modal.CloudBucketMount("voxara", bucket_endpoint_url="https://t3.storage.dev", secret=s3_secrets)
}, timeout=600)
class FileImportServer:
    @modal.fastapi_endpoint(method="POST", requires_proxy_auth=True)
    def import_video(self, req: FileImportRequest) -> FileImportResponse:
        video_uuid = str(uuid.uuid4())
        s3_key = f"fal/{video_uuid}.mp4"
        s3_path = f"/s3-mount/{s3_key}"
        os.makedirs(os.path.dirname(s3_path), exist_ok=True)
        try:
            curl_cmd = ["curl", "-L", "--fail", "--proto-default", "https", "--retry", "3", "--retry-delay", "2", req.video_url, "-o", s3_path]
            subprocess.run(curl_cmd, check=True)
        except Exception:
            if os.path.exists(s3_path):
                os.remove(s3_path)
            raise

        return FileImportResponse(s3_key=s3_key)
    

@app.local_entrypoint()
def main():
    import requests
    test = "https://public-voxara.t3.storage.dev/samples/voices/2.wav"
    server = FileImportServer()
    endpoint_url = server.import_video.get_web_url()

    request = FileImportRequest(
        video_url=test
    )
    payload = request.model_dump()
    headers = {
            "Modal-Key": "wk-c6cs7SvJNkuG4Voag7DcEO",
            "Modal-Secret": "ws-2dfjKcFo8pDWdgZJ4FoWf1"
    }
    response = requests.post(endpoint_url, json=payload, headers=headers)
    response.raise_for_status()
    results = FileImportResponse(**response.json())
    print("Generated video S3 key:", results.s3_key)
