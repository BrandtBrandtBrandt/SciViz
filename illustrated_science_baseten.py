import requests
from dotenv import load_dotenv
import os
import base64
import json

# Load environment variables from .env file
load_dotenv()

# API key from environment variable
BASETEN_API_KEY = os.getenv("BASETEN_KEY")
if not BASETEN_API_KEY:
    raise ValueError("API_KEY not found. Please ensure it's set in the .env file.")

# Replace the empty string with your model id below
model_id = "vq0mjd43"

values = {
    "prompt": "a cuddly dragon above a forrest, spewing flowers"
}

# Call model endpoint
res = requests.post(
    f"https://model-{model_id}.api.baseten.co/production/predict",
    headers={"Authorization": f"Api-Key {BASETEN_API_KEY}"},
    json={"workflow_values": values},
)

res = res.json()
# print("Full API Response:", res)  # Inspect the response

# Save the full API response to a text file
try:
    with open("api_response.txt", "w") as f:
        json.dump(res, f, indent=4)  # Pretty-print with indentation
    print("Full API response saved to api_response.txt")
except Exception as e:
    print(f"Failed to save API response to file: {e}")

# Processing image
try:
    preamble = "data:image/png;base64,"
    # Adjust the index based on the actual response structure
    image_data = res["result"][0]["data"].replace(preamble, "")
    output = base64.b64decode(image_data)

    # Save image to file
    with open("SciViz_image.png", 'wb') as img_file:
        img_file.write(output)
    print("Generated image saved as SciViz_image.png")

    # Optionally, open the image (adjust command based on OS)
    os.system("open SciViz_image.png")  # macOS
    # os.system("start SciViz_image.png")  # Windows
    # os.system("xdg-open SciViz_image.png")  # Linux
except KeyError as e:
    print(f"Key error: {e}. Please check the response structure.")
except Exception as e:
    print(f"An error occurred: {e}")

# Processing video
try:
    preamble = "data:video/mp4;base64,"
    # Adjust the key path based on the actual response structure
    for count, item in enumerate(res.get("result", [])):
        if item.get("format") == "mp4":
            video_object = count
            break

    video_data = res["result"][video_object]["data"].replace(preamble, "")
    output = base64.b64decode(video_data)

    # Save video to file
    with open("SciViz_video.mp4", 'wb') as video_file:
        video_file.write(output)
    print("Generated video saved as SciViz_video.mp4")

    # Optionally, open the video (adjust command based on OS)
    os.system("open SciViz_video.mp4")  # macOS
    # os.system("start SciViz_video.mp4")  # Windows
    # os.system("xdg-open SciViz_video.mp4")  # Linux
except KeyError as e:
    print(f"Key error: {e}. Please check the response structure.")
except Exception as e:
    print(f"An error occurred: {e}")