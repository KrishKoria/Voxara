import io
import os
import uuid
import modal
from chatterbox.tts import ChatterboxTTS
from pydantic import BaseModel
from typing import Optional
import torch
import torchaudio
app = modal.App("text-to-speech-generator")
image = (
    modal.Image.debian_slim(python_version="3.11").pip_install("numpy>=1.24,<1.26")
    .pip_install_from_requirements("text-to-speech/requirements.txt")
    .apt_install("ffmpeg")
)

class TextToSpeechRequest(BaseModel):
    text: str
    voice_S3_Key: Optional[str] = None
class TextToSpeechResponse(BaseModel):
    s3_key: str

volume = modal.Volume.from_name("huggingface-cache-chatterbox", create_if_missing=True)
s3_secrets = modal.Secret.from_name("Voxara-AWS")


@app.cls(image=image, secrets=[s3_secrets],gpu="L40S", volumes={
    "/root/.cache/huggingface": volume,
    "/s3-mount": modal.CloudBucketMount("voxara", bucket_endpoint_url="https://t3.storage.dev", secret=s3_secrets)
}, scaledown_window=120)
class TextToSpeechServer:
    @modal.enter()
    def load_model(self):
        self.model = ChatterboxTTS.from_pretrained(device="cuda")

    @modal.fastapi_endpoint(method="POST", requires_proxy_auth=True)
    def generate_speech(self, req: TextToSpeechRequest) -> TextToSpeechResponse:
        with torch.no_grad():
            if req.voice_S3_Key:
                audio_path = f"/s3-mount/{req.voice_S3_Key}"
                if not os.path.exists(audio_path):
                    raise FileNotFoundError(f"Voice file not found at {audio_path}")
                output = self.model.generate(req.text, audio_prompt_path=audio_path)
            else:
                output = self.model.generate(req.text)
            output_cpu = output.cpu()
        
        buffer = io.BytesIO()
        torchaudio.save(buffer, output_cpu, self.model.sr, format="wav")
        buffer.seek(0)
        audio_bytes = buffer.read()
        audio_uuid = str(uuid.uuid4())
        s3_key = f"tts/{audio_uuid}.wav"
        s3_path = f"/s3-mount/{s3_key}"
        os.makedirs(os.path.dirname(s3_path), exist_ok=True)
        with open(s3_path, "wb") as f:
            f.write(audio_bytes)
        return TextToSpeechResponse(s3_key=s3_key)
    

@app.local_entrypoint()
def main():
    import requests
    server = TextToSpeechServer()
    endpoint_url = server.generate_speech.get_web_url()

    request = TextToSpeechRequest(
        text="Hello, this is a test of the text to speech system.",
        voice_S3_Key="samples/voices/test.wav"
    )
    payload = request.model_dump()
    headers = {
            "Modal-Key": "wk-c6cs7SvJNkuG4Voag7DcEO",
            "Modal-Secret": "ws-2dfjKcFo8pDWdgZJ4FoWf1"
    }
    response = requests.post(endpoint_url, json=payload, headers=headers)
    response.raise_for_status()
    results = TextToSpeechResponse(**response.json())
    print("Generated audio S3 key:", results.s3_key)
