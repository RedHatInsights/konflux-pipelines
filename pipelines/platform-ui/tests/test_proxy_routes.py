"""Regression coverage for early E2E proxy route availability."""

import os
from pathlib import Path
import subprocess
import tempfile
import time
import unittest

import yaml


PIPELINE_PATH = Path(__file__).parents[1] / "docker-build-run-all-tests-v3.yaml"


class ProxyRoutesTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        with PIPELINE_PATH.open(encoding="utf-8") as pipeline_file:
            cls.pipeline = yaml.safe_load(pipeline_file)

        cls.task = next(
            task
            for task in cls.pipeline["spec"]["tasks"]
            if task["name"] == "run-e2e-tests"
        )["taskSpec"]
        cls.steps = cls.task["steps"]
        cls.volumes = {volume["name"]: volume for volume in cls.task["volumes"]}
        cls.proxy = next(
            sidecar
            for sidecar in cls.task["sidecars"]
            if sidecar["name"] == "frontend-dev-proxy"
        )

    def test_configmap_is_mounted_directly_without_hiding_writable_config(self):
        route_volume = self.volumes["proxy-routes-configmap"]
        self.assertEqual(
            route_volume["configMap"]["items"], [{"key": "routes", "path": "routes"}]
        )

        mounts = {mount["mountPath"]: mount for mount in self.proxy["volumeMounts"]}
        self.assertEqual(mounts["/config"]["name"], "proxy-config")
        self.assertNotIn("readOnly", mounts["/config"])
        self.assertEqual(mounts["/config/routes"]["name"], "proxy-routes-configmap")
        self.assertEqual(mounts["/config/routes"]["subPath"], "routes")
        self.assertTrue(mounts["/config/routes"]["readOnly"])
        self.assertEqual(self.volumes["proxy-config"]["emptyDir"], {})

    def test_route_validation_precedes_source_extraction_and_install(self):
        names = [step.get("name") for step in self.steps]
        validation_index = names.index("validate-proxy-routes")
        extraction_index = names.index("use-trusted-artifact")
        setup_index = names.index("workspace-setup")
        self.assertLess(validation_index, extraction_index)
        self.assertLess(validation_index, setup_index)

        validation = self.steps[validation_index]
        self.assertTrue(validation["securityContext"]["runAsNonRoot"])
        self.assertEqual(validation["securityContext"]["runAsUser"], 1000)
        self.assertIn("[ ! -f /configmap-data/routes ]", validation["script"])
        self.assertIn("[ ! -s /configmap-data/routes ]", validation["script"])
        self.assertNotIn("cp /configmap-data/routes", validation["script"])
        self.assertIn(
            {"name": "proxy-routes-configmap", "mountPath": "/configmap-data", "readOnly": True},
            validation["volumeMounts"],
        )

    def test_missing_and_empty_routes_fail_validation(self):
        validation_script = self.steps[0]["script"]
        with tempfile.TemporaryDirectory() as temporary_directory:
            route_path = Path(temporary_directory) / "routes"
            script = validation_script.replace(
                "/configmap-data/routes", str(route_path)
            )

            missing = subprocess.run(
                ["/bin/sh", "-c", script], text=True, capture_output=True, check=False
            )
            self.assertNotEqual(missing.returncode, 0)
            self.assertIn("routes file not found", missing.stdout)

            route_path.touch()
            empty = subprocess.run(
                ["/bin/sh", "-c", script], text=True, capture_output=True, check=False
            )
            self.assertNotEqual(empty.returncode, 0)
            self.assertIn("routes file is empty", empty.stdout)

            route_path.write_text("handle /example/* {\n}\n", encoding="utf-8")
            valid = subprocess.run(
                ["/bin/sh", "-c", script], text=True, capture_output=True, check=False
            )
            self.assertEqual(valid.returncode, 0, valid.stdout + valid.stderr)

    def test_proxy_starts_while_workspace_install_is_delayed(self):
        """A mounted route must let the sidecar start before npm setup finishes."""
        startup_script = self.pipeline["spec"]["params"]
        startup_script = next(
            parameter["default"]
            for parameter in startup_script
            if parameter["name"] == "e2e-proxy-startup-script"
        )

        with tempfile.TemporaryDirectory() as temporary_directory:
            root = Path(temporary_directory)
            route_path = root / "routes"
            route_path.write_text("handle /example/* {\n}\n", encoding="utf-8")
            bin_directory = root / "bin"
            bin_directory.mkdir()

            wget = bin_directory / "wget"
            wget.write_text("#!/bin/sh\nexit 0\n", encoding="utf-8")
            wget.chmod(0o755)

            caddy = bin_directory / "caddy"
            caddy.write_text(
                "#!/bin/sh\n"
                'if [ -f "$INSTALL_DONE" ]; then\n'
                '  printf after > "$PROXY_STARTED"\n'
                "else\n"
                '  printf before > "$PROXY_STARTED"\n'
                "fi\n",
                encoding="utf-8",
            )
            caddy.chmod(0o755)

            install_started = root / "install-started"
            install_done = root / "install-done"
            proxy_started = root / "proxy-started"
            install_code = (
                "import pathlib, time; "
                f"pathlib.Path({str(install_started)!r}).touch(); "
                "time.sleep(1.5); "
                f"pathlib.Path({str(install_done)!r}).touch()"
            )
            install = subprocess.Popen(["python3", "-c", install_code])
            try:
                deadline = time.monotonic() + 5
                while not install_started.exists() and time.monotonic() < deadline:
                    time.sleep(0.01)
                self.assertTrue(install_started.exists(), "delayed setup did not start")

                env = os.environ.copy()
                env.update(
                    {
                        "PATH": f"{bin_directory}:{env['PATH']}",
                        "INSTALL_DONE": str(install_done),
                        "PROXY_STARTED": str(proxy_started),
                        "APP_PORT": "8000",
                        "READINESS_PATH": "",
                        "READINESS_TIMEOUT": "10",
                        "HCC_ENV_URL": "https://example.test",
                    }
                )
                script = startup_script.replace("/config/routes", str(route_path))
                proxy = subprocess.run(
                    ["/bin/sh", "-c", script],
                    env=env,
                    text=True,
                    capture_output=True,
                    timeout=5,
                    check=False,
                )
                self.assertEqual(proxy.returncode, 0, proxy.stdout + proxy.stderr)
                self.assertEqual(proxy_started.read_text(encoding="utf-8"), "before")
            finally:
                install.wait(timeout=5)


if __name__ == "__main__":
    unittest.main()
