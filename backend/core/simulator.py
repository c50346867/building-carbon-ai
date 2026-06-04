# -*- coding: utf-8 -*-
"""
建筑碳排放数据模拟器 — 生成典型建筑排放数据集
Building Carbon Emission Simulator — Generate realistic building emission data
"""

from typing import Dict, List, Optional
from dataclasses import dataclass, field
import random
import csv
import io
from datetime import datetime, timedelta


@dataclass
class BuildingProfile:
    """建筑基本参数"""
    name: str = "典型商业办公建筑"
    floor_area_m2: float = 10000.0
    floors_above: int = 12
    floors_below: int = 2
    year_built: int = 2015
    building_type: str = "commercial_office"
    occupancy_rate: float = 0.85
    hvac_type: str = "vrf"  # vrf, chiller, heat_pump
    location: str = "上海"
    region: str = "华东"


@dataclass
class SimulatedDataPoint:
    """单月模拟数据点"""
    year: int
    month: int
    electricity_kwh: float
    gas_m3: float
    diesel_kg: float
    water_m3: float
    co2e_kg: float
    hdd: float   # 采暖度日数
    cdd: float   # 制冷度日数
    occupancy: float
    ambient_temp_c: float
    notes: str = ""


@dataclass
class SimulationConfig:
    """模拟配置参数"""
    start_year: int = 2021
    end_year: int = 2025
    base_electricity_kwh_per_m2: float = 85.0      # kWh/m²/年
    base_gas_m3_per_m2: float = 8.5                  # m³/m²/年
    base_water_m3_per_m2: float = 1.2                # m³/m²/年
    diesel_emergency_ratio: float = 0.02             # 柴油占比
    noise_level: float = 0.05                        # 随机噪声 5%
    include_refrigerant: bool = True                  # 是否含制冷剂泄漏
    include_ev_charging: bool = True                  # 是否含电动车充电
    include_greening: bool = True                     # 是否含绿化碳汇


class BuildingSimulator:
    """
    建筑碳排放数据模拟器
    
    基于典型商用建筑的能耗特征，生成近似的月度碳排放数据，
    含季节效应、温度效应、以及噪声。
    """

    # 各城市气候数据 (月度平均气温 °C)
    CITY_CLIMATE: Dict[str, List[float]] = {
        "上海": [4.5, 6.0, 10.0, 15.5, 21.0, 25.0, 28.5, 28.0, 24.0, 18.5, 12.5, 6.5],
        "北京": [-3.0, 0.0, 7.0, 14.5, 20.5, 25.5, 27.5, 26.0, 21.0, 14.0, 5.0, -1.5],
        "广州": [14.0, 15.5, 19.0, 23.0, 26.5, 28.5, 29.5, 29.0, 27.5, 24.0, 19.5, 15.0],
        "深圳": [15.5, 16.5, 19.5, 23.0, 26.5, 28.5, 29.5, 29.0, 27.5, 24.5, 20.5, 16.5],
        "成都": [5.5, 7.5, 12.0, 17.0, 21.5, 24.5, 26.5, 26.0, 22.0, 17.0, 11.5, 6.5],
    }

    # 中国区域电网排放因子 (kg CO₂/kWh)
    GRID_FACTORS: Dict[str, float] = {
        "华东": 0.7035,
        "华北": 0.8843,
        "华南": 0.5267,
        "华中": 0.5915,
        "西北": 0.6666,
        "西南": 0.3875,
        "东北": 0.7769,
    }

    # 其他排放因子
    GAS_FACTOR = 2.165         # kg CO₂/m³ 天然气
    DIESEL_FACTOR = 3.186      # kg CO₂/kg 柴油
    WATER_FACTOR = 0.344       # kg CO₂/m³ 自来水

    def __init__(self, profile: Optional[BuildingProfile] = None):
        self.profile = profile or BuildingProfile()
        self.config = SimulationConfig()
        self._data: List[SimulatedDataPoint] = []

    def _get_climate(self) -> List[float]:
        """获取城市气候数据"""
        return self.CITY_CLIMATE.get(
            self.profile.location,
            self.CITY_CLIMATE["上海"]
        )

    def _monthly_factor(self, month: int) -> float:
        """
        基于温度的季节性因子
        冬季采暖 + 夏季制冷 → 能耗双峰
        """
        temps = self._get_climate()
        t = temps[month - 1]

        # 制冷度日数 (基温 26°C)
        cdd = max(t - 26, 0)
        # 采暖度日数 (基温 18°C)
        hdd = max(18 - t, 0)

        # 采暖/制冷能耗比例
        heating_factor = 1.0 + (hdd / 18) * 0.6   # 最大增加60%
        cooling_factor = 1.0 + (cdd / 10) * 0.5   # 最大增加50%

        # 春秋季基准
        base = 1.0
        if hdd > 0:
            return base * heating_factor
        elif cdd > 0:
            return base * cooling_factor
        return base * 0.85  # 过渡季节能耗较低

    def simulate(self) -> List[SimulatedDataPoint]:
        """
        运���模拟，生成月度碳排放数据。
        
        Returns:
            List[SimulatedDataPoint]: 模拟数据点列表
        """
        self._data = []
        random.seed(42)  # 可复现
        temps = self._get_climate()
        region_factor = self.GRID_FACTORS.get(self.profile.region, 0.7035)

        for year in range(self.config.start_year, self.config.end_year + 1):
            for month in range(1, 13):
                noise = 1.0 + random.uniform(
                    -self.config.noise_level,
                    self.config.noise_level
                )
                season = self._monthly_factor(month)
                occ = self.profile.occupancy_rate * (
                    0.9 if month in [2, 8] else 1.0
                )  # 春节/暑假入住率略低

                # 月度天数
                if month == 2:
                    days = 28 if year % 4 != 0 else 29
                elif month in [4, 6, 9, 11]:
                    days = 30
                else:
                    days = 31

                day_ratio = days / 30.0

                # 用电量 (kWh)
                yearly_elec = self.config.base_electricity_kwh_per_m2 * self.profile.floor_area_m2
                monthly_elec = (yearly_elec / 12) * season * noise * day_ratio
                # 年增长1.5%
                yearly_growth = 1.0 + (year - self.config.start_year) * 0.015
                monthly_elec *= yearly_growth

                # 天然气 (m³) — 冬季采暖消耗大
                yearly_gas = self.config.base_gas_m3_per_m2 * self.profile.floor_area_m2
                gas_season_factor = max(temps[month - 1], 5) / 15
                monthly_gas = (yearly_gas / 12) * (1.8 - gas_season_factor) * noise * day_ratio

                # ���油 (kg) — 备用发电
                monthly_diesel = (yearly_elec * self.config.diesel_emergency_ratio / 12) * noise

                # 用水 (m³)
                yearly_water = self.config.base_water_m3_per_m2 * self.profile.floor_area_m2
                water_season = 1.0 + (0.15 if month in [6, 7, 8, 9] else -0.05)
                monthly_water = (yearly_water / 12) * water_season * noise

                # 碳排放计算
                co2_elec = monthly_elec * region_factor
                co2_gas = monthly_gas * self.GAS_FACTOR
                co2_diesel = monthly_diesel * self.DIESEL_FACTOR
                co2_water = monthly_water * self.WATER_FACTOR

                # 制冷剂泄漏 (Scope 1)
                co2_refrigerant = 0
                if self.config.include_refrigerant and month in [5, 6, 7]:
                    # 夏季制冷剂微泄漏
                    co2_refrigerant = random.uniform(50, 200) * noise

                # 电动车充电 (Scope 2)
                co2_ev = 0
                if self.config.include_ev_charging:
                    co2_ev = monthly_elec * 0.03 * region_factor * noise

                total_co2 = (co2_elec + co2_gas + co2_diesel
                             + co2_water + co2_refrigerant + co2_ev)

                # 绿植碳汇 (负排放)
                if self.config.include_greening:
                    green_area = self.profile.floor_area_m2 * 0.15  # 15%绿化面积
                    carbon_sink = green_area * 0.02 * noise  # 20g/m²/日
                    total_co2 -= carbon_sink * days

                total_co2 = max(total_co2, 0)

                hdd_val = max(18 - temps[month - 1], 0) * days
                cdd_val = max(temps[month - 1] - 26, 0) * days

                dp = SimulatedDataPoint(
                    year=year,
                    month=month,
                    electricity_kwh=round(monthly_elec, 2),
                    gas_m3=round(monthly_gas, 2),
                    diesel_kg=round(monthly_diesel, 2),
                    water_m3=round(monthly_water, 2),
                    co2e_kg=round(total_co2, 2),
                    hdd=round(hdd_val, 1),
                    cdd=round(cdd_val, 1),
                    occupancy=round(occ, 2),
                    ambient_temp_c=round(temps[month - 1], 1),
                    notes=f"{self.profile.name} - {year}-{month:02d}",
                )
                self._data.append(dp)

        return self._data

    @property
    def data(self) -> List[SimulatedDataPoint]:
        return self._data

    def to_csv(self) -> str:
        """导出为 CSV 字符串"""
        output = io.StringIO()
        writer = csv.writer(output)
        writer.writerow([
            "year", "month", "electricity_kwh", "gas_m3", "diesel_kg",
            "water_m3", "co2e_kg", "hdd", "cdd", "occupancy",
            "ambient_temp_c", "notes"
        ])
        for dp in self._data:
            writer.writerow([
                dp.year, dp.month, dp.electricity_kwh, dp.gas_m3,
                dp.diesel_kg, dp.water_m3, dp.co2e_kg, dp.hdd,
                dp.cdd, dp.occupancy, dp.ambient_temp_c, dp.notes,
            ])
        return output.getvalue()

    def summary_stats(self) -> Dict:
        """生成统计摘要"""
        if not self._data:
            return {}

        total_co2 = sum(d.co2e_kg for d in self._data)
        total_elec = sum(d.electricity_kwh for d in self._data)
        total_gas = sum(d.gas_m3 for d in self._data)

        years = set(d.year for d in self._data)
        annual_co2 = {}
        for y in years:
            y_data = [d for d in self._data if d.year == y]
            annual_co2[y] = round(sum(d.co2e_kg for d in y_data), 2)

        return {
            "building": self.profile.name,
            "location": self.profile.location,
            "floor_area_m2": self.profile.floor_area_m2,
            "period": f"{self.config.start_year}-{self.config.end_year}",
            "total_co2e_kg": round(total_co2, 2),
            "total_co2e_tco2e": round(total_co2 / 1000, 2),
            "total_electricity_kwh": round(total_elec, 2),
            "total_gas_m3": round(total_gas, 2),
            "annual_co2e_kg": annual_co2,
            "avg_monthly_co2e_kg": round(total_co2 / len(self._data), 2) if self._data else 0,
            "intensity_kgco2e_per_m2": round(
                total_co2 / self.profile.floor_area_m2, 2
            ) if self.profile.floor_area_m2 > 0 else 0,
        }
