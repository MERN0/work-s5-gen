"""Fixed vocabularies shared by prompts and the deterministic validator."""

ACTION_VERBS = {"SET", "WAIT"}
VERIFICATION_VERB = "VERIFY"
ALL_ACTION_VERBS = ACTION_VERBS | {VERIFICATION_VERB}

TEST_START_MARKER = "Test_start"
TEST_END_MARKER = "End_of_test"

# The fixed 9-item ODC trigger taxonomy. A test case's odc_trigger, when set,
# must be one of these — only classify when it clearly applies, else leave blank.
ODC_TRIGGER_TAXONOMY: list[str] = [
    "Test Coverage",
    "Test Variation",
    "Test Sequencing",
    "Test Interaction",
    "Workload Volume/Stress",
    "Recovery/Exception",
    "Start-up/Restart",
    "Hardware Configuration",
    "Software Configuration",
]

MODE_OF_EXECUTION_VALUES: list[str] = ["Manual", "Automated", "Semi-automated"]
PRIORITY_VALUES: list[str] = ["P1", "P2", "P3", "P4", "P5"]
