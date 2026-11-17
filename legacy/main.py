from util import gen_visual
from util import gen_prompt
import streamlit as st
# from PIL import Image
# import os
import time


st.title("Science Visuals")

# User text input
user_prompt = st.text_input("Paste a link to a Scientific Text and Hit Generate")

# Add a generate button
if st.button("Generate"):
    # Check if the user provided input
    if user_prompt.strip():
        # Show spinner while the task runs
        with st.spinner('Wait for it…   (video generation can take up to three minutes)'):
            time.sleep(5)
            try:
                # Call the gen_visual function with the user prompt
                gen_visual_prompt = gen_prompt(user_prompt)
                gen_image, gen_video = gen_visual(gen_visual_prompt)

                # Display the generated video
                if gen_video:
                    video_file_path = "gen_visuald_video.mp4"
                    # Save the video to a file
                    with open(video_file_path, "wb") as video_file:
                        video_file.write(gen_video)

                    # Display the video in the Streamlit app
                    st.video(video_file_path, loop=True, autoplay=True, muted=True)
                else:
                    st.error("Video generation failed. Please try again.")
            except Exception as e:
                st.error(f"An error occurred during generation: {e}")

        # This will only run after the spinner finishes (i.e., after the above code completes)
        st.success("Done!")
    else:
        st.warning("Please enter a prompt before clicking Generate.")