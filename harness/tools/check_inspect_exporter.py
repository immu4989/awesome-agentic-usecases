"""Exercise a pinned real Inspect producer with fixed mock tasks, never supplied user tasks/logs."""

import argparse
from contextlib import contextmanager
from importlib.metadata import distributions, version
import json
from pathlib import Path
import shutil
import socket
import sys

from aau_harness.agent_bom import AgentBomError, digest, rendered
from aau_harness.eval_inspect import create_inspect_pack, inspect_payloads, verify_inspect_pack
from aau_harness.inspect_diagnostic import create_diagnostic, verify_diagnostic
from aau_harness.evidence_index import create_index, verify_index


INSPECT_VERSION = '0.3.291'
BOUNDARY = (
    'Maintainer-run interoperability exercise using the pinned Inspect mock provider and fixed synthetic tasks. '
    'Not a live-model evaluation, independent reproduction, all-version compatibility, or government adoption. '
    'Only the specified producer version is exercised; dependency versions are recorded, not a complete '
    'hash-locked environment. Python socket tripwires detect attempted IP connections in this process; '
    'they are not an OS-enforced network sandbox or proof about native code/subprocess networking. '
    'No arbitrary input tasks, user logs, model credentials, provider configuration, or external datasets '
    'are accepted. Native logs retain their original bytes and may include local paths/runtime metadata: '
    'keep outputs local and review before disclosure. Producer timestamps/UUIDs mean separate runs need '
    'not be byte-identical; the fixed projected scores/census and rejection behavior must agree. '
    'Inspect may write its normal per-user sample-buffer/cache directories outside the output directory. '
    'Mock token usage is explicitly constructed as zero to avoid tokenizer downloads, not measured usage.'
)


@contextmanager
def deny_ip_connections():
    """A test tripwire, not a security boundary. Preserve Unix socket pairs used by asyncio."""
    originals = {name: getattr(socket.socket, name) for name in ('connect', 'connect_ex', 'sendto')}
    attempted = []
    def guarded(name):
        def call(sock, *args, **kwargs):
            if sock.family in (socket.AF_INET, socket.AF_INET6):
                attempted.append(name)
                raise RuntimeError('compatibility probe forbids IP network operations')
            return originals[name](sock, *args, **kwargs)
        return call
    try:
        for name in originals:
            setattr(socket.socket, name, guarded(name))
        yield attempted
    finally:
        for name, method in originals.items():
            setattr(socket.socket, name, method)


def mapping():
    return {'plan_version': 'aau-inspect-observation-plan/1.0',
            'source_label': 'Fixed Inspect mock-producer interoperability exercise; not a live model evaluation',
            'sample_map': [{'sample_id': 1, 'scenario_id': 'correct'}, {'sample_id': 2, 'scenario_id': 'incorrect'}],
            'n_repeats': 2,
            'metrics': {'label_score': {'scorer': 'match', 'value_key': None, 'encoding': 'labels', 'labels': {'C': 1, 'I': 0}},
                        'numeric_score': {'scorer': 'numeric_match', 'value_key': None, 'encoding': 'number'}}}


def check_projection(plan_raw, source_raw):
    report, files = inspect_payloads(plan_raw, source_raw, plan_sha256=digest(plan_raw))
    recording = json.loads(files['recording.json'])
    rows = {(r['scenario_id'], r['repeat']): r['metrics'] for r in recording['observations']}
    expected = {(name, repeat): {'label_score': value, 'numeric_score': value}
                for name, value in (('correct', 1), ('incorrect', 0)) for repeat in range(2)}
    if rows != expected or report['observation_count'] != 4 or report['declared_inspect_version'] != INSPECT_VERSION:
        raise ValueError('native exporter projection differs from the fixed compatibility contract')
    if 'evaluation_context' in json.loads(files['evaluation.json']):
        raise ValueError('import invented evaluation context')
    return report


def check_interruption(source_raw):
    """The negative control must fail for our intended solver error, not an unrelated setup error."""
    samples = json.loads(source_raw).get('samples', [])
    expected = {(identity, epoch) for identity in (1, 2) for epoch in (1, 2)}
    if (len(samples) != 4 or {(s.get('id'), s.get('epoch')) for s in samples} != expected
            or any(s.get('error', {}).get('message') !=
                   "RuntimeError('intentional synthetic solver interruption')" for s in samples)):
        raise ValueError('negative control did not record all four intended solver interruptions')


def exercise(directory):
    if directory.exists() or directory.is_symlink():
        raise ValueError('refusing to overwrite compatibility output')
    if version('inspect_ai') != INSPECT_VERSION:
        raise ValueError('install the exact documented Inspect producer version in an isolated environment')
    directory.mkdir(parents=True, exist_ok=False)
    with deny_ip_connections() as attempted:
        from inspect_ai import Task, eval
        from inspect_ai._util.logger import init_logger
        from inspect_ai.dataset import Sample
        from inspect_ai.log import read_eval_log, write_eval_log
        from inspect_ai.model import ModelOutput, ModelUsage, get_model
        from inspect_ai.scorer import Score, match, mean, scorer
        from inspect_ai.solver import generate, solver

        # Version-pinned test setup: keep Inspect's own trace rotation/writes inside this new output.
        trace_dir = directory / 'producer-traces'
        trace_dir.mkdir()
        init_logger('warning', trace_dir=trace_dir)

        def fixed_output(*args):
            output = ModelOutput.from_content(model='mockllm/model', content='Default output from mockllm/model')
            # Explicit constructed usage keeps the mock provider from fetching tokenizer data.
            # These are not measured tokens, and AAU imports no token/cost/latency fields.
            output.usage = ModelUsage(input_tokens=0, output_tokens=0, total_tokens=0)
            return output

        model = get_model('mockllm/model', custom_outputs=fixed_output)

        @scorer(metrics=[mean()])
        def numeric_match():
            async def score(state, target):
                return Score(value=int(state.output.completion == target.text))
            return score

        @solver
        def interrupted():
            async def solve(state, generate):
                raise RuntimeError('intentional synthetic solver interruption')
            return solve

        samples = [Sample(id=1, input='Fixed public mock input A', target='Default output from mockllm/model'),
                   Sample(id=2, input='Fixed public mock input B', target='A deliberately different target')]
        task = Task(dataset=samples, solver=generate(), scorer=[match(), numeric_match()])
        logs = eval(task, model=model, epochs=2, log_format='json', log_dir=str(directory / 'native-json'),
                    display='none', max_connections=1)
        if len(logs) != 1 or logs[0].status != 'success':
            raise ValueError('fixed mock evaluation did not finish successfully')
        original = Path(logs[0].location).read_bytes()
        plan_raw = rendered(mapping())
        check_projection(plan_raw, original)
        create_inspect_pack(plan_raw, original, directory / 'converted-json', plan_sha256=digest(plan_raw))
        verify_inspect_pack(directory / 'converted-json', plan_sha256=digest(plan_raw))

        # Official API handles current binary/condensed storage. AAU does not implement a second .eval parser.
        native_binary = directory / 'producer.eval'
        write_eval_log(logs[0], native_binary, format='eval')
        reread = read_eval_log(native_binary)
        roundtrip = directory / 'roundtrip.json'
        write_eval_log(reread, roundtrip, format='json')
        roundtrip_raw = roundtrip.read_bytes()
        check_projection(plan_raw, roundtrip_raw)
        create_inspect_pack(plan_raw, roundtrip_raw, directory / 'converted-roundtrip', plan_sha256=digest(plan_raw))
        verify_inspect_pack(directory / 'converted-roundtrip', plan_sha256=digest(plan_raw))

        error_task = Task(dataset=samples, solver=interrupted(), scorer=[match(), numeric_match()])
        errors = eval(error_task, model=model, epochs=2, log_format='json', log_dir=str(directory / 'native-error'),
                      display='none', fail_on_error=False, max_connections=1)
        if len(errors) != 1:
            raise ValueError('negative control returned an unexpected task-log count')
        error_raw = Path(errors[0].location).read_bytes()
        check_interruption(error_raw)
        try:
            inspect_payloads(plan_raw, error_raw, plan_sha256=digest(plan_raw))
        except AgentBomError:
            pass
        else:
            raise ValueError('interrupted native evidence was accepted as a complete conversion')
        create_diagnostic(plan_raw, error_raw, directory / 'interrupted-diagnostic', plan_sha256=digest(plan_raw))
        diagnostic = verify_diagnostic(directory / 'interrupted-diagnostic', plan_sha256=digest(plan_raw))
        if diagnostic['conversion_eligibility']['status'] != 'rejected_by_current_converter':
            raise ValueError('diagnostic did not preserve strict rejection')
        delivery = directory / 'index-delivery'
        shutil.copytree(directory / 'interrupted-diagnostic', delivery / 'diagnostic')
        request = {'request_version': 'aau-evidence-index-request/1.0', 'purpose': 'Synthetic native interrupted-source check',
                   'items': [{'item_id': name, 'profile': 'inspect-' + name, 'purpose': 'Require this native evidence layer',
                              'controls': {'plan_sha256': digest(plan_raw)}} for name in ('conversion', 'diagnostic')],
                   'bindings': [{'left': {'item_id': 'conversion', 'role': 'source'},
                                 'right': {'item_id': 'diagnostic', 'role': 'source'}}]}
        request_raw = rendered(request)
        index = create_index(request_raw, delivery, directory / 'source-index', request_sha256=digest(request_raw))
        if (verify_index(directory / 'source-index', request_sha256=digest(request_raw)) != index
                or index['exit_code'] != 1 or index['items'][0]['verification_status'] != 'missing'
                or index['items'][1]['verification_status'] != 'verified'
                or index['items'][1]['native_report']['conversion_eligibility']['status'] != 'rejected_by_current_converter'):
            raise ValueError('native interrupted-source index substituted diagnostic evidence for conversion')
        if attempted:
            raise ValueError('producer attempted IP networking')
    report = {'check_version': 'aau-inspect-producer-compatibility/1.0', 'inspect_version': version('inspect_ai'),
              'python_version': sys.version.split()[0], 'producer_model': 'mockllm/model',
              'checks': {'json_projection': True, 'official_eval_roundtrip_projection': True,
                         'interrupted_import_rejected': True, 'interrupted_diagnostic_verified': True,
                         'interrupted_index_preserves_missing_conversion': True},
              'plan_sha256': digest(plan_raw), 'raw_sha256': {'json': digest(original), 'eval': digest(native_binary.read_bytes()),
                                                            'roundtrip_json': digest(roundtrip_raw), 'error_json': digest(error_raw)},
              'dependency_versions': dict(sorted((d.metadata['Name'], d.version) for d in distributions())),
              'ip_network_attempts': len(attempted), 'boundary': BOUNDARY}
    with (directory / 'compatibility.json').open('xb') as stream:
        stream.write(rendered(report))
    return report


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--out', type=Path, required=True)
    args = parser.parse_args(argv)
    try:
        report = exercise(args.out.resolve())
        print(f'Inspect {report["inspect_version"]}: {len(report["checks"])} mock-producer compatibility checks passed; not live-model evaluation.')
        return 0
    except (ValueError, OSError, RuntimeError) as exc:
        print(f'error: compatibility check failed ({type(exc).__name__}); inspect local diagnostics.', file=sys.stderr)
        return 2


if __name__ == '__main__':
    raise SystemExit(main())
