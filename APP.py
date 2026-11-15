# Earthset: lunar landing site navigator (NASA Space Apps Challenge 2026).
# Code written with the assistance of Claude (Anthropic), an AI assistant,
# under the direction of the team (Souad and Melissa).
# Sun and Earth positions come from NASA JPL Horizons via the astroquery package.
import time
from datetime import date, timedelta

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
import streamlit as st
from astroquery.jplhorizons import Horizons

st.set_page_config(page_title="Earthset: lunar landing site navigator", layout="wide")

# (east longitude in degrees, latitude in degrees).
# Shackleton, Malapert Massif, Connecting Ridge, Nobile and Haworth were read from
# Quickmap. Odysseus and SLIM come from NASA's lunar landing-site table.
# The other coordinates are approximate.
SITES = {
    "Apollo 11 (Mare Tranquillitatis)": (23.47, 0.67),
    "Apollo 17 (Taurus-Littrow)": (30.77, 20.19),
    "Chang'e-4 (Von Karman crater)": (177.59, -45.46),
    "Chandrayaan-3 (near 69.4 S)": (32.32, -69.37),
    "Malapert massif (approx.)": (359.76, -85.98),
    "Near the south pole (illustrative, 89.5 S)": (0.0, -89.5),
    "Shackleton crater (center, real floor is permanently shadowed)": (129.78, -89.67),
    "Nobile crater (center)": (53.27, -85.28),
    "Haworth (Artemis III candidate region, center)": (337.22, -86.76),
    "Connecting Ridge (Artemis candidate region)": (222.5, -89.46),
    "Odysseus / IM-1 (Malapert A, CLPS)": (1.44, -80.13),
    "Apollo 12 (Oceanus Procellarum)": (336.58, -3.01),
    "Apollo 14 (Fra Mauro)": (342.53, -3.65),
    "Apollo 15 (Hadley-Apennine)": (3.63, 26.13),
    "Apollo 16 (Descartes)": (15.50, -8.97),
    "Chang'e-3 (Mare Imbrium)": (340.49, 44.12),
    "Chang'e-5 (Oceanus Procellarum)": (308.08, 43.06),
    "Chang'e-6 (Apollo basin)": (206.01, -41.64),
    "SLIM (near Shioli crater)": (25.25, -13.32),
}

# Verdict thresholds: share of the window with the Sun / Earth usable.
# These are the team's own choice, not a NASA standard.
GOOD, MEDIUM = 70.0, 30.0


@st.cache_data(ttl=3600, show_spinner=False)
def fetch_track(body, lon, lat, start_iso, stop_iso):
    """Hourly azimuth and elevation (degrees) of a body seen from the Moon's surface."""
    loc = {"lon": lon, "lat": lat, "elevation": 0.0, "body": 301}
    epochs = {"start": start_iso, "stop": stop_iso, "step": "1h"}
    last = None
    for attempt in range(3):
        try:
            t = Horizons(id=body, location=loc, epochs=epochs).ephemerides(quantities="4")
            return pd.DataFrame(
                {"jd": np.array(t["datetime_jd"], dtype=float),
                 "az": np.array(t["AZ"], dtype=float),
                 "el": np.array(t["EL"], dtype=float)}
            )
        except Exception as exc:
            last = exc
            time.sleep(2 * (attempt + 1))
    raise RuntimeError(f"JPL Horizons did not answer: {last}")


def get_window(lon, lat, start, days):
    start_iso = start.strftime("%Y-%m-%d")
    stop_iso = (start + timedelta(days=days)).strftime("%Y-%m-%d")
    sun = fetch_track("10", lon, lat, start_iso, stop_iso)
    earth = fetch_track("399", lon, lat, start_iso, stop_iso)
    n = min(len(sun), len(earth))
    return sun.iloc[:n].reset_index(drop=True), earth.iloc[:n].reset_index(drop=True)


def longest_run(mask):
    best = cur = 0
    for m in mask:
        cur = cur + 1 if m else 0
        best = max(best, cur)
    return best  # hourly steps, so this is hours


def hours_to_change(mask):
    """Hours until the state at the first step flips, or None."""
    flip = int(np.argmax(mask != mask[0]))
    return flip if mask[flip] != mask[0] else None


def countdown(mask, name, up_word, down_word):
    h = hours_to_change(mask)
    if h is None:
        state = "up" if mask[0] else "down"
        return f"{name} stays {state} for the whole window"
    word = down_word if mask[0] else up_word
    return f"{name} {word} in {h} h ({h / 24:.1f} days)"


def metrics(sun, earth, min_sun, min_earth):
    s = (sun["el"] > min_sun).to_numpy()
    e = (earth["el"] > min_earth).to_numpy()
    return {
        "s": s, "e": e,
        "sun": 100 * s.mean(), "earth": 100 * e.mean(), "both": 100 * (s & e).mean(),
        "dark": longest_run(~s), "earth_out": longest_run(~e),
    }


def verdict(pct):
    if pct >= GOOD:
        return "🟢 Good"
    if pct >= MEDIUM:
        return "🟡 Medium"
    return "🔴 Poor"


st.title("Earthset: lunar landing site navigator")
st.write(
    "Compare when the Sun and Earth are above the horizon at candidate landing "
    "sites. The Sun sets the power budget. Earth sets the direct-to-Earth "
    "communication windows. Pick sites, a landing date and a possible delay."
)
st.markdown(
    "Want a fast two-site view that loads instantly? Open the companion page: "
    "[Lunar Landing Site Navigator]"
    "(https://lunar-site-navigator.github.io/lunar-landing-site-navigator/)."
)

with st.sidebar:
    st.header("Scenario")
    chosen = st.multiselect(
        "Sites",
        list(SITES),
        default=[
            "Apollo 11 (Mare Tranquillitatis)",
            "Malapert massif (approx.)",
            "Near the south pole (illustrative, 89.5 S)",
        ],
    )
    st.caption("Custom site (optional)")
    c_lat = st.number_input("Latitude (deg, south negative)", -90.0, 90.0, 0.0, 0.1)
    c_lon = st.number_input("East longitude (deg)", 0.0, 360.0, 0.0, 0.1)
    use_custom = st.checkbox("Add the custom site")
    start = st.date_input("Landing date (start of the window)", value=date(2026, 11, 15))
    days = st.slider("Days in the window", 1, 60, 30)
    delay = st.radio(
        "What if the landing slips?", [0, 1, 3, 7], horizontal=True,
        format_func=lambda d: "No delay" if d == 0 else (f"+{d} day" if d == 1 else f"+{d} days"),
    )
    min_sun = st.slider("Minimum Sun elevation for power (deg)", 0.0, 10.0, 0.0, 0.5)
    min_earth = st.slider("Minimum Earth elevation for comms (deg)", 0.0, 10.0, 0.0, 0.5)

sites = {n: SITES[n] for n in chosen}
if use_custom:
    sites[f"Custom ({c_lat:.2f}, {c_lon:.2f})"] = (c_lon, c_lat)
if not sites:
    st.info("Choose at least one site in the sidebar.")
    st.stop()

data = {}
for name, (lon, lat) in sites.items():
    try:
        with st.spinner(f"Asking JPL Horizons about {name}..."):
            sun, earth = get_window(lon, lat, start, days)
            m = metrics(sun, earth, min_sun, min_earth)
            md = None
            if delay:
                sun_d, earth_d = get_window(lon, lat, start + timedelta(days=delay), days)
                md = metrics(sun_d, earth_d, min_sun, min_earth)
    except RuntimeError as exc:
        st.error(f"{name}: {exc}. Wait a minute and reload the page.")
        continue
    data[name] = {"sun": sun, "earth": earth, "m": m, "md": md}

if not data:
    st.stop()

# ---------- Site cards, side by side ----------
st.subheader("Site cards")
names = list(data)
for i in range(0, len(names), 3):
    group = names[i:i + 3]
    cols = st.columns(len(group))
    for col, name in zip(cols, group):
        d = data[name]
        m = d["m"]
        with col, st.container(border=True):
            st.markdown(f"**{name}**")
            st.markdown(f"Solar power: {verdict(m['sun'])} ({m['sun']:.0f}% of the window)")
            st.markdown(f"Earth link: {verdict(m['earth'])} ({m['earth']:.0f}%)")
            st.markdown(f"Both at once: {verdict(m['both'])} ({m['both']:.0f}%)")
            c1, c2 = st.columns(2)
            c1.metric("Sun at start", f"{d['sun']['el'].iloc[0]:.1f}°")
            c2.metric("Earth at start", f"{d['earth']['el'].iloc[0]:.1f}°")
            st.caption(countdown(m["s"], "Power", "returns", "ends"))
            st.caption(countdown(m["e"], "Earth link", "returns", "ends"))
            if d["md"] is not None:
                md = d["md"]
                st.markdown(
                    f"**If the landing slips {delay} {'day' if delay == 1 else 'days'}:** power {verdict(md['sun'])} "
                    f"({md['sun']:.0f}%), Earth link {verdict(md['earth'])} "
                    f"({md['earth']:.0f}%), both {verdict(md['both'])} ({md['both']:.0f}%)"
                )

with st.expander("How the verdicts are defined"):
    st.write(
        f"Each verdict uses the share of the window (hourly steps) when the Sun, "
        f"Earth, or both are above the minimum elevation set in the sidebar. "
        f"Good: {GOOD:.0f}% or more. Medium: {MEDIUM:.0f}% to {GOOD:.0f}%. "
        f"Poor: under {MEDIUM:.0f}%. These thresholds are the team's own choice, "
        f"not a NASA standard. Verdicts describe a smooth Moon with no terrain."
    )

# ---------- Tables ----------
st.subheader("Comparison")
rows = [{
    "Site": n,
    "Sun up (%)": round(d["m"]["sun"], 1),
    "Earth up (%)": round(d["m"]["earth"], 1),
    "Both up (%)": round(d["m"]["both"], 1),
    "Longest dark spell (h)": d["m"]["dark"],
    "Longest Earth-out spell (h)": d["m"]["earth_out"],
} for n, d in data.items()]
st.dataframe(pd.DataFrame(rows).set_index("Site"), width="stretch")

if delay:
    st.subheader(f"Effect of a {delay}-day delay (% of the window)")
    rows = []
    for n, d in data.items():
        if d["md"] is None:
            continue
        rows.append({
            "Site": n,
            "Sun now": round(d["m"]["sun"], 1),
            "Sun delayed": round(d["md"]["sun"], 1),
            "Earth now": round(d["m"]["earth"], 1),
            "Earth delayed": round(d["md"]["earth"], 1),
            "Both now": round(d["m"]["both"], 1),
            "Both delayed": round(d["md"]["both"], 1),
        })
    st.dataframe(pd.DataFrame(rows).set_index("Site"), width="stretch")

# ---------- Elevation plots ----------
st.subheader("Sun and Earth over the window")
for name, d in data.items():
    sun, earth = d["sun"], d["earth"]
    s, e = d["m"]["s"], d["m"]["e"]
    times = pd.to_datetime(sun["jd"], origin="julian", unit="D")
    fig, ax = plt.subplots(figsize=(11, 3.2))
    ax.plot(times, sun["el"], label="Sun", color="#e69f00")
    ax.plot(times, earth["el"], label="Earth", color="#0072b2")
    ax.axhline(0, color="k", lw=0.8)
    both = s & e
    ax.fill_between(times, -90, 90, where=both, color="green", alpha=0.15,
                    label="Sun and Earth both usable")
    lim = max(5.0, float(np.nanmax(np.abs(np.r_[sun["el"], earth["el"]]))) * 1.1)
    ax.set_ylim(-lim, lim)
    ax.set_ylabel("Elevation (deg)")
    ax.set_title(name)
    ax.legend(loc="upper right", ncol=3, fontsize=8)
    fig.autofmt_xdate()
    st.pyplot(fig)
    plt.close(fig)

# ---------- Sky view ----------
st.subheader("Sky view at a chosen moment")
pick = st.selectbox("Site", list(data))
sun, earth = data[pick]["sun"], data[pick]["earth"]
hour = st.slider("Hours from the landing date", 0, len(sun) - 1, 0)
when = pd.to_datetime(sun["jd"].iloc[hour], origin="julian", unit="D")
fig, ax = plt.subplots(figsize=(11, 4.6))
ax.scatter(sun["az"], sun["el"], s=6, color="#e69f00", alpha=0.35, label="Sun (whole window)")
ax.scatter(earth["az"], earth["el"], s=6, color="#0072b2", alpha=0.35, label="Earth (whole window)")
ax.scatter(sun["az"].iloc[hour], sun["el"].iloc[hour], s=170, color="#e69f00",
           edgecolor="k", zorder=5, label="Sun at the chosen time")
ax.scatter(earth["az"].iloc[hour], earth["el"].iloc[hour], s=170, color="#0072b2",
           edgecolor="k", zorder=5, label="Earth at the chosen time")
ax.axhline(0, color="k", lw=1)
ax.fill_between([0, 360], -90, 0, color="grey", alpha=0.25)
ax.set_xlim(0, 360)
ax.set_xticks(range(0, 361, 45))
ax.set_xticklabels(["N", "NE", "E", "SE", "S", "SW", "W", "NW", "N"])
top = float(np.nanmax(np.r_[sun["el"], earth["el"]]))
bottom = float(np.nanmin(np.r_[sun["el"], earth["el"]]))
ax.set_ylim(min(-2.0, bottom - 1), max(4.0, top + 1))
ax.set_xlabel("Compass direction")
ax.set_ylabel("Elevation (deg)")
ax.set_title(f"{pick} at {when:%Y-%m-%d %H:%M} UTC: grey is below the horizon")
ax.legend(loc="upper center", bbox_to_anchor=(0.5, -0.2), ncol=4, fontsize=8)
fig.subplots_adjust(bottom=0.3)
st.pyplot(fig)
plt.close(fig)
st.write(
    f"Sun: {sun['el'].iloc[hour]:.1f} deg elevation, compass {sun['az'].iloc[hour]:.0f} deg. "
    f"Earth: {earth['el'].iloc[hour]:.1f} deg elevation, compass {earth['az'].iloc[hour]:.0f} deg."
)

st.caption(
    "Method: hourly Sun and Earth elevation from JPL Horizons for an observer on "
    "the Moon's surface, no terrain and no atmosphere. Real horizons at the south "
    "pole are shaped by mountains and crater walls, so treat 'up' as the "
    "smooth-sphere case. Coordinates for Shackleton, Malapert Massif, Connecting "
    "Ridge, Nobile and Haworth were read from Quickmap; Odysseus and SLIM come "
    "from NASA's landing-site table; other site coordinates are approximate. "
    "Sources: JPL Horizons (ssd.jpl.nasa.gov/horizons), Quickmap and Moon Trek."
)
