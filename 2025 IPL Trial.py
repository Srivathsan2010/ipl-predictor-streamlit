import streamlit as st
import json
import datetime
import os
import pandas as pd
from streamlit_google_signin import st_google_signin
import database
import fetch_results
import scoring

# --- 1. SETUP & CONFIGURATION ---
st.set_page_config(page_title="IPL Predictor 2025", layout="centered", page_icon="🏏")

# Initialize SQLite database
database.init_db()

# FILE CONFIGURATION
JSON_FILE_PATH = "ipl-2025-squad-final_new.json"

# --- GOOGLE AUTHENTICATION ---
CLIENT_ID = None

# Attempt to get CLIENT_ID from Streamlit Secrets
if "google_auth" in st.secrets:
    CLIENT_ID = st.secrets["google_auth"].get("client_id")

# Fallback: Attempt to get CLIENT_ID from local JSON file
if not CLIENT_ID and os.path.exists("google_credentials.json"):
    try:
        with open("google_credentials.json", "r") as f:
            creds = json.load(f)
            CLIENT_ID = creds.get("web", {}).get("client_id")
    except Exception:
        pass

if not CLIENT_ID:
    st.error("🚨 **CRITICAL SETUP ERROR** 🚨\n\nGoogle Auth Client ID is missing! Please configure `[google_auth]` in Streamlit Secrets or provide `google_credentials.json` locally.")
    st.stop()

# --- 2. DATA LOADING FUNCTION ---
@st.cache_data
def load_and_process_data():
    if not os.path.exists(JSON_FILE_PATH):
        st.error(f"❌ Error: The file '{JSON_FILE_PATH}' was not found.")
        st.info("Missing data JSON.")
        st.stop()
        
    with open(JSON_FILE_PATH, 'r') as f:
        raw_data = json.load(f)
        
    team_map = {} 
    squad_map = {} 
    for team in raw_data.get('squads', []):
        team_map[team['team_name']] = team['team_abbr']
        squad_map[team['team_abbr']] = sorted(team['players'])
        
    processed_matches = []
    matches_per_group = 14
    
    for index, match in enumerate(raw_data.get('schedule', [])):
        date_obj = None
        try:
            date_obj = datetime.datetime.strptime(match['date_time(est)'], "%Y-%m-%d %H:%M")
            date_str = date_obj.strftime("%b %d, %I:%M %p") 
        except:
            date_str = match.get('date_time(est)', 'Unknown Date')
        
        t1_name = match['team1']
        t2_name = match['team2']
        t1_abbr = team_map.get(t1_name, t1_name[:3].upper())
        t2_abbr = team_map.get(t2_name, t2_name[:3].upper())
        
        group_id = (index // matches_per_group) + 1
        
        processed_matches.append({
            "id": match['matchId'],
            "display_id": index + 1,
            "date": date_str,
            "date_obj": date_obj,
            "team_a": t1_abbr,
            "team_b": t2_abbr,
            "venue": match['venue'],
            "group": group_id
        })
        
    return processed_matches, squad_map

MATCHES, SQUADS = load_and_process_data()

# --- SESSION STATE INITIALIZATION ---
if 'selected_match' not in st.session_state:
    st.session_state.selected_match = None
if 'selected_view_match' not in st.session_state:
    st.session_state.selected_view_match = None
if 'nav_selection' not in st.session_state:
    st.session_state.nav_selection = "📅 Fixtures"

# --- 3. PAGE 1: FIXTURE LIST ---
def show_fixture_list(user_email):
    # Fetch previously predicted matches from DB
    user_preds = database.get_user_predictions(user_email)
    predicted_match_ids = {p['match_id']: p for p in user_preds}

    st.title("📅 IPL 2025 Fixtures")
    st.write("Select a match to predict.")
    
    if MATCHES:
        unique_groups = sorted(list(set(m['group'] for m in MATCHES)))
        selected_group = st.selectbox("Filter by Group", unique_groups, format_func=lambda x: "Playoffs" if x == 6 else f"Group {x}")
        visible_matches = [m for m in MATCHES if m['group'] == selected_group]
    else:
        visible_matches = []

    for match in visible_matches:
        with st.container():
            col1, col2, col3 = st.columns([1, 4, 2])
            with col1:
                st.write(f"**#{match['display_id']}**")
            with col2:
                st.write(f"**{match['team_a']} vs {match['team_b']}**")
                st.caption(f"{match['date']} • {match['venue']}")
                if match['id'] in predicted_match_ids:
                    st.success("✅ Predicted", icon="✅")
            with col3:
                if st.button("Predict ➜", key=f"btn_{match['id']}"):
                    st.session_state.selected_match = match
                    st.rerun()
            st.divider()

# --- 4. PAGE 2: PREDICTION FORM ---
def show_prediction_form(user_email):
    match = st.session_state.selected_match
    group_id = match['group']
    team_a_players = SQUADS.get(match['team_a'], [])
    team_b_players = SQUADS.get(match['team_b'], [])
    all_match_players = ["-- Select Player --"] + sorted(team_a_players + team_b_players)
    
    is_2x_locked = database.has_used_multiplier_in_group(user_email, group_id)
    
    # Check if a prediction already exists to pre-fill the form
    existing_preds = database.get_user_predictions(user_email)
    existing_pred = next((p for p in existing_preds if p['match_id'] == match['id']), None)
    
    default_winner_idx = 0
    default_oc_idx = 0
    default_pc_idx = 0
    default_2x = False
    
    if existing_pred:
        try:
            default_winner_idx = [match['team_a'], match['team_b']].index(existing_pred['winner'])
        except ValueError:
            pass
        if existing_pred['orange_cap'] in all_match_players:
            default_oc_idx = all_match_players.index(existing_pred['orange_cap'])
        if existing_pred['purple_cap'] in all_match_players:
            default_pc_idx = all_match_players.index(existing_pred['purple_cap'])
        default_2x = bool(existing_pred['multiplier_used'])

    if st.button("⬅ Back to Fixtures"):
        st.session_state.selected_match = None
        st.rerun()

    st.title(f"{match['team_a']} vs {match['team_b']}")
    st.caption(f"Match #{match['display_id']} • {match['venue']} • {'Playoffs' if group_id == 6 else f'Group {group_id}'}")
    
    with st.form(key="prediction_form"):
        st.write("### 1. Match Winner")
        winner = st.radio("Who will win?", [match['team_a'], match['team_b']], index=default_winner_idx, horizontal=True)
        
        col1, col2 = st.columns(2)
        with col1:
            st.write("### 2. Orange Cap")
            oc_pick = st.selectbox("Select Batsman", all_match_players, index=default_oc_idx, key="oc")
            
        with col2:
            st.write("### 3. Purple Cap")
            pc_pick = st.selectbox("Select Bowler", all_match_players, index=default_pc_idx, key="pc")
            
        st.write("### 4. Booster")
        use_2x = st.checkbox(
            "🔥 Apply 2X Multiplier?", 
            value=default_2x,
            disabled=(is_2x_locked and not default_2x),
            help=f"You can only use this once for {'Playoffs' if group_id == 6 else f'Group {group_id}'}."
        )
        if is_2x_locked and not default_2x:
            st.warning(f"🔒 You already used your 2X Booster for {'Playoffs' if group_id == 6 else f'Group {group_id}'}")
            
        st.write("---")
        
        if st.form_submit_button("Submit Prediction", type="primary"):
            if oc_pick == "-- Select Player --" or pc_pick == "-- Select Player --":
                st.error("⚠️ Please select players for both Orange and Purple caps.")
            else:
                database.save_prediction(
                    email=user_email,
                    match_id=match['id'],
                    winner=winner,
                    orange_cap=oc_pick,
                    purple_cap=pc_pick,
                    multiplier_used=use_2x,
                    group_id=group_id
                )
                st.success("✅ Saved! Click 'Back' to return.")

# --- 5. PAGE 3: PROFILE VIEW ---
def show_profile(user_email, user_name, game_name):
    st.title("👤 My Profile")
    st.write(f"**Game Name:** {game_name}")
    st.write(f"**Real Name:** {user_name}")
    st.write(f"**Email:** {user_email}")
    st.divider()
    
    st.subheader("📊 My Recent Predictions")
    preds = database.get_user_predictions(user_email)
    
    if not preds:
        st.info("You haven't made any predictions yet. Head to the Fixtures tab to get started!")
        return
        
    for p in preds:
        match_info = next((m for m in MATCHES if m['id'] == p['match_id']), None)
        if match_info:
            group_display = "Playoffs" if p['group_id'] == 6 else f"Group {p['group_id']}"
            with st.expander(f"{group_display}: {match_info['team_a']} vs {match_info['team_b']} (Match #{match_info['display_id']})"):
                st.write(f"🏅 **Predicted Winner:** {p['winner']}")
                st.write(f"🏏 **Orange Cap Pick:** {p['orange_cap']}")
                st.write(f"⚾ **Purple Cap Pick:** {p['purple_cap']}")
                if p['multiplier_used']:
                    st.write("🔥 **2X Multiplier Applied**")

# --- 6. PAGE 4: PLAYERS VIEW ---
def show_players():
    st.title("🏏 Registered Players")
    st.write("Here are all the users participating in the predictor so far:")
    st.divider()
    
    all_users = database.get_all_users()
    if not all_users:
        st.info("No players have set up their Game Names yet!")
        return

    # Create a nice layout for displaying the users
    for user in all_users:
        st.markdown(f"**{user['game_name']}**")
        st.divider()

# --- 7. PAGE 5: PREDICTIONS LIST ---
def show_predictions_list():
    import zoneinfo
    st.title("🔮 Match Predictions")
    st.write("Select a match to see everyone's predictions.")
    
    if MATCHES:
        unique_groups = sorted(list(set(m['group'] for m in MATCHES)))
        selected_group = st.selectbox("Filter by Group", unique_groups, format_func=lambda x: "Playoffs" if x == 6 else f"Group {x}", key="pred_group_filter")
        visible_matches = [m for m in MATCHES if m['group'] == selected_group]
    else:
        visible_matches = []

    ny_tz = zoneinfo.ZoneInfo("America/New_York")
    current_time_ny = datetime.datetime.now(ny_tz).replace(tzinfo=None)

    for match in visible_matches:
        with st.container():
            col1, col2, col3 = st.columns([1, 4, 4]) # adjusted col width
            with col1:
                st.write(f"**#{match['display_id']}**")
            with col2:
                st.write(f"**{match['team_a']} vs {match['team_b']}**")
                st.caption(f"{match['date']} • {match['venue']}")
            with col3:
                # Prediction unlock logic: unlocks 25 mins prior to EST match time
                is_unlocked = True
                unlock_delta = ""
                
                if match.get("date_obj"):
                    unlock_time = match["date_obj"] - datetime.timedelta(minutes=25)
                    if current_time_ny < unlock_time:
                        is_unlocked = False
                        
                        diff = unlock_time - current_time_ny
                        total_minutes = int(diff.total_seconds() // 60)
                        if total_minutes > 1440:
                            unlock_delta = f"{total_minutes // 1440} days"
                        elif total_minutes > 60:
                            unlock_delta = f"{total_minutes // 60} hours"
                        else:
                            unlock_delta = f"{total_minutes} mins"
                            
                if is_unlocked:
                    if st.button("View Predictions ➜", key=f"view_btn_{match['id']}"):
                        st.session_state.selected_view_match = match
                        st.rerun()
                else:
                    st.button(f"🔒 Unlocks in {unlock_delta}", key=f"view_btn_locked_{match['id']}", disabled=True, help="Predictions are revealed 25 mins prior to match start.")
            st.divider()

# --- 8. PAGE 6: MATCH PREDICTIONS VIEW ---
def show_match_predictions():
    match = st.session_state.selected_view_match
    
    if st.button("⬅ Back to Matches", key="back_to_pred_list"):
        st.session_state.selected_view_match = None
        st.rerun()

    st.title(f"{match['team_a']} vs {match['team_b']}")
    st.caption(f"Match #{match['display_id']} • {match['venue']} • {'Playoffs' if match['group'] == 6 else f'Group {match['group']}'}")
    st.divider()
    
    predictions = database.get_match_predictions(match['id'])
    if not predictions:
        st.info("No predictions have been submitted for this match yet.")
        return
        
    st.write(f"### 📊 Predictions ({len(predictions)})")
    
    table_data = []
    for p in predictions:
        table_data.append({
            "User": p['game_name'],
            "Winner": p['winner'],
            "Orange Cap": p['orange_cap'],
            "Purple Cap": p['purple_cap'],
            "Multiplier": "🔥" if p['multiplier_used'] else ""
        })
        
    st.dataframe(table_data, use_container_width=True, hide_index=True)

# --- 8.5 PAGE 7: LEADERBOARD ---
def show_leaderboard():
    st.title("🏆 Leaderboard")
    
    col1, col2 = st.columns([3, 1])
    with col1:
        st.write("Rankings based on predictions.")
    with col2:
        if st.button("🔄 Fetch Latest Results"):
            with st.spinner("Fetching matches from Cricbuzz..."):
                fetch_results.fetch_all()
            st.success("Results updated!")
            st.rerun()

    scores, match_scores = scoring.calculate_scores()
    
    if not scores:
        st.info("No scores available yet.")
        return
        
    all_users = {u['email']: u for u in database.get_all_users()}
    
    leaderboard_data = []
    for email, score in scores.items():
        user = all_users.get(email)
        if user:
            leaderboard_data.append({
                "User": user['game_name'],
                "Points": score
            })
            
    leaderboard_data.sort(key=lambda x: x['Points'], reverse=True)
    
    for idx, row in enumerate(leaderboard_data):
        row["Rank"] = idx + 1
        
    st.dataframe(
        leaderboard_data,
        column_order=("Rank", "User", "Points"),
        hide_index=True,
        use_container_width=True
    )

# --- 8.5 PAGE 8: ADMIN DASHBOARD ---
def show_admin_dashboard():
    st.title("👑 Admin Dashboard")
    st.write("Master Sheet: Match Results & User Scores")
    
    # Needs to fetch all matches
    from scoring import calculate_scores
    scores, match_scores = calculate_scores()
    
    # get match results and users
    match_results = database.get_all_match_results() # {match_id: dict()}
    all_users = {u['email']: u['game_name'] for u in database.get_all_users()}
    
    # Organise user predictions for W, OC, PC for each match
    all_preds_raw = database.get_all_predictions()
    preds_by_match = {}
    for p in all_preds_raw:
        m_id = p['match_id']
        email = p['email']
        if m_id not in preds_by_match:
            preds_by_match[m_id] = {}
        preds_by_match[m_id][email] = p
        
    scores_by_match = {}
    for entry in match_scores:
        m_id = entry['match_id']
        email = entry['email']
        if m_id not in scores_by_match:
            scores_by_match[m_id] = {}
        scores_by_match[m_id][email] = entry['points_earned']
        
    table_data = []
    
    for match in MATCHES:
        m_id = match['id']
        row = {
            "Match #": match['display_id'],
            "Match": f"{match['team_a']} vs {match['team_b']}",
        }
        
        if m_id in match_results:
            res = match_results[m_id]
            row["Actual Winner"] = res.get("winner", "")
            row["Actual OC"] = res.get("orange_cap", "")
            row["Actual PC"] = res.get("purple_cap", "")
        else:
            row["Actual Winner"] = ""
            row["Actual OC"] = ""
            row["Actual PC"] = ""
            
        # For each user, add their W, OC, PC and Pts
        for email, game_name in all_users.items():
            user_pred = preds_by_match.get(m_id, {}).get(email, {})
            row[f"{game_name} Win"] = user_pred.get('winner', "")
            row[f"{game_name} OC"] = user_pred.get('orange_cap', "")
            row[f"{game_name} PC"] = user_pred.get('purple_cap', "")
            row[f"{game_name} Pts"] = scores_by_match.get(m_id, {}).get(email, 0)
            
        table_data.append(row)
        
    if table_data:
        df = pd.DataFrame(table_data)
        st.dataframe(df, use_container_width=True, hide_index=True)
    else:
        st.info("No match data available yet.")

# --- 9. MAIN CONTROLLER ---
def main():
    # Session Persistence Tab Sync Strategy: 
    # Use st.query_params to carry session to new tabs and survive component cookie delays

    if "user_email" in st.query_params and not st.session_state.get('connected'):
        st.session_state["connected"] = True
        st.session_state["user_info"] = {
            "email": st.query_params.get("user_email"),
            "name": st.query_params.get("user_name", "Unknown User")
        }
    
    if not st.session_state.get('connected', False):
        st.title("Welcome to IPL Predictor 2025 🏏")
        st.write("Please sign in with your Google account to track your predictions!")
        
        # Render the custom Streamlit Google Sign-In Component
        token_payload = st_google_signin(client_id=CLIENT_ID)
        
        if token_payload:
            st.session_state["connected"] = True
            st.session_state["user_info"] = {
                "email": token_payload.get('email', 'unknown@example.com'),
                "name": token_payload.get('name', 'Unknown User')
            }
            # Sync to query params so new tabs can share session
            st.query_params["user_email"] = token_payload.get('email', 'unknown@example.com')
            st.query_params["user_name"] = token_payload.get('name', 'Unknown User')
            st.rerun()
            
        return
        
    # Ensure user info is processed
    user_info = st.session_state.get('user_info', {})
    user_email = user_info.get('email', 'unknown@example.com')
    user_name = user_info.get('name', 'Unknown User')
    
    # Sync to query params so new tabs / page reloads keep the session without waiting for cookies
    if st.query_params.get("user_email") != user_email:
        st.query_params["user_email"] = user_email
        st.query_params["user_name"] = user_name
    
    # Preload user into DB
    database.create_or_get_user(user_email, user_name)
    user_data = database.get_user(user_email)

    # User registration: force users to enter a Game Name
    if not user_data or not user_data.get('game_name'):
        st.title("Welcome to IPL Predictor 2025 🏏")
        st.write("Please choose a Game Name to complete your registration!")
        with st.form("game_name_form"):
            new_game_name = st.text_input("Enter Game Name")
            if st.form_submit_button("Save Game Name", type="primary"):
                if new_game_name.strip():
                    database.update_game_name(user_email, new_game_name.strip())
                    st.success("Game Name saved! Loading app...")
                    st.rerun()
                else:
                    st.error("Game Name cannot be empty.")
        return

    game_name = user_data.get('game_name')

    # Sidebar Navigation System
    with st.sidebar:
        st.write(f"Welcome back,")
        st.write(f"**{game_name}**")
        if st.button("Log Out"):
            st.session_state.clear()
            st.query_params.clear()
            st.rerun()
        st.divider()
        
        st.write("### ⚙️ Main Navigation")
        if st.button("👤 My Profile", use_container_width=True, type="primary" if st.session_state.nav_selection == "👤 My Profile" else "secondary"):
            st.session_state.nav_selection = "👤 My Profile"
            st.rerun()
            
        if st.button("🏏 Players", use_container_width=True, type="primary" if st.session_state.nav_selection == "🏏 Players" else "secondary"):
            st.session_state.nav_selection = "🏏 Players"
            st.rerun()
            
        st.divider()
        st.write("### 🏏 IPL 2025")
        
        if st.button("📅 Fixtures", use_container_width=True, type="primary" if st.session_state.nav_selection == "📅 Fixtures" else "secondary"):
            st.session_state.nav_selection = "📅 Fixtures"
            st.session_state.selected_match = None
            st.rerun()
            
        if st.button("🔮 Predictions", use_container_width=True, type="primary" if st.session_state.nav_selection == "🔮 Predictions" else "secondary"):
            st.session_state.nav_selection = "🔮 Predictions"
            st.session_state.selected_view_match = None
            st.rerun()
            
        if st.button("🏆 Leaderboard", use_container_width=True, type="primary" if st.session_state.nav_selection == "🏆 Leaderboard" else "secondary"):
            st.session_state.nav_selection = "🏆 Leaderboard"
            st.rerun()

        if user_email == "msrivats2010@gmail.com":
            st.divider()
            st.write("### 🛡️ Admin")
            if st.button("👑 Admin Dashboard", use_container_width=True, type="primary" if st.session_state.nav_selection == "👑 Admin Dashboard" else "secondary"):
                st.session_state.nav_selection = "👑 Admin Dashboard"
                st.rerun()

    # Route request
    if st.session_state.nav_selection == "📅 Fixtures":
        if st.session_state.selected_match is None:
            show_fixture_list(user_email)
        else:
            show_prediction_form(user_email)
    elif st.session_state.nav_selection == "👤 My Profile":
        show_profile(user_email, user_name, game_name)
    elif st.session_state.nav_selection == "🏏 Players":
        show_players()
    elif st.session_state.nav_selection == "🔮 Predictions":
        if st.session_state.selected_view_match is None:
            show_predictions_list()
        else:
            show_match_predictions()
    elif st.session_state.nav_selection == "🏆 Leaderboard":
        show_leaderboard()
    elif st.session_state.nav_selection == "👑 Admin Dashboard":
        show_admin_dashboard()

if __name__ == "__main__":
    main()