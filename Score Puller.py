import requests
import json
from datetime import datetime
from apiclient import discovery
from httplib2 import Http
from oauth2client import client, file, tools
import pytz

SCOPES = [
	"https://www.googleapis.com/auth/spreadsheets",
	"https://www.googleapis.com/auth/drive",
	"https://www.googleapis.com/auth/drive.file"
]

SHEETS_DISCOVERY_DOC = "https://sheets.googleapis.com/$discovery/rest?version=v4"

def get_google_sheets_service():
	store = file.Storage("token.json")
	creds = store.get()
	if not creds or creds.invalid:
		flow = client.flow_from_clientsecrets("credentials_mine.json", SCOPES)
		creds = tools.run_flow(flow, store)

	service = discovery.build(
		"sheets",
		"v4",
		http=creds.authorize(Http()),
		discoveryServiceUrl=SHEETS_DISCOVERY_DOC,
		static_discovery=False,
	)
	return service

headers = {
	"X-RapidAPI-Key": "df8b086635msh92585d5dcb5bc07p14a97ejsn4d3ca5d7d26c",
	"X-RapidAPI-Host": "cricbuzz-cricket.p.rapidapi.com"
}

def get_match_id():
	with open("ipl-2025-schedule_new.json") as f:
		schedule = json.load(f)

	# Get today's date in yyyy-mm-dd format
	today_str = datetime.today().strftime("%Y-%m-%d")

	# Collect match IDs for today
	today_match_ids = []

	# Loop through matches
	print(schedule)
	for match in schedule:
		match_date = match.get("date_time(est)", "")
		match_id = match.get("matchId", "")

		# Convert match date to yyyy-mm-dd
		try:
			match_date_obj = datetime.strptime(match_date, "%Y-%m-%d %H:%M")
			print(match_date_obj, today_str)
			if match_date_obj.strftime("%Y-%m-%d") == today_str:
				today_match_ids.append(match_id)
		except Exception as e:
			print(e)

	return today_match_ids

def get_scorecard(match_id):
	url = "https://cricbuzz-cricket.p.rapidapi.com/mcenter/v1/{}/hscard".format(match_id)
	response = requests.get(url, headers=headers)
	if response.status_code == 200:
		#utils.write_json('scorecard-match.json',response.json())
		return response.json()
	else:
		return {}

def format_data(data, match):
	match_number = data.get("matchHeader", {}).get("matchDescription", "")
	team1 = data.get("matchHeader", {}).get("team1", {}).get("name", "")
	team2 = data.get("matchHeader", {}).get("team2", {}).get("name", "")
	winner = data.get("matchHeader", {}).get("result", {}).get("winningTeam", "")

	# Combine all batsmen
	all_batsmen = []
	for innings in data['scoreCard']:
		batsmen = innings.get('batTeamDetails', {}).get('batsmenData', {})
		for batsman in batsmen.values():
			all_batsmen.append({
				"name": batsman['batName'],
				"runs": batsman['runs']
			})

	# Find Orange Cap and ties
	max_runs = max(b['runs'] for b in all_batsmen)
	orange_cap_all = [b for b in all_batsmen if b['runs'] == max_runs]
	orange_cap_all.sort(key=lambda x: x['name'])

	orange_cap = orange_cap_all[0]
	orange_cap_ties = orange_cap_all[1:]

	# Find batsmen within 5 runs of max (Orange Cap 2nd)
	orange_cap_2nd = [b for b in all_batsmen if max_runs - 5 <= b['runs'] < max_runs]
	orange_cap_2nd.sort(key=lambda x: (-x['runs'], x['name']))

	# Check if orange cap scored a hundred
	oc_freehit = orange_cap['name'] if orange_cap['runs'] >= 100 else ''

	# Combine all bowlers
	all_bowlers = []
	for innings in data['scoreCard']:
		bowlers = innings.get('bowlTeamDetails', {}).get('bowlersData', {})
		for bowler in bowlers.values():
			all_bowlers.append({
				"name": bowler['bowlName'],
				"wickets": bowler['wickets'],
				"economy": bowler['economy']
			})

	# Find Purple Cap and ties
	max_wickets = max(b['wickets'] for b in all_bowlers)
	top_bowlers = [b for b in all_bowlers if b['wickets'] == max_wickets]
	top_bowlers.sort(key=lambda x: (x['economy'], x['name']))

	purple_cap = top_bowlers[0]
	purple_cap_ties = top_bowlers[1:]

	# Check if purple cap took 4 or more wickets
	pc_freehit = purple_cap['name'] if purple_cap['wickets'] >= 4 else ''

	# Prepare rows for spreadsheet in the specified format
	rows = [
		["WINNER", winner],
		["ORANGE CAP", orange_cap['name']],
		["ORANGE CAP TIE 1", orange_cap_ties[0]['name'] if len(orange_cap_ties) > 0 else ""],
		["ORANGE CAP 2nd 1", orange_cap_2nd[0]['name'] if len(orange_cap_2nd) > 0 else ""],
		["ORANGE CAP 2nd 2", orange_cap_2nd[1]['name'] if len(orange_cap_2nd) > 1 else ""],
		["ORANGE CAP 2nd 3", orange_cap_2nd[2]['name'] if len(orange_cap_2nd) > 2 else ""],
		["PURPLE CAP", purple_cap['name']],
		["PURPLE CAP TIE 1", purple_cap_ties[0]['name'] if len(purple_cap_ties) > 0 else ""],
		["PURPLE CAP TIE 2", purple_cap_ties[1]['name'] if len(purple_cap_ties) > 1 else ""],
		["PURPLE CAP TIE 3", purple_cap_ties[2]['name'] if len(purple_cap_ties) > 2 else ""],
		["PURPLE CAP TIE 4", purple_cap_ties[3]['name'] if len(purple_cap_ties) > 3 else ""],
		["PURPLE CAP TIE 5", purple_cap_ties[4]['name'] if len(purple_cap_ties) > 4 else ""],
		["MATCH#", match_number],
		["TEAM 1", team1],
		["TEAM 2", team2],
		["OC FREEHIT", oc_freehit],
		["PC FREEHIT", pc_freehit]
	]

	print(rows)
	# Write to Google Spreadsheet
	try:
		service = get_google_sheets_service()
		spreadsheet_id = '19365vzYTMQkGrkP0fFuQ54SC5N05995-vmL_ABD9u-E'  # Your spreadsheet ID
		
		# 1. Create and write to new match sheet
		range_name = f'Match {match_number}!A1'  # Creates a new sheet for each match
		
		# Create a new sheet for this match
		body = {
			'requests': [{
				'addSheet': {
					'properties': {
						'title': f'Match {match_number}'
					}
				}
			}]
		}
		service.spreadsheets().batchUpdate(
			spreadsheetId=spreadsheet_id,
			body=body
		).execute()

		# Write the data to new match sheet
		body = {
			'values': rows
		}
		result = service.spreadsheets().values().update(
			spreadsheetId=spreadsheet_id,
			range=range_name,
			valueInputOption='RAW',
			body=body
		).execute()
		
		# 2. Write to Response Input sheet
		response_input_range = 'Response Input!B68:C84'
		result = service.spreadsheets().values().update(
			spreadsheetId=spreadsheet_id,
			range=response_input_range,
			valueInputOption='RAW',
			body=body
		).execute()
		
		print(f"Data written to Google Spreadsheet for match {match_number} and Response Input sheet")
	except Exception as e:
		print(f"Error writing to Google Spreadsheet: {e}")

if __name__ == '__main__':
	matches = get_match_id()
	for match in matches:
		match_data = get_scorecard(match)
		format_data(match_data, match)
