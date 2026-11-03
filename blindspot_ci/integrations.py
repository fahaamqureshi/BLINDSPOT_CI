"""Install the bundled, instruction-only evaluation skill into an explicit project."""
from pathlib import Path

SKILL = Path(__file__).parent / "agent_skill" / "SKILL.md"
TARGETS = {"codex": ".agents", "claude": ".claude"}


def install_skill(project: Path, target: str) -> Path:
    if target not in TARGETS:
        raise ValueError("target must be codex or claude")
    project = project.expanduser().resolve()
    if not project.is_dir():
        raise ValueError("project must be an existing directory")
    destination = project / TARGETS[target] / "skills" / "blindspot-ci" / "SKILL.md"
    if not destination.resolve().is_relative_to(project):
        raise ValueError("skill destination must remain inside the selected project")
    content = SKILL.read_bytes()
    if destination.is_symlink():
        raise ValueError("refusing to replace a linked skill file")
    if destination.exists():
        if destination.read_bytes() != content:
            raise FileExistsError("A different blindspot-ci skill already exists; preserve or remove it explicitly.")
        return destination
    destination.parent.mkdir(parents=True, exist_ok=True)
    with destination.open("xb") as handle:
        handle.write(content)
    return destination
