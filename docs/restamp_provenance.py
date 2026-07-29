"""Recompute derived provenance flags in committed results. Never touches a measurement.

`model_pinned` is not data, it is a conclusion drawn from `requested_model` and
`served_model`, both of which are recorded in the file. The rule that derived it was wrong
for a while: it looked for markers like "latest" in the identifier and so filed
`deepseek-chat` as pinned, even though the provider served `deepseek-v4-flash`. Asking for
one model and being handed another is the plainest possible evidence that a name floats.

Rather than re-run those evals to fix a boolean, this recomputes the flag from the model
names already in each file. It is committed so the edit is auditable: it reads
`requested_model` and `served_model`, writes `model_pinned`,
`served_differs_from_requested` and `reproducibility_note`, and asserts every metric is
byte-identical afterwards.

    python docs/restamp_provenance.py --check    # report, change nothing
    python docs/restamp_provenance.py            # rewrite in place
"""

from __future__ import annotations

import argparse
import glob
import json
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "harness", "src"))

from aau_harness.provenance import is_floating  # noqa: E402


def derive(requested: str | None, served: str | None) -> dict:
    redirected = bool(requested) and bool(served) and served != requested
    out = {
        "served_differs_from_requested": redirected,
        "model_pinned": bool(served) and not is_floating(served) and not redirected,
    }
    if redirected:
        out["reproducibility_note"] = (
            f"requested {requested!r} but the provider served {served!r}; the identifier "
            "is an alias, so re-running may exercise different weights."
        )
    return out


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--check", action="store_true", help="report without writing")
    args = ap.parse_args()

    changed = 0
    for path in sorted(glob.glob(os.path.join(ROOT, "*", "*", "results", "*.json"))):
        with open(path) as f:
            doc = json.load(f)
        prov = doc.get("provenance")
        if not prov:
            continue
        before_metrics = json.dumps(doc.get("results"), sort_keys=True)
        new = derive(prov.get("requested_model"), prov.get("served_model"))
        if all(prov.get(k) == v for k, v in new.items()):
            continue

        changed += 1
        rel = os.path.relpath(path, ROOT)
        print(f"{'would fix' if args.check else 'fixed'}: {rel}")
        for k, v in new.items():
            if prov.get(k) != v:
                print(f"    {k}: {prov.get(k)!r} -> {v!r}")
        if args.check:
            continue

        prov.update(new)
        # the guarantee that makes editing a committed result acceptable at all
        assert json.dumps(doc.get("results"), sort_keys=True) == before_metrics
        with open(path, "w") as f:
            json.dump(doc, f, indent=2)
            f.write("\n")

    print(f"\n{changed} file(s) {'need fixing' if args.check else 'updated'}")


if __name__ == "__main__":
    main()
