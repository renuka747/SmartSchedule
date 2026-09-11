from typing import Dict, List, Tuple
from pydantic import BaseModel

# Type aliases for readability
SessionID = str

class Session(BaseModel):
    """
    Represents a single class session node in our conflict graph.
    Pydantic is used here for data validation and consistency with 
    the rest of the FastAPI models/schemas.
    """
    id: SessionID
    subject: str
    faculty: str
    division: str
    room: str

# Adjacency list type signature:
# Maps a SessionID to a list of tuples containing (ConflictingSessionID, ConflictReasons)
# ConflictReasons will be a list of strings: ["faculty", "room", "division"]
ConflictGraph = Dict[SessionID, List[Tuple[SessionID, List[str]]]]

def conflicts(session_a: Session, session_b: Session) -> List[str]:
    """
    Compares two sessions and returns a list of conflict reasons between
    them (e.g. ["faculty"], ["room", "division"], or [] if no conflict).
    """
    reasons = []
    
    if session_a.faculty == session_b.faculty:
        reasons.append("faculty")
        
    if session_a.room == session_b.room:
        reasons.append("room")
        
    if session_a.division == session_b.division:
        reasons.append("division")
        
    return reasons

def build_conflict_graph(sessions: List[Session]) -> ConflictGraph:
    """
    Takes the full list of sessions and returns the adjacency list
    conflict graph, using conflicts() for each pairwise comparison.
    """
    # Initialize the adjacency list with empty lists for all sessions
    graph: ConflictGraph = {session.id: [] for session in sessions}
    
    n = len(sessions)
    
    # Loop over every unique pair of sessions (no self-loops, no duplicate checks)
    for i in range(n):
        for j in range(i + 1, n):
            session_a = sessions[i]
            session_b = sessions[j]
            
            # FUTURE OPTIMIZATION NOTE: 
            # We are currently doing an O(n^2) brute-force check. 
            # Later, we can group sessions into buckets by faculty/room/division 
            # first, so we only run conflicts() within those specific buckets.
            
            conflict_reasons = conflicts(session_a, session_b)
            if conflict_reasons:
                # Add edge in BOTH directions (undirected graph)
                graph[session_a.id].append((session_b.id, conflict_reasons))
                graph[session_b.id].append((session_a.id, conflict_reasons))
                
    return graph
if __name__ == "__main__":
    # Setup 5 test sessions
    sessions = [
        Session(id="S1", subject="Math", faculty="F1", division="D1", room="R1"),
        # S2 conflicts with S1 on division (D1)
        Session(id="S2", subject="Physics", faculty="F2", division="D1", room="R2"),
        # S3 conflicts with S1 on faculty (F1)
        Session(id="S3", subject="Chemistry", faculty="F1", division="D2", room="R3"),
        # S4 conflicts with S1 on room (R1)
        Session(id="S4", subject="Biology", faculty="F3", division="D3", room="R1"),
        # S5 is completely isolated, no conflicts
        Session(id="S5", subject="History", faculty="F4", division="D4", room="R4"),
    ]

    graph = build_conflict_graph(sessions)

    import json
    print(json.dumps(graph, indent=2))

    # PREDICTIONS TO VERIFY BY HAND:
    # S1 should have edges to S2 (division), S3 (faculty), and S4 (room).
    # S2, S3, and S4 should each have exactly 1 edge pointing back to S1.
    # S2, S3, S4 should NOT conflict with each other.
    # S5 should have an empty list [].