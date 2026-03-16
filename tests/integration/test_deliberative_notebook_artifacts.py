from pathlib import Path


def test_deliberative_notebook_output_paths_are_stable() -> None:
    output_dir = Path("output/research")

    assert (output_dir / "decripto-club-operational-dossier.md").parent == output_dir
    assert (output_dir / "decripto-club-deliberation-state.json").parent == output_dir
