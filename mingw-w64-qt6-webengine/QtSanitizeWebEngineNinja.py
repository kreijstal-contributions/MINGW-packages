#!/usr/bin/env python3
import pathlib
import re
import sys


def is_thirdparty_object(path: str) -> bool:
    path = path.removeprefix("./")
    return bool(
        re.match(r"obj/(?:.*third_party|net/third_party|skia)/", path)
    )


build_dir = pathlib.Path(sys.argv[1])
changed_files = 0
changed_edges = 0
removed_inputs = 0

for ninja_file in (build_dir / "obj").rglob("*.ninja"):
    original = ninja_file.read_text(encoding="utf-8")
    output_lines = []
    file_changed = False

    for line in original.splitlines(keepends=True):
        ending = "\r\n" if line.endswith("\r\n") else "\n" if line.endswith("\n") else ""
        content = line.removesuffix(ending)
        match = re.match(r"^build (.+): alink(?: (.*))?$", content)
        if match is None:
            output_lines.append(line)
            continue

        outputs = match.group(1)
        inputs = (match.group(2) or "").split()
        output_paths = [token for token in outputs.split() if token != "|"]
        make_phony = any(
            is_thirdparty_object(path)
            or pathlib.PurePosixPath(path).name == "libQtWebEngineCoreSandbox.a"
            for path in output_paths
        )

        if make_phony:
            replacement = f"build {outputs}: phony{ending}"
            removed_inputs += len(inputs)
        else:
            filtered_inputs = [
                token for token in inputs if not is_thirdparty_object(token)
            ]
            removed_inputs += len(inputs) - len(filtered_inputs)
            replacement = (
                f"build {outputs}: alink"
                + (f" {' '.join(filtered_inputs)}" if filtered_inputs else "")
                + ending
            )

        if replacement != line:
            file_changed = True
            changed_edges += 1
        output_lines.append(replacement)

    if file_changed:
        ninja_file.write_text("".join(output_lines), encoding="utf-8", newline="")
        changed_files += 1

print(
    f"sanitized_files={changed_files} "
    f"sanitized_edges={changed_edges} "
    f"removed_inputs={removed_inputs}"
)
