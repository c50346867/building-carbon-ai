# -*- coding: utf-8 -*-
"""
碳排放预测器 — 基于历史数据和机器学习的时序预测
Emission Predictor — Time-series forecasting with ML
"""

from typing import Dict, List, Optional, Tuple
from dataclasses import dataclass, field
from datetime import datetime, timedelta
import math
import json


@dataclass
class HistoricalRecord:
    """历史碳排放记录"""
    date: str          # YYYY-MM-DD
    co2e_kg: float     # 当日/月碳排放 (kg)
    electricity_kwh: float = 0.0
    gas_m3: float = 0.0
    hdd: float = 0.0   # Heating Degree Days
    cdd: float = 0.0   # Cooling Degree Days
    occupancy: float = 0.8  # 入住率 0-1
    weekday: int = 0   # 0=Monday


@dataclass
class ForecastResult:
    """预测结果"""
    predictions: List[Dict] = field(default_factory=list)
    total_predicted_tco2e: float = 0.0
    peak_month: str = ""
    peak_value: float = 0.0
    confidence_lower: List[float] = field(default_factory=list)
    confidence_upper: List[float] = field(default_factory=list)
    method: str = "seasonal_decomposition"


class EmissionPredictor:
    """
    碳排放预测器
    
    基于历史碳排放数据、建筑运行特征及天气/季节因素，
    采用季节性分解 + 线性趋势外推进行预测。
    """

    def __init__(self, history: Optional[List[HistoricalRecord]] = None):
        self.history = history or []

    def add_record(self, record: HistoricalRecord) -> None:
        """添加一条历史记录"""
        self.history.append(record)

    def _compute_seasonal_factors(self) -> Dict[int, float]:
        """按月计算季节性因子 (12个月)"""
        if not self.history:
            return {m: 1.0 for m in range(1, 13)}

        monthly_totals: Dict[int, List[float]] = {}
        for rec in self.history:
            try:
                month = int(rec.date.split("-")[1])
            except (IndexError, ValueError):
                continue
            if month not in monthly_totals:
                monthly_totals[month] = []
            monthly_totals[month].append(rec.co2e_kg)

        monthly_avg = {}
        for m in range(1, 13):
            vals = monthly_totals.get(m, [])
            monthly_avg[m] = sum(vals) / len(vals) if vals else 0.0

        if not monthly_avg:
            return {m: 1.0 for m in range(1, 13)}

        overall_avg = sum(monthly_avg.values()) / max(len([v for v in monthly_avg.values() if v > 0]), 1)

        return {
            m: (avg / overall_avg) if overall_avg > 0 else 1.0
            for m, avg in monthly_avg.items()
        }

    def _compute_trend(self) -> Tuple[float, float]:
        """
        计算线性趋势 (slope, intercept)
        使用简单线性回归
        """
        n = len(self.history)
        if n < 2:
            return 0.0, (self.history[-1].co2e_kg if self.history else 0.0)

        x_vals = list(range(n))
        y_vals = [r.co2e_kg for r in self.history]
        x_mean = sum(x_vals) / n
        y_mean = sum(y_vals) / n

        num = sum((x - x_mean) * (y - y_mean) for x, y in zip(x_vals, y_vals))
        den = sum((x - x_mean) ** 2 for x in x_vals)

        slope = num / den if den != 0 else 0.0
        intercept = y_mean - slope * x_mean
        return slope, intercept

    def forecast(
        self,
        periods: int = 12,
        period_type: str = "month",
        confidence_level: float = 0.95,
    ) -> ForecastResult:
        """
        预测未来碳排放。
        
        Args:
            periods: 预测期数
            period_type: "month" 或 "year"
            confidence_level: 置信水平 (0-1)
            
        Returns:
            ForecastResult: 预测结果
        """
        if not self.history:
            return ForecastResult()

        seasonal = self._compute_seasonal_factors()
        slope, intercept = self._compute_trend()
        base_value = self.history[-1].co2e_kg if self.history else 0.0

        # 标准差（用于置信区间）
        residuals = []
        for i, rec in enumerate(self.history):
            trend_val = intercept + slope * i
            try:
                month = int(rec.date.split("-")[1])
            except (IndexError, ValueError):
                month = 1
            seasonal_val = seasonal.get(month, 1.0)
            predicted = trend_val * seasonal_val
            residuals.append(rec.co2e_kg - predicted)

        std_dev = math.sqrt(
            sum(r ** 2 for r in residuals) / max(len(residuals), 1)
        ) if residuals else base_value * 0.05

        # Z-score for confidence level
        z_map = {0.90: 1.645, 0.95: 1.96, 0.99: 2.576}
        z = z_map.get(confidence_level, 1.96)

        result = ForecastResult()
        result.method = "seasonal_decomposition"

        last_date = datetime.strptime(
            self.history[-1].date, "%Y-%m-%d"
        ) if self.history else datetime.now()

        peak_val = 0.0
        peak_month_str = ""

        for i in range(1, periods + 1):
            if period_type == "month":
                # 推算月份
                year_offset = (last_date.month - 1 + i) // 12
                month = ((last_date.month - 1 + i) % 12) + 1
                year = last_date.year + year_offset
                pred_date = f"{year}-{month:02d}"
                seasonal_factor = seasonal.get(month, 1.0)
            else:
                pred_date = f"{last_date.year + i}"
                seasonal_factor = 1.0

            trend_val = base_value + slope * i
            pred_raw = trend_val * seasonal_factor
            pred_co2e = max(pred_raw, 0)  # 不能为负

            ci = z * std_dev * math.sqrt(1 + 1.0 / max(len(self.history), 1))

            result.predictions.append({
                "date": pred_date,
                "predicted_co2e_kg": round(pred_co2e, 2),
                "seasonal_factor": round(seasonal_factor, 4),
            })
            result.confidence_lower.append(round(max(pred_co2e - ci, 0), 2))
            result.confidence_upper.append(round(pred_co2e + ci, 2))

            if pred_co2e > peak_val:
                peak_val = pred_co2e
                peak_month_str = pred_date

        result.total_predicted_tco2e = round(
            sum(p["predicted_co2e_kg"] for p in result.predictions) / 1000, 2
        )
        result.peak_month = peak_month_str
        result.peak_value = round(peak_val, 2)

        return result

    def to_json(self, result: ForecastResult) -> str:
        """序列化预测结果为 JSON"""
        return json.dumps({
            "method": result.method,
            "total_predicted_tco2e": result.total_predicted_tco2e,
            "peak_month": result.peak_month,
            "peak_value": result.peak_value,
            "predictions": result.predictions,
            "confidence_lower": result.confidence_lower,
            "confidence_upper": result.confidence_upper,
        }, ensure_ascii=False, indent=2)
