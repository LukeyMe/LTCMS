import streamlit as st
import plotly.graph_objects as go
import pandas as pd
from datetime import datetime, timedelta, date
import uuid
import os
import json
import copy

# -------------- Page configuration -------------------
st.set_page_config(page_title="LTCMS - Lipa Technical Center", layout="wide", initial_sidebar_state="expanded")

# -------------- Persistent data file -----------------
DATA_FILE = "ltcms_state.json"

# -------------- CSS Styling (UNCHANGED) ---------------
st.markdown("""
<style>
    .main > div { padding-top: 1rem; }
    .dashboard-card {
        background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
        color: white; padding: 20px;
        border-radius: 10px; text-align: center; margin: 10px 0;
        box-shadow: 0 4px 15px rgba(0,0,0,0.1);
    }
    .dashboard-metric { font-size: 2.5rem; font-weight: bold; margin: 10px 0; }
    .dashboard-label { font-size: 0.9rem; opacity: 0.9; }
    .equipment-grid {
        display: grid; grid-template-columns: repeat(3, 1fr);
        gap: 15px; margin: 20px 0;
    }
    .equipment-card {
        border: 2px solid #28a745;
        border-radius: 8px; padding: 15px;
        background: white; box-shadow: 0 2px 8px rgba(0,0,0,0.1);
        cursor: pointer; transition: all 0.3s ease;
        min-height: 180px; position: relative;
    }
    .equipment-card:hover {
        transform: translateY(-3px);
        box-shadow: 0 4px 15px rgba(0,0,0,0.2);
        border-color: #20c997;
    }
    .equipment-header {
        background: linear-gradient(135deg, #28a745, #20c997);
        color: white; padding: 8px 12px;
        border-radius: 5px; margin: -15px -15px 15px -15px;
        font-size: 14px; font-weight: bold; text-align: center;
    }
    .parameter-section {
        background:#eef6ea;padding:5px 10px;
        border-radius:6px; margin:10px 0;
    }
    .parameter-title { font-size: 1rem; margin-bottom: 6px; }
    .parameter-item {
        font-size:13px; border-left:3px solid #28a745;
        padding-left:8px; margin-bottom:4px;
    }
    .test-item {
        background: #f8f9fa;
        border-left: 3px solid #007bff;
        padding: 6px 10px;
        margin: 3px 0;
        border-radius: 3px;
        font-size: 11px;
    }
    .status-badge {
        position: absolute; top: 10px; right: 10px;
        padding: 4px 8px; border-radius: 12px;
        font-size: 11px; font-weight: bold;
    }
    .status-running { background: #d4edda; color: #155724; }
    .status-idle { background: #fff3cd; color: #856404; }
    .status-maintenance { background: #f8d7da; color: #721c24; }
    .status-scheduled { background: #d1ecf1; color: #0c5460; }
    .modal-overlay {
        position: fixed; top: 0; left: 0; width: 100%;
        height: 100%; background: rgba(0,0,0,0.5); z-index: 1000;
        display: flex; justify-content: center; align-items: center;
    }
    .modal-content {
        background: white; border-radius: 15px; padding: 30px;
        max-width: 800px; max-height: 90vh; overflow-y: auto;
        box-shadow: 0 10px 30px rgba(0,0,0,0.3); border: 3px solid #007bff;
    }
    .modebar { display: none !important; }
</style>
""", unsafe_allow_html=True)

# -------------- Persistent Storage Utilities -----------------
def load_app_state():
    if os.path.exists(DATA_FILE):
        with open(DATA_FILE, "r") as f:
            state = json.load(f)
            # convert back to date objects
            for eq_id, schedules in state.get("schedules", {}).items():
                for s in schedules:
                    for field in ("start_date", "end_date"):
                        if isinstance(s.get(field), str):
                            s[field] = datetime.strptime(s[field], "%Y-%m-%d").date()
            return state
    return {}

def save_app_state():
    # make a deep copy so we don't mutate session state
    save_state = {
        'equipment_data': copy.deepcopy(st.session_state.equipment_data),
        'schedules': copy.deepcopy(st.session_state.schedules)
    }
    # convert dates to strings in the copy only
    for eq_id, schedules in save_state['schedules'].items():
        for s in schedules:
            for field in ("start_date", "end_date"):
                val = s.get(field)
                if isinstance(val, (date, datetime)):
                    s[field] = val.strftime("%Y-%m-%d")
            # also convert created_at if present
            if isinstance(s.get('created_at'), datetime):
                s['created_at'] = s['created_at'].strftime("%Y-%m-%d %H:%M:%S")
    with open(DATA_FILE, "w") as f:
        json.dump(save_state, f, indent=2, default=str)

# -------------- Session State Initialization ---------------
if 'app_state_loaded' not in st.session_state:
    loaded_state = load_app_state()
    st.session_state.equipment_data = loaded_state.get('equipment_data', {})
    st.session_state.schedules = loaded_state.get('schedules', {})
    st.session_state.selected_group = 'ALL'
    st.session_state.show_add_equipment = False
    st.session_state.show_schedule_form = None
    st.session_state.show_settings = None
    st.session_state.show_test_status = False
    st.session_state.app_state_loaded = True

def reset_all_modals():
    st.session_state.show_add_equipment = False
    st.session_state.show_schedule_form = None
    st.session_state.show_settings = None
    st.session_state.show_test_status = False

# -------------- Constants and Helpers (UNCHANGED) ------------------------
EQUIPMENT_GROUPS = {
    'ALL': {'name': 'All Equipment', 'icon': '🏭'},
    'THERMAL_SHOCK': {
        'name': 'Thermal Shock Chambers',
        'icon': '❄️🔥',
        'parameters': ['min_temperature', 'max_temperature', 'dwell_time', 'num_cycles'],
        'defaults': {'min_temperature': -55, 'max_temperature': 125, 'dwell_time': 30, 'num_cycles': 10},
        'display_params': ['min_temperature', 'max_temperature', 'dwell_time', 'num_cycles']
    },
    'TEMP_HUMIDITY': {
        'name': 'Temperature & Humidity Chambers',
        'icon': '🌡️',
        'parameters': ['ambient_temperature', 'relative_humidity'],
        'defaults': {'ambient_temperature': 25, 'relative_humidity': 50},
        'display_params': ['ambient_temperature', 'relative_humidity']
    },
    'VIBRATION': {
        'name': 'Vibration Equipment',
        'icon': '📳',
        'parameters': ['amplitude_gs', 'frequency_hz', 'duration', 'num_axis', 'sweep_time'],
        'defaults': {'amplitude_gs': 5.0, 'frequency_hz': 100, 'duration': 60, 'num_axis': 3, 'sweep_time': 10},
        'display_params': ['amplitude_gs', 'frequency_hz', 'num_axis', 'duration']
    },
    'SALT_FOG': {
        'name': 'Salt Fog Chambers',
        'icon': '🌊',
        'parameters': ['duration'],
        'defaults': {'duration': 48},
        'display_params': ['duration']
    },
    'PULSE_TESTER': {
        'name': 'Pulse Testers',
        'icon': '⚡',
        'parameters': ['pulse_interval', 'pulse_current', 'pulse_width', 'num_cycles'],
        'defaults': {'pulse_interval': 1, 'pulse_current': 10, 'pulse_width': 100, 'num_cycles': 1000},
        'display_params': ['pulse_current', 'pulse_width', 'pulse_interval']
    },
    'TEMP_OVENS': {
        'name': 'Temperature Ovens',
        'icon': '🔥',
        'parameters': ['ambient_temperature'],
        'defaults': {'ambient_temperature': 150},
        'display_params': ['ambient_temperature']
    }
}

TEST_STATUS_OPTIONS = ['Scheduled', 'In Progress', 'Completed', 'On Hold', 'Cancelled']

def get_parameter_display_name(param_name):
    param_names = {
        'min_temperature': 'Min Temp',
        'max_temperature': 'Max Temp',
        'dwell_time': 'Dwell Time',
        'num_cycles': 'Cycles',
        'ambient_temperature': 'Temperature',
        'relative_humidity': 'Humidity',
        'amplitude_gs': 'Amplitude',
        'frequency_hz': 'Frequency',
        'duration': 'Duration',
        'num_axis': 'Axis',
        'sweep_time': 'Sweep Time',
        'pulse_interval': 'Interval',
        'pulse_current': 'Current',
        'pulse_width': 'Width'
    }
    return param_names.get(param_name, param_name.replace('_', ' ').title())

def get_parameter_unit(param_name):
    units = {
        'min_temperature': '°C',
        'max_temperature': '°C',
        'ambient_temperature': '°C',
        'relative_humidity': '%',
        'dwell_time': 'min',
        'duration': 'hrs',
        'amplitude_gs': 'g',
        'frequency_hz': 'Hz',
        'pulse_interval': 'ms',
        'pulse_current': 'mA',
        'pulse_width': 'μs',
        'sweep_time': 'min'
    }
    return units.get(param_name, '')

def create_mini_donut(load_percentage, size=70):
    if load_percentage >= 90:
        color = '#dc3545'
    elif load_percentage >= 70:
        color = '#ffc107'
    else:
        color = '#28a745'
    fig = go.Figure(data=[go.Pie(
        labels=['Used', 'Available'],
        values=[load_percentage, 100 - load_percentage],
        hole=0.7,
        marker_colors=[color, '#e9ecef'],
        textinfo='none'
    )])
    fig.update_layout(
        showlegend=False,
        height=size,
        width=size,
        margin=dict(t=0, b=0, l=0, r=0),
        annotations=[{
            'text': f'<b>{load_percentage}%</b>',
            'x': 0.5, 'y': 0.5,
            'font_size': 8,
            'showarrow': False
        }]
    )
    return fig

def get_next_scheduled_date(equipment_id):
    if equipment_id not in st.session_state.schedules:
        return None
    upcoming_dates = []
    for schedule in st.session_state.schedules[equipment_id]:
        if schedule['status'] in ['Scheduled', 'In Progress']:
            upcoming_dates.append(schedule['start_date'])
    return min(upcoming_dates) if upcoming_dates else None

# -------------- Modal: Add Equipment (UNCHANGED) --------------------
@st.dialog("Add New Equipment")
def add_equipment_modal():
    st.markdown("### ➕ Add New Equipment")
    col1, col2 = st.columns(2)
    with col1:
        equipment_id = st.text_input("Equipment ID", placeholder="e.g., TS001, TH002", key="new_eq_id")
        equipment_name = st.text_input("Equipment Name", placeholder="e.g., Thermal Shock Chamber TS001", key="new_eq_name")
        equipment_type = st.selectbox("Equipment Type", options=list(EQUIPMENT_GROUPS.keys())[1:], format_func=lambda x: EQUIPMENT_GROUPS[x]['name'], key="new_eq_type")
        location = st.text_input("Location", placeholder="e.g., Lab A-1", key="new_eq_location")
    with col2:
        status = st.selectbox("Status", options=['Idle', 'Running', 'Maintenance', 'Scheduled'], key="new_eq_status")
        channels = 1
        if equipment_type == 'PULSE_TESTER':
            channels = st.number_input("Number of Channels", min_value=1, max_value=32, value=8, key="new_eq_channels")
    if equipment_type in EQUIPMENT_GROUPS and 'parameters' in EQUIPMENT_GROUPS[equipment_type]:
        st.markdown("### Equipment Parameters")
        params = {}
        defaults = EQUIPMENT_GROUPS[equipment_type]['defaults']
        for param in EQUIPMENT_GROUPS[equipment_type]['parameters']:
            label = get_parameter_display_name(param)
            unit = get_parameter_unit(param)
            label_with_unit = f"{label} ({unit})" if unit else label
            params[param] = st.number_input(label_with_unit, value=float(defaults[param]), key=f"new_param_{param}")
    col_add, col_cancel = st.columns([1,1])
    with col_add:
        if st.button("✅ Add Equipment", type="primary"):
            if equipment_id and equipment_name and equipment_id not in st.session_state.equipment_data:
                equipment_data = {
                    'name': equipment_name,
                    'type': equipment_type,
                    'location': location,
                    'status': status,
                    'load_percentage': 0,
                    'last_updated': datetime.now()
                }
                if equipment_type in EQUIPMENT_GROUPS and 'parameters' in EQUIPMENT_GROUPS[equipment_type]:
                    equipment_data['parameters'] = params
                if equipment_type == 'PULSE_TESTER':
                    equipment_data['channels'] = channels
                st.session_state.equipment_data[equipment_id] = equipment_data
                save_app_state()
                st.success(f"✅ Equipment {equipment_id} added successfully!")
                st.session_state.show_add_equipment = False
                st.rerun()
            elif equipment_id in st.session_state.equipment_data:
                st.error("Equipment ID already exists!")
            else:
                st.error("Please fill in Equipment ID and Name")
    with col_cancel:
        if st.button("❌ Cancel"):
            st.session_state.show_add_equipment = False
            st.rerun()

# -------------- Modal: Schedule Test (UNCHANGED) ----------------------
@st.dialog("Schedule Test")
def schedule_test_modal(equipment_id):
    st.markdown(f"### 📅 Schedule Test for {equipment_id}")
    equipment = st.session_state.equipment_data[equipment_id]
    col1, col2 = st.columns(2)
    with col1:
        test_id = st.text_input("Test ID", placeholder="e.g., LTC-2024-001", key="schedule_test_id")
        user_name = st.text_input("Assigned User", placeholder="Enter user name", key="schedule_user")
        load_percentage = st.slider("Load Percentage (%)", 1, 100, 50, 1, key="schedule_load")
    with col2:
        start_date = st.date_input("Start Date", value=date.today(), key="schedule_start")
        end_date = st.date_input("End Date", value=date.today()+timedelta(days=7), key="schedule_end")
        priority = st.selectbox("Priority", options=["Low", "Medium", "High", "Critical"], index=1, key="schedule_priority")
        selected_channels = []
        if equipment['type'] == 'PULSE_TESTER':
            available_channels = list(range(1, equipment.get('channels', 8) + 1))
            selected_channels = st.multiselect("Select Channels", options=available_channels, default=[1], key="schedule_channels")
    test_params = {}
    if equipment['type'] in EQUIPMENT_GROUPS and 'parameters' in EQUIPMENT_GROUPS[equipment['type']]:
        st.markdown("### Test Parameters")
        defaults = EQUIPMENT_GROUPS[equipment['type']]['defaults']
        for param in EQUIPMENT_GROUPS[equipment['type']]['parameters']:
            label = get_parameter_display_name(param)
            unit = get_parameter_unit(param)
            label_with_unit = f"Test {label} ({unit})" if unit else f"Test {label}"
            test_params[param] = st.number_input(label_with_unit, value=float(defaults[param]), key=f"test_param_{param}")
    test_description = st.text_area("Test Description", placeholder="Enter test conditions and requirements...", key="schedule_description")
    col_schedule, col_cancel = st.columns([1,1])
    with col_schedule:
        if st.button("📅 Schedule Test", type="primary"):
            if test_id and user_name:
                if equipment_id not in st.session_state.schedules:
                    st.session_state.schedules[equipment_id] = []
                schedule_id = str(uuid.uuid4())
                schedule_data = {
                    'schedule_id': schedule_id,
                    'test_id': test_id,
                    'user': user_name,
                    'start_date': start_date,
                    'end_date': end_date,
                    'load_percentage': load_percentage,
                    'priority': priority,
                    'description': test_description,
                    'test_parameters': test_params,
                    'status': 'Scheduled',
                    'created_at': datetime.now()
                }
                if equipment['type'] == 'PULSE_TESTER' and selected_channels:
                    schedule_data['channels'] = selected_channels
                st.session_state.schedules[equipment_id].append(schedule_data)
                current_load = sum(s['load_percentage'] for s in st.session_state.schedules[equipment_id])
                st.session_state.equipment_data[equipment_id]['load_percentage'] = min(current_load, 100)
                # Do not downgrade status from Running or Maintenance
                cur_status = st.session_state.equipment_data[equipment_id]['status']
                if cur_status not in ['Running', 'Maintenance']:
                    st.session_state.equipment_data[equipment_id]['status'] = 'Scheduled'
                save_app_state()
                st.success(f"✅ Test {test_id} scheduled successfully!")
                st.session_state.show_schedule_form = None
                st.rerun()
            else:
                st.error("Please fill in Test ID and User name")
    with col_cancel:
        if st.button("❌ Cancel"):
            st.session_state.show_schedule_form = None
            st.rerun()

# -------------- Modal: Equipment Settings (UNCHANGED) -----------------
@st.dialog("Equipment Settings")
def equipment_settings_modal(equipment_id):
    st.markdown(f"### ⚙️ Settings for {equipment_id}")
    equipment = st.session_state.equipment_data[equipment_id]
    col1, col2 = st.columns(2)
    with col1:
        new_status = st.selectbox("Equipment Status", ['Idle', 'Running', 'Maintenance', 'Scheduled'], index=['Idle', 'Running', 'Maintenance', 'Scheduled'].index(equipment['status']), key=f"settings_status_{equipment_id}")
        st.write(f"**Equipment Type:** {EQUIPMENT_GROUPS[equipment['type']]['name']}")
        st.write(f"**Location:** {equipment['location']}")
        st.write(f"**Current Load:** {equipment['load_percentage']}%")
        if equipment['type'] == 'PULSE_TESTER':
            new_channels = st.number_input("Number of Channels", min_value=1, max_value=32, value=equipment.get('channels', 8), key=f"settings_channels_{equipment_id}")
        else:
            new_channels = None
    with col2:
        st.markdown("### Current Parameters")
        if 'parameters' in equipment:
            for param, value in equipment['parameters'].items():
                label = get_parameter_display_name(param)
                unit = get_parameter_unit(param)
                st.write(f"**{label}:** {value} {unit}")
    if 'parameters' in equipment:
        st.markdown("### Edit Parameters")
        new_params = {}
        for param, value in equipment['parameters'].items():
            label = get_parameter_display_name(param)
            unit = get_parameter_unit(param)
            label_with_unit = f"{label} ({unit})" if unit else label
            new_params[param] = st.number_input(label_with_unit, value=float(value), key=f"settings_param_{param}_{equipment_id}")
    else:
        new_params = None
    col_apply, col_cancel = st.columns([1,1])
    with col_apply:
        if st.button("✅ Apply Changes", type="primary"):
            st.session_state.equipment_data[equipment_id]['status'] = new_status
            st.session_state.equipment_data[equipment_id]['last_updated'] = datetime.now()
            if new_channels is not None:
                st.session_state.equipment_data[equipment_id]['channels'] = new_channels
            if new_params is not None:
                st.session_state.equipment_data[equipment_id]['parameters'] = new_params
            save_app_state()
            st.success(f"✅ Settings updated for {equipment_id}")
            st.session_state.show_settings = None
            st.rerun()
    with col_cancel:
        if st.button("❌ Cancel"):
            st.session_state.show_settings = None
            st.rerun()

# -------------- Modal: Test Status Management (UNCHANGED) ----------------
@st.dialog("Test Status Management")
def test_status_modal():
    st.markdown("### 📋 Test Status Management")
    all_schedules = []
    for eq_id, schedules in st.session_state.schedules.items():
        for i, schedule in enumerate(schedules):
            schedule_data = schedule.copy()
            schedule_data['equipment_id'] = eq_id
            schedule_data['schedule_index'] = i
            all_schedules.append(schedule_data)
    if not all_schedules:
        st.info("No scheduled tests found.")
        if st.button("❌ Close"):
            st.session_state.show_test_status = False
            st.rerun()
        return
    st.markdown("#### Edit status or delete any test directly below:")
    for schedule in all_schedules:
        schedule_id = schedule.get('schedule_id', str(uuid.uuid4()))
        eq_id = schedule['equipment_id']
        i = schedule['schedule_index']
        c1, c2, c3, c4, c5, c6 = st.columns([2,2,2,2,2,1])
        with c1: st.write(f"**Test ID:** {schedule['test_id']}")
        with c2: st.write(f"**User:** {schedule['user']}")
        with c3: st.write(f"**Start:** {schedule['start_date']}")
        with c4: st.write(f"**End:** {schedule['end_date']}")
        with c5:
            status_idx = TEST_STATUS_OPTIONS.index(schedule['status']) if schedule['status'] in TEST_STATUS_OPTIONS else 0
            new_status = st.selectbox("Status", TEST_STATUS_OPTIONS, index=status_idx, key=f"status_{schedule_id}_{i}")
        with c6:
            delete_me = st.button("🗑️", key=f"delete_{schedule_id}_{i}")
        if new_status != schedule['status']:
            st.session_state.schedules[eq_id][i]['status'] = new_status
            save_app_state()
            st.success(f"Test {schedule['test_id']} status updated to {new_status}!")
            st.rerun()
        if delete_me:
            removed = st.session_state.schedules[eq_id].pop(i)
            if not st.session_state.schedules[eq_id]:
                st.session_state.equipment_data[eq_id]['status'] = 'Idle'
            save_app_state()
            st.success(f"Test {removed['test_id']} deleted.")
            st.rerun()
        st.write("---")
    if st.button("❌ Close (Exit Management)"):
        st.session_state.show_test_status = False
        st.rerun()

# -------------- Render Equipment Card -----------------------
def render_equipment_card(eq_id, eq_data):
    group_info = EQUIPMENT_GROUPS[eq_data['type']]
    card_html = f'''
    <div class="equipment-card">
        <div class="equipment-header">{group_info['icon']} {eq_id}</div>
        <div class="status-badge status-{eq_data['status'].lower()}">{eq_data['status']}</div>
    '''
    st.markdown(card_html, unsafe_allow_html=True)

    # Equipment parameters
    st.markdown('<div class="parameter-section">', unsafe_allow_html=True)
    st.markdown('<div class="parameter-title"><b>Equipment Parameters</b></div>', unsafe_allow_html=True)
    for param in group_info.get('display_params', []):
        if 'parameters' in eq_data and param in eq_data['parameters']:
            label = get_parameter_display_name(param)
            unit = get_parameter_unit(param)
            value = eq_data['parameters'][param]
            st.markdown(f'<div class="parameter-item">{label}: <b>{value} {unit}</b></div>', unsafe_allow_html=True)
    st.markdown('</div>', unsafe_allow_html=True)

    # Next for salt fog
    if eq_data['type'] == 'SALT_FOG':
        next_date = get_next_scheduled_date(eq_id)
        if next_date:
            st.markdown(f'<div class="parameter-display">📅 Next: {next_date.strftime("%Y-%m-%d")}</div>', unsafe_allow_html=True)
        else:
            st.markdown('<div class="parameter-display">📅 No scheduled tests</div>', unsafe_allow_html=True)

    # Scheduled tests
    if eq_id in st.session_state.schedules and st.session_state.schedules[eq_id]:
        for schedule in st.session_state.schedules[eq_id]:
            # safely format dates whether they're date objects or strings
            sd = schedule["start_date"]
            ed = schedule["end_date"]
            start_str = sd.strftime("%Y-%m-%d") if hasattr(sd, "strftime") else sd
            end_str   = ed.strftime("%Y-%m-%d") if hasattr(ed, "strftime") else ed

            st.markdown(
                f'<div class="test-item">📋 <b>{schedule["test_id"]}</b> | 👤 {schedule["user"]} | '
                f'📊 {schedule["load_percentage"]}% | 🗓 {start_str} ➔ {end_str}</div>',
                unsafe_allow_html=True
            )

    # Donut chart
    col_chart, col_spacer = st.columns([1,3])
    with col_chart:
        fig = create_mini_donut(eq_data['load_percentage'], 70)
        st.plotly_chart(fig, config={'displayModeBar': False}, use_container_width=True, key=f"chart_{eq_id}")

    # Action buttons
    col_schedule, col_settings = st.columns(2)
    with col_schedule:
        if st.button("📅 Schedule", key=f"schedule_btn_{eq_id}", use_container_width=True):
            reset_all_modals()
            st.session_state.show_schedule_form = eq_id
            st.rerun()
    with col_settings:
        if st.button("⚙️ Settings", key=f"settings_btn_{eq_id}", use_container_width=True):
            reset_all_modals()
            st.session_state.show_settings = eq_id
            st.rerun()

    st.markdown('</div>', unsafe_allow_html=True)

# -------------- Main function -----------------------------
def main():
    # Show modals
    if st.session_state.show_add_equipment: add_equipment_modal()
    if st.session_state.show_schedule_form is not None: schedule_test_modal(st.session_state.show_schedule_form)
    if st.session_state.show_settings is not None: equipment_settings_modal(st.session_state.show_settings)
    if st.session_state.show_test_status: test_status_modal()

    st.title("🏭 LTCMS - Lipa Technical Center Management System")
    st.markdown("**Real-time Equipment & Test Management Dashboard**")

    # Sidebar controls
    with st.sidebar:
        st.header("🔧 System Controls")
        if st.button("➕ Add New Equipment"):
            reset_all_modals()
            st.session_state.show_add_equipment = True
            st.rerun()
        if st.button("📋 Manage Test Status"):
            reset_all_modals()
            st.session_state.show_test_status = True
            st.rerun()
        st.markdown("---")
        if st.button("🔄 Refresh Dashboard"): st.rerun()
        st.markdown("---")
        total_equipment = len(st.session_state.equipment_data)
        total_schedules = sum(len(s) for s in st.session_state.schedules.values())
        st.metric("Total Equipment", total_equipment)
        st.metric("Active Schedules", total_schedules)
        if total_equipment > 0:
            avg_utilization = sum(eq['load_percentage'] for eq in st.session_state.equipment_data.values()) / total_equipment
            st.metric("Avg Utilization", f"{avg_utilization:.1f}%")

    # Summary cards
    st.markdown("## 📊 System Dashboard")
    if not st.session_state.equipment_data:
        st.info("👆 **Welcome to LTCMS!** Click 'Add New Equipment' in the sidebar to get started.")
        return

    equipment = st.session_state.equipment_data
    counts = {s: sum(1 for eq in equipment.values() if eq['status']==s.capitalize()) for s in ['running','idle','maintenance','scheduled']}
    total_tests = sum(len(s) for s in st.session_state.schedules.values())
    cols = st.columns(5)
    styles = [
        ("running","#28a745,#20c997","🟢 RUNNING"),
        ("idle","#ffc107,#fd7e14","🟡 IDLE"),
        ("maintenance","#dc3545,#c82333","🔴 MAINTENANCE"),
        ("scheduled","#17a2b8,#138496","🔵 SCHEDULED"),
        ("total","#6f42c1,#5a32a3","📋 TOTAL TESTS")
    ]
    for col, (key, grad, label) in zip(cols, styles):
        val = counts.get(key, total_tests) if key!="total" else total_tests
        col.markdown(f'''<div class="dashboard-card" style="background: linear-gradient(135deg, {grad});">
                        <div class="dashboard-metric">{val}</div>
                        <div class="dashboard-label">{label}</div></div>''', unsafe_allow_html=True)

    # Equipment groups
    st.markdown("## 🎯 Equipment Groups")
    grp_cols = st.columns(len(EQUIPMENT_GROUPS))
    for i,(gk,gi) in enumerate(EQUIPMENT_GROUPS.items()):
        with grp_cols[i]:
            if st.button(f"{gi['icon']} {gi['name']}",
                         key=f"group_{gk}",
                         type="primary" if st.session_state.selected_group==gk else "secondary"):
                reset_all_modals()
                st.session_state.selected_group = gk
                st.rerun()

    # Filter & render
    filtered = equipment if st.session_state.selected_group=='ALL' else {k:v for k,v in equipment.items() if v['type']==st.session_state.selected_group}
    st.markdown("## 🏭 Equipment Status")
    if not filtered:
        name = EQUIPMENT_GROUPS[st.session_state.selected_group]['name']
        st.info(f"No equipment found in '{name}' group. Add some equipment to get started!")
        return

    items = list(filtered.items())
    for row in range(0,len(items),3):
        cols = st.columns(3)
        for idx in range(3):
            if row+idx < len(items):
                eq_id, eq_data = items[row+idx]
                with cols[idx]:
                    render_equipment_card(eq_id, eq_data)

    # Active schedules table
    if st.session_state.schedules:
        st.markdown("---")
        st.markdown("## 📋 Active Schedules Overview")
        rows = []
        for eq_id, schs in st.session_state.schedules.items():
            for s in schs:
                rows.append({
                    'Equipment': eq_id,
                    'Test ID': s['test_id'],
                    'User': s['user'],
                    'Start': s['start_date'].strftime('%Y-%m-%d') if hasattr(s['start_date'],'strftime') else s['start_date'],
                    'End':   s['end_date'].strftime('%Y-%m-%d')   if hasattr(s['end_date'],'strftime')   else s['end_date'],
                    'Load %': s['load_percentage'],
                    'Priority': s['priority'],
                    'Status':   s['status'],
                    **({'Channels': ', '.join(map(str,s['channels']))} if 'channels' in s else {})
                })
        if rows:
            df = pd.DataFrame(rows)
            st.dataframe(df, use_container_width=True, hide_index=True)
            csv = df.to_csv(index=False)
            st.download_button("📥 Export Schedule Data", data=csv, file_name=f"ltcms_schedules_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv", mime="text/csv")

    st.markdown("---")
    st.markdown(f"**LTCMS Dashboard Active** | **Last Update:** {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")


if __name__ == "__main__":
    main()
