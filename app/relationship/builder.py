from __future__ import annotations

import json
import threading
import time
from pathlib import Path
from typing import Any

from app.clients.deepseek import DeepSeekClient
from app.relationship.storage import read_relationship_meta, update_relationship_meta, write_relationship_graph

def _read_json(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {}
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
        return data if isinstance(data, dict) else {}
    except Exception:
        return {}


def _extract_json(text: str) -> dict[str, Any]:
    raw = (text or "").strip()
    try:
        data = json.loads(raw)
        if isinstance(data, dict):
            return data
    except Exception:
        pass

    start = raw.find("{")
    end = raw.rfind("}")
    if start != -1 and end != -1 and end > start:
        candidate = raw[start : end + 1]
        try:
            data = json.loads(candidate)
            if isinstance(data, dict):
                return data
        except Exception:
            pass

    return {"raw": raw}


def _compact_list(value: Any, *, limit: int = 6, max_item_chars: int = 90) -> list[str]:
    if not isinstance(value, list):
        return []
    items: list[str] = []
    for x in value:
        s = str(x).strip()
        if not s:
            continue
        if len(s) > max_item_chars:
            s = s[: max_item_chars - 1].rstrip() + "…"
        items.append(s)
        if len(items) >= limit:
            break
    return items


def _pick(analysis: dict, *keys: str, default: str = "") -> str:
    for k in keys:
        v = analysis.get(k)
        if isinstance(v, str) and v.strip():
            return v.strip()
    return default


def _build_paper_summary(job_id: str, meta: dict[str, Any], analysis: dict[str, Any]) -> dict[str, Any]:
    title = _pick(analysis, "标题", "title", "paper_title", default=job_id)
    authors = _pick(analysis, "作者", "authors", default="")
    year = _pick(analysis, "年份", "year", default="")
    abstract = _pick(analysis, "摘要", "abstract", default="")
    if abstract and len(abstract) > 260:
        abstract = abstract[:259].rstrip() + "…"

    tags = meta.get("tags") if isinstance(meta.get("tags"), list) else []
    tags = [str(t).strip() for t in tags if str(t).strip()]
    tags = tags[:12]

    return {
        "id": job_id,
        "title": title,
        "authors": authors,
        "year": year,
        "tags": tags,
        "abstract": abstract,
        "main_conclusions": _compact_list(analysis.get("主要结论") or analysis.get("main_conclusions")),
        "innovations": _compact_list(analysis.get("创新点") or analysis.get("innovations")),
        "methods": _compact_list(analysis.get("实验方法") or analysis.get("methods")),
        "limitations": _compact_list(analysis.get("不足") or analysis.get("limitations")),
        "insights": _compact_list(analysis.get("研究启发") or analysis.get("insights")),
    }


def list_analyzed_papers(output_dir: Path, *, max_papers: int = 30) -> list[dict[str, Any]]:
    max_papers = max(2, min(120, int(max_papers or 30)))
    output_dir = output_dir.resolve()
    papers: list[dict[str, Any]] = []

    if not output_dir.exists():
        return papers

    skip_dirs = {"drawings", "weekly_reports", "relationship_graph"}
    job_dirs: list[Path] = []
    for p in output_dir.iterdir():
        if not p.is_dir():
            continue
        if p.name in skip_dirs:
            continue
        if (p / "analysis.json").exists():
            job_dirs.append(p)

    job_dirs.sort(key=lambda p: p.name, reverse=True)
    for p in job_dirs[:max_papers]:
        job_id = p.name
        meta = _read_json(p / "meta.json")
        analysis = _read_json(p / "analysis.json")
        if not analysis:
            continue
        papers.append(_build_paper_summary(job_id, meta, analysis))

    return papers


def _normalize_graph(raw: dict[str, Any], papers: list[dict[str, Any]]) -> dict[str, Any]:
    if not isinstance(raw, dict):
        raw = {}

    nodes_raw = raw.get("nodes")
    if not isinstance(nodes_raw, list):
        nodes_raw = raw.get("节点")
    nodes: list[dict[str, Any]] = [x for x in nodes_raw if isinstance(x, dict)] if isinstance(nodes_raw, list) else []

    edges_raw = raw.get("edges")
    if not isinstance(edges_raw, list):
        edges_raw = raw.get("边")
    edges: list[dict[str, Any]] = [x for x in edges_raw if isinstance(x, dict)] if isinstance(edges_raw, list) else []

    clusters_raw = raw.get("clusters")
    if not isinstance(clusters_raw, list):
        clusters_raw = raw.get("聚类") or raw.get("clusters")
    clusters: list[dict[str, Any]] = [x for x in clusters_raw if isinstance(x, dict)] if isinstance(clusters_raw, list) else []

    paper_by_id = {str(p.get("id") or ""): p for p in papers if str(p.get("id") or "").strip()}
    node_by_id: dict[str, dict[str, Any]] = {}

    for n in nodes:
        node_id = str(n.get("id") or n.get("job_id") or n.get("paper_id") or "").strip()
        if not node_id:
            continue
        if node_id not in paper_by_id:
            continue
        title = str(n.get("title") or n.get("标题") or n.get("name") or "").strip() or paper_by_id[node_id].get("title", node_id)
        node_by_id[node_id] = {
            "id": node_id,
            "title": title,
            "authors": str(n.get("authors") or n.get("作者") or paper_by_id[node_id].get("authors") or "").strip(),
            "year": str(n.get("year") or n.get("年份") or paper_by_id[node_id].get("year") or "").strip(),
            "tags": n.get("tags") if isinstance(n.get("tags"), list) else paper_by_id[node_id].get("tags", []),
            "keywords": n.get("keywords") if isinstance(n.get("keywords"), list) else [],
            "summary": str(n.get("summary") or n.get("简介") or "").strip(),
        }

    # Ensure all papers exist as nodes.
    for pid, p in paper_by_id.items():
        if pid in node_by_id:
            continue
        node_by_id[pid] = {
            "id": pid,
            "title": str(p.get("title") or pid),
            "authors": str(p.get("authors") or ""),
            "year": str(p.get("year") or ""),
            "tags": p.get("tags") or [],
            "keywords": [],
            "summary": "",
        }

    known = set(node_by_id.keys())
    normalized_edges: list[dict[str, Any]] = []
    seen: set[tuple[str, str, str]] = set()

    for e in edges:
        src = str(e.get("source") or e.get("from") or e.get("src") or e.get("源") or "").strip()
        dst = str(e.get("target") or e.get("to") or e.get("dst") or e.get("目标") or "").strip()
        if not src or not dst or src == dst:
            continue
        if src not in known or dst not in known:
            continue
        typ = str(e.get("type") or e.get("relation") or e.get("关系") or "related").strip() or "related"
        reason = str(e.get("reason") or e.get("desc") or e.get("解释") or "").strip()
        try:
            weight = int(e.get("weight") or e.get("score") or e.get("强度") or 3)
        except Exception:
            weight = 3
        weight = max(1, min(5, weight))

        a, b = (src, dst) if src < dst else (dst, src)
        key = (a, b, typ)
        if key in seen:
            continue
        seen.add(key)
        normalized_edges.append({"source": src, "target": dst, "type": typ, "weight": weight, "reason": reason})

    # Normalize clusters
    normalized_clusters: list[dict[str, Any]] = []
    for c in clusters:
        cid = str(c.get("id") or c.get("cid") or c.get("cluster_id") or "").strip()
        name = str(c.get("name") or c.get("主题") or c.get("title") or "").strip()
        node_ids = c.get("node_ids") or c.get("nodes") or c.get("papers") or []
        if not isinstance(node_ids, list):
            node_ids = []
        node_ids = [str(x).strip() for x in node_ids if str(x).strip() and str(x).strip() in known]
        if not node_ids:
            continue
        if not cid:
            cid = f"c{len(normalized_clusters) + 1}"
        normalized_clusters.append(
            {
                "id": cid,
                "name": name or cid,
                "node_ids": node_ids,
                "keywords": c.get("keywords") if isinstance(c.get("keywords"), list) else [],
            }
        )

    return {
        "version": int(raw.get("version") or 1),
        "nodes": list(node_by_id.values()),
        "edges": normalized_edges,
        "clusters": normalized_clusters,
        "notes": str(raw.get("notes") or raw.get("说明") or "").strip(),
    }


def build_relationship_graph(
    output_dir: Path,
    *,
    max_papers: int = 30,
    client: DeepSeekClient,
    temperature: float = 0.2,
) -> dict[str, Any]:
    papers = list_analyzed_papers(output_dir, max_papers=max_papers)
    if len(papers) < 2:
        return {"version": 1, "nodes": [{"id": p["id"], "title": p.get("title", p["id"])} for p in papers], "edges": [], "clusters": []}

    system = (
        "你是一个学术知识图谱构建助手。你将收到多篇论文的结构化信息（标题/摘要/要点/方法/标签）。\n"
        "任务：推断论文之间的内在关系，输出一个“文献关系图谱” JSON，用于前端可视化。\n"
        "严格要求：\n"
        "1) 只输出合法 JSON，不要输出任何额外文字。\n"
        "2) 输出 schema 必须包含：version, nodes, edges, clusters。\n"
        "3) nodes 必须覆盖输入的每篇论文（以 id 为准），每个 id 只出现一次。\n"
        "4) edges 表示无向概念关系：不要自环，不要重复；只保留强相关（weight>=3）；总边数<=min(80, 3*N)。\n"
        "5) clusters 用于主题聚类：每个 cluster 给 name、node_ids、keywords。\n"
        "6) 不要编造论文中不存在的具体数值/数据集/参数；不确定用“未明确”。\n"
        "字段约束：\n"
        "- version: 1\n"
        "- nodes: [{id,title,authors,year,tags,keywords,summary}]\n"
        "- edges: [{source,target,type,weight,reason}]\n"
        "- type 建议从：same_topic, method_similar, extends, contrasts, application, complementary, survey_relation 里选（也可自定义简短英文）。\n"
        "- weight: 1-5 (只输出>=3)\n"
        "- reason: 1 句话，<=50 字\n"
        "- summary: <=80 字\n"
    )
    payload = {"papers": papers, "constraints": {"max_edges": min(80, 3 * len(papers))}}
    user = "输入 JSON：\n\n" + json.dumps(payload, ensure_ascii=False, indent=2)
    messages = [{"role": "system", "content": system}, {"role": "user", "content": user}]
    out = client.chat_completions(messages, temperature=temperature)
    raw = _extract_json(out)
    return _normalize_graph(raw, papers)


def start_build_relationship_graph(
    output_dir: Path,
    *,
    max_papers: int = 30,
    force: bool = False,
) -> dict[str, Any]:
    meta = read_relationship_meta(output_dir)
    if meta.get("state") == "running" and not force:
        raise RuntimeError("relationship graph is running")

    update_relationship_meta(output_dir, {"state": "running", "error": "", "max_papers": int(max_papers or 30)})

    def worker():
        try:
            client = DeepSeekClient.from_config()
            graph = build_relationship_graph(output_dir, max_papers=max_papers, client=client)
            graph["generated_at"] = time.strftime("%Y-%m-%d %H:%M:%S")
            graph["papers_count"] = len(graph.get("nodes") or [])
            write_relationship_graph(output_dir, graph)
            update_relationship_meta(output_dir, {"state": "succeeded", "error": "", "papers_count": graph.get("papers_count", 0)})
        except Exception as e:
            update_relationship_meta(output_dir, {"state": "failed", "error": str(e)})

    threading.Thread(target=worker, daemon=True).start()
    return read_relationship_meta(output_dir)
