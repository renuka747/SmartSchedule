import sys
import os
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.core.graph_builder import Session, build_conflict_graph
import json

sessions = [
    Session(id="S1", subject="Math", faculty="F1", division="D1", room="R1"),
    Session(id="S2", subject="Physics", faculty="F2", division="D1", room="R2"),
    Session(id="S3", subject="Chemistry", faculty="F1", division="D2", room="R3"),
    Session(id="S4", subject="Biology", faculty="F3", division="D3", room="R1"),
    Session(id="S5", subject="History", faculty="F4", division="D4", room="R4"),
]

graph = build_conflict_graph(sessions)
print(json.dumps(graph, indent=2))
