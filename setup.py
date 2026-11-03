"""Include only public demonstration assets in built Python distributions."""
from pathlib import Path

from setuptools import setup
from setuptools.command.build_py import build_py

PUBLIC_ASSETS = (
    "data/scenarios.json", "datasets/manifest.json", "datasets/real-labels-template.json",
    "datasets/samples/absent.png", "datasets/samples/alternate_view.png",
    "datasets/samples/low_light.png", "datasets/samples/normal.png", "datasets/samples/occluded.png",
    "fixtures/mock_responses.json", "fixtures/ground_truth.json", "fixtures/expected_demo.json",
    "fixtures/examples/8f6003378706480a.json", "fixtures/examples/a165cd6773cd433a.json",
    "fixtures/policies/long-video.json",
)


class BuildPy(build_py):
    def run(self):
        super().run()
        root = Path(__file__).resolve().parent
        for name in PUBLIC_ASSETS:
            target = Path(self.build_lib) / "blindspot_ci" / "_bundled" / name
            target.parent.mkdir(parents=True, exist_ok=True)
            self.copy_file(str(root / name), str(target))


setup(cmdclass={"build_py": BuildPy})
