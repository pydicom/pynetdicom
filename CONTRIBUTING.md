Contribution Guide
==================

Dependencies
------------
[pydicom](https://github.com/pydicom/pydicom>) (use the most recent development version)

How to contribute
-----------------
1. Fork the master branch of the project repository by clicking on the 'Fork' button near the top right of the page. This creates a copy of the repository under your GitHub user account. For more details on how to fork a repository see [this guide](https://help.github.com/articles/fork-a-repo/).

2. Clone your fork to your local disk:
    ```bash
    git clone https://github.com/YourUsername/pynetdicom.git
    cd pynetdicom
    ```

3. Create a new branch to hold your development changes:
    ```bash
    git checkout -b my-branch
    ```

4. Develop the feature on your branch. Files can be added using `git add` and changes committed using `git commit`. For more on using git see the [Git documentation](https://git-scm.com/documentation).

5. When you're ready, push your changes to your GitHub account:
    ```bash
    git push -u origin my-branch
    ```

6. You can then create a pull request using [these instructions](https://help.github.com/articles/creating-a-pull-request-from-a-fork).

Pull Requests
-------------

- Please prefix the title of your pull request with `[WIP]` if its in progress and `[MRG]` when you consider it complete and ready for review.
- When fixing bugs your first commit should be the addition of tests that reproduce the original issue and any related issues.
- Use pytest to run the unit tests.
- When adding features you should have complete documentation and 100% unit test coverage that covers not just the lines of code but ensure that the feature works as intended.
- When writing documentation please reference the DICOM Standard where possible. When dealing with significant parts of the code base (`DIMSEMessage.decode_msg()` for example) you should have inline comments that reference both the DICOM Standard and explain in detail what the code is doing and why.
- Docstrings should use UK English and follow the [numpy  docstring](https://numpydoc.readthedocs.io/en/latest/) style.


Code Style
----------
- [Black](https://github.com/psf/black) is required
- Type hints should pass using the current [mypy](https://mypy-lang.org/) release
- There are a handful of project-specific styles that should be used:
  - `ae` for an ApplicationEntity object
  - `acse` for the ACSE object
  - `assoc` for an Association object
  - `dimse` for the DIMSE object
  - `ds` for a pydicom Dataset object
  - Variable and function names should be `lower_case_underscore`, including acronyms such as `context_id` and `uid`.
  - Where a variable corresponds directly to a DICOM Data Element use a name that is identical to the element keyword (i.e. the DIMSE command set elements such as MessageID and AffectedSOPClassUID correspond to attributes such as `C_STORE.MessageID` and `C_STORE.AffectedSOPClassUID`).


Testing
-------

To install the test requirements use:

  ```bash
  pip install -e .[tests]
  ```

Then to run the core tests:

  ```bash
  cd pynetdicom/tests
  pytest
  ```

The application tests are in `pynetdicom/apps/tests`


Documentation
-------------
To install the documentation build requirements use:

  ```bash
  pip install -e .[docs]
  ```

To build the documentation run:

  ```bash
  cd docs
  make html
  ```

The built documentation should be visible in the `docs/_build` directory and can be viewed locally using a web browser.
