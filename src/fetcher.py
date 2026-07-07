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

    def fetch_current_legacy_data(self, force: bool = False) -> Path:
        """Download current-week Legacy futures COT report."""
        output_file = self.config.data_dir / "legacy_current.txt"

        if output_file.exists() and not force:
            print("Current Legacy data already exists, skipping download")
            return output_file

        url = self.config.get_current_legacy_url()
        print("Downloading current Legacy COT data...")
        content = self._download_current_text(url)
        header = self._header_from_cached_file("legacy_*.txt")
        output_file.write_text(f"{header}\n{content}\n", encoding="utf-8")

        print(f"Saved current Legacy data to {output_file}")
        return output_file

    def fetch_current_disaggregated_data(self, force: bool = False) -> Path:
        """Download current-week Disaggregated futures COT report."""
        output_file = self.config.data_dir / "disaggregated_current.txt"

        if output_file.exists() and not force:
            print("Current Disaggregated data already exists, skipping download")
            return output_file

        url = self.config.get_current_disaggregated_url()
        print("Downloading current Disaggregated COT data...")
        content = self._download_current_text(url)
        header = self._header_from_cached_file("disaggregated_*.txt")
        output_file.write_text(f"{header}\n{content}\n", encoding="utf-8")

        print(f"Saved current Disaggregated data to {output_file}")
        return output_file

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

        try:
            legacy_files.append(self.fetch_current_legacy_data(force=force))
        except Exception as e:
            print(f"Warning: Could not fetch current Legacy data: {e}")

        try:
            disaggregated_files.append(
                self.fetch_current_disaggregated_data(force=force)
            )
        except Exception as e:
            print(f"Warning: Could not fetch current Disaggregated data: {e}")

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

    def _download_current_text(self, url: str) -> str:
        response = requests.get(url, timeout=60)
        response.raise_for_status()
        content = response.text.strip()
        if not content:
            raise ValueError(f"Empty CFTC current report: {url}")
        if content.lstrip().startswith("<"):
            raise ValueError(f"CFTC current report returned HTML instead of text: {url}")
        return content

    def _header_from_cached_file(self, pattern: str) -> str:
        for path in sorted(self.config.data_dir.glob(pattern), reverse=True):
            if path.name.endswith("_current.txt"):
                continue
            if not path.is_file() or path.stat().st_size == 0:
                continue
            with path.open(encoding="utf-8", errors="ignore") as handle:
                header = handle.readline().strip()
            if header:
                return header
        raise FileNotFoundError(f"No cached annual file found for header pattern {pattern}")
