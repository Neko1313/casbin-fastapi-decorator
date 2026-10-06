# Security Policy

`casbin-fastapi-decorator` is an authorization library, so bugs in it can have security impact (for example a permission check that is skipped or evaluated against the wrong subject). We take such reports seriously.

## Supported versions

Security fixes are released for the latest minor version of the `1.x` line.

| Version | Supported |
|---|:---:|
| 1.x (latest) | ✅ |
| < 1.0 | ❌ |

## Reporting a vulnerability

**Please do not open a public issue for security problems.**

Report privately through GitHub:
[Report a vulnerability](https://github.com/Neko1313/casbin-fastapi-decorator/security/advisories/new)

Please include:

- the affected package and version,
- a minimal reproduction (app, model, policy),
- the impact you see (e.g. authorization bypass, privilege escalation).

You can expect an acknowledgement within a few days. We will keep you updated while the issue is investigated and fixed, and credit you in the advisory unless you prefer to stay anonymous.
