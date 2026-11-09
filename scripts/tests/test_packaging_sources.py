import importlib.util
import tempfile
import unittest
from pathlib import Path


SCRIPT = Path(__file__).resolve().parents[1] / "package_catia-toolbox.py"
SPEC = importlib.util.spec_from_file_location("package_catia_toolbox", SCRIPT)
assert SPEC is not None and SPEC.loader is not None
PACKAGER = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(PACKAGER)


class PackagingSourcesTests(unittest.TestCase):
    def test_framework_tokens_keep_the_archive_design_tokens_path(self):
        with tempfile.TemporaryDirectory() as temporary:
            repo = Path(temporary)
            (repo / "apps" / "sample").mkdir(parents=True)
            (repo / "apps" / "sample" / "main.py").write_text("app", encoding="utf-8")
            token_dir = repo / "framework" / "design-tokens"
            token_dir.mkdir(parents=True)
            (token_dir / "theme.css").write_text("theme", encoding="utf-8")

            sources = PACKAGER._walk_sources(repo, ["apps/sample", "design-tokens"])

            self.assertEqual(
                {archive_path.as_posix() for _, archive_path in sources},
                {"apps/sample/main.py", "design-tokens/theme.css"},
            )

    def test_packaging_fails_if_framework_submodule_tokens_are_missing(self):
        with tempfile.TemporaryDirectory() as temporary:
            with self.assertRaisesRegex(FileNotFoundError, "initialize the framework submodule"):
                PACKAGER._walk_sources(Path(temporary), ["design-tokens"])


if __name__ == "__main__":
    unittest.main()
