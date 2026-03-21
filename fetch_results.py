import requests
import json
from datetime import datetime
import json
import database

import streamlit as st

HEADERS = {
    "X-RapidAPI-Host": "cricbuzz-cricket.p.rapidapi.com"
}
try:
    HEADERS["X-RapidAPI-Key"] = st.secrets["rapidapi"]["key"]
except (FileNotFoundError, KeyError, Exception):
    HEADERS["X-RapidAPI-Key"] = "df8b086635msh92585d5dcb5bc07p14a97ejsn4d3ca5d7d26c" # Fallback

SCHEDULE_FILE = r"ipl-2025-squad-final_new.json"

def get_matches_for_group(group_id):
    with open(SCHEDULE_FILE, 'r') as f:
        data = json.load(f)
    
    matches_per_group = 14
    schedule = data.get('schedule', [])
    
    matches_in_group = []
    for index, match in enumerate(schedule):
        g_id = (index // matches_per_group) + 1
        if g_id == group_id:
            matches_in_group.append((match['matchId'], g_id))
            
    return matches_in_group

def get_scorecard(match_id):
	url = "https://cricbuzz-cricket.p.rapidapi.com/mcenter/v1/{}/hscard".format(match_id)
	response = requests.get(url, headers=HEADERS)
	if response.status_code == 200:
		return response.json()
	else:
		return {}

def process_match(match_id, group_id):
    data = get_scorecard(match_id)
    if not data or 'matchHeader' not in data:
        print(f"Skipping match {match_id} (No scorecard logic yet)")
        return
        
    state = data.get('matchHeader', {}).get('state', '')
    if state not in ['Complete', 'Abandon']:
        print(f"Match {match_id} state is {state}, skipping.")
        return
        
    winner = data.get('matchHeader', {}).get('result', {}).get('winningTeam', '')
    
    # Check if abandoned
    if state == 'Abandon':
        print(f"Match {match_id} abandoned.")
        database.save_match_result(
            match_id=match_id,
            winner="ABANDONED",
            orange_cap="", orange_cap_rest="[]", orange_cap_2nd="[]",
            purple_cap="", purple_cap_rest="[]",
            oc_freehit_player="", pc_freehit_player="",
            group_id=group_id
        )
        return

    # Extract batsmen
    all_batsmen = []
    if 'scoreCard' in data:
        for innings in data['scoreCard']:
            batsmen = innings.get('batTeamDetails', {}).get('batsmenData', {})
            for batsman in batsmen.values():
                b_name = batsman.get('batName', '')
                runs = batsman.get('runs', 0)
                sr = batsman.get('strikeRate', 0)
                # handle "did not bat" or missing
                if runs is not None:
                    # sometimes names have " (c)", " (wk)" etc. we might need to exact match 
                    # with squads for better matching, but keeping simple for now
                    all_batsmen.append({
                        "name": b_name,
                        "runs": int(runs) if isinstance(runs, (int, str)) and str(runs).isdigit() else 0,
                        "sr": float(sr) if sr and str(sr).replace('.','').isdigit() else 0.0
                    })

    # Extract bowlers
    all_bowlers = []
    if 'scoreCard' in data:
        for innings in data['scoreCard']:
            bowlers = innings.get('bowlTeamDetails', {}).get('bowlersData', {})
            for bowler in bowlers.values():
                name = bowler.get('bowlName', '')
                wickets = bowler.get('wickets', 0)
                eco = bowler.get('economy', 0)
                if wickets is not None:
                    all_bowlers.append({
                        "name": name,
                        "wickets": int(wickets) if isinstance(wickets, (int, str)) and str(wickets).isdigit() else 0,
                        "economy": float(eco) if eco and str(eco).replace('.','').isdigit() else 999.0
                    })
                    
    # Process Orange Cap
    if all_batsmen:
        max_runs = max(b['runs'] for b in all_batsmen)
        # Players with max runs
        top_batsmen = [b for b in all_batsmen if b['runs'] == max_runs]
        # Sort by best strike rate descending
        top_batsmen.sort(key=lambda x: -x['sr'])
        
        orange_cap = top_batsmen[0]['name']
        orange_cap_rest = json.dumps([b['name'] for b in top_batsmen[1:]])
        
        orange_cap_2nd_arr = [b['name'] for b in all_batsmen if max_runs - 5 <= b['runs'] < max_runs]
        orange_cap_2nd = json.dumps(orange_cap_2nd_arr)
        
        oc_freehit = orange_cap if top_batsmen[0]['runs'] >= 100 else ""
    else:
        orange_cap = ""
        orange_cap_rest = "[]"
        orange_cap_2nd = "[]"
        oc_freehit = ""

    # Process Purple Cap
    if all_bowlers:
        max_wickets = max(b['wickets'] for b in all_bowlers)
        top_bowlers = [b for b in all_bowlers if b['wickets'] == max_wickets]
        # Sort by best economy ascending
        top_bowlers.sort(key=lambda x: x['economy'])
        
        purple_cap = top_bowlers[0]['name']
        purple_cap_rest = json.dumps([b['name'] for b in top_bowlers[1:]])
        
        pc_freehit = purple_cap if top_bowlers[0]['wickets'] >= 5 else "" # score puller had 4 before, scoring guide says more than 5 (>=5 is typical haul)
    else:
        purple_cap = ""
        purple_cap_rest = "[]"
        pc_freehit = ""

    database.save_match_result(
        match_id=match_id,
        winner=winner,
        orange_cap=orange_cap,
        orange_cap_rest=orange_cap_rest,
        orange_cap_2nd=orange_cap_2nd,
        purple_cap=purple_cap,
        purple_cap_rest=purple_cap_rest,
        oc_freehit_player=oc_freehit,
        pc_freehit_player=pc_freehit,
        group_id=group_id
    )
    print(f"Processed results for match {match_id} - Winner: {winner}")

def fetch_all():
    print("Fetching matches from schedule...")
    with open(SCHEDULE_FILE, 'r') as f:
        data = json.load(f)
    
    matches_per_group = 14
    schedule = data.get('schedule', [])
    
    for index, match in enumerate(schedule):
        match_id = match['matchId']
        group_id = (index // matches_per_group) + 1
        process_match(match_id, group_id)

if __name__ == '__main__':
    fetch_all()
