Issue #87

Title: Sort results alphabetically in the `list` command output

Body:
The `list` subcommand returns results in creation order, which makes it
hard to scan long lists. Results should be sorted alphabetically by name
instead.

The change should be limited to the `list` command; other commands are
not affected.

Definition of done:
- `acme list` outputs entries sorted A→Z by name.
- The order flag `--sort` is not required (sort is always alphabetical).
- Existing tests are updated to match the new output order.

Estimated effort: ~1 hour.

Labels: enhancement, good-first-contribution
