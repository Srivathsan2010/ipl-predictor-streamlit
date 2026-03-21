import json
import database

SCHEDULE_FILE = r"C:\Users\shrir\Desktop\IPL 2025\ipl-2025-squad-final_new.json"

def get_schedule_ordered():
    with open(SCHEDULE_FILE, 'r') as f:
        data = json.load(f)
    return data.get('schedule', [])

def calculate_scores():
    users_scores = {}
    users_streaks = {}
    users_freehits_oc = {}
    users_freehits_pc = {}
    
    # Init users
    for u in database.get_all_users():
        email = u['email']
        users_scores[email] = 0
        users_streaks[email] = 0
        users_freehits_oc[email] = False
        users_freehits_pc[email] = False

    schedule = get_schedule_ordered()
    match_results = database.get_all_match_results()
    all_preds = database.get_all_predictions()
    
    # Organize preds by match_id
    preds_by_match = {}
    for p in all_preds:
        preds_by_match.setdefault(p['match_id'], []).append(p)

    user_match_scores = []

    for match in schedule:
        m_id = match['matchId']
        if m_id not in match_results:
            continue
        
        res = match_results[m_id]
        if res['winner'] == 'ABANDONED':
            for email in users_streaks:
                users_streaks[email] = 0
            continue
            
        try:
            oc_rest = json.loads(res.get('orange_cap_rest', '[]'))
        except:
            oc_rest = []
        try:
            oc_2nd = json.loads(res.get('orange_cap_2nd', '[]'))
        except:
            oc_2nd = []
        try:
            pc_rest = json.loads(res.get('purple_cap_rest', '[]'))
        except:
            pc_rest = []

        preds = preds_by_match.get(m_id, [])
        for p in preds:
            email = p['email']
            
            # initialize if predicting for first time not in DB users yet
            if email not in users_scores:
                users_scores[email] = 0
                users_streaks[email] = 0
                users_freehits_oc[email] = False
                users_freehits_pc[email] = False

            base_points = 0
            is_winner_correct = False
            
            # 1. Winner
            if p['winner'] == res['winner']:
                base_points += 1
                is_winner_correct = True
                users_streaks[email] += 1
            else:
                users_streaks[email] = 0
                
            # 2. Orange Cap
            predicted_oc = p['orange_cap']
            if predicted_oc == res['orange_cap']:
                base_points += 3
            elif predicted_oc in oc_rest:
                base_points += 2
            elif predicted_oc in oc_2nd:
                base_points += 1
                
            # 3. Purple Cap
            predicted_pc = p['purple_cap']
            if predicted_pc == res['purple_cap']:
                base_points += 3
            elif predicted_pc in pc_rest:
                base_points += 2
                
            # Streak Bonus
            if is_winner_correct and users_streaks[email] >= 5:
                base_points += 2
                users_streaks[email] = 0  
                
            # Multipliers
            p_used_mult = p['multiplier_used']
            has_oc_fh = users_freehits_oc[email]
            has_pc_fh = users_freehits_pc[email]
            
            multiplier_factor = 1
            if p_used_mult and not has_oc_fh and not has_pc_fh:
                multiplier_factor = 2
            elif p_used_mult and (has_oc_fh ^ has_pc_fh):
                multiplier_factor = 4
            elif p_used_mult and has_oc_fh and has_pc_fh:
                multiplier_factor = 6
            elif not p_used_mult and (has_oc_fh ^ has_pc_fh):
                multiplier_factor = 2
            elif not p_used_mult and has_oc_fh and has_pc_fh:
                multiplier_factor = 4
                
            total_points = base_points * multiplier_factor
            
            users_scores[email] += total_points
            
            user_match_scores.append({
                'email': email,
                'match_id': m_id,
                'points_earned': total_points,
                'multiplier_factor': multiplier_factor,
                'base_points': base_points
            })

            # Reset freehits
            users_freehits_oc[email] = False
            users_freehits_pc[email] = False
            
            # Earn new freehits for FUTURE matches
            if res['oc_freehit_player'] and predicted_oc == res['oc_freehit_player']:
                users_freehits_oc[email] = True
            if res['pc_freehit_player'] and predicted_pc == res['pc_freehit_player']:
                users_freehits_pc[email] = True

    return users_scores, user_match_scores

if __name__ == '__main__':
    scores, match_scores = calculate_scores()
    for email, score in scores.items():
        print(f"{email}: {score} pts")
