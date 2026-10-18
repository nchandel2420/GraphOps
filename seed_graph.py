"""
Seed the GraphOps demo graph in FalkorDB.

Prerequisites:
    python -m pip install falkordb

Run:
    python seed_graph.py

Defaults:
    FalkorDB host: localhost
    FalkorDB port: 6379
    Graph name: graphops

You can override the connection with environment variables:
    FALKORDB_HOST, FALKORDB_PORT, FALKORDB_GRAPH
"""

import os
from falkordb import FalkorDB


HOST = os.getenv("FALKORDB_HOST", "localhost")
PORT = int(os.getenv("FALKORDB_PORT", "6379"))
GRAPH_NAME = os.getenv("FALKORDB_GRAPH", "graphops")


def run(graph, query, params=None):
    """Run one Cypher query and return its result."""
    return graph.query(query, params or {})


def seed():
    db = FalkorDB(host=HOST, port=PORT)
    graph = db.select_graph(GRAPH_NAME)

    print(f"Connecting to FalkorDB at {HOST}:{PORT}")
    print(f"Seeding graph: {GRAPH_NAME}")

    # 1) Projects
    projects = [
        {"id": "P1", "name": "Mutual Fund Platform", "description": "Mutual fund investing and SIP workflows"},
        {"id": "P2", "name": "Trading Platform", "description": "Order placement and trading workflows"},
    ]
    for item in projects:
        run(graph, """
            MERGE (n:Project {id: $id})
            SET n.name = $name, n.description = $description
        """, item)

    # 2) Teams
    teams = [
        {"id": "T1", "name": "Payments Team"},
        {"id": "T2", "name": "Mutual Fund Team"},
        {"id": "T3", "name": "Platform Team"},
    ]
    for item in teams:
        run(graph, """
            MERGE (n:Team {id: $id})
            SET n.name = $name
        """, item)

    # 3) People
    people = [
        {"id": "U1", "name": "Aarav", "role": "Payments Engineer"},
        {"id": "U2", "name": "Maya", "role": "Mutual Fund Engineer"},
        {"id": "U3", "name": "Ishita", "role": "Platform Engineer"},
        {"id": "U4", "name": "Kabir", "role": "On-call Engineer"},
    ]
    for item in people:
        run(graph, """
            MERGE (n:Person {id: $id})
            SET n.name = $name, n.role = $role
        """, item)

    # 4) Services
    services = [
        {"id": "S1", "name": "Order API", "status": "healthy", "criticality": "high"},
        {"id": "S2", "name": "Payment Service", "status": "degraded", "criticality": "critical"},
        {"id": "S3", "name": "Payment Gateway", "status": "down", "criticality": "critical"},
        {"id": "S4", "name": "SIP Service", "status": "healthy", "criticality": "high"},
        {"id": "S5", "name": "Notification Service", "status": "healthy", "criticality": "medium"},
        {"id": "S6", "name": "NAV Service", "status": "healthy", "criticality": "high"},
        {"id": "S7", "name": "Authentication Service", "status": "healthy", "criticality": "critical"},
    ]
    for item in services:
        run(graph, """
            MERGE (n:Service {id: $id})
            SET n.name = $name, n.status = $status, n.criticality = $criticality
        """, item)

    # 5) Incidents
    incidents = [
        {
            "id": "I1",
            "title": "Payment Gateway Timeout",
            "status": "resolved",
            "severity": "high",
            "summary": "Requests to the payment gateway timed out, delaying payment confirmations."
        },
        {
            "id": "I2",
            "title": "Payment Latency Spike",
            "status": "open",
            "severity": "critical",
            "summary": "Payment Service latency increased while the payment gateway was unavailable."
        },
        {
            "id": "I3",
            "title": "NAV Refresh Delay",
            "status": "resolved",
            "severity": "medium",
            "summary": "NAV data refresh ran late and temporarily delayed updated NAV visibility."
        },
    ]
    for item in incidents:
        run(graph, """
            MERGE (n:Incident {id: $id})
            SET n.title = $title, n.status = $status,
                n.severity = $severity, n.summary = $summary
        """, item)

    # 6) Decisions / action plans
    decisions = [
        {
            "id": "D1",
            "title": "Restore gateway connectivity",
            "summary": "Restore gateway connectivity, then verify payment success rate and latency."
        },
        {
            "id": "D2",
            "title": "Inspect payment latency",
            "summary": "Inspect payment latency, gateway error rates, and recent deployment changes."
        },
        {
            "id": "D3",
            "title": "Restart NAV refresh worker",
            "summary": "Restart the NAV refresh worker and validate data freshness after recovery."
        },
    ]
    for item in decisions:
        run(graph, """
            MERGE (n:Decision {id: $id})
            SET n.title = $title, n.summary = $summary
        """, item)

    # 7) Relationships: projects contain services
    relationships = [
        ("P1", "S4"), ("P1", "S5"), ("P1", "S6"), ("P1", "S2"),
        ("P2", "S1"), ("P2", "S2"), ("P2", "S7"),
    ]
    for project_id, service_id in relationships:
        run(graph, """
            MATCH (p:Project {id: $project_id}), (s:Service {id: $service_id})
            MERGE (p)-[:CONTAINS]->(s)
        """, {"project_id": project_id, "service_id": service_id})

    # Services depend on other services. Direction:
    # (dependent service)-[:DEPENDS_ON]->(dependency)
    dependencies = [
        ("S1", "S2"),  # Order API depends on Payment Service
        ("S2", "S3"),  # Payment Service depends on Payment Gateway
        ("S4", "S2"),  # SIP Service depends on Payment Service
        ("S4", "S5"),  # SIP Service depends on Notification Service
        ("S1", "S7"),  # Order API depends on Authentication Service
    ]
    for service_id, dependency_id in dependencies:
        run(graph, """
            MATCH (s:Service {id: $service_id}), (d:Service {id: $dependency_id})
            MERGE (s)-[:DEPENDS_ON]->(d)
        """, {"service_id": service_id, "dependency_id": dependency_id})

    # Team ownership
    ownerships = [
        ("T1", "S2"), ("T1", "S3"),
        ("T2", "S4"), ("T2", "S6"),
        ("T3", "S1"), ("T3", "S5"), ("T3", "S7"),
    ]
    for team_id, service_id in ownerships:
        run(graph, """
            MATCH (t:Team {id: $team_id}), (s:Service {id: $service_id})
            MERGE (t)-[:OWNS]->(s)
        """, {"team_id": team_id, "service_id": service_id})

    # People are members of teams
    memberships = [
        ("U1", "T1"), ("U2", "T2"), ("U3", "T3"), ("U4", "T1"),
    ]
    for person_id, team_id in memberships:
        run(graph, """
            MATCH (p:Person {id: $person_id}), (t:Team {id: $team_id})
            MERGE (p)-[:MEMBER_OF]->(t)
        """, {"person_id": person_id, "team_id": team_id})

    # Incidents affect services
    affected = [
        ("I1", "S3"), ("I1", "S2"),
        ("I2", "S2"), ("I2", "S3"),
        ("I3", "S6"),
    ]
    for incident_id, service_id in affected:
        run(graph, """
            MATCH (i:Incident {id: $incident_id}), (s:Service {id: $service_id})
            MERGE (i)-[:AFFECTS]->(s)
        """, {"incident_id": incident_id, "service_id": service_id})

    # Incident action plans / decisions
    incident_decisions = [("I1", "D1"), ("I2", "D2"), ("I3", "D3")]
    for incident_id, decision_id in incident_decisions:
        run(graph, """
            MATCH (i:Incident {id: $incident_id}), (d:Decision {id: $decision_id})
            MERGE (i)-[:RESOLVED_BY]->(d)
        """, {"incident_id": incident_id, "decision_id": decision_id})

    # People who handled incidents
    handlers = [("I1", "U1"), ("I2", "U4"), ("I3", "U2")]
    for incident_id, person_id in handlers:
        run(graph, """
            MATCH (i:Incident {id: $incident_id}), (p:Person {id: $person_id})
            MERGE (i)-[:HANDLED_BY]->(p)
        """, {"incident_id": incident_id, "person_id": person_id})

    # Verify data was written
    print("\n--- Node counts ---")
    for label in ["Project", "Team", "Person", "Service", "Incident", "Decision"]:
        result = run(graph, f"MATCH (n:{label}) RETURN count(n)")
        count = result.result_set[0][0] if result.result_set else 0
        print(f"{label}: {count}")

    result = run(graph, "MATCH ()-[r]->() RETURN count(r)")
    relationship_count = result.result_set[0][0] if result.result_set else 0
    print(f"Relationships: {relationship_count}")

    print("\n--- Sample services ---")
    result = run(graph, """
        MATCH (s:Service)
        RETURN s.id, s.name, s.status
        ORDER BY s.id
    """)
    for row in result.result_set:
        print(f"{row[0]} | {row[1]} | status={row[2]}")

    print("\nSeed complete. The script uses MERGE, so rerunning it will not duplicate")
    print("nodes or relationships with the same IDs and relationship patterns.")


if __name__ == "__main__":
    try:
        seed()
    except Exception as exc:
        print("\nSeed failed.")
        print(f"Error: {exc}")
        print("Check that FalkorDB is running and reachable on localhost:6379.")
        raise
