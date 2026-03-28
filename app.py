import streamlit as st
import pandas as pd
import numpy as np
import plotly.express as px
import plotly.graph_objects as go
from io import BytesIO
from datetime import timedelta

# ─── Page config ───────────────────────────────────────────────────────────────
st.set_page_config(
    page_title="NOMOI · Fairness Intelligence",
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
    st.markdown("**Fairness & Workload Intelligence**")
    st.markdown("---")

    st.markdown("### How to use")
    st.markdown("""
**Step 1 — Export from Kronos**
In Kronos Dimensions / Workforce Central, run the **Timecard Detail** or **Schedule Detail** export for your unit. You need one row per shift (punch-in / punch-out), not a summary.

**Step 2 — Map your columns**
After uploading, NOMOI will ask you to match your column names to the required fields. This takes 30 seconds.

**Step 3 — Read the dashboard**
- 🟢 Green — balanced, safe
- 🟡 Yellow — early warning
- 🔴 Red — immediate action

**Step 4 — Act before publishing**
Use the action table to identify swaps, then make changes in Kronos before the schedule goes live.
    """)

    st.markdown("---")
    st.markdown("### Thresholds")
    st.markdown("""
| Flag | Trigger |
|---|---|
| 🔴 Red | Z > 1.5σ **or** hrs > 185 **or** 3+ consec. nights |
| 🟡 Yellow | Z > 0.5σ **or** hrs > 165 |
| 🟢 Green | Within ±0.5σ and hrs < 165 |

Based on UAE Federal Decree-Law No. 33 of 2021 (48h/week standard).
    """)

    st.markdown("---")
    st.markdown("### Expected CSV columns")
    st.markdown("""
Any export with these data points works — column names don't need to match exactly, you'll map them after upload:

- Employee ID (unique staff identifier)
- Department / unit / ward
- Shift date
- Shift start time (punch-in)
- Shift end time (punch-out)
- Skill level *(optional)*
    """)
    st.markdown("---")
    st.caption("NOMOI MVP v1.0 · SSMC Shadow Pilot · Not connected to any scheduling system")


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
        # First 4 nurses overworked — structural inequity baked in
        pool = list(rng.choice(ids[:4], 3, replace=False)) + \
               list(rng.choice(ids[4:], 7, replace=False))
        for nurse in pool:
            idx = ids.index(nurse)
            night = rng.random() < 0.38
            dur = 14 if rng.random() < 0.18 else 12
            sh = 19 if night else 7
            start = date + timedelta(hours=sh)
            end = start + timedelta(hours=dur)
            rows.append({
                "EmployeeID": nurse,
                "DepartmentCode": depts[idx],
                "ShiftDate": date.date(),
                "StartTime": start,
                "EndTime": end,
                "SkillLevel": skills[idx],
            })
    return pd.DataFrame(rows)


# ─── Cleaning & analytics ───────────────────────────────────────────────────────
@st.cache_data
def process_data(df_raw, col_map):
    df = df_raw.rename(columns={v: k for k, v in col_map.items() if v and v in df_raw.columns})

    required = ["EmployeeID", "StartTime", "EndTime"]
    missing = [c for c in required if c not in df.columns]
    if missing:
        raise ValueError(f"After mapping, still missing columns: {missing}")

    df = df.drop_duplicates()
    df = df.dropna(subset=["StartTime", "EndTime"])

    df["StartTime"] = pd.to_datetime(df["StartTime"], infer_datetime_format=True, errors="coerce")
    df["EndTime"]   = pd.to_datetime(df["EndTime"],   infer_datetime_format=True, errors="coerce")
    df = df.dropna(subset=["StartTime", "EndTime"])

    df["DurationHrs"] = (df["EndTime"] - df["StartTime"]).dt.total_seconds() / 3600
    df = df[df["DurationHrs"].between(1, 24)]  # sanity filter

    df["ShiftDate"]  = pd.to_datetime(df["StartTime"]).dt.date
    df["IsWeekend"]  = df["StartTime"].dt.dayofweek >= 5
    df["IsNight"]    = df["StartTime"].dt.hour >= 19
    df["IsOvertime"] = df["DurationHrs"] > 12

    dept_col = "DepartmentCode" if "DepartmentCode" in df.columns else None

    agg = df.groupby("EmployeeID").agg(
        TotalShifts  = ("ShiftDate", "count"),
        TotalHours   = ("DurationHrs", "sum"),
        WeekendShifts= ("IsWeekend", "sum"),
        NightShifts  = ("IsNight", "sum"),
        OTShifts     = ("IsOvertime", "sum"),
    ).reset_index()

    if dept_col:
        dept_map = df.groupby("EmployeeID")[dept_col].agg(lambda x: x.mode()[0] if len(x) > 0 else "—")
        agg = agg.merge(dept_map.rename("Department"), on="EmployeeID")

    if "SkillLevel" in df.columns:
        skill_map = df.groupby("EmployeeID")["SkillLevel"].agg(lambda x: x.mode()[0] if len(x) > 0 else "—")
        agg = agg.merge(skill_map, on="EmployeeID")

    agg["TotalHours"]    = agg["TotalHours"].round(1)
    agg["DayShifts"]     = agg["TotalShifts"] - agg["NightShifts"] - agg["WeekendShifts"]
    agg["DayShifts"]     = agg["DayShifts"].clip(lower=0)

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
def column_mapper(df):
    st.markdown("### Map your columns")
    st.markdown("Match your Kronos export columns to NOMOI's expected fields. Required fields are marked \\*.")
    cols = ["— not in this file —"] + list(df.columns)

    def best_guess(keywords):
        for c in df.columns:
            if any(k in c.lower() for k in keywords):
                return c
        return cols[0]

    c1, c2, c3 = st.columns(3)
    with c1:
        emp   = st.selectbox("Employee ID *",      cols, index=cols.index(best_guess(["employee", "emp", "person", "id", "staff", "pernr"])))
        dept  = st.selectbox("Department / Unit",  cols, index=cols.index(best_guess(["dept", "unit", "ward", "cost", "comp", "department"])))
    with c2:
        start = st.selectbox("Shift start / punch-in *",  cols, index=cols.index(best_guess(["start", "in", "begin", "from", "punch_in", "punchin"])))
        end   = st.selectbox("Shift end / punch-out *",   cols, index=cols.index(best_guess(["end", "out", "finish", "to", "punch_out", "punchout"])))
    with c3:
        skill = st.selectbox("Skill / grade *(optional)*", cols, index=cols.index(best_guess(["skill", "grade", "level", "seniority", "category"])))

    return {
        "EmployeeID":      emp   if emp   != cols[0] else None,
        "DepartmentCode":  dept  if dept  != cols[0] else None,
        "StartTime":       start if start != cols[0] else None,
        "EndTime":         end   if end   != cols[0] else None,
        "SkillLevel":      skill if skill != cols[0] else None,
    }


# ─── Charts ────────────────────────────────────────────────────────────────────
def scatter_chart(agg):
    fig = px.scatter(
        agg, x="TotalHours", y="ZScore",
        color="RiskFlag",
        color_discrete_map=FLAG_COLORS,
        hover_data={"EmployeeID": True, "TotalHours": True, "ZScore": True, "RiskFlag": True},
        text="EmployeeID",
    )
    fig.update_traces(textposition="top center", textfont_size=8, marker_size=9)
    fig.add_hline(y=0,    line_dash="dash", line_color="#aaa", line_width=1, annotation_text="Dept mean")
    fig.add_hline(y=1.5,  line_dash="dot",  line_color="#e24b4a", line_width=1, annotation_text="Red threshold")
    fig.add_hline(y=-1.5, line_dash="dot",  line_color="#e24b4a", line_width=1)
    fig.add_hline(y=0.5,  line_dash="dot",  line_color="#ef9f27", line_width=1, annotation_text="Yellow threshold")
    fig.update_layout(
        margin=dict(t=20, b=20, l=0, r=0), height=320,
        xaxis_title="Total hours", yaxis_title="Z-score (σ from mean)",
        legend_title="Risk flag", showlegend=True,
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


# ─── Action table ───────────────────────────────────────────────────────────────
def action_table(agg):
    at_risk = agg[agg["RiskFlag"].isin(["Red", "Yellow"])].sort_values("ZScore", ascending=False).copy()
    if at_risk.empty:
        st.success("No at-risk personnel detected. Schedule is balanced.")
        return

    display_cols = ["EmployeeID", "RiskFlag", "TotalHours", "ZScore", "NightShifts", "WeekendShifts", "OTShifts"]
    if "Department" in at_risk.columns:
        display_cols.insert(2, "Department")
    if "SkillLevel" in at_risk.columns:
        display_cols.insert(-1, "SkillLevel")

    display_cols = [c for c in display_cols if c in at_risk.columns]

    def style_flag(val):
        colors = {"Red": "background-color:#ffe0e0;color:#791f1f",
                  "Yellow": "background-color:#fff3cd;color:#633806"}
        return colors.get(val, "")

    styled = at_risk[display_cols].style.applymap(style_flag, subset=["RiskFlag"])
    st.dataframe(styled, use_container_width=True, hide_index=True)

    csv = at_risk[display_cols].to_csv(index=False).encode("utf-8")
    st.download_button(
        label="⬇ Download at-risk list (CSV)",
        data=csv,
        file_name="nomoi_at_risk.csv",
        mime="text/csv",
    )


# ─── Main ───────────────────────────────────────────────────────────────────────
st.markdown("# NOMOI — Fairness & Workload Intelligence")
st.caption("Shadow analytics layer for hospital scheduling · Upload a Kronos or SAP schedule export to begin")

st.divider()

# ── Upload / demo toggle
col_u, col_d = st.columns([3, 1])
with col_u:
    uploaded = st.file_uploader("Upload Kronos / SAP schedule export (CSV)", type=["csv"], label_visibility="collapsed")
with col_d:
    demo_mode = st.checkbox("Use demo data", value=uploaded is None, disabled=uploaded is not None)

# ── Load data
if uploaded is not None:
    try:
        raw_df = pd.read_csv(uploaded)
        st.success(f"Loaded {len(raw_df):,} rows · {raw_df.shape[1]} columns detected")

        with st.expander("Preview raw data (first 10 rows)", expanded=False):
            st.dataframe(raw_df.head(10), use_container_width=True)

        col_map = column_mapper(raw_df)

        if st.button("Run NOMOI analysis", type="primary"):
            with st.spinner("Processing..."):
                try:
                    agg, shift_df, mean_h, std_h = process_data(raw_df, col_map)
                    st.session_state["agg"]      = agg
                    st.session_state["shift_df"] = shift_df
                    st.session_state["mean_h"]   = mean_h
                    st.session_state["std_h"]    = std_h
                    st.session_state["ready"]    = True
                except Exception as e:
                    st.error(f"Processing error: {e}")
                    st.session_state["ready"] = False

        ready = st.session_state.get("ready", False)
        if ready:
            agg      = st.session_state["agg"]
            shift_df = st.session_state["shift_df"]
            mean_h   = st.session_state["mean_h"]
            std_h    = st.session_state["std_h"]
        else:
            st.stop()

    except Exception as e:
        st.error(f"Could not read file: {e}")
        st.stop()

else:
    raw_df = generate_synthetic_data()
    col_map = {k: k for k in ["EmployeeID", "DepartmentCode", "StartTime", "EndTime", "SkillLevel"]}
    agg, shift_df, mean_h, std_h = process_data(raw_df, col_map)
    st.info("Showing synthetic demo data (ICU-Alpha, 15 nurses, 30 days). Upload a real CSV to analyse your unit.")

# ── Department filter (if available)
if "Department" in agg.columns and agg["Department"].nunique() > 1:
    depts = ["All departments"] + sorted(agg["Department"].unique().tolist())
    selected_dept = st.selectbox("Filter by department", depts)
    if selected_dept != "All departments":
        agg      = agg[agg["Department"] == selected_dept]
        shift_df = shift_df[shift_df["EmployeeID"].isin(agg["EmployeeID"])]

st.divider()

# ── KPI cards
red_n    = (agg["RiskFlag"] == "Red").sum()
yellow_n = (agg["RiskFlag"] == "Yellow").sum()
total_h  = int(agg["TotalHours"].sum())

k1, k2, k3, k4, k5 = st.columns(5)
k1.metric("Active nurses",        len(agg))
k2.metric("Total scheduled hrs",  f"{total_h:,}h")
k3.metric("Dept mean",            f"{mean_h}h")
k4.metric("System σ (fairness)",  f"±{std_h}h",  delta="Lower = fairer", delta_color="off")
k5.metric("🔴 Red flag critical", int(red_n),     delta=f"+{yellow_n} yellow" if yellow_n else None, delta_color="inverse")

st.divider()

# ── Charts row 1
st.markdown("## Schedule equity overview")
ch1, ch2 = st.columns(2)

with ch1:
    st.markdown("**Workload fairness distribution**")
    st.caption("Individual Z-score vs total hours · Hover for detail")
    st.plotly_chart(scatter_chart(agg), use_container_width=True)

with ch2:
    st.markdown("**Shift composition per nurse**")
    st.caption("Day / night / weekend split · Sorted by total volume")
    st.plotly_chart(bar_chart(agg), use_container_width=True)

st.divider()

# ── Charts row 2
st.markdown("## Overtime & intervention")
ch3, ch4 = st.columns(2)

with ch3:
    st.markdown("**Overtime intensity heatmap**")
    st.caption("OT instances by day of week · Dark cells = structural scheduling failures")
    hm = heatmap_chart(shift_df, agg)
    if hm:
        st.plotly_chart(hm, use_container_width=True)
    else:
        st.info("No overtime detected in this dataset.")

with ch4:
    st.markdown("**Action required: at-risk personnel**")
    st.caption("Yellow + Red flags only · Sorted by deviation score")
    action_table(agg)

st.divider()

# ── Raw metrics table
with st.expander("Full metrics table (all staff)", expanded=False):
    display = agg.copy()
    display["TotalHours"] = display["TotalHours"].round(1)
    display["ZScore"]     = display["ZScore"].round(2)
    st.dataframe(display, use_container_width=True, hide_index=True)
    full_csv = display.to_csv(index=False).encode("utf-8")
    st.download_button("⬇ Download full metrics (CSV)", full_csv, "nomoi_full_metrics.csv", "text/csv")

st.caption("NOMOI does not write to or connect with Kronos, SAP, or any scheduling system. All data processing is in-session only.")
