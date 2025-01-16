from util import generate
import streamlit as st
from PIL import Image

st.title("Logo lake")

# upload file
file = st.file_uploader('', type=['jpeg', 'jpg', 'png'])

# display image
if file is not None:
    user_image = Image.open(file).convert('RGB')
    # st.image(image, use_column_width=True)

    # generate image
    gen_image = generate(user_image)

    # display image
    st.image(gen_image, use_container_width=True, caption="Generated Image")

