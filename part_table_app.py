# multi_rack_fg_stock.py
import streamlit as st
import pandas as pd
from datetime import datetime
import hashlib
import io
import math

# ----------------------------
# App config
# ----------------------------
st.set_page_config(page_title="Multi-Rack FG Stock Board", layout="wide")

# ----------------------------
# Demo authenticator (IN-APP demo only)
# ----------------------------
USERS = {
    "Vishal": {"pw_hash": hashlib.sha256(b"master123").hexdigest(), "role": "master"},
    "Kittu": {"pw_hash": hashlib.sha256(b"input123").hexdigest(), "role": "input"},
    "1306764": {"pw_hash": hashlib.sha256(b"output123").hexdigest(), "role": "output"},
}

def hash_pw(pw: str) -> str:
    return hashlib.sha256(pw.encode("utf-8")).hexdigest()

def login(username: str, password: str):
    u = USERS.get(username)
    if not u:
        return False, None
    return (u["pw_hash"] == hash_pw(password)), u["role"]

# ----------------------------
# Constants
# ----------------------------
PACKAGING_WEIGHT = 25.0  # kg per non-empty cell
CELL_CAPACITY = 25       # pieces per cell
RACK_SPACES = {"A": 9, "B": 15, "C": 12, "D": 6, "E": 24, "F": 57}
FIXED_ROWS = 3

# ----------------------------
# Init session state
# ----------------------------
if "logged_in" not in st.session_state:
    st.session_state.logged_in = False
    st.session_state.user = None
    st.session_state.role = None

if "part_master" not in st.session_state:
    st.session_state.part_master = {
        "10283026": {"Weight": 8.05, "Customer": "Mahindra Pune", "Tube Length": 1254},
        "10291078": {"Weight": 7.90, "Customer": "Mahindra Pune", "Tube Length": 1245},
        "10282069": {"Weight": 8.95, "Customer": "Mahindra Pune", "Tube Length": 1262},
    }

if "racks" not in st.session_state:
    racks = {}
    for r, spaces in RACK_SPACES.items():
        cols = math.ceil(spaces / FIXED_ROWS)
        grid = [[{"Part No": None, "Quantity": 0} for _ in range(cols)] for _ in range(FIXED_ROWS)]
        racks[r] = {"rows": FIXED_ROWS, "cols": cols, "array": grid, "spaces": spaces}
    st.session_state.racks = racks

if "history" not in st.session_state:
    st.session_state.history = []

# ----------------------------
# Utilities
# ----------------------------
def ts_now():
    return datetime.now().strftime("%Y-%m-%d %H:%M:%S")

def cell_total_weight(cell):
    pn, qty = cell["Part No"], cell["Quantity"]
    if qty > 0 and pn:
        pm = st.session_state.part_master.get(pn, {})
        return qty * pm.get("Weight", 0.0) + PACKAGING_WEIGHT
    return 0.0

def total_weight_all():
    return sum(
        cell_total_weight(c)
        for rack in st.session_state.racks.values()
        for row in rack["array"]
        for c in row
    )

def add_history(action, rack, cell_no, part_no, qty, user, note=""):
    st.session_state.history.insert(
        0,
        {
            "Timestamp": ts_now(),
            "User": user,
            "Action": action,
            "Rack": rack,
            "Cell": cell_no,
            "Part No": part_no,
            "Quantity": qty,
            "Note": note,
        },
    )

# --- NEW: Helpers for consistent cell mapping ---
def cell_no_to_indices(rack, cell_no):
    """Map 1-based cell number to array indices, bottom-up numbering."""
    cols = rack["cols"]
    rows = rack["rows"]
    row_order = (cell_no - 1) // cols  # bottom-up row index
    row_idx = rows - 1 - row_order     # flip because array[0] is top
    col_idx = (cell_no - 1) % cols
    return row_idx, col_idx

def indices_to_cell_no(rack, row_idx, col_idx):
    """Map array indices back to 1-based cell number (bottom-up)."""
    cols = rack["cols"]
    rows = rack["rows"]
    row_order = rows - 1 - row_idx
    return row_order * cols + col_idx + 1

def prepare_rack_grid_csv():
    rows_out = []
    for rn, rack in st.session_state.racks.items():
        cell_no = 1
        for row_order in range(rack["rows"]):  # bottom row first
            display_row = rack["rows"] - 1 - row_order
            for j in range(rack["cols"]):
                if cell_no > rack["spaces"]:
                    break
                c = rack["array"][display_row][j]
                pm = st.session_state.part_master.get(c["Part No"], {}) if c["Part No"] else {}
                rows_out.append(
                    {
                        "Rack": rn,
                        "Cell": cell_no,
                        "Part No": c["Part No"],
                        "Customer": pm.get("Customer", ""),
                        "Tube Length (mm)": pm.get("Tube Length", ""),
                        "Quantity": c["Quantity"],
                        "Total Weight (kg)": round(cell_total_weight(c), 2),
                    }
                )
                cell_no += 1
    return pd.DataFrame(rows_out)

def prepare_part_master_csv_bytes():
    df = pd.DataFrame.from_dict(st.session_state.part_master, orient="index").reset_index()
    df = df.rename(columns={"index": "Part No"})
    buf = io.StringIO()
    df.to_csv(buf, index=False)
    return buf.getvalue().encode("utf-8")

def prepare_history_csv_bytes():
    if not st.session_state.history:
        return "".encode("utf-8")
    df = pd.DataFrame(st.session_state.history)
    buf = io.StringIO()
    df.to_csv(buf, index=False)
    return buf.getvalue().encode("utf-8")

# ----------------------------
# Sidebar - Authentication + Navigation
# ----------------------------
with st.sidebar:
    st.title("Access")
    if not st.session_state.logged_in:
        with st.form("login_form"):
            username = st.text_input("Username")
            password = st.text_input("Password", type="password")
            if st.form_submit_button("Login"):
                ok, role = login(username.strip(), password)
                if ok:
                    st.session_state.logged_in = True
                    st.session_state.user = username.strip()
                    st.session_state.role = role
                    st.rerun()
                else:
                    st.error("Invalid credentials")
    else:
        st.markdown(f"**User:** {st.session_state.user}")
        st.markdown(f"**Role:** {st.session_state.role}")
        if st.button("Logout"):
            st.session_state.logged_in = False
            st.session_state.user = None
            st.session_state.role = None
            st.rerun()

        st.markdown("---")
        st.subheader("Navigation")
        if st.session_state.role == "master":
            page = st.radio("Select Page", ["Master", "Input", "Output"])
        elif st.session_state.role == "input":
            page = st.radio("Select Page", ["Input", "Output"])
        else:
            page = st.radio("Select Page", ["Output"])

if not st.session_state.logged_in:
    st.title("Multi-Rack FG Stock Board")
    st.info("Welcome to the FG Stock Dashboard")
    st.stop()

# ----------------------------
# Role flags
# ----------------------------
role = st.session_state.role
can_master = role == "master"
can_input = role in ("master", "input")
can_output = role in ("master", "input", "output")

# ----------------------------
# Header
# ----------------------------
col1, col2 = st.columns([3, 1])
with col1:
    st.title("Multi-Rack FG Stock Board")
    st.caption(f"Signed in as {st.session_state.user} ({role})")
with col2:
    total_qty = sum(c["Quantity"] for r in st.session_state.racks.values() for row in r["array"] for c in row)
    st.metric("Total Qty", f"{total_qty}")

# ----------------------------
# MASTER Tab
# ----------------------------
if page == "Master" and can_master:
    st.subheader("Part Master")
    with st.form("part_master_form"):
        pn = st.text_input("Part No").strip()
        wt = st.number_input("Weight (kg)", min_value=0.0, step=0.01, format="%.2f")
        cust = st.text_input("Customer")
        tube = st.number_input("Tube Length (mm)", min_value=0, step=1)
        if st.form_submit_button("Add / Update Part"):
            if pn:
                st.session_state.part_master[pn] = {"Weight": wt, "Customer": cust, "Tube Length": int(tube)}
                add_history("Master Update", "-", "-", pn, 0, st.session_state.user)
                st.success(f"Updated master for {pn}")

    # Bulk upload
    st.markdown("### Bulk Upload Part Master")
    uploaded_file = st.file_uploader("Upload Excel file", type=["xlsx"])
    if uploaded_file:
        try:
            df = pd.read_excel(uploaded_file)
            if {"Part No", "Weight", "Customer", "Tube Length"}.issubset(df.columns):
                for _, row in df.iterrows():
                    pn = str(row["Part No"])
                    st.session_state.part_master[pn] = {
                        "Weight": float(row["Weight"]),
                        "Customer": row["Customer"],
                        "Tube Length": int(row["Tube Length"]),
                    }
                st.success("Part Master updated from Excel file")
            else:
                st.error("Excel must contain columns: Part No, Weight, Customer, Tube Length")
        except Exception as e:
            st.error(f"Error reading file: {e}")

    st.dataframe(pd.DataFrame.from_dict(st.session_state.part_master, orient="index").reset_index().rename(columns={"index":"Part No"}))
    st.download_button("⬇️ Download Part Master CSV", data=prepare_part_master_csv_bytes(), file_name="part_master.csv", mime="text/csv")

# ----------------------------
# INPUT Tab
# ----------------------------
if page == "Input" and can_input:
    st.subheader("Stock Input")
    rack_ui = st.selectbox("Rack", options=list(st.session_state.racks.keys()))
    rack_data = st.session_state.racks[rack_ui]
    SPACES = rack_data["spaces"]

    with st.form("stock_form", clear_on_submit=True):
        cell_no = st.number_input("Cell No", min_value=1, max_value=SPACES, value=1, step=1)
        part_no = st.selectbox("Part No", options=sorted(st.session_state.part_master.keys()))
        qty = st.number_input("Quantity", min_value=1, step=1)
        action = st.radio("Action", ["Add", "Subtract"], horizontal=True)
        if st.form_submit_button("Apply"):
            row_idx, col_idx = cell_no_to_indices(rack_data, cell_no)
            cell = rack_data["array"][row_idx][col_idx]
            if action == "Add":
                if cell["Part No"] in (None, part_no):
                    if cell["Quantity"] + qty <= CELL_CAPACITY:
                        cell["Part No"] = part_no
                        cell["Quantity"] += qty
                        add_history("Add", rack_ui, cell_no, part_no, qty, st.session_state.user)
                        st.success(f"Added {qty} of {part_no} at {rack_ui} Cell {cell_no}")
                    else:
                        st.error("Exceeds cell capacity")
                else:
                    st.error("Cell already has a different part")
            else:  # Subtract
                if cell["Part No"] == part_no and cell["Quantity"] >= qty:
                    cell["Quantity"] -= qty
                    if cell["Quantity"] == 0: cell["Part No"] = None
                    add_history("Subtract", rack_ui, cell_no, part_no, qty, st.session_state.user)
                    st.success(f"Subtracted {qty} from {rack_ui} Cell {cell_no}")
                else:
                    st.error("Mismatch or insufficient stock")

    st.download_button("⬇️ Download Grid CSV", data=prepare_rack_grid_csv().to_csv(index=False).encode("utf-8"), file_name="grid.csv", mime="text/csv")

# ----------------------------
# OUTPUT Tab
# ----------------------------
if page == "Output" and can_output:
    st.subheader("Rack Overview")
    out_rack = st.selectbox("Select Rack to View", options=list(st.session_state.racks.keys()))
    rack = st.session_state.racks[out_rack]

    # --- Rack layout ---
    st.markdown("### Rack Layout")
    ROWS = rack["rows"]
    COLS = rack["cols"]
    SPACES = rack["spaces"]

    html = """
    <style>
      .rack-wrap { overflow-x: auto; margin-bottom: 12px; }
      .rack-table { border-collapse: collapse; width: 100%; font-family: Arial, sans-serif; }
      .rack-table th, .rack-table td { border: 1px solid #e6e6e6; padding: 10px; text-align: center; vertical-align: middle; min-width:140px; }
      .rack-table th { background:#fafafa; font-weight:700; }
      .row-label { background:#f5f7fa; font-weight:700; width:90px; }
      .cell-empty { background:#f2f3f4; color:#6c757d; min-height:70px; }
      .cell-filled { background:#e6f7ea; min-height:85px; }
      .cell-content { font-size:14px; line-height:1.25; }
    </style>
    <div class="rack-wrap">
    <table class="rack-table">
      <thead>
        <tr><th class="row-label">Row</th>
    """

    for col_h in range(1, COLS + 1):
        html += f"<th>Col {col_h}</th>"
    html += "</tr></thead><tbody>"

    cell_counter = 1
    for row_order in range(ROWS):  # bottom row first
        display_r = ROWS - 1 - row_order
        html += "<tr>"
        html += f"<td class='row-label'>Row {row_order + 1}</td>"
        for c in range(COLS):
            if cell_counter <= SPACES:
                cell_obj = rack["array"][display_r][c]
                if cell_obj.get("Part No"):
                    wt = round(cell_total_weight(cell_obj), 2)
                    content = (
                        f"<div class='cell-content'>"
                        f"<div style='font-weight:700'>Cell {cell_counter}</div>"
                        f"<div style='margin-top:6px'>{cell_obj['Part No']}</div>"
                        f"<div>Qty: {cell_obj['Quantity']}</div>"
                        f"<div style='font-size:12px;margin-top:4px;color:#333'>Wt: {wt} kg</div>"
                        f"</div>"
                    )
                    css = "cell-filled"
                else:
                    content = (
                        f"<div class='cell-content'>"
                        f"<div style='font-weight:700'>Cell {cell_counter}</div>"
                        f"<div style='color:#6c757d;margin-top:6px'>Empty</div>"
                        f"</div>"
                    )
                    css = "cell-empty"
            else:
                content = ""
                css = "cell-empty"
            html += f"<td class='{css}'>{content}</td>"
            cell_counter += 1
        html += "</tr>"

    html += "</tbody></table></div>"
    st.markdown(html, unsafe_allow_html=True)

    # --- FIFO Finder ---
    st.subheader("FIFO Part Finder")
    search_part = st.text_input("Part No")
    if st.button("Find FIFO Cell"):
        fifo = None
        for ev in reversed(st.session_state.history):
            if ev["Action"] == "Add" and ev["Part No"] == search_part:
                rk, cell_no = ev["Rack"], ev["Cell"]
                rack_check = st.session_state.racks[rk]
                row_idx, col_idx = cell_no_to_indices(rack_check, cell_no)
                cell = rack_check["array"][row_idx][col_idx]
                if cell["Part No"] == search_part and cell["Quantity"] > 0:
                    fifo = ev
                    break
        if fifo:
            st.success(f"FIFO pick: Rack {fifo['Rack']} Cell {fifo['Cell']} (Qty: {cell['Quantity']})")
        else:
            st.warning("No FIFO candidate found")

    # --- History Log ---
    st.subheader("History Log")
    if st.session_state.history:
        df_hist = pd.DataFrame(st.session_state.history)[["Timestamp","User","Action","Rack","Cell","Part No","Quantity"]]
        st.dataframe(df_hist)
        st.download_button("⬇️ Download History CSV", data=prepare_history_csv_bytes(), file_name="history.csv", mime="text/csv")
    else:
        st.info("No history yet")
