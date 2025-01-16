from util import generate
import streamlit as st
from PIL import Image
import os

st.title("Science Visuals")

# User text input
user_prompt = st.text_input("Enter text to generate an image and video:")

# Add a Generate button
if st.button("Generate"):
    # Check if the user provided input
    if user_prompt.strip():
        try:
            # Call the generate function with the user prompt
            gen_image, gen_video = generate(user_prompt)

            # Display the generated image
            if gen_image:
                st.image(gen_image, use_container_width=True, caption="Generated Image")
            else:
                st.error("Image generation failed. Please try again.")

            # Display the generated video
            if gen_video:
                video_file_path = "generated_video.mp4"
                # Save the video to a file
                with open(video_file_path, "wb") as video_file:
                    video_file.write(gen_video)

                # Display the video in the Streamlit app
                st.video(video_file_path)  # Removed the caption argument
            else:
                st.error("Video generation failed. Please try again.")

        except Exception as e:
            st.error(f"An error occurred during generation: {e}")
    else:
        st.warning("Please enter a prompt before clicking Generate.")