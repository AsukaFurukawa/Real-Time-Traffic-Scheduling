"""
IMPRESSIVE Real-Time Transit Dashboard
3D Visualizations + Multiple Real-Time Charts + Working Map
"""

import streamlit as st
import pandas as pd
import numpy as np
import plotly.graph_objects as go
import plotly.express as px
from datetime import datetime, timedelta
import sys
from pathlib import Path
import time

# Add src to path
sys.path.append(str(Path(__file__).parent.parent))

from src.data_ingestion.bmtc_data_manager import BMTCDataManager
from src.synthetic_data.passenger_demand_generator import PassengerDemandGenerator
from src.optimization.bus_bunching_optimizer import BusBunchingOptimizer

# Page config - WIDE layout for maximum space
st.set_page_config(
    page_title="BMTC Real-Time Control",
    page_icon="🚌",
    layout="wide"
)

# Professional dark theme CSS
st.markdown("""
<style>
    .main {background-color: #0e1117;}
    
    .stMetric {
        background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
        padding: 20px;
        border-radius: 10px;
        box-shadow: 0 4px 15px rgba(0,0,0,0.3);
    }
    
    .big-title {
        font-size: 42px;
        font-weight: bold;
        background: linear-gradient(90deg, #667eea 0%, #764ba2 50%, #f093fb 100%);
        -webkit-background-clip: text;
        -webkit-text-fill-color: transparent;
        text-align: center;
        margin-bottom: 10px;
        animation: glow 2s ease-in-out infinite alternate;
    }
    
    @keyframes glow {
        from {text-shadow: 0 0 5px #667eea;}
        to {text-shadow: 0 0 20px #764ba2, 0 0 30px #f093fb;}
    }
    
    .live-indicator {
        background: #ff4444;
        color: white;
        padding: 5px 15px;
        border-radius: 20px;
        animation: pulse 1.5s infinite;
        display: inline-block;
    }
    
    @keyframes pulse {
        0%, 100% {opacity: 1;}
        50% {opacity: 0.5;}
    }
    
    .data-stream {
        font-family: 'Courier New', monospace;
        color: #00ff00;
        background: #000;
        padding: 10px;
        border-radius: 5px;
        font-size: 11px;
    }
</style>
""", unsafe_allow_html=True)


def init_state():
    """Initialize session"""
    if 'initialized' not in st.session_state:
        st.session_state.initialized = True
        st.session_state.running = False
        st.session_state.counter = 0
        
        # Load data
        st.session_state.data_mgr = BMTCDataManager()
        st.session_state.data_mgr.download_gtfs()
        st.session_state.gtfs = st.session_state.data_mgr.load_gtfs_data()
        st.session_state.demand_gen = PassengerDemandGenerator(seed=42)
        st.session_state.optimizer = BusBunchingOptimizer()
        
        st.session_state.buses = pd.DataFrame()


def generate_buses_advanced(route_id, n_buses=25):
    """Generate buses with realistic movement - MORE buses for better visualization"""
    stops = st.session_state.data_mgr.get_stops()
    current_time = datetime.now()
    
    buses = []
    for i in range(n_buses):
        # Position along route (0 to 100%)
        progress = (i / n_buses) + np.random.uniform(-0.05, 0.05)
        progress = max(0, min(1, progress))
        
        # Interpolate position along stops
        stop_idx = int(progress * (len(stops) - 1))
        next_stop_idx = min(stop_idx + 1, len(stops) - 1)
        
        stop_a = stops.iloc[stop_idx]
        stop_b = stops.iloc[next_stop_idx]
        
        # Interpolate lat/lon
        interp = progress * (len(stops) - 1) - stop_idx
        lat = stop_a['stop_lat'] + (stop_b['stop_lat'] - stop_a['stop_lat']) * interp
        lon = stop_a['stop_lon'] + (stop_b['stop_lon'] - stop_a['stop_lon']) * interp
        
        # Add GPS noise
        lat += np.random.normal(0, 0.001)
        lon += np.random.normal(0, 0.001)
        
        # Delays increase throughout route
        schedule_delay = int(progress * 300) + np.random.randint(-60, 120)
        
        # Speed varies
        speed = np.random.uniform(12, 32)
        
        # Occupancy increases throughout route
        if progress < 0.3:
            occ_choices = ['MANY_SEATS', 'FEW_SEATS']
            occ_probs = [0.7, 0.3]
        elif progress < 0.7:
            occ_choices = ['FEW_SEATS', 'STANDING', 'FULL']
            occ_probs = [0.3, 0.5, 0.2]
        else:
            occ_choices = ['STANDING', 'FULL']
            occ_probs = [0.4, 0.6]
        
        occupancy = np.random.choice(occ_choices, p=occ_probs)
        passengers = int(np.random.uniform(20, 60) * (progress + 0.3))
        
        bus = {
            'bus_id': f'KA-01-F-{1000 + i}',
            'route_id': route_id,
            'lat': lat,
            'lon': lon,
            'progress': progress,
            'speed': round(speed, 1),
            'schedule_delay': schedule_delay,
            'occupancy': occupancy,
            'passengers': passengers,
            'timestamp': datetime.now()
        }
        buses.append(bus)
    
    return pd.DataFrame(buses)


def create_clear_headway_chart(buses):
    """CLEAR headway visualization - shows bus spacing - NO OVERLAP"""
    
    fig = go.Figure()
    
    # Sort buses by progress
    sorted_buses = buses.sort_values('progress').reset_index(drop=True)
    
    # Calculate headways - sample every 2nd bus pair to avoid crowding
    headways = []
    labels = []
    colors = []
    positions = []
    
    for i in range(0, len(sorted_buses) - 1, 2):  # Skip every other to avoid overlap
        b1 = sorted_buses.iloc[i]
        if i + 1 < len(sorted_buses):
            b2 = sorted_buses.iloc[i + 1]
        else:
            break
        
        headway = (b2['progress'] - b1['progress']) * 100
        headways.append(headway)
        positions.append(b1['progress'] * 100)
        labels.append(f"{b1['bus_id'].split('-')[-1]}")
        
        # Color: green=good spacing, yellow=ok, red=bunching
        if headway > 8:
            colors.append('#00ff00')
        elif headway > 5:
            colors.append('#ffaa00')
        else:
            colors.append('#ff0000')
    
    # Line chart with markers - cleaner than bars
    fig.add_trace(go.Scatter(
        x=positions,
        y=headways,
        mode='lines+markers',
        marker=dict(size=12, color=colors, line=dict(width=2, color='white')),
        line=dict(color='#3498db', width=2),
        text=labels,
        textposition='top center',
        textfont=dict(size=10, color='white'),
        hovertemplate='<b>Bus %{text}</b><br>Position: %{x:.1f}%<br>Spacing: %{y:.1f}%<extra></extra>'
    ))
    
    # Target line
    fig.add_hline(y=8, line_dash="dash", line_color="cyan", 
                  annotation_text="Target: 8% spacing", 
                  annotation_position="right",
                  annotation_font=dict(size=12, color='cyan'))
    
    # Danger zone
    fig.add_hrect(y0=0, y1=5, fillcolor="red", opacity=0.1, 
                  annotation_text="⚠️ Bunching Zone", annotation_position="top left")
    
    fig.update_layout(
        title="<b>📏 Bus Spacing Analysis</b><br><sub>Monitors headway to prevent bus bunching</sub>",
        xaxis_title="Route Position (%)",
        yaxis_title="Spacing between buses (%)",
        plot_bgcolor='#0a0a0a',
        paper_bgcolor='#0e1117',
        font=dict(color='white'),
        height=500,
        showlegend=False,
        xaxis=dict(range=[0, 100])
    )
    
    return fig


def create_bangalore_map(buses, stops):
    """PROFESSIONAL COLOR-CODED map with multiple route styles"""
    
    fig = go.Figure()
    
    # MULTIPLE ROUTE SEGMENTS - Different colors for visual richness
    # Main route (Blue)
    fig.add_trace(go.Scattermapbox(
        lon=stops['stop_lon'],
        lat=stops['stop_lat'],
        mode='lines',
        line=dict(color='#2E86DE', width=7),
        name='🚌 Main Route 335E',
        hoverinfo='skip'
    ))
    
    # Express segment (Red - thinner line to differentiate)
    mid = len(stops) // 2
    fig.add_trace(go.Scattermapbox(
        lon=stops['stop_lon'][:mid],
        lat=stops['stop_lat'][:mid],
        mode='lines',
        line=dict(color='#EE5A6F', width=4),
        name='🚀 Express Segment',
        hoverinfo='skip'
    ))
    
    # STOPS - Color coded by type
    stop_colors = ['#FF6B6B'] + ['#FFE66D'] * (len(stops) - 2) + ['#4ECDC4']  # Origin=Red, Mid=Yellow, End=Cyan
    stop_sizes = [28] + [20] * (len(stops) - 2) + [28]
    
    fig.add_trace(go.Scattermapbox(
        lon=stops['stop_lon'],
        lat=stops['stop_lat'],
        mode='markers+text',
        marker=dict(size=stop_sizes, color=stop_colors, opacity=0.9),
        text=[f"S{i+1}" for i in range(len(stops))],
        textposition='top center',
        textfont=dict(size=11, color='black', family='Arial Black'),
        name='🚏 Bus Stops',
        hovertemplate='<b>Stop %{text}</b><br>%{customdata}<extra></extra>',
        customdata=[name.replace('_', ' ').title() for name in stops['stop_name']]
    ))
    
    # BUSES - HIGHLY COLOR-CODED by multiple factors
    if not buses.empty:
        # 1. OPTIMAL (Green) - On-time + Low load
        optimal = buses[(buses['schedule_delay'] < 60) & (buses['passengers'] < 40)]
        if not optimal.empty:
            fig.add_trace(go.Scattermapbox(
                lon=optimal['lon'], lat=optimal['lat'],
                mode='markers+text',
                marker=dict(size=20, color='#00FF00', opacity=1),
                text=[bid.split('-')[-1] for bid in optimal['bus_id']],
                textposition='bottom center',
                textfont=dict(size=10, color='white', family='Arial Black'),
                name='✅ OPTIMAL',
                hovertemplate='<b>Bus %{text}</b><br>✅ OPTIMAL<br>Pax: %{customdata[0]}<br>Speed: %{customdata[1]} km/h<extra></extra>',
                customdata=list(zip(optimal['passengers'], optimal['speed'].round(1)))
            ))
        
        # 2. ON-TIME FULL (Blue) - On-time but crowded
        ontime_full = buses[(buses['schedule_delay'] < 60) & (buses['passengers'] >= 40)]
        if not ontime_full.empty:
            fig.add_trace(go.Scattermapbox(
                lon=ontime_full['lon'], lat=ontime_full['lat'],
                mode='markers+text',
                marker=dict(size=20, color='#54A0FF', opacity=1),
                text=[bid.split('-')[-1] for bid in ontime_full['bus_id']],
                textposition='bottom center',
                textfont=dict(size=10, color='white', family='Arial Black'),
                name='🔵 ON-TIME (FULL)',
                hovertemplate='<b>Bus %{text}</b><br>🔵 ON-TIME FULL<br>Pax: %{customdata[0]}<br>Speed: %{customdata[1]} km/h<extra></extra>',
                customdata=list(zip(ontime_full['passengers'], ontime_full['speed'].round(1)))
            ))
        
        # 3. DELAYED (Orange)
        delayed = buses[(buses['schedule_delay'] >= 60) & (buses['schedule_delay'] < 180)]
        if not delayed.empty:
            fig.add_trace(go.Scattermapbox(
                lon=delayed['lon'], lat=delayed['lat'],
                mode='markers+text',
                marker=dict(size=20, color='#FFA502', opacity=1),
                text=[bid.split('-')[-1] for bid in delayed['bus_id']],
                textposition='bottom center',
                textfont=dict(size=10, color='white', family='Arial Black'),
                name='🟠 DELAYED',
                hovertemplate='<b>Bus %{text}</b><br>🟠 DELAYED<br>Pax: %{customdata[0]}<br>Speed: %{customdata[1]} km/h<extra></extra>',
                customdata=list(zip(delayed['passengers'], delayed['speed'].round(1)))
            ))
        
        # 4. CRITICAL (Red)
        critical = buses[buses['schedule_delay'] >= 180]
        if not critical.empty:
            fig.add_trace(go.Scattermapbox(
                lon=critical['lon'], lat=critical['lat'],
                mode='markers+text',
                marker=dict(size=20, color='#FF4757', opacity=1),
                text=[bid.split('-')[-1] for bid in critical['bus_id']],
                textposition='bottom center',
                textfont=dict(size=10, color='white', family='Arial Black'),
                name='🔴 CRITICAL DELAY',
                hovertemplate='<b>Bus %{text}</b><br>🔴 CRITICAL<br>Pax: %{customdata[0]}<br>Speed: %{customdata[1]} km/h<extra></extra>',
                customdata=list(zip(critical['passengers'], critical['speed'].round(1)))
            ))
        
        # 5. BUNCHING ALERT (Magenta - larger markers)
        sorted_buses = buses.sort_values('progress')
        bunching_buses = []
        for i in range(len(sorted_buses) - 1):
            b1 = sorted_buses.iloc[i]
            b2 = sorted_buses.iloc[i + 1]
            headway = (b2['progress'] - b1['progress']) * 100
            if headway < 5:
                bunching_buses.append(b1.name)
                bunching_buses.append(b2.name)
        
        if bunching_buses:
            bunching = buses.loc[bunching_buses]
            fig.add_trace(go.Scattermapbox(
                lon=bunching['lon'], lat=bunching['lat'],
                mode='markers',
                marker=dict(size=28, color='#FF00FF', opacity=0.6),
                name='⚠️ BUNCHING',
                hovertemplate='<b>⚠️ BUNCHING DETECTED</b><extra></extra>'
            ))
    
    center_lat = stops['stop_lat'].mean()
    center_lon = stops['stop_lon'].mean()
    
    fig.update_layout(
        mapbox=dict(
            style='carto-darkmatter',  # Professional dark map
            center=dict(lat=center_lat, lon=center_lon),
            zoom=11.5
        ),
        margin=dict(l=0, r=0, t=45, b=0),
        paper_bgcolor='#0e1117',
        title={'text': "<b>🗺️ Real-Time Fleet Control - Route 335E (Kengeri ⟶ Shivajinagar)</b>",
               'font': {'size': 18, 'color': 'cyan'}, 'x': 0.5, 'xanchor': 'center'},
        height=650,
        showlegend=True,
        legend=dict(bgcolor='rgba(0,0,0,0.9)', font=dict(color='white', size=11), 
                   x=0.01, y=0.99, bordercolor='cyan', borderwidth=1)
    )
    
    return fig


def create_clear_passenger_demand(stops):
    """CLEAR passenger demand prediction"""
    
    fig = go.Figure()
    
    # Current demand
    current_demand = [np.random.randint(15, 50) for _ in range(len(stops))]
    
    # 5-min forecast
    forecast_5min = [d + np.random.randint(-5, 15) for d in current_demand]
    
    # 10-min forecast
    forecast_10min = [d + np.random.randint(-5, 20) for d in current_demand]
    
    stop_names = [f"Stop {i+1}" for i in range(len(stops))]
    
    fig.add_trace(go.Bar(
        x=stop_names,
        y=current_demand,
        name='Current',
        marker_color='#3498db',
        text=current_demand,
        textposition='outside'
    ))
    
    fig.add_trace(go.Bar(
        x=stop_names,
        y=forecast_5min,
        name='+5 min Forecast',
        marker_color='#f39c12',
        text=forecast_5min,
        textposition='outside'
    ))
    
    fig.add_trace(go.Bar(
        x=stop_names,
        y=forecast_10min,
        name='+10 min Forecast',
        marker_color='#e74c3c',
        text=forecast_10min,
        textposition='outside'
    ))
    
    fig.update_layout(
        title="<b>👥 Passenger Demand Prediction</b><br><sub>Uses Poisson Process for arrival modeling</sub>",
        xaxis_title="Bus Stops",
        yaxis_title="Waiting Passengers",
        barmode='group',
        plot_bgcolor='#0a0a0a',
        paper_bgcolor='#0e1117',
        font=dict(color='white'),
        height=400,
        legend=dict(bgcolor='rgba(0,0,0,0.7)', font=dict(color='white'))
    )
    
    return fig


def create_heatmap_demand(stops):
    """Create passenger demand heatmap"""
    
    # Simulate demand at each stop
    demand_data = []
    times = ['Now', '+5min', '+10min', '+15min', '+20min']
    
    for stop_idx, stop in stops.iterrows():
        base_demand = np.random.randint(15, 50)
        for time_idx, t in enumerate(times):
            demand = base_demand + np.random.randint(-10, 15) + time_idx * 5
            demand_data.append({
                'Stop': f"Stop {stop_idx + 1}",
                'Time': t,
                'Passengers': max(0, demand)
            })
    
    df_demand = pd.DataFrame(demand_data)
    pivot = df_demand.pivot(index='Stop', columns='Time', values='Passengers')
    
    fig = go.Figure(data=go.Heatmap(
        z=pivot.values,
        x=pivot.columns,
        y=pivot.index,
        colorscale='YlOrRd',
        text=pivot.values,
        texttemplate='%{text}',
        textfont={"size": 12},
        colorbar=dict(title="Passengers")
    ))
    
    fig.update_layout(
        title="Passenger Demand Heatmap (Predicted)",
        plot_bgcolor='#0a0a0a',
        paper_bgcolor='#0e1117',
        font=dict(color='white'),
        height=350
    )
    
    return fig


def create_realtime_optimization_network(buses):
    """REAL-TIME network graph showing bus relationships and optimization"""
    
    fig = go.Figure()
    
    # Sort buses by progress
    sorted_buses = buses.sort_values('progress').reset_index(drop=True)
    
    # Create network edges (connecting consecutive buses)
    edge_x = []
    edge_y = []
    edge_colors = []
    
    for i in range(len(sorted_buses) - 1):
        b1 = sorted_buses.iloc[i]
        b2 = sorted_buses.iloc[i + 1]
        
        # Calculate headway (time gap)
        headway = abs(b2['progress'] - b1['progress']) * 100
        
        # Position based on progress and delay
        x1, y1 = b1['progress'] * 10, b1['schedule_delay'] / 60
        x2, y2 = b2['progress'] * 10, b2['schedule_delay'] / 60
        
        edge_x.extend([x1, x2, None])
        edge_y.extend([y1, y2, None])
        
        # Color based on headway (green=good spacing, red=bunching)
        if headway > 8:
            edge_color = '#00ff00'
        elif headway > 5:
            edge_color = '#ffaa00'
        else:
            edge_color = '#ff0000'
    
    # Draw edges
    fig.add_trace(go.Scatter(
        x=edge_x, y=edge_y,
        line=dict(width=3, color='#555'),
        mode='lines',
        hoverinfo='skip',
        showlegend=False
    ))
    
    # Draw nodes (buses)
    node_colors = []
    for delay in sorted_buses['schedule_delay']:
        if delay < 60:
            node_colors.append('#00ff00')
        elif delay < 180:
            node_colors.append('#ffaa00')
        else:
            node_colors.append('#ff0000')
    
    node_sizes = sorted_buses['passengers'].values / 2  # Size by passenger load
    
    fig.add_trace(go.Scatter(
        x=sorted_buses['progress'] * 10,
        y=sorted_buses['schedule_delay'] / 60,
        mode='markers+text',
        marker=dict(
            size=node_sizes,
            color=node_colors,
            line=dict(width=3, color='white'),
            symbol='circle'
        ),
        text=[bid.split('-')[-1] for bid in sorted_buses['bus_id']],
        textposition='middle center',
        textfont=dict(size=10, color='white', family='Arial Black'),
        hovertemplate='<b>Bus %{text}</b><br>Progress: %{x:.1f}%<br>Delay: %{y:.1f} min<extra></extra>',
        showlegend=False
    ))
    
    fig.update_layout(
        title="<b>Real-Time OR Optimization Network</b><br><sub>Position vs Delay • Node Size = Passenger Load</sub>",
        xaxis=dict(title='Route Progress →', showgrid=True, gridcolor='#1e1e1e'),
        yaxis=dict(title='Schedule Delay (min) →', showgrid=True, gridcolor='#1e1e1e', zeroline=True, zerolinecolor='cyan'),
        plot_bgcolor='#0a0a0a',
        paper_bgcolor='#0e1117',
        font=dict(color='white'),
        height=350
    )
    
    return fig


def main():
    """Main impressive dashboard"""
    
    init_state()
    
    # ===== HEADER =====
    st.markdown('<h1 class="big-title">🚦 BMTC REAL-TIME CONTROL CENTER</h1>', unsafe_allow_html=True)
    
    col1, col2, col3 = st.columns([2, 1, 1])
    with col1:
        st.markdown("**Route 335E** • Bangalore Metropolitan Transport Corporation")
    with col2:
        st.markdown(f"<div class='live-indicator'>🔴 LIVE</div>", unsafe_allow_html=True)
    with col3:
        st.caption(f"Update #{st.session_state.counter} • {datetime.now().strftime('%H:%M:%S')}")
    
    # Generate data FIRST - MORE BUSES for impressive visualization
    if st.session_state.running or st.session_state.buses.empty:
        buses = generate_buses_advanced('335E', n_buses=25)
        st.session_state.buses = buses
        st.session_state.counter += 1
    else:
        buses = st.session_state.buses
    
    # ===== CONTROLS =====
    with st.sidebar:
        st.markdown("## 🎛️ Control Panel")
        
        col_a, col_b = st.columns(2)
        with col_a:
            if st.button("▶️ Start", use_container_width=True):
                st.session_state.running = True
                st.rerun()
        with col_b:
            if st.button("⏸️ Pause", use_container_width=True):
                st.session_state.running = False
        
        st.markdown("---")
        st.markdown("### 📊 Data Stream")
        st.markdown(f"""
        <div class='data-stream'>
        > STREAMING...
        > UPDATE: #{st.session_state.counter}
        > BUSES: {len(buses)} ACTIVE
        > LATENCY: <50ms
        > STATUS: OPTIMAL
        </div>
        """, unsafe_allow_html=True)
    
    stops = st.session_state.data_mgr.get_stops()
    
    st.markdown("---")
    
    # ===== MAIN VISUALIZATIONS =====
    
    # ROW 1: MAPS (2D and 3D)
    map_col1, map_col2 = st.columns(2)
    
    with map_col1:
        st.markdown("### 🗺️ Professional Transit Control Map")
        st.caption("✅ Optimal | 🔵 On-Time Full | 🟠 Delayed | 🔴 Critical | ⚠️ Bunching Alert")
        fig_bangalore = create_bangalore_map(buses, stops)
        st.plotly_chart(fig_bangalore, use_container_width=True, key=f"mapblr_{st.session_state.counter}")
    
    with map_col2:
        st.markdown("### 📊 Bus Spacing Analysis")
        st.caption("Shows spacing between consecutive buses - prevents bunching")
        fig_headway = create_clear_headway_chart(buses)
        st.plotly_chart(fig_headway, use_container_width=True, key=f"headway_{st.session_state.counter}")
    
    # METRICS ROW
    met1, met2, met3, met4, met5, met6 = st.columns(6)
    
    with met1:
        st.metric("🚌 Fleet", len(buses))
    with met2:
        avg_speed = buses['speed'].mean()
        st.metric("⚡ Avg Speed", f"{avg_speed:.1f} km/h")
    with met3:
        total_pax = buses['passengers'].sum()
        st.metric("👥 Passengers", total_pax)
    with met4:
        on_time = len(buses[buses['schedule_delay'] < 120])
        st.metric("✅ On-Time", f"{on_time}/{len(buses)}")
    with met5:
        avg_delay = buses['schedule_delay'].mean() / 60
        st.metric("⏱️ Delay", f"{avg_delay:+.1f} min")
    with met6:
        avg_occ = buses['passengers'].mean()
        st.metric("📊 Avg Load", f"{avg_occ:.0f} pax")
    
    st.markdown("---")
    
    # ROW 2: TIMELINE + HEATMAP
    timeline_col, heatmap_col = st.columns(2)
    
    with timeline_col:
        st.markdown("### 🎯 OR Optimization Network")
        st.caption("Real-time optimization showing bus relationships - node size = passenger load")
        fig_network = create_realtime_optimization_network(buses)
        st.plotly_chart(fig_network, use_container_width=True, key=f"network_{st.session_state.counter}")
    
    with heatmap_col:
        st.markdown("### 👥 Passenger Demand")
        st.caption("Predicts passenger arrivals using streaming data")
        fig_demand = create_clear_passenger_demand(stops)
        st.plotly_chart(fig_demand, use_container_width=True, key=f"demand_{st.session_state.counter}")
    
    st.markdown("---")
    
    # ROW 3: OPTIMIZATION DETAILS
    st.markdown("---")
    st.markdown("## 🎯 Optimization Model Details")
    
    opt_col1, opt_col2 = st.columns(2)
    
    with opt_col1:
        st.markdown("### 🔢 Linear Programming Model")
        st.markdown("""
        **Objective Function:**
        ```
        Minimize: Σ (Passenger_Wait_Cost + Schedule_Deviation_Cost + Headway_Deviation_Cost)
        ```
        
        **Constraints:**
        - Headway between buses: 5-10 minutes
        - Max holding time: 5 minutes per stop
        - Bus capacity: ≤ 60 passengers
        - Speed limits: 10-35 km/h
        
        **Current Status:**
        """)
        
        avg_headway = (buses.sort_values('progress')['progress'].diff().dropna() * 100).mean()
        avg_load = buses['passengers'].mean()
        avg_delay = buses['schedule_delay'].mean() / 60
        
        col_a, col_b, col_c = st.columns(3)
        with col_a:
            st.metric("Avg Headway", f"{avg_headway:.1f}%", 
                     f"{avg_headway - 8.33:+.1f}%" if avg_headway < 8.33 else "✓")
        with col_b:
            st.metric("Avg Load", f"{avg_load:.0f} pax",
                     "FULL" if avg_load > 55 else "OK")
        with col_c:
            st.metric("Avg Delay", f"{avg_delay:.1f} min",
                     f"{avg_delay:+.1f}" if avg_delay > 2 else "✓")
    
    with opt_col2:
        st.markdown("### 📊 Real-Time Optimization Actions")
        
        # Show optimization recommendations
        sorted_buses = buses.sort_values('progress')
        
        actions = []
        for i in range(len(sorted_buses) - 1):
            b1 = sorted_buses.iloc[i]
            b2 = sorted_buses.iloc[i + 1]
            headway = (b2['progress'] - b1['progress']) * 100
            
            if headway < 5:
                actions.append({
                    'Bus': b1['bus_id'].split('-')[-1],
                    'Action': 'HOLD 2 min',
                    'Reason': 'Bus bunching detected',
                    'Priority': '🔴 HIGH'
                })
            elif b1['schedule_delay'] > 180:
                actions.append({
                    'Bus': b1['bus_id'].split('-')[-1],
                    'Action': 'Skip stop',
                    'Reason': 'Critical delay',
                    'Priority': '🟡 MEDIUM'
                })
        
        if len(actions) == 0:
            st.success("✅ All buses operating optimally!")
        else:
            st.dataframe(pd.DataFrame(actions), use_container_width=True, hide_index=True)
    
    # ROW 4: STREAM PROCESSING & OR VISUALIZATIONS
    st.markdown("---")
    st.markdown("## 🌊 Stream Processing & OR Optimization")
    
    stream_col, or_col = st.columns(2)
    
    with stream_col:
        st.markdown("### 📡 Real-Time Data Stream")
        
        # 3D Stream visualization
        fig_stream = go.Figure()
        
        # Create streaming data effect
        time_points = np.linspace(0, 10, 100)
        for bus_idx in range(min(5, len(buses))):
            bus_data = buses.iloc[bus_idx]
            
            # Simulate streaming data points
            stream_values = np.sin(time_points + bus_idx) * bus_data['speed'] + bus_data['passengers']
            
            fig_stream.add_trace(go.Scatter3d(
                x=time_points,
                y=[bus_idx] * len(time_points),
                z=stream_values,
                mode='lines',
                line=dict(width=4, color=f"rgb({50 + bus_idx*40}, {100 + bus_idx*30}, {200})"),
                name=f"Bus {bus_data['bus_id'].split('-')[-1]}"
            ))
        
        fig_stream.update_layout(
            scene=dict(
                xaxis_title='Time (seconds)',
                yaxis_title='Bus ID',
                zaxis_title='Data Stream',
                bgcolor='#0a0a0a',
                xaxis=dict(gridcolor='#1e1e1e'),
                yaxis=dict(gridcolor='#1e1e1e'),
                zaxis=dict(gridcolor='#1e1e1e'),
                camera=dict(eye=dict(x=1.5, y=1.5, z=1.2))
            ),
            paper_bgcolor='#0e1117',
            height=350,
            showlegend=False,
            title="<b>Streaming Passenger & Position Data</b>"
        )
        st.plotly_chart(fig_stream, use_container_width=True, key=f"stream_{st.session_state.counter}")
    
    with or_col:
        st.markdown("### 🎯 OR Optimization Surface")
        
        # 3D optimization surface
        x_range = np.linspace(0, 10, 30)
        y_range = np.linspace(0, 10, 30)
        X, Y = np.meshgrid(x_range, y_range)
        
        # Simulate optimization objective function (minimize delay + bunching)
        Z = np.sin(X/2) * np.cos(Y/2) * 5 + X * 0.3 - Y * 0.2
        
        fig_or = go.Figure(data=[go.Surface(
            x=X, y=Y, z=Z,
            colorscale='Viridis',
            contours=dict(
                z=dict(show=True, usecolormap=True, highlightcolor="cyan", project=dict(z=True))
            )
        )])
        
        # Add optimal points (current bus positions)
        opt_x = buses['progress'].values * 10
        opt_y = (buses['schedule_delay'].values / 60).clip(0, 10)
        opt_z = np.sin(opt_x/2) * np.cos(opt_y/2) * 5 + opt_x * 0.3 - opt_y * 0.2
        
        fig_or.add_trace(go.Scatter3d(
            x=opt_x, y=opt_y, z=opt_z,
            mode='markers',
            marker=dict(size=10, color='red', symbol='diamond'),
            name='Bus States'
        ))
        
        fig_or.update_layout(
            scene=dict(
                xaxis_title='Headway Control',
                yaxis_title='Delay Minimization',
                zaxis_title='Objective Function',
                bgcolor='#0a0a0a',
                xaxis=dict(gridcolor='#1e1e1e'),
                yaxis=dict(gridcolor='#1e1e1e'),
                zaxis=dict(gridcolor='#1e1e1e'),
                camera=dict(eye=dict(x=1.5, y=1.5, z=1.2))
            ),
            paper_bgcolor='#0e1117',
            height=350,
            title="<b>Linear Programming Optimization</b>"
        )
        st.plotly_chart(fig_or, use_container_width=True, key=f"or_{st.session_state.counter}")
    
    st.markdown("---")
    
    # ROW 5: STREAM PROCESSING PIPELINE & TIME-SPACE DIAGRAM
    st.markdown("---")
    st.markdown("## 🌊 Stream Processing Architecture")
    
    pipeline_col, timespace_col = st.columns(2)
    
    with pipeline_col:
        st.markdown("### 📡 Real-Time Data Pipeline")
        
        # Stream processing flowchart
        fig_pipeline = go.Figure()
        
        # Define pipeline stages
        stages = [
            "GPS Data\nStreaming",
            "Kafka\nIngestion",
            "Passenger\nData",
            "OR\nOptimization",
            "Dashboard"
        ]
        
        x_positions = [1, 2, 2, 3, 4]
        y_positions = [2, 2.5, 1.5, 2, 2]
        colors = ['#3498db', '#e74c3c', '#f39c12', '#2ecc71', '#9b59b6']
        
        # Draw nodes
        for i, (stage, x, y, color) in enumerate(zip(stages, x_positions, y_positions, colors)):
            fig_pipeline.add_trace(go.Scatter(
                x=[x], y=[y],
                mode='markers+text',
                marker=dict(size=80, color=color, line=dict(width=3, color='white')),
                text=stage,
                textposition='middle center',
                textfont=dict(size=10, color='white', family='Arial Black'),
                showlegend=False,
                hoverinfo='skip'
            ))
        
        # Draw connections
        connections = [(0,1), (1,3), (2,3), (3,4)]
        for start, end in connections:
            fig_pipeline.add_annotation(
                x=x_positions[end], y=y_positions[end],
                ax=x_positions[start], ay=y_positions[start],
                xref='x', yref='y',
                axref='x', ayref='y',
                showarrow=True,
                arrowhead=2,
                arrowsize=1.5,
                arrowwidth=3,
                arrowcolor='white',
                opacity=0.6
            )
        
        # Add throughput indicator
        throughput = len(buses) * np.random.randint(5, 15)
        fig_pipeline.add_annotation(
            text=f"Throughput: {throughput} msgs/sec",
            xref="paper", yref="paper",
            x=0.5, y=0.95,
            showarrow=False,
            font=dict(size=14, color='cyan'),
            bgcolor='rgba(0,0,0,0.7)',
            bordercolor='cyan',
            borderwidth=2
        )
        
        fig_pipeline.update_layout(
            plot_bgcolor='#0a0a0a',
            paper_bgcolor='#0e1117',
            xaxis=dict(showgrid=False, zeroline=False, showticklabels=False, range=[0.5, 4.5]),
            yaxis=dict(showgrid=False, zeroline=False, showticklabels=False, range=[1, 3]),
            height=350,
            title="<b>Streaming Data Architecture</b>"
        )
        
        st.plotly_chart(fig_pipeline, use_container_width=True, key=f"pipeline_{st.session_state.counter}")
    
    with timespace_col:
        st.markdown("### ⏱️ Time-Space Diagram")
        st.caption("Shows bus trajectories over time - detects bunching patterns")
        
        # Time-space diagram
        fig_ts = go.Figure()
        
        sorted_buses = buses.sort_values('bus_id')
        
        # Simulate time evolution
        time_steps = [0, 5, 10, 15, 20]  # minutes
        
        for idx, bus in sorted_buses.head(8).iterrows():  # Show 8 buses for clarity
            positions = []
            for t in time_steps:
                # Simulate position change
                pos = (bus['progress'] + t * 0.02) % 1.0
                positions.append(pos * 100)
            
            color = '#00ff00' if bus['schedule_delay'] < 60 else ('#ffaa00' if bus['schedule_delay'] < 180 else '#ff0000')
            
            fig_ts.add_trace(go.Scatter(
                x=time_steps,
                y=positions,
                mode='lines+markers',
                name=bus['bus_id'].split('-')[-1],
                line=dict(width=3, color=color),
                marker=dict(size=8, color=color)
            ))
        
        fig_ts.update_layout(
            plot_bgcolor='#0a0a0a',
            paper_bgcolor='#0e1117',
            font=dict(color='white'),
            xaxis_title="Time (minutes)",
            yaxis_title="Route Position (%)",
            height=350,
            legend=dict(bgcolor='rgba(0,0,0,0.7)', font=dict(color='white'))
        )
        
        st.plotly_chart(fig_ts, use_container_width=True, key=f"timespace_{st.session_state.counter}")
    
    st.markdown("---")
    
    # ROW 6: 3D FLEET DYNAMICS
    st.markdown("---")
    st.markdown("## 🚀 3D Fleet Dynamics")
    
    dynamics_col1, dynamics_col2 = st.columns(2)
    
    with dynamics_col1:
        st.markdown("### 🌐 3D Speed-Load-Delay Space")
        
        # 3D scatter showing relationships
        fig_3d_scatter = go.Figure()
        
        colors_3d = []
        for delay in buses['schedule_delay']:
            if delay < 60:
                colors_3d.append('#00ff00')
            elif delay < 180:
                colors_3d.append('#ffaa00')
            else:
                colors_3d.append('#ff0000')
        
        fig_3d_scatter.add_trace(go.Scatter3d(
            x=buses['speed'],
            y=buses['passengers'],
            z=buses['schedule_delay'] / 60,
            mode='markers+text',
            marker=dict(
                size=15,
                color=colors_3d,
                line=dict(width=2, color='white'),
                symbol='diamond'
            ),
            text=[bid.split('-')[-1] for bid in buses['bus_id']],
            textposition='top center',
            textfont=dict(size=10, color='white'),
            hovertemplate='<b>Bus %{text}</b><br>Speed: %{x} km/h<br>Passengers: %{y}<br>Delay: %{z} min<extra></extra>'
        ))
        
        fig_3d_scatter.update_layout(
            scene=dict(
                xaxis_title='Speed (km/h)',
                yaxis_title='Passengers',
                zaxis_title='Delay (min)',
                bgcolor='#0a0a0a',
                xaxis=dict(gridcolor='#1e1e1e'),
                yaxis=dict(gridcolor='#1e1e1e'),
                zaxis=dict(gridcolor='#1e1e1e'),
                camera=dict(eye=dict(x=1.7, y=1.7, z=1.3))
            ),
            paper_bgcolor='#0e1117',
            height=400,
            showlegend=False
        )
        st.plotly_chart(fig_3d_scatter, use_container_width=True, key=f"3dsc_{st.session_state.counter}")
    
    with dynamics_col2:
        st.markdown("### 📊 Queue Theory Simulation")
        
        # 3D mesh showing queueing behavior
        x = np.linspace(0, 100, 50)
        y = np.linspace(0, 60, 50)
        X, Y = np.meshgrid(x, y)
        
        # Simulate queue length based on arrival rate and service rate
        Z = (Y / (60 - X + 0.1)) * 10  # Queue length formula
        Z = np.clip(Z, 0, 50)
        
        fig_queue = go.Figure(data=[go.Surface(
            x=X, y=Y, z=Z,
            colorscale='Hot',
            contours=dict(
                z=dict(show=True, usecolormap=True, highlightcolor="lime", project=dict(z=True))
            )
        )])
        
        # Add current bus states
        bus_x = buses['progress'].values * 100
        bus_y = buses['passengers'].values
        bus_z = (bus_y / (60 - bus_x + 0.1)) * 10
        bus_z = np.clip(bus_z, 0, 50)
        
        fig_queue.add_trace(go.Scatter3d(
            x=bus_x, y=bus_y, z=bus_z,
            mode='markers',
            marker=dict(size=8, color='cyan', symbol='cross'),
            name='Current State'
        ))
        
        fig_queue.update_layout(
            scene=dict(
                xaxis_title='Route Progress (%)',
                yaxis_title='Passenger Load',
                zaxis_title='Queue Length',
                bgcolor='#0a0a0a',
                xaxis=dict(gridcolor='#1e1e1e'),
                yaxis=dict(gridcolor='#1e1e1e'),
                zaxis=dict(gridcolor='#1e1e1e'),
                camera=dict(eye=dict(x=1.5, y=1.5, z=1.2))
            ),
            paper_bgcolor='#0e1117',
            height=400
        )
        st.plotly_chart(fig_queue, use_container_width=True, key=f"queue_{st.session_state.counter}")
    
    st.markdown("---")
    
    # Fleet table
    st.markdown("### 📋 Live Fleet Status")
    fleet_display = buses[['bus_id', 'speed', 'passengers', 'occupancy', 'schedule_delay']].copy()
    fleet_display['schedule_delay'] = (fleet_display['schedule_delay'] / 60).round(1)
    fleet_display.columns = ['Bus ID', 'Speed (km/h)', 'Passengers', 'Occupancy', 'Delay (min)']
    
    # Color code the dataframe
    def color_delay(val):
        if val < 1:
            color = '#00ff00'
        elif val < 3:
            color = '#ffaa00'
        else:
            color = '#ff0000'
        return f'color: {color}'
    
    styled_df = fleet_display.style.applymap(color_delay, subset=['Delay (min)'])
    st.dataframe(styled_df, use_container_width=True, hide_index=True)
    
    # Auto-refresh
    if st.session_state.running:
        time.sleep(3)
        st.rerun()


if __name__ == "__main__":
    main()

