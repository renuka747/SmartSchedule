VALID_DAYS = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday"]

# Each period as (label, start_time, end_time). Lunch (13:00-14:00) is
# intentionally excluded — no session can ever be scheduled there.
PERIODS = [
    ("P1", "09:00", "10:00"),
    ("P2", "10:00", "11:00"),
    ("P3", "11:00", "12:00"),
    ("P4", "12:00", "13:00"),
    ("P5", "14:00", "15:00"),
    ("P6", "15:00", "16:00"),
    ("P7", "16:00", "17:00"),
]
