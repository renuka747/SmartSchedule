import pytest
from app.core.graph_builder import Session
from app.constraints.availability import TimeSlot
from app.core.constants import PERIODS, VALID_DAYS
from app.quality.scorer import (
    calculate_gap_score, 
    calculate_balance_score, 
    calculate_utilization_score, 
    score_timetable,
    InvalidTimeSlotError,
    InvalidDayError,
    MissingSessionDataError
)

@pytest.fixture
def fake_sessions():
    return {
        "S1": Session(id="S1", subject="Math", faculty="Dr. Smith", division="DivA", room="R1"),
        "S2": Session(id="S2", subject="Physics", faculty="Dr. Smith", division="DivA", room="R2"),
        "S3": Session(id="S3", subject="Chemistry", faculty="Dr. Jones", division="DivA", room="R3"),
        "S4": Session(id="S4", subject="CS", faculty="Dr. Turing", division="DivB", room="R1"),
        "S5": Session(id="S5", subject="Bio", faculty="Dr. Darwin", division="DivB", room="R2"),
        "S6": Session(id="S6", subject="Math", faculty="Dr. Smith", division="DivB", room="R3"),
    }

# --- GAP TESTS ---
def test_gap_score_back_to_back(fake_sessions):
    tt = {
        "S1": TimeSlot(day="Monday", start_time="09:00"),
        "S2": TimeSlot(day="Monday", start_time="10:00"),
        "S3": TimeSlot(day="Monday", start_time="11:00"),
    }
    assert calculate_gap_score(tt, fake_sessions) == 100.0

def test_gap_score_single_class(fake_sessions):
    tt = {"S1": TimeSlot(day="Tuesday", start_time="09:00")}
    assert calculate_gap_score(tt, fake_sessions) == 100.0

def test_gap_score_real_gaps(fake_sessions):
    tt = {
        "S1": TimeSlot(day="Wednesday", start_time="09:00"), 
        "S2": TimeSlot(day="Wednesday", start_time="12:00"), 
        "S3": TimeSlot(day="Wednesday", start_time="15:00"), 
    }
    assert abs(calculate_gap_score(tt, fake_sessions) - 66.666) < 0.001

def test_gap_score_realistic(fake_sessions):
    tt = {
        "S1": TimeSlot(day="Monday", start_time="09:00"),
        "S2": TimeSlot(day="Monday", start_time="10:00"),
        "S3": TimeSlot(day="Monday", start_time="11:00"),
        "S4": TimeSlot(day="Tuesday", start_time="09:00"),
        "S5": TimeSlot(day="Tuesday", start_time="12:00"),
        "S6": TimeSlot(day="Tuesday", start_time="16:00"), 
    }
    assert abs(calculate_gap_score(tt, fake_sessions) - 88.57) < 0.01

# --- BALANCE TESTS ---
def test_balance_score_empty(fake_sessions):
    assert calculate_balance_score({}, fake_sessions) == 100.0

def test_balance_score_perfect():
    tt = {}
    sessions = {}
    for i, day in enumerate(VALID_DAYS):
        sid = f"SEven_{i}"
        sessions[sid] = Session(id=sid, subject="M", faculty="Fac", division="Div", room="R1")
        tt[sid] = TimeSlot(day=day, start_time="09:00")
    assert calculate_balance_score(tt, sessions) == 100.0

def test_balance_score_worst():
    tt = {}
    sessions = {}
    for i, period_tuple in enumerate(PERIODS):
        sid = f"SWorst_{i}"
        sessions[sid] = Session(id=sid, subject="M", faculty="Fac", division="Div", room="R1")
        tt[sid] = TimeSlot(day="Monday", start_time=period_tuple[1])
    assert abs(calculate_balance_score(tt, sessions) - 0.0) < 0.001

def test_balance_score_mixed():
    tt = {}
    sessions = {}
    for i, day in enumerate(VALID_DAYS):
        sid = f"SEven_{i}"
        sessions[sid] = Session(id=sid, subject="M", faculty="EvenFac", division="EvenDiv", room="R1")
        tt[sid] = TimeSlot(day=day, start_time="09:00")
        
    for i, period_tuple in enumerate(PERIODS):
        sid = f"SWorst_{i}"
        sessions[sid] = Session(id=sid, subject="M", faculty="WorstFac", division="WorstDiv", room="R1")
        tt[sid] = TimeSlot(day="Monday", start_time=period_tuple[1])
        
    assert abs(calculate_balance_score(tt, sessions) - 50.0) < 0.001

# --- UTILIZATION TESTS ---
def test_utilization_score_empty(fake_sessions):
    assert calculate_utilization_score({}, fake_sessions) == 100.0

def test_utilization_score_packed():
    sessions = {
        "S1": Session(id="S1", subject="M", faculty="F", division="D", room="R1"),
        "S2": Session(id="S2", subject="P", faculty="F", division="D", room="R1"),
        "S3": Session(id="S3", subject="C", faculty="F", division="D", room="R1"),
    }
    tt = {
        "S1": TimeSlot(day="Monday", start_time="09:00"),
        "S2": TimeSlot(day="Monday", start_time="10:00"),
        "S3": TimeSlot(day="Monday", start_time="11:00"),
    }
    assert abs(calculate_utilization_score(tt, sessions) - (3/35 * 100.0)) < 0.001

def test_utilization_score_spread():
    sessions = {
        "S1": Session(id="S1", subject="M", faculty="F", division="D", room="R1"),
        "S2": Session(id="S2", subject="P", faculty="F", division="D", room="R2"),
        "S3": Session(id="S3", subject="C", faculty="F", division="D", room="R3"),
    }
    tt = {
        "S1": TimeSlot(day="Monday", start_time="09:00"),
        "S2": TimeSlot(day="Monday", start_time="10:00"),
        "S3": TimeSlot(day="Monday", start_time="11:00"),
    }
    assert abs(calculate_utilization_score(tt, sessions) - (3/105 * 100.0)) < 0.001

def test_utilization_score_one_session():
    sessions = {"S1": Session(id="S1", subject="M", faculty="F", division="D", room="R1")}
    tt = {"S1": TimeSlot(day="Monday", start_time="09:00")}
    assert abs(calculate_utilization_score(tt, sessions) - (1/35 * 100.0)) < 0.001

# --- SCORE TIMETABLE INTEGRATION TESTS ---
def test_score_timetable_valid(fake_sessions):
    tt = {
        "S1": TimeSlot(day="Monday", start_time="09:00"),
        "S2": TimeSlot(day="Monday", start_time="10:00"),
        "S3": TimeSlot(day="Monday", start_time="11:00"),
        "S4": TimeSlot(day="Tuesday", start_time="09:00"),
        "S5": TimeSlot(day="Tuesday", start_time="12:00"),
        "S6": TimeSlot(day="Tuesday", start_time="16:00"), 
    }
    result = score_timetable(tt, list(fake_sessions.values()))
    
    expected_total = (result.gap_score * 0.4) + (result.balance_score * 0.4) + (result.utilization_score * 0.2)
    assert abs(result.total_score - expected_total) < 0.001
    assert abs(result.total_score - 66.10) < 0.01

# --- EXCEPTIONS (Parametrized) ---
def test_invalid_timeslot_error(fake_sessions):
    tt = {"S1": TimeSlot(day="Wednesday", start_time="08:00")}
    with pytest.raises(InvalidTimeSlotError) as exc_info:
        calculate_gap_score(tt, fake_sessions)
    assert "08:00" in str(exc_info.value)

def test_invalid_day_error(fake_sessions):
    tt = {"S1": TimeSlot(day="Saturday", start_time="09:00")}
    with pytest.raises(InvalidDayError) as exc_info:
        calculate_balance_score(tt, fake_sessions)
    assert "Saturday" in str(exc_info.value)

def test_missing_session_data_error(fake_sessions):
    tt = {"S999": TimeSlot(day="Monday", start_time="09:00")}
    with pytest.raises(MissingSessionDataError) as exc_info:
        score_timetable(tt, list(fake_sessions.values()))
    assert "S999" in str(exc_info.value)

@pytest.mark.parametrize("bad_weights, expected_msg", [
    ({"gaps": 0.5, "balance": 0.5, "utilization": 0.5}, "sum to 1.0"),
    ({"gaps": 0.5, "balance": 0.5}, "missing required keys"),
])
def test_weights_validation_errors(fake_sessions, bad_weights, expected_msg):
    tt = {"S1": TimeSlot(day="Monday", start_time="09:00")}
    with pytest.raises(ValueError) as exc_info:
        score_timetable(tt, list(fake_sessions.values()), weights=bad_weights)
    assert expected_msg in str(exc_info.value)
