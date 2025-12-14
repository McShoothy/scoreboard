"""
Bracket generation functions for different tournament formats.
"""
import math
import random
from itertools import combinations

from app import db
from app.models import Match


def create_single_elimination_bracket(tournament_id, team_ids):
    """Create elimination bracket for the tournament with bye support for uneven teams."""
    num_teams = len(team_ids)
    if num_teams < 2:
        return
    
    # Convert to list of ints and shuffle
    team_ids = [int(t) for t in team_ids]
    random.shuffle(team_ids)
    
    # Calculate bracket size (next power of 2)
    num_rounds = math.ceil(math.log2(num_teams))
    bracket_size = 2 ** num_rounds
    num_byes = bracket_size - num_teams
    
    # Create all match slots first
    all_matches = []
    for round_num in range(1, num_rounds + 1):
        matches_in_round = bracket_size // (2 ** round_num)
        for match_num in range(1, matches_in_round + 1):
            match = Match(
                tournament_id=tournament_id,
                round_number=round_num,
                match_number=match_num
            )
            db.session.add(match)
            all_matches.append(match)
    
    db.session.commit()
    
    # Link matches to next round
    for round_num in range(1, num_rounds):
        current_round = [m for m in all_matches if m.round_number == round_num]
        next_round = [m for m in all_matches if m.round_number == round_num + 1]
        
        for i, match in enumerate(current_round):
            next_match_idx = i // 2
            if next_match_idx < len(next_round):
                match.next_match_id = next_round[next_match_idx].id
    
    db.session.commit()
    
    # Get first round matches
    first_round = [m for m in all_matches if m.round_number == 1]
    first_round.sort(key=lambda m: m.match_number)
    
    # Pad team list with None for byes
    padded_teams = team_ids + [None] * num_byes
    
    # Assign teams to first round - standard seeding
    for i, match in enumerate(first_round):
        team1_idx = i * 2
        team2_idx = i * 2 + 1
        
        if team1_idx < len(padded_teams):
            match.team1_id = padded_teams[team1_idx]
        if team2_idx < len(padded_teams):
            match.team2_id = padded_teams[team2_idx]
        
        # Auto-complete bye matches (one team is None)
        if match.team1_id and not match.team2_id:
            match.winner_id = match.team1_id
            match.is_completed = True
            # Advance winner to next round
            if match.next_match_id:
                next_match = Match.query.get(match.next_match_id)
                if next_match:
                    if match.match_number % 2 == 1:
                        next_match.team1_id = match.team1_id
                    else:
                        next_match.team2_id = match.team1_id
        elif match.team2_id and not match.team1_id:
            match.winner_id = match.team2_id
            match.is_completed = True
            if match.next_match_id:
                next_match = Match.query.get(match.next_match_id)
                if next_match:
                    if match.match_number % 2 == 1:
                        next_match.team1_id = match.team2_id
                    else:
                        next_match.team2_id = match.team2_id
        elif not match.team1_id and not match.team2_id:
            match.is_completed = True
    
    db.session.commit()
    
    # Set first playable match as current
    for match in all_matches:
        if not match.is_completed and match.team1_id and match.team2_id:
            match.is_current = True
            break
    
    db.session.commit()


def create_double_elimination_bracket(tournament_id, team_ids):
    """Create double elimination bracket - winners and losers brackets."""
    num_teams = len(team_ids)
    if num_teams < 3:
        return
    
    team_ids = list(team_ids)
    random.shuffle(team_ids)
    
    # Calculate rounds for winners bracket
    num_rounds = math.ceil(math.log2(num_teams))
    total_slots = 2 ** num_rounds
    num_byes = total_slots - num_teams
    
    # Create winners bracket matches
    matches = []
    for round_num in range(1, num_rounds + 1):
        matches_in_round = total_slots // (2 ** round_num)
        for match_num in range(1, matches_in_round + 1):
            match = Match(
                tournament_id=tournament_id,
                round_number=round_num,
                match_number=match_num,
                match_type='bracket'
            )
            db.session.add(match)
            matches.append(match)
    
    # Create losers bracket matches
    losers_rounds = (num_rounds - 1) * 2
    losers_match_num = 1
    for round_num in range(1, losers_rounds + 1):
        if round_num % 2 == 1:
            matches_in_round = max(1, total_slots // (2 ** ((round_num + 1) // 2 + 1)))
        else:
            matches_in_round = max(1, total_slots // (2 ** (round_num // 2 + 1)))
        
        for match_num in range(1, matches_in_round + 1):
            match = Match(
                tournament_id=tournament_id,
                round_number=100 + round_num,
                match_number=losers_match_num,
                match_type='losers_bracket'
            )
            db.session.add(match)
            matches.append(match)
            losers_match_num += 1
    
    # Grand finals
    grand_finals = Match(
        tournament_id=tournament_id,
        round_number=200,
        match_number=1,
        match_type='finals'
    )
    db.session.add(grand_finals)
    matches.append(grand_finals)
    
    db.session.commit()
    
    # Assign teams to first round
    first_round = [m for m in matches if m.round_number == 1]
    bye_teams = team_ids[:num_byes]
    playing_teams = team_ids[num_byes:]
    
    for i, team_id in enumerate(playing_teams):
        match_idx = i // 2
        if match_idx < len(first_round):
            if i % 2 == 0:
                first_round[match_idx].team1_id = int(team_id)
            else:
                first_round[match_idx].team2_id = int(team_id)
    
    # Handle byes
    second_round = [m for m in matches if m.round_number == 2 and m.match_type == 'bracket']
    for i, team_id in enumerate(bye_teams):
        if i < len(second_round):
            if second_round[i].team1_id is None:
                second_round[i].team1_id = int(team_id)
            else:
                second_round[i].team2_id = int(team_id)
    
    # Set first match as current
    for match in first_round:
        if match.team1_id and match.team2_id:
            match.is_current = True
            break
    
    db.session.commit()


def create_round_robin(tournament_id, team_ids):
    """Create round robin - every team plays every other team."""
    num_teams = len(team_ids)
    if num_teams < 3:
        return
    
    team_ids = list(team_ids)
    random.shuffle(team_ids)
    
    # Generate all possible pairings
    all_pairings = list(combinations(team_ids, 2))
    random.shuffle(all_pairings)
    
    # Create matches
    matches_per_round = max(1, num_teams // 2)
    round_num = 1
    match_num = 1
    
    for i, (team1_id, team2_id) in enumerate(all_pairings):
        match = Match(
            tournament_id=tournament_id,
            round_number=round_num,
            match_number=match_num,
            team1_id=int(team1_id),
            team2_id=int(team2_id),
            match_type='group',
            group_name='Round Robin'
        )
        db.session.add(match)
        
        match_num += 1
        if match_num > matches_per_round:
            match_num = 1
            round_num += 1
    
    db.session.commit()
    
    # Set first match as current
    first_match = Match.query.filter_by(tournament_id=tournament_id).order_by(Match.round_number, Match.match_number).first()
    if first_match:
        first_match.is_current = True
        db.session.commit()


def create_round_robin_playoffs(tournament_id, team_ids):
    """Create round robin group stage followed by top 4 playoffs."""
    num_teams = len(team_ids)
    if num_teams < 5:
        return
    
    team_ids = list(team_ids)
    random.shuffle(team_ids)
    
    # Create round robin group stage matches
    all_pairings = list(combinations(team_ids, 2))
    random.shuffle(all_pairings)
    
    matches_per_round = max(1, num_teams // 2)
    round_num = 1
    match_num = 1
    
    for i, (team1_id, team2_id) in enumerate(all_pairings):
        match = Match(
            tournament_id=tournament_id,
            round_number=round_num,
            match_number=match_num,
            team1_id=int(team1_id),
            team2_id=int(team2_id),
            match_type='group',
            group_name='Group Stage'
        )
        db.session.add(match)
        
        match_num += 1
        if match_num > matches_per_round:
            match_num = 1
            round_num += 1
    
    # Create playoff bracket (4 teams - semifinals and finals)
    playoff_round = 100
    
    semi1 = Match(
        tournament_id=tournament_id,
        round_number=playoff_round,
        match_number=1,
        match_type='bracket',
        group_name='Semifinal 1'
    )
    db.session.add(semi1)
    
    semi2 = Match(
        tournament_id=tournament_id,
        round_number=playoff_round,
        match_number=2,
        match_type='bracket',
        group_name='Semifinal 2'
    )
    db.session.add(semi2)
    
    db.session.commit()
    
    finals = Match(
        tournament_id=tournament_id,
        round_number=playoff_round + 1,
        match_number=1,
        match_type='finals',
        group_name='Finals'
    )
    db.session.add(finals)
    
    semi1.next_match_id = finals.id
    semi2.next_match_id = finals.id
    
    db.session.commit()
    
    # Set first group match as current
    first_match = Match.query.filter_by(tournament_id=tournament_id, match_type='group').order_by(Match.round_number, Match.match_number).first()
    if first_match:
        first_match.is_current = True
        db.session.commit()


def create_swiss_round(tournament_id, team_ids, round_num=1):
    """Create a Swiss system round - pair teams with similar records."""
    num_teams = len(team_ids)
    if num_teams < 4:
        return
    
    team_ids = list(team_ids)
    random.shuffle(team_ids)
    
    # For first round, just pair randomly
    match_num = 1
    for i in range(0, len(team_ids) - 1, 2):
        match = Match(
            tournament_id=tournament_id,
            round_number=round_num,
            match_number=match_num,
            team1_id=int(team_ids[i]),
            team2_id=int(team_ids[i + 1]) if i + 1 < len(team_ids) else None,
            match_type='group',
            group_name=f'Swiss Round {round_num}'
        )
        db.session.add(match)
        match_num += 1
    
    # If odd number of teams, last team gets a bye
    if num_teams % 2 == 1:
        bye_match = Match(
            tournament_id=tournament_id,
            round_number=round_num,
            match_number=match_num,
            team1_id=int(team_ids[-1]),
            team2_id=None,
            match_type='group',
            group_name=f'Swiss Round {round_num} (Bye)',
            is_completed=True,
            winner_id=int(team_ids[-1])
        )
        db.session.add(bye_match)
    
    db.session.commit()
    
    # Set first match as current
    first_match = Match.query.filter_by(tournament_id=tournament_id, round_number=round_num).order_by(Match.match_number).first()
    if first_match and first_match.team1_id and first_match.team2_id:
        first_match.is_current = True
        db.session.commit()
