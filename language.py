"""Language selection utilities."""
# import streamlit as st
# from localization import get_translation
#
# lang_display = {
#     "en": "🇬🇧 English",
#     "he": "🇮🇱 עברית"
# }
#
# def setup_language_selector():
#     """
#     Initializes and displays a language selector in the sidebar.
#     Forces a rerun if the user changes the language.
#     """
#     if "lang" not in st.session_state:
#         st.session_state.lang = "en"
#
#     prev_lang = st.session_state.lang
#     selected_lang = st.sidebar.selectbox(
#         "🌐 Language", ["en", "he"],
#         index=["en", "he"].index(prev_lang),
#         format_func=lambda x: lang_display[x]
#     )
#
#     if selected_lang != prev_lang:
#         st.session_state.lang = selected_lang
#         st.rerun()
#
# def get_translator():
#     """
#     Returns the translation dictionary for the current language.
#     """
#     return get_translation(st.session_state.get("lang", "en"))




import streamlit as st
from localization import get_translation

lang_display = {
    "en": "🇬🇧 English",
    "he": "🇮🇱 עברית"
}

def setup_language_selector(key: str = "language_selector"):
    """
    Initializes and displays a language selector in the sidebar.
    Forces a rerun if the user changes the language.
    """
    if "lang" not in st.session_state:
        st.session_state.lang = "en"

    prev_lang = st.session_state.lang
    selected_lang = st.sidebar.selectbox(
        "🌐 Language",
        ["en", "he"],
        index=["en", "he"].index(prev_lang),
        format_func=lambda x: lang_display[x],
        key=key
    )

    if selected_lang != prev_lang:
        st.session_state.lang = selected_lang
        st.rerun()

def get_translator():
    """
    Returns the translation dictionary for the current language.
    """
    return get_translation(st.session_state.get("lang", "en"))
