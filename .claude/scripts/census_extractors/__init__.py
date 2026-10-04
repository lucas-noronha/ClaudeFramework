"""Pluggable census extractors (ADR 0019). One module per stack, named
after the `census.extractor` config value with dashes as underscores.
Each exposes `extract(ref, settings) -> [(kind, identifier, "path:line")]`
and must be deterministic: same ref and settings, same output.
"""
