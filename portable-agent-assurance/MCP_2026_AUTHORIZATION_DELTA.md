# MCP 2026-07-28 Authorization Delta

Research snapshot: **2026-08-30**. This is an experimental AAU recorded-fixture profile, not an
MCP or OAuth implementation, conformance test, security review, certification, or compliance
determination.

## Why this companion exists

The stable Portable Agent Assurance 0.1 record shape was evaluated against MCP `2025-06-18`. It is
not silently relabeled as current. The `2026-07-28` revision retains resource indicators, audience
validation, and the token-passthrough prohibition while adding or clarifying authorization-response
issuer validation, issuer-bound client credentials, scope selection and step-up. The current core
also makes requests self-describing with method and tool-name headers.

The companion gate binds the current revision, method/tool headers, authorization-response issuer,
credential issuer, authorization and token resources, token audience, minimized initial scopes,
scope-union step-up, passthrough, and query transport. It compiles two legitimate clean twins and
fourteen single-delta violations from one exact public synthetic profile. Expected answers never
enter the command-adapter request.

## Premise checks

- Issuer inclusion remains conditional on advertised support in this revision; a present issuer
  is always compared, and an advertised-but-absent issuer is rejected.
- Client ID Metadata Documents are preferred. Dynamic Client Registration is deprecated but still
  permitted, so registration mode is recorded without making DCR an automatic failure.
- Initial scope minimization and user-delegated step-up are `SHOULD` behaviors. The stricter block
  outcomes are conservative AAU profile choices, not statements of MCP conformance.
- Method and name headers are a core `2026-07-28` transport delta, while issuer, resource, token,
  and scope behaviors come from the authorization specification. One recorded evaluator cannot
  establish the rest of either specification.
- The gate does not perform discovery, registration, OAuth, HTTP, token validation, an MCP request,
  or tool execution. It cannot prove that a deployed decision preceded a side effect.

## Primary sources

- Model Context Protocol, [2026-07-28 release](https://blog.modelcontextprotocol.io/posts/2026-07-28/), July 28, 2026.
- Model Context Protocol, [Authorization 2026-07-28](https://modelcontextprotocol.io/specification/2026-07-28/basic/authorization), accessed August 30, 2026.
- IETF, [RFC 9207: OAuth 2.0 Authorization Server Issuer Identification](https://www.rfc-editor.org/rfc/rfc9207), March 2022.
- IETF, [RFC 8707: Resource Indicators for OAuth 2.0](https://www.rfc-editor.org/rfc/rfc8707), February 2020.
