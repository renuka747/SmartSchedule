"""
SmartSchedule Quality Scorer Engine.

This module evaluates the quality of a valid timetable and assigns numerical scores.

Known Limitations:
- Room Types/Capacities: The Utilization metric assumes any room can host any session. 
  The Session model currently has no room-capacity or room-type field (e.g., lecture hall vs lab). 
  Thus, the utilization formula will score "cram a 200-person lecture and a 20-person lab into 
  the same single room" as a utilization improvement, even though that is physically nonsensical. 
  This is an explicit limitation of the model.
"""

import math
from typing import Dict, List, Optional
from collections import defaultdict
from pydantic import BaseModel
from app.core.graph_builder import Session, SessionID
from app.constraints.availability import TimeSlot
from app.core.constants import PERIODS, VALID_DAYS

class InvalidTimeSlotError(Exception):
    """Raised when a scheduled time slot is not found in the valid PERIODS grid."""
    pass

class InvalidDayError(Exception):
    """Raised when a scheduled day is not found in the valid VALID_DAYS grid."""
    pass

class MissingSessionDataError(Exception):
    """Raised when a SessionID in the timetable is not found in the provided session data."""
    pass

class TimetableScore(BaseModel):
    gap_score: float
    balance_score: float
    utilization_score: float
    total_score: float

# Build the lookup dict ONCE at module load time.
# PERIODS is a list of tuples: (label, start_time, end_time)
PERIOD_INDEX_LOOKUP = {
    start_time: index 
    for index, (label, start_time, end_time) in enumerate(PERIODS)
}

def get_period_index(start_time: str) -> int:
    """
    Safely maps a time string to its chronological index (0, 1, 2...).
    Uses the pre-built PERIOD_INDEX_LOOKUP from shared constants.
    Raises InvalidTimeSlotError if an invalid time is scheduled.
    """
    try:
        return PERIOD_INDEX_LOOKUP[start_time]
    except KeyError:
        raise InvalidTimeSlotError(
            f"TimeSlot start_time '{start_time}' is not in the valid PERIODS grid."
        )

def calculate_gap_score(timetable: Dict[SessionID, TimeSlot], sessions: Dict[SessionID, Session]) -> float:
    """
    Calculates the gap penalty for both faculty and divisions, returning a 0-100 score.
    A gap is an unassigned slot strictly between a faculty/division's first and last class on a given day.
    """
    daily_schedules = defaultdict(list)
    
    for session_id, slot in timetable.items():
        session = sessions[session_id]
        p_idx = get_period_index(slot.start_time)
        
        # Track schedule separately for the Faculty and the Division
        daily_schedules[("Faculty", session.faculty, slot.day)].append(p_idx)
        daily_schedules[("Division", session.division, slot.day)].append(p_idx)
        
    if not daily_schedules:
        return 100.0

    total_gaps = 0
    
    for entity_tuple, indices in daily_schedules.items():
        # If an entity has 0 or 1 class on a given day, gaps are mathematically impossible.
        if len(indices) < 2:
            continue
            
        min_idx = min(indices)
        max_idx = max(indices)
        
        span = max_idx - min_idx + 1
        gaps_for_entity_day = span - len(indices)
        total_gaps += gaps_for_entity_day

    # Normalization: average gaps across all evaluated entity-days
    average_gaps_per_entity_day = total_gaps / len(daily_schedules)
    
    # 20.0 factor mathematically anchors the score: the absolute worst-case average 
    # is 5 gaps per day (span 7, 2 classes), which perfectly hits 0.0 (100 - 5*20 = 0).
    score = max(0.0, 100.0 - (average_gaps_per_entity_day * 20.0))
    return score

def calculate_balance_score(timetable: Dict[SessionID, TimeSlot], sessions: Dict[SessionID, Session]) -> float:
    """
    Calculates the balance penalty for faculty and divisions, returning a 0-100 score.
    Balance is based on the max-min difference in daily session counts over the full 5-day week.
    """
    if not timetable:
        return 100.0
        
    # Group session counts by (Entity Type, Entity ID) across the 5 VALID_DAYS.
    # We map day_name -> day_index for fast lookup.
    day_indices = {day: idx for idx, day in enumerate(VALID_DAYS)}
    
    # weekly_counts: key = (EntityType, EntityID), value = List of 5 integers (one per day)
    weekly_counts = defaultdict(lambda: [0] * len(VALID_DAYS))
    
    for session_id, slot in timetable.items():
        session = sessions[session_id]
        
        if slot.day not in day_indices:
            raise InvalidDayError(f"TimeSlot day '{slot.day}' is not in the valid VALID_DAYS grid.")
            
        d_idx = day_indices[slot.day]
        weekly_counts[("Faculty", session.faculty)][d_idx] += 1
        weekly_counts[("Division", session.division)][d_idx] += 1
            
    if not weekly_counts:
        return 100.0

    total_diff = 0
    
    for entity_tuple, counts in weekly_counts.items():
        # max and min are taken across all 5 VALID_DAYS, including 0s.
        diff = max(counts) - min(counts)
        total_diff += diff
        
    # Denominator is the number of distinct entities (faculty + divisions), NOT entity-days!
    average_diff = total_diff / len(weekly_counts)
    
    # 100.0 / 7.0 factor anchors the worst case (average diff of 7) exactly to 0.0.
    score = max(0.0, 100.0 - (average_diff * (100.0 / 7.0)))
    return score

def calculate_utilization_score(timetable: Dict[SessionID, TimeSlot], sessions: Dict[SessionID, Session]) -> float:
    """
    Calculates the spatial utilization efficiency, returning a 0-100 score.
    Higher scores mean classes are packed densely into fewer rooms.
    """
    if not timetable:
        return 100.0
        
    rooms_used = set()
    for session_id in timetable.keys():
        session = sessions[session_id]
        rooms_used.add(session.room)
        
    distinct_rooms_used = len(rooms_used)
    
    # The grid size representing 100% capacity for a single room for the entire week
    periods_per_day = len(PERIODS)
    days_per_week = len(VALID_DAYS)
    room_weekly_capacity = periods_per_day * days_per_week # e.g. 7 * 5 = 35
    
    total_capacity = distinct_rooms_used * room_weekly_capacity
    
    # NOTE: We assume no two sessions share the same room at the same time, 
    # which is guaranteed by the constraints engine upstream. 
    # Thus, len(timetable) is the exact true count of occupied slot-room blocks.
    occupied_slots = len(timetable)
    
    ratio = occupied_slots / total_capacity
    return ratio * 100.0

def score_timetable(
    timetable: Dict[SessionID, TimeSlot], 
    session_list: List[Session], 
    weights: Optional[Dict[str, float]] = None
) -> TimetableScore:
    """
    Evaluates the overall quality of a timetable and computes a weighted total score (0-100).
    """
    if weights is None:
        weights = {"gaps": 0.4, "balance": 0.4, "utilization": 0.2}
        
    # Validate missing weight keys
    required_keys = {"gaps", "balance", "utilization"}
    missing_keys = required_keys - set(weights.keys())
    if missing_keys:
        raise ValueError(f"Weights dict is missing required keys: {missing_keys}")
        
    # Validate weights sum to 1.0 (with small float tolerance)
    weight_sum = sum(weights.values())
    if not math.isclose(weight_sum, 1.0, rel_tol=1e-5):
        raise ValueError(f"Weights must sum to 1.0, but got {weight_sum:.4f}")
        
    # Convert session_list to dict for O(1) lookups
    sessions_dict = {s.id: s for s in session_list}
    
    # Validate all scheduled sessions exist in data
    for session_id in timetable.keys():
        if session_id not in sessions_dict:
            raise MissingSessionDataError(f"SessionID '{session_id}' in timetable is missing from session_list.")
            
    # Compute component scores
    gaps = calculate_gap_score(timetable, sessions_dict)
    balance = calculate_balance_score(timetable, sessions_dict)
    utilization = calculate_utilization_score(timetable, sessions_dict)
    
    # Weighted sum
    total_score = (
        (gaps * weights["gaps"]) + 
        (balance * weights["balance"]) + 
        (utilization * weights["utilization"])
    )
    
    return TimetableScore(
        gap_score=gaps,
        balance_score=balance,
        utilization_score=utilization,
        total_score=total_score
    )

if __name__ == "__main__":
    print("================================")
    print("Running Quality Scorer tests...")
    print("================================")
    
    s1 = Session(id="S1", subject="Math", faculty="Dr. Smith", division="DivA", room="R1")
    s2 = Session(id="S2", subject="Physics", faculty="Dr. Smith", division="DivA", room="R2")
    s3 = Session(id="S3", subject="Chemistry", faculty="Dr. Jones", division="DivA", room="R3")
    sessions = {"S1": s1, "S2": s2, "S3": s3}
    
    print("\n--- calculate_gap_score tests ---")
    tt_perfect = {
        "S1": TimeSlot(day="Monday", start_time="09:00"),
        "S2": TimeSlot(day="Monday", start_time="10:00"),
        "S3": TimeSlot(day="Monday", start_time="11:00"),
    }
    assert calculate_gap_score(tt_perfect, sessions) == 100.0
    print("Gap Test 1 Passed: Back-to-back classes (Score 100.0)")
    
    tt_single = {
        "S1": TimeSlot(day="Tuesday", start_time="09:00"),
    }
    assert calculate_gap_score(tt_single, sessions) == 100.0
    print("Gap Test 2 Passed: Single class on a day (Score 100.0)")
    
    tt_gaps = {
        "S1": TimeSlot(day="Wednesday", start_time="09:00"), 
        "S2": TimeSlot(day="Wednesday", start_time="12:00"), 
        "S3": TimeSlot(day="Wednesday", start_time="15:00"), 
    }
    score_gaps = calculate_gap_score(tt_gaps, sessions)
    assert abs(score_gaps - 66.666) < 0.001
    print("Gap Test 3 Passed: Real gaps penalized correctly (Score ~66.67)")
    
    tt_invalid = {
        "S1": TimeSlot(day="Wednesday", start_time="08:00"),
    }
    try:
        calculate_gap_score(tt_invalid, sessions)
        assert False, "Should have raised InvalidTimeSlotError"
    except InvalidTimeSlotError as e:
        print("Gap Test 4 Passed: InvalidTimeSlotError raised correctly")

    s4 = Session(id="S4", subject="CS", faculty="Dr. Turing", division="DivB", room="R1")
    s5 = Session(id="S5", subject="Bio", faculty="Dr. Darwin", division="DivB", room="R2")
    s6 = Session(id="S6", subject="Math", faculty="Dr. Smith", division="DivB", room="R3")
    sessions_real = {"S1": s1, "S2": s2, "S3": s3, "S4": s4, "S5": s5, "S6": s6}
    
    tt_real = {
        "S1": TimeSlot(day="Monday", start_time="09:00"),
        "S2": TimeSlot(day="Monday", start_time="10:00"),
        "S3": TimeSlot(day="Monday", start_time="11:00"),
        "S4": TimeSlot(day="Tuesday", start_time="09:00"),
        "S5": TimeSlot(day="Tuesday", start_time="12:00"),
        "S6": TimeSlot(day="Tuesday", start_time="16:00"), 
    }
    score_real = calculate_gap_score(tt_real, sessions_real)
    print(f"Gap Test 5 Passed: Realistic Score differentiating schedule quality = {score_real:.2f}")
    
    print("\n--- calculate_balance_score tests ---")
    assert calculate_balance_score({}, sessions_real) == 100.0
    print("Balance Test 1 Passed: Empty timetable (Score 100.0)")
    
    tt_even = {}
    sessions_even = {}
    for i, day in enumerate(VALID_DAYS):
        sid = f"SEven_{i}"
        sessions_even[sid] = Session(id=sid, subject="Math", faculty="EvenFac", division="EvenDiv", room="R1")
        tt_even[sid] = TimeSlot(day=day, start_time="09:00")
        
    assert calculate_balance_score(tt_even, sessions_even) == 100.0
    print("Balance Test 2 Passed: Perfectly even schedule 1-1-1-1-1 (Score 100.0)")
    
    tt_worst = {}
    sessions_worst = {}
    for i, period_tuple in enumerate(PERIODS):
        sid = f"SWorst_{i}"
        sessions_worst[sid] = Session(id=sid, subject="Math", faculty="WorstFac", division="WorstDiv", room="R1")
        tt_worst[sid] = TimeSlot(day="Monday", start_time=period_tuple[1])
        
    score_worst = calculate_balance_score(tt_worst, sessions_worst)
    assert abs(score_worst - 0.0) < 0.001
    print("Balance Test 3 Passed: 7-0-0-0-0 worst case (Score ~0.0)")
    
    tt_mixed = {**tt_even, **tt_worst}
    sessions_mixed = {**sessions_even, **sessions_worst}
    score_mixed = calculate_balance_score(tt_mixed, sessions_mixed)
    assert abs(score_mixed - 50.0) < 0.001
    print("Balance Test 4 Passed: Realistic mixed case (Score ~50.0)")
    
    tt_invalid_day = {
        "S1": TimeSlot(day="Saturday", start_time="09:00"),
    }
    try:
        calculate_balance_score(tt_invalid_day, sessions)
        assert False, "Should have raised InvalidDayError"
    except InvalidDayError as e:
        print("Balance Test 5 Passed: InvalidDayError raised correctly")
        
    print("\n--- calculate_utilization_score tests ---")
    
    # CASE 1: Empty timetable
    assert calculate_utilization_score({}, sessions) == 100.0
    print("Utilization Test 1 Passed: Empty timetable (Score 100.0)")
    
    # CASE 2: Packed into 1 room
    sessions_packed = {
        "S1": Session(id="S1", subject="M", faculty="F", division="D", room="R1"),
        "S2": Session(id="S2", subject="P", faculty="F", division="D", room="R1"),
        "S3": Session(id="S3", subject="C", faculty="F", division="D", room="R1"),
    }
    score_packed = calculate_utilization_score(tt_perfect, sessions_packed)
    assert abs(score_packed - (3/35 * 100.0)) < 0.001
    print(f"Utilization Test 2 Passed: 1-room packed (Score {score_packed:.2f})")
    
    # CASE 3: Spread across multiple rooms
    sessions_spread = {
        "S1": Session(id="S1", subject="M", faculty="F", division="D", room="R1"),
        "S2": Session(id="S2", subject="P", faculty="F", division="D", room="R2"),
        "S3": Session(id="S3", subject="C", faculty="F", division="D", room="R3"),
    }
    score_spread = calculate_utilization_score(tt_perfect, sessions_spread)
    assert abs(score_spread - (3/105 * 100.0)) < 0.001
    print(f"Utilization Test 3 Passed: 3-room spread (Score {score_spread:.2f})")
    
    # CASE 4: Exactly 1 session
    tt_one = {"S1": TimeSlot(day="Monday", start_time="09:00")}
    score_one = calculate_utilization_score(tt_one, sessions_packed)
    assert abs(score_one - (1/35 * 100.0)) < 0.001
    print(f"Utilization Test 4 Passed: 1-session edge case (Score {score_one:.2f})")
    
    print("\n--- score_timetable tests ---")
    # CASE 1: Valid timetable
    score_result = score_timetable(tt_real, list(sessions_real.values()))
    
    print(f"Integration Test 1 Passed: Valid timetable (Total Score: {score_result.total_score:.2f})")
    print(f"  --> Gaps: {score_result.gap_score:.2f} * 0.4 = {score_result.gap_score * 0.4:.2f}")
    print(f"  --> Balance: {score_result.balance_score:.2f} * 0.4 = {score_result.balance_score * 0.4:.2f}")
    print(f"  --> Utilization: {score_result.utilization_score:.2f} * 0.2 = {score_result.utilization_score * 0.2:.2f}")
    expected_total = (score_result.gap_score * 0.4) + (score_result.balance_score * 0.4) + (score_result.utilization_score * 0.2)
    assert abs(score_result.total_score - expected_total) < 0.001
    
    # CASE 2: Missing SessionID
    tt_missing = {"S999": TimeSlot(day="Monday", start_time="09:00")}
    try:
        score_timetable(tt_missing, list(sessions_real.values()))
        assert False, "Should have raised MissingSessionDataError"
    except MissingSessionDataError as e:
        assert "S999" in str(e)
        print("Integration Test 2 Passed: MissingSessionDataError raised correctly")
        
    # CASE 3: Weights don't sum to 1.0
    bad_weights_sum = {"gaps": 0.5, "balance": 0.5, "utilization": 0.5}
    try:
        score_timetable(tt_real, list(sessions_real.values()), weights=bad_weights_sum)
        assert False, "Should have raised ValueError for weight sum"
    except ValueError as e:
        assert "sum to 1.0" in str(e)
        print("Integration Test 3 Passed: Weight sum ValueError raised correctly")
        
    # CASE 4: Missing weight key
    bad_weights_key = {"gaps": 0.5, "balance": 0.5}
    try:
        score_timetable(tt_real, list(sessions_real.values()), weights=bad_weights_key)
        assert False, "Should have raised ValueError for missing keys"
    except ValueError as e:
        assert "missing required keys" in str(e)
        print("Integration Test 4 Passed: Missing weight key ValueError raised correctly")

    print("\nAll integration tests passed!")
