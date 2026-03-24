from __future__ import annotations

import os
from collections.abc import Mapping


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
        if key in {"SUPABASE_URL", "SUPABASE_ANON_KEY"} and "supabase" in st.secrets:
            nested = st.secrets["supabase"]
            if isinstance(nested, Mapping):
                if key == "SUPABASE_URL":
                    for candidate in ("url", "SUPABASE_URL"):
                        if candidate in nested and str(nested[candidate]).strip():
                            return str(nested[candidate]).strip()
                if key == "SUPABASE_ANON_KEY":
                    for candidate in ("anon_key", "SUPABASE_ANON_KEY"):
                        if candidate in nested and str(nested[candidate]).strip():
                            return str(nested[candidate]).strip()
    except Exception:
        pass

    return str(default).strip()
