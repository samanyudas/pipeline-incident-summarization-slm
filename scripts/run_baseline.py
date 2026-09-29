"""Run the unchanged Qwen model with a chosen incident-summary prompt."""

import argparse
import hashlib
import json
import re
import subprocess
from pathlib import Path


root = Path(__file__).resolve().parents[1]
model = root / "models/Qwen3.5-0.8B-BF16.gguf"
if not model.is_file():
    raise SystemExit(f"Model file missing: {model}")
parser = argparse.ArgumentParser(description=__doc__)
prompt_source = parser.add_mutually_exclusive_group()
prompt_source.add_argument("--instruction-file", type=Path)
prompt_source.add_argument("--dataset-manifest", type=Path)
parser.add_argument("--label", default="baseline")
parser.add_argument("report_numbers", nargs="+")
args = parser.parse_args()
if args.label != "baseline" and not (args.instruction_file or args.dataset_manifest):
    parser.error("--label requires --instruction-file or --dataset-manifest")
if (args.instruction_file or args.dataset_manifest) and args.label == "baseline":
    parser.error("A custom prompt source requires a non-baseline --label")
if not re.fullmatch(r"[a-z0-9_]+", args.label):
    parser.error("--label may contain only lowercase letters, numbers, and underscores")
instruction = args.instruction_file.read_text(encoding="utf-8").strip() if args.instruction_file else None

headings = (
    "When", "Where", "What failed", "What happened", "Root cause",
    "Contributing factors", "Evidence / certainty",
)
development = json.loads((root / "examples/evaluation_candidates.json").read_text(encoding="utf-8"))
development_ids = {entry["report_number"] for entry in development["selection"]}
if args.dataset_manifest:
    try:
        dataset = json.loads(args.dataset_manifest.read_text(encoding="utf-8"))
        if dataset["schema_version"] != 1 or dataset["format"] != "messages-only-jsonl":
            raise ValueError("Unsupported dataset manifest schema or format")
        training_name = dataset["training_file"]
        if not isinstance(training_name, str) or Path(training_name).name != training_name:
            raise ValueError("training_file must name a local sibling file")
        training_path = args.dataset_manifest.parent / training_name
        if training_path.resolve().parent != args.dataset_manifest.parent.resolve():
            raise ValueError("training_file must resolve to a local sibling file")
        training_bytes = training_path.read_bytes()
        if hashlib.sha256(training_bytes).hexdigest() != dataset["training_sha256"]:
            raise ValueError("Dataset training-file hash mismatch")
        if dataset["source_sha256"] != development["source_sha256"]:
            raise ValueError("Dataset and development source hashes differ")
        instruction = dataset["system_instruction"]
        if not isinstance(instruction, str) or not instruction.strip():
            raise ValueError("Dataset system instruction is empty")
        training_rows = [json.loads(line) for line in training_bytes.decode("utf-8").splitlines()]
        if not training_rows or len(training_rows) != dataset["training_records"]:
            raise ValueError("Dataset training-record count mismatch")
        if any(row["messages"][0] != {"role": "system", "content": instruction} for row in training_rows):
            raise ValueError("Dataset instruction differs from training examples")
    except (OSError, ValueError, KeyError, TypeError, IndexError) as error:
        raise SystemExit(f"Invalid dataset manifest: {error}") from error

# Validate the complete request before writing prompts or invoking the model.
for report_number in args.report_numbers:
    if report_number not in development_ids:
        raise SystemExit(f"{report_number} is not a development report")

for report_number in args.report_numbers:
    case_path = root / "examples" / f"incident_{report_number}.json"
    case = json.loads(case_path.read_text(encoding="utf-8"))
    if case["source_report_number"] != report_number:
        raise SystemExit(f"Report number mismatch in {case_path}")

    if args.dataset_manifest:
        prompt = json.dumps(case["input"], ensure_ascii=False, sort_keys=True)
    else:
        prompt = "Incident report fields:\n" + "\n".join(
            f"{key}: {value}" for key, value in case["input"].items()
        ) + "\n"
    prompt_name = f"incident_{report_number}_prompt.txt" if args.label == "baseline" else f"incident_{report_number}_{args.label}_prompt.txt"
    prompt_path = root / "examples" / prompt_name
    prompt_path.write_text(prompt, encoding="utf-8")

    command = [
        "llama-cli", "-m", str(model), "--reasoning", "off",
        "-sys", instruction or case["system_instruction"], "-f", str(prompt_path),
        "-st", "--no-display-prompt", "-n", "700", "--temp", "0",
        "-c", "4096",
    ]
    result = subprocess.run(command, capture_output=True, text=True, timeout=180)
    raw_prefix = root / "examples" / f"incident_{report_number}_{args.label}"
    raw_stdout_path = raw_prefix.with_name(raw_prefix.name + "_stdout.txt")
    raw_stderr_path = raw_prefix.with_name(raw_prefix.name + "_stderr.txt")
    raw_stdout_path.write_text(result.stdout, encoding="utf-8")
    raw_stderr_path.write_text(result.stderr, encoding="utf-8")
    if result.returncode:
        raise SystemExit(f"Qwen failed on {report_number}: {result.stderr[-1500:]}")

    heading_prefix = r"(?m)^[ \t]*(?:(?:[-*]|[0-9]+[.)])[ \t]+)?(?:\*\*)?"
    match = re.search(heading_prefix + r"When:(?:\*\*)?", result.stdout)
    end = result.stdout.find("\n[ Prompt:", match.start() if match else 0)
    if not match or end < 0:
        raise SystemExit(f"Could not isolate Qwen's answer for {report_number}; raw output saved to {raw_stdout_path}")
    answer = result.stdout[match.start():end].rstrip("\r\n") + "\n"
    answer_path = root / "examples" / f"incident_{report_number}_{args.label}.txt"
    answer_path.write_text(answer, encoding="utf-8")
    missing = [heading for heading in headings if not re.search(heading_prefix + re.escape(heading) + r":(?:\*\*)?", answer)]
    print(f"{report_number}: saved {answer_path.relative_to(root)}; missing headings: {missing}")
