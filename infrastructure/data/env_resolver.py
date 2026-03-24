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
        if key in {"SUPABASE_URL", "SUPABASE_ANON_KEY"}:
            for section_name in ("supabase", "SUPABASE"):
                if section_name not in st.secrets:
                    continue
                nested = st.secrets[section_name]
                if key == "SUPABASE_URL":
                    for candidate in ("url", "SUPABASE_URL"):
                        try:
                            value = nested[candidate]  # type: ignore[index]
                        except Exception:
                            value = getattr(nested, candidate, "")
                        if str(value).strip():
                            return str(value).strip()
                if key == "SUPABASE_ANON_KEY":
                    for candidate in ("anon_key", "SUPABASE_ANON_KEY"):
                        try:
                            value = nested[candidate]  # type: ignore[index]
                        except Exception:
                            value = getattr(nested, candidate, "")
                        if str(value).strip():
                            return str(value).strip()
    except Exception:
        pass

    return str(default).strip()
