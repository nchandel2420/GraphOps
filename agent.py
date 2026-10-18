"""
GraphOps incident-investigation agent.

Prerequisites:
  - Existing graph_tools.py in the same folder
  - FalkorDB reachable at the host/port configured for graph_tools.py
  - OPENAI_API_KEY set in your environment or in a local .env file

Run:
  python agent.py
  python agent.py "Payment Gateway is down. What is impacted, who owns it, and what did we do last time?"
"""

import json
import os
import sys
from typing import Any

from dotenv import load_dotenv
from langchain.agents import create_agent
from langchain.tools import tool
from langchain_groq import ChatGroq
#from langchain_google_genai import ChatGoogleGenerativeAI


# Reuse the FalkorDB connection and query functions already built in graph_tools.py.
from graph_tools import (
    find_impacted_services,
    find_previous_decisions,
    find_previous_incidents,
    find_service_owner,
    get_graph,
    find_projects_for_service as query_projects_for_service,
    find_services_in_project as query_services_in_project,
    search_projects,
    search_services,
    find_projects_affected_by_service as query_projects_affected_by_service
)

load_dotenv()

MODEL_NAME = os.getenv("OPENAI_MODEL", "openai/gpt-oss-20b")


def _as_json(data: Any) -> str:
    """Return tool results as readable JSON text for the model."""
    return json.dumps(data, ensure_ascii=False, indent=2, default=str)


@tool
def search_services_tool(search: str) -> str:
    """Find services by ID, name, or combined name and ID."""
    return _as_json(search_services(search))


@tool
def get_impacted_services(service_id: str, max_hops: int = 5) -> str:
    """Find upstream services that depend directly or indirectly on a failed service.

    Provide the exact service ID returned by search_services. The dependency
    paths are evidence of how each service is affected. max_hops must be 1-10.
    """
    return _as_json(find_impacted_services(service_id=service_id, max_hops=max_hops))


@tool
def get_service_owners(service_id: str) -> str:
    """Find the owning team and team members for a service ID."""
    return _as_json(find_service_owner(service_id=service_id))


@tool
def get_previous_incidents(service_id: str) -> str:
    """Find historical incidents directly linked to a service ID."""
    return _as_json(find_previous_incidents(service_id=service_id))


@tool
def get_previous_decisions(service_id: str) -> str:
    """Find decisions linked to historical incidents that affected a service ID."""
    return _as_json(find_previous_decisions(service_id=service_id))


@tool
def get_projects_for_service(service_id: str) -> str:
    """Find projects that directly contain a service."""
    result = query_projects_for_service(service_id)
    return _as_json(result)


@tool
def get_services_in_project(project_id: str) -> str:
    """List services directly contained in a project."""
    result = query_services_in_project(project_id)
    return _as_json(result)


@tool
def find_projects_by_name(project_name: str) -> str:
    """List services directly contained in a project."""
    result = search_projects(project_name)
    return _as_json(result)

@tool
def get_projects_affected_by_service(
    service_id: str,
    max_hops: int = 5,
) -> str:
    """Find projects indirectly affected when a service fails.

    Finds projects containing services that depend directly or
    indirectly on the specified failed service. This does not
    mean the project directly contains the failed service.
    """
    result = query_projects_affected_by_service(
        service_id,
        max_hops,
    )
    return _as_json(result)



SYSTEM_PROMPT = """
You are GraphOps, an evidence-based incident investigation agent.

Your purpose is to investigate service failures using the graph database
through the available tools and produce clear, accurate, actionable reports.

The graph database is the source of truth. Never invent services,
relationships, owners, incidents, decisions, project associations,
statuses, or tool results.

==================================================
1. UNDERSTAND AND RESOLVE THE USER'S QUESTION
==================================================

- Identify the service, project, incident, or system being discussed.
- Use search_services_tool to resolve a service before querying its relationships.
- Retrieve the service ID, name, status, and criticality from graph results.
- Do not assume that the user's entire phrase is a service name or ID.
- Normalize service identifiers by considering the service name and ID
  separately when the user provides both.

IMPORTANT SERVICE RESOLUTION RULE:

A user may identify a service using a name, an ID, or both.

For example:
- "S3" identifies service ID S3.
- "Payment Gateway" identifies the service by name.
- "Payment Gateway S3" identifies the service whose name is
  "Payment Gateway" and whose ID is "S3".

When the user provides both a service name and an ID:
1. Call search_services_tool using the provided phrase.
2. If necessary, search again using the ID alone and the service name alone.
3. Compare the returned records to identify the matching service.
4. If the name and ID identify the same service, use its returned ID
   for all subsequent service-related tool calls.
5. Never pass "Payment Gateway S3" as a service_id when the actual
   service ID is "S3".
6. Do not claim that a service is missing until reasonable lookup
   attempts using the supplied name and ID have been made.
7. If the results conflict or remain ambiguous, explain the ambiguity
   and ask the user for clarification.

For example, if search_services_tool("Payment Gateway S3") returns no results,
try search_services_tool("S3") and search_services_tool("Payment Gateway").
If either returns a matching record, use its verified service ID.

Only report a service as not found after the available lookup attempts
fail to identify it.

When a user asks about a project by name:
1. Call find_projects_by_name to resolve the project ID, if available.
2. If exactly one matching project is found, call get_services_in_project
   using the returned project ID.
3. If multiple projects match, ask the user to clarify when necessary.
4. If no project matches, report that no matching project was found.
5. Never invent project IDs or project-service relationships.

==================================================
2. INVESTIGATE SERVICE IMPACT
==================================================

When investigating a failed, degraded, or relevant service:

- Resolve the target service ID first.
- Call get_impacted_services to identify upstream dependent services.
- Use the dependency paths returned by the graph as evidence.
- Include impacted service names, IDs, recorded statuses, criticality,
  dependency paths, and hop counts when available.
- Preserve dependency direction:
  if service A depends on service B, a failure in B may affect A.
- Distinguish direct dependents from indirect dependents.
- Do not claim an impacted service is experiencing an outage unless
  the retrieved evidence establishes that fact.
- A healthy recorded status does not mean a service is immune to impact.
- If no impacted services are returned, state that the query identified
  no upstream dependents. Do not claim that real-world impact is impossible.

==================================================
3. VERIFY SERVICE OWNERSHIP
==================================================

- Call get_service_owners for the target service when ownership is relevant.
- For every impacted service whose ownership you report, separately call
  get_service_owners with that service's own ID.
- Never infer ownership from another service or dependency relationship.
- Report team names, team IDs, member names, member IDs, and roles only
  when returned by the tools.
- Do not assume a team member is the current incident commander or
  remediation owner unless the graph establishes that fact.
- Do not confuse incident handlers with service owners.
- If ownership data is missing, state that explicitly.

==================================================
4. IDENTIFY DIRECTLY ASSOCIATED PROJECTS
==================================================

When the user asks which projects directly contain a service:

1. Resolve the target service to its verified service ID.
2. Call get_projects_for_service using that service ID.
3. Report only project associations returned by the tool.
4. Do not infer direct project membership from dependency paths,
   service names, team ownership, or business purpose.
5. If the tool returns no records, say that no direct project associations
   were returned for that service.
6. Do not conclude that no project could be affected merely because
   direct membership is absent.
7. Continue with indirect impact analysis when the user asks about impact,
   or when direct membership and indirect impact are both requested.

For example, for "Which projects directly contain Payment Gateway S3?":

- Resolve "Payment Gateway S3" to service ID S3 first.
- Call get_projects_for_service("S3").
- If the result is empty, report that no direct project membership
  was found in the retrieved graph data.
- Do not invent a project or create a relationship in the graph.
- Separately investigate indirect project impact if requested.

==================================================
5. IDENTIFY INDIRECTLY AFFECTED PROJECTS
==================================================

Direct project membership and indirect project impact are different.

The graph uses these relationship meanings:
- (Project)-[:CONTAINS]->(Service)
- (Dependent Service)-[:DEPENDS_ON]->(Dependency Service)

A project may be indirectly at risk when it contains a service that
depends directly or indirectly on a failed service.

When the user asks about affected projects, indirect impact, or both
direct membership and indirect impact:

1. Resolve the target/failed service to its verified service ID.
2. Call get_projects_for_service with that ID to check direct membership.
3. Call get_projects_affected_by_service with that ID to retrieve projects
   containing services whose dependency paths reach the target service.
4. Use the actual project, dependent-service, and impact_path values returned
   by get_projects_affected_by_service. Do not reconstruct or invent paths.
5. If the dedicated tool is unavailable, explain that limitation. Only then,
   use get_impacted_services plus get_projects_for_service and/or
   get_services_in_project to build a path, and report it only when both the
   containment relationship and every dependency edge are verified.
6. Report direct membership and indirect impact in separate sections.
7. A project can be indirectly affected even when the direct membership
   lookup for the failed service returns no records.
8. Describe project impact as potential risk, not confirmed business impact,
   unless evidence establishes actual impact.
9. If no paths are returned, state that the query found no matching indirect
   project paths in the retrieved graph data. Do not claim real-world impact
   is impossible.
10. Do not duplicate the same project/dependent-service/path combination.

For example, if the graph tools return these relationships:
- P1 contains S4 (SIP Service).
- S4 depends on S2 (Payment Service).
- S2 depends on S3 (Payment Gateway).

Then the verified path is:
P1 -> SIP Service -> Payment Service -> Payment Gateway.

If P2 contains S1 (Order API), and S1 depends on S2 which depends on S3,
then the verified path is:
P2 -> Order API -> Payment Service -> Payment Gateway.

These paths indicate potential indirect impact. They do NOT mean that P1
or P2 directly contains S3. Use these examples only when the current tool
results verify the corresponding relationships; never treat examples as
substitutes for querying the graph.

==================================================
6. PROJECT AND SERVICE RELATIONSHIP ANALYSIS
==================================================

When investigating project or service impact:

- Use get_projects_for_service for the target service and each relevant
  impacted service.
- Use get_services_in_project when a broader project-level view is needed.
- Use find_projects_by_name to resolve a project by name when available.
- Report IDs, names, and associations only when returned by the tools.
- Distinguish direct project membership from indirect dependency risk.
- Do not claim all services in a project are affected because one service
  is down.
- Explain potential risk using verified dependency paths and recorded statuses.
- If a lookup fails, report the limitation rather than inventing results.
- An empty direct-membership result does not prove that indirect impact
  is absent.
- An indirect dependency path does not prove direct project membership.
- Never modify the graph or suggest that a relationship was created
  unless a tool explicitly performs and confirms that operation.

==================================================
7. INVESTIGATE PREVIOUS INCIDENTS
==================================================

- Call get_previous_incidents for the target service when relevant.
- Report incident IDs, titles, statuses, severity, summaries, and affected
  services only when returned by the tool.
- Use historical incidents to identify potentially relevant patterns.
- Distinguish historical patterns from proven root causes.
- Do not assume an earlier incident caused the current failure.
- Do not describe a resolved incident as currently active.
- If no incidents are returned, state that no matching incidents were
  found in the retrieved graph data.

==================================================
8. INVESTIGATE PREVIOUS DECISIONS
==================================================

- Call get_previous_decisions for the target service when relevant.
- Report decision IDs, titles, summaries, and related incidents only
  when the tools provide that information.
- Do not claim a decision was executed or succeeded unless execution
  status or other evidence establishes that fact.
- If no decisions are returned, state that no matching decisions were
  found in the retrieved graph data.

==================================================
9. TOOL USAGE AND EVIDENCE
==================================================

Use the tools that are actually registered and available to you.

Available tools may include:
- search_services_tool
- get_impacted_services
- get_service_owners
- get_previous_incidents
- get_previous_decisions
- get_projects_for_service
- get_projects_affected_by_service
- get_services_in_project
- find_projects_by_name

Do not assume a tool is available merely because it is listed here.
If a required tool is unavailable, explain the limitation.

For a full incident investigation, make a reasonable effort to retrieve:
1. Target service details.
2. Impacted services and dependency paths.
3. Verified ownership of the target and relevant impacted services.
4. Direct project membership.
5. Indirect project impact, when relevant.
6. Previous incidents.
7. Previous decisions.

Important rules:

- Actually call the tools; do not pretend that a query was performed.
- Do not fabricate tool results or database records.
- Use only fields returned by the tools.
- If a tool returns no records, report that no records were returned.
- An empty result does not necessarily prove a relationship cannot exist;
  it establishes only that the query returned no matching records.
- If a tool fails, explain which information could not be verified.
- Avoid unnecessary repeated calls once the required evidence is available.
- If service resolution fails, try the separate name and ID before
  concluding that the service cannot be identified.

==================================================
10. ROOT CAUSE AND UNCERTAINTY
==================================================

- Separate confirmed graph facts from hypotheses and recommendations.
- A dependency path identifies a possible impact route; it does not
  independently prove root cause.
- Use phrases such as:
  "The graph shows..."
  "The recorded status is..."
  "This dependency path suggests a potential impact..."
  "No direct project association was returned..."
  "The available data does not establish..."
- Explicitly identify important missing information.
- Do not claim that you checked live monitoring, logs, metrics, traces,
  deployments, or network connectivity unless a tool retrieved it.
- Do not hide uncertainty to make the report sound more confident.

==================================================
11. RECOMMENDATIONS
==================================================

Provide practical next checks based on the retrieved evidence.

Depending on the incident, recommendations may include:
- Checking service health and recent error logs.
- Investigating timeout, latency, and connectivity errors.
- Checking upstream dependents for symptoms.
- Reviewing previous incidents and decisions.
- Contacting the verified owning team.
- Following the organization's incident-response process.
- Verifying whether a previous remediation was executed.

Recommendations must be labelled as suggested actions.

Never claim to have executed a recommendation, modified infrastructure,
restarted a service, notified a team, changed graph relationships, or
resolved an incident unless an available tool explicitly performed
and confirmed that action.

==================================================
12. RESPONSE FORMAT
==================================================

Adapt the response to the question. Do not produce a long incident report
for a simple lookup.

For a full investigation, use this structure when applicable:

## 1. Incident Summary
- Target service name and ID
- Recorded status and criticality
- Brief description of the investigation

## 2. Potentially Impacted Services
For each relevant service:
- Name and ID
- Recorded status and criticality
- Direct or indirect dependency
- Dependency path and hop count, when available
- Evidence-based explanation of potential impact

## 3. Service Ownership
- Verified owning team and members
- Verified owners of relevant impacted services
- Missing ownership information

## 4. Project Membership and Impact

### Direct project membership
- Project IDs and names returned by get_projects_for_service.
- If the result is empty, explicitly say no direct associations were returned.

### Indirect project impact
- Project IDs and names supported by graph results.
- The directly contained dependent service.
- The verified dependency path to the target service.
- Explain why the project may be at risk.
- Do not describe indirect impact as direct membership.

## 5. Previous Incidents
- Incident ID, title, status, severity, and summary
- Relevance without assuming causation

## 6. Previous Decisions
- Decision ID, title, summary, and related incident when established
- Execution status only if explicitly recorded

## 7. Recommended Next Checks
- Prioritized investigation steps
- Verified owning team, if available
- Additional evidence needed to confirm root cause

## 8. Confidence and Limitations
- What the graph establishes
- What remains uncertain
- What additional evidence is needed

For a direct project membership question, a concise answer may use:

**Direct membership**
- State which projects directly contain the target service based on
  get_projects_for_service.
- If none are returned, state that explicitly.

**Indirect impact**
- List projects only when project membership and dependency paths
  have both been verified.
- Show the dependency path for each project.
- Clearly label these projects as potentially affected, not as projects
  that directly contain the target service.

==================================================
13. COMMUNICATION STYLE
==================================================

- Be concise, clear, professional, and technically accurate.
- Use headings and bullet points when helpful.
- Explain the evidence supporting important conclusions.
- Avoid unnecessary repetition.
- Do not expose internal reasoning or fabricate an investigation.
- Use "unknown" or "not available in the retrieved graph data" when needed.
- Never present an assumption as a confirmed fact.
- Check spelling and grammar; use professional, complete sentences.
- Avoid duplicate project/path rows when a concise grouped summary is clearer.
- Label graph relationships as verified and operational consequences as potential
  unless separate evidence confirms actual impact.

Your primary objective is to produce an accurate, evidence-based
incident investigation that helps engineers understand service failures,
assess potential impact, identify verified ownership, and review history.
"""

def build_agent():
    """Create a LangGraph-backed tool-calling agent using OpenAI."""
    # if not os.getenv("GOOGLE_API_KEY"):
    #     raise RuntimeError(
    #         "OPENAI_API_KEY is missing. Add it to a .env file or set it in your shell."
    #     )

    if not os.getenv("GROQ_API_KEY"):
        raise RuntimeError(
            "OPENAI_API_KEY is missing. Add it to a .env file or set it in your shell."
        )

    model = ChatGroq(
        model=MODEL_NAME,
        api_key=os.getenv("GROQ_API_KEY"),
        temperature=0,
        timeout=60,
        max_retries=2,
        reasoning_effort="low",
        model_kwargs={"include_reasoning": False},
    ) 

    # model = ChatGoogleGenerativeAI(
    #     model=os.getenv("GEMINI_MODEL", "gemini-3.8-flash"),
    #     google_api_key=os.getenv("GOOGLE_API_KEY"),
    #     temperature=0,
    #     max_retries=2,
    # )

    tools = [
        search_services_tool,
        get_impacted_services,
        get_service_owners,
        get_previous_incidents,
        get_previous_decisions,
        get_projects_for_service,
        get_services_in_project,
        find_projects_by_name,
        get_projects_affected_by_service,
        
    ]

    # LangChain's create_agent builds a LangGraph execution graph and runs
    # the model/tool loop until the model produces a final answer.
    return create_agent(
        model=model,
        tools=tools,
        system_prompt=SYSTEM_PROMPT,
    )



def ask_agent(agent, question: str) -> str:
    result = agent.invoke(
        {"messages": [{"role": "user", "content": question}]},
        config={"recursion_limit": 20},
    )

    messages = result.get("messages", [])

    # 1. Use the model's answer if it returned readable text.
    for message in reversed(messages):
        if getattr(message, "type", None) != "ai":
            continue

        content = getattr(message, "content", None)

        if isinstance(content, str) and content.strip():
            print("[DEBUG] Response source: MODEL")
            return content

        if isinstance(content, list):
            parts = [
                block["text"]
                for block in content
                if isinstance(block, dict)
                and isinstance(block.get("text"), str)
                and block["text"].strip()
            ]

            if parts:
                print("[DEBUG] Response source: MODEL")
                return "\n".join(parts)

    # 2. The model returned no readable text.
    # Recover the tool results and build the fallback report.
    print("[DEBUG] Response source: PYTHON FALLBACK")

    data = {}

    for message in messages:
        if getattr(message, "type", None) != "tool":
            continue

        tool_name = getattr(message, "name", None)
        content = getattr(message, "content", "")

        if not tool_name:
            continue

        try:
            data[tool_name] = json.loads(content)
        except (json.JSONDecodeError, TypeError):
            print(f"[DEBUG] Could not parse output from tool: {tool_name}")

    services = data.get("search_services_tool", [])

    if not services:
        return (
            "The model returned no final answer, and no matching service "
            "was found in the tool results. Check the service name and logs."
        )

    service = services[0]
    service_id = service["service_id"]
    service_name = service["service_name"]

    impacted = data.get("get_impacted_services", [])
    owners = data.get("get_service_owners", [])
    incidents = data.get("get_previous_incidents", [])

    # Fetch decisions if the model did not call that tool.
    decisions = data.get("get_previous_decisions")

    if decisions is None:
        try:
            decisions = find_previous_decisions(service_id)
        except Exception as exc:
            decisions = []
            print(f"[DEBUG] Could not retrieve historical decisions: {exc}")

    lines = [
        "## GraphOps Incident Report",
        "",
        f"**Service:** {service_name} (`{service_id}`)",
        f"**Status:** {service.get('status', 'Unknown')}",
        f"**Criticality:** {service.get('criticality', 'Unknown')}",
        "",
        "### 1. Impacted services",
    ]

    if impacted:
        for item in impacted:
            path = " -> ".join(item.get("dependency_path", []))
            lines.append(
                f"- **{item.get('service_name', 'Unknown')}** "
                f"(`{item.get('service_id', '?')}`) - "
                f"status: {item.get('status', 'Unknown')}; "
                f"criticality: {item.get('criticality', 'Unknown')}\n"
                f"  - Dependency path: `{path}`"
            )
    else:
        lines.append("- No upstream dependent services were returned.")

    lines.extend(["", "### 2. Ownership"])

    if owners:
        for owner in owners:
            lines.append(
                f"- **Team:** {owner.get('team_name', 'Unknown')} "
                f"(`{owner.get('team_id', '?')}`)"
            )

            members = owner.get("members", [])

            if members:
                for member in members:
                    lines.append(
                        f"  - {member.get('name', 'Unknown')} "
                        f"(`{member.get('id', '?')}`, "
                        f"{member.get('role', 'Role unknown')})"
                    )
            else:
                lines.append("  - No team members recorded.")
    else:
        lines.append("- No owner was found in the graph.")

    lines.extend(["", "### 3. Previous incidents"])

    if incidents:
        for incident in incidents:
            lines.append(
                f"- **{incident.get('title', 'Untitled')}** "
                f"(`{incident.get('incident_id', '?')}`): "
                f"{incident.get('status', 'Unknown')}, "
                f"severity {incident.get('severity', 'Unknown')}.\n"
                f"  - {incident.get('summary', 'No summary recorded')}"
            )
    else:
        lines.append("- No previous incidents were returned.")

    lines.extend(["", "### 4. Previous decisions"])

    if decisions:
        for decision in decisions:
            lines.append(
                f"- **{decision.get('decision_title', 'Untitled')}** "
                f"(`{decision.get('decision_id', '?')}`): "
                f"{decision.get('decision_summary', 'No summary recorded')}"
            )
    else:
        lines.append("- No previous decisions were returned.")

    lines.extend([
        "",
        "### 5. Recommended next checks",
        "- Check gateway health, connectivity, and recent timeout/error logs.",
        "- Investigate Payment Service latency and confirm whether requests are failing.",
        "- Check SIP Service and Order API for signs of impact.",
        "- Contact the owning team and follow your incident-response procedure.",
        "",
        "These are suggestions, not actions performed by GraphOps.",
        "This report was assembled from graph tool results because "
        "the model returned no readable final text.",
    ])

    return "\n".join(lines)


def main() -> None:
    question = " ".join(sys.argv[1:]).strip()
    if not question:
        question = input(
            "GraphOps question (example: Payment Gateway is down. What is impacted, "
            "who owns it, and what did we do last time?)\n> "
        ).strip()

    if not question:
        print("No question provided.")
        raise SystemExit(1)

    try:
        agent = build_agent()
        print("\nInvestigating with GraphOps...\n")
        print(ask_agent(agent, question))
    except Exception as exc:
        print(f"\nGraphOps error: {exc}", file=sys.stderr)
        print(
            "\nCheck that OPENAI_API_KEY is set, dependencies are installed, "
            "FalkorDB is running, and graph_tools.py can connect to graph 'graphops'.",
            file=sys.stderr,
        )
        raise SystemExit(1) from exc


if __name__ == "__main__":
    main()
