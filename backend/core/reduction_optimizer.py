# -*- coding: utf-8 -*-
"""
减排路径优化器 — 智能推荐最优减排组合策略
Reduction Optimizer — Intelligent decarbonization pathway optimization
"""

from typing import Dict, List, Optional, Tuple
from dataclasses import dataclass, field
from enum import Enum


class MeasureCategory(Enum):
    ENERGY_EFFICIENCY = "节能改造"
    RENEWABLE_ENERGY = "可再生能源"
    GREEN_POWER = "绿电采购"
    CARBON_TRADING = "碳交易"
    OPERATIONAL = "运营优化"
    BEHAVIORAL = "行为改变"


@dataclass
class ReductionMeasure:
    """单项减排措施"""
    name: str
    category: MeasureCategory
    reduction_potential_tco2e: float   # 年减排潜力 (吨 CO₂e)
    investment_cost_cny: float         # 投资成本 (元)
    annual_cost_saving_cny: float      # 年节省运营成本 (元)
    lifetime_years: int = 10           # 措施寿命期
    implementation_days: int = 90      # 实施周期 (天)
    description: str = ""
    carbon_abatement_cost_cny_per_tco2e: float = 0.0  # 碳减排成本

    def __post_init__(self):
        if self.annual_cost_saving_cny > 0 or self.reduction_potential_tco2e > 0:
            self.carbon_abatement_cost_cny_per_tco2e = round(
                (self.investment_cost_cny / max(self.lifetime_years, 1)
                 - self.annual_cost_saving_cny)
                / max(self.reduction_potential_tco2e, 0.001),
                2
            )

    @property
    def payback_years(self) -> float:
        """简单投资回收期 (年)"""
        annual_net_benefit = self.annual_cost_saving_cny
        if annual_net_benefit <= 0:
            return float("inf")
        return round(self.investment_cost_cny / annual_net_benefit, 1)

    @property
    def cost_effectiveness(self) -> str:
        """成本效益等级"""
        cost = self.carbon_abatement_cost_cny_per_tco2e
        if cost < 0:
            return "💰 负成本（直接盈利）"
        elif cost < 100:
            return "✅ 低成本"
        elif cost < 500:
            return "🟡 中等成本"
        elif cost < 2000:
            return "🟠 较高成本"
        else:
            return "🔴 高成本"


@dataclass
class OptimizationResult:
    """优化结果"""
    measures: List[ReductionMeasure] = field(default_factory=list)
    total_reduction_tco2e: float = 0.0
    total_investment_cny: float = 0.0
    total_annual_saving_cny: float = 0.0
    weighted_abatement_cost: float = 0.0
    target_achieved: bool = False


class ReductionOptimizer:
    """
    减排路径优化器
    
    根据输入当前碳排数据，输出最优减排组合策略。
    支持按投资回报排序、碳减排成本排序及目标约束优化。
    """

    def __init__(self, current_annual_tco2e: float = 0):
        self.current_annual = current_annual_tco2e
        self._measures: List[ReductionMeasure] = []

    def add_measure(self, measure: ReductionMeasure) -> None:
        """添加候选减排措施"""
        self._measures.append(measure)

    def add_default_measures(self) -> None:
        """添加默认的典型建筑减排措施库"""
        defaults = [
            ReductionMeasure(
                name="LED照明改造",
                category=MeasureCategory.ENERGY_EFFICIENCY,
                reduction_potential_tco2e=12.5,
                investment_cost_cny=80000,
                annual_cost_saving_cny=35000,
                lifetime_years=8,
                implementation_days=30,
                description="将传统照明更换为高效LED灯具，配套智能感应控制",
            ),
            ReductionMeasure(
                name="屋顶分布式光伏",
                category=MeasureCategory.RENEWABLE_ENERGY,
                reduction_potential_tco2e=45.0,
                investment_cost_cny=450000,
                annual_cost_saving_cny=60000,
                lifetime_years=25,
                implementation_days=120,
                description="利用屋顶面积安装光伏板，自发自用余电上网",
            ),
            ReductionMeasure(
                name="暖通空调( HVAC)能效提升",
                category=MeasureCategory.ENERGY_EFFICIENCY,
                reduction_potential_tco2e=28.3,
                investment_cost_cny=250000,
                annual_cost_saving_cny=55000,
                lifetime_years=15,
                implementation_days=90,
                description="更换高能效冷水机组+变频水泵+BA系统优化",
            ),
            ReductionMeasure(
                name="绿电采购 (30%)",
                category=MeasureCategory.GREEN_POWER,
                reduction_potential_tco2e=35.0,
                investment_cost_cny=5000,
                annual_cost_saving_cny=-15000,
                lifetime_years=1,
                implementation_days=15,
                description="通过电力市场购买绿色电力证书或直购绿电",
            ),
            ReductionMeasure(
                name="建筑围护结构节能改造",
                category=MeasureCategory.ENERGY_EFFICIENCY,
                reduction_potential_tco2e=18.6,
                investment_cost_cny=350000,
                annual_cost_saving_cny=40000,
                lifetime_years=20,
                implementation_days=180,
                description="外墙保温+Low-E玻璃+屋顶隔热层升级",
            ),
            ReductionMeasure(
                name="碳排放权交易",
                category=MeasureCategory.CARBON_TRADING,
                reduction_potential_tco2e=50.0,
                investment_cost_cny=75000,
                annual_cost_saving_cny=0,
                lifetime_years=1,
                implementation_days=30,
                description="购买CCER/碳配额弥补��排缺口",
            ),
            ReductionMeasure(
                name="智慧能源管理系统 (EMS)",
                category=MeasureCategory.OPERATIONAL,
                reduction_potential_tco2e=15.2,
                investment_cost_cny=180000,
                annual_cost_saving_cny=45000,
                lifetime_years=10,
                implementation_days=60,
                description="部署能源监控+AI优化控制+需量管理系统",
            ),
            ReductionMeasure(
                name="行为节能计划",
                category=MeasureCategory.BEHAVIORAL,
                reduction_potential_tco2e=5.0,
                investment_cost_cny=15000,
                annual_cost_saving_cny=12000,
                lifetime_years=3,
                implementation_days=45,
                description="节能培训+能效竞赛+自动断电策略+空调温度设定",
            ),
            ReductionMeasure(
                name="空调冷源余热回收",
                category=MeasureCategory.ENERGY_EFFICIENCY,
                reduction_potential_tco2e=8.4,
                investment_cost_cny=120000,
                annual_cost_saving_cny=28000,
                lifetime_years=15,
                implementation_days=60,
                description="利用冷凝热制备生活热水，减少锅炉能耗",
            ),
            ReductionMeasure(
                name="电梯能量回馈系统",
                category=MeasureCategory.ENERGY_EFFICIENCY,
                reduction_potential_tco2e=3.2,
                investment_cost_cny=60000,
                annual_cost_saving_cny=12000,
                lifetime_years=12,
                implementation_days=45,
                description="加装电梯能量回馈装置，将制动能量转化为电能",
            ),
        ]
        self._measures.extend(defaults)

    def _score_measure(self, m: ReductionMeasure) -> float:
        """
        综合评分（越低越优先）
        考虑：碳减排成本(40%) + 回收期(30%) + 实施难度(30%)
        """
        # 碳减排成本评分 (归一化)
        cost_score = min(m.carbon_abatement_cost_cny_per_tco2e / 500, 100) if m.carbon_abatement_cost_cny_per_tco2e > 0 else 0

        # 投资回收期评分
        payback_score = min(m.payback_years / 10, 10) if m.payback_years != float("inf") else 10

        # 实施难度评分（按天数折算）
        impl_score = m.implementation_days / 365 * 10

        return cost_score * 0.4 + payback_score * 0.3 + impl_score * 0.3

    def optimize(
        self,
        reduction_target_percent: float = 30.0,
        max_budget_cny: float = float("inf"),
        sort_by: str = "comprehensive",
    ) -> OptimizationResult:
        """
        优化减排路径。
        
        Args:
            reduction_target_percent: 减排目标百分比 (如 30%)
            max_budget_cny: 最大投资预算 (元)
            sort_by: 排序方式 comprehensive | payback | cost_effective
            
        Returns:
            OptimizationResult: 优化后的推荐方案
        """
        target_tco2e = self.current_annual * reduction_target_percent / 100.0
        result = OptimizationResult()

        if not self._measures:
            return result

        # 评分排序
        if sort_by == "payback":
            sorted_measures = sorted(
                self._measures,
                key=lambda m: (m.payback_years if m.payback_years != float("inf") else 1e9)
            )
        elif sort_by == "cost_effective":
            sorted_measures = sorted(
                self._measures,
                key=lambda m: m.carbon_abatement_cost_cny_per_tco2e
            )
        else:
            sorted_measures = sorted(
                self._measures,
                key=lambda m: self._score_measure(m)
            )

        cumulative_reduction = 0.0
        cumulative_investment = 0.0
        cumulative_saving = 0.0

        for m in sorted_measures:
            if cumulative_reduction >= target_tco2e:
                break
            if cumulative_investment + m.investment_cost_cny > max_budget_cny:
                continue

            result.measures.append(m)
            cumulative_reduction += m.reduction_potential_tco2e
            cumulative_investment += m.investment_cost_cny
            cumulative_saving += m.annual_cost_saving_cny

        result.total_reduction_tco2e = round(cumulative_reduction, 2)
        result.total_investment_cny = round(cumulative_investment, 2)
        result.total_annual_saving_cny = round(cumulative_saving, 2)
        result.target_achieved = cumulative_reduction >= target_tco2e

        weighted_cost = 0
        if result.measures and cumulative_reduction > 0:
            for m in result.measures:
                weighted_cost += m.carbon_abatement_cost_cny_per_tco2e * (
                    m.reduction_potential_tco2e / cumulative_reduction
                )
        result.weighted_abatement_cost = round(weighted_cost, 2)

        return result

    def generate_report_text(self, result: OptimizationResult) -> str:
        """生成可读的优化报告文本"""
        lines = [
            "📋 减排路径优化报告",
            "=" * 60,
            f"当前年排放: {self.current_annual:.0f} tCO₂e",
            f"减排目标:   {result.total_reduction_tco2e:.1f} tCO₂e "
            f"({'✅ 达成' if result.target_achieved else '⚠️ 未完全达成'})",
            f"总投资:     ¥{result.total_investment_cny:,.0f}",
            f"年节省:     ¥{result.total_annual_saving_cny:,.0f}",
            f"加权减排成本: ¥{result.weighted_abatement_cost:.0f}/tCO₂e",
            "-" * 60,
            "推荐措施（按优先级）:",
            "-" * 60,
        ]
        for i, m in enumerate(result.measures, 1):
            lines.append(
                f"\n  {i}. {m.name} [{m.category.value}]"
                f"\n     🏭 减排: {m.reduction_potential_tco2e:.1f} tCO₂e/年"
                f"\n     💰 投资: ¥{m.investment_cost_cny:,.0f} | 年节省: ¥{m.annual_cost_saving_cny:,.0f}"
                f"\n     📅 ���收期: {m.payback_years if m.payback_years != float('inf') else 'N/A'}年"
                f"\n     📝 {m.description}"
            )
        return "\n".join(lines)
