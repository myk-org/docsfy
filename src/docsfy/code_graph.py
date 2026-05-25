"""Code knowledge graph generation using Graphify.

Builds a knowledge graph from a repository's source code before the AI planner
runs. Produces GRAPH_REPORT.md and graph.json in the repo's graphify-out/ directory.
"""

from __future__ import annotations

import asyncio
import json
from pathlib import Path
from typing import Any

from simple_logger.logger import get_logger

from docsfy.ai_client import AIResult, call_ai_once, run_parallel_with_limit

logger = get_logger(name=__name__)

# Graphify's system prompt for semantic extraction (copied from graphify.llm._EXTRACTION_SYSTEM)
_EXTRACTION_SYSTEM = """\
You are a graphify semantic extraction agent. Extract a knowledge graph fragment from the files provided.
Output ONLY valid JSON — no explanation, no markdown fences, no preamble.

Rules:
- EXTRACTED: relationship explicit in source (import, call, citation, reference)
- INFERRED: reasonable inference (shared data structure, implied dependency)
- AMBIGUOUS: uncertain — flag for review, do not omit

Node ID format: lowercase, only [a-z0-9_], no dots or slashes.
Format: {stem}_{entity} where stem = filename without extension, entity = symbol name (both normalised).

Output exactly this schema:
{"nodes":[{"id":"stem_entity","label":"Human Readable Name","file_type":"code|document|paper|image|rationale|concept","source_file":"relative/path","source_location":null,"source_url":null,"captured_at":null,"author":null,"contributor":null}],"edges":[{"source":"node_id","target":"node_id","relation":"calls|implements|references|cites|conceptually_related_to|shares_data_with|semantically_similar_to","confidence":"EXTRACTED|INFERRED|AMBIGUOUS","confidence_score":1.0,"source_file":"relative/path","source_location":null,"weight":1.0}],"hyperedges":[],"input_tokens":0,"output_tokens":0}
"""

# Max chars per file in the extraction prompt (matches graphify's _FILE_CHAR_CAP)
_FILE_CHAR_CAP = 20_000

# Max files per semantic extraction chunk
_CHUNK_SIZE = 20


def _read_files(paths: list[Path], root: Path) -> str:
    """Format file contents for the semantic extraction prompt."""
    logger.debug("Reading %d files for semantic extraction", len(paths))
    parts: list[str] = []
    for p in paths:
        try:
            rel = p.relative_to(root)
        except ValueError:
            rel = p
        # Guard against symlinks escaping the repo directory
        try:
            resolved = p.resolve()
            if not resolved.is_relative_to(root.resolve()):
                logger.warning("Skipping out-of-tree file: %s", p)
                continue
        except (OSError, ValueError):
            continue
        try:
            content = p.read_text(encoding="utf-8", errors="replace")
        except OSError as exc:
            logger.debug("Skipping unreadable file %s: %s", p, exc)
            continue
        parts.append(f"=== {rel} ===\n{content[:_FILE_CHAR_CAP]}")
    return "\n\n".join(parts)


def _parse_llm_json(raw: str) -> dict[str, Any]:
    """Parse JSON from LLM response, stripping markdown fences if present."""
    if raw.startswith("```"):
        raw = raw.split("```", 2)[1]
        if raw.startswith("json"):
            raw = raw[4:]
        raw = raw.rsplit("```", 1)[0]
    try:
        return json.loads(raw.strip())
    except json.JSONDecodeError as exc:
        logger.warning("LLM returned invalid JSON for semantic extraction: %s", exc)
        return {"nodes": [], "edges": [], "hyperedges": []}


async def _extract_semantic_chunk(
    chunk: list[Path],
    root: Path,
    ai_provider: str,
    ai_model: str,
    ai_call_timeout: int | None = None,
) -> dict[str, Any]:
    """Extract semantic nodes/edges from a chunk of files via pi-sidecar."""
    user_message = _read_files(chunk, root)
    if not user_message.strip():
        return {
            "nodes": [],
            "edges": [],
            "hyperedges": [],
            "input_tokens": 0,
            "output_tokens": 0,
        }

    logger.debug(
        "Semantic chunk: %d files, prompt size: %d chars", len(chunk), len(user_message)
    )

    result: AIResult = await call_ai_once(
        user_message,
        ai_provider=ai_provider,
        ai_model=ai_model,
        system_prompt=_EXTRACTION_SYSTEM,
        ai_call_timeout=ai_call_timeout,
    )

    if not result.success:
        logger.warning("Semantic extraction chunk failed: %s", result.text[:200])
        return {
            "nodes": [],
            "edges": [],
            "hyperedges": [],
            "input_tokens": 0,
            "output_tokens": 0,
        }

    if not result.text or not result.text.strip():
        logger.warning(
            "Semantic extraction chunk returned empty text (input_tokens=%d, output_tokens=%d)",
            result.usage.input_tokens if result.usage else 0,
            result.usage.output_tokens if result.usage else 0,
        )
        return {
            "nodes": [],
            "edges": [],
            "hyperedges": [],
            "input_tokens": result.usage.input_tokens if result.usage else 0,
            "output_tokens": result.usage.output_tokens if result.usage else 0,
        }

    parsed = _parse_llm_json(result.text)
    parsed["input_tokens"] = result.usage.input_tokens if result.usage else 0
    parsed["output_tokens"] = result.usage.output_tokens if result.usage else 0
    logger.debug(
        "Semantic chunk result: %d nodes, %d edges",
        len(parsed.get("nodes", [])),
        len(parsed.get("edges", [])),
    )
    return parsed


async def _extract_semantic(
    files: list[Path],
    root: Path,
    ai_provider: str,
    ai_model: str,
    ai_call_timeout: int | None = None,
    max_concurrency: int = 3,
) -> dict[str, Any]:
    """Extract semantic relationships from all files in parallel chunks."""
    if not files:
        return {
            "nodes": [],
            "edges": [],
            "hyperedges": [],
            "input_tokens": 0,
            "output_tokens": 0,
        }

    # Chunk files (group by parent directory for better cross-file detection)
    by_dir: dict[Path, list[Path]] = {}
    for f in files:
        by_dir.setdefault(f.parent, []).append(f)

    chunks: list[list[Path]] = []
    current: list[Path] = []
    for directory in sorted(by_dir):
        for path in by_dir[directory]:
            current.append(path)
            if len(current) >= _CHUNK_SIZE:
                chunks.append(current)
                current = []
    if current:
        chunks.append(current)

    if not chunks:
        return {
            "nodes": [],
            "edges": [],
            "hyperedges": [],
            "input_tokens": 0,
            "output_tokens": 0,
        }

    logger.info("Semantic extraction: %d files in %d chunks", len(files), len(chunks))

    coroutines = [
        _extract_semantic_chunk(chunk, root, ai_provider, ai_model, ai_call_timeout)
        for chunk in chunks
    ]
    results = await run_parallel_with_limit(coroutines, max_concurrency=max_concurrency)

    # Merge all chunk results
    merged: dict[str, Any] = {
        "nodes": [],
        "edges": [],
        "hyperedges": [],
        "input_tokens": 0,
        "output_tokens": 0,
    }
    seen_ids: set[str] = set()
    seen_edges: set[tuple[str, str, str]] = set()
    for idx, r in enumerate(results):
        if isinstance(r, Exception):
            logger.warning("Semantic extraction chunk %d failed: %s", idx, r)
            continue
        for node in r.get("nodes", []):
            nid = node.get("id", "")
            if nid and nid not in seen_ids:
                seen_ids.add(nid)
                merged["nodes"].append(node)
        for edge in r.get("edges", []):
            edge_key = (
                edge.get("source", ""),
                edge.get("target", ""),
                edge.get("relation", ""),
            )
            if edge_key not in seen_edges:
                seen_edges.add(edge_key)
                merged["edges"].append(edge)
        merged["hyperedges"].extend(r.get("hyperedges", []))
        merged["input_tokens"] += r.get("input_tokens", 0)
        merged["output_tokens"] += r.get("output_tokens", 0)

    logger.info(
        "Semantic extraction complete: %d nodes, %d edges from %d chunks",
        len(merged["nodes"]),
        len(merged["edges"]),
        len(chunks),
    )
    return merged


async def _label_communities(
    communities: dict[int, list[str]],
    graph: Any,  # nx.Graph
    ai_provider: str,
    ai_model: str,
    ai_call_timeout: int | None = None,
) -> dict[int, str]:
    """Use AI to label each community with a 2-5 word descriptive name."""
    if not communities:
        return {}

    logger.debug("Labeling %d communities", len(communities))

    # Build a prompt with community node labels
    community_descriptions: list[str] = []
    for cid, nodes in sorted(communities.items()):
        node_labels = []
        for nid in nodes[:15]:  # Cap at 15 nodes per community for prompt size
            data = graph.nodes.get(nid, {})
            label = data.get("label", nid)
            node_labels.append(label)
        community_descriptions.append(f"Community {cid}: {', '.join(node_labels)}")

    prompt = (
        "For each community below, write a 2-5 word plain-language name that describes "
        "what the nodes in that community have in common. "
        "Return a JSON object mapping community ID (as string) to the label.\n\n"
        + "\n".join(community_descriptions)
        + "\n\nRespond with ONLY a JSON object. No explanation."
    )

    result: AIResult = await call_ai_once(
        prompt,
        ai_provider=ai_provider,
        ai_model=ai_model,
        ai_call_timeout=ai_call_timeout,
    )

    if not result.success:
        logger.warning("Community labeling failed: %s", result.text[:200])
        return {cid: f"Community {cid}" for cid in communities}

    if not result.text or not result.text.strip():
        logger.warning("Community labeling returned empty text")
        return {cid: f"Community {cid}" for cid in communities}

    parsed = _parse_llm_json(result.text)
    if not isinstance(parsed, dict):
        return {cid: f"Community {cid}" for cid in communities}

    labels: dict[int, str] = {}
    for cid in communities:
        label = parsed.get(str(cid), f"Community {cid}")
        if isinstance(label, str):
            labels[cid] = label
        else:
            labels[cid] = f"Community {cid}"
    logger.info(
        "Community labeling complete: %s",
        ", ".join(f"{cid}={label}" for cid, label in labels.items()),
    )
    return labels


async def build_code_graph(
    repo_dir: Path,
    ai_provider: str,
    ai_model: str,
    ai_call_timeout: int | None = None,
) -> Path | None:
    """Build a Graphify knowledge graph for the repository.

    Runs the full pipeline: detection → AST extraction → semantic extraction
    (via pi-sidecar) → graph build → clustering → analysis → report.

    Returns the path to GRAPH_REPORT.md on success, or None on failure.
    """
    try:
        from graphify.detect import detect
        from graphify.extract import extract, collect_files
        from graphify.build import build_from_json
        from graphify.cluster import cluster, score_all
        from graphify.analyze import (
            god_nodes,
            surprising_connections,
            suggest_questions,
        )
        from graphify.report import generate as generate_report
        from graphify.export import to_json
    except ImportError:
        logger.warning(
            "graphifyy package not installed, skipping code graph generation"
        )
        return None

    output_dir = repo_dir / "graphify-out"
    output_dir.mkdir(parents=True, exist_ok=True)

    try:
        # Step 1: Detect files
        logger.info("Code graph: detecting files in %s", repo_dir)
        detection = detect(repo_dir, follow_symlinks=False)
        total_files = detection.get("total_files", 0)
        if total_files == 0:
            logger.warning("Code graph: no supported files found")
            return None
        logger.info("Code graph: detected %d files", total_files)

        # Step 2: AST extraction (deterministic, free)
        code_files: list[Path] = []
        for f in detection.get("files", {}).get("code", []):
            p = Path(f)
            if p.is_dir():
                code_files.extend(collect_files(p))
            else:
                code_files.append(p)

        ast_result: dict[str, Any] = {
            "nodes": [],
            "edges": [],
            "input_tokens": 0,
            "output_tokens": 0,
        }
        if code_files:
            logger.info("Code graph: AST extraction on %d code files", len(code_files))
            ast_result = await asyncio.to_thread(extract, code_files, repo_dir)
            logger.info(
                "Code graph: AST result \u2014 %d nodes, %d edges",
                len(ast_result.get("nodes", [])),
                len(ast_result.get("edges", [])),
            )

        # Step 3: Semantic extraction via sidecar (LLM-powered)
        # Collect non-code files for semantic extraction
        non_code_files: list[Path] = []
        for category in ("document", "paper"):
            for f in detection.get("files", {}).get(category, []):
                non_code_files.append(Path(f))

        semantic_result: dict[str, Any] = {
            "nodes": [],
            "edges": [],
            "hyperedges": [],
            "input_tokens": 0,
            "output_tokens": 0,
        }
        if non_code_files:
            semantic_result = await _extract_semantic(
                non_code_files, repo_dir, ai_provider, ai_model, ai_call_timeout
            )
        else:
            logger.info("Code graph: no non-code files, skipping semantic extraction")

        # Step 4: Merge AST + semantic
        seen_ids = {n["id"] for n in ast_result.get("nodes", [])}
        merged_nodes = list(ast_result.get("nodes", []))
        for n in semantic_result.get("nodes", []):
            if n.get("id") and n["id"] not in seen_ids:
                merged_nodes.append(n)
                seen_ids.add(n["id"])
        merged_edges = ast_result.get("edges", []) + semantic_result.get("edges", [])
        logger.info(
            "Code graph: merged \u2014 %d nodes, %d edges",
            len(merged_nodes),
            len(merged_edges),
        )
        merged_extraction = {
            "nodes": merged_nodes,
            "edges": merged_edges,
            "hyperedges": semantic_result.get("hyperedges", []),
            "input_tokens": ast_result.get("input_tokens", 0)
            + semantic_result.get("input_tokens", 0),
            "output_tokens": ast_result.get("output_tokens", 0)
            + semantic_result.get("output_tokens", 0),
        }

        # Step 5: Build graph
        logger.info(
            "Code graph: building graph (%d nodes, %d edges)",
            len(merged_nodes),
            len(merged_edges),
        )
        G = build_from_json(merged_extraction)
        if G.number_of_nodes() == 0:
            logger.warning("Code graph: graph is empty after build")
            return None

        # Step 6: Cluster
        communities = cluster(G)
        cohesion = score_all(G, communities)
        logger.info("Code graph: %d communities detected", len(communities))

        # Step 7: Analysis
        gods = god_nodes(G)
        surprises = surprising_connections(G, communities)

        # Step 8: Label communities via AI
        labels = await _label_communities(
            communities, G, ai_provider, ai_model, ai_call_timeout
        )

        # Step 9: Generate suggested questions
        questions = suggest_questions(G, communities, labels)

        # Step 10: Generate report
        tokens = {
            "input": merged_extraction.get("input_tokens", 0),
            "output": merged_extraction.get("output_tokens", 0),
        }
        report = generate_report(
            G,
            communities,
            cohesion,
            labels,
            gods,
            surprises,
            detection,
            tokens,
            str(repo_dir),
            suggested_questions=questions,
        )

        # Step 11: Write outputs
        report_path = output_dir / "GRAPH_REPORT.md"
        report_path.write_text(report, encoding="utf-8")
        to_json(G, communities, str(output_dir / "graph.json"))

        logger.info(
            "Code graph: complete — %d nodes, %d edges, %d communities. Report: %s",
            G.number_of_nodes(),
            G.number_of_edges(),
            len(communities),
            report_path,
        )
        return report_path

    except Exception:
        logger.warning("Code graph generation failed", exc_info=True)
        return None
