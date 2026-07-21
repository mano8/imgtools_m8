# imgtools_m8

## Layer

Platform (image processing library).

## Purpose

Provide reusable image-processing utilities as a pure computation library.

## Repository boundaries

- Do not add service-layer dependencies.
- Keep the library free of external service coupling.
- Keep inputs and outputs deterministic.

## Standalone authority

This file, `pyproject.toml`, repository documentation, and existing CI are the
authoritative local context. A verified nearest workspace may optionally add
launcher-selected Python policies and tasks; its absence is a successful
standalone condition and does not make a parent workspace necessary.

When a task requires quality validation, follow the repository documentation and
CI together with the applicable selected Python policy.
