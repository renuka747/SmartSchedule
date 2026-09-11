from typing import Dict, List, Tuple
from collections import defaultdict
from app.core.graph_builder import Session, SessionID
from app.constraints.availability import TimeSlot

# ==========================================
# 1. SHARED CONSTANTS (Flagged for coordination)
# ==========================================
# COORDINATION REQUIRED: Renuka's graph_coloring.py MUST use this exact same list
# to assign time slots. If she assigns a slot not in this list, gap scoring will crash.
# Consider moving this to an `app/core/constants.py` file later so both modules import it.
VALID_DAYS = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday"]
PERIODS = ["09:00", "10:00", "11:00", "12:00", "13:00", "14:00", "15:00"]

def get_period_index(start_time: str) -> int:
    """
    Safely maps a time string to its chronological index (0, 1, 2...).
    Raises ValueError if an invalid time is scheduled.
    """
    return PERIODS.index(start_time)

def calculate_gap_score(timetable: Dict[SessionID, TimeSlot], sessions: Dict[SessionID, Session]) -> float:
    """
    Calculates the gap penalty for both faculty and divisions, returning a 0-100 score.
    A gap is an unassigned slot strictly between a faculty/division's first and last class on a given day.
    """
    # Group booked period indices by (Entity Type, Entity ID, Day)
    daily_schedules = defaultdict(list)
    
    for session_id, slot in timetable.items():
        session = sessions[session_id]
        p_idx = get_period_index(slot.start_time)
        
        # Track schedule separately for the Faculty and the Division
        daily_schedules[("Faculty", session.faculty, slot.day)].append(p_idx)
        daily_schedules[("Division", session.division, slot.day)].append(p_idx)
        
    total_gaps = 0
    
    for entity_tuple, indices in daily_schedules.items():
        if len(indices) < 2:
            continue # No gaps possible if you only have 0 or 1 class that day
            
        min_idx = min(indices)
        max_idx = max(indices)
        
        # O(1) mathematical gap calculation:
        # The number of slots between the first and last class (inclusive)
        # minus the number of actual classes scheduled in that span.
        # e.g., min=0, max=3, classes=[0, 1, 3]
        # Span = 3 - 0 + 1 = 4 slots total. We have 3 classes.
        # Gaps = 4 - 3 = 1 gap.
        span = max_idx - min_idx + 1
        gaps_for_entity_day = span - len(indices)
        
        total_gaps += gaps_for_entity_day

    # Normalization: Deduct 5 points per gap slot from a perfect 100.
    # Floor at 0.0 so we don't return negative scores for horrific timetables.
    score = max(0.0, 100.0 - (total_gaps * 5.0))
    return score

if __name__ == "__main__":
    # --- Manual Tests for Gap Score ---
    print("Running Quality Scorer tests...")
    
    # Setup Fake Session Data
    s1 = Session(id="S1", subject="Math", faculty="Dr. Smith", division="DivA", room="R1")
    s2 = Session(id="S2", subject="Physics", faculty="Dr. Smith", division="DivA", room="R2")
    s3 = Session(id="S3", subject="Chemistry", faculty="Dr. Jones", division="DivA", room="R3")
    sessions = {"S1": s1, "S2": s2, "S3": s3}
    
    # Scenario 1: Perfect schedule, back-to-back
    # Dr. Smith teaches 09:00 and 10:00. DivA has classes 09:00, 10:00, 11:00.
    # No gaps for anyone.
    tt_perfect = {
        "S1": TimeSlot(day="Monday", start_time="09:00"),
        "S2": TimeSlot(day="Monday", start_time="10:00"),
        "S3": TimeSlot(day="Monday", start_time="11:00"),
    }
    score_perfect = calculate_gap_score(tt_perfect, sessions)
    assert score_perfect == 100.0, f"Expected 100.0, got {score_perfect}"
    print("Test 1 Passed: Perfect back-to-back schedule scored 100.0")
    
    # Scenario 2: Gaps introduced
    # S1 at 09:00, S2 at 11:00 -> Gap at 10:00 for Dr. Smith & DivA.
    # S3 at 12:00 -> DivA has classes at 09:00, 11:00, 12:00 (Span 4, Classes 3 = 1 gap).
    tt_gaps = {
        "S1": TimeSlot(day="Monday", start_time="09:00"),
        "S2": TimeSlot(day="Monday", start_time="11:00"),
        "S3": TimeSlot(day="Monday", start_time="12:00"),
    }
    # Expected Gaps: Dr. Smith (1) + DivA (1) + Dr. Jones (0) = 2 total gaps.
    # Penalty = 2 * 5.0 = 10.0 deduction.
    score_gaps = calculate_gap_score(tt_gaps, sessions)
    assert score_gaps == 90.0, f"Expected 90.0, got {score_gaps}"
    print("Test 2 Passed: Schedule with 2 gaps scored 90.0")
    
    print("All calculate_gap_score tests passed!")
