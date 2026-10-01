# CONTRIBUTING TO FLYNC

## Introduction

Thank you for your interest in contributing to the FLYNC project. This project is licensed under the Apache License v2.0, and we welcome contributions from the community to enhance its functionality, improve documentation, and fix issues.

This document outlines the process for contributing to the project. By following these guidelines, you help ensure a smooth and collaborative development process.

All contributions must comply with the **Apache-2.0 license**. Ensure you understand the terms of the license before contributing.

## Getting Started

Before contributing, familiarize yourself with the project:

- **Repository**: The source code is hosted at <https://github.com/Technica-Engineering/FLYNC>.
- **Documentation**: Read the main documentation to understand the project's functionality and structure.
- **Issue Tracker**: Check the issue tracker for open issues, bugs, or feature requests.

To contribute, you will need:

- **Python 3.12 to 3.14** (`requires-python = ">=3.12,<3.15"`)
- Git for version control
- A code editor (e.g., VS Code, PyCharm)
- Familiarity with the project dependencies (e.g., ``pydantic``, ``pyyaml``, ``pytest``)

To get a glance of the project dependencies, check:
```bash
uv tree
```

## Contribution Workflow

Follow these steps to contribute to the FLYNC project:

1. **Fork the Repository**:

   - Fork the repository (see Github on how to fork).

2. **Create a Feature Branch**:

   - Clone your fork of FLYNC, if not done already.

   - Create a new branch for your contribution with a meaningful name and structure using this format:
    ```bash
    <type>/<description>
    ```
    - `main`: The main development branch (e.g., main, master, or develop)
    - `feature/` (or `feat/`): For new features (e.g., `feature/add-login-page`, `feat/add-login-page`)
    - `bugfix/` (or `fix/`): For bug fixes (e.g., `bugfix/fix-header-bug`, `fix/header-bug`)
    - `hotfix/`: For urgent fixes (e.g., `hotfix/security-patch`)
    - `chore/`: For non-code tasks like dependency, docs updates (e.g., `chore/update-dependencies`)

    *See the full [guideline for conventional branch naming](https://conventional-branch.github.io/).*

    **Release branches** are the exception to the `<type>/<description>` scheme: each minor line has a
    flat `release-<major>.<minor>` branch (e.g., `release-0.14`), cut from `main` and used to prepare the
    release (version bump, release notes). The release itself is a **tag** named
    `release-<major>.<minor>.<patch>` (e.g., `release-0.14.0`, release candidates `release-0.14.0-rc1`) —
    the tag `uv-dynamic-versioning` derives the package version from. After the release the branch stays
    open for bugfixes; CI pipelines run on `main` and on all `release-*` branches.

    To create a branch use this command:
     ```bash
     git checkout -b <type>/<description>
     ```

3. **Make Changes**:

   - Implement your changes, ensuring they align with the project's coding standards.
   - Update or add tests to cover your changes (if applicable).
   - Update documentation by adding examples or extending the API reference (if applicable).

4. **Commit Changes**:

   - Write clear, concise commit messages using the same conventional types as the branch names
     above (`feat`, `fix`, `chore`, ...):
     ```
     <type>: short description

     Detailed description
     Reference to issue
     ```

     Example:
     ```
     feat: add support for new validate command

     Added a new command to validate SOME/IP configurations with enhanced error reporting.

     Closes: #123456
     ```

5. **Push Changes**:

   - Push your branch to your fork:
    ```bash
    git push origin your-branch-name
    ```

6. **Submit a Pull Request**:

   - Open a pull request (PR) against the main repository's ``main`` branch — or, for fixes that must reach an
     already released line, against the corresponding ``release-<major>.<minor>`` branch (see *Release branches* above).
   - Provide a clear description of your changes, referencing any related issues (e.g., ``Closes: #123``).
   - Ensure your PR passes all automated checks (e.g., linting, tests).

7. **Code Review**:

   - The project maintainers will review your PR.
   - Address any feedback by making additional commits to the same branch.
   - Once approved, your changes will be merged.

  > **HINT**: Keep your fork in sync with the upstream repository by periodically pulling changes:

  ```bash
  git remote add upstream main-repo-url
  git fetch upstream
  git rebase upstream/main
  ```


## Coding Standards

The FLYNC project adheres to strict coding standards to ensure consistency, maintainability, and readability across the codebase.

These standards are particularly important when introducing new parts to the model, such as new classes, methods, or configuration validations, to ensure seamless integration with the existing architecture.

This document outlines the coding standards for contributing to the FLYNC project, with a focus on Python conventions, Pydantic model development, and best practices for automotive configuration management.

All contributors must follow these guidelines to maintain the project's quality and compatibility with its license.

### General Python conventions

The FLYNC project follows [PEP 8](https://www.python.org/dev/peps/pep-0008/) for Python code style, with specific conventions tailored to the project's needs.

Key guidelines include:

- **Indentation**: Use 4 spaces per indentation level. Do not use tabs.
- **Line Length**: Limit lines to 149 characters for readability.
- **Imports**:
    - Group imports in the following order: standard library, third-party, local project modules.
    - Use explicit imports (e.g., ``from pydantic import Field`` instead of ``import pydantic``).
    - Prefer built-in generics and PEP 604 unions (``list[X]``, ``X | None``) over ``typing.List`` / ``typing.Optional`` in new code.
- **Naming Conventions**:
    - **Classes**: Use **PascalCase** (e.g., ``SwitchPort``, ``MulticastGroup``).
    - **Methods and Functions**: Use **snake_case** (e.g., ``validate_config``, ``get_config``).
    - **Variables**: Use **snake_case** for variables and attributes (e.g., ``silicon_port_no``, ``default_vlan_id``).
    - **Constants**: Use **UPPER_SNAKE_CASE** for constants (e.g., ``INSTANCES``).
    - **Private Attributes**: Prefix with a single underscore (e.g., ``_mdi_config``); see the [model patterns](docs/source/development/model_patterns.rst) for the required form in Pydantic v2 models.
- **Docstrings**: Follow [PEP 257](https://www.python.org/dev/peps/pep-0257/) for docstrings. Use triple double-quotes (``"""``) and include:
    - A brief description of the class, method, or function.
    - Parameters, return values, and exceptions (if applicable) in a structured format.
    - Model classes use the NumPy-style ``Parameters`` section documented in the [model patterns](docs/source/development/model_patterns.rst) — it feeds the API reference and is checked by ``scripts/ci/check_model_docstrings.py``.

### Pydantic Model Development

FLYNC relies heavily on [Pydantic](https://docs.pydantic.dev/latest/) for data validation and model definition.

The modelling conventions for new classes, fields, and validators are documented in the
**[Model Development Guide](docs/source/development/index.rst)** — each rule there shown as a
short example, with the CI gate that enforces it:

| Topic | Guide page |
|---|---|
| ``FLYNCBaseModel``, field and constraint conventions, NumPy docstrings, private attributes, typing rules (PEP 604, no redundant quotes, ``Self``) | [model_patterns](docs/source/development/model_patterns.rst) |
| ``External``/``Implied``/``Reference`` annotations and discriminated unions | [structure_and_polymorphism](docs/source/development/structure_and_polymorphism.rst) — annotation details also in the [field annotations](docs/source/flync_reference/sdk_core/field_annotations.rst) reference |
| Validator choice (``BeforeValidator``/``AfterValidator``, ``model_validator`` modes), the error catalog, testing findings | [validators_and_errors](docs/source/development/validators_and_errors.rst) |

The shortest version:

- Inherit from ``FLYNCBaseModel`` and inherit its config (``extra="forbid"`` etc.) — do not re-declare it; document every field in the class docstring's NumPy ``Parameters`` section.
- Children declare their own ``name``; uniqueness is enforced **on the owning parent** via ``validate_list_items_unique``.
- Never raise a bare ``ValueError`` from a model — use the catalogued ``err_*``/``warn`` factories (see *Error Handling and Logging* below).


### Error Handling and Logging

- **Logging**:
    - Use the ``logging`` module for debugging and informational messages.
    - Log relevant events, such as file parsing or validation steps:

    ```python
        logger.info(f"Parsed Service Interface: {service_interface}")
    ```
- **Error propagation**
    - Raise findings through the error catalog — ``err_minor`` / ``err_major`` / ``err_fatal`` (raise the returned error) and ``warn`` (record, do not raise) from ``flync.core.utils.exceptions``, never a bare ``ValueError``.
    - The id format, the mandatory ``category=`` / ``error_number=`` arguments, the ``flync errors`` workflow, and pinning errors in tests are documented in the [Model Development Guide](docs/source/development/validators_and_errors.rst).

## File and Directory Structure

When introducing new model components, ensure they align with the project's directory structure:

- Place new model classes in the appropriate module (e.g., ``src/flync/model/flync_4_ecu/`` for ECU-related models, ``src/flync/model/flync_4_tsn/`` for TSN-related models).
- Use descriptive file names in **snake_case** (e.g., ``phy.py``, ``internal_topology.py``).
- Maintain a consistent module hierarchy, mirroring the configuration structure (e.g., ``controllers/``, ``ports/``).

> **HINT**: When adding a new model, check for compatibility with existing YAML schemas to avoid breaking existing configurations.

## Testing

All new model components must include tests to validate their behavior:

- **Test Framework**: Use ``pytest`` for unit and integration tests.
- **Test Location**: Place tests in ``tests/``, mirroring the source structure (e.g. ``tests/unit_test/model/tests_4_ecu/`` for ``src/flync/model/flync_4_ecu/``).
- **Test Coverage**:
    - Test all fields and validators, including edge cases.
    - Test error conditions (e.g., invalid VLAN IDs, missing required fields).
- **Pin the exact error**: negative tests must use ``assert_single_error`` from ``tests/error_assertions.py``, which asserts a single error and pins its ``FLYNC-...`` id — a bare substring ``assert`` passes on any unrelated error.
- Run tests from the repository root:

```bash
uv run pytest
```

> **WARNING**: Ensure all tests pass before submitting a pull request. Untested code will not be accepted.


## Documentation

Update documentation for any changes that affect usage or contribution guidelines.

- **Code Documentation**:
    - Provide comprehensive docstrings for all classes, methods, and functions.
    - Use RST-style references for cross-linking to other classes or modules (e.g., `:class:~flync.model.flync_4_ecu.phy.MII`.
    - Include usage notes for complex configurations (e.g., conditions for optional fields).

- **Project Documentation**:
    - Update any RST file to reflect new model components or changes to existing ones.
    - Use reStructuredText (RST) for all documentation files deployed to the documentation.
    - Update this ``CONTRIBUTING.md`` if new contribution processes are introduced.

> **NOTE**: Preview RST files using a tool like Sphinx or an RST viewer to ensure correct rendering.


## Issue Reporting

If you encounter bugs or have feature requests:

- Check the issue tracker to avoid duplicates.
- Open a new issue with:
  - A clear title (e.g., ``Bug: YAML parsing fails with invalid syntax``).
  - A detailed description, including steps to reproduce, expected behavior, and actual behavior.
  - Relevant logs or screenshots.
  - Your environment (e.g., Python version, OS).

> **ATTENTION**: Provide as much detail as possible in issue reports to help maintainers diagnose and resolve issues quickly.

## Feature Requests

We welcome ideas that improve usability, performance, or integration with automotive toolchains.

When suggesting a feature, please describe:

- The problem you are trying to solve
- Your expected workflow
- How the feature would integrate into SDV development processes

## Security Issues

If you discover a potential security issue, please **do not** report it publicly in the issue tracker.

Instead, contact the maintainers directly via [flync@technica-engineering.de](mailto:flync@technica-engineering.de)

This allows us to investigate and address the issue responsibly.


## Code of Conduct

The project maintainers are committed to fostering an inclusive and respectful community. All contributors must adhere to the following principles:

- Be respectful and professional in all interactions.
- Avoid discriminatory language or behavior.
- Collaborate constructively, providing helpful feedback.

Violations may result in removal from the project.


License
-------

The FLYNC project is licensed under **Apache-2.0**. By contributing, you agree that your contributions will be licensed under its regulations.
