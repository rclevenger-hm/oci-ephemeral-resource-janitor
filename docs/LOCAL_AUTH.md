# Local OCI authentication

The janitor supports the OCI SDK's normal configuration-file authentication for local development. Keep working credentials outside the repository.

## Recommended local setup

1. Copy `examples/oci-config.example` to the OCI SDK's normal user-level configuration path, typically `~/.oci/config`.
2. Replace the placeholders with your own tenancy, user, fingerprint, key path, and region.
3. Restrict the private key and configuration file to the local user according to your operating-system policy.
4. Leave `OCI_CONFIG_FILE` unset to use the SDK default, or point it at another file outside the checkout.
5. Use `OCI_CONFIG_PROFILE` when a profile other than `DEFAULT` is required.

The repository-local `.oci/` directory intentionally ignores all files except its `.gitignore`. This prevents a working profile or key-adjacent material from being committed accidentally.

For OCI Functions, prefer resource-principal authentication instead of shipping a local configuration file into the function package.
