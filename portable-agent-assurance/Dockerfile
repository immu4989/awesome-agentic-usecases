FROM python:3.12-slim@sha256:09f7da3bc104798d0afb40bc08d23ab2da20a76130cec1f2ef170848f5d85217

WORKDIR /work
COPY aau_assurance.py ./
COPY examples ./examples

RUN useradd --create-home --uid 10001 runner && mkdir /result && chown runner:runner /result
USER runner

ENTRYPOINT ["/bin/sh", "-c"]
CMD ["python3 aau_assurance.py evaluate examples/synthetic-assurance-envelope.json examples/mcp-a2a-conformance-suite.json --out /result/receipt.json && python3 aau_assurance.py verify /result/receipt.json --envelope examples/synthetic-assurance-envelope.json --suite examples/mcp-a2a-conformance-suite.json"]
