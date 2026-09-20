# Chat-Lokal temporary relay

Temporary recovery/control plane for repairing the local-only Chat-Lokal stack on the owner's Mac.

- GitHub is temporary.
- The Mac polls only the default branch.
- An ephemeral GitHub Actions token is encrypted to a one-off RSA public key.
- Results are written back to `relay/result.json`.
- The relay and credentials will be removed after the local transport passes the final gates.

Do not use this repository as a permanent runtime dependency.
