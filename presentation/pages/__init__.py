# -*- coding: utf-8 -*-
"""presentation/pages — thin Streamlit page wrappers.

Each page in this package must:
  1. Accept a service/context object (not raw session_state)
  2. Call services for any data/business logic
  3. Only contain rendering logic (st.* calls)
"""
