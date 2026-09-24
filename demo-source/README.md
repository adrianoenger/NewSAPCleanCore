# Demo Source — SAP Custom Code Samples

Synthetic SAP custom code for Clean Core Analyzer PoC demonstrations.

## Structure

- `ABAP/` — ABAP class, function module, program, and XML metadata
- `DDIC/` — DDIC table and domain definitions
- `CONFIG/` — System configuration

## Usage

This directory is automatically scanned when running the demo seed:
```bash
docker compose exec backend python -m seed apply
```
