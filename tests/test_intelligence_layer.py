import unittest

import pandas as pd

from core.credit_spread_scanner import generate_alerts
from core.intelligence_layer import (
    classify_risk_profile,
    compute_unified_score,
    enrich_scanner_dataframe,
    filter_smart_alerts,
)


class TestIntelligenceLayer(unittest.TestCase):
    def test_unified_score_stable_with_missing_data(self):
        row = {
            "Ticker": "SPY",
            "Tipo": "Bull Put",
            "Crédito": 0.55,
            "DTE": 32,
        }
        score, components, profile, explain = compute_unified_score(row)
        self.assertGreaterEqual(score, 0.0)
        self.assertLessEqual(score, 100.0)
        self.assertEqual(set(components.keys()), {"liquidity", "bid_ask", "relative_iv", "oi_volume", "strike_distance", "estimated_risk"})
        self.assertIn(profile, {"Conservadora", "Balanceada", "Agresiva"})
        self.assertIn("summary", explain)

    def test_risk_profile_classification_consistency(self):
        conservative = {
            "POP %": 82,
            "Delta Vendido": 0.14,
            "DTE": 35,
            "Crédito": 0.45,
            "Strike Vendido": 430,
            "Strike Comprado": 425,
        }
        aggressive = {
            "POP %": 60,
            "Delta Vendido": 0.24,
            "DTE": 15,
            "Crédito": 1.25,
            "Strike Vendido": 430,
            "Strike Comprado": 428,
        }
        self.assertEqual(classify_risk_profile(conservative), "Conservadora")
        self.assertEqual(classify_risk_profile(aggressive), "Agresiva")

    def test_enrich_dataframe_non_regression_contract(self):
        base = pd.DataFrame(
            [
                {
                    "Ticker": "SPY",
                    "Tipo": "Bull Put",
                    "Score Final": 74.5,
                    "Score Oportunidad": 78,
                    "Crédito": 0.65,
                    "Riesgo Máx": 2.35,
                    "DTE": 30,
                    "Dist Strike %": 4.8,
                    "IV Rank": 48,
                    "Volumen": 340,
                    "OI": 1200,
                    "Bid-Ask": 0.09,
                    "Delta Vendido": 0.16,
                }
            ]
        )
        out = enrich_scanner_dataframe(base)
        self.assertEqual(len(out), len(base))
        for required in ["Ticker", "Tipo", "Score Final", "Score Oportunidad"]:
            self.assertIn(required, out.columns)
        for added in ["Score Unificado", "Perfil Riesgo", "Explicacion Ejecutiva", "Senales Positivas", "Senales Negativas", "Riesgos Clave"]:
            self.assertIn(added, out.columns)

    def test_generate_alerts_scanner_non_breakage(self):
        df = pd.DataFrame(
            [
                {
                    "Ticker": "SPY",
                    "Spot": 530,
                    "Tipo": "Bull Put",
                    "Strike Vendido": 520,
                    "Strike Comprado": 515,
                    "DTE": 32,
                    "Delta Vendido": 0.15,
                    "Tendencia": "Alcista",
                    "Crédito": 0.70,
                    "Riesgo Máx": 4.30,
                    "Dist Strike %": 4.5,
                    "OI": 1500,
                    "Volumen": 420,
                    "Bid-Ask": 0.08,
                    "IV Rank": 45,
                    "Score Oportunidad": 82,
                    "Score Unificado": 88,
                }
            ]
        )
        alerts = generate_alerts(
            df,
            account_size=25000,
            strict_rules={
                "r1_whitelist": False,
                "r2_iv_rank": False,
                "r3_dte": False,
                "r4_delta": False,
                "r5_trend": False,
                "r6_width": False,
                "r7_credit_pct": False,
                "r8_distance": False,
                "r9_liquidity": False,
            },
        )
        self.assertFalse(alerts.empty)
        self.assertIn("Score Unificado", alerts.columns)

    def test_smart_alert_preferences(self):
        df = pd.DataFrame(
            [
                {"Ticker": "SPY", "Score Unificado": 86, "DTE": 34, "Crédito": 0.8, "Bid-Ask": 0.09},
                {"Ticker": "QQQ", "Score Unificado": 62, "DTE": 40, "Crédito": 0.6, "Bid-Ask": 0.11},
            ]
        )
        out = filter_smart_alerts(
            df,
            preferences={"min_score": 75, "dte_min": 21, "dte_max": 50, "max_spread": 0.1, "min_premium": 0.5},
        )
        self.assertEqual(len(out), 1)
        self.assertEqual(out.iloc[0]["Ticker"], "SPY")


if __name__ == "__main__":
    unittest.main()
