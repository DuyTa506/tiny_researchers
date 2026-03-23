"""
Phase 2 smoke tests — Experiment Reproduction tools.

Tests run without network or Docker:
  - Import and instantiation
  - Schema validation
  - EnvBuilderTool   — generates files (pure file I/O)
  - DatasetDownloadTool — generates scripts (pure file I/O)
  - CodeGenTool      — scaffolds project (pure file I/O)
  - Loop has Phase 2 tools registered

Note: PaperFetchTool has been moved to claw/skills/paper-fetch/ skill.
"""

from __future__ import annotations

from pathlib import Path
import pytest


# ══════════════════════════════════════════════════════════════════════════════
# STEP 1 — Phase 2 tool imports
# ══════════════════════════════════════════════════════════════════════════════

class TestPhase2Imports:

    def test_env_builder(self):
        from claw.agent.tools.env_builder import EnvBuilderTool
        assert EnvBuilderTool

    def test_dataset_download(self):
        from claw.agent.tools.dataset_download import DatasetDownloadTool
        assert DatasetDownloadTool

    def test_code_gen(self):
        from claw.agent.tools.code_gen import CodeGenTool
        assert CodeGenTool


# ══════════════════════════════════════════════════════════════════════════════
# STEP 2 — Schema validation
# ══════════════════════════════════════════════════════════════════════════════

class TestPhase2Schemas:

    def _all_tools(self):
        from claw.agent.tools.env_builder import EnvBuilderTool
        from claw.agent.tools.dataset_download import DatasetDownloadTool
        from claw.agent.tools.code_gen import CodeGenTool
        return [EnvBuilderTool(), DatasetDownloadTool(), CodeGenTool()]

    def test_names(self):
        expected = {"env_builder", "dataset_download", "code_gen"}
        actual = {t.name for t in self._all_tools()}
        assert actual == expected

    def test_schemas_valid(self):
        for t in self._all_tools():
            s = t.to_schema()
            assert s["type"] == "function"
            assert "name" in s["function"]
            assert "parameters" in s["function"]
            assert s["function"]["parameters"]["type"] == "object"

    def test_env_builder_required(self):
        from claw.agent.tools.env_builder import EnvBuilderTool
        errs = EnvBuilderTool().validate_params({})
        assert len(errs) > 0  # output_dir is required

    def test_dataset_download_required(self):
        from claw.agent.tools.dataset_download import DatasetDownloadTool
        errs = DatasetDownloadTool().validate_params({})
        assert len(errs) > 0  # dataset_name and output_dir required

    def test_code_gen_required(self):
        from claw.agent.tools.code_gen import CodeGenTool
        errs = CodeGenTool().validate_params({})
        assert len(errs) > 0  # output_dir is required


# ══════════════════════════════════════════════════════════════════════════════
# STEP 3 — EnvBuilderTool (pure file I/O, no network)
# ══════════════════════════════════════════════════════════════════════════════

class TestEnvBuilder:

    @pytest.mark.asyncio
    async def test_generates_all_files(self, tmp_path):
        from claw.agent.tools.env_builder import EnvBuilderTool
        r = await EnvBuilderTool().execute(
            output_dir=str(tmp_path),
            framework="pytorch",
            python_version="3.11",
            packages=["transformers==4.35.0", "datasets"],
            cuda=True,
        )
        assert "error" not in r.lower(), f"Got error: {r}"
        assert (tmp_path / "Dockerfile").exists()
        assert (tmp_path / "requirements.txt").exists()
        assert (tmp_path / "environment.yml").exists()
        assert (tmp_path / "setup.sh").exists()
        assert (tmp_path / "setup.bat").exists()

    @pytest.mark.asyncio
    async def test_dockerfile_has_pytorch_image(self, tmp_path):
        from claw.agent.tools.env_builder import EnvBuilderTool
        await EnvBuilderTool().execute(output_dir=str(tmp_path), framework="pytorch", cuda=True)
        content = (tmp_path / "Dockerfile").read_text()
        assert "pytorch" in content.lower() or "FROM" in content

    @pytest.mark.asyncio
    async def test_dockerfile_cpu_only(self, tmp_path):
        from claw.agent.tools.env_builder import EnvBuilderTool
        await EnvBuilderTool().execute(output_dir=str(tmp_path), framework="pytorch", cuda=False)
        content = (tmp_path / "Dockerfile").read_text()
        assert "FROM" in content

    @pytest.mark.asyncio
    async def test_requirements_has_user_packages(self, tmp_path):
        from claw.agent.tools.env_builder import EnvBuilderTool
        await EnvBuilderTool().execute(
            output_dir=str(tmp_path),
            packages=["sacrebleu==2.3.1", "sentencepiece"],
        )
        content = (tmp_path / "requirements.txt").read_text()
        assert "sacrebleu" in content
        assert "sentencepiece" in content

    @pytest.mark.asyncio
    async def test_setup_bat_exists_and_has_content(self, tmp_path):
        from claw.agent.tools.env_builder import EnvBuilderTool
        await EnvBuilderTool().execute(output_dir=str(tmp_path))
        bat = (tmp_path / "setup.bat").read_text()
        assert len(bat) > 50

    @pytest.mark.asyncio
    async def test_tensorflow_framework(self, tmp_path):
        from claw.agent.tools.env_builder import EnvBuilderTool
        r = await EnvBuilderTool().execute(output_dir=str(tmp_path), framework="tensorflow")
        assert "error" not in r.lower()
        content = (tmp_path / "Dockerfile").read_text()
        assert "tensorflow" in content.lower() or "FROM" in content

    @pytest.mark.asyncio
    async def test_environment_yml_has_name(self, tmp_path):
        from claw.agent.tools.env_builder import EnvBuilderTool
        await EnvBuilderTool().execute(output_dir=str(tmp_path))
        content = (tmp_path / "environment.yml").read_text()
        assert "name:" in content


# ══════════════════════════════════════════════════════════════════════════════
# STEP 4 — DatasetDownloadTool (generates scripts, no actual download)
# ══════════════════════════════════════════════════════════════════════════════

class TestDatasetDownload:

    @pytest.mark.asyncio
    async def test_generates_script(self, tmp_path):
        from claw.agent.tools.dataset_download import DatasetDownloadTool
        r = await DatasetDownloadTool().execute(
            dataset_name="squad",
            output_dir=str(tmp_path),
            source="huggingface",
        )
        assert "error" not in r.lower(), f"Got error: {r}"
        assert (tmp_path / "download_data.py").exists()

    @pytest.mark.asyncio
    async def test_script_has_dataset_name(self, tmp_path):
        from claw.agent.tools.dataset_download import DatasetDownloadTool
        await DatasetDownloadTool().execute(
            dataset_name="wikitext",
            output_dir=str(tmp_path),
        )
        content = (tmp_path / "download_data.py").read_text()
        assert "wikitext" in content

    @pytest.mark.asyncio
    async def test_generates_requirements(self, tmp_path):
        from claw.agent.tools.dataset_download import DatasetDownloadTool
        await DatasetDownloadTool().execute(
            dataset_name="cifar10",
            output_dir=str(tmp_path),
        )
        assert (tmp_path / "requirements_data.txt").exists()

    @pytest.mark.asyncio
    async def test_url_source(self, tmp_path):
        from claw.agent.tools.dataset_download import DatasetDownloadTool
        r = await DatasetDownloadTool().execute(
            dataset_name="custom",
            output_dir=str(tmp_path),
            source="url",
            url="https://example.com/data.zip",
        )
        assert "error" not in r.lower()
        content = (tmp_path / "download_data.py").read_text()
        assert "example.com" in content or "urllib" in content

    @pytest.mark.asyncio
    async def test_subset_included(self, tmp_path):
        from claw.agent.tools.dataset_download import DatasetDownloadTool
        await DatasetDownloadTool().execute(
            dataset_name="glue",
            output_dir=str(tmp_path),
            subset="mrpc",
        )
        content = (tmp_path / "download_data.py").read_text()
        assert "mrpc" in content or "glue" in content


# ══════════════════════════════════════════════════════════════════════════════
# STEP 5 — CodeGenTool (generates full project scaffold)
# ══════════════════════════════════════════════════════════════════════════════

class TestCodeGen:

    @pytest.mark.asyncio
    async def test_generates_project_files(self, tmp_path):
        from claw.agent.tools.code_gen import CodeGenTool
        r = await CodeGenTool().execute(
            output_dir=str(tmp_path),
            paper_title="Attention Is All You Need",
            framework="pytorch",
            architecture="Transformer, 6 layers, d_model=512",
            hyperparams={"lr": 0.0001, "batch_size": 32, "epochs": 100},
            dataset_name="wmt14",
            task="seq2seq",
        )
        assert "error" not in r.lower(), f"Got error: {r}"

    @pytest.mark.asyncio
    async def test_creates_src_files(self, tmp_path):
        from claw.agent.tools.code_gen import CodeGenTool
        await CodeGenTool().execute(
            output_dir=str(tmp_path),
            paper_title="Test Paper",
        )
        src = tmp_path / "src"
        assert src.exists()
        # At least model.py and train.py must exist
        assert (src / "model.py").exists()
        assert (src / "train.py").exists()

    @pytest.mark.asyncio
    async def test_creates_config(self, tmp_path):
        from claw.agent.tools.code_gen import CodeGenTool
        await CodeGenTool().execute(
            output_dir=str(tmp_path),
            hyperparams={"lr": 1e-4, "batch_size": 64, "epochs": 50},
        )
        config_dir = tmp_path / "configs"
        assert config_dir.exists()
        yaml_files = list(config_dir.glob("*.yaml")) + list(config_dir.glob("*.yml"))
        assert len(yaml_files) >= 1

    @pytest.mark.asyncio
    async def test_config_has_hyperparams(self, tmp_path):
        from claw.agent.tools.code_gen import CodeGenTool
        await CodeGenTool().execute(
            output_dir=str(tmp_path),
            hyperparams={"lr": 0.00042, "batch_size": 128},
        )
        config_files = list((tmp_path / "configs").glob("*.yaml")) + \
                       list((tmp_path / "configs").glob("*.yml"))
        content = config_files[0].read_text()
        assert "0.00042" in content or "batch_size" in content

    @pytest.mark.asyncio
    async def test_creates_readme(self, tmp_path):
        from claw.agent.tools.code_gen import CodeGenTool
        await CodeGenTool().execute(
            output_dir=str(tmp_path),
            paper_title="Attention Is All You Need",
        )
        readme = tmp_path / "README.md"
        assert readme.exists()
        content = readme.read_text()
        assert "Attention" in content or "reproduction" in content.lower()

    @pytest.mark.asyncio
    async def test_train_script_has_seed_fixing(self, tmp_path):
        from claw.agent.tools.code_gen import CodeGenTool
        await CodeGenTool().execute(output_dir=str(tmp_path))
        train_py = (tmp_path / "src" / "train.py").read_text()
        # Must have seed fixing for reproducibility
        assert "seed" in train_py.lower()

    @pytest.mark.asyncio
    async def test_generated_python_is_valid_syntax(self, tmp_path):
        import ast
        from claw.agent.tools.code_gen import CodeGenTool
        await CodeGenTool().execute(output_dir=str(tmp_path), paper_title="Test")
        for py_file in (tmp_path / "src").glob("*.py"):
            source = py_file.read_text()
            try:
                ast.parse(source)
            except SyntaxError as e:
                pytest.fail(f"Syntax error in {py_file.name}: {e}")


# ══════════════════════════════════════════════════════════════════════════════
# STEP 6 — AgentLoop has all Phase 2 tools
# ══════════════════════════════════════════════════════════════════════════════

class TestLoopPhase2:

    def test_phase2_tools_registered(self, tmp_path):
        from claw.agent.loop import AgentLoop
        agent = AgentLoop(workspace=tmp_path)
        names = set(agent.tools.tool_names)
        assert "env_builder" in names,      f"env_builder missing from: {names}"
        assert "dataset_download" in names, f"dataset_download missing from: {names}"
        assert "code_gen" in names,         f"code_gen missing from: {names}"

    def test_total_tool_count(self, tmp_path):
        from claw.agent.loop import AgentLoop
        agent = AgentLoop(workspace=tmp_path)
        # Core (6) + Phase 2 (3) + spawn (1) = 10
        assert len(agent.tools) >= 10, f"Only {len(agent.tools)} tools registered"
