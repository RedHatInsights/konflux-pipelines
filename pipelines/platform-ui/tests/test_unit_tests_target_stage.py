"""Regression coverage for target-stage forwarding in the unit-test pipeline."""

from pathlib import Path
import unittest

import yaml


PIPELINE_PATH = Path(__file__).parents[1] / "docker-build-run-unit-tests.yaml"


class UnitTestsTargetStageTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        with PIPELINE_PATH.open(encoding="utf-8") as pipeline_file:
            cls.pipeline = yaml.safe_load(pipeline_file)

        cls.params = {
            parameter["name"]: parameter
            for parameter in cls.pipeline["spec"]["params"]
        }
        cls.tasks = {
            task["name"]: task for task in cls.pipeline["spec"]["tasks"]
        }

    def test_target_stage_is_optional_and_preserves_legacy_defaults(self):
        target_stage = self.params["target-stage"]
        self.assertEqual(target_stage["type"], "string")
        self.assertEqual(target_stage["default"], "")
        self.assertEqual(self.params["hermetic"]["default"], "false")
        self.assertEqual(self.params["prefetch-input"]["default"], "")

    def test_empty_and_named_targets_reach_build_and_coverity(self):
        task_param_names = {
            "build-container": "TARGET_STAGE",
            "sast-coverity-check": "TARGET_STAGE",
        }
        for task_name, task_param_name in task_param_names.items():
            with self.subTest(task=task_name):
                bindings = {
                    parameter["name"]: parameter["value"]
                    for parameter in self.tasks[task_name]["params"]
                }
                self.assertEqual(
                    bindings[task_param_name], "$(params.target-stage)"
                )

                for target_stage in ("", "deploy", "artifact"):
                    with self.subTest(target_stage=target_stage):
                        forwarded = bindings[task_param_name].replace(
                            "$(params.target-stage)", target_stage
                        )
                        self.assertEqual(forwarded, target_stage)

    def test_target_selection_does_not_change_hermetic_or_prefetch_bindings(self):
        for task_name in ("build-container", "sast-coverity-check"):
            with self.subTest(task=task_name):
                bindings = {
                    parameter["name"]: parameter["value"]
                    for parameter in self.tasks[task_name]["params"]
                }
                self.assertEqual(bindings["HERMETIC"], "$(params.hermetic)")
                self.assertEqual(
                    bindings["PREFETCH_INPUT"], "$(params.prefetch-input)"
                )


if __name__ == "__main__":
    unittest.main()
