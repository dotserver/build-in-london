"""Dashboard skeleton. Run with:  uv run streamlit run app/streamlit_app.py"""

import plotly.express as px
import streamlit as st

from house_london_hackathon import load_borough_boundaries

st.set_page_config(page_title="House London!", layout="wide")
st.title("House London! — borough explorer")

boroughs = load_borough_boundaries()
# Placeholder metric: replace with your real borough-level indicator joined on `code`.
boroughs["area_km2"] = boroughs.to_crs(27700).area / 1e6

metric = st.selectbox("Metric", ["area_km2"])
fig = px.choropleth_map(
    boroughs,
    geojson=boroughs.__geo_interface__,
    locations=boroughs.index,
    color=metric,
    hover_name="name",
    map_style="carto-positron",
    center={"lat": 51.49, "lon": -0.11},
    zoom=8.6,
    opacity=0.7,
)
fig.update_layout(margin=dict(l=0, r=0, t=0, b=0), height=600)
st.plotly_chart(fig, width="stretch")
st.dataframe(boroughs.drop(columns="geometry").sort_values(metric, ascending=False))
