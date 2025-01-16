import requests
from dotenv import load_dotenv
import os
import base64
import random
from PIL import Image
from io import BytesIO

# Load environment variables from .env file
load_dotenv()

# API key from environment variable
BASETEN_API_KEY = os.getenv("SD_LIGHTNING_API")
if not BASETEN_API_KEY:
    raise ValueError("API_KEY not found. Please ensure it's set in the .env file.")

# Replace the empty string with your model id below
model_id = "5qe60523"



### PIL IMAGE TO BASE64 ###
def pil_image_to_base64(pil_image):
    buf = BytesIO()
    pil_image.save(buf, format="PNG")
    byte_im = buf.getvalue()
    # Convert to base64 and prepend the data URL scheme
    return "data:image/png;base64," + base64.b64encode(byte_im).decode("utf-8")


def generate(user_image):

    # user image to base64
    base64_str = pil_image_to_base64(user_image)

    values = {
  "positive_prompt": "A forrest seen from above, with a lake in the center, 4k",
  "negative_prompt": "blurry, text, low quality",
  "controlnet_image": "https://drive.google.com/uc?export=download&id=1P1OmivWs7KyU8yUAbrZ8oM9TxEj3DpxB",
  #"controlnet_image": base64_str,
  "seed": random.randint(1, 1000000)
    }
    
    #Call model endpoint
    res = requests.post(
        f"https://model-{model_id}.api.baseten.co/production/predict",
        headers={"Authorization": f"Api-Key {BASETEN_API_KEY}"},
        json={"workflow_values": values},
    )

    res = res.json()
    preamble = "data:image/png;base64,"
    output = base64.b64decode(res["result"][1]["data"].replace(preamble, ""))



    # 1) Get the base64 string by removing the preamble
    base64_str = res["result"][1]["data"].replace(preamble, "")

    # 2) Decode once into bytes
    img_bytes = base64.b64decode(base64_str)

    # 3) Convert those bytes into a PIL image
    generated_img = Image.open(BytesIO(img_bytes)).convert("RGB")

    return generated_img