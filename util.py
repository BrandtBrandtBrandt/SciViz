import requests
from dotenv import load_dotenv
import os
import base64
# import random
# from PIL import Image
from io import BytesIO
import json
from griptape.structures import Agent
from griptape.tools import PromptSummaryTool, WebScraperTool

# Load environment variables from .env file
load_dotenv()

# API key from environment variable
BASETEN_API_KEY = os.getenv("BASETEN_KEY")
if not BASETEN_API_KEY:
    raise ValueError("API_KEY not found. Please ensure it's set in the .env file.")

# Replace the empty string with your model id below
model_id = "vq0mjd43"



### PIL IMAGE TO BASE64 ###
def pil_image_to_base64(pil_image):
    buf = BytesIO()
    pil_image.save(buf, format="PNG")
    byte_im = buf.getvalue()
    # Convert to base64 and prepend the data URL scheme
    return "data:image/png;base64," + base64.b64encode(byte_im).decode("utf-8")


def gen_visual(user_prompt):

    values = {
        "prompt": f"{user_prompt}"
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
        output_image = base64.b64decode(image_data)

        # Save image to file
        #with open("SciViz_image.png", 'wb') as img_file:
        #    img_file.write(output)
        #print("Generated image saved as SciViz_image.png")

        # Optionally, open the image (adjust command based on OS)
        # os.system("open SciViz_image.png")  # macOS
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
        output_video = base64.b64decode(video_data)

        # Save video to file
        #with open("SciViz_video.mp4", 'wb') as video_file:
        #    video_file.write(output)
        #print("Generated video saved as SciViz_video.mp4")

        # Optionally, open the video (adjust command based on OS)
        # os.system("open SciViz_video.mp4")  # macOS
        # os.system("start SciViz_video.mp4")  # Windows
        # os.system("xdg-open SciViz_video.mp4")  # Linux
    except KeyError as e:
        print(f"Key error: {e}. Please check the response structure.")
    except Exception as e:
        print(f"An error occurred: {e}")


    return output_image, output_video

### chatGPT prompting API Call ###
def gen_prompt(user_link):


    # import json

    load_dotenv()  # Load environment variables

    # 1) Create an Agent with the web scraping and summarization tools
    agent_scraper = Agent(tools=[
        WebScraperTool(off_prompt=True),
        PromptSummaryTool(off_prompt=False)
    ])

    # 2) Scrape the website and store the output
    scraped_run = agent_scraper.run(
        f"Summarize this article: {user_link}"
    )

    #scraped_run

    #print("Here is the final text:")
    #print(json.dumps(scraped_run))
    #print(dir(scraped_run))

    # print(f"scarped output: {scraped_run.output}")

    scraped_output = scraped_run.output



    # 3) Now create a second Agent for the final prompt
    agent_prompt = Agent()

    # 4) Combine the scraped output with your instructions
    final_input = (
        f"{scraped_output}\n\n"
        "You are a master illustrator. Write a descriptive image prompt for stable diffusion "
        "that effectively illustrates the article above. Focus on the subject of the article as "
        "the main element of the graphic and start the prompt with that. The style of the image "
        "should be: graphic design, swiss style, retro futurism, art deco, bauhaus, modern. "
        "only write the prompt."
    )

    # 5) Run the second agent and print/return the result
    # response = agent_prompt.run(final_input)
    response = agent_prompt.run(final_input)
    # print(response.output)

    generatedResponse = response.output

    return generatedResponse
