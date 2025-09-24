import glob
import os
import shutil
import subprocess
import tempfile
import uuid
import modal
from pydantic import BaseModel
app = modal.App("hallo3-portrait-avatar")

volume = modal.Volume.from_name("hallo3-cache", create_if_missing=True)

volumes = {
    "/models": volume,
}

def download_model():
    from huggingface_hub import snapshot_download
    snapshot_download("fudan-generative-ai/hallo3", local_dir="/models/pretrained_models", ignore_patterns=[])

image = (
    modal.Image.from_registry("nvidia/cuda:12.1.1-devel-ubuntu20.04", add_python="3.10")
    .env({"DEBIAN_FRONTEND": "noninteractive"})
    .apt_install(["git", "ffmpeg", "clang", "libaio-dev"])
    .pip_install_from_requirements("photo-to-video/requirements.txt")
    .run_commands("git clone https://github.com/fudan-generative-vision/hallo3 /hallo3")
    .run_commands("ln -s /models/pretrained_models /hallo3/pretrained_models")
    .run_function(download_model, volumes=volumes) # type: ignore
)

class PortraitAvatarRequest(BaseModel):
    transcript: str
    photo_S3_Key: str 
    audio_S3_Key: str

class PortraitAvatarResponse(BaseModel):
    video_s3_key: str


s3_secrets = modal.Secret.from_name("Voxara-AWS")


@app.cls(image=image, secrets=[s3_secrets],gpu="A100-80GB", volumes={
    **volumes,
    "/s3-mount": modal.CloudBucketMount("voxara", bucket_endpoint_url="https://t3.storage.dev", secret=s3_secrets)
}, timeout=2700)

class PortraitAvatarServer:
    @modal.fastapi_endpoint(method="POST", requires_proxy_auth=True)
    def generate_video(self, req: PortraitAvatarRequest) -> PortraitAvatarResponse:
    
        temp_dir = tempfile.mkdtemp()
        try: 
            photo_path = f"/s3-mount/{req.photo_S3_Key}" 
            audio_path = f"/s3-mount/{req.audio_S3_Key}"
            if not os.path.exists(photo_path):
                raise FileNotFoundError(f"Photo S3 key not found: {req.photo_S3_Key}")
            if not os.path.exists(audio_path):
                raise FileNotFoundError(f"Audio S3 key not found: {req.audio_S3_Key}")
            
            input_txt_path = os.path.join(temp_dir, "input.txt")
            with open(input_txt_path, "w") as f:
                f.write(f"{req.transcript}@@{photo_path}@@{audio_path}\n")
            
            output_dir = os.path.join(temp_dir, "output")
            os.makedirs(output_dir, exist_ok=True)

            cmd = [
                "bash", "/hallo3/scripts/inference_long_batch.sh", input_txt_path, output_dir
            ]
            
            subprocess.run(cmd, check=True, cwd="/hallo3")

            generated_file = None
            for fpath in glob.glob(os.path.join(output_dir, "**", "*.mp4"), recursive=True):
                generated_file = fpath
                break
            
            if generated_file is None:
                raise RuntimeError("No video file generated.")
            
            final_video_path = os.path.join(temp_dir, "final_output.mp4")
            ffmpeg_cmd = [
                "ffmpeg", "-i", generated_file, "-i", audio_path, "-c:v",
                "copy", "-c:a", "aac", "-shortest", final_video_path
            ]
            subprocess.run(ffmpeg_cmd, check=True)

            video_uuid = str(uuid.uuid4())
            s3_key = f"ptv/{video_uuid}.mp4"
            s3_path = f"/s3-mount/{s3_key}"
            os.makedirs(os.path.dirname(s3_path), exist_ok=True)
            shutil.copy(final_video_path, s3_path)
            return PortraitAvatarResponse(video_s3_key=s3_key)
        
        finally:
            if os.path.exists(temp_dir):
                shutil.rmtree(temp_dir)
    

@app.local_entrypoint()
def main():
    import requests
    server = PortraitAvatarServer()
    endpoint_url = server.generate_video.get_web_url()

    request = PortraitAvatarRequest(
        transcript="Hello, this is a test of the portrait avatar generation system.",
        photo_S3_Key="samples/photos/0018.jpg",
        audio_S3_Key="samples/voices/test.wav"
    )
    payload = request.model_dump()
    headers = {
            "Modal-Key": "wk-c6cs7SvJNkuG4Voag7DcEO",
            "Modal-Secret": "ws-2dfjKcFo8pDWdgZJ4FoWf1"
    }
    response = requests.post(endpoint_url, json=payload, headers=headers)
    response.raise_for_status()
    results = PortraitAvatarResponse(**response.json())
    print("Generated video S3 key:", results.video_s3_key)
