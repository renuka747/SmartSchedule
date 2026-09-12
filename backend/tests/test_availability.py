import pytest
from app.constraints.availability import (
    TimeSlot, is_faculty_available, is_room_available, 
    book, unbook, SlotAlreadyBookedError
)

@pytest.fixture
def empty_state():
    return {}, {}

@pytest.fixture
def slot_1():
    return TimeSlot(day="Monday", start_time="09:00")

@pytest.fixture
def slot_2():
    return TimeSlot(day="Monday", start_time="10:00")

def test_initial_availability(empty_state, slot_1):
    booked_faculty, booked_rooms = empty_state
    assert is_faculty_available("Dr. Smith", slot_1, booked_faculty) is True
    assert is_room_available("Room A", slot_1, booked_rooms) is True

def test_successful_booking(empty_state, slot_1):
    booked_faculty, booked_rooms = empty_state
    book("Dr. Smith", "Room A", slot_1, booked_faculty, booked_rooms)
    assert not is_faculty_available("Dr. Smith", slot_1, booked_faculty)
    assert not is_room_available("Room A", slot_1, booked_rooms)

def test_conflict_rejection_faculty(empty_state, slot_1):
    booked_faculty, booked_rooms = empty_state
    book("Dr. Smith", "Room A", slot_1, booked_faculty, booked_rooms)
    
    with pytest.raises(SlotAlreadyBookedError) as exc_info:
        book("Dr. Smith", "Room B", slot_1, booked_faculty, booked_rooms)
        
    assert "Dr. Smith is already booked" in str(exc_info.value)
    # Ensure room was unharmed
    assert "Room B" not in booked_rooms or slot_1 not in booked_rooms.get("Room B", set())

def test_conflict_rejection_room(empty_state, slot_1):
    booked_faculty, booked_rooms = empty_state
    book("Dr. Smith", "Room A", slot_1, booked_faculty, booked_rooms)
    
    with pytest.raises(SlotAlreadyBookedError) as exc_info:
        book("Dr. Jones", "Room A", slot_1, booked_faculty, booked_rooms)
        
    assert "Room A is already booked" in str(exc_info.value)
    # Ensure faculty unharmed
    assert "Dr. Jones" not in booked_faculty or slot_1 not in booked_faculty.get("Dr. Jones", set())

def test_successful_unbooking(empty_state, slot_1):
    booked_faculty, booked_rooms = empty_state
    book("Dr. Smith", "Room A", slot_1, booked_faculty, booked_rooms)
    unbook("Dr. Smith", "Room A", slot_1, booked_faculty, booked_rooms)
    
    assert is_faculty_available("Dr. Smith", slot_1, booked_faculty) is True
    assert is_room_available("Room A", slot_1, booked_rooms) is True

def test_idempotent_unbooking(empty_state, slot_2):
    booked_faculty, booked_rooms = empty_state
    
    # 1. Unseen keys (Dr. Who, Room X)
    unbook("Dr. Who", "Room X", slot_2, booked_faculty, booked_rooms)
    
    # 2. Seen keys, but slot was never booked
    booked_faculty["Dr. Smith"] = set()
    booked_rooms["Room A"] = set()
    unbook("Dr. Smith", "Room A", slot_2, booked_faculty, booked_rooms)
    
    # If no exception was raised, it passed (no-op works).
