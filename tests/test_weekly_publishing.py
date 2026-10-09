import importlib.util
import io
import json
import os
import subprocess
import tempfile
import unittest
from pathlib import Path
from datetime import datetime
import zipfile
from unittest.mock import Mock, patch


def load_script(name):
    spec = importlib.util.spec_from_file_location(name, Path(__file__).resolve().parents[1] / "scripts" / f"{name}.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


publisher = load_script("publish_to_csfox_gh")
runner = load_script("run_cotpy_weekly")


class PublishingTests(unittest.TestCase):
    def test_transient_failures_and_timeout_recover(self):
        failures = [
            subprocess.TimeoutExpired("gh", 120),
            subprocess.CompletedProcess([], 1, b"", b"network is down"),
            subprocess.CompletedProcess([], 1, b"", b"Please try resubmitting your request (HTTP 400)"),
            subprocess.CompletedProcess([], 0, b'{"sha":"ok"}', b""),
        ]
        with patch.object(publisher, "_gh_command", return_value="gh"), patch.object(publisher.subprocess, "run", side_effect=failures) as run, patch.object(publisher.time, "sleep"):
            self.assertEqual(publisher._gh_json("test"), {"sha": "ok"})
            self.assertEqual(run.call_count, 4)
            self.assertEqual(run.call_args.kwargs["timeout"], 120)

    def test_permanent_error_reports_actual_attempts(self):
        failure = subprocess.CompletedProcess([], 1, b"", b"HTTP 403 forbidden")
        with patch.object(publisher, "_gh_command", return_value="gh"), patch.object(publisher.subprocess, "run", return_value=failure) as run:
            with self.assertRaisesRegex(RuntimeError, "after 1 attempt"):
                publisher._gh_json("test")
            self.assertEqual(run.call_count, 1)

    def test_retry_exhaustion(self):
        with patch.object(publisher, "_gh_command", return_value="gh"), patch.object(publisher.subprocess, "run", side_effect=subprocess.TimeoutExpired("gh", 120)) as run, patch.object(publisher.time, "sleep"):
            with self.assertRaisesRegex(RuntimeError, "after 5 attempt"):
                publisher._gh_json("test")
            self.assertEqual(run.call_count, 5)

    def test_unchanged_reports_still_verify_pages(self):
        content = b"dashboard"
        responses = [
            {"login": "test"}, {"object": {"sha": "commit"}},
            {"tree": {"sha": "tree"}},
            {"tree": [{"path": "cotpy/charts/dashboard.html", "sha": publisher._blob_sha(content)}]},
            {"sha": "tree"},
        ]
        source = Mock()
        source.read_bytes.return_value = content
        with patch.object(publisher.os, "chdir"), patch.object(publisher, "DRY_RUN", False), patch.object(publisher, "TRIGGER_PAGES", True), patch.object(publisher, "_gh_json", side_effect=responses), patch.object(publisher, "_publish_files", return_value=[(source, "cotpy/charts/dashboard.html")]), patch.object(publisher, "_index_html", return_value={}), patch.object(publisher, "_site_index", return_value=""), patch.object(publisher, "_create_blob", return_value={"sha": "index"}) as blob, patch.object(publisher, "_ensure_pages") as pages:
            self.assertEqual(publisher.main(), 0)
            pages.assert_called_once_with(publisher._repo_name(), "commit")
            # Only the generated root index needs uploading.
            blob.assert_called_once()

    def test_pages_waits_for_correct_commit_and_live_content(self):
        pages = {"source": {"branch": publisher.BRANCH, "path": "/"}, "html_url": "https://example.com/"}
        old = {"commit": "old", "status": "built"}
        built = {"commit": "new", "status": "built"}
        response = Mock()
        response.__enter__ = Mock(return_value=response)
        response.__exit__ = Mock(return_value=False)
        response.read.side_effect = [b"old", b"new"]
        dashboard = Mock()
        dashboard.read_bytes.return_value = b"new"
        with patch.object(publisher, "_gh_json", side_effect=[pages, old, {}, old, built, built]) as api, patch.object(publisher, "DASHBOARD", dashboard), patch.object(publisher, "urlopen", return_value=response), patch.object(publisher.time, "sleep"):
            publisher._ensure_pages("owner/repo", "new")
            self.assertEqual(response.read.call_count, 2)
            self.assertIn(unittest.mock.call("repos/owner/repo/pages/builds", method="POST"), api.call_args_list)

    def test_failed_pages_build_is_failure(self):
        pages = {"source": {"branch": publisher.BRANCH, "path": "/"}, "html_url": "https://example.com/"}
        with patch.object(publisher, "_gh_json", side_effect=[pages, {"commit": "new", "status": "building"}, {"commit": "new", "status": "errored"}]), patch.object(publisher, "DASHBOARD", Mock()):
            with self.assertRaisesRegex(RuntimeError, "build failed"):
                publisher._ensure_pages("owner/repo", "new")


class RunnerTests(unittest.TestCase):
    def write_current_reports(self, directory, report_date):
        data = Path(directory) / "data"
        data.mkdir()
        for kind in ("legacy", "disaggregated"):
            column = ("As of Date in Form YYYY-MM-DD" if kind == "legacy"
                      else "Report_Date_as_YYYY-MM-DD")
            (data / f"{kind}_current.txt").write_text(
                f'Market_and_Exchange_Names,{column}\nGOLD,{report_date}\n'
            )

    def test_freshly_downloaded_stale_report_is_rejected(self):
        with tempfile.TemporaryDirectory() as directory, patch.object(runner, "PROJECT", Path(directory)), patch.object(runner, "datetime") as clock:
            clock.now.return_value = datetime(2026, 10, 3)
            self.write_current_reports(directory, "2026-09-22")
            with self.assertRaisesRegex(RuntimeError, "Stale COT report"):
                runner.check_downloads(0)

    def test_new_year_accepts_previous_year_weekly_report_without_new_archive(self):
        with tempfile.TemporaryDirectory() as directory, patch.object(runner, "PROJECT", Path(directory)), patch.object(runner, "datetime") as clock:
            clock.now.return_value = datetime(2027, 1, 2)
            self.write_current_reports(directory, "2026-12-29")
            runner.check_downloads(0)

    def test_release_delay_override(self):
        with tempfile.TemporaryDirectory() as directory, patch.object(runner, "PROJECT", Path(directory)), patch.object(runner, "datetime") as clock, patch.dict(os.environ, {"COTPY_MAX_REPORT_AGE_DAYS": "14"}):
            clock.now.return_value = datetime(2026, 10, 3)
            self.write_current_reports(directory, "2026-09-22")
            runner.check_downloads(0)

    def test_failed_current_week_download_cannot_use_cached_week(self):
        with tempfile.TemporaryDirectory() as directory, patch.object(runner, "PROJECT", Path(directory)):
            self.write_current_reports(directory, "2026-09-29")
            with self.assertRaisesRegex(RuntimeError, "not refreshed"):
                runner.check_downloads(10**12)

    def test_concurrent_runner_skips_work(self):
        import fcntl
        with tempfile.TemporaryDirectory() as directory, patch.object(runner, "PROJECT", Path(directory)), patch.object(runner, "run_stage") as stage:
            logs = Path(directory) / "logs"
            logs.mkdir()
            with (logs / "weekly.lock").open("a") as lock:
                fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
                self.assertEqual(runner.main(), 0)
                stage.assert_not_called()

    def test_incomplete_market_charts_fail(self):
        import main
        with patch.object(main, "get_enabled_display_names", return_value=["GOLD"]), patch.object(main, "load_and_analyze_data", return_value=(Mock(), Mock())), patch.object(main, "COTVisualizer") as visualizer:
            visualizer.return_value.save_all_charts.return_value = {"dashboard": Path("old.html")}
            with self.assertRaisesRegex(RuntimeError, "GOLD_interactive"):
                main.cmd_market_charts(Mock())

    def test_publish_retries_without_regenerating(self):
        with patch.object(runner, "record"), patch.object(runner, "run_command", side_effect=[RuntimeError("offline"), None]) as run, patch.object(runner.time, "sleep"):
            runner.run_stage("publish", [["publisher"]], 3600)
            self.assertEqual(run.call_args_list, [unittest.mock.call(["publisher"], 3600)] * 2)

    def test_failure_is_recorded_and_propagated(self):
        with tempfile.TemporaryDirectory() as directory, patch.object(runner, "STATUS", Path(directory) / "status.json"), patch.object(runner, "run_command", side_effect=RuntimeError("offline")), patch.object(runner.time, "sleep"):
            with self.assertRaisesRegex(RuntimeError, "offline"):
                runner.run_stage("publish", [["publisher"]], 3600)
            status = json.loads(runner.STATUS.read_text())
            self.assertEqual((status["state"], status["attempt"]), ("failed", 3))

    def test_missing_download_rejected(self):
        with tempfile.TemporaryDirectory() as directory, patch.object(runner, "PROJECT", Path(directory)):
            with self.assertRaisesRegex(RuntimeError, "not refreshed"):
                runner.check_downloads(0)

    def test_timeout_kills_process_group(self):
        process = Mock(pid=123)
        process.wait.side_effect = [subprocess.TimeoutExpired("test", 1), 0]
        with patch.object(runner.subprocess, "Popen", return_value=process), patch.object(runner.os, "killpg") as kill:
            with self.assertRaises(subprocess.TimeoutExpired):
                runner.run_command(["test"], 1)
            kill.assert_called_once_with(123, runner.signal.SIGKILL)


class FetchingTests(unittest.TestCase):
    def test_update_reuses_history_but_refreshes_mutable_archives_and_week(self):
        from src.fetcher import COTFetcher
        archive = io.BytesIO()
        with zipfile.ZipFile(archive, "w") as bundle:
            bundle.writestr("report.txt", "header\nnew annual data")
        with tempfile.TemporaryDirectory() as directory:
            config = Mock(data_dir=Path(directory))
            fetcher = COTFetcher(config)
            year = datetime.now().year
            for kind in ("legacy", "disaggregated"):
                for suffix in (str(year - 1), str(year), "current"):
                    (config.data_dir / f"{kind}_{suffix}.txt").write_text("header\nold data")
            with patch("src.fetcher.requests.get", return_value=Mock(content=archive.getvalue())) as get, patch.object(fetcher, "_download_current_text", return_value="fresh week") as current:
                for method in (fetcher.fetch_legacy_data, fetcher.fetch_disaggregated_data):
                    self.assertIn("old data", method(year - 1).read_text())
                    self.assertIn("new annual data", method(year).read_text())
                self.assertIn("fresh week", fetcher.fetch_current_legacy_data().read_text())
                self.assertIn("fresh week", fetcher.fetch_current_disaggregated_data().read_text())
                self.assertEqual(get.call_count, 2)
                self.assertEqual(current.call_count, 2)

    def test_current_download_failure_propagates(self):
        from src.fetcher import COTFetcher
        fetcher = COTFetcher(Mock())
        fetcher.config.get_years_to_fetch.return_value = []
        with patch.object(fetcher, "fetch_current_legacy_data", side_effect=RuntimeError("offline")), patch.object(fetcher, "fetch_current_disaggregated_data", return_value=Path("fresh")):
            with self.assertRaisesRegex(RuntimeError, "Could not refresh current COT reports: Legacy: offline"):
                fetcher.fetch_all_data()


if __name__ == "__main__":
    unittest.main()
