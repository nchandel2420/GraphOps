
from falkordb import FalkorDB

db = FalkorDB(host="localhost", port=6379)
graph = db.select_graph("graphops")

result = graph.query("""
MATCH (n)
RETURN labels(n) AS labels, n.name AS name, n.id AS id
LIMIT 20
""")

print("Records found:", len(result.result_set))

for row in result.result_set:
    print(row)
