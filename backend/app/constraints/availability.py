"""
SmartSchedule Availability Constraint Engine.

Design Decisions:
1. "Track Booked, Not Free": Instead of pre-populating a massive grid of all possible
   free slots, we only track what is currently booked. Availability is determined by
   the absence of a booking. This provides O(1) average time complexity lookups
   via hash sets while drastically reducing memory footprint.

2. Asymmetric Enforcement (Strict Book vs. Lenient Unbook):
   - `book()` is strict and raises a `SlotAlreadyBookedError` on conflicts. A silent
     overwrite here would result in a physical impossibility (double booking a room
     or faculty), compromising the entire schedule.
   - `unbook()` is lenient and idempotent (silent no-op if the slot wasn't booked).
     This design simplifies cleanup and rollback routines in speculative algorithms
     (like a backtracking repair engine), where ensuring a "clean slate" is more
     important than perfectly tracking every speculative application.
"""

from typing import Dict, Set
from pydantic import BaseModel, ConfigDict

class TimeSlot(BaseModel):
    day: str          # e.g., "Monday"
    start_time: str   # e.g., "09:00"

    model_config = ConfigDict(frozen=True)   # hashable, for use in sets/dict keys

FacultyID = str
RoomID = str

BookedFaculty = Dict[FacultyID, Set[TimeSlot]]
BookedRooms = Dict[RoomID, Set[TimeSlot]]

def is_faculty_available(faculty_id: FacultyID, slot: TimeSlot, booked: BookedFaculty) -> bool:
    """
    Checks if a faculty member is available at a given time slot.
    Returns True if the faculty_id has no session at that slot, False otherwise.
    """
    if faculty_id not in booked:
        return True
    
    return slot not in booked[faculty_id]

def is_room_available(room_id: RoomID, slot: TimeSlot, booked: BookedRooms) -> bool:
    """
    Checks if a room is available at a given time slot.
    Returns True if the room_id has no session at that slot, False otherwise.
    """
    if room_id not in booked:
        return True
    
    return slot not in booked[room_id]

class SlotAlreadyBookedError(Exception):
    """Raised when attempting to book a faculty or room that's already occupied at the given slot."""
    pass

def book(faculty_id: FacultyID, room_id: RoomID, slot: TimeSlot, booked_faculty: BookedFaculty, booked_rooms: BookedRooms) -> None:
    """
    Attempts to book a faculty and room for a specific time slot.
    Raises SlotAlreadyBookedError if either resource is already taken.
    """
    # 1. Check availability FIRST
    if not is_faculty_available(faculty_id, slot, booked_faculty):
        raise SlotAlreadyBookedError(f"{faculty_id} is already booked at {slot.day} {slot.start_time}")
        
    if not is_room_available(room_id, slot, booked_rooms):
        raise SlotAlreadyBookedError(f"{room_id} is already booked at {slot.day} {slot.start_time}")
        
    # 2. Mutate state ONLY AFTER both checks pass
    if faculty_id not in booked_faculty:
        booked_faculty[faculty_id] = set()
    booked_faculty[faculty_id].add(slot)
    
    if room_id not in booked_rooms:
        booked_rooms[room_id] = set()
    booked_rooms[room_id].add(slot)

def unbook(faculty_id: FacultyID, room_id: RoomID, slot: TimeSlot, booked_faculty: BookedFaculty, booked_rooms: BookedRooms) -> None:
    """
    Removes a booked slot for a faculty and room.
    This operation is idempotent: it silently no-ops if the slot wasn't booked.
    """
    if faculty_id in booked_faculty:
        booked_faculty[faculty_id].discard(slot)
        
    if room_id in booked_rooms:
        booked_rooms[room_id].discard(slot)

if __name__ == "__main__":
    # --- Consolidated Manual Tests ---
    print("Running availability module tests...")

    # Setup state
    slot_1 = TimeSlot(day="Monday", start_time="09:00")
    slot_2 = TimeSlot(day="Monday", start_time="10:00")
    
    booked_faculty: BookedFaculty = {}
    booked_rooms: BookedRooms = {}

    # Test 1: Initial Availability
    assert is_faculty_available("Dr. Smith", slot_1, booked_faculty) == True
    assert is_room_available("Room A", slot_1, booked_rooms) == True
    print("Test 1 Passed: Initial availability correct.")

    # Test 2: Successful Booking
    book("Dr. Smith", "Room A", slot_1, booked_faculty, booked_rooms)
    assert not is_faculty_available("Dr. Smith", slot_1, booked_faculty)
    assert not is_room_available("Room A", slot_1, booked_rooms)
    print("Test 2 Passed: Successful booking updates availability.")

    # Test 3: Conflict Rejection (Faculty)
    try:
        book("Dr. Smith", "Room B", slot_1, booked_faculty, booked_rooms)
        assert False, "Should have raised exception"
    except SlotAlreadyBookedError as e:
        assert "Dr. Smith is already booked" in str(e)
        assert "Room B" not in booked_rooms or slot_1 not in booked_rooms.get("Room B", set())
        print("Test 3 Passed: Caught faculty conflict, room unharmed.")

    # Test 4: Conflict Rejection (Room)
    try:
        book("Dr. Jones", "Room A", slot_1, booked_faculty, booked_rooms)
        assert False, "Should have raised exception"
    except SlotAlreadyBookedError as e:
        assert "Room A is already booked" in str(e)
        assert "Dr. Jones" not in booked_faculty or slot_1 not in booked_faculty.get("Dr. Jones", set())
        print("Test 4 Passed: Caught room conflict, faculty unharmed.")

    # Test 5: Successful Unbooking
    unbook("Dr. Smith", "Room A", slot_1, booked_faculty, booked_rooms)
    assert is_faculty_available("Dr. Smith", slot_1, booked_faculty)
    assert is_room_available("Room A", slot_1, booked_rooms)
    print("Test 5 Passed: Successful unbooking restores availability.")

    # Test 6: Idempotent Unbooking (Unseen keys and unbooked slots)
    # Dr. Who and Room X have never been seen.
    unbook("Dr. Who", "Room X", slot_2, booked_faculty, booked_rooms)
    # Dr. Smith and Room A exist, but slot_2 was never booked for them.
    unbook("Dr. Smith", "Room A", slot_2, booked_faculty, booked_rooms)
    print("Test 6 Passed: Unbooking unseen keys or unbooked slots safely no-ops.")

    print("All tests passed successfully!")
