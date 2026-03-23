from __future__ import annotations

import os


def get_env_value(key: str, default: str = "") -> str:
    """Resolve a config value from OS env first, then Streamlit secrets.

    Streamlit Cloud secrets are not always mirrored to os.environ,
    so we check both sources.
    """
    value = os.getenv(key)
    if value is not None and str(value).strip() != "":
        return str(value).strip()

    try:
        import streamlit as st

        if key in st.secrets:
            return str(st.secrets[key]).strip()

        # Support common nested secret structure:
        # [supabase]
        # url = "..."
        # anon_key = "..."
        if key == "SUPABASE_URL" and "supabase" in st.secrets:
            nested = st.secrets["supabase"]
            if isinstance(nested, dict) and "url" in nested:
                return str(nested["url"]).strip()
        if key == "SUPABASE_ANON_KEY" and "supabase" in st.secrets:
            nested = st.secrets["supabase"]
            if isinstance(nested, dict) and "anon_key" in nested:
                return str(nested["anon_key"]).strip()
    except Exception:
        pass

    return str(default).strip()
