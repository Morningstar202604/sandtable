# Security Policy

## Reporting a vulnerability

Please report vulnerabilities through private security advisories or by
contacting the maintainers directly. Do **not** open a public issue for
exploitable problems. Expect a response within 7 days.

## Secrets and credentials (hard rules)

This project touches two kinds of sensitive data:

1. **LLM API keys** — belong in `.env` (gitignored) or environment variables.
   They may also be entered in the web settings panel (kept in process
   memory only; never written to disk, never echoed back).
2. **Git remote tokens** — use your platform's credential manager or SSH keys;
   do not embed tokens in URLs that end up in committed files or shell history.

Before pushing, check:

```bash
git grep -inE "sk-[a-zA-Z0-9]{20,}|ghp_[a-zA-Z0-9]{20,}" -- ':!*.md'
```

Any key that has ever reached a commit must be considered compromised:
revoke and rotate it at the provider immediately.

## Supported versions

| Version | Supported |
|---|---|
| 0.1.x | ✅ |
