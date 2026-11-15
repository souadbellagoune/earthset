[README.md](https://github.com/user-attachments/files/34885698/README.md)
# Earthset: lunar landing site navigator

Built for the NASA Space Apps Challenge 2026, challenge "Lunar Landing Site Navigator".

- Live app: https://earthset-bagbiixzdyfp4xjspyupzx.streamlit.app/
- Companion page (fast two-site view): https://lunar-site-navigator.github.io/lunar-landing-site-navigator/

## What it does

Earthset compares lunar landing sites by the two things that shape a south pole mission: sunlight for power and a line of sight to Earth for communication. It is meant for mission planners, educators and the public.

For each selected site and date window it shows:

- Good, Medium or Poor verdicts for solar power, the Earth link, and both at once
- The Sun and Earth elevation at the start of the window, and the hours until power or the Earth link ends or returns
- A comparison table, with the longest dark spell and the longest Earth-out spell
- What happens if the landing slips by 1, 3 or 7 days
- Elevation plots with the periods when both are usable shaded
- A sky view with a time slider, showing the compass direction and elevation of the Sun and Earth at any hour

## How to use it

1. Pick sites in the sidebar (19 are listed), or add custom coordinates.
2. Set the landing date and the length of the window (1 to 60 days).
3. Pick a possible delay.
4. Set a minimum Sun and Earth elevation if your panels or antenna need some angle above the horizon.

## How the numbers are computed

- Hourly Sun and Earth azimuth and elevation come from the NASA JPL Horizons system, for an observer on the Moon's surface, through the `astroquery` package.
- "Sun up" is the share of hourly steps in the window when the Sun is above the minimum elevation. "Earth up" works the same way, and "both" needs both at once.
- Verdicts: Good is 70% or more of the window, Medium is 30% to 70%, Poor is under 30%. These thresholds are our own choice, not a NASA standard.
- The countdown is the number of hours from the start of the window until the state first changes.
- A delay re-runs the same window shifted by the chosen number of days.

## Limits

- **No terrain.** The Moon is treated as a smooth sphere. Real south pole horizons are shaped by mountains and crater walls, so the results are the best case. A site such as Shackleton, whose floor is permanently shadowed, will still show sunlight. The app shows a warning for sites south of 80 degrees south.
- **Horizons dependency.** The app asks Horizons live. If Horizons is busy, the page shows an error and works again after a minute or two.
- **Hourly resolution.** Events shorter than an hour are not resolved.
- **Site coordinates.** Coordinates for Shackleton, Malapert massif, Connecting Ridge, Nobile and Haworth were read from Quickmap. Odysseus and SLIM come from NASA's lunar landing-site table. The other coordinates are approximate.

## Data and tools

- NASA JPL Horizons System: https://ssd.jpl.nasa.gov/horizons/
- Quickmap (Arizona State University, LROC): used to read site coordinates
- Python, Streamlit, astroquery, pandas, NumPy, Matplotlib, hosted on Streamlit Community Cloud

## Run it locally

```
pip install -r requirements.txt
streamlit run app.py
```



## Credits

Souad: science, direction and review. Melissa: the companion page, whose ideas (delay buttons, side-by-side site cards, simple verdicts) are reflected in this app.

This is an independent project. It is not endorsed or approved by NASA, which is not responsible for its content. Data remain subject to each source's terms of use.

## Next steps

- Add horizon masks from LOLA elevation data, so crater walls and ridges shape the results
- Check every site coordinate against Quickmap and Moon Trek
- Add finer time steps near sunset and Earthset
