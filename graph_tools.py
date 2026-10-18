"""
GraphOps: reusable FalkorDB investigation tools.

Install: python -m pip install falkordb
Defaults: FALKORDB_HOST=localhost, FALKORDB_PORT=6379, FALKORDB_GRAPH=graphops
Run demo: python graph_tools.py
"""
import os
from pprint import pprint
from typing import Any

from falkordb import FalkorDB

HOST = os.getenv("FALKORDB_HOST", "localhost")
PORT = int(os.getenv("FALKORDB_PORT", "6379"))
GRAPH_NAME = os.getenv("FALKORDB_GRAPH", "graphops")


def get_graph():
    """Connect to FalkorDB and select the GraphOps graph."""
    db = FalkorDB(host=HOST, port=PORT)
    return db.select_graph(GRAPH_NAME)

def _rows_to_dicts(result, columns: list[str]) -> list[dict[str, Any]]:
    """Convert FalkorDB result rows to dictionaries with readable keys."""
    return [
        {column: row[index] for index, column in enumerate(columns)}
        for row in result.result_set
    ]

def find_impacted_services(service_id: str = "S3", max_hops: int = 5) -> list[dict[str, Any]]:
    """
    Find upstream services that depend on service_id.
    Each dependency_path is evidence showing how a service reaches the target.
    """
    if not isinstance(max_hops, int) or isinstance(max_hops, bool) or not 1 <= max_hops <= 10:
        raise ValueError("max_hops must be an integer between 1 and 10")

    graph = get_graph()
    # max_hops is validated as an integer before being interpolated into Cypher.
    query = f"""
        MATCH path =
            (s:Service)-[:DEPENDS_ON*1..{max_hops}]->
            (failed:Service {{id: $service_id}})
        RETURN
            s.id,
            s.name,
            s.status,
            s.criticality,
            [n IN nodes(path) | n.name],
            length(path)
        ORDER BY length(path) ASC
    """
    result = graph.query(query, {"service_id": service_id})
    return _rows_to_dicts(
        result,
        ["service_id", "service_name", "status", "criticality", "dependency_path", "hops"],
    )


def find_service_owner(service_id: str) -> list[dict[str, Any]]:
    """Return the owning team(s) and the people who belong to each team."""
    graph = get_graph()
    query = """
        MATCH (team:Team)-[:OWNS]->(service:Service {id: $service_id})
        OPTIONAL MATCH (person:Person)-[:MEMBER_OF]->(team)
        RETURN
            service.id,
            service.name,
            team.id,
            team.name,
            person.id,
            person.name,
            person.role
        ORDER BY person.name
    """
    result = graph.query(query, {"service_id": service_id})
    rows = _rows_to_dicts(
        result,
        ["service_id", "service_name", "team_id", "team_name",
         "person_id", "person_name", "person_role"],
    )

    # Group one row per person into one record per owning team.
    owners: dict[tuple[str, str], dict[str, Any]] = {}
    for row in rows:
        key = (row["team_id"], row["team_name"])
        if key not in owners:
            owners[key] = {
                "service_id": row["service_id"],
                "service_name": row["service_name"],
                "team_id": row["team_id"],
                "team_name": row["team_name"],
                "members": [],
            }
        if row["person_id"] is not None:
            member = {
                "id": row["person_id"],
                "name": row["person_name"],
                "role": row["person_role"],
            }
            if member not in owners[key]["members"]:
                owners[key]["members"].append(member)

    return list(owners.values())


def find_previous_incidents(service_id: str) -> list[dict[str, Any]]:
    """Return incidents directly connected to the specified service."""
    graph = get_graph()
    query = """
        MATCH (incident:Incident)-[:AFFECTS]->(service:Service {id: $service_id})
        RETURN
            incident.id,
            incident.title,
            incident.status,
            incident.severity,
            incident.summary
        ORDER BY incident.id
    """
    result = graph.query(query, {"service_id": service_id})
    return _rows_to_dicts(
        result,
        ["incident_id", "title", "status", "severity", "summary"],
    )


def find_previous_decisions(service_id: str) -> list[dict[str, Any]]:
    """Return decisions linked to incidents that affected the specified service."""
    graph = get_graph()
    query = """
        MATCH
            (incident:Incident)-[:AFFECTS]->(service:Service {id: $service_id}),
            (incident)-[:RESOLVED_BY]->(decision:Decision)
        RETURN
            incident.id,
            incident.title,
            incident.status,
            decision.id,
            decision.title,
            decision.summary
        ORDER BY incident.id
    """
    result = graph.query(query, {"service_id": service_id})
    return _rows_to_dicts(
        result,
        ["incident_id", "incident_title", "incident_status",
         "decision_id", "decision_title", "decision_summary"],
    )

def find_projects_for_service(service_id: str) -> list[dict]:
    """Find projects that directly contain a service."""
    graph = get_graph()

    query = """
        MATCH (project:Project)-[:CONTAINS]->(service:Service {id: $service_id})
        RETURN
            project.id AS project_id,
            project.name AS project_name,
            service.id AS service_id,
            service.name AS service_name
        ORDER BY project.name
    """

    result = graph.query(query, {"service_id": service_id})

    return [
        {
            "project_id": row[0],
            "project_name": row[1],
            "service_id": row[2],
            "service_name": row[3],
        }
        for row in result.result_set
    ]



def search_services(search: str) -> list[dict[str, Any]]:
    """Find services by ID, name, partial name, or combined name and ID."""
    graph = get_graph()

    query = """
        MATCH (service:Service)
        RETURN
            service.id AS service_id,
            service.name AS service_name,
            service.status AS status,
            service.criticality AS criticality
        ORDER BY service.name
    """

    result = graph.query(query)

    services = [
        {
            "service_id": row[0],
            "service_name": row[1],
            "status": row[2],
            "criticality": row[3],
        }
        for row in result.result_set
    ]

    search_text = " ".join(search.lower().split())

    if not search_text:
        return []

    # Prefer an exact ID or exact service-name match.
    exact_matches = [
        service for service in services
        if search_text in (
            service["service_id"].lower(),
            service["service_name"].lower(),
        )
    ]

    if exact_matches:
        return exact_matches

    # Support a combined phrase such as "Payment Gateway S3".
    combined_matches = [
        service for service in services
        if service["service_id"].lower() in search_text
        and service["service_name"].lower() in search_text
    ]

    if combined_matches:
        return combined_matches

    # Fall back to partial ID or service-name matching.
    return [
        service for service in services
        if search_text in service["service_id"].lower()
        or search_text in service["service_name"].lower()
        or service["service_name"].lower() in search_text
    ]




def find_services_in_project(project_id: str) -> list[dict[str, Any]]:
    """Find all services directly contained in a project."""
    graph = get_graph()

    query = """
        MATCH (project:Project {id: $project_id})-[:CONTAINS]->(service:Service)
        RETURN
            project.id AS project_id,
            project.name AS project_name,
            service.id AS service_id,
            service.name AS service_name,
            service.status AS status,
            service.criticality AS criticality
        ORDER BY service.name
    """

    result = graph.query(query, {"project_id": project_id})

    return [
        {
            "project_id": row[0],
            "project_name": row[1],
            "service_id": row[2],
            "service_name": row[3],
            "status": row[4],
            "criticality": row[5],
        }
        for row in result.result_set
    ]

def search_projects(project_name: str) -> list[dict]:
    """Find projects by name or ID."""
    graph = get_graph()

    query = """
            MATCH (p:Project)
            WITH p, toLower(trim($search)) AS search_text
            WHERE
                toLower(p.id) = search_text
                OR toLower(p.name) = search_text
                OR (
                    search_text CONTAINS toLower(p.id)
                    AND toLower(p.name) CONTAINS
                        trim(replace(search_text, toLower(p.id), ''))
                )
            RETURN
                p.id AS project_id,
                p.name AS project_name
            ORDER BY p.name
        """

    result = graph.query(query, {"search": project_name})

    return [
        {
            "project_id": row[0],
            "project_name": row[1],
        }
        for row in result.result_set
    ]



def find_projects_affected_by_service(
    service_id: str,
    max_hops: int = 5,
) -> list[dict[str, Any]]:
    """Find projects indirectly affected by a service failure."""
    if not 1 <= max_hops <= 10:
        raise ValueError("max_hops must be between 1 and 10")

    graph = get_graph()

    query = f"""
        MATCH path =
            (project:Project)-[:CONTAINS]->(dependent:Service)
            -[:DEPENDS_ON*1..{max_hops}]->
            (failed:Service {{id: $service_id}})
        RETURN DISTINCT
            project.id AS project_id,
            project.name AS project_name,
            dependent.id AS dependent_service_id,
            dependent.name AS dependent_service_name,
            failed.id AS failed_service_id,
            failed.name AS failed_service_name,
            [node IN nodes(path) |
                coalesce(node.name, node.id)
            ] AS impact_path
        ORDER BY project.name, dependent.name
    """

    result = graph.query(query, {"service_id": service_id})

    return [
        {
            "project_id": row[0],
            "project_name": row[1],
            "dependent_service_id": row[2],
            "dependent_service_name": row[3],
            "failed_service_id": row[4],
            "failed_service_name": row[5],
            "impact_path": row[6],
        }
        for row in result.result_set
    ]

if __name__ == "__main__":
    print(f"Connected graph: {GRAPH_NAME} at {HOST}:{PORT}")
    examples = [
        ("Impacted services for Payment Gateway (S3)", find_impacted_services("S3")),
        ("Owner of Payment Gateway (S3)", find_service_owner("S3")),
        ("Previous incidents affecting Payment Gateway (S3)", find_previous_incidents("S3")),
        ("Previous decisions for incidents affecting Payment Gateway (S3)", find_previous_decisions("S3")),
    ]
    for heading, data in examples:
        print(f"\n--- {heading} ---")
        pprint(data, sort_dicts=False)
