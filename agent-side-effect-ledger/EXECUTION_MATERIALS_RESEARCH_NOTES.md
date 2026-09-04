# Python execution-material research notes

Research checked on 2026-09-04. This control answers a deliberately narrow question: which regular
workspace Python files are statically reachable from the declared adapter entrypoint under the
tool's bounded search model, and are those exact bytes preserved with the behavioral evidence?

## Source-to-control ledger

| Primary source fact | Executable design choice | Explicit non-claim |
|---|---|---|
| Python's import statement first searches for a named module, and import behavior can also be invoked or modified through `__import__`, `importlib`, `sys.meta_path`, `sys.path`, and hooks | Parse ordinary `import` and `from ... import ...` syntax transitively; reject obvious dynamic loading calls; enumerate matching files on each source file's workspace ancestor paths | Static analysis is not a complete description of Python's extensible runtime import machinery |
| Python's path-based finder can load source, bytecode, extension modules, zip files, and other locations from an installation-dependent search path | Capture regular local source files only and disclose unresolved module names | The set does not capture the interpreter, bytecode, native modules, zip imports, installed distributions, or actual runtime search order |
| SLSA provenance uses `resolvedDependencies` for known artifacts that may affect a build and calls dependency completeness best effort | Preserve each captured source path, size, SHA-256 digest, and bytes in a self-contained material set | The AAU file is not SLSA provenance, has no builder identity, and does not claim dependency completeness |
| SLSA verification guidance treats dependency verification as a separate policy concern, not something provenance performs automatically | Matrix verification recomputes every material byte and Release Binding compares matrix and release material-set digests | Digest equality is not source trust, vulnerability analysis, signature verification, or proof that those bytes executed |

## Premise checks

1. **An entrypoint is not the implementation.** A one-line adapter can import all consequential
   behavior from another workspace module while its own digest remains unchanged.
2. **A source set must carry bytes.** Paths and hashes alone leave a verifier dependent on the
   original workspace. Each material record therefore embeds canonical base64 and is independently
   size- and digest-checked.
3. **Search ambiguity should increase evidence, not pick a convenient file.** If the same module
   path exists at more than one eligible workspace ancestor, all matching regular files are
   retained. This may over-approximate actual execution and avoids claiming a runtime order the
   static tool did not observe.
4. **Unresolved is evidence, not success.** Standard-library and installed-package names remain in
   an explicit list. Their presence prevents a green local-material result from being read as a
   complete dependency closure.
5. **Obvious dynamic loading invalidates the static contract.** Calls such as `__import__`,
   `importlib.import_module`, `runpy.run_path`, `exec`, and `eval` fail capture. This catches common
   evasions but cannot prove that every indirect loader, plugin hook, file read, or generated module
   was found.
6. **Two observations do not prove continuous immutability.** The matrix compares every captured
   source before and after the run. A file could still change between those observations.
7. **Release equality is still not workload identity.** Binding the release-side static material
   set to the tested set closes one substitution path. It does not observe a deployment, process,
   container, configuration, environment variable, credential, package resolver, or target system.

Matrix 0.5 adds a separate CPython workspace-read observation rather than inflating this static
contract. See [RUNTIME_OBSERVATION_RESEARCH_NOTES.md](RUNTIME_OBSERVATION_RESEARCH_NOTES.md).

## Official sources

- [Python language reference — the import system](https://docs.python.org/3/reference/import.html)
- [Python documentation — initialization of `sys.path`](https://docs.python.org/3/library/sys_path_init.html)
- [SLSA 1.2 build provenance and `resolvedDependencies`](https://slsa.dev/spec/v1.2/build-provenance)
- [SLSA 1.2 artifact verification](https://slsa.dev/spec/v1.2/verifying-artifacts)
