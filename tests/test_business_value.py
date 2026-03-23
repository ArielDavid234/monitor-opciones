import unittest

from infrastructure.platform.business_value import (
    PLAN_FREE,
    PLAN_PRO,
    aggregate_business_metrics,
    assign_ab_variant,
    check_watchlist_limit,
    evaluate_ab_experiment,
    get_plan_policy,
    has_feature_access,
    is_feature_enabled_for_user,
)


class TestBusinessValue(unittest.TestCase):
    def test_plan_policies_and_features(self):
        free = get_plan_policy(PLAN_FREE)
        pro = get_plan_policy(PLAN_PRO)

        self.assertGreater(pro.scans_per_day, free.scans_per_day)
        self.assertTrue(has_feature_access("pro", "stress_tests"))
        self.assertFalse(has_feature_access("free", "stress_tests"))

    def test_watchlist_limit_enforced(self):
        blocked = check_watchlist_limit("free", current_watchlist_size=12)
        self.assertFalse(blocked["allowed"])

        allowed = check_watchlist_limit("pro", current_watchlist_size=12)
        self.assertTrue(allowed["allowed"])

    def test_ab_assignment_is_stable(self):
        v1 = assign_ab_variant("user-1", "upgrade_prompt_copy_v1")
        v2 = assign_ab_variant("user-1", "upgrade_prompt_copy_v1")
        self.assertEqual(v1, v2)
        self.assertIn(v1, {"A", "B"})

    def test_ab_significance_and_recommendation(self):
        rows = []
        rows.extend({"experiment": "upgrade_prompt_copy_v1", "variant": "A", "converted": False} for _ in range(80))
        rows.extend({"experiment": "upgrade_prompt_copy_v1", "variant": "A", "converted": True} for _ in range(20))
        rows.extend({"experiment": "upgrade_prompt_copy_v1", "variant": "B", "converted": False} for _ in range(60))
        rows.extend({"experiment": "upgrade_prompt_copy_v1", "variant": "B", "converted": True} for _ in range(40))

        out = evaluate_ab_experiment(rows, "upgrade_prompt_copy_v1")
        self.assertEqual(out["winner"], "B")
        self.assertLess(out["p_value"], 0.05)

    def test_feature_rollout_gate(self):
        self.assertFalse(is_feature_enabled_for_user(feature_name="smart_alerts", plan="free", user_id="u-free", cohort=0))
        self.assertTrue(is_feature_enabled_for_user(feature_name="advanced_score", plan="pro", user_id="u-pro", cohort=0))

    def test_aggregate_business_contains_executive_dashboard(self):
        class _FakeAuth:
            def fetch_all_profiles(self):
                return [{"id": "u1", "role": "pro"}]

            def load_user_data(self, user_id, key):
                if key == "business_usage_daily":
                    return {
                        "2099-01-01": {
                            "estimated_cost_usd": 1.2,
                            "revenue_estimate_usd": 4.0,
                            "scans": 3,
                            "cache_hits": 20,
                            "cache_misses": 5,
                        }
                    }
                if key == "intelligence_daily":
                    return {
                        "2099-01-01": {
                            "rows_seen": 10,
                            "high_score_rows": 4,
                            "avg_score_acc": 220.0,
                            "scans": 3,
                            "risk_conservadora": 3,
                            "risk_balanceada": 5,
                            "risk_agresiva": 2,
                            "decision_time_seconds_sum": 40,
                            "decision_events": 2,
                        }
                    }
                if key == "product_events":
                    return [
                        {"ts": "2099-01-01T10:00:00+00:00", "event": "user_scan_started", "metadata": {}},
                        {"ts": "2099-01-01T10:00:10+00:00", "event": "user_scan_completed", "metadata": {}},
                    ]
                if key == "ab_conversions":
                    return []
                if key == "ab_assignments":
                    return {}
                return {}

            def save_user_data(self, user_id, key, value):
                return None

        out = aggregate_business_metrics(_FakeAuth(), lookback_days=7)
        self.assertIn("executive_dashboard", out)
        exec_dash = out["executive_dashboard"]
        self.assertIn("dau", exec_dash)
        self.assertIn("high_score_rate", exec_dash)
        self.assertIn("conversion_by_plan", exec_dash)


if __name__ == "__main__":
    unittest.main()
