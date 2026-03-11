import os
import time
import requests

API_KEY = os.environ["ECOM_IMAGE_AGENT_NVIDIA_API_KEY"]
url = "https://integrate.api.nvidia.com/v1/chat/completions"

payload = {
    "model": "z-ai/glm5",
    "messages": [{"role": "user", "content": "reply only: ok"}],
    "temperature": 0.0,
    "max_tokens": 8,
    "stream": False,
}

s = requests.Session()
s.trust_env = False

t0 = time.time()
try:
    r = s.post(
        url,
        headers={
            "Authorization": f"Bearer {API_KEY}",
            "Content-Type": "application/json",
            "Accept": "application/json",
        },
        json=payload,
        timeout=(10, 120),
    )
    t1 = time.time()
    print("elapsed:", round(t1 - t0, 2), "sec")
    print("status:", r.status_code)
    print(r.text[:1000])
except Exception as e:
    t1 = time.time()
    print("elapsed before error:", round(t1 - t0, 2), "sec")
    raise