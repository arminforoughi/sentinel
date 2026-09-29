"""Dependency graph: Neo4j when configured, deterministic in-memory fallback otherwise.
Both back the same API so the agent never cares which is live."""
from __future__ import annotations

import asyncio
from collections import deque

from . import config
from .topology import SERVICES, EDGES
from .state import store


class MemoryGraph:
    source = "memory"

    def __init__(self):
        self.nodes = {s["name"]: dict(s) for s in SERVICES}
        self.out: dict[str, set] = {n: set() for n in self.nodes}      # depends on
        self.inn: dict[str, set] = {n: set() for n in self.nodes}      # depended on by
        for a, b in EDGES:
            self.out[a].add(b)
            self.inn[b].add(a)

    def upstream(self, name: str, depth: int = 5) -> list[dict]:
        """Services that (transitively) depend on `name` — the blast radius."""
        seen, q, out = {name}, deque([(name, 0)]), []
        while q:
            cur, d = q.popleft()
            if d >= depth:
                continue
            for u in sorted(self.inn.get(cur, ())):
                if u not in seen:
                    seen.add(u)
                    out.append({"name": u, "hops": d + 1})
                    q.append((u, d + 1))
        return out

    def downstream(self, name: str) -> list[str]:
        return sorted(self.out.get(name, ()))

    def export(self) -> dict:
        return {
            "source": self.source,
            "nodes": list(self.nodes.values()),
            "edges": [{"source": a, "target": b} for a, b in EDGES],
        }


class Neo4jGraph(MemoryGraph):
    source = "neo4j"

    def __init__(self, driver):
        super().__init__()
        self.driver = driver
        self.db = config.NEO4J_DATABASE

    def seed(self):
        with self.driver.session(database=self.db) as s:
            s.run("MERGE (:_Sentinel {id: 1})")
            for svc in SERVICES:
                s.run(
                    "MERGE (n:Service {name:$name}) SET n += $props",
                    name=svc["name"],
                    props={k: v for k, v in svc.items() if k != "name"},
                )
            for a, b in EDGES:
                s.run(
                    "MATCH (a:Service {name:$a}),(b:Service {name:$b}) MERGE (a)-[:DEPENDS_ON]->(b)",
                    a=a, b=b,
                )

    def upstream(self, name: str, depth: int = 5) -> list[dict]:
        try:
            with self.driver.session(database=self.db) as s:
                rows = s.run(
                    "MATCH p=(u:Service)-[:DEPENDS_ON*1..%d]->(t:Service {name:$name}) "
                    "WITH u, min(length(p)) AS hops RETURN u.name AS name, hops ORDER BY hops, name" % depth,
                    name=name,
                ).data()
            return [{"name": r["name"], "hops": r["hops"]} for r in rows]
        except Exception as e:  # fall back but keep serving
            store.log("warn", "neo4j", f"query failed, using memory graph: {e}")
            return super().upstream(name, depth)

    def cypher(self, query: str, params: dict | None = None) -> list[dict]:
        with self.driver.session(database=self.db) as s:
            return s.run(query, **(params or {})).data()


graph: MemoryGraph = MemoryGraph()


async def init_graph():
    global graph
    if not config.NEO4J_URI:
        store.set_integration("neo4j", status="fallback", detail="NEO4J_URI not set — in-memory graph", calls=0)
        store.log("info", "graph", "Using in-memory dependency graph (set NEO4J_URI for Neo4j)")
        return
    try:
        from neo4j import GraphDatabase

        def connect():
            drv = GraphDatabase.driver(config.NEO4J_URI, auth=(config.NEO4J_USERNAME, config.NEO4J_PASSWORD))
            drv.verify_connectivity()
            g = Neo4jGraph(drv)
            g.seed()
            return g

        graph = await asyncio.to_thread(connect)
        store.set_integration("neo4j", status="connected", detail=config.NEO4J_URI, calls=0)
        store.log("info", "graph", f"Neo4j connected and seeded ({len(SERVICES)} services, {len(EDGES)} edges)")
    except Exception as e:
        store.set_integration("neo4j", status="error", detail=str(e)[:160], calls=0)
        store.log("error", "graph", f"Neo4j unavailable ({e}); using in-memory graph")


def blast_radius(service: str) -> tuple[list[dict], str]:
    res = graph.upstream(service, depth=int(store.policy.get("blast_depth", 5)))
    integ = store.integrations.get("neo4j", {})
    if graph.source == "neo4j":
        store.set_integration("neo4j", calls=integ.get("calls", 0) + 1)
    return res, graph.source
