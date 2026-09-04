# CPython workspace observation research notes

Research checked on 2026-09-04. This control answers a deliberately narrow question: which regular
files inside the declared workspace did the tested CPython processes attempt to read or execute,
what digest was sampled immediately before each application open, and do those paths still carry
the same digest when a release is bound?

## Source-to-control ledger

| Primary source fact | Executable design choice | Explicit non-claim |
|---|---|---|
| Python's `site` module is imported during initialization unless `-S` is used, and then attempts to import `sitecustomize` | Matrix commands already require the script at `argv[1]`, so interpreter flags cannot precede it; the runner prepends an exact observer directory to `PYTHONPATH` and requires one startup marker from every expected process | Environment-based startup is not native pre-initialization instrumentation and a trusted command can interfere with it |
| CPython publishes stable audit-event argument schemas within a feature release for events such as `open`, `import`, `exec`, `cpython.run_file`, `socket.connect`, and `subprocess.Popen` | A Python audit hook records only normalized workspace paths, pre-open size/digest observations, and coarse capability classes; network, process, and other event arguments are discarded | Event availability is implementation-specific and event presence does not establish intent, harm, or policy violation |
| Python's `sys.addaudithook` documentation explicitly says Python-level hooks are not suitable for a sandbox and malicious code can bypass them | The receipt states this boundary, retains the exact observer bytes, and treats commands as trusted local staging code | A green observation is not containment, malware analysis, enforcement, or evidence against a malicious adapter |
| PEP 578 says runtime audit hooks provide visibility into otherwise difficult-to-observe actions and separately explains why the feature is not a sandbox | Missing startup markers, malformed traces, symbolic paths, workspace writes, changing digests, and observer-byte drift fail closed | The tool does not claim complete operating-system visibility or that every possible file or native access raises a Python event |
| SLSA build provenance represents known resolved dependencies by URI and digest and describes dependency completeness as best effort | Runtime-only workspace inputs are preserved as path, size, and SHA-256—not copied content—and Release Binding re-hashes those exact paths | This is not SLSA provenance, has no builder identity, and does not establish dependency trust or completeness |

## Premise checks

1. **Static reachability is not runtime use.** A file can be imported on an unexercised branch, and
   a configuration file can affect behavior without appearing in Python import syntax. Static and
   observed sets therefore remain separate.
2. **A missing process is missing evidence.** Semantic, crash, and race runners know how many
   primary processes they start. The reference must produce exactly 12, 24, and 73 startup markers;
   zero or extra markers are structural failures.
3. **Observation must start before the adapter script.** The runner injects the observer through
   `sitecustomize` and binds the exact injected bytes into the matrix pack. Merely importing a
   logger from adapter code would leave startup and import behavior outside the evidence boundary.
4. **Read evidence should not become an accidental secret archive.** Runtime-only content may be
   configuration, policy, or data. The public pack retains normalized path, size, and digest only;
   it never embeds those bytes. Users must still keep proprietary paths and data out of public
   runs.
5. **A digest sample is not the bytes consumed.** The hook samples a regular file immediately
   before the original application open and compares it again after the run. A time-of-check/time-
   of-use window remains and is stated in every receipt.
6. **Workspace writes destroy clean input evidence.** A process that opens a workspace path with
   write capability fails the observation. Crash and race state belongs in the runner-provided
   temporary directories, not beside reviewed source.
7. **Capability events are signals, not verdicts.** Network, subprocess, native-load, dynamic-code,
   and instrumentation-change classes are disclosed without target arguments and do not
   automatically convert behavioral evidence into a failure.
8. **Release comparison is not re-execution.** Release Binding re-hashes tested paths and detects a
   substituted runtime policy, but it does not rerun the release or identify a deployed workload.

## Official sources

- [Python documentation — `site` and `sitecustomize`](https://docs.python.org/3/library/site.html)
- [Python documentation — `sys.addaudithook` and its sandbox warning](https://docs.python.org/3/library/sys.html#sys.addaudithook)
- [Python documentation — CPython audit events](https://docs.python.org/3/library/audit_events.html)
- [PEP 578 — Python Runtime Audit Hooks](https://peps.python.org/pep-0578/)
- [PEP 551 — Security transparency in the Python runtime](https://peps.python.org/pep-0551/)
- [Python command-line and environment behavior](https://docs.python.org/3/using/cmdline.html)
- [SLSA 1.2 build provenance](https://slsa.dev/spec/v1.2/build-provenance)
- [SLSA 1.2 artifact verification](https://slsa.dev/spec/v1.2/verifying-artifacts)
