import streamlit as st
import utils as ut

# load default style settings
ut.default_style()

# sidebar menu
ut.create_menu()

# home
st.image('images/Logo_Eyetism.png', use_column_width="auto")
