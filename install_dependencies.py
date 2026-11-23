"""Install project requirements into the Python interpreter running this file."""

import importlib.util
from pathlib import Path
import subprocess
import sys


def main() -> None:
    print(f"Installing into: {sys.executable}", flush=True)
    if not (3, 11) <= sys.version_info[:2] <= (3, 13):
        raise SystemExit(
            "This project's pinned requirements use Python 3.11-3.13. "
            f"The selected kernel uses Python {sys.version.split()[0]}. "
            "Select a Python 3.11-3.13 kernel and run setup again."
        )

    requirements = Path(__file__).resolve().parent / "requirements.txt"
    if not requirements.is_file():
        raise SystemExit(f"Missing requirements file: {requirements}")

    # Use this interpreter throughout, including when called from a notebook.
    # Calling a bare `pip` could install into a different Python environment.
    if importlib.util.find_spec("pip") is None:
        subprocess.run([sys.executable, "-m", "ensurepip", "--upgrade"], check=True)
    subprocess.run(
        [sys.executable, "-m", "pip", "install", "--quiet", "--disable-pip-version-check",
         "-r", str(requirements)],
        check=True,
    )

    # Verify in a fresh process so already-imported packages cannot mask changes.
    subprocess.run(
        [sys.executable, "-c",
         "import pandas, numpy, pyarrow, pycountry, jupyterlab, ipykernel, nbformat, nbclient; "
         "from src.preprocessing import clean_cost_of_living, clean_income, clean_property_prices; "
         "print('Dependency and preprocessing imports: OK')"],
        cwd=requirements.parent,
        check=True,
    )
    print(
        "Setup complete. Open data_preprocessing.ipynb with the same Python kernel, "
        "restart that kernel, then Run All.",
        flush=True,
    )


if __name__ == "__main__":
    try:
        main()
    except subprocess.CalledProcessError as error:
        print(
            "Setup did not complete. Check the error above. "
            f"The Python environment being used is: {sys.executable}",
            file=sys.stderr,
        )
        raise SystemExit(error.returncode) from None
