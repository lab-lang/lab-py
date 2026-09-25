# Releasing lab-compiler

The PyPI distribution is `lab-compiler`; the Python import is `lab`. The version is defined in `src/lab/_version.py`. Hatchling reads that file for both the wheel and source distribution, and the compiler records the same version in its output.

## One-time setup

Create the `pypi` environment in the [repository settings](https://github.com/the-lab-compiler/lab-py/settings/environments). Restrict deployment tags to `v*` and configure any required reviewers there.

For the first release, add a pending publisher under [PyPI account publishing](https://pypi.org/manage/account/publishing/):

| Field | Value |
| --- | --- |
| PyPI project name | `lab-compiler` |
| GitHub owner | `the-lab-compiler` |
| Repository name | `lab-py` |
| Workflow filename | `publish.yml` |
| Environment name | `pypi` |

If the project already exists under your account, add the same publisher in its publishing settings. This uses [PyPI Trusted Publishing](https://docs.pypi.org/trusted-publishers/using-a-publisher/) and requires no stored PyPI API token. A [pending publisher](https://docs.pypi.org/trusted-publishers/creating-a-project-through-oidc/) does not reserve the package name; the first successful upload creates the project.

## Validate a release

Update `src/lab/_version.py` when preparing a new version, then run from the repository root:

```sh
uv lock
uv sync --locked --all-extras
uv run --no-sync ruff check .
uv run --no-sync mypy
uv run --no-sync pytest -q
uv build --no-sources
uv run --no-sync twine check --strict dist/*
```

Build into an empty `dist/` directory so old releases are not included. `uv build` creates a source distribution and builds the wheel from it. Confirm both artifacts can be installed in fresh environments; for version `0.1.0`:

```sh
uv venv /tmp/lab-compiler-wheel --python 3.12
uv pip install --python /tmp/lab-compiler-wheel/bin/python dist/lab_compiler-0.1.0-py3-none-any.whl
/tmp/lab-compiler-wheel/bin/python -I scripts/check_install.py

uv venv /tmp/lab-compiler-sdist --python 3.12
uv pip install --python /tmp/lab-compiler-sdist/bin/python dist/lab_compiler-0.1.0.tar.gz
/tmp/lab-compiler-sdist/bin/python -I scripts/check_install.py
```

The install check verifies distribution metadata, version agreement, the license and typing marker, and manual compilation without importing robot SDKs. `-I` ensures Python imports the installed package. CI runs the test suite with core dependencies and both optional SDKs on Python 3.11 and 3.12, then builds and checks both artifacts. PUDU equivalence tests skip unless the separate checkout is available at the path specified in `tests/test_ot2_equivalence.py`; CI does not fetch it. Robot tests use offline simulation and command recording.

## Publish

1. Merge the release changes and confirm CI passes on the intended commit.
2. Create a GitHub release for that commit with a tag matching the package version exactly, such as `v0.1.0`.
3. Publish the GitHub release. Draft releases do not upload packages.
4. The `Publish to PyPI` workflow runs CI again for the release, checks the tag against the package version, and uploads the validated artifacts through the `pypi` environment. Approve the environment deployment if required reviewers are configured.
5. Confirm the version appears on [PyPI](https://pypi.org/project/lab-compiler/) and install it in a fresh environment:

   ```sh
   python -m pip install "lab-compiler==0.1.0"
   python -c "import lab; print(lab.__version__)"
   ```

Publishing a GitHub release triggers a real PyPI upload, including releases marked as prereleases. Use a PEP 440 prerelease version such as `0.2.0rc1` and a matching tag when that is intended. PyPI does not allow replacing an uploaded file; corrections require a new version.
