# Overnight Failure Taxonomy

Every recorded failure is categorized as requested. Absence of a category means no failure of that type was observed in this measurement run.

| Category | Count | Repositories |
|---|---:|---|
| semantic_routing_failure | 0 |  |
| graph_failure | 3 | LangChain, Qdrant, QuixBugs |
| investigation_failure | 0 |  |
| impact_failure | 0 |  |
| build_failure | 0 |  |
| performance_failure | 1 | Atlas self |
| other | 0 |  |

## Details

| Repo | Category | Reason |
|---|---|---|
| QuixBugs | graph_failure | graph has <=1 module or no edges |
| LangChain | graph_failure | graph has <=1 module or no edges |
| Qdrant | graph_failure | graph has <=1 module or no edges |
| Atlas self | performance_failure | per-repository timeout after 2400s |
