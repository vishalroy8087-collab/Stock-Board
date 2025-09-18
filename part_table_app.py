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

# ---- Helper functions to ensure consistent mapping ----
def cell_no_to_indices(rack, cell_no):
    """
    Convert 1-based cell_no (bottom-left = 1, left->right, bottom->top)
    to internal array indices (row_idx, col_idx) where array[0] is top row.
    """
    cols = rack["cols"]
    rows = rack["rows"]
    if cell_no < 1 or cell_no > rack["spaces"]:
        raise ValueError("cell_no out of range")
    row_order_from_bottom = (cell_no - 1) // cols  # 0-based bottom row = 0
    row_idx = rows - 1 - row_order_from_bottom    # flip because array[0] is top
    col_idx = (cell_no - 1) % cols
    return row_idx, col_idx

def indices_to_cell_no(rack, row_idx, col_idx):
    """
    Convert internal array indices back to 1-based cell_no (bottom-left = 1).
    """
    cols = rack["cols"]
    rows = rack["rows"]
    if row_idx < 0 or row_idx >= rows or col_idx < 0 or col_idx >= cols:
        raise ValueError("indices out of range")
    row_order_from_bottom = rows - 1 - row_idx
    return row_order_from_bottom * cols + col_idx + 1

def prepare_rack_grid_csv():
    """
    Prepare CSV rows in the same bottom-up cell order displayed to users.
    """
    rows_out = []
    for rn, rack in st.session_state.racks.items():
        cell_no = 1
        # iterate bottom row first to match displayed numbering
        for row_order in range(rack["rows"]):
            display_row = rack["rows"] - 1 - row_order
            for col in range(rack["cols"]):
                if cell_no > rack["spaces"]:
                    break
                c = rack["array"][display_row][col]
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
            try:
                row_idx, col_idx = cell_no_to_indices(rack_data, cell_no)
            except ValueError:
                st.error("Invalid cell number")
            else:
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
                        if cell["Quantity"] == 0:
                            cell["Part No"] = None
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

    # --- Color Legend ---
    st.markdown("""
    <div style="margin-bottom:10px;">
      <span style="background:#d9fdd3; padding:4px 8px; border:1px solid #ccc; margin-right:8px;">🟩 Empty</span>
      <span style="background:#fff9c4; padding:4px 8px; border:1px solid #ccc; margin-right:8px;">🟨 &lt;50%</span>
      <span style="background:#ffe0b2; padding:4px 8px; border:1px solid #ccc; margin-right:8px;">🟧 ≥50%</span>
      <span style="background:#ffcdd2; padding:4px 8px; border:1px solid #ccc;">🟥 Full</span>
    </div>
    """, unsafe_allow_html=True)

    # --- Rack Layout (no headers) ---
    st.markdown("### Rack Layout")
    ROWS = rack["rows"]
    COLS = rack["cols"]
    SPACES = rack["spaces"]

    html = """
    <style>
      .rack-wrap { overflow-x: auto; margin-bottom: 12px; }
      .rack-table { border-collapse: collapse; font-family: Arial, sans-serif; margin:auto; }
      .rack-table td { border: 1px solid #e6e6e6; padding: 10px; text-align: center; vertical-align: middle; min-width:140px; }
      .cell-empty { background:#d9fdd3; color:#2e7d32; }
      .cell-partial { background:#fff9c4; color:#9e7700; }
      .cell-mid { background:#ffe0b2; color:#e65100; }
      .cell-full { background:#ffcdd2; color:#b71c1c; }
      .cell-content { font-size:14px; line-height:1.25; }
    </style>
    <div class="rack-wrap">
    <table class="rack-table"><tbody>
    """

    cell_counter = 1
    for row_order in range(ROWS):  # bottom row first (row_order 0 => bottom)
        display_r = ROWS - 1 - row_order
        html += "<tr>"
        for c in range(COLS):
            if cell_counter <= SPACES:
                cell_obj = rack["array"][display_r][c]
                qty = cell_obj["Quantity"]
                part_no = cell_obj.get("Part No")

                if not part_no or qty == 0:
                    css = "cell-empty"
                    content = (
                        f"<div class='cell-content'>"
                        f"<div style='font-weight:700'>Cell {cell_counter}</div>"
                        f"<div style='margin-top:6px'>Empty</div>"
                        f"</div>"
                    )
                else:
                    fill_ratio = qty / CELL_CAPACITY
                    if fill_ratio >= 1.0:
                        css = "cell-full"
                    elif fill_ratio >= 0.5:
                        css = "cell-mid"
                    else:
                        css = "cell-partial"
                    wt = round(cell_total_weight(cell_obj), 2)
                    content = (
                        f"<div class='cell-content'>"
                        f"<div style='font-weight:700'>Cell {cell_counter}</div>"
                        f"<div style='margin-top:6px'>{part_no}</div>"
                        f"<div>Qty: {qty}</div>"
                        f"<div style='font-size:12px;color:#333'>Wt: {wt} kg</div>"
                        f"</div>"
                    )
            else:
                css = "cell-empty"
                content = ""
            html += f"<td class='{css}'>{content}</td>"
            cell_counter += 1
        html += "</tr>"

    html += "</tbody></table></div>"
    st.markdown(html, unsafe_allow_html=True)

    # --- FIFO Finder (oldest Add event that still has stock) ---
    st.subheader("FIFO Part Finder")
    search_part = st.text_input("Part No")
    if st.button("Find FIFO Cell"):
        fifo = None
        # history[0] is most recent, so reversed() gives oldest->newest
        for ev in reversed(st.session_state.history):
            if ev["Action"] == "Add" and ev["Part No"] == search_part:
                rk, cell_no = ev["Rack"], ev["Cell"]
                rack_check = st.session_state.racks.get(rk)
                if not rack_check:
                    continue
                try:
                    row_idx, col_idx = cell_no_to_indices(rack_check, cell_no)
                except ValueError:
                    continue
                cell = rack_check["array"][row_idx][col_idx]
                if cell["Part No"] == search_part and cell["Quantity"] > 0:
                    fifo = {"Rack": rk, "Cell": cell_no, "Qty": cell["Quantity"]}
                    break
        if fifo:
            st.success(f"FIFO pick: Rack {fifo['Rack']} Cell {fifo['Cell']} (Qty: {fifo['Qty']})")
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
