import streamlit as st
import gspread
import os

@st.cache_resource(ttl=600)
def get_spreadsheet():
    credentials_dict = dict(st.secrets["gcp_service_account"])
    gc = gspread.service_account_from_dict(credentials_dict)
    url = st.secrets["gsheets"]["spreadsheet_url"]
    return gc.open_by_url(url)

@st.cache_resource(ttl=600)
def get_worksheet_resource(name, headers_if_not_found=None):
    sh = get_spreadsheet()
    import time
    for i in range(3):
        try:
            return sh.worksheet(name)
        except gspread.exceptions.WorksheetNotFound:
            if headers_if_not_found:
                ws = sh.add_worksheet(title=name, rows="1000", cols="20")
                ws.append_row(headers_if_not_found)
                return ws
            raise
        except gspread.exceptions.APIError as e:
            if i == 2:
                raise Exception(f"Google Sheets API Error (Worksheet '{name}'): Code {getattr(e.response, 'status_code', 'Unknown')}, Message: {getattr(e.response, 'text', str(e))}")
            time.sleep(2)

@st.cache_data(ttl=15)
def get_cached_records(sheet_name):
    ws = get_worksheet_resource(sheet_name)
    import time
    for i in range(3):
        try:
            return ws.get_all_records()
        except gspread.exceptions.APIError as e:
            if i == 2:
                raise Exception(f"Google Sheets API Fetch Error (Records '{sheet_name}'): Code {getattr(e.response, 'status_code', 'Unknown')}, Message: {getattr(e.response, 'text', str(e))}")
            time.sleep(2)

def clear_db_cache():
    get_cached_records.clear()

def init_db():
    get_worksheet_resource("users", ["email", "name", "game_name"])
    get_worksheet_resource("predictions", ["id", "email", "match_id", "winner", "orange_cap", "purple_cap", "multiplier_used", "group_id"])
    get_worksheet_resource("match_results", ["match_id", "winner", "orange_cap", "orange_cap_rest", "orange_cap_2nd", "purple_cap", "purple_cap_rest", "oc_freehit_player", "pc_freehit_player", "group_id"])

def create_or_get_user(email, name):
    ws = get_worksheet_resource("users")
    records = get_cached_records("users")
    for row in records:
        if str(row.get("email")) == str(email):
            return  # User already exists
    ws.append_row([email, name, ""])
    clear_db_cache()

def save_prediction(email, match_id, winner, orange_cap, purple_cap, multiplier_used, group_id):
    ws = get_worksheet_resource("predictions")
    mult_val = 1 if multiplier_used else 0
    records = get_cached_records("predictions")
    
    found_row_idx = None
    max_id = 0
    for i, row in enumerate(records):
        if str(row.get("email")) == str(email) and str(row.get("match_id")) == str(match_id):
            found_row_idx = i + 2
        try:
            cur_id = int(row.get("id", 0))
            if cur_id > max_id:
                max_id = cur_id
        except:
            pass
            
    if found_row_idx:
        cell_range = f'C{found_row_idx}:H{found_row_idx}'
        ws.update(values=[[match_id, winner, orange_cap, purple_cap, mult_val, group_id]], range_name=cell_range)
    else:
        new_id = max_id + 1
        ws.append_row([new_id, email, match_id, winner, orange_cap, purple_cap, mult_val, group_id])
    clear_db_cache()

def get_user_predictions(email):
    records = get_cached_records("predictions")
    results = []
    for row in records:
        if str(row.get("email")) == str(email):
            row["match_id"] = int(row.get("match_id", 0))
            row["group_id"] = int(row.get("group_id", 0))
            row["multiplier_used"] = int(row.get("multiplier_used", 0))
            results.append(row)
    return results

def has_used_multiplier_in_group(email, group_id):
    preds = get_user_predictions(email)
    for p in preds:
        if str(p.get("group_id")) == str(group_id) and int(p.get("multiplier_used", 0)) == 1:
            return True
    return False

def get_user(email):
    records = get_cached_records("users")
    for row in records:
        if str(row.get("email")) == str(email):
            return row
    return None

def update_game_name(email, game_name):
    ws = get_worksheet_resource("users")
    records = get_cached_records("users")
    for i, row in enumerate(records):
        if str(row.get("email")) == str(email):
            ws.update_cell(i + 2, 3, game_name)
            break
    clear_db_cache()

def get_all_users():
    records = get_cached_records("users")
    return [row for row in records if str(row.get("game_name")).strip() != ""]

def get_match_predictions(match_id):
    preds = get_cached_records("predictions")
    users = get_cached_records("users")
    
    valid_users = {str(u["email"]): u["game_name"] for u in users if str(u.get("game_name")).strip() != ""}
    
    results = []
    for p in preds:
        email = str(p.get("email"))
        if str(p.get("match_id")) == str(match_id) and email in valid_users:
            results.append({
                "game_name": valid_users[email],
                "winner": p.get("winner"),
                "orange_cap": p.get("orange_cap"),
                "purple_cap": p.get("purple_cap"),
                "multiplier_used": int(p.get("multiplier_used", 0))
            })
    return results

def save_match_result(match_id, winner, orange_cap, orange_cap_rest, orange_cap_2nd, purple_cap, purple_cap_rest, oc_freehit_player, pc_freehit_player, group_id):
    ws = get_worksheet_resource("match_results")
    records = get_cached_records("match_results")
    
    found_row_idx = None
    for i, row in enumerate(records):
        if str(row.get("match_id")) == str(match_id):
            found_row_idx = i + 2
            break
            
    val_list = [match_id, winner, orange_cap, orange_cap_rest, orange_cap_2nd, purple_cap, purple_cap_rest, oc_freehit_player, pc_freehit_player, group_id]
    
    if found_row_idx:
        ws.update(values=[val_list], range_name=f'A{found_row_idx}:J{found_row_idx}')
    else:
        ws.append_row(val_list)
    clear_db_cache()

def get_all_match_results():
    records = get_cached_records("match_results")
    
    results = {}
    for row in records:
        m_id = int(row.get("match_id", 0))
        row["match_id"] = m_id
        results[m_id] = row
    return results

def get_all_predictions():
    # Defensive deep copy logic to avoid mutability issues with Streamlit cache
    import copy
    records = copy.deepcopy(get_cached_records("predictions"))
    
    for row in records:
        row["match_id"] = int(row.get("match_id", 0))
        row["group_id"] = int(row.get("group_id", 0))
        row["multiplier_used"] = int(row.get("multiplier_used", 0))
    return records
