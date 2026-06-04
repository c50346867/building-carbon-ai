# -*- coding: utf-8 -*-
"""
Building Carbon Management AI — FastAPI Backend API
"""

from fastapi import FastAPI, Query
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field
from typing import List, Optional, Dict
import json

from backend.core.carbon_calculator import (
    CarbonCalculator, EmissionSource, EmissionScope, CarbonReport,
)
from backend.core.emission_predictor import EmissionPredictor, HistoricalRecord
from backend.core.reduction_optimizer import (
    ReductionOptimizer, ReductionMeasure, MeasureCategory,
)
from backend.core.simulator import BuildingSimulator, BuildingProfile

app = FastAPI(
    title="AI 建筑碳管理平台 API",
    description="Building Carbon Management AI — 碳排放计算、预测与减排优化",
    version="1.0.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ── 共享数据 ──
calculator = CarbonCalculator()
predictor = EmissionPredictor()
optimizer = ReductionOptimizer()


# ── Pydantic Models ──

class EmissionSourceRequest(BaseModel):
    name: str
    scope: str = "scope_2"
    activity_data: float
    emission_factor: float = 0.0
    unit: str = ""
    category: str = ""


class QuickEstimateRequest(BaseModel):
    electricity_kwh: float = 0
    natural_gas_m3: float = 0
    diesel_kg: float = 0
    water_m3: float = 0
    floor_area_m2: float = 1000.0
    region: str = "华东"


class RecordRequest(BaseModel):
    date: str
    co2e_kg: float
    electricity_kwh: float = 0
    gas_m3: float = 0


class OptimizeRequest(BaseModel):
    current_annual_tco2e: float
    reduction_target_percent: float = 30.0
    max_budget_cny: float = 1_000_000
    sort_by: str = "comprehensive"


class SimulateRequest(BaseModel):
    name: str = "典型商业办公建筑"
    floor_area_m2: float = 10000.0
    location: str = "上海"
    region: str = "华东"
    start_year: int = 2021
    end_year: int = 2025


# ── Emission Factors ──

@app.get("/api/v1/factors")
def get_factors(region: str = Query("华东", description="区域")):
    factors = CarbonCalculator().emission_factors
    return {
        "region_grid_factors": {
            "华北": 0.8843, "东北": 0.7769, "华东": 0.7035,
            "华中": 0.5915, "西北": 0.6666, "南方": 0.5267, "西南": 0.3875,
        },
        "selected_region": region,
        "factor_kgco2_per_kwh": {
            "华北": 0.8843, "东北": 0.7769, "华东": 0.7035,
            "华中": 0.5915, "西北": 0.6666, "南方": 0.5267, "西南": 0.3875,
        }.get(region, 0.7035),
    }


# ── Carbon Calculator ──

@app.post("/api/v1/calculate")
def calculate_emission(sources: List[EmissionSourceRequest]):
    srcs = []
    for s in sources:
        scope_map = {
            "scope_1": EmissionScope.SCOPE_1,
            "scope_2": EmissionScope.SCOPE_2,
            "scope_3": EmissionScope.SCOPE_3,
        }
        srcs.append(EmissionSource(
            name=s.name,
            scope=scope_map.get(s.scope, EmissionScope.SCOPE_2),
            activity_data=s.activity_data,
            emission_factor=s.emission_factor,
            unit=s.unit,
            category=s.category,
        ))
    report = calculator.calculate(
        [EmissionSource(name=s.name, scope=EmissionScope.SCOPE_2,
                        activity_data=s.activity_data, emission_factor=s.emission_factor,
                        unit=s.unit, category=s.category) for s in sources]
    )
    return _report_to_dict(report)


@app.post("/api/v1/quick-estimate")
def quick_estimate(req: QuickEstimateRequest):
    report = calculator.quick_estimate(
        electricity_kwh=req.electricity_kwh,
        natural_gas_m3=req.natural_gas_m3,
        diesel_kg=req.diesel_kg,
        water_m3=req.water_m3,
        floor_area_m2=req.floor_area_m2,
        region=req.region,
    )
    return _report_to_dict(report)


def _report_to_dict(report: CarbonReport) -> dict:
    return {
        "scope_1_kg": report.scope_1_total,
        "scope_2_kg": report.scope_2_total,
        "scope_3_kg": report.scope_3_total,
        "grand_total_kg": report.grand_total_kg,
        "grand_total_tco2e": report.grand_total_tco2e,
        "intensity_kgco2e_per_m2": report.intensity_kgco2e_per_m2,
        "details": [
            {
                "source": r.source_name,
                "scope": r.scope.value,
                "activity": r.activity_value,
                "factor": r.factor,
                "co2e_kg": r.co2e_kg,
            }
            for r in report.results
        ],
    }


# ── Emission Predictor ──

@app.post("/api/v1/predictor/add-record")
def add_record(rec: RecordRequest):
    record = HistoricalRecord(
        date=rec.date,
        co2e_kg=rec.co2e_kg,
        electricity_kwh=rec.electricity_kwh,
        gas_m3=rec.gas_m3,
    )
    predictor.add_record(record)
    return {"status": "ok", "records_count": len(predictor.history)}


@app.post("/api/v1/predictor/forecast")
def forecast(periods: int = Query(12, description="预测期数"), period_type: str = Query("month", description="month/year")):
    from backend.core.emission_predictor import HistoricalRecord as HR
    # If no records, generate from simulator
    if not predictor.history:
        sim = BuildingSimulator()
        sim.simulate()
        for dp in sim.data:
            predictor.add_record(HR(
                date=f"{dp.year}-{dp.month:02d}",
                co2e_kg=dp.co2e_kg,
                electricity_kwh=dp.electricity_kwh,
                gas_m3=dp.gas_m3,
            ))
    result = predictor.forecast(periods=periods, period_type=period_type)
    return json.loads(predictor.to_json(result))


# ── Reduction Optimizer ──

@app.post("/api/v1/optimize")
def optimize(req: OptimizeRequest):
    opt = ReductionOptimizer(current_annual_tco2e=req.current_annual_tco2e)
    opt.add_default_measures()
    result = opt.optimize(
        reduction_target_percent=req.reduction_target_percent,
        max_budget_cny=req.max_budget_cny,
        sort_by=req.sort_by,
    )
    return {
        "current_annual_tco2e": req.current_annual_tco2e,
        "reduction_target_percent": req.reduction_target_percent,
        "total_reduction_tco2e": result.total_reduction_tco2e,
        "total_investment_cny": result.total_investment_cny,
        "total_annual_saving_cny": result.total_annual_saving_cny,
        "weighted_abatement_cost": result.weighted_abatement_cost,
        "target_achieved": result.target_achieved,
        "measures": [
            {
                "name": m.name,
                "category": m.category.value,
                "reduction_tco2e": m.reduction_potential_tco2e,
                "investment_cny": m.investment_cost_cny,
                "annual_saving_cny": m.annual_cost_saving_cny,
                "payback_years": m.payback_years if m.payback_years != float("inf") else None,
                "abatement_cost": m.carbon_abatement_cost_cny_per_tco2e,
                "cost_effectiveness": m.cost_effectiveness,
                "implementation_days": m.implementation_days,
                "description": m.description,
            }
            for m in result.measures
        ],
    }


# ── Simulator ──

@app.post("/api/v1/simulate")
def simulate(req: SimulateRequest):
    profile = BuildingProfile(
        name=req.name,
        floor_area_m2=req.floor_area_m2,
        location=req.location,
        region=req.region,
    )
    sim = BuildingSimulator(profile=profile)
    sim.config.start_year = req.start_year
    sim.config.end_year = req.end_year
    sim.simulate()
    stats = sim.summary_stats()
    return {
        "stats": stats,
        "data": [
            {
                "year": d.year,
                "month": d.month,
                "electricity_kwh": d.electricity_kwh,
                "gas_m3": d.gas_m3,
                "diesel_kg": d.diesel_kg,
                "water_m3": d.water_m3,
                "co2e_kg": d.co2e_kg,
                "hdd": d.hdd,
                "cdd": d.cdd,
                "occupancy": d.occupancy,
                "ambient_temp_c": d.ambient_temp_c,
            }
            for d in sim.data
        ],
    }


@app.get("/api/v1/health")
def health_check():
    return {
        "status": "ok",
        "version": "1.0.0",
        "service": "Building Carbon Management AI",
    }
