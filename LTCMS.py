import streamlit as st
import plotly.graph_objects as go
import plotly.express as px
import pandas as pd
from datetime import datetime, timedelta, date
import calendar
import uuid
import os
import json
import copy
import base64
import requests

# -------------- Page configuration -------------------
st.set_page_config(
    page_title="LTCMS - Lipa Technical Center", 
    layout="wide", 
    initial_sidebar_state="expanded"
)

# GitHub Repo Settings for JSON persistence and backup
REPO = "LukeyMe/LTCMS"
FILE_PATH = "ltcms_state.json"
BRANCH = "main"
TOKEN = st.secrets["GITHUB_TOKEN"]

DATA_FILE = "ltcms_state.json"

# -------------- CSS Styling ---------------
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
        gap: 10px; margin: 20px 0; padding: 10px;
        border: 1px solid #e0e0e0; border-radius: 10px;
        background: #fafafa;   
    }
    .equipment-card {
        border: 2px solid #28a745;
        border-radius: 10px; padding: 15px;
        background: white; box-shadow: 0 3px 10px rgba(0,0,0,0.1);
        cursor: pointer; transition: all 0.3s ease;
        min-height: 50px; position: relative;
    }
    .equipment-card:hover {
        transform: translateY(-3px);
        box-shadow: 0 6px 20px rgba(0,0,0,0.15);
        border-color: #20c997;
    }
    .equipment-header {
        background: linear-gradient(135deg, #28a745, #20c997);
        color: white; padding: 6px 10px;
        border-radius: 5px; margin: -15px -15px 10px -15px;
        font-size: 14px; font-weight: bold; text-align: center;
    }
    .parameter-section {
        background:#eef6ea;padding:4px 8px;
        border-radius:6px; margin:8px 0;
    }
    .parameter-title { font-size: 0.9rem; margin-bottom: 4px; font-weight: bold; }
    .parameter-item {
        font-size:12px; border-left:3px solid #28a745;
        padding-left:6px; margin-bottom:2px;
    }
    .test-item {
        background: #f8f9fa;
        border-left: 3px solid #007bff;
        padding: 4px 8px;
        margin: 2px 0;
        border-radius: 3px;
        font-size: 10px;
    }
    .progress-bar {
        background: #e0e0e0;
        border-radius: 8px;
        height: 12px;
        margin-top: 6px;
        width: 100%;
    }
    .progress-fill {
        height: 100%;
        border-radius: 8px;
        background: linear-gradient(90deg, #007bff 0%, #29c7ac 100%);
        transition: width 0.6s ease;
    }
    .status-badge {
        position: absolute; top: 8px; right: 8px;
        padding: 3px 6px; border-radius: 10px;
        font-size: 10px; font-weight: bold;
    }
    .status-running { background: #d4edda; color: #155724; }
    .status-idle { background: #fff3cd; color: #856404; }
    .status-maintenance { background: #f8d7da; color: #721c24; }
    .status-scheduled { background: #d1ecf1; color: #0c5460; }
    /* Universal modal override for full width/height */
div[data-testid="stModal"],
div[data-testid="stModal"] > div[role="dialog"],
div[role="dialog"] {
    width: 85vw !important;
    max-width: 180vw !important;
    height: 85vh !important;
    max-height: 85vh !important;
    margin: auto !important;
    padding: 0 !important;
    border-radius: 0.5 !important;
    top: 0 !important;
    left: 0 !important;
    right: 0 !important;
    bottom: 0 !important;
    position: fixed !important;
    overflow: hidden !important;
    display: flex !important;
    flex-direction: column !important;
}

div[data-testid="stModal"] > div[role="dialog"] > div:first-child {
    flex-grow: 1 !important;
    overflow-y: auto !important;
    height: 100% !important;
    padding: 20px 40px !important;
    box-sizing: border-box !important;
}

/* Widen select dropdowns */
[data-baseweb="select"] {
    min-width: 180px !important;
    max-width: 280px !important;
    width: 100% !important;
}

/* Make buttons wider */
.stButton > button {
    min-width: 130px !important;
}

/* Inputs and textareas to full width */
input[type="text"], input[type="number"], textarea {
    width: 100% !important;
    min-width: 150px !important;
}

/* Optional: reduce columns count in your modal code */
/* And use wider relative widths in st.columns calls */
</style>
""", unsafe_allow_html=True)

# -------------- Persistent Storage Utilities -----------------
def load_app_state():
    url = f"https://api.github.com/repos/{REPO}/contents/{FILE_PATH}?ref={BRANCH}"
    headers = {"Authorization": f"token {TOKEN}"}
    r = requests.get(url, headers=headers)

    if r.status_code == 200:
        content = r.json().get("content", "")
        decoded = base64.b64decode(content).decode("utf-8")
        state = json.loads(decoded)

        # Convert string dates back to date objects
        for eq_id, schedules in state.get("schedules", {}).items():
            for s in schedules:
                for field in ("start_date", "end_date"):
                    if isinstance(s.get(field), str):
                        try:
                            s[field] = datetime.strptime(s[field], "%Y-%m-%d").date()
                        except ValueError:
                            pass
                if isinstance(s.get("created_at"), str):
                    try:
                        s["created_at"] = datetime.strptime(s["created_at"], "%Y-%m-%d %H:%M:%S")
                    except ValueError:
                        pass

        return state

    else:
        st.error(f"Failed to load state from GitHub: {r.status_code} - {r.text}")
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
    # Serialize to JSON
    new_content = json.dumps(save_state, indent=2, default=str)
    # Get the current sha of the file on GitHub (required by GitHub API)
    url = f"https://api.github.com/repos/{REPO}/contents/{FILE_PATH}?ref={BRANCH}"
    headers = {"Authorization": f"token {TOKEN}"}
    r = requests.get(url, headers=headers)
    if r.status_code == 200:
        sha = r.json().get("sha")
        if not sha:
            st.error("Could not get file sha for updating state on GitHub.")
            return
        data = {
            "message": "Update LTCMS state from Streamlit app",
            "content": base64.b64encode(new_content.encode("utf-8")).decode("utf-8"),
            "branch": BRANCH,
            "sha": sha
        }
        r_put = requests.put(url, headers=headers, data=json.dumps(data))
        if r_put.status_code not in (200, 201):
            st.error(f"Error saving state file to GitHub: {r_put.status_code} - {r_put.text}")
    else:
        st.error(f"Failed to get current file sha from GitHub: {r.status_code} - {r.text}")

# CHANGE #5 - Automated Backup on Friday
def backup_json_file():
    today = datetime.now()
    # 4 is Friday (Monday=0)
    if today.weekday() == 4:
        # Download the raw file from the repo
        url = f"https://raw.githubusercontent.com/{REPO}/{BRANCH}/{FILE_PATH}"
        r = requests.get(url)
        if r.status_code == 200:
            backup_file = f"ltcms_state_{today.strftime('%Y%m%d')}.json"
            # Push to GitHub as backup
            url_api = f"https://api.github.com/repos/{REPO}/contents/{backup_file}?ref={BRANCH}"
            headers = {"Authorization": f"token {TOKEN}"}
            r_api = requests.get(url_api, headers=headers)
            sha = None
            if r_api.status_code == 200:
                sha = r_api.json().get("sha")
            data = {
                "message": f"Automated weekly backup {today.strftime('%Y-%m-%d')}",
                "content": base64.b64encode(r.content).decode("utf-8"),
                "branch": BRANCH
            }
            if sha:
                data["sha"] = sha
            put_r = requests.put(url_api, headers=headers, data=json.dumps(data))
            if put_r.status_code not in (200, 201):
                st.error(f"Error creating backup file: {put_r.status_code} - {put_r.text}")

# Early on, run backup in each session (idempotent unless new commits are made)
backup_json_file()

# -------------- Auto-cleanup completed tests -----------------
def cleanup_completed_tests():
    """Remove completed tests and update equipment load percentages"""
    changes_made = False
    for eq_id in list(st.session_state.schedules.keys()):
        schedules = st.session_state.schedules[eq_id]
        original_count = len(schedules)
        
        # Remove completed tests
        st.session_state.schedules[eq_id] = [s for s in schedules if s.get('status') != 'Completed']
        
        if len(st.session_state.schedules[eq_id]) != original_count:
            changes_made = True
            
            # Recalculate load percentage
            remaining_load = sum(s['load_percentage'] for s in st.session_state.schedules[eq_id])
            st.session_state.equipment_data[eq_id]['load_percentage'] = remaining_load
            
            # Update equipment status if no active schedules
            if not st.session_state.schedules[eq_id]:
                current_status = st.session_state.equipment_data[eq_id]['status']
                if current_status == 'Scheduled':
                    st.session_state.equipment_data[eq_id]['status'] = 'Idle'
    
    if changes_made:
        save_app_state()

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
    st.session_state.show_edit_equipment = None
    st.session_state.show_all_schedules = False
    st.session_state.show_calendar = None
    st.session_state.search_term = ""
    st.session_state.app_state_loaded = True

cleanup_completed_tests()

def reset_all_modals():
    st.session_state.show_add_equipment = False
    st.session_state.show_schedule_form = None
    st.session_state.show_settings = None
    st.session_state.show_test_status = False
    st.session_state.show_edit_equipment = None
    st.session_state.show_all_schedules = False
    st.session_state.show_calendar = None

# -------------- Constants and Helpers ------------------------
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
        'parameters': ['amplitude_gs', 'frequency_hz', 'duration', 'num_axis', 'sweep_time', 'num_plates'],
        'defaults': {'amplitude_gs': 5.0, 'frequency_hz': 100, 'duration': 60, 'num_axis': 3, 'sweep_time': 10, 'num_plates': 3},
        'display_params': ['amplitude_gs', 'frequency_hz', 'num_axis', 'duration', 'num_plates']
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
        'pulse_width': 'Width',
        'num_plates': 'Plates'
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
        'sweep_time': 'min',
        'num_plates': 'plates'
    }
    return units.get(param_name, '')

def create_mini_donut(load_percentage, size=60):
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
        margin=dict(t=0, b=20, l=0, r=80),
        annotations=[{
            'text': f'<b>{load_percentage}%</b>',
            'x': 0.5, 'y': 0.5,
            'font_size': 7,
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

def parse_date(val):
    # Accept date, pd.Timestamp, or string
    if isinstance(val, date):
        return val
    if isinstance(val, datetime):
        return val.date()
    if isinstance(val, pd.Timestamp):
        return val.to_pydatetime().date()
    try:
        return datetime.strptime(val, "%Y-%m-%d").date()
    except Exception:
        return date.today()
# -------------- Modal: Add Equipment --------------------
@st.dialog("Add New Equipment")
def add_equipment_modal():
    st.markdown("### ➕ Add New Equipment")
    
    col1, col2, col3, col4 = st.columns(4)
    with col1:
        equipment_id = st.text_input("Equipment ID", placeholder="e.g., TS001, TH002", key="new_eq_id")
        equipment_name = st.text_input("Equipment Name", placeholder="e.g., Thermal Shock Chamber TS001", key="new_eq_name")
        equipment_type = st.selectbox("Equipment Type", options=list(EQUIPMENT_GROUPS.keys())[1:],
                                      format_func=lambda x: EQUIPMENT_GROUPS[x]['name'], key="new_eq_type")
    with col2:
        location = st.text_input("Location", placeholder="e.g., Lab A-1", key="new_eq_location")
        status = st.selectbox("Status", options=['Idle', 'Running', 'Maintenance', 'Scheduled'], key="new_eq_status")
        channels = 1
        plates = 3
        if equipment_type == 'PULSE_TESTER':
            channels = st.number_input("Number of Channels", min_value=1, max_value=32, value=8, key="new_eq_channels")
        elif equipment_type == 'VIBRATION':
            plates = st.number_input("Number of Plates", min_value=1, max_value=10, value=3, key="new_eq_plates")
    with col3:
        params = {}
        if equipment_type in EQUIPMENT_GROUPS and 'parameters' in EQUIPMENT_GROUPS[equipment_type]:
            st.markdown("**Equipment Parameters**")
            defaults = EQUIPMENT_GROUPS[equipment_type]['defaults']
            for param in EQUIPMENT_GROUPS[equipment_type]['parameters'][:4]:  # First 4 params
                label = get_parameter_display_name(param)
                unit = get_parameter_unit(param)
                label_with_unit = f"{label} ({unit})" if unit else label
                if param == 'num_plates':
                    params[param] = plates
                else:
                    params[param] = st.number_input(label_with_unit, value=float(defaults[param]), key=f"new_param_{param}")
    with col4:
        if equipment_type in EQUIPMENT_GROUPS and 'parameters' in EQUIPMENT_GROUPS[equipment_type]:
            remaining_params = EQUIPMENT_GROUPS[equipment_type]['parameters'][4:]
            if remaining_params:
                st.markdown("**Additional Parameters**")
                for param in remaining_params:
                    if param not in params:
                        label = get_parameter_display_name(param)
                        unit = get_parameter_unit(param)
                        label_with_unit = f"{label} ({unit})" if unit else label
                        params[param] = st.number_input(label_with_unit, value=float(defaults[param]), key=f"new_param_{param}")
    col_add, col_cancel = st.columns([1,1])
    with col_add:
        if st.button("✅ Add Equipment", type="primary", use_container_width=True):
            if equipment_id and equipment_name:
                if equipment_id in st.session_state.equipment_data:
                    st.error("Equipment ID already exists!")
                else:
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
                    elif equipment_type == 'VIBRATION':
                        equipment_data['plates'] = plates
                    st.session_state.equipment_data[equipment_id] = equipment_data
                    save_app_state()
                    st.success(f"✅ Equipment {equipment_id} added successfully!")
                    st.session_state.show_add_equipment = False
                    st.rerun()
            else:
                st.error("Please fill in Equipment ID and Name")
    with col_cancel:
        if st.button("❌ Cancel", use_container_width=True):
            st.session_state.show_add_equipment = False
            st.rerun()

# -------------- Modal: All Schedules View --------------------
@st.dialog("All Schedules & Requests")
def all_schedules_modal():
    st.markdown("### 📋 Complete Schedule History")

    # Get all schedules
    all_schedules = []
    for eq_id, schedules in st.session_state.schedules.items():
        for i, schedule in enumerate(schedules):
            schedule_data = schedule.copy()
            schedule_data['equipment_id'] = eq_id
            schedule_data['schedule_index'] = i
            all_schedules.append(schedule_data)

    if not all_schedules:
        st.info("No schedules found.")
        if st.button("❌ Close"):
            st.session_state.show_all_schedules = False
            st.rerun()
        return

    # Filter options
    col1, col2, col3, col4 = st.columns(4)
    with col1:
        status_filter = st.selectbox("Filter by Status",
                                     options=['All'] + TEST_STATUS_OPTIONS,
                                     key="all_schedules_status_filter")
    with col2:
        equipment_filter = st.selectbox("Filter by Equipment",
                                        options=['All'] + list(st.session_state.equipment_data.keys()),
                                        key="all_schedules_equipment_filter")
    with col3:
        user_filter = st.text_input("Filter by User", key="all_schedules_user_filter")
    with col4:
        date_filter = st.date_input("Filter by Date", value=None, key="all_schedules_date_filter")

    # Apply filters
    filtered_schedules = all_schedules.copy()

    if status_filter != 'All':
        filtered_schedules = [s for s in filtered_schedules if s.get('status') == status_filter]

    if equipment_filter != 'All':
        filtered_schedules = [s for s in filtered_schedules if s.get('equipment_id') == equipment_filter]

    if user_filter:
        filtered_schedules = [s for s in filtered_schedules if user_filter.lower() in s.get('user', '').lower()]

    if date_filter:
        filtered_schedules = [s for s in filtered_schedules
                             if s.get('start_date') == date_filter or s.get('end_date') == date_filter]

    st.markdown(f"#### Showing {len(filtered_schedules)} of {len(all_schedules)} total schedules")

    if filtered_schedules:
        # Display schedules with delete option
        st.markdown("#### Schedule List")
        cols = st.columns([2, 2, 2, 2, 2, 1.5, 1.5, 1.5, 1])
        headers = ["Equipment", "Test ID", "User", "Start Date", "End Date", "Status", "Load%", "Created", "Delete"]
        for col, header in zip(cols, headers):
            col.markdown(f"**{header}**")
        st.markdown("---")

        for schedule in filtered_schedules:
            schedule_id = schedule.get('schedule_id', str(uuid.uuid4()))
            eq_id = schedule['equipment_id']
            i = schedule['schedule_index']
            cols = st.columns([2, 2, 2, 2, 2, 1.5, 1.5, 1.5, 1])

            with cols[0]:
                st.write(schedule.get('equipment_id', 'Unknown'))
            with cols[1]:
                st.write(schedule.get('test_id', 'N/A'))
            with cols[2]:
                st.write(schedule.get('user', 'N/A'))
            with cols[3]:
                st.write(str(schedule.get('start_date', 'N/A')))
            with cols[4]:
                st.write(str(schedule.get('end_date', 'N/A')))
            with cols[5]:
                st.write(schedule.get('status', 'Unknown'))
            with cols[6]:
                st.write(f"{schedule.get('load_percentage', 0)}%")
            with cols[7]:
                created_at = schedule.get('created_at', 'N/A')
                if isinstance(created_at, datetime):
                    created_at = created_at.strftime("%Y-%m-%d %H:%M")
                st.write(created_at)
            with cols[8]:
                if st.button("🗑️", key=f"delete_schedule_{schedule_id}_{i}"):
                    # Remove the schedule
                    removed = st.session_state.schedules[eq_id].pop(i)
                    # Update equipment load
                    remaining_load = sum(s['load_percentage'] for s in st.session_state.schedules[eq_id])
                    st.session_state.equipment_data[eq_id]['load_percentage'] = remaining_load
                    # Update equipment status if no schedules remain
                    if not st.session_state.schedules[eq_id]:
                        st.session_state.equipment_data[eq_id]['status'] = 'Idle'
                    save_app_state()
                    st.success(f"Test {removed['test_id']} permanently deleted.")
                    st.rerun()

            # Display additional info (e.g., Channels, Plates)
            if 'channels' in schedule or 'plates' in schedule:
                extra_info = []
                if 'channels' in schedule:
                    extra_info.append(f"Channels: {', '.join(map(str, schedule['channels']))}")
                if 'plates' in schedule:
                    extra_info.append(f"Plates: {', '.join(map(str, schedule['plates']))}")
                st.markdown(f"<div style='font-size:12px;color:#666;padding-left:20px;'>{' | '.join(extra_info)}</div>", unsafe_allow_html=True)

            st.markdown("---")

        # Export options
        col_export1, col_export2, col_close = st.columns(3)
        with col_export1:
            rows = []
            for schedule in filtered_schedules:
                row_data = {
                    'Equipment': schedule.get('equipment_id', 'Unknown'),
                    'Test ID': schedule.get('test_id', 'N/A'),
                    'User': schedule.get('user', 'N/A'),
                    'Start Date': schedule.get('start_date', 'N/A'),
                    'End Date': schedule.get('end_date', 'N/A'),
                    'Load %': schedule.get('load_percentage', 0),
                    'Priority': schedule.get('priority', 'Medium'),
                    'Status': schedule.get('status', 'Unknown'),
                    'Created': schedule.get('created_at', 'N/A')
                }
                if 'channels' in schedule:
                    row_data['Channels'] = ', '.join(map(str, schedule['channels']))
                if 'plates' in schedule:
                    row_data['Plates'] = ', '.join(map(str, schedule['plates']))
                rows.append(row_data)
            df = pd.DataFrame(rows)
            csv = df.to_csv(index=False)
            st.download_button("📥 Export to CSV",
                              data=csv,
                              file_name=f"ltcms_all_schedules_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv",
                              mime="text/csv",
                              use_container_width=True)

        with col_export2:
            if len(filtered_schedules) != len(all_schedules):
                csv = df.to_csv(index=False)
                st.download_button("📥 Export Filtered",
                                  data=csv,
                                  file_name=f"ltcms_filtered_schedules_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv",
                                  mime="text/csv",
                                  use_container_width=True)

        with col_close:
            if st.button("❌ Close", use_container_width=True):
                st.session_state.show_all_schedules = False
                st.rerun()
    else:
        st.info("No schedules match the current filters.")
        if st.button("❌ Close"):
            st.session_state.show_all_schedules = False
            st.rerun()
            
# -------------- Modal: Edit Equipment with editable ID (#3 change) --------------------
@st.dialog("Edit Equipment")
def edit_equipment_modal(equipment_id):
    st.markdown(f"### ✏️ Edit Equipment: {equipment_id}")
    equipment = st.session_state.equipment_data[equipment_id]

    col1, col2, col3, col4 = st.columns(4)
    with col1:
        new_eq_id = st.text_input("Equipment ID", value=equipment_id, key="edit_eq_id")  # Editable!
        new_name = st.text_input("Equipment Name", value=equipment['name'], key="edit_eq_name")
        new_location = st.text_input("Location", value=equipment['location'], key="edit_eq_location")
        new_status = st.selectbox("Status", ['Idle', 'Running', 'Maintenance', 'Scheduled'],
                                index=['Idle', 'Running', 'Maintenance', 'Scheduled'].index(equipment['status']), key="edit_eq_status")
    with col2:
        st.write(f"**Type:** {EQUIPMENT_GROUPS[equipment['type']]['name']}")
        st.write(f"**Current Load:** {equipment['load_percentage']}%")
        if equipment['type'] == 'PULSE_TESTER':
            new_channels = st.number_input("Number of Channels", min_value=1, max_value=32,
                                          value=equipment.get('channels', 8), key="edit_eq_channels")
        elif equipment['type'] == 'VIBRATION':
            new_plates = st.number_input("Number of Plates", min_value=1, max_value=10,
                                        value=equipment.get('plates', 3), key="edit_eq_plates")
        else:
            new_channels = None
            new_plates = None
    with col3:
        new_params = {}
        if 'parameters' in equipment:
            st.markdown("**Equipment Parameters**")
            params_list = list(equipment['parameters'].items())
            half_point = len(params_list) // 2
            for param, value in params_list[:half_point]:
                label = get_parameter_display_name(param)
                unit = get_parameter_unit(param)
                label_with_unit = f"{label} ({unit})" if unit else label
                new_params[param] = st.number_input(label_with_unit, value=float(value), key=f"edit_param_{param}_{equipment_id}")
    with col4:
        if 'parameters' in equipment and len(equipment['parameters']) > 1:
            st.markdown("**Additional Parameters**")
            params_list = list(equipment['parameters'].items())
            half_point = len(params_list) // 2
            for param, value in params_list[half_point:]:
                label = get_parameter_display_name(param)
                unit = get_parameter_unit(param)
                label_with_unit = f"{label} ({unit})" if unit else label
                new_params[param] = st.number_input(label_with_unit, value=float(value), key=f"edit_param2_{param}_{equipment_id}")
    col_save, col_delete, col_cancel = st.columns(3)
    with col_save:
        if st.button("💾 Save Changes", type="primary", use_container_width=True):
            if new_eq_id != equipment_id:
                if new_eq_id in st.session_state.equipment_data:
                    st.error("Equipment ID already exists!")
                    return
                # Move equipment data & schedules to new ID key
                st.session_state.equipment_data[new_eq_id] = st.session_state.equipment_data.pop(equipment_id)
                if equipment_id in st.session_state.schedules:
                    st.session_state.schedules[new_eq_id] = st.session_state.schedules.pop(equipment_id)
                equipment_id = new_eq_id  # for further updates
            st.session_state.equipment_data[equipment_id]['name'] = new_name
            st.session_state.equipment_data[equipment_id]['location'] = new_location
            st.session_state.equipment_data[equipment_id]['status'] = new_status
            st.session_state.equipment_data[equipment_id]['last_updated'] = datetime.now()
            if new_channels is not None:
                st.session_state.equipment_data[equipment_id]['channels'] = new_channels
            if new_plates is not None:
                st.session_state.equipment_data[equipment_id]['plates'] = new_plates
            if new_params:
                st.session_state.equipment_data[equipment_id]['parameters'] = new_params
            save_app_state()
            st.success(f"✅ Equipment {equipment_id} updated successfully!")
            st.session_state.show_edit_equipment = None
            st.rerun()
    with col_delete:
        if st.button("🗑️ Delete Equipment", type="secondary", use_container_width=True):
            if equipment_id in st.session_state.equipment_data:
                del st.session_state.equipment_data[equipment_id]
            if equipment_id in st.session_state.schedules:
                del st.session_state.schedules[equipment_id]
            save_app_state()
            st.success(f"✅ Equipment {equipment_id} deleted successfully!")
            st.session_state.show_edit_equipment = None
            st.rerun()
    with col_cancel:
        if st.button("❌ Cancel", use_container_width=True):
            st.session_state.show_edit_equipment = None
            st.rerun()

# -------------- Modal: Schedule Test ----------------------
@st.dialog("Schedule Test")
def schedule_test_modal(equipment_id):
    st.markdown(f"### 📅 Schedule Test for {equipment_id}")
    equipment = st.session_state.equipment_data[equipment_id]

    # Collect currently blocked dates for reference only
    blocked_dates = set()
    if equipment_id in st.session_state.schedules:
        for schedule in st.session_state.schedules[equipment_id]:
            if schedule['status'] in ['Scheduled', 'In Progress']:
                start_date = schedule['start_date']
                end_date = schedule['end_date']
                if isinstance(start_date, str):
                    start_date = datetime.strptime(start_date, "%Y-%m-%d").date()
                if isinstance(end_date, str):
                    end_date = datetime.strptime(end_date, "%Y-%m-%d").date()
                current_date = start_date
                while current_date <= end_date:
                    blocked_dates.add(current_date)
                    current_date += timedelta(days=1)

    col1, col2, col3, col4 = st.columns(4)
    with col1:
        test_id = st.text_input("Test ID", placeholder="e.g., LTC-2024-001", key="schedule_test_id")
        user_name = st.text_input("Assigned User", placeholder="Enter user name", key="schedule_user")
        load_percentage = st.slider("Load Percentage (%)", 1, 100, 50, 1, key="schedule_load")
    with col2:
        start_date = st.date_input("Start Date", value=date.today(), key="schedule_start")
        end_date = st.date_input("End Date", value=date.today() + timedelta(days=7), key="schedule_end")
        priority = st.selectbox("Priority", options=["Low", "Medium", "High", "Critical"], index=1, key="schedule_priority")
        # Show date conflicts but allow scheduling
        conflict_dates = []
        if start_date and end_date:
            current_date = start_date
            while current_date <= end_date:
                if current_date in blocked_dates:
                    conflict_dates.append(current_date)
                current_date += timedelta(days=1)
        if conflict_dates:
            st.warning(f"⚠️ The following dates have existing schedules: {', '.join([d.strftime('%Y-%m-%d') for d in conflict_dates])}. You can still schedule this test.")
    with col3:
        selected_channels = []
        selected_plates = []
        if equipment['type'] == 'PULSE_TESTER':
            available_channels = list(range(1, equipment.get('channels', 8) + 1))
            selected_channels = st.multiselect("Select Channels", options=available_channels, default=[1], key="schedule_channels")
        elif equipment['type'] == 'VIBRATION':
            available_plates = list(range(1, equipment.get('plates', 3) + 1))
            selected_plates = st.multiselect("Select Plates", options=available_plates, default=[1], key="schedule_plates")
    with col4:
        test_params = {}
        if equipment['type'] in EQUIPMENT_GROUPS and 'parameters' in EQUIPMENT_GROUPS[equipment['type']]:
            st.markdown("**Test Parameters**")
            defaults = EQUIPMENT_GROUPS[equipment['type']]['defaults']
            for param in EQUIPMENT_GROUPS[equipment['type']]['parameters'][:4]:
                label = get_parameter_display_name(param)
                unit = get_parameter_unit(param)
                label_with_unit = f"Test {label} ({unit})" if unit else f"Test {label}"
                test_params[param] = st.number_input(label_with_unit, value=float(defaults[param]), key=f"test_param_{param}")
    test_description = st.text_area("Test Description", placeholder="Enter test conditions and requirements...", key="schedule_description")
    col_schedule, col_calendar, col_cancel = st.columns(3)
    with col_schedule:
        if st.button("📅 Schedule Test", type="primary", use_container_width=True):
            if not test_id or not user_name:
                st.error("Please fill in Test ID and User name")
                return
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
            if equipment['type'] == 'VIBRATION' and selected_plates:
                schedule_data['plates'] = selected_plates
            st.session_state.schedules[equipment_id].append(schedule_data)
            current_load = sum(s['load_percentage'] for s in st.session_state.schedules[equipment_id])
            st.session_state.equipment_data[equipment_id]['load_percentage'] = min(current_load, 100)
            cur_status = st.session_state.equipment_data[equipment_id]['status']
            if cur_status not in ['Running', 'Maintenance']:
                st.session_state.equipment_data[equipment_id]['status'] = 'Scheduled'
            save_app_state()
            st.success(f"✅ Test {test_id} scheduled successfully!")
            st.session_state.show_schedule_form = None
            st.rerun()
    with col_calendar:
        if st.button("📅 View Calendar", use_container_width=True):
            st.session_state.show_calendar = equipment_id
            st.rerun()
    with col_cancel:
        if st.button("❌ Cancel", use_container_width=True):
            st.session_state.show_schedule_form = None
            st.rerun()

# -------------- Modal: Equipment Settings -----------------
@st.dialog("Equipment Settings")
def equipment_settings_modal(equipment_id):
    st.markdown(f"### ⚙️ Settings for {equipment_id}")
    equipment = st.session_state.equipment_data[equipment_id]

    col1, col2, col3 = st.columns(3)
    with col1:
        new_status = st.selectbox("Equipment Status", 
                                  ['Idle', 'Running', 'Maintenance', 'Scheduled'], 
                                  index=['Idle', 'Running', 'Maintenance', 'Scheduled'].index(equipment['status']), 
                                  key=f"settings_status_{equipment_id}")
        st.write(f"**Equipment Type:** {EQUIPMENT_GROUPS[equipment['type']]['name']}")
        st.write(f"**Location:** {equipment['location']}")
        st.write(f"**Current Load:** {equipment['load_percentage']}%")
        if equipment['type'] == 'PULSE_TESTER':
            new_channels = st.number_input("Number of Channels", min_value=1, max_value=32, 
                                          value=equipment.get('channels', 8), key=f"settings_channels_{equipment_id}")
        elif equipment['type'] == 'VIBRATION':
            new_plates = st.number_input("Number of Plates", min_value=1, max_value=10,
                                        value=equipment.get('plates', 3), key=f"settings_plates_{equipment_id}")
        else:
            new_channels = None
            new_plates = None
    with col2:
        if 'parameters' in equipment:
            st.markdown("### Current Parameters")
            for param, value in equipment['parameters'].items():
                label = get_parameter_display_name(param)
                unit = get_parameter_unit(param)
                st.write(f"**{label}:** {value} {unit}")
    with col3:
        new_params = {}
        if 'parameters' in equipment:
            st.markdown("### Edit Parameters")
            for param, value in equipment['parameters'].items():
                label = get_parameter_display_name(param)
                unit = get_parameter_unit(param)
                label_with_unit = f"{label} ({unit})" if unit else label
                new_params[param] = st.number_input(label_with_unit, value=float(value), key=f"settings_param_{param}_{equipment_id}")
    col_apply, col_cancel = st.columns([1,1])
    with col_apply:
        if st.button("✅ Apply Changes", type="primary", use_container_width=True):
            st.session_state.equipment_data[equipment_id]['status'] = new_status
            st.session_state.equipment_data[equipment_id]['last_updated'] = datetime.now()
            if new_channels is not None:
                st.session_state.equipment_data[equipment_id]['channels'] = new_channels
            if new_plates is not None:
                st.session_state.equipment_data[equipment_id]['plates'] = new_plates
            if new_params:
                st.session_state.equipment_data[equipment_id]['parameters'] = new_params
            save_app_state()
            st.success(f"✅ Settings updated for {equipment_id}")
            st.session_state.show_settings = None
            st.rerun()
    with col_cancel:
        if st.button("❌ Cancel", use_container_width=True):
            st.session_state.show_settings = None
            st.rerun()

# -------------- Modal: Active Test Status Management ----------------
@st.dialog("Active Test Status Management")
def test_status_modal():
    st.markdown("### 📋 Active Test Status Management")

    all_schedules = []
    for eq_id, schedules in st.session_state.schedules.items():
        for i, schedule in enumerate(schedules):
            schedule_data = schedule.copy()
            schedule_data['equipment_id'] = eq_id
            schedule_data['schedule_index'] = i
            all_schedules.append(schedule_data)

    if not all_schedules:
        st.info("No active tests found.")
        if st.button("❌ Close", use_container_width=True):
            st.session_state.show_test_status = False
            st.rerun()
        return

    st.markdown("#### Edit test details below:")

    # Define column widths for better alignment
    cols = st.columns([2, 2, 2, 2, 2, 1.5, 1.5, 1.5, 1])
    headers = ["Equipment", "Test ID", "User", "Start Date", "End Date", "Status", "Load%", "Action", "Save"]
    for col, header in zip(cols, headers):
        col.markdown(f"**{header}**")

    st.markdown("---")

    for schedule in all_schedules:
        schedule_id = schedule.get('schedule_id', str(uuid.uuid4()))
        eq_id = schedule['equipment_id']
        i = schedule['schedule_index']

        cols = st.columns([2, 2, 2, 2, 2, 1.5, 1.5, 1.5, 1])

        with cols[0]:
            st.write(eq_id)

        with cols[1]:
            new_test_id = st.text_input("", value=schedule['test_id'], key=f"test_id_{schedule_id}_{i}", label_visibility="collapsed")

        with cols[2]:
            new_user = st.text_input("", value=schedule['user'], key=f"user_{schedule_id}_{i}", label_visibility="collapsed")

        with cols[3]:
            start_date = parse_date(schedule['start_date'])
            new_start_date = st.date_input("", value=start_date, key=f"start_date_{schedule_id}_{i}", label_visibility="collapsed")

        with cols[4]:
            end_date = parse_date(schedule['end_date'])
            new_end_date = st.date_input("", value=end_date, key=f"end_date_{schedule_id}_{i}", label_visibility="collapsed")

        with cols[5]:
            status_idx = TEST_STATUS_OPTIONS.index(schedule['status']) if schedule['status'] in TEST_STATUS_OPTIONS else 0
            new_status = st.selectbox("", TEST_STATUS_OPTIONS, index=status_idx, key=f"status_{schedule_id}_{i}", label_visibility="collapsed")

        with cols[6]:
            new_load = st.number_input("", min_value=1, max_value=100, value=schedule['load_percentage'], key=f"load_{schedule_id}_{i}", label_visibility="collapsed")

        with cols[7]:
            delete_me = st.button("🗑️", key=f"delete_{schedule_id}_{i}")

        with cols[8]:
            save_me = st.button("💾", key=f"save_{schedule_id}_{i}")

        # Handle Save button
        if save_me:
            # Validate inputs
            if not new_test_id or not new_user:
                st.error(f"Please provide Test ID and User for test {schedule['test_id']}")
                continue
            if new_start_date > new_end_date:
                st.error(f"Start Date cannot be after End Date for test {schedule['test_id']}")
                continue

            # Update schedule data
            st.session_state.schedules[eq_id][i]['test_id'] = new_test_id
            st.session_state.schedules[eq_id][i]['user'] = new_user
            st.session_state.schedules[eq_id][i]['start_date'] = new_start_date
            st.session_state.schedules[eq_id][i]['end_date'] = new_end_date
            st.session_state.schedules[eq_id][i]['status'] = new_status
            st.session_state.schedules[eq_id][i]['load_percentage'] = new_load

            # Recalculate equipment load percentage
            remaining_load = sum(s['load_percentage'] for s in st.session_state.schedules[eq_id])
            st.session_state.equipment_data[eq_id]['load_percentage'] = min(remaining_load, 100)

            # Update equipment status if needed
            if not any(s['status'] in ['Scheduled', 'In Progress'] for s in st.session_state.schedules[eq_id]):
                st.session_state.equipment_data[eq_id]['status'] = 'Idle'
            elif new_status in ['Scheduled', 'In Progress']:
                st.session_state.equipment_data[eq_id]['status'] = 'Scheduled'

            if new_status == 'Completed':
                cleanup_completed_tests()

            save_app_state()
            st.success(f"Test {new_test_id} updated successfully!")
            st.rerun()

        # Handle Delete button
        if delete_me:
            removed = st.session_state.schedules[eq_id].pop(i)
            remaining_load = sum(s['load_percentage'] for s in st.session_state.schedules[eq_id])
            st.session_state.equipment_data[eq_id]['load_percentage'] = remaining_load
            if not st.session_state.schedules[eq_id]:
                st.session_state.equipment_data[eq_id]['status'] = 'Idle'
            save_app_state()
            st.success(f"Test {removed['test_id']} deleted.")
            st.rerun()

        st.markdown("---")

    if st.button("❌ Close", use_container_width=True):
        st.session_state.show_test_status = False
        st.rerun()
        
# -------- Equipment Calendar ----------------------
@st.dialog("Equipment Calendar")
def calendar_modal(equipment_id):
    # Defensive check: ensure equipment_id exists
    if equipment_id not in st.session_state.equipment_data:
        st.error(f"Equipment ID '{equipment_id}' not found.")
        if st.button("❌ Close"):
            st.session_state.show_calendar = None
            st.rerun()
        return

    import calendar
    from datetime import datetime, date, timedelta

    st.markdown(f"### 📅 Calendar View: {equipment_id}")
    
    col1, col2 = st.columns([2, 1])
    
    with col1:
        # Calendar controls: month and year selectors
        today = date.today()
        selected_month = st.selectbox(
            "Month", 
            options=list(range(1, 13)), 
            index=today.month - 1,
            format_func=lambda x: calendar.month_name[x]
        )
        selected_year = st.number_input(
            "Year", min_value=2024, max_value=2030, value=today.year
        )
        
        # Generate month calendar (weeks with days or zeros)
        cal = calendar.monthcalendar(selected_year, selected_month)
        
        # Collect blocked dates for this equipment in this month
        blocked_dates = set()
        if equipment_id in st.session_state.schedules:
            for schedule in st.session_state.schedules[equipment_id]:
                if schedule.get('status') in ['Scheduled', 'In Progress']:
                    start_date = schedule.get('start_date')
                    end_date = schedule.get('end_date')

                    # Defensive date conversion
                    try:
                        if isinstance(start_date, str):
                            start_date = datetime.strptime(start_date, "%Y-%m-%d").date()
                        if isinstance(end_date, str):
                            end_date = datetime.strptime(end_date, "%Y-%m-%d").date()
                    except Exception as e:
                        st.warning(f"Warning: Could not parse dates for test '{schedule.get('test_id', 'N/A')}': {e}")
                        continue

                    current_date = start_date
                    while current_date <= end_date:
                        blocked_dates.add(current_date)
                        current_date += timedelta(days=1)
        
        st.markdown("#### Calendar")
        # Day headers
        days = ['Mon', 'Tue', 'Wed', 'Thu', 'Fri', 'Sat', 'Sun']
        header_cols = st.columns(7)
        for i, day in enumerate(days):
            header_cols[i].markdown(f"**{day}**")
        
        # Helper function to get inline CSS for calendar day boxes
        def get_inline_style(status):
            base = (
                "border:1px solid #ddd; padding:10px 5px; margin:1px; "
                "border-radius:4px; text-align:center; font-weight:600; font-size:14px; "
                "min-height:40px; min-width:40px; line-height:40px; user-select:none; cursor:default;"
            )
            styles = {
                "available": "background-color:#d4edda; color:#155724;",
                "blocked": "background-color:#f8d7da; color:#721c24;",
                "today":   "background-color:#bee5eb; color:#0c5460; font-weight:700; border:2px solid #0c5460;"
            }
            return base + styles.get(status, "")

        # Render calendar grid with inline styles
        for week in cal:
            week_cols = st.columns(7)
            for i, day in enumerate(week):
                if day == 0:
                    week_cols[i].markdown("")  # empty cell for padding
                else:
                    current_date = date(selected_year, selected_month, day)
                    
                    # Determine day status
                    if current_date in blocked_dates:
                        style = get_inline_style("blocked")
                    elif current_date == today:
                        style = get_inline_style("today")
                    else:
                        style = get_inline_style("available")

                    week_cols[i].markdown(
                        f'<div style="{style}">{day}</div>', unsafe_allow_html=True
                    )
    
    with col2:
        st.markdown("#### Legend")
        st.markdown('🟢 **Available** - Open for scheduling')
        st.markdown('🔴 **Blocked** - Already scheduled')
        st.markdown('🔵 **Today** - Current date')
        
        st.markdown("#### Scheduled Tests This Month")
        month_schedules = []
        if equipment_id in st.session_state.schedules:
            for schedule in st.session_state.schedules[equipment_id]:
                start_date = schedule.get('start_date')
                if isinstance(start_date, str):
                    try:
                        start_date = datetime.strptime(start_date, "%Y-%m-%d").date()
                    except Exception:
                        continue
                
                if start_date.month == selected_month and start_date.year == selected_year:
                    month_schedules.append(schedule)
            
            if month_schedules:
                for schedule in month_schedules:
                    start_day_str = (
                        schedule['start_date'].strftime("%d") 
                        if hasattr(schedule['start_date'], 'strftime') 
                        else str(schedule['start_date'])
                    )
                    st.markdown(f"**{start_day_str}th:** {schedule['test_id']} ({schedule['user']})")
            else:
                st.info("No tests scheduled this month")
    
    if st.button("❌ Close"):
        st.session_state.show_calendar = None
        st.rerun()



# -------------- Render Equipment Card with Progression (#4) -----------------------
def render_equipment_card(eq_id, eq_data):
    group_info = EQUIPMENT_GROUPS[eq_data['type']]
    card_html = f'''
    <div class="equipment-card">
        <div class="equipment-header">{group_info['icon']} {eq_id}</div>
        <div class="status-badge status-{eq_data['status'].lower()}">{eq_data['status']}</div>
    '''
    st.markdown(card_html, unsafe_allow_html=True)

    st.markdown('<div class="parameter-section">', unsafe_allow_html=True)
    st.markdown('<div class="parameter-title">Equipment Parameters</div>', unsafe_allow_html=True)
    for param in group_info.get('display_params', []):
        if 'parameters' in eq_data and param in eq_data['parameters']:
            label = get_parameter_display_name(param)
            unit = get_parameter_unit(param)
            value = eq_data['parameters'][param]
            st.markdown(f'<div class="parameter-item">{label}: <b>{value} {unit}</b></div>', unsafe_allow_html=True)

    if eq_data['type'] == 'VIBRATION' and 'plates' in eq_data:
        st.markdown(f'<div class="parameter-item">Available Plates: <b>{eq_data["plates"]}</b></div>', unsafe_allow_html=True)
    st.markdown('</div>', unsafe_allow_html=True)

    # Scheduled tests (exclude completed ones)
    active_schedules = []
    if eq_id in st.session_state.schedules:
        active_schedules = [s for s in st.session_state.schedules[eq_id] if s.get('status') != 'Completed']

    for schedule in active_schedules:
        sd = schedule["start_date"]
        ed = schedule["end_date"]
        start_str = sd.strftime("%Y-%m-%d") if hasattr(sd, "strftime") else sd
        end_str = ed.strftime("%Y-%m-%d") if hasattr(ed, "strftime") else ed

        extra_info = ""
        if 'channels' in schedule:
            extra_info = f" | 📡 Ch: {','.join(map(str, schedule['channels']))}"
        elif 'plates' in schedule:
            extra_info = f" | 🔲 Plates: {','.join(map(str, schedule['plates']))}"

        # Calculate progression %
        total_days = (parse_date(ed) - parse_date(sd)).days + 1
        elapsed_days = (date.today() - parse_date(sd)).days + 1
        progression = None
        if total_days > 0 and elapsed_days > 0:
            progression = int((elapsed_days / total_days) * 100)
            progression = min(max(progression, 0), 100)

        st.markdown(
            f'<div class="test-item">📋 <b>{schedule["test_id"]}</b> | 👤 {schedule["user"]} | '
            f'📊 {schedule["load_percentage"]}% | 🗓 {start_str} ➔ {end_str}{extra_info}'
            + (f'<br>🟦 Progress: {progression}%'
               f'<div class="progress-bar"><div class="progress-fill" style="width:{progression}%;"></div></div>'
                if progression is not None else '')
            + '</div>',
            unsafe_allow_html=True
        )

    col_chart, col_buttons = st.columns([1, 3])
    with col_chart:
        fig = create_mini_donut(eq_data['load_percentage'], 60)
        st.plotly_chart(fig, config={'displayModeBar': False}, use_container_width=True, key=f"chart_{eq_id}")
    with col_buttons:
        col_schedule, col_calendar, col_settings, col_edit = st.columns(4)
        with col_schedule:
            if st.button("📅", key=f"schedule_btn_{eq_id}", help="Schedule Test"):
                reset_all_modals()
                st.session_state.show_schedule_form = eq_id
                st.rerun()
        with col_calendar:
            if st.button("📆", key=f"calendar_btn_{eq_id}", help="View Calendar"):
                reset_all_modals()
                st.session_state.show_calendar = eq_id
                st.rerun()
        with col_settings:
            if st.button("⚙️", key=f"settings_btn_{eq_id}", help="Settings"):
                reset_all_modals()
                st.session_state.show_settings = eq_id
                st.rerun()
        with col_edit:
            if st.button("✏️", key=f"edit_btn_{eq_id}", help="Edit Equipment"):
                reset_all_modals()
                st.session_state.show_edit_equipment = eq_id
                st.rerun()

    st.markdown('</div>', unsafe_allow_html=True)
# -------------- Main function -----------------------------
def main():
    # Show modals
    if st.session_state.show_add_equipment: 
        add_equipment_modal()
    if st.session_state.show_schedule_form is not None: 
        schedule_test_modal(st.session_state.show_schedule_form)
    if st.session_state.show_settings is not None: 
        equipment_settings_modal(st.session_state.show_settings)
    if st.session_state.show_test_status: 
        test_status_modal()
    if st.session_state.show_edit_equipment is not None:
        edit_equipment_modal(st.session_state.show_edit_equipment)
    if st.session_state.show_all_schedules:
        all_schedules_modal()
    if st.session_state.show_calendar is not None:
        calendar_modal(st.session_state.show_calendar)

    st.title("🏭 LTCMS - Lipa Technical Center Management System")
    st.markdown("**Real-time Equipment & Test Management Dashboard**")

    # Sidebar controls
    with st.sidebar:
        st.sidebar.image(
            "https://raw.githubusercontent.com/LukeyMe/LTCMS/main/LFpng.png",
            use_container_width=True,
            caption="Lipa Technical Center"
        )
        st.header("🔧 System Controls")
        if st.button("➕ Add New Equipment", use_container_width=True):
            reset_all_modals()
            st.session_state.show_add_equipment = True
            st.rerun()

        if st.button("📋 Manage Active Tests", use_container_width=True):
            reset_all_modals()
            st.session_state.show_test_status = True
            st.rerun()

        if st.button("📊 See All Schedules", use_container_width=True):
            reset_all_modals()
            st.session_state.show_all_schedules = True
            st.rerun()

        st.markdown("---")
        st.markdown("**🔍 Search Equipment**")
        search_term = st.text_input("", placeholder="Search by ID or name...", key="equipment_search")
        st.session_state.search_term = search_term.lower()
        st.markdown("---")
        if st.button("🔄 Refresh Dashboard", use_container_width=True): 
            cleanup_completed_tests()
            st.rerun()

        st.markdown("---")
        total_equipment = len(st.session_state.equipment_data)
        total_schedules = sum(len([s for s in schedules if s.get('status') != 'Completed']) 
                              for schedules in st.session_state.schedules.values())
        completed_tests = sum(len([s for s in schedules if s.get('status') == 'Completed']) 
                              for schedules in st.session_state.schedules.values())
        st.metric("Total Equipment", total_equipment)
        st.metric("Active Schedules", total_schedules)
        st.metric("Completed Tests", completed_tests)
        if total_equipment > 0:
            avg_utilization = sum(eq['load_percentage'] for eq in st.session_state.equipment_data.values()) / total_equipment
            st.metric("Avg Utilization", f"{avg_utilization:.1f}%")
        if total_equipment > 0:
            st.markdown("---")
            st.markdown("**📈 Utilization Chart**")
            equipment_names = list(st.session_state.equipment_data.keys())
            utilizations = [st.session_state.equipment_data[eq]['load_percentage'] for eq in equipment_names]
            fig = px.bar(x=equipment_names, y=utilizations, 
                         title="Equipment Utilization %", color=utilizations,
                         color_continuous_scale="RdYlGn_r")
            fig.update_layout(height=300, showlegend=False)
            st.plotly_chart(fig, use_container_width=True)

    # Summary cards
    st.markdown("## 📊 System Dashboard")
    if not st.session_state.equipment_data:
        st.info("👆 **Welcome to LTCMS!** Click 'Add New Equipment' in the sidebar to get started.")
        return

    equipment = st.session_state.equipment_data
    # Group filtering (#1)
    group_filter = st.session_state.selected_group
    if group_filter == 'ALL':
        filtered_equipment = equipment
    else:
        filtered_equipment = {k: v for k, v in equipment.items() if v['type'] == group_filter}

    filtered = filtered_equipment
    if st.session_state.search_term:
        filtered = {k: v for k, v in filtered.items()
                    if st.session_state.search_term in k.lower() or
                       st.session_state.search_term in v['name'].lower()}

    counts = {s: sum(1 for eq in filtered_equipment.values() if eq['status'] == s.capitalize())
              for s in ['running', 'idle', 'maintenance', 'scheduled']}
    total_active_tests = sum(
        len([s for s in st.session_state.schedules.get(eqk, []) if s.get('status') != 'Completed'])
        for eqk in filtered_equipment.keys()
    )

    cols = st.columns(5)
    styles = [
        ("running", "#28a745,#20c997", "🟢 RUNNING"),
        ("idle", "#ffc107,#fd7e14", "🟡 IDLE"),
        ("maintenance", "#dc3545,#c82333", "🔴 MAINTENANCE"),
        ("scheduled", "#17a2b8,#138496", "🔵 SCHEDULED"),
        ("total", "#6f42c1,#5a32a3", "📋 ACTIVE TESTS")
    ]
    for col, (key, grad, label) in zip(cols, styles):
        val = counts.get(key, total_active_tests) if key != "total" else total_active_tests
        col.markdown(
            f'''<div class="dashboard-card" style="background: linear-gradient(135deg, {grad});">
            <div class="dashboard-metric">{val}</div>
            <div class="dashboard-label">{label}</div></div>''', unsafe_allow_html=True
        )

    # Equipment group selector
    st.markdown("## 🎯 Equipment Groups")
    grp_cols = st.columns(len(EQUIPMENT_GROUPS))
    for i, (gk, gi) in enumerate(EQUIPMENT_GROUPS.items()):
        with grp_cols[i]:
            if st.button(f"{gi['icon']} {gi['name']}",
                         key=f"group_{gk}",
                         type="primary" if st.session_state.selected_group == gk else "secondary"):
                reset_all_modals()
                st.session_state.selected_group = gk
                st.rerun()

    # Equipment grid
    st.markdown("## 🏭 Equipment Status")
    if not filtered:
        if st.session_state.search_term:
            st.info(f"No equipment found matching '{st.session_state.search_term}'. Try a different search term.")
        else:
            name = EQUIPMENT_GROUPS[st.session_state.selected_group]['name']
            st.info(f"No equipment found in '{name}' group. Add some equipment to get started!")
        return

    st.markdown('<div class="equipment-grid">', unsafe_allow_html=True)
    items = list(filtered.items())
    for row in range(0, len(items), 3):
        cols = st.columns(3)
        for idx in range(3):
            if row + idx < len(items):
                eq_id, eq_data = items[row + idx]
                with cols[idx]:
                    render_equipment_card(eq_id, eq_data)
    st.markdown('</div>', unsafe_allow_html=True)

    # Active schedules overview table for filtered equipment only (#1)
    active_schedules_exist = any(
        any(s.get('status') != 'Completed' for s in st.session_state.schedules.get(eqk, []))
        for eqk in filtered_equipment.keys()
    )

    if active_schedules_exist:
        st.markdown("---")
        st.markdown("## 📋 Active Schedules Overview")
        rows = []
        for eq_id in filtered_equipment.keys():
            for s in st.session_state.schedules.get(eq_id, []):
                if s.get('status') != 'Completed':
                    sd, ed = s['start_date'], s['end_date']
                    row_data = {
                        'Equipment': eq_id,
                        'Test ID': s['test_id'],
                        'User': s['user'],
                        'Start': sd.strftime('%Y-%m-%d') if hasattr(sd, 'strftime') else sd,
                        'End': ed.strftime('%Y-%m-%d') if hasattr(ed, 'strftime') else ed,
                        'Load %': s['load_percentage'],
                        'Priority': s['priority'],
                        'Status': s['status']
                    }
                    # Progression
                    total_days = (parse_date(ed) - parse_date(sd)).days + 1
                    elapsed_days = (date.today() - parse_date(sd)).days + 1
                    progression = int((elapsed_days / total_days) * 100) if total_days > 0 else 0
                    row_data['Progress %'] = f"{min(max(progression, 0), 100)}%"
                    if 'channels' in s:
                        row_data['Channels'] = ', '.join(map(str, s['channels']))
                    if 'plates' in s:
                        row_data['Plates'] = ', '.join(map(str, s['plates']))
                    rows.append(row_data)
        if rows:
            df = pd.DataFrame(rows)
            st.dataframe(df, use_container_width=True, hide_index=True)
            csv = df.to_csv(index=False)
            st.download_button("📥 Export Active Schedule Data", data=csv,
                              file_name=f"ltcms_active_schedules_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv",
                              mime="text/csv")

    st.markdown("---")
    st.markdown(f"**LTCMS Dashboard Active** | **Last Update:** {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")

    if st.session_state.get('cleanup_notification'):
        st.success("✅ Completed tests have been automatically removed from equipment schedules.")
        st.session_state.cleanup_notification = False

if __name__ == "__main__":
    main()
