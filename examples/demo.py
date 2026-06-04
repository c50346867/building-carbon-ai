# -*- coding: utf-8 -*-
"""
建筑碳管理平台 — 使用示例
Building Carbon Management AI — Demo
"""

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from backend.core.simulator import BuildingSimulator, BuildingProfile
from backend.core.carbon_calculator import CarbonCalculator, EmissionSource, EmissionScope
from backend.core.emission_predictor import EmissionPredictor, HistoricalRecord
from backend.core.reduction_optimizer import ReductionOptimizer, ReductionMeasure


def demo_simulator():
    """示例 1: 数据模拟"""
    print("=" * 60)
    print("📊 示例 1: 建筑碳排放数据模拟")
    print("=" * 60)

    profile = BuildingProfile(
        name="上海XX商业大厦",
        floor_area_m2=15000,
        location="上海",
        region="华东",
    )
    sim = BuildingSimulator(profile=profile)
    sim.simulate()
    stats = sim.summary_stats()

    print(f"  建筑: {stats['building']}")
    print(f"  位置: {stats['location']}")
    print(f"  面积: {stats['floor_area_m2']:,.0f} m²")
    print(f"  周期: {stats['period']}")
    print(f"  总排放: {stats['total_co2e_tco2e']:.2f} tCO₂e")
    print(f"  碳排放强度: {stats['intensity_kgco2e_per_m2']:.2f} kgCO₂e/m²")
    print(f"  年均排放: {stats['annual_co2e_kg']}")
    print()


def demo_calculator():
    """示例 2: 碳排放计算"""
    print("=" * 60)
    print("🧮 示例 2: 碳排放计算")
    print("=" * 60)

    cal = CarbonCalculator()
    report = cal.quick_estimate(
        electricity_kwh=85000,
        natural_gas_m3=8800,
        diesel_kg=500,
        water_m3=1200,
        floor_area_m2=10000,
        region="华东",
    )
    print(cal.summary_text(report))
    print()


def demo_predictor():
    """示例 3: 碳排放预测"""
    print("=" * 60)
    print("🔮 示例 3: 碳排放预测")
    print("=" * 60)

    # Generate dummy history
    sim = BuildingSimulator()
    sim.simulate()

    pred = EmissionPredictor()
    for dp in sim.data:
        pred.add_record(HistoricalRecord(
            date=f"{dp.year}-{dp.month:02d}",
            co2e_kg=dp.co2e_kg,
            electricity_kwh=dp.electricity_kwh,
            gas_m3=dp.gas_m3,
        ))

    result = pred.forecast(periods=6)
    print(f"  预测方法: {result.method}")
    print(f"  预测总量: {result.total_predicted_tco2e:.2f} tCO₂e")
    print(f"  排放峰值: {result.peak_month} ({result.peak_value:.0f} kg)")
    print("  月度预测:")
    for p in result.predictions:
        print(f"    {p['date']}: {p['predicted_co2e_kg']:>10.2f} kg CO₂e")
    print()


def demo_optimizer():
    """示例 4: 减排路径优化"""
    print("=" * 60)
    print("🎯 示例 4: 减排路径优化")
    print("=" * 60)

    opt = ReductionOptimizer(current_annual_tco2e=500)
    opt.add_default_measures()
    result = opt.optimize(reduction_target_percent=30)

    print(opt.generate_report_text(result))
    print()


if __name__ == "__main__":
    print()
    print("🌱 AI 建筑碳管理平台 — 示例程序")
    print()

    demo_simulator()
    demo_calculator()
    demo_predictor()
    demo_optimizer()

    print("=" * 60)
    print("✅ 所有示例运行完成！")
    print("=" * 60)
