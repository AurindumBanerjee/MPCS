from __future__ import annotations

import sys
from pathlib import Path
from typing import Optional
import typer
from rich.console import Console
from rich.table import Table

from hkg.config import (
    DATA_DIR,
    PROJECT_ROOT,
    get_modality_seed,
    get_remedy_abbreviations,
    get_sections_config,
    get_sources_config,
    settings,
)
from hkg.eval.run_eval import run_extraction_eval
from hkg.extract.extractor import ExtractionPipeline
from hkg.ingest.chunker import create_chunks_from_parsed
from hkg.ingest.parse_html import parse_html_source
from hkg.ingest.parse_pdf import parse_pdf_source
from hkg.llm.xai_client import XAIClient
from hkg.load.chroma_loader import ChromaLoader
from hkg.load.neo4j_loader import Neo4jLoader
from hkg.query.agent import SingleLLMAgent
from hkg.query.tools import HKGQueryTools

app = typer.Typer(help="Homeopathic Materia Medica Knowledge Graph CLI (hkg)")
console = Console()


@app.command()
def doctor():
    """Check connectivity to Neo4j, ChromaDB, and xAI API, and print resolved config."""
    console.print("\n[bold cyan]=== HKG Doctor: Environment & Connectivity Check ===[/bold cyan]\n")

    table = Table(title="System & Configuration")
    table.add_column("Component", style="bold")
    table.add_column("Status")
    table.add_column("Details")

    # 1. Config & Paths
    sources = get_sources_config()
    abbrs = get_remedy_abbreviations()
    sections = get_sections_config()
    table.add_row(
        "Config Files",
        "[green]OK[/green]",
        f"Sources: {len(sources)}, Abbreviations: {len(abbrs)}, Sections: {len(sections)}",
    )

    # 2. xAI / LLM API
    llm = XAIClient()
    llm_health = llm.health_check()
    if llm_health.get("status") == "ok":
        table.add_row(
            "xAI API",
            "[green]CONNECTED[/green]",
            f"Model: {llm_health.get('model')} (endpoint: {llm.base_url})",
        )
    elif llm_health.get("status") == "warning":
        table.add_row(
            "xAI API",
            "[yellow]NOT CONFIGURED[/yellow]",
            f"{llm_health.get('message')} Target model: {llm_health.get('model')}",
        )
    else:
        table.add_row(
            "xAI API",
            "[red]FAILED[/red]",
            f"Error: {llm_health.get('error')}",
        )

    # 3. ChromaDB
    try:
        import chromadb

        settings.CHROMA_DIR.mkdir(parents=True, exist_ok=True)
        chroma_client = chromadb.PersistentClient(path=str(settings.CHROMA_DIR))
        colls = chroma_client.list_collections()
        table.add_row(
            "ChromaDB",
            "[green]OK[/green]",
            f"Path: {settings.CHROMA_DIR} | Existing collections: {len(colls)}",
        )
    except Exception as e:
        table.add_row("ChromaDB", "[red]ERROR[/red]", str(e))

    # 4. Neo4j
    try:
        from neo4j import GraphDatabase

        driver = GraphDatabase.driver(
            settings.NEO4J_URI,
            auth=(settings.NEO4J_USER, settings.NEO4J_PASSWORD),
            connection_timeout=3.0,
        )
        with driver.session() as session:
            result = session.run("RETURN 1 AS num").single()
            if result and result["num"] == 1:
                table.add_row(
                    "Neo4j",
                    "[green]CONNECTED[/green]",
                    f"URI: {settings.NEO4J_URI} (User: {settings.NEO4J_USER})",
                )
            else:
                table.add_row("Neo4j", "[yellow]UNKNOWN[/yellow]", "No result returned")
        driver.close()
    except Exception as e:
        table.add_row(
            "Neo4j",
            "[yellow]UNAVAILABLE[/yellow]",
            f"Could not connect to {settings.NEO4J_URI}: {e}. (Run 'docker compose up -d' if running locally)",
        )

    console.print(table)
    console.print(f"\n[dim]Target Model Name: [bold]{settings.LLM_MODEL}[/bold][/dim]")
    console.print(f"[dim]Schema Version: {settings.SCHEMA_VERSION}[/dim]\n")


@app.command()
def parse(
    source_file: Path = typer.Argument(..., help="Path to raw source file (.html, .htm, .pdf)"),
    source_key: str = typer.Option("boericke_pocket_manual", help="Source identifier"),
):
    """Parse raw source file (preserving bold/italic markup) into data/parsed/."""
    ext = source_file.suffix.lower()
    console.print(f"Parsing [bold]{source_file}[/bold] as [cyan]{source_key}[/cyan]...")

    if ext in (".html", ".htm"):
        out_path = parse_html_source(source_file, source_key=source_key)
    elif ext == ".pdf":
        out_path = parse_pdf_source(source_file, source_key=source_key)
    else:
        console.print(f"[red]Unsupported format: {ext}. Expected .html or .pdf[/red]")
        raise typer.Exit(1)

    console.print(f"[green]Successfully parsed to:[/green] {out_path}")


@app.command()
def chunk(
    parsed_file: Path = typer.Argument(..., help="Path to parsed .jsonl file"),
    output_file: Optional[Path] = typer.Option(None, help="Output chunks file"),
):
    """Create section-level chunks from parsed records."""
    out = create_chunks_from_parsed(parsed_file, output_path=output_file)
    console.print(f"[green]Successfully generated chunks at:[/green] {out}")


@app.command()
def extract(
    chunks_file: Path = typer.Argument(..., help="Path to chunks.jsonl file"),
    run_id: Optional[str] = typer.Option(None, help="Custom run ID"),
):
    """Run LLM extraction and validation pipeline over chunks."""
    console.print(f"Running extraction over [bold]{chunks_file}[/bold]...")
    pipeline = ExtractionPipeline(run_id=run_id)
    out_file = pipeline.run_on_chunks_file(chunks_file)

    console.print(f"[green]Extraction complete![/green]")
    console.print(f"Output: {out_file}")
    console.print(f"Stats: {pipeline.stats}")


@app.command()
def load_neo4j(
    extracted_file: Path = typer.Argument(..., help="Path to extracted run JSONL"),
):
    """Load extracted occurrences into Neo4j with idempotent constraints."""
    import json

    console.print(f"Loading [bold]{extracted_file}[/bold] into Neo4j...")
    loader = Neo4jLoader()
    loader.apply_constraints()

    occurrences = []
    relationships = []
    with open(extracted_file, "r", encoding="utf-8") as f:
        for line in f:
            if not line.strip():
                continue
            rec = json.loads(line)
            occurrences.extend(rec.get("occurrences", []))
            for rel in rec.get("relationships", []):
                relationships.append({
                    "source_remedy_id": f"remedy:{rec.get('remedy_name', '').lower().replace(' ', '_')}",
                    "target_remedy_id": f"remedy:{rel.get('remedy_raw', '').lower().replace(' ', '_')}",
                    "type": rel.get("type", "compare"),
                    "chunk_id": rec.get("chunk_id", ""),
                    "note_raw": rel.get("note_raw"),
                })

    if occurrences:
        loader.load_occurrences_batch(occurrences)
    if relationships:
        loader.load_relationships_batch(relationships)

    loader.close()
    console.print(f"[green]Loaded {len(occurrences)} occurrences into Neo4j successfully.[/green]")


@app.command()
def load_chroma(
    extracted_file: Path = typer.Argument(..., help="Path to extracted run JSONL"),
):
    """Index extracted occurrences into ChromaDB for semantic search."""
    import json

    console.print(f"Indexing [bold]{extracted_file}[/bold] in ChromaDB...")
    chroma = ChromaLoader()

    occurrences = []
    with open(extracted_file, "r", encoding="utf-8") as f:
        for line in f:
            if not line.strip():
                continue
            rec = json.loads(line)
            occurrences.extend(rec.get("occurrences", []))

    chroma.index_occurrences(occurrences)
    console.print(f"[green]Indexed {len(occurrences)} occurrences in ChromaDB.[/green]")


@app.command()
def ask(
    query_text: str = typer.Argument(..., help="User symptom query or question"),
):
    """Ask the thin single-LLM agent with tool calling and emergency guard."""
    console.print(f"\n[cyan]Query:[/cyan] {query_text}\n")
    agent = SingleLLMAgent()
    res = agent.query(query_text)

    if res.get("is_emergency"):
        console.print(f"[bold red]{res['answer']}[/bold red]\n")
    else:
        console.print(f"[bold green]Answer:[/bold green]\n{res['answer']}\n")


@app.command()
def eval_extraction(
    predictions_file: Path = typer.Argument(..., help="Path to predictions JSONL"),
    gold_file: Optional[Path] = typer.Option(None, help="Path to gold set JSONL"),
):
    """Run extraction benchmark against gold set per plan §11."""
    run_extraction_eval(predictions_file, gold_file=gold_file)


def main():
    app()


if __name__ == "__main__":
    main()
