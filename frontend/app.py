# -*- coding: utf-8 -*-
"""
Building Carbon Management AI — Streamlit Dashboard
AI 建筑碳管理平台 — 碳管理仪表盘
"""

import streamlit as st
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import json
import sys
import os

# Ensure project root is in path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from backend.core.simulator import BuildingSimulator, BuildingProfile, SimulationConfig
from backend.core.carbon_calculator import CarbonCalculator, EmissionScope
from backend.core.emission_predictor import EmissionPredictor, HistoricalRecord
from backend.core.reduction_optimizer import (
    ReductionOptimizer, ReductionMeasure, MeasureCategory,
)

# ── Page Config ──
st.set_page_config(
    page_title="AI 建筑碳管理平台",
    page_icon="🌱",
    layout="wide",
    initial_sidebar_state="expanded",
)

# ���─ Dark Theme ──
st.markdown("""
<style>
    .main-header {
        font-size: 2.2rem;
        font-weight: 700;
        color: #4ade80;
        margin-bottom: 0.5rem;
    }
    .sub-header {
        font-size: 1.1rem;
        color: #94a3b8;
        margin-bottom: 2rem;
    }
    .metric-card {
        background: #1e293b;
        border-radius: 12px;
        padding: 1.5rem;
        border-left: 4px solid #4ade80;
    }
    .metric-label {
        font-size: 0.85rem;
        color: #94a3b8;
    }
    .metric-value {
        font-size: 1.8rem;
        font-weight: 700;
        color: #e2e8f0;
    }
    .metric-unit {
        font-size: 0.9rem;
        color: #64748b;
    }
    .badge-scope1 { color: #f87171; font-weight: 600; }
    .badge-scope2 { color: #fbbf24; font-weight: 600; }
    .badge-scope3 { color: #60a5fa; font-weight: 600; }
    .stApp { background: #0f172a; }
    section[data-testid="stSidebar"] > div { background: #1e293b; }
</style>
""", unsafe_allow_html=True)

# ── Sidebar ──
st.sidebar.markdown("## 🌱 AI 建筑碳管理")
st.sidebar.markdown("---")

building_type = st.sidebar.selectbox(
    "建筑类型",
    ["商业办公", "购物中心", "酒店", "医院", "学校", "住宅"],
    index=0,
)

location = st.sidebar.selectbox(
    "所在城市",
    ["上海", "北京", "广州", "深圳", "成都"],
    index=0,
)

floor_area = st.sidebar.number_input(
    "建筑面积 (m²)", min_value=100, max_value=500000, value=10000, step=500,
)

region_map = {
    "上海": "华东", "北京": "华北", "广州": "华南",
    "深圳": "华南", "成都": "西南",
}
region = region_map.get(location, "华东")

sim_years = st.sidebar.slider("数据年份范围", 2020, 2026, (2021, 2025))

st.sidebar.markdown("---")
st.sidebar.markdown("**🏭 关于平台**")
st.sidebar.markdown(
    "AI 建筑碳管理平台基于中国建筑碳排放标准 (GB/T 51366-2019)，"
    "提供碳排放计算、预测与减排路径优化一体化方案。",
)
st.sidebar.markdown("v1.0.0 | 🌱 种梦计划")


# ── Generate Data ──
@st.cache_data
def load_simulation_data(bt, loc, fa, reg, sy, ey):
    profile = BuildingProfile(
        name=bt,
        floor_area_m2=fa,
        location=loc,
        region=reg,
    )
    sim = BuildingSimulator(profile=profile)
    sim.config.start_year = sy
    sim.config.end_year = ey
    sim.simulate()
    df = pd.DataFrame([{
        "year": d.year,
        "month": d.month,
        "date": f"{d.year}-{d.month:02d}",
        "electricity_kwh": d.electricity_kwh,
        "gas_m3": d.gas_m3,
        "diesel_kg": d.diesel_kg,
        "water_m3": d.water_m3,
        "co2e_kg": d.co2e_kg,
        "hdd": d.hdd,
        "cdd": d.cdd,
        "occupancy": d.occupancy,
        "ambient_temp_c": d.ambient_temp_c,
    } for d in sim.data])

    # Add year-month sort key
    df["ym"] = df["year"] * 100 + df["month"]
    df = df.sort_values("ym")

    # Calculate Scope breakdown
    cal = CarbonCalculator()
    scope_data = []
    for _, row in df.iterrows():
        report = cal.quick_estimate(
            electricity_kwh=row["electricity_kwh"],
            natural_gas_m3=row["gas_m3"],
            diesel_kg=row["diesel_kg"],
            water_m3=row["water_m3"],
            floor_area_m2=fa,
            region=reg,
        )
        scope_data.append({
            "date": row["date"],
            "scope_1": report.scope_1_total,
            "scope_2": report.scope_2_total,
            "scope_3": report.scope_3_total,
            "total": report.grand_total_kg,
            "intensity": report.intensity_kgco2e_per_m2,
        })
    scope_df = pd.DataFrame(scope_data)

    # Stats
    total_co2 = df["co2e_kg"].sum()
    intensity = total_co2 / fa

    return df, scope_df, {
        "total_co2_t": round(total_co2 / 1000, 2),
        "intensity": round(intensity, 2),
        "avg_monthly": round(total_co2 / len(df), 2),
    }


with st.spinner("正在生成模拟数据..."):
    df, scope_df, stats = load_simulation_data(
        building_type, location, floor_area, region,
        sim_years[0], sim_years[1],
    )


# ── Header ──
st.markdown(f'<div class="main-header">🌱 AI 建筑碳管理平台</div>',
            unsafe_allow_html=True)
st.markdown(f'<div class="sub-header">{building_type} | {location} | {floor_area:,.0f} m² | {region}区域</div>',
            unsafe_allow_html=True)

# ── Top Metric Cards ──
col1, col2, col3, col4 = st.columns(4)
with col1:
    st.markdown(
        f'<div class="metric-card">'
        f'<div class="metric-label">总碳排放 (累计)</div>'
        f'<div class="metric-value">{stats["total_co2_t"]:,.2f}</div>'
        f'<div class="metric-unit">吨 CO₂e</div>'
        f'</div>',
        unsafe_allow_html=True,
    )
with col2:
    st.markdown(
        f'<div class="metric-card" style="border-left-color: #60a5fa;">'
        f'<div class="metric-label">碳排放强度</div>'
        f'<div class="metric-value">{stats["intensity"]:,.2f}</div>'
        f'<div class="metric-unit">kg CO₂e / m²</div>'
        f'</div>',
        unsafe_allow_html=True,
    )
with col3:
    latest_total = scope_df["total"].iloc[-1] if len(scope_df) > 0 else 0
    prev_total = scope_df["total"].iloc[-13] if len(scope_df) > 12 else 0
    yoy = ((latest_total - prev_total) / prev_total * 100) if prev_total > 0 else 0
    color = "#f87171" if yoy > 0 else "#4ade80"
    st.markdown(
        f'<div class="metric-card" style="border-left-color: {color};">'
        f'<div class="metric-label">同比变化 (最新月)</div>'
        f'<div class="metric-value" style="color: {color};">{yoy:+.1f}%</div>'
        f'<div class="metric-unit">同比去年同期</div>'
        f'</div>',
        unsafe_allow_html=True,
    )
with col4:
    avg_occ = df["occupancy"].mean()
    st.markdown(
        f'<div class="metric-card" style="border-left-color: #a78bfa;">'
        f'<div class="metric-label">平均入住率</div>'
        f'<div class="metric-value">{avg_occ*100:.0f}%</div>'
        f'<div class="metric-unit">运营状态</div>'
        f'</div>',
        unsafe_allow_html=True,
    )

st.markdown("---")

# ── Row 1: Scope Pie + Trend ──
col1, col2 = st.columns([1, 2])

with col1:
    st.markdown("**📊 Scope 1/2/3 排放占比**")
    scope_totals = {
        "Scope 1 (直接)": scope_df["scope_1"].sum(),
        "Scope 2 (电力/热力)": scope_df["scope_2"].sum(),
        "Scope 3 (其他间接)": scope_df["scope_3"].sum(),
    }
    fig_pie = px.pie(
        names=list(scope_totals.keys()),
        values=list(scope_totals.values()),
        color_discrete_sequence=["#f87171", "#fbbf24", "#60a5fa"],
        hole=0.4,
    )
    fig_pie.update_layout(
        paper_bgcolor="rgba(0,0,0,0)",
        plot_bgcolor="rgba(0,0,0,0)",
        font=dict(color="#e2e8f0"),
        margin=dict(l=10, r=10, t=10, b=10),
        legend=dict(orientation="h", y=-0.1),
    )
    st.plotly_chart(fig_pie, use_container_width=True)

with col2:
    st.markdown("**📈 碳排放月度趋势**")
    trend_df = scope_df.copy()
    trend_df["date"] = pd.to_datetime(trend_df["date"])

    fig_trend = go.Figure()
    fig_trend.add_trace(go.Scatter(
        x=trend_df["date"],
        y=trend_df["scope_1"],
        name="Scope 1",
        line=dict(color="#f87171", width=1.5),
        stackgroup="one",
    ))
    fig_trend.add_trace(go.Scatter(
        x=trend_df["date"],
        y=trend_df["scope_2"],
        name="Scope 2",
        line=dict(color="#fbbf24", width=1.5),
        stackgroup="one",
    ))
    fig_trend.add_trace(go.Scatter(
        x=trend_df["date"],
        y=trend_df["scope_3"],
        name="Scope 3",
        line=dict(color="#60a5fa", width=1.5),
        stackgroup="one",
    ))
    fig_trend.update_layout(
        xaxis_title="",
        yaxis_title="kg CO₂e",
        paper_bgcolor="rgba(0,0,0,0)",
        plot_bgcolor="rgba(0,0,0,0)",
        font=dict(color="#e2e8f0"),
        hovermode="x unified",
        legend=dict(orientation="h", y=1.1),
        margin=dict(l=10, r=10, t=20, b=30),
    )
    st.plotly_chart(fig_trend, use_container_width=True)

# ── Row 2: Energy breakdown + Temp overlay ──
col1, col2 = st.columns(2)

with col1:
    st.markdown("**⚡ 能源消耗结构**")
    energy_totals = {
        "电力 (kWh)": df["electricity_kwh"].sum(),
        "天然气 (m³)": df["gas_m3"].sum(),
        "柴油 (kg)": df["diesel_kg"].sum(),
        "用水 (m³)": df["water_m3"].sum(),
    }
    fig_energy = px.bar(
        x=list(energy_totals.keys()),
        y=list(energy_totals.values()),
        color=list(energy_totals.keys()),
        color_discrete_sequence=["#fbbf24", "#f87171", "#a78bfa", "#60a5fa"],
    )
    fig_energy.update_layout(
        showlegend=False,
        paper_bgcolor="rgba(0,0,0,0)",
        plot_bgcolor="rgba(0,0,0,0)",
        font=dict(color="#e2e8f0"),
        margin=dict(l=10, r=10, t=10, b=30),
        yaxis_title="",
    )
    fig_energy.update_xaxes(tickangle=-20)
    st.plotly_chart(fig_energy, use_container_width=True)

with col2:
    st.markdown("**🌡️ 碳排放 vs 环境温度**")
    temp_df = df.groupby("month").agg({
        "co2e_kg": "mean",
        "ambient_temp_c": "mean",
    }).reset_index()

    fig_temp = go.Figure()
    fig_temp.add_trace(go.Bar(
        x=temp_df["month"],
        y=temp_df["co2e_kg"],
        name="月均碳排放",
        marker_color="#4ade80",
        opacity=0.7,
        yaxis="y",
    ))
    fig_temp.add_trace(go.Scatter(
        x=temp_df["month"],
        y=temp_df["ambient_temp_c"],
        name="月均温度",
        line=dict(color="#f87171", width=2.5),
        yaxis="y2",
    ))
    fig_temp.update_layout(
        xaxis=dict(tickmode="array", tickvals=list(range(1, 13)),
                    ticktext=["1月", "2月", "3月", "4月", "5月", "6月",
                              "7月", "8月", "9月", "10月", "11月", "12月"]),
        yaxis=dict(title="kg CO₂e", side="left"),
        yaxis2=dict(title="°C", overlaying="y", side="right"),
        paper_bgcolor="rgba(0,0,0,0)",
        plot_bgcolor="rgba(0,0,0,0)",
        font=dict(color="#e2e8f0"),
        hovermode="x unified",
        margin=dict(l=10, r=10, t=10, b=30),
    )
    st.plotly_chart(fig_temp, use_container_width=True)

st.markdown("---")

# ── Row 3: Emission Forecast ──
st.markdown("**🔮 碳排放预测 (未来12个月)**")

with st.spinner("正在生��预测..."):
    pred = EmissionPredictor()
    for _, row in df.iterrows():
        pred.add_record(HistoricalRecord(
            date=row["date"] + "-01",
            co2e_kg=row["co2e_kg"],
            electricity_kwh=row["electricity_kwh"],
            gas_m3=row["gas_m3"],
        ))
    forecast = pred.forecast(periods=12, period_type="month")

    forecast_df = pd.DataFrame(forecast.predictions)
    forecast_df["date"] = pd.to_datetime(forecast_df["date"])
    forecast_df["lower"] = forecast.confidence_lower
    forecast_df["upper"] = forecast.confidence_upper

fig_forecast = go.Figure()
fig_forecast.add_trace(go.Scatter(
    x=forecast_df["date"],
    y=forecast_df["predicted_co2e_kg"],
    name="预测值",
    line=dict(color="#4ade80", width=2.5),
    mode="lines+markers",
))
fig_forecast.add_trace(go.Scatter(
    x=forecast_df["date"],
    y=forecast_df["upper"],
    fill=None,
    mode="lines",
    line=dict(color="rgba(74, 222, 128, 0.2)", width=0),
    showlegend=False,
))
fig_forecast.add_trace(go.Scatter(
    x=forecast_df["date"],
    y=forecast_df["lower"],
    fill="tonexty",
    mode="lines",
    line=dict(color="rgba(74, 222, 128, 0.2)", width=0),
    name="95% 置信区间",
))
fig_forecast.update_layout(
    paper_bgcolor="rgba(0,0,0,0)",
    plot_bgcolor="rgba(0,0,0,0)",
    font=dict(color="#e2e8f0"),
    hovermode="x unified",
    margin=dict(l=10, r=10, t=10, b=30),
    yaxis_title="kg CO₂e",
    annotations=[
        dict(
            x=1, y=1.05,
            xref="paper", yref="paper",
            text=f"📊 预测总量: {forecast.total_predicted_tco2e:.2f} tCO₂e | "
                 f"峰值: {forecast.peak_month} ({forecast.peak_value:.0f} kg)",
            showarrow=False,
            font=dict(size=12, color="#94a3b8"),
        )
    ],
)
st.plotly_chart(fig_forecast, use_container_width=True)

st.markdown("---")

# ── Row 4: Reduction Optimization ──
st.markdown("**🎯 减排路径优化推荐**")

current_tco2e = round(df["co2e_kg"].sum() / 1000, 2)
target_pct = st.slider("减排目标 (%)", 10, 60, 30, 5)
max_budget = st.number_input("最大投资预算 (万元)", min_value=0, max_value=2000,
                              value=300, step=50) * 10000

opt = ReductionOptimizer(current_annual_tco2e=current_tco2e)
opt.add_default_measures()
opt_result = opt.optimize(
    reduction_target_percent=target_pct,
    max_budget_cny=max_budget,
)

if opt_result.measures:
    st.markdown(
        f"**当前年排放:** {current_tco2e:.0f} tCO₂e &nbsp;|&nbsp; "
        f"**可减排:** {opt_result.total_reduction_tco2e:.1f} tCO₂e "
        f"({'✅ 达标' if opt_result.target_achieved else '⚠️ 未完全达标'}) &nbsp;|&nbsp; "
        f"**总投资:** ¥{opt_result.total_investment_cny:,.0f} &nbsp;|&nbsp; "
        f"**年节省:** ¥{opt_result.total_annual_saving_cny:,.0f}"
    )

    measures_data = []
    for i, m in enumerate(opt_result.measures, 1):
        measures_data.append({
            "优先级": i,
            "措施": m.name,
            "类别": m.category.value,
            "减排量 (tCO₂e)": m.reduction_potential_tco2e,
            "投资 (万元)": round(m.investment_cost_cny / 10000, 1),
            "年节省 (万元)": round(m.annual_cost_saving_cny / 10000, 1),
            "回收期 (���)": m.payback_years if m.payback_years != float("inf") else "N/A",
            "碳减排成本 (元/t)": m.carbon_abatement_cost_cny_per_tco2e,
            "效果评估": m.cost_effectiveness,
        })

    measures_df = pd.DataFrame(measures_data)
    st.dataframe(measures_df, use_container_width=True, hide_index=True)
else:
    st.info("当前条件下无推荐的减排措施，请调整参数。")

st.markdown("---")

# ── Row 5: Carbon Neutrality Roadmap ──
st.markdown("**🗺️ 碳中和路线图**")

roadmap_steps = []
cumulative_tco2e = 0.0
for i, m in enumerate(opt_result.measures):
    cumulative_tco2e += m.reduction_potential_tco2e
    roadmap_steps.append({
        "阶段": i + 1,
        "措施": m.name,
        "实施周期 (天)": m.implementation_days,
        "累计减排 (tCO₂e)": round(cumulative_tco2e, 1),
        "累计投资 (万元)": round(sum(om.investment_cost_cny for om in opt_result.measures[:i+1]) / 10000, 1),
    })

if roadmap_steps:
    roadmap_df = pd.DataFrame(roadmap_steps)
    fig_roadmap = px.timeline(
        roadmap_df,
        x_start=[0] * len(roadmap_df),
        x_end=roadmap_df["实施周期 (天)"],
        y=roadmap_df["措施"],
        color=roadmap_df["累计减排 (tCO₂e)"],
        color_continuous_scale="greens",
        title="碳中和路线图 — 按实施周期排列",
    )
    fig_roadmap.update_layout(
        paper_bgcolor="rgba(0,0,0,0)",
        plot_bgcolor="rgba(0,0,0,0)",
        font=dict(color="#e2e8f0"),
        xaxis_title="实施天数",
        yaxis_title="",
        coloraxis_colorbar=dict(title="累计减排 tCO₂e"),
        margin=dict(l=10, r=10, t=40, b=30),
    )
    fig_roadmap.update_yashes(autorange="reversed")
    st.plotly_chart(fig_roadmap, use_container_width=True)

st.markdown("---")

# ── Raw Data ──
with st.expander("📋 查看原始数据"):
    display_df = df.copy()
    display_df["co2e_t"] = display_df["co2e_kg"] / 1000
    display_cols = [
        "year", "month", "electricity_kwh", "gas_m3", "diesel_kg",
        "water_m3", "co2e_t", "ambient_temp_c", "occupancy",
    ]
    st.dataframe(
        display_df[display_cols].round(2),
        use_container_width=True,
        hide_index=True,
    )

    csv = df.to_csv(index=False).encode("utf-8")
    st.download_button(
        label="📥 下载 CSV 数据",
        data=csv,
        file_name=f"building_carbon_data_{location}.csv",
        mime="text/csv",
    )
