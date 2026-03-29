import streamlit as st
import pandas as pd
import numpy as np
import plotly.express as px
import plotly.graph_objects as go
from io import BytesIO
from datetime import timedelta

# ─── Page config ───────────────────────────────────────────────────────────────
st.set_page_config(
    page_title="NOMOI · Schedule Intelligence",
    page_icon="🏥",
    layout="wide",
    initial_sidebar_state="expanded",
)

# ─── CSS ───────────────────────────────────────────────────────────────────────
st.markdown("""
<style>
    .block-container { padding-top: 1.5rem; padding-bottom: 2rem; }
    .stMetric { background: #f8f8f6; border-radius: 8px; padding: 0.75rem 1rem; border-left: 3px solid #888; }
    div[data-testid="stMetricValue"] { font-size: 1.6rem; font-weight: 500; }
    div[data-testid="stMetricLabel"] { font-size: 0.75rem; text-transform: uppercase; letter-spacing: 0.06em; color: #888; }
    .flag-red    { color: #e24b4a; font-weight: 600; }
    .flag-yellow { color: #ba7517; font-weight: 600; }
    .flag-green  { color: #3b6d11; font-weight: 600; }
    h1 { font-size: 1.4rem !important; font-weight: 500 !important; letter-spacing: 0.05em; }
    h2 { font-size: 1rem !important; font-weight: 500 !important; }
    h3 { font-size: 0.9rem !important; font-weight: 500 !important; color: #888; }
</style>
""", unsafe_allow_html=True)

FLAG_COLORS = {"Red": "#e24b4a", "Yellow": "#ef9f27", "Green": "#639922"}

# ─── Sidebar ───────────────────────────────────────────────────────────────────
with st.sidebar:
    st.markdown("## NOMOI")
    st.markdown("**Schedule Intelligence**")
    st.markdown("---")

    app_mode = st.radio(
        "Mode",
        ["🩺 Nursing Fairness", "🧾 Overtime Tracker"],
        index=0,
        help="Nursing Fairness: full equity analytics. Overtime Tracker: streamlined OT view for admin/billing.",
    )
    is_nursing = app_mode.startswith("🩺")

    st.markdown("---")

    st.markdown("### OT calculation")
    ot_method = st.radio(
        "How should overtime be detected?",
        ["Auto (scheduled vs actual)", "Threshold (flat hours)", "Pay Code column"],
        index=0,
        help="Auto: compares scheduled to actual times. Threshold: flags shifts exceeding set hours. Pay Code: reads OT from Kronos.",
    )
    if ot_method.startswith("Threshold"):
        ot_threshold = st.slider("Standard shift length (hrs)", 6, 14, 12 if is_nursing else 8, 1,
                                  help="Shifts exceeding this duration are flagged as OT")
    else:
        ot_threshold = 12 if is_nursing else 8

    ot_weekly_cap = st.number_input("Weekly hours cap (UAE default 48)", value=48, min_value=30, max_value=80, step=1)

    if not is_nursing:
        st.markdown("---")
        st.markdown("### OT cost estimation")
        base_hourly = st.number_input("Base hourly rate (AED)", value=0.0, min_value=0.0, step=10.0,
                                       help="Set to 0 to hide cost estimates.")
        ot_regular_mult = st.number_input("Regular OT multiplier", value=1.25, min_value=1.0, step=0.05,
                                           help="UAE standard: 125%")
        ot_night_mult = st.number_input("Night OT multiplier", value=1.50, min_value=1.0, step=0.05,
                                         help="UAE standard: 150% for 10pm–4am")
    else:
        base_hourly = 0.0
        ot_regular_mult = 1.25
        ot_night_mult = 1.50

    st.markdown("---")

    if is_nursing:
        st.markdown("### How to use")
        st.markdown("""
**Step 1 — Export from Kronos**
Run **Timecard Detail** or **Schedule Detail** export. One row per shift.

**Step 2 — Map your columns**
After uploading, match column names to NOMOI fields (30 sec).

**Step 3 — Current vs proposed**
Upload your current schedule first, then optionally a proposed revision to see impact.

**Step 4 — Read the dashboard**
- 🟢 Green — balanced, safe
- 🟡 Yellow — early warning
- 🔴 Red — immediate action
        """)

        st.markdown("---")
        st.markdown("### Thresholds")
        st.markdown("""
| Flag | Trigger |
|---|---|
| 🔴 Red | Z > 1.5σ **or** hrs > 185 |
| 🟡 Yellow | Z > 0.5σ **or** hrs > 165 |
| 🟢 Green | Within ±0.5σ and hrs < 165 |
        """)
    else:
        st.markdown("### How to use (billing)")
        st.markdown("""
**Step 1 — Export from Kronos**
Run Timecard Detail for your cost centre. One row per shift/punch.

**Step 2 — Map columns**
Employee ID, timestamps, and optionally scheduled times + Pay Code.

**Step 3 — Current vs proposed**
Upload current period first, then optionally a revised schedule.

**Step 4 — Export**
Download OT summary for payroll or your line manager.
        """)

    st.markdown("---")
    st.caption("NOMOI v2.0 · Shadow analytics · Not connected to any scheduling system")


# ─── Synthetic data ─────────────────────────────────────────────────────────────
@st.cache_data
def generate_synthetic_data():
    rng = np.random.default_rng(42)
    ids = [f"RN_{str(i).zfill(3)}" for i in range(1, 16)]
    depts = ["ICU-Alpha"] * 12 + ["ICU-Beta"] * 3
    skills = (["Senior"] * 6 + ["Junior"] * 9)
    rows = []
    base = pd.Timestamp("2026-04-01")
    for day in range(30):
        date = base + timedelta(days=day)
        pool = list(rng.choice(ids[:4], 3, replace=False)) + \
               list(rng.choice(ids[4:], 7, replace=False))
        for nurse in pool:
            idx = ids.index(nurse)
            night = rng.random() < 0.38
            dur = 14 if rng.random() < 0.18 else 12
            sh = 19 if night else 7
            start = date + timedelta(hours=sh)
            end = start + timedelta(hours=dur)
            sched_end = start + timedelta(hours=12)
            rows.append({
                "EmployeeID": nurse,
                "DepartmentCode": depts[idx],
                "ShiftDate": date.date(),
                "ScheduledStart": start,
                "ScheduledEnd": sched_end,
                "StartTime": start,
                "EndTime": end,
                "SkillLevel": skills[idx],
            })
    return pd.DataFrame(rows)


@st.cache_data
def generate_proposed_from_current(shift_df):
    """Simulate a 'proposed' schedule that flattens inequities for demo mode."""
    rng = np.random.default_rng(99)
    df = shift_df.copy()

    hours_per_emp = df.groupby("EmployeeID")["DurationHrs"].sum()
    mean_h = hours_per_emp.mean()

    drop_indices = []
    add_rows = []

    for emp_id in hours_per_emp.index:
        emp_hours = hours_per_emp[emp_id]
        emp_mask = df["EmployeeID"] == emp_id
        emp_rows = df[emp_mask]

        if emp_hours > mean_h * 1.12:
            # Overworked: remove some shifts
            n_drop = max(1, int(len(emp_rows) * 0.12))
            drop_indices.extend(emp_rows.sample(n=min(n_drop, len(emp_rows)), random_state=99).index.tolist())
        elif emp_hours < mean_h * 0.88:
            # Underworked: add shifts
            if len(emp_rows) > 0:
                for _ in range(max(1, int(len(emp_rows) * 0.08))):
                    template = emp_rows.iloc[0].copy()
                    template["ShiftDate"] = template["ShiftDate"] + timedelta(days=int(rng.integers(1, 5)))
                    add_rows.append(template)

    df = df.drop(drop_indices)

    # Trim OT: cap all shifts at 12h
    ot_mask = df["DurationHrs"] > 12
    if ot_mask.any():
        df.loc[ot_mask, "EndTime"] = df.loc[ot_mask, "StartTime"] + pd.to_timedelta("12h")
        df.loc[ot_mask, "DurationHrs"] = 12.0
        if "OTHours" in df.columns:
            df.loc[ot_mask, "OTHours"] = 0.0

    if add_rows:
        df = pd.concat([df, pd.DataFrame(add_rows)], ignore_index=True)

    return df


# ─── Cleaning & analytics ───────────────────────────────────────────────────────
@st.cache_data
def process_data(df_raw, col_map, ot_method_key, ot_thresh, weekly_cap):
    df = df_raw.copy()

    rename_map = {v: k for k, v in col_map.items() if v and v != "— not in this file —" and v in df.columns}
    df = df.rename(columns=rename_map)

    required = ["EmployeeID", "StartTime", "EndTime"]
    missing = [c for c in required if c not in df.columns]
    if missing:
        raise ValueError(f"After mapping, still missing columns: {missing}")

    df = df.drop_duplicates()
    df = df.dropna(subset=["StartTime", "EndTime"])
    df["EmployeeID"] = df["EmployeeID"].astype(str).str.strip()

    df["StartTime"] = pd.to_datetime(df["StartTime"], format="mixed", errors="coerce")
    df["EndTime"]   = pd.to_datetime(df["EndTime"],   format="mixed", errors="coerce")
    df = df.dropna(subset=["StartTime", "EndTime"])

    df["DurationHrs"] = (df["EndTime"] - df["StartTime"]).dt.total_seconds() / 3600
    df = df[df["DurationHrs"].between(0.5, 24)]

    df["ShiftDate"] = df["StartTime"].dt.date
    df["IsWeekend"] = df["StartTime"].dt.dayofweek >= 5
    df["IsNight"]   = df["StartTime"].dt.hour >= 19

    # ── OT calculation by method ──
    has_sched = ("ScheduledStart" in df.columns) and ("ScheduledEnd" in df.columns)
    has_paycode = "PayCode" in df.columns

    if ot_method_key == "Pay Code column" and has_paycode:
        df["OTHours"] = 0.0
        ot_mask = df["PayCode"].astype(str).str.upper().str.contains("OT|OVERTIME|OVER", na=False)
        df.loc[ot_mask, "OTHours"] = df.loc[ot_mask, "DurationHrs"]
        df["IsOvertime"] = ot_mask
    elif ot_method_key == "Auto (scheduled vs actual)" and has_sched:
        df["ScheduledStart"] = pd.to_datetime(df["ScheduledStart"], format="mixed", errors="coerce")
        df["ScheduledEnd"]   = pd.to_datetime(df["ScheduledEnd"],   format="mixed", errors="coerce")
        df["ScheduledHrs"] = (df["ScheduledEnd"] - df["ScheduledStart"]).dt.total_seconds() / 3600
        df["ScheduledHrs"] = df["ScheduledHrs"].clip(lower=0)
        df["OTHours"] = (df["DurationHrs"] - df["ScheduledHrs"]).clip(lower=0)
        df["IsOvertime"] = df["OTHours"] > 0.25
    else:
        # Threshold fallback (also used if Auto selected but no scheduled columns present)
        df["OTHours"] = (df["DurationHrs"] - ot_thresh).clip(lower=0)
        df["IsOvertime"] = df["DurationHrs"] > ot_thresh

    df["IsNightOT"] = df["IsOvertime"] & ((df["StartTime"].dt.hour >= 22) | (df["StartTime"].dt.hour < 4))

    # ── Weekly aggregation for cap-based OT ──
    df["WeekNum"] = df["StartTime"].dt.isocalendar().week.astype(int)
    weekly = df.groupby(["EmployeeID", "WeekNum"])["DurationHrs"].sum().reset_index()
    weekly.columns = ["EmployeeID", "WeekNum", "WeeklyHrs"]
    weekly["WeeklyOT"] = (weekly["WeeklyHrs"] - weekly_cap).clip(lower=0)

    dept_col = "DepartmentCode" if "DepartmentCode" in df.columns else None

    agg = df.groupby("EmployeeID").agg(
        TotalShifts   = ("ShiftDate", "count"),
        TotalHours    = ("DurationHrs", "sum"),
        WeekendShifts = ("IsWeekend", "sum"),
        NightShifts   = ("IsNight", "sum"),
        OTShifts      = ("IsOvertime", "sum"),
        OTHours       = ("OTHours", "sum"),
        NightOTShifts = ("IsNightOT", "sum"),
    ).reset_index()

    weekly_ot_agg = weekly.groupby("EmployeeID")["WeeklyOT"].sum().reset_index()
    weekly_ot_agg.columns = ["EmployeeID", "WeeklyCapOT"]
    agg = agg.merge(weekly_ot_agg, on="EmployeeID", how="left")
    agg["WeeklyCapOT"] = agg["WeeklyCapOT"].fillna(0).round(1)

    if dept_col:
        dept_map = df.groupby("EmployeeID")[dept_col].agg(lambda x: x.mode().iloc[0] if len(x) > 0 else "—")
        agg = agg.merge(dept_map.rename("Department"), on="EmployeeID")

    if "SkillLevel" in df.columns:
        skill_map = df.groupby("EmployeeID")["SkillLevel"].agg(lambda x: x.mode().iloc[0] if len(x) > 0 else "—")
        agg = agg.merge(skill_map, on="EmployeeID")

    agg["TotalHours"] = agg["TotalHours"].round(1)
    agg["OTHours"]    = agg["OTHours"].round(1)
    agg["DayShifts"]  = (agg["TotalShifts"] - agg["NightShifts"] - agg["WeekendShifts"]).clip(lower=0)

    mean_h = agg["TotalHours"].mean()
    std_h  = agg["TotalHours"].std()
    std_h  = std_h if std_h > 0 else 1.0

    agg["ZScore"] = ((agg["TotalHours"] - mean_h) / std_h).round(2)

    def flag(row):
        if row["ZScore"] > 1.5 or row["TotalHours"] > 185:
            return "Red"
        elif row["ZScore"] > 0.5 or row["TotalHours"] > 165:
            return "Yellow"
        return "Green"

    agg["RiskFlag"] = agg.apply(flag, axis=1)

    return agg, df, round(mean_h, 1), round(std_h, 1)


# ─── Column mapping UI ──────────────────────────────────────────────────────────
def column_mapper(df, key_prefix="current"):
    st.markdown("### Map your columns")
    st.markdown("Match your export columns to NOMOI fields. Required \\*. Optional fields unlock better OT detection.")
    cols = ["— not in this file —"] + list(df.columns)

    def best_guess(keywords):
        for c in df.columns:
            if any(k in c.lower() for k in keywords):
                return c
        return cols[0]

    c1, c2, c3, c4 = st.columns(4)
    with c1:
        emp   = st.selectbox("Employee ID *",      cols, index=cols.index(best_guess(["employee", "emp", "person", "id", "staff", "pernr"])), key=f"{key_prefix}_emp")
        dept  = st.selectbox("Department / Unit",  cols, index=cols.index(best_guess(["dept", "unit", "ward", "cost", "comp", "department"])), key=f"{key_prefix}_dept")
    with c2:
        start = st.selectbox("Actual start *",  cols, index=cols.index(best_guess(["start", "in", "begin", "actual_start", "punch_in", "punchin"])), key=f"{key_prefix}_start")
        end   = st.selectbox("Actual end *",    cols, index=cols.index(best_guess(["end", "out", "finish", "actual_end", "punch_out", "punchout"])), key=f"{key_prefix}_end")
    with c3:
        sched_start = st.selectbox("Scheduled start", cols, index=cols.index(best_guess(["sched", "expected_start", "plan_start", "roster_start", "scheduledstart"])), key=f"{key_prefix}_ss")
        sched_end   = st.selectbox("Scheduled end",   cols, index=cols.index(best_guess(["sched", "expected_end", "plan_end", "roster_end", "scheduledend"])), key=f"{key_prefix}_se")
    with c4:
        skill   = st.selectbox("Skill / grade",  cols, index=cols.index(best_guess(["skill", "grade", "level", "seniority", "category"])), key=f"{key_prefix}_skill")
        paycode = st.selectbox("Pay Code",        cols, index=cols.index(best_guess(["pay", "code", "paycode", "pay_code"])), key=f"{key_prefix}_pc")

    return {
        "EmployeeID":      emp         if emp         != cols[0] else None,
        "DepartmentCode":  dept        if dept        != cols[0] else None,
        "StartTime":       start       if start       != cols[0] else None,
        "EndTime":         end         if end         != cols[0] else None,
        "ScheduledStart":  sched_start if sched_start != cols[0] else None,
        "ScheduledEnd":    sched_end   if sched_end   != cols[0] else None,
        "SkillLevel":      skill       if skill       != cols[0] else None,
        "PayCode":         paycode     if paycode     != cols[0] else None,
    }


# ─── Charts ────────────────────────────────────────────────────────────────────
def scatter_chart(agg, proposed_agg=None):
    fig = go.Figure()

    if proposed_agg is not None and not proposed_agg.empty:
        fig.add_trace(go.Scatter(
            x=proposed_agg["TotalHours"], y=proposed_agg["ZScore"],
            mode="markers+text", text=proposed_agg["EmployeeID"],
            textposition="top center", textfont=dict(size=7, color="#aaa"),
            marker=dict(size=11, color=[FLAG_COLORS.get(f, "#ccc") for f in proposed_agg["RiskFlag"]],
                        symbol="diamond", opacity=0.45, line=dict(width=1, color="#fff")),
            name="Proposed",
            hovertemplate="<b>%{text}</b> (Proposed)<br>Hours: %{x:.1f}<br>Z: %{y:.2f}<extra></extra>",
        ))
        # Draw arrows from current to proposed
        for _, row in agg.iterrows():
            p_row = proposed_agg[proposed_agg["EmployeeID"] == row["EmployeeID"]]
            if not p_row.empty:
                p_row = p_row.iloc[0]
                fig.add_annotation(
                    x=p_row["TotalHours"], y=p_row["ZScore"],
                    ax=row["TotalHours"], ay=row["ZScore"],
                    xref="x", yref="y", axref="x", ayref="y",
                    showarrow=True, arrowhead=3, arrowsize=1, arrowwidth=1.2,
                    arrowcolor="#bbb", opacity=0.5,
                )

    fig.add_trace(go.Scatter(
        x=agg["TotalHours"], y=agg["ZScore"],
        mode="markers+text", text=agg["EmployeeID"],
        textposition="top center", textfont=dict(size=8),
        marker=dict(size=9, color=[FLAG_COLORS.get(f, "#ccc") for f in agg["RiskFlag"]]),
        name="Current",
        hovertemplate="<b>%{text}</b> (Current)<br>Hours: %{x:.1f}<br>Z: %{y:.2f}<extra></extra>",
    ))

    fig.add_hline(y=0,    line_dash="dash", line_color="#aaa", line_width=1, annotation_text="Dept mean")
    fig.add_hline(y=1.5,  line_dash="dot",  line_color="#e24b4a", line_width=1, annotation_text="Red threshold")
    fig.add_hline(y=-1.5, line_dash="dot",  line_color="#e24b4a", line_width=1)
    fig.add_hline(y=0.5,  line_dash="dot",  line_color="#ef9f27", line_width=1, annotation_text="Yellow threshold")
    fig.update_layout(
        margin=dict(t=20, b=20, l=0, r=0), height=340,
        xaxis_title="Total hours", yaxis_title="Z-score (σ from mean)",
        legend_title="Schedule version", showlegend=True,
        plot_bgcolor="rgba(0,0,0,0)", paper_bgcolor="rgba(0,0,0,0)",
        font=dict(size=11),
    )
    return fig


def bar_chart(agg):
    plot_df = agg.sort_values("TotalShifts", ascending=True)
    fig = go.Figure()
    fig.add_bar(y=plot_df["EmployeeID"], x=plot_df["DayShifts"],     name="Day shifts",     orientation="h", marker_color="#378add")
    fig.add_bar(y=plot_df["EmployeeID"], x=plot_df["NightShifts"],   name="Night shifts",   orientation="h", marker_color="#185fa5")
    fig.add_bar(y=plot_df["EmployeeID"], x=plot_df["WeekendShifts"], name="Weekend shifts", orientation="h", marker_color="#d85a30")
    fig.update_layout(
        barmode="stack",
        margin=dict(t=20, b=20, l=0, r=0),
        height=max(280, len(agg) * 20 + 60),
        xaxis_title="Shift count", yaxis_title="",
        legend_title="Shift type",
        plot_bgcolor="rgba(0,0,0,0)", paper_bgcolor="rgba(0,0,0,0)",
        font=dict(size=11),
    )
    return fig


def heatmap_chart(shift_df, agg):
    ot_df = shift_df[shift_df["IsOvertime"]].copy()
    if ot_df.empty:
        return None
    ot_df["DayOfWeek"] = pd.to_datetime(ot_df["StartTime"]).dt.day_name()
    ot_cnt = ot_df.groupby(["EmployeeID", "DayOfWeek"]).size().reset_index(name="OTCount")
    day_order = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"]
    fig = px.density_heatmap(
        ot_cnt, x="DayOfWeek", y="EmployeeID", z="OTCount",
        color_continuous_scale="Reds",
        category_orders={"DayOfWeek": day_order},
    )
    fig.update_layout(
        margin=dict(t=20, b=20, l=0, r=0),
        height=max(280, len(agg) * 20 + 60),
        xaxis_title="", yaxis_title="",
        coloraxis_colorbar_title="OT count",
        plot_bgcolor="rgba(0,0,0,0)", paper_bgcolor="rgba(0,0,0,0)",
        font=dict(size=11),
    )
    return fig


def ot_summary_chart(agg, weekly_cap_val):
    plot_df = agg.sort_values("OTHours", ascending=True).copy()
    fig = go.Figure()
    fig.add_bar(y=plot_df["EmployeeID"], x=plot_df["OTHours"],      name="Shift-level OT",           orientation="h", marker_color="#e24b4a")
    fig.add_bar(y=plot_df["EmployeeID"], x=plot_df["WeeklyCapOT"],  name=f"Weekly cap OT (>{weekly_cap_val}h)", orientation="h", marker_color="#ba7517")
    fig.update_layout(
        barmode="group",
        margin=dict(t=20, b=20, l=0, r=0),
        height=max(280, len(agg) * 22 + 60),
        xaxis_title="OT Hours", yaxis_title="",
        legend_title="OT type",
        plot_bgcolor="rgba(0,0,0,0)", paper_bgcolor="rgba(0,0,0,0)",
        font=dict(size=11),
    )
    return fig


# ─── Impact helpers ────────────────────────────────────────────────────────────
def delta_str(current_val, proposed_val, unit=""):
    if proposed_val is None:
        return None
    diff = proposed_val - current_val
    if isinstance(diff, float):
        return f"{diff:+.1f}{unit}"
    return f"{diff:+d}{unit}"


def impact_table(current_agg, proposed_agg):
    merged = current_agg[["EmployeeID", "TotalHours", "OTHours", "ZScore", "RiskFlag", "NightShifts", "WeekendShifts"]].merge(
        proposed_agg[["EmployeeID", "TotalHours", "OTHours", "ZScore", "RiskFlag", "NightShifts", "WeekendShifts"]],
        on="EmployeeID", how="outer", suffixes=("_curr", "_prop"),
    )

    for col in ["TotalHours", "OTHours", "ZScore", "NightShifts", "WeekendShifts"]:
        merged[f"{col}_Δ"] = (merged[f"{col}_prop"].fillna(0) - merged[f"{col}_curr"].fillna(0)).round(1)

    merged["FlagChange"] = merged.apply(
        lambda r: f"{r.get('RiskFlag_curr', '—')} → {r.get('RiskFlag_prop', '—')}"
                  if r.get("RiskFlag_curr") != r.get("RiskFlag_prop") else str(r.get("RiskFlag_curr", "—")),
        axis=1
    )

    display_cols = ["EmployeeID", "FlagChange",
                    "TotalHours_curr", "TotalHours_prop", "TotalHours_Δ",
                    "OTHours_curr", "OTHours_prop", "OTHours_Δ",
                    "ZScore_curr", "ZScore_prop", "ZScore_Δ"]
    display_cols = [c for c in display_cols if c in merged.columns]

    nice_names = {
        "TotalHours_curr": "Hrs (now)", "TotalHours_prop": "Hrs (proposed)", "TotalHours_Δ": "Hrs Δ",
        "OTHours_curr": "OT (now)", "OTHours_prop": "OT (proposed)", "OTHours_Δ": "OT Δ",
        "ZScore_curr": "Z (now)", "ZScore_prop": "Z (proposed)", "ZScore_Δ": "Z Δ",
        "FlagChange": "Risk flag",
    }

    show = merged[display_cols].rename(columns=nice_names)
    sort_col = "OT Δ" if "OT Δ" in show.columns else show.columns[0]
    show = show.sort_values(sort_col)

    def style_delta(val):
        try:
            v = float(val)
            if v < -0.1:
                return "color: #3b6d11; font-weight: 600;"
            elif v > 0.1:
                return "color: #e24b4a; font-weight: 600;"
        except (ValueError, TypeError):
            pass
        return ""

    delta_cols = [c for c in show.columns if "Δ" in c]
    styled = show.style.map(style_delta, subset=delta_cols)
    return styled, merged


# ─── Action table ───────────────────────────────────────────────────────────────
def action_table(agg):
    at_risk = agg[agg["RiskFlag"].isin(["Red", "Yellow"])].sort_values("ZScore", ascending=False).copy()
    if at_risk.empty:
        st.success("No at-risk personnel detected. Schedule is balanced.")
        return

    display_cols = ["EmployeeID", "RiskFlag", "TotalHours", "OTHours", "ZScore", "NightShifts", "WeekendShifts", "OTShifts"]
    if "Department" in at_risk.columns:
        display_cols.insert(2, "Department")
    if "SkillLevel" in at_risk.columns:
        display_cols.insert(-1, "SkillLevel")
    display_cols = [c for c in display_cols if c in at_risk.columns]

    def style_flag(val):
        colors = {"Red": "background-color:#ffe0e0;color:#791f1f",
                  "Yellow": "background-color:#fff3cd;color:#633806"}
        return colors.get(val, "")

    styled = at_risk[display_cols].style.map(style_flag, subset=["RiskFlag"])
    st.dataframe(styled, use_container_width=True, hide_index=True)

    csv = at_risk[display_cols].to_csv(index=False).encode("utf-8")
    st.download_button("⬇ Download at-risk list (CSV)", data=csv, file_name="nomoi_at_risk.csv", mime="text/csv")


# ─── OT billing export ────────────────────────────────────────────────────────
def ot_billing_export(agg, shift_df, base_rate, reg_mult, night_mult):
    ot_export = agg[["EmployeeID", "TotalShifts", "TotalHours", "OTShifts", "OTHours", "NightOTShifts", "WeeklyCapOT"]].copy()
    if "Department" in agg.columns:
        ot_export.insert(1, "Department", agg["Department"])

    if base_rate > 0:
        ot_export["RegularOT_AED"] = ((ot_export["OTHours"] - ot_export["NightOTShifts"] * 2) .clip(lower=0) * base_rate * reg_mult).round(2)
        ot_export["NightOT_AED"]   = (ot_export["NightOTShifts"] * 2 * base_rate * night_mult).round(2)
        ot_export["TotalOT_AED"]   = (ot_export["RegularOT_AED"] + ot_export["NightOT_AED"]).round(2)

    st.dataframe(ot_export, use_container_width=True, hide_index=True)
    csv = ot_export.to_csv(index=False).encode("utf-8")
    st.download_button("⬇ Download OT report (CSV)", data=csv, file_name="nomoi_ot_report.csv", mime="text/csv",
                       help="One row per employee. Ready for payroll.")


# ──────────────────────────────────────────────────────────────────────────────
# ─── MAIN ────────────────────────────────────────────────────────────────────
# ──────────────────────────────────────────────────────────────────────────────

mode_label = "Nursing Fairness" if is_nursing else "Overtime Tracker"
st.markdown(f"# NOMOI — {mode_label}")
st.caption("Shadow analytics · Upload current schedule, then optionally a proposed revision to see impact")
st.divider()

# ── Upload area
col_u1, col_u2, col_d = st.columns([2, 2, 1])
with col_u1:
    uploaded_current = st.file_uploader("📂 Current schedule (CSV)", type=["csv"], key="upload_current")
with col_u2:
    uploaded_proposed = st.file_uploader("📂 Proposed schedule (CSV)", type=["csv"], key="upload_proposed",
                                          help="Same format as current. Upload to compare impact.")
with col_d:
    demo_mode = st.checkbox("Use demo data", value=uploaded_current is None, disabled=uploaded_current is not None)

has_proposed = False

# ── Load & process ──
if uploaded_current is not None:
    try:
        raw_df = pd.read_csv(uploaded_current)
        st.success(f"Current: {len(raw_df):,} rows · {raw_df.shape[1]} columns")

        with st.expander("Preview current data (first 10 rows)", expanded=False):
            st.dataframe(raw_df.head(10), use_container_width=True)

        col_map = column_mapper(raw_df, key_prefix="current")

        raw_proposed = None
        if uploaded_proposed:
            raw_proposed = pd.read_csv(uploaded_proposed)
            st.success(f"Proposed: {len(raw_proposed):,} rows · {raw_proposed.shape[1]} columns")

        if st.button("Run NOMOI analysis", type="primary"):
            with st.spinner("Processing current schedule..."):
                try:
                    agg, shift_df, mean_h, std_h = process_data(raw_df, col_map, ot_method, ot_threshold, ot_weekly_cap)
                    st.session_state["agg"]      = agg
                    st.session_state["shift_df"] = shift_df
                    st.session_state["mean_h"]   = mean_h
                    st.session_state["std_h"]    = std_h
                    st.session_state["ready"]    = True

                    if raw_proposed is not None:
                        with st.spinner("Processing proposed schedule..."):
                            p_agg, p_shift, p_mean, p_std = process_data(raw_proposed, col_map, ot_method, ot_threshold, ot_weekly_cap)
                            st.session_state["p_agg"]    = p_agg
                            st.session_state["p_shift"]  = p_shift
                            st.session_state["p_mean"]   = p_mean
                            st.session_state["p_std"]    = p_std
                            st.session_state["has_proposed"] = True
                    else:
                        st.session_state["has_proposed"] = False

                except Exception as e:
                    st.error(f"Processing error: {e}")
                    st.session_state["ready"] = False

        ready = st.session_state.get("ready", False)
        if ready:
            agg      = st.session_state["agg"]
            shift_df = st.session_state["shift_df"]
            mean_h   = st.session_state["mean_h"]
            std_h    = st.session_state["std_h"]
            has_proposed = st.session_state.get("has_proposed", False)
            if has_proposed:
                p_agg   = st.session_state["p_agg"]
                p_shift = st.session_state["p_shift"]
                p_mean  = st.session_state["p_mean"]
                p_std   = st.session_state["p_std"]
        else:
            st.stop()

    except Exception as e:
        st.error(f"Could not read file: {e}")
        st.stop()

else:
    # Demo mode
    raw_df = generate_synthetic_data()
    col_map = {k: k for k in ["EmployeeID", "DepartmentCode", "StartTime", "EndTime", "ScheduledStart", "ScheduledEnd", "SkillLevel"]}
    agg, shift_df, mean_h, std_h = process_data(raw_df, col_map, ot_method, ot_threshold, ot_weekly_cap)

    proposed_shift_df = generate_proposed_from_current(shift_df)
    p_agg, p_shift, p_mean, p_std = process_data(proposed_shift_df, col_map, ot_method, ot_threshold, ot_weekly_cap)
    has_proposed = True

    st.info("Demo mode: synthetic current + auto-generated proposed schedule. Upload a real CSV to analyse your unit.")

# ── Department filter
if "Department" in agg.columns and agg["Department"].nunique() > 1:
    depts = ["All departments"] + sorted(agg["Department"].unique().tolist())
    selected_dept = st.selectbox("Filter by department", depts)
    if selected_dept != "All departments":
        agg      = agg[agg["Department"] == selected_dept]
        shift_df = shift_df[shift_df["EmployeeID"].isin(agg["EmployeeID"])]
        if has_proposed and "Department" in p_agg.columns:
            p_agg   = p_agg[p_agg["Department"] == selected_dept]
            p_shift = p_shift[p_shift["EmployeeID"].isin(p_agg["EmployeeID"])]

# ── Employee filter (supports single-nurse uploads)
all_employees = sorted(agg["EmployeeID"].unique().tolist())
if len(all_employees) > 1:
    emp_options = ["All staff"] + all_employees
    selected_emp = st.selectbox("Filter by employee", emp_options,
                                 help="Single employee view or full unit.")
    if selected_emp != "All staff":
        agg      = agg[agg["EmployeeID"] == selected_emp]
        shift_df = shift_df[shift_df["EmployeeID"] == selected_emp]
        if has_proposed:
            p_agg   = p_agg[p_agg["EmployeeID"] == selected_emp]
            p_shift = p_shift[p_shift["EmployeeID"] == selected_emp]

st.divider()

# ──────────────────────────────────────────────────────────────────────────────
# ─── KPI CARDS ───────────────────────────────────────────────────────────────
# ──────────────────────────────────────────────────────────────────────────────

red_n    = int((agg["RiskFlag"] == "Red").sum())
yellow_n = int((agg["RiskFlag"] == "Yellow").sum())
total_h  = int(agg["TotalHours"].sum())
total_ot = round(float(agg["OTHours"].sum()), 1)

k1, k2, k3, k4, k5 = st.columns(5)

if has_proposed:
    p_red_n    = int((p_agg["RiskFlag"] == "Red").sum())
    p_total_h  = int(p_agg["TotalHours"].sum())
    p_total_ot = round(float(p_agg["OTHours"].sum()), 1)
    p_std_val  = p_std

    k1.metric("Active nurses",       len(agg),           delta=delta_str(len(agg), len(p_agg)))
    k2.metric("Total scheduled hrs", f"{total_h:,}h",    delta=delta_str(total_h, p_total_h, "h"))
    k3.metric("System σ (fairness)", f"±{std_h}h",       delta=delta_str(std_h, p_std_val, "h"), delta_color="inverse")
    k4.metric("Total OT hours",      f"{total_ot}h",     delta=delta_str(total_ot, p_total_ot, "h"), delta_color="inverse")
    k5.metric("🔴 Red flags",        red_n,               delta=delta_str(red_n, p_red_n), delta_color="inverse")
else:
    k1.metric("Active nurses",       len(agg))
    k2.metric("Total scheduled hrs", f"{total_h:,}h")
    k3.metric("System σ (fairness)", f"±{std_h}h",       delta="Lower = fairer", delta_color="off")
    k4.metric("Total OT hours",      f"{total_ot}h")
    k5.metric("🔴 Red flags",        red_n,               delta=f"+{yellow_n} yellow" if yellow_n else None, delta_color="inverse")

if has_proposed:
    st.caption("📊 KPI deltas show proposed vs current. Green ↓ in σ, OT, and red flags = improvement.")

st.divider()

# ──────────────────────────────────────────────────────────────────────────────
# ─── IMPACT TABLE ────────────────────────────────────────────────────────────
# ──────────────────────────────────────────────────────────────────────────────

if has_proposed:
    st.markdown("## Impact analysis: current → proposed")
    st.caption("Per-employee comparison. Green Δ = improvement (less hours/OT/risk). Red Δ = regression.")
    styled_impact, impact_raw = impact_table(agg, p_agg)
    st.dataframe(styled_impact, use_container_width=True, hide_index=True)

    csv_impact = impact_raw.to_csv(index=False).encode("utf-8")
    st.download_button("⬇ Download impact report (CSV)", data=csv_impact, file_name="nomoi_impact_report.csv", mime="text/csv")
    st.divider()


# ──────────────────────────────────────────────────────────────────────────────
# ─── NURSING FAIRNESS PANELS ─────────────────────────────────────────────────
# ──────────────────────────────────────────────────────────────────────────────

if is_nursing:
    st.markdown("## Schedule equity overview")
    ch1, ch2 = st.columns(2)

    with ch1:
        st.markdown("**Workload fairness distribution**")
        label = "Circles = current · Diamonds = proposed" if has_proposed else "Individual Z-score vs total hours"
        st.caption(label)
        proposed_for_chart = p_agg if has_proposed else None
        st.plotly_chart(scatter_chart(agg, proposed_for_chart), use_container_width=True)

    with ch2:
        st.markdown("**Shift composition per nurse**")
        st.caption("Day / night / weekend split · Sorted by total volume")
        st.plotly_chart(bar_chart(agg), use_container_width=True)

    st.divider()

    st.markdown("## Overtime & intervention")
    ch3, ch4 = st.columns(2)

    with ch3:
        st.markdown("**Overtime intensity heatmap**")
        st.caption("OT by day of week · Dark cells = structural failures")
        hm = heatmap_chart(shift_df, agg)
        if hm:
            st.plotly_chart(hm, use_container_width=True)
        else:
            st.info("No overtime detected in this dataset.")

    with ch4:
        st.markdown("**Action required: at-risk personnel**")
        st.caption("Yellow + Red flags · Sorted by deviation score")
        action_table(agg)

    st.divider()

    with st.expander("Full metrics table (all staff)", expanded=False):
        display = agg.copy()
        st.dataframe(display, use_container_width=True, hide_index=True)
        full_csv = display.to_csv(index=False).encode("utf-8")
        st.download_button("⬇ Download full metrics (CSV)", full_csv, "nomoi_full_metrics.csv", "text/csv")


# ──────────────────────────────────────────────────────────────────────────────
# ─── OVERTIME TRACKER PANELS (billing mode) ──────────────────────────────────
# ──────────────────────────────────────────────────────────────────────────────

if not is_nursing:
    st.markdown("## Overtime breakdown")
    ot1, ot2 = st.columns(2)

    with ot1:
        st.markdown("**OT hours per employee**")
        st.caption("Shift-level OT vs weekly-cap OT")
        st.plotly_chart(ot_summary_chart(agg, ot_weekly_cap), use_container_width=True)

    with ot2:
        st.markdown("**OT heatmap by day**")
        st.caption("When does OT cluster?")
        hm = heatmap_chart(shift_df, agg)
        if hm:
            st.plotly_chart(hm, use_container_width=True)
        else:
            st.info("No overtime detected.")

    st.divider()

    st.markdown("## OT report & export")
    ot_billing_export(agg, shift_df, base_hourly, ot_regular_mult, ot_night_mult)

    if has_proposed:
        st.divider()
        st.markdown("## Proposed schedule OT comparison")
        cur_ot_val = round(float(agg["OTHours"].sum()), 1)
        p_ot_val   = round(float(p_agg["OTHours"].sum()), 1)
        diff_ot    = round(p_ot_val - cur_ot_val, 1)
        col_s1, col_s2, col_s3 = st.columns(3)
        col_s1.metric("Current total OT", f"{cur_ot_val}h")
        col_s2.metric("Proposed total OT", f"{p_ot_val}h", delta=f"{diff_ot:+.1f}h", delta_color="inverse")
        if base_hourly > 0:
            savings = abs(diff_ot) * base_hourly * ot_regular_mult if diff_ot < 0 else 0
            col_s3.metric("Est. OT savings", f"{savings:,.0f} AED" if savings > 0 else "—")

        st.markdown("**Proposed OT per employee**")
        st.plotly_chart(ot_summary_chart(p_agg, ot_weekly_cap), use_container_width=True)


# ──────────────────────────────────────────────────────────────────────────────
# ─── SHIFT-LEVEL EXPORT (one row per shift) ──────────────────────────────────
# ──────────────────────────────────────────────────────────────────────────────

st.divider()
with st.expander("📋 Shift-level export (one row per shift)", expanded=False):
    st.caption("Mirrors your upload granularity — one row per shift, OT fields appended.")
    export_cols = ["EmployeeID", "ShiftDate", "StartTime", "EndTime", "DurationHrs",
                   "IsWeekend", "IsNight", "IsOvertime", "OTHours"]
    if "DepartmentCode" in shift_df.columns:
        export_cols.insert(1, "DepartmentCode")
    if "ScheduledStart" in shift_df.columns:
        export_cols.insert(export_cols.index("StartTime"), "ScheduledStart")
    if "ScheduledEnd" in shift_df.columns:
        export_cols.insert(export_cols.index("EndTime"), "ScheduledEnd")
    export_cols = [c for c in export_cols if c in shift_df.columns]

    st.dataframe(shift_df[export_cols].head(50), use_container_width=True, hide_index=True)
    shift_csv = shift_df[export_cols].to_csv(index=False).encode("utf-8")
    st.download_button("⬇ Download shift-level data (CSV)", data=shift_csv, file_name="nomoi_shifts.csv", mime="text/csv")

st.caption("NOMOI does not write to or connect with Kronos, SAP, or any scheduling system. All data processing is in-session only.")
