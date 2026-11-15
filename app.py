import time
from datetime import date, timedelta

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
import streamlit as st
from astroquery.jplhorizons import Horizons

st.set_page_config(page_title="Earthset: lunar landing site navigator", layout="wide")

# (east longitude in degrees, latitude in degrees). Coordinates are approximate
# and must be checked against Quickmap or Moon Trek before they are cited.
SITES = {
    "Apollo 11 (Mare Tranquillitatis)": (23.47, 0.67),
    "Apollo 17 (Taurus-Littrow)": (30.77, 20.19),
    "Chang'e-4 (Von Karman crater)": (177.59, -45.46),
    "Chandrayaan-3 (near 69.4 S)": (32.32, -69.37),
    "Malapert massif (approx.)": (0.0, -85.9),
    "Near the south pole (illustrative, 89.5 S)": (0.0, -89.5),
}


@st.cache_data(ttl=3600, show_spinner=False)
def fetch_track(body, lon, lat, start_iso, stop_iso):
    """Hourly elevation (degrees) of a body seen from a point on the Moon."""
    loc = {"lon": lon, "lat": lat, "elevation": 0.0, "body": 301}
    epochs = {"start": start_iso, "stop": stop_iso, "step": "1h"}
    last = None
    for attempt in range(3):
        try:
            t = Horizons(id=body, location=loc, epochs=epochs).ephemerides(quantities="4")
            return pd.DataFrame(
                {"jd": np.array(t["datetime_jd"], dtype=float),
                 "el": np.array(t["EL"], dtype=float)}
            )
        except Exception as exc:
            last = exc
            time.sleep(2 * (attempt + 1))
    raise RuntimeError(f"JPL Horizons did not answer: {last}")


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


st.title("Earthset: lunar landing site navigator")
st.write(
    "Compare when the Sun and Earth are above the horizon at candidate landing "
    "sites. The Sun sets the power budget. Earth sets the direct-to-Earth "
    "communication windows."
)

with st.sidebar:
    st.header("Scenario")
    chosen = st.multiselect("Sites", list(SITES), default=list(SITES)[-2:])
    st.caption("Custom site (optional)")
    c_lat = st.number_input("Latitude (deg, south negative)", -90.0, 90.0, 0.0, 0.1)
    c_lon = st.number_input("East longitude (deg)", 0.0, 360.0, 0.0, 0.1)
    use_custom = st.checkbox("Add the custom site")
    start = st.date_input("Start date", value=date.today())
    days = st.slider("Days", 1, 60, 30)
    min_sun = st.slider("Minimum Sun elevation for power (deg)", 0.0, 10.0, 0.0, 0.5)
    min_earth = st.slider("Minimum Earth elevation for comms (deg)", 0.0, 10.0, 0.0, 0.5)

sites = {n: SITES[n] for n in chosen}
if use_custom:
    sites[f"Custom ({c_lat:.2f}, {c_lon:.2f})"] = (c_lon, c_lat)
if not sites:
    st.info("Choose at least one site in the sidebar.")
    st.stop()

start_iso = start.strftime("%Y-%m-%d")
stop_iso = (start + timedelta(days=days)).strftime("%Y-%m-%d")

rows, tracks = [], {}
for name, (lon, lat) in sites.items():
    try:
        with st.spinner(f"Asking JPL Horizons about {name}..."):
            sun = fetch_track("10", lon, lat, start_iso, stop_iso)
            earth = fetch_track("399", lon, lat, start_iso, stop_iso)
    except RuntimeError as exc:
        st.error(f"{name}: {exc}. Wait a minute and reload the page.")
        continue
    n = min(len(sun), len(earth))
    sun, earth = sun.iloc[:n], earth.iloc[:n]
    s = (sun["el"] > min_sun).to_numpy()
    e = (earth["el"] > min_earth).to_numpy()
    tracks[name] = (sun, earth, s, e)
    rows.append({
        "Site": name,
        "Sun up (%)": round(100 * s.mean(), 1),
        "Earth up (%)": round(100 * e.mean(), 1),
        "Both up (%)": round(100 * (s & e).mean(), 1),
        "Longest dark spell (h)": longest_run(~s),
        "Longest Earth-out spell (h)": longest_run(~e),
    })

if not rows:
    st.stop()

st.subheader("Comparison")
st.dataframe(pd.DataFrame(rows).set_index("Site"), width="stretch")

st.subheader("Sun and Earth over the window")
for name, (sun, earth, s, e) in tracks.items():
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
    c1, c2 = st.columns(2)
    c1.write(countdown(s, "Power", "returns", "ends"))
    c2.write(countdown(e, "Earth link", "returns", "ends"))

st.caption(
    "Method: hourly Sun and Earth elevation from JPL Horizons for an observer on "
    "the Moon's surface, no terrain and no atmosphere. Real horizons at the south "
    "pole are shaped by mountains and crater walls, so treat 'up' as the "
    "smooth-sphere case. Site coordinates are approximate. Sources: JPL Horizons "
    "(ssd.jpl.nasa.gov/horizons), Quickmap and Moon Trek for site coordinates."
)
