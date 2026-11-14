# Review: PR # (closes #323)

**Verdict: approve.**

- Secret handling: the value is read from `secrets.HF_TOKEN` into the step's env and written to a 0600 temp file that is removed after use. Modal's output goes to /dev/null and nothing is echoed. GitHub masks the secret either way.
- Idempotent: `--force` overwrites. Without `HF_TOKEN`, the step exits 0 and leaves Modal's existing secret alone, so the earlier dashboard path still works.
- Gated by the same `MODAL_TOKEN_SECRET` check as the run step, so forks with no token skip it.
- Docs: setup step 4 and the credentials table agree with the workflow.
- Tests: both branches checked locally against a stub `modal`; YAML parses. No Python changed.
