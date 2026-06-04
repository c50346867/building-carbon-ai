# -*- coding: utf-8 -*-
"""
建筑碳管理平台 — 单元测试
"""

import sys
import os
import json
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from backend.core.carbon_calculator import (
    CarbonCalculator, EmissionSource, EmissionScope, CarbonReport,
)
from backend.core.emission_predictor import (
    EmissionPredictor, HistoricalRecord, ForecastResult,
)
from backend.core.reduction_optimizer import (
    ReductionOptimizer, ReductionMeasure, MeasureCategory, OptimizationResult,
)
from backend.core.simulator import (
    BuildingSimulator, BuildingProfile, SimulatedDataPoint,
)


class TestCarbonCalculator(unittest.TestCase):
    """碳排放计算器测试"""

    def setUp(self):
        self.calc = CarbonCalculator()

    def test_quick_estimate_returns_report(self):
        report = self.calc.quick_estimate(
            electricity_kwh=100000,
            natural_gas_m3=10000,
            floor_area_m2=10000,
            region="华东",
        )
        self.assertIsInstance(report, CarbonReport)
        self.assertGreater(report.grand_total_kg, 0)
        self.assertGreater(report.intensity_kgco2e_per_m2, 0)

    def test_scope_breakdown(self):
        report = self.calc.quick_estimate(
            electricity_kwh=100000,
            natural_gas_m3=10000,
            diesel_kg=2000,
            water_m3=1500,
            floor_area_m2=8000,
            region="华北",
        )
        self.assertGreater(report.scope_1_total, 0)
        self.assertGreater(report.scope_2_total, 0)
        self.assertGreater(report.scope_3_total, 0)
        self.assertAlmostEqual(
            report.grand_total_kg,
            report.scope_1_total + report.scope_2_total + report.scope_3_total,
        )

    def test_zero_inputs(self):
        report = self.calc.quick_estimate()
        self.assertAlmostEqual(report.grand_total_kg, 0.0)

    def test_intensity_zero_area(self):
        report = self.calc.quick_estimate(
            electricity_kwh=1000,
            floor_area_m2=0,
        )
        self.assertEqual(report.intensity_kgco2e_per_m2, 0)


class TestEmissionPredictor(unittest.TestCase):
    """碳排放预测器测试"""

    def setUp(self):
        self.pred = EmissionPredictor()
        for i in range(24):
            month = (i % 12) + 1
            day = 1  # any valid day
            self.pred.add_record(HistoricalRecord(
                date=f"2023-{month:02d}-{day:02d}",
                co2e_kg=50000 + (i * 200) + (i % 12) * 1000,
            ))

    def test_forecast_returns_result(self):
        result = self.pred.forecast(periods=6)
        self.assertIsInstance(result, ForecastResult)
        self.assertEqual(len(result.predictions), 6)

    def test_forecast_positive_values(self):
        result = self.pred.forecast(periods=12)
        for p in result.predictions:
            self.assertGreaterEqual(p["predicted_co2e_kg"], 0)

    def test_confidence_intervals(self):
        result = self.pred.forecast(periods=3)
        self.assertEqual(len(result.confidence_lower), 3)
        self.assertEqual(len(result.confidence_upper), 3)
        for l, u in zip(result.confidence_lower, result.confidence_upper):
            self.assertLessEqual(l, u)

    def test_to_json(self):
        result = self.pred.forecast(periods=3)
        json_str = self.pred.to_json(result)
        parsed = json.loads(json_str)
        self.assertIn("predictions", parsed)
        self.assertIn("peak_month", parsed)


class TestReductionOptimizer(unittest.TestCase):
    """减排路径优化器测试"""

    def setUp(self):
        self.opt = ReductionOptimizer(current_annual_tco2e=500)
        self.opt.add_default_measures()

    def test_optimize_returns_result(self):
        result = self.opt.optimize(reduction_target_percent=30)
        self.assertIsInstance(result, OptimizationResult)
        self.assertGreater(len(result.measures), 0)

    def test_reduction_target(self):
        result = self.opt.optimize(reduction_target_percent=50)
        self.assertGreater(result.total_reduction_tco2e, 0)

    def test_budget_constraint(self):
        result = self.opt.optimize(
            reduction_target_percent=50,
            max_budget_cny=100000,
        )
        for m in result.measures:
            self.assertLessEqual(m.investment_cost_cny, 100000)

    def test_no_measures(self):
        opt = ReductionOptimizer(current_annual_tco2e=100)
        result = opt.optimize()
        self.assertEqual(len(result.measures), 0)

    def test_sort_by_payback(self):
        result = self.opt.optimize(sort_by="payback")
        if len(result.measures) > 1:
            self.assertLessEqual(
                result.measures[0].payback_years,
                result.measures[1].payback_years,
            )


class TestMeasurePricing(unittest.TestCase):
    """减排措施定价与回收期测试"""

    def test_payback_years(self):
        m = ReductionMeasure(
            name="测试",
            category=MeasureCategory.ENERGY_EFFICIENCY,
            reduction_potential_tco2e=10,
            investment_cost_cny=100000,
            annual_cost_saving_cny=25000,
        )
        self.assertEqual(m.payback_years, 4.0)

    def test_negative_cost_effectiveness(self):
        """负成本（直接盈利）检测"""
        m = ReductionMeasure(
            name="盈利措施",
            category=MeasureCategory.ENERGY_EFFICIENCY,
            reduction_potential_tco2e=10,
            investment_cost_cny=50000,
            annual_cost_saving_cny=30000,
        )
        self.assertIn("负成本", m.cost_effectiveness)


class TestBuildingSimulator(unittest.TestCase):
    """建筑模拟器测试"""

    def test_simulate_generates_data(self):
        sim = BuildingSimulator()
        data = sim.simulate()
        self.assertGreater(len(data), 0)
        self.assertIsInstance(data[0], SimulatedDataPoint)

    def test_different_locations(self):
        for loc in ["上海", "北京", "广州"]:
            profile = BuildingProfile(location=loc)
            sim = BuildingSimulator(profile=profile)
            sim.simulate()
            self.assertGreater(len(sim.data), 0)

    def test_to_csv_format(self):
        sim = BuildingSimulator()
        sim.simulate()
        csv = sim.to_csv()
        self.assertIn("year", csv)
        self.assertIn("co2e_kg", csv)

    def test_summary_stats(self):
        sim = BuildingSimulator()
        sim.simulate()
        stats = sim.summary_stats()
        self.assertIn("total_co2e_kg", stats)
        self.assertIn("intensity_kgco2e_per_m2", stats)


if __name__ == "__main__":
    unittest.main(verbosity=2)
