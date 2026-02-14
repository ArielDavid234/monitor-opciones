"""Temp script to fix header in app_web.py"""
with open('app_web.py', 'r', encoding='utf-8') as f:
    lines = f.readlines()

# Find ENCABEZADO PRINCIPAL and TABS PRINCIPALES
start_idx = None
end_idx = None
for i, line in enumerate(lines):
    if 'ENCABEZADO PRINCIPAL' in line and start_idx is None:
        start_idx = i - 1  # include the comment bar above
    if 'TABS PRINCIPALES' in line and start_idx is not None:
        end_idx = i + 1  # include the comment bar below
        break

print(f"Replacing lines {start_idx+1} to {end_idx+1}")

new_block = [
    "# ============================================================================\n",
    "#                    ENCABEZADO PRINCIPAL\n",
    "# ============================================================================\n",
    "# Header superior: search + upgrade\n",
    "col_search, col_upgrade = st.columns([5, 1])\n",
    "with col_search:\n",
    '    _search_query = st.text_input("\U0001f50d Search...", placeholder="Buscar ticker, contrato, strike...", label_visibility="collapsed")\n',
    "with col_upgrade:\n",
    '    st.button("Upgrade \U0001f48e", type="primary", use_container_width=True)\n',
    "\n",
    "st.markdown(\n",
    '    f"""\n',
    '    <div class="scanner-header">\n',
    '        <h1>\U0001f451 OPTIONS<span style="color: #00ff88;">KING</span> Analytics</h1>\n',
    '        <p class="subtitle">\n',
    '            Esc\u00e1ner institucional de actividad inusual en opciones \u2014 <b style="color: #00ff88;">{ticker_symbol}</b>\n',
    "        </p>\n",
    '        <span class="badge">\u25cf LIVE \u2022 Anti-Ban \u2022 An\u00e1lisis Avanzado</span>\n',
    "    </div>\n",
    '    """,\n',
    "    unsafe_allow_html=True,\n",
    ")\n",
    "\n",
    "# ============================================================================\n",
    "#                    TABS PRINCIPALES\n",
    "# ============================================================================\n",
]

lines[start_idx:end_idx+1] = new_block

with open('app_web.py', 'w', encoding='utf-8') as f:
    f.writelines(lines)

print("OK - header replaced successfully")
