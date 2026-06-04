# -*- coding: utf-8 -*-
"""
碳排放计算器 — 支持 Scope 1/2/3 碳排放计算
Carbon Emission Calculator — Scope 1, 2, 3 compliant
"""

from typing import Dict, List, Optional
from dataclasses import dataclass, field
from enum import Enum


class EmissionScope(Enum):
    SCOPE_1 = "scope_1"  # Direct emissions (natural gas, diesel, refrigerants)
    SCOPE_2 = "scope_2"  # Indirect from purchased energy
    SCOPE_3 = "scope_3"  # Upstream/downstream indirect


@dataclass
class EmissionSource:
    """碳排放源"""
    name: str
    scope: EmissionScope
    activity_data: float         # Activity data (kWh, m³, kg, etc.)
    emission_factor: float       # kg CO₂e per unit
    unit: str = ""
    category: str = ""


@dataclass
class EmissionResult:
    """单次排放计算结果"""
    source_name: str
    scope: EmissionScope
    activity_value: float
    factor: float
    co2e_kg: float
    category: str = ""


@dataclass
class CarbonReport:
    """完整碳排放报告"""
    building_id: str = ""
    period: str = ""
    results: List[EmissionResult] = field(default_factory=list)
    scope_1_total: float = 0.0
    scope_2_total: float = 0.0
    scope_3_total: float = 0.0
    grand_total_kg: float = 0.0
    floor_area_m2: float = 1.0
    intensity_kgco2e_per_m2: float = 0.0

    @property
    def grand_total_tco2e(self) -> float:
        return round(self.grand_total_kg / 1000, 2)


class CarbonCalculator:
    """
    碳排放计算器
    
    根据 IPCC 国家温室气体清单指南及中国建筑碳排放计算标准 (GB/T 51366-2019) 设计。
    支持三大 Scope — 直接排放、间接排放、供应链排放。
    """

    def __init__(self, emission_factors: Optional[Dict[str, float]] = None):
        self.emission_factors = emission_factors or {}

    @staticmethod
    def gwp_co2() -> float:
        """CO₂ GWP = 1 (基准)"""
        return 1.0

    def calculate(self, sources: List[EmissionSource]) -> CarbonReport:
        """
        对输入的所有排放源进行计算。
        
        Args:
            sources: 排放源列表
            
        Returns:
            CarbonReport: 完整碳排放报告
        """
        report = CarbonReport()
        for src in sources:
            factor = self.emission_factors.get(
                src.name,
                src.emission_factor
            )
            co2e = src.activity_data * factor
            result = EmissionResult(
                source_name=src.name,
                scope=src.scope,
                activity_value=src.activity_data,
                factor=factor,
                co2e_kg=round(co2e, 4),
                category=src.category,
            )
            report.results.append(result)

            if src.scope == EmissionScope.SCOPE_1:
                report.scope_1_total += co2e
            elif src.scope == EmissionScope.SCOPE_2:
                report.scope_2_total += co2e
            elif src.scope == EmissionScope.SCOPE_3:
                report.scope_3_total += co2e

        report.scope_1_total = round(report.scope_1_total, 2)
        report.scope_2_total = round(report.scope_2_total, 2)
        report.scope_3_total = round(report.scope_3_total, 2)
        report.grand_total_kg = round(
            report.scope_1_total + report.scope_2_total + report.scope_3_total, 2
        )
        if report.floor_area_m2 > 0:
            report.intensity_kgco2e_per_m2 = round(
                report.grand_total_kg / report.floor_area_m2, 2
            )
        return report

    def quick_estimate(
        self,
        electricity_kwh: float = 0,
        natural_gas_m3: float = 0,
        diesel_kg: float = 0,
        water_m3: float = 0,
        floor_area_m2: float = 1.0,
        region: str = "华东",
    ) -> CarbonReport:
        """
        快速估算典型建筑碳排放。
        
        Args:
            electricity_kwh: 外购电量 (kWh)
            natural_gas_m3: 天然气用量 (m³)
            diesel_kg: 柴油用量 (kg)
            water_m3: 用水量 (m³)
            floor_area_m2: 建筑面积 (m²)
            region: 所在区域（华东/华北/华南/华中/西北/西南/东北）
            
        Returns:
            CarbonReport: 碳排放估算报告
        """
        # 中国区域电网基准线排放因子 (kg CO₂/kWh), 2024参考值
        grid_factors = {
            "华北": 0.8843,
            "东北": 0.7769,
            "华东": 0.7035,
            "华中": 0.5915,
            "西北": 0.6666,
            "南方": 0.5267,
            "西南": 0.3875,
        }
        elec_factor = grid_factors.get(region, 0.7035)

        # 缺省排放因子
        gas_factor = self.emission_factors.get("天然气", 2.165)   # kg CO₂/m³
        diesel_factor = self.emission_factors.get("柴油", 3.186)  # kg CO₂/kg
        water_factor = self.emission_factors.get("自来水", 0.344)  # kg CO₂/m³

        sources = [
            EmissionSource(
                name="外购电力",
                scope=EmissionScope.SCOPE_2,
                activity_data=electricity_kwh,
                emission_factor=elec_factor,
                unit="kWh",
                category="电力",
            ),
            EmissionSource(
                name="天然气",
                scope=EmissionScope.SCOPE_1,
                activity_data=natural_gas_m3,
                emission_factor=gas_factor,
                unit="m³",
                category="燃气",
            ),
            EmissionSource(
                name="柴油",
                scope=EmissionScope.SCOPE_1,
                activity_data=diesel_kg,
                emission_factor=diesel_factor,
                unit="kg",
                category="燃油",
            ),
            EmissionSource(
                name="自来水",
                scope=EmissionScope.SCOPE_3,
                activity_data=water_m3,
                emission_factor=water_factor,
                unit="m³",
                category="水资源",
            ),
        ]
        # Filter out zero-activity sources
        sources = [s for s in sources if s.activity_data > 0]
        report = self.calculate(sources)
        report.floor_area_m2 = floor_area_m2
        report.intensity_kgco2e_per_m2 = round(
            report.grand_total_kg / floor_area_m2, 2
        ) if floor_area_m2 > 0 else 0.0
        return report

    def summary_text(self, report: CarbonReport) -> str:
        """生成可读的摘要文本"""
        lines = [
            f"📊 碳排放报告 — {report.building_id or '建筑'} ({report.period or '本期'})",
            f"{'=' * 50}",
            f"  Scope 1 (直接排放):      {report.scope_1_total:>12.2f} kg CO₂e",
            f"  Scope 2 (间接-电力/热力): {report.scope_2_total:>12.2f} kg CO₂e",
            f"  Scope 3 (其他间接):      {report.scope_3_total:>12.2f} kg CO₂e",
            f"  {'─' * 40}",
            f"  排放总量:               {report.grand_total_kg:>12.2f} kg CO₂e",
            f"  碳排放强度:             {report.intensity_kgco2e_per_m2:>12.2f} kg CO₂e/m²",
            f"{'=' * 50}",
        ]
        for r in report.results:
            lines.append(
                f"  · {r.source_name:<20s} {r.activity_value:>10.1f} {r.unit or 'unit'} "
                f"× {r.factor:.4f} = {r.co2e_kg:>8.2f} kg CO₂e"
            )
        return "\n".join(lines)
