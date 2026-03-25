"""
ui.styles — paquete de estilos CSS. Concatena sub-módulos y exporta CSS_STYLES.
"""
from ui.styles.base import BASE_CSS
from ui.styles.sidebar import SIDEBAR_CSS
from ui.styles.cards import CARDS_CSS
from ui.styles.tables import TABLES_CSS
from ui.styles.charts import CHARTS_CSS
from ui.styles.misc import MISC_CSS

CSS_STYLES = "<style>" + BASE_CSS + SIDEBAR_CSS + CARDS_CSS + CHARTS_CSS + TABLES_CSS + MISC_CSS + "</style>"

__all__ = ["CSS_STYLES"]
