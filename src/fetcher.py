"""Download COT data from CFTC website."""

import io
import zipfile
from pathlib import Path
from typing import Optional

import requests

from .config import Config, default_config


class COTFetcher:
    """Fetch COT data from CFTC website."""

    def __init__(self, config: Optional[Config] = None):
        self.config = config or default_config

    def fetch_legacy_data(self, year: int, force: bool = False) -> Path:
        """
        Download Legacy COT report for a specific year.

        Args:
            year: Year to download
            force: If True, re-download even if file exists

        Returns:
            Path to the downloaded/extracted file
        """
        output_file = self.config.data_dir / f"legacy_{year}.txt"

        if output_file.exists() and not force:
            print(f"Legacy {year} data already exists, skipping download")
            return output_file

        url = self.config.get_legacy_url(year)
        print(f"Downloading Legacy COT data for {year}...")

        try:
            response = requests.get(url, timeout=60)
            response.raise_for_status()

            # Extract from zip
            with zipfile.ZipFile(io.BytesIO(response.content)) as zf:
                # Find the .txt file in the zip
                txt_files = [f for f in zf.namelist() if f.endswith(".txt")]
                if not txt_files:
                    raise ValueError(f"No .txt file found in zip for year {year}")

                # Extract the first txt file
                with zf.open(txt_files[0]) as src:
                    content = src.read()
                    output_file.write_bytes(content)

            print(f"Saved Legacy {year} data to {output_file}")
            return output_file

        except requests.RequestException as e:
            print(f"Error downloading Legacy {year} data: {e}")
            raise

    def fetch_disaggregated_data(self, year: int, force: bool = False) -> Path:
        """
        Download Disaggregated COT report for a specific year.

        Args:
            year: Year to download
            force: If True, re-download even if file exists

        Returns:
            Path to the downloaded/extracted file
        """
        output_file = self.config.data_dir / f"disaggregated_{year}.txt"

        if output_file.exists() and not force:
            print(f"Disaggregated {year} data already exists, skipping download")
            return output_file

        url = self.config.get_disaggregated_url(year)
        print(f"Downloading Disaggregated COT data for {year}...")

        try:
            response = requests.get(url, timeout=60)
            response.raise_for_status()

            # Extract from zip
            with zipfile.ZipFile(io.BytesIO(response.content)) as zf:
                # Find the .txt file in the zip
                txt_files = [f for f in zf.namelist() if f.endswith(".txt")]
                if not txt_files:
                    raise ValueError(f"No .txt file found in zip for year {year}")

                # Extract the first txt file
                with zf.open(txt_files[0]) as src:
                    content = src.read()
                    output_file.write_bytes(content)

            print(f"Saved Disaggregated {year} data to {output_file}")
            return output_file

        except requests.RequestException as e:
            print(f"Error downloading Disaggregated {year} data: {e}")
            raise

    def fetch_all_data(self, force: bool = False) -> dict[str, list[Path]]:
        """
        Download all COT data for configured years.

        Args:
            force: If True, re-download all files

        Returns:
            Dictionary with 'legacy' and 'disaggregated' keys containing file paths
        """
        years = self.config.get_years_to_fetch()
        legacy_files = []
        disaggregated_files = []

        for year in years:
            try:
                legacy_files.append(self.fetch_legacy_data(year, force=force))
            except Exception as e:
                print(f"Warning: Could not fetch Legacy {year}: {e}")

            try:
                disaggregated_files.append(
                    self.fetch_disaggregated_data(year, force=force)
                )
            except Exception as e:
                print(f"Warning: Could not fetch Disaggregated {year}: {e}")

        return {"legacy": legacy_files, "disaggregated": disaggregated_files}

    def get_cached_files(self) -> dict[str, list[Path]]:
        """
        Get list of already downloaded files.

        Returns:
            Dictionary with 'legacy' and 'disaggregated' keys containing file paths
        """
        legacy_files = sorted(self.config.data_dir.glob("legacy_*.txt"))
        disaggregated_files = sorted(self.config.data_dir.glob("disaggregated_*.txt"))

        return {"legacy": legacy_files, "disaggregated": disaggregated_files}
