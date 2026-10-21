from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Optional

import typer
from rich.console import Console
from rich.progress import BarColumn, MofNCompleteColumn, Progress, TimeElapsedColumn, TimeRemainingColumn
from rich.table import Table

from lkg.config import (
    DATA_DIR,
    get_remedy_abbreviations,
    get_sections_config,
    get_sources_config,
    settings,
)

app = typer.Typer(help="Local (Ollama) Homeopathic Materia Medica Knowledge Graph CLI (lkg)")
console = Console()

BATCH = 500


def _apply_overrides(model: Optional[str], hosts: Optional[str]) -> None:
    """Allow --model / --hosts to override .env for this invocation."""
    if model:
        settings.LLM_MODEL = model
    if hosts:
        settings.OLLAMA_HOSTS = [h.strip() for h in hosts.split(",") if h.strip()]


def _read_extracted(extracted_file: Path) -> list[dict[str, Any]]:
    recs = []
    with open(extracted_file, "r", encoding="utf-8") as f:
        for line in f:
            if line.strip():
                recs.append(json.loads(line))
    return recs


def _count_lines(path: Path) -> int:
    with open(path, "r", encoding="utf-8") as f:
        return sum(1 for line in f if line.strip())


@app.command()
def doctor(
    model: Optional[str] = typer.Option(None, help="Override LLM_MODEL"),
    hosts: Optional[str] = typer.Option(None, help="Override OLLAMA_HOSTS (comma-separated)"),
):
    """Check connectivity to Ollama, Neo4j and ChromaDB, and print resolved config."""
    _apply_overrides(model, hosts)
    from lkg.llm.ollama_client import OllamaClient, OllamaEmbeddingFunction

    console.print("\n[bold cyan]=== LKG Doctor: Local Environment Check ===[/bold cyan]\n")
    table = Table(title="System & Configuration")
    table.add_column("Component", style="bold")
    table.add_column("Status")
    table.add_column("Details")

    table.add_row(
        "Config Files",
        "[green]OK[/green]",
        f"Sources: {len(get_sources_config())}, Abbreviations: {len(get_remedy_abbreviations())}, "
        f"Sections: {len(get_sections_config())}",
    )

    llm = OllamaClient()
    h = llm.health_check()
    color = {"ok": "green", "warning": "yellow"}.get(h["status"], "red")
    table.add_row("Ollama LLM", f"[{color}]{h['status'].upper()}[/{color}]", f"{settings.LLM_MODEL}: {h['message']}")
    for host, info in h["hosts"].items():
        if info.get("ok"):
            table.add_row(f"  host {host}", "[green]UP[/green]",
                          f"model pulled: {info['has_model']} | {', '.join(info['models'][:5])}")
        else:
            table.add_row(f"  host {host}", "[red]DOWN[/red]", str(info.get("error"))[:120])

    emb = OllamaEmbeddingFunction()
    if emb.is_available():
        table.add_row("Ollama Embeddings", "[green]OK[/green]", emb.model)
    else:
        table.add_row("Ollama Embeddings", "[yellow]UNAVAILABLE[/yellow]",
                      f"`ollama pull {emb.model}` (falls back to hash embeddings)")

    try:
        import chromadb

        settings.CHROMA_DIR.mkdir(parents=True, exist_ok=True)
        cols = chromadb.PersistentClient(path=str(settings.CHROMA_DIR)).list_collections()
        table.add_row("ChromaDB", "[green]OK[/green]", f"{settings.CHROMA_DIR} | collections: {len(cols)}")
    except Exception as e:
        table.add_row("ChromaDB", "[red]ERROR[/red]", str(e))

    try:
        from neo4j import GraphDatabase

        driver = GraphDatabase.driver(
            settings.NEO4J_URI, auth=(settings.NEO4J_USER, settings.NEO4J_PASSWORD), connection_timeout=3.0
        )
        with driver.session() as s:
            s.run("RETURN 1").single()
        driver.close()
        table.add_row("Neo4j", "[green]CONNECTED[/green]", settings.NEO4J_URI)
    except Exception as e:
        table.add_row("Neo4j", "[yellow]UNAVAILABLE[/yellow]", f"{e} (run 'docker compose up -d')")

    console.print(table)
    console.print(f"[dim]Workers: {settings.EXTRACT_WORKERS} | num_ctx: {settings.OLLAMA_NUM_CTX} | "
                  f"schema {settings.SCHEMA_VERSION} | prompt {settings.PROMPT_VERSION}[/dim]\n")


@app.command()
def parse(
    source_file: Path = typer.Argument(..., help="Path to raw source file (.html, .htm, .pdf)"),
    source_key: str = typer.Option("hahnemann_materia_medica", help="Source identifier"),
):
    """Parse raw source file (preserving bold/italic markup) into data/parsed/."""
    from lkg.ingest.parse_html import parse_html_source
    from lkg.ingest.parse_pdf import parse_pdf_source

    ext = source_file.suffix.lower()
    console.print(f"Parsing [bold]{source_file}[/bold] as [cyan]{source_key}[/cyan]...")
    if ext in (".html", ".htm"):
        out_path = parse_html_source(source_file, source_key=source_key)
    elif ext == ".pdf":
        out_path = parse_pdf_source(source_file, source_key=source_key)
    else:
        console.print(f"[red]Unsupported format: {ext}[/red]")
        raise typer.Exit(1)
    console.print(f"[green]Parsed {_count_lines(out_path)} records to:[/green] {out_path}")


@app.command()
def chunk(
    parsed_file: Path = typer.Argument(..., help="Path to parsed .jsonl file"),
    output_file: Optional[Path] = typer.Option(None, help="Output chunks file"),
    max_chars: int = typer.Option(3000, help="Max chars per chunk (keep small for local models)"),
):
    """Create section-level chunks from parsed records."""
    from lkg.ingest.chunker import create_chunks_from_parsed

    out = create_chunks_from_parsed(parsed_file, output_path=output_file, max_chunk_chars=max_chars)
    console.print(f"[green]Generated {_count_lines(out)} chunks at:[/green] {out}")


@app.command()
def extract(
    chunks_file: Path = typer.Argument(..., help="Path to chunks.jsonl file"),
    run_id: Optional[str] = typer.Option(None, help="Run ID (reuse the same ID to resume)"),
    workers: Optional[int] = typer.Option(None, help="Parallel requests (default EXTRACT_WORKERS)"),
    limit: Optional[int] = typer.Option(None, help="Only process the first N pending chunks"),
    model: Optional[str] = typer.Option(None, help="Override LLM_MODEL"),
    hosts: Optional[str] = typer.Option(None, help="Override OLLAMA_HOSTS (comma-separated)"),
    mock: bool = typer.Option(False, help="Use mock LLM (no Ollama needed)"),
):
    """Run local LLM extraction + validation over chunks (resumable, parallel, round-robin hosts)."""
    _apply_overrides(model, hosts)
    from lkg.extract.extractor import ExtractionPipeline
    from lkg.llm.mock_client import MockLLMClient
    from lkg.llm.ollama_client import OllamaClient

    if mock:
        llm = MockLLMClient()
    else:
        llm = OllamaClient()
        h = llm.health_check()
        if h["status"] == "error":
            console.print(f"[red]{h['message']}[/red]")
            raise typer.Exit(1)
        if h["status"] == "warning":
            console.print(f"[yellow]{h['message']}[/yellow]")

    pipeline = ExtractionPipeline(llm_client=llm, run_id=run_id, workers=workers)
    console.print(
        f"Run [bold]{pipeline.run_id}[/bold] | model [cyan]{getattr(llm, 'model', 'mock')}[/cyan] | "
        f"hosts {getattr(llm, 'base_url', '-')} | workers {pipeline.workers}"
    )

    total = _count_lines(chunks_file)
    with Progress(
        "[progress.description]{task.description}", BarColumn(), MofNCompleteColumn(),
        TimeElapsedColumn(), TimeRemainingColumn(), console=console,
    ) as prog:
        task = prog.add_task("Extracting", total=total)

        def on_done(res: dict[str, Any]) -> None:
            prog.advance(task)
            if res.get("error"):
                prog.console.print(f"[red]x {res['chunk_id']}: {res['error'][:120]}[/red]")

        # Advance past chunks already done in a previous (resumed) run
        prog.advance(task, len(pipeline._done_chunk_ids()))
        out_file = pipeline.run_on_chunks_file(chunks_file, limit=limit, progress=on_done)

    console.print(f"[green]Extraction complete:[/green] {out_file}")
    console.print(f"Stats: {pipeline.stats}")


@app.command()
def load_neo4j(extracted_file: Path = typer.Argument(..., help="Path to extracted run JSONL")):
    """Load extracted occurrences + remedy relationships into Neo4j (idempotent)."""
    from lkg.load.neo4j_loader import Neo4jLoader
    from lkg.resolve.aliases import RemedyResolver
    from lkg.schema.graph import make_remedy_id

    loader = Neo4jLoader()
    loader.apply_constraints()
    resolver = RemedyResolver()

    occurrences: list[dict[str, Any]] = []
    relationships: list[dict[str, Any]] = []
    for rec in _read_extracted(extracted_file):
        occurrences.extend(rec.get("occurrences", []))
        src_name = rec.get("remedy_name", "")
        if src_name:
            resolver.register_canonical(src_name)
        for rel in rec.get("relationships", []):
            tgt = resolver.resolve(rel.get("remedy_raw", ""))  # resolves abbreviations e.g. "Ars."
            relationships.append({
                "source_remedy_id": make_remedy_id(src_name),
                "source_name": src_name,
                "target_remedy_id": tgt["remedy_id"],
                "target_name": tgt["canonical_name"],
                "type": rel.get("type", "compare"),
                "chunk_id": rec.get("chunk_id", ""),
                "note_raw": rel.get("note_raw"),
            })

    for i in range(0, len(occurrences), BATCH):
        loader.load_occurrences_batch(occurrences[i : i + BATCH])
    for i in range(0, len(relationships), BATCH):
        loader.load_relationships_batch(relationships[i : i + BATCH])
    loader.close()
    console.print(f"[green]Loaded {len(occurrences)} occurrences and {len(relationships)} "
                  f"relationships into Neo4j.[/green]")


@app.command()
def load_chroma(extracted_file: Path = typer.Argument(..., help="Path to extracted run JSONL")):
    """Index extracted occurrences into ChromaDB (Ollama embeddings + BM25)."""
    from lkg.load.chroma_loader import ChromaLoader

    chroma = ChromaLoader()
    occurrences = [o for rec in _read_extracted(extracted_file) for o in rec.get("occurrences", [])]
    for i in range(0, len(occurrences), BATCH):
        chroma.index_occurrences(occurrences[i : i + BATCH])
    console.print(f"[green]Indexed {len(occurrences)} occurrences in ChromaDB "
                  f"(embeddings: {chroma.embedding_backend}).[/green]")


@app.command()
def run(
    source_file: Path = typer.Argument(..., help="Materia medica PDF/HTML"),
    source_key: str = typer.Option("hahnemann_materia_medica", help="Source identifier"),
    run_id: Optional[str] = typer.Option(None, help="Run ID (reuse to resume)"),
    workers: Optional[int] = typer.Option(None, help="Parallel requests"),
    limit: Optional[int] = typer.Option(None, help="Only extract first N chunks (pilot)"),
    model: Optional[str] = typer.Option(None, help="Override LLM_MODEL"),
    hosts: Optional[str] = typer.Option(None, help="Override OLLAMA_HOSTS"),
    max_chars: int = typer.Option(3000, help="Max chars per chunk"),
    skip_neo4j: bool = typer.Option(False, help="Skip Neo4j load"),
    skip_chroma: bool = typer.Option(False, help="Skip ChromaDB indexing"),
):
    """End-to-end: parse -> chunk -> extract -> load Neo4j -> index Chroma."""
    _apply_overrides(model, hosts)
    from lkg.ingest.chunker import create_chunks_from_parsed

    parse(source_file, source_key=source_key)
    parsed = DATA_DIR / "parsed" / f"{source_key}.jsonl"
    chunks_path = DATA_DIR / "chunks" / f"{source_key}_chunks.jsonl"
    create_chunks_from_parsed(parsed, output_path=chunks_path, max_chunk_chars=max_chars)
    console.print(f"[green]Chunks:[/green] {chunks_path} ({_count_lines(chunks_path)})")

    rid = run_id or f"{source_key}_{settings.LLM_MODEL.replace(':', '_').replace('/', '_')}"
    extract(chunks_path, run_id=rid, workers=workers, limit=limit, model=None, hosts=None, mock=False)
    extracted = DATA_DIR / "extracted" / f"{rid}.jsonl"

    if not skip_neo4j:
        try:
            load_neo4j(extracted)
        except Exception as e:
            console.print(f"[yellow]Neo4j load skipped: {e}[/yellow]")
    if not skip_chroma:
        load_chroma(extracted)
    viz([extracted])


@app.command()
def build_remedy(
    remedy_name: str = typer.Argument(..., help="Remedy name, e.g. 'Arnica montana' or 'Belladonna'"),
    chunks_file: Optional[Path] = typer.Option(None, help="Path to pre-prepared remedy chunks.jsonl"),
    source_pdf: Optional[Path] = typer.Option(None, help="Raw PDF to parse if chunks not provided"),
    limit: Optional[int] = typer.Option(None, help="Limit number of chunks for a pilot test"),
    workers: int = typer.Option(2, help="Parallel workers (constrained per machine rules)"),
):
    """Build an individual remedy Knowledge Graph (merging classical book + PubMed literature)."""
    from lkg.build_remedy import (
        build_single_remedy_kg,
        extract_remedy_from_parsed,
    )
    from lkg.ingest.parse_pdf import parse_pdf_source

    slug = remedy_name.lower().replace(" ", "_")
    if not chunks_file:
        if not source_pdf:
            source_pdf = PROJECT_ROOT / "data" / "Materia_medica.pdf"
            if not source_pdf.exists():
                source_pdf = Path(r"D:\MyStuff\GitHub\MPCS\docs\Materia Medica Samuel Hahnemann.pdf")
        parsed_out = parse_pdf_source(source_pdf, source_key=f"parsed_{slug}")
        chunks_file = DATA_DIR / "chunks" / f"{slug}_chunks.jsonl"
        count = extract_remedy_from_parsed(remedy_name, parsed_out, chunks_file)
        console.print(f"[green]Extracted {count} section chunks for {remedy_name} to:[/green] {chunks_file}")

    html_name = f"kg_{slug}.html"
    console.print(f"Preparing single-remedy KG for [bold]{remedy_name}[/bold] (workers={workers})...")
    out = build_single_remedy_kg(
        remedy_name=remedy_name,
        chunks_path=chunks_file,
        output_html_name=html_name,
        workers=workers,
        limit=limit,
    )
    console.print(f"[bold green]Individual KG generated successfully![/bold green] Open at: {out}")


@app.command()
def viz(
    extracted_files: list[Path] = typer.Argument(..., help="One or more extracted JSONL files to merge & visualize"),
    output_html: Optional[Path] = typer.Option(None, help="Output interactive HTML path"),
    title: str = typer.Option("Materia Medica & Cognitive-Affective Knowledge Graph", help="Graph header title"),
):
    """Build unified multi-source concept graph and export interactive dark-mode HTML visualizer."""
    from lkg.viz.graph_viz import export_interactive_html

    out = export_interactive_html(extracted_files, output_html=output_html, title=title)
    console.print(f"[green]Interactive KG exported to:[/green] {out}")
    console.print(f"[dim]Graph JSON exported to:[/dim] {out.with_suffix('.graph.json')}")


@app.command()
def ask(
    query_text: str = typer.Argument(..., help="User symptom query or question"),
    model: Optional[str] = typer.Option(None, help="Override LLM_MODEL"),
):
    """Ask the local single-LLM agent (with emergency guard)."""
    _apply_overrides(model, None)
    from lkg.query.agent import SingleLLMAgent

    console.print(f"\n[cyan]Query:[/cyan] {query_text}\n")
    res = SingleLLMAgent().query(query_text)
    style = "bold red" if res.get("is_emergency") else "bold green"
    console.print(f"[{style}]Answer:[/{style}]\n{res['answer']}\n")


@app.command()
def eval_extraction(
    predictions_file: Path = typer.Argument(..., help="Path to predictions JSONL"),
    gold_file: Optional[Path] = typer.Option(None, help="Path to gold set JSONL"),
):
    """Run extraction benchmark against gold set."""
    from lkg.eval.run_eval import run_extraction_eval

    run_extraction_eval(predictions_file, gold_file=gold_file)


def main():
    app()


if __name__ == "__main__":
    main()
