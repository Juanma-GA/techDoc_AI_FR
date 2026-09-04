# Application README Template

Use this structure for every `apps/<poc>/README.md`. Keep shared rules in `STANDARD_POC.md`; do not copy the full repository standard into an application README.

## Purpose

State the business problem and intended users.

## Maturity

State the maturity level and what has been validated.

## Features

List user-visible capabilities and critical workflows.

## Port

State the assigned default port and explain that launchers select the next free port when needed. Link to the repository application inventory.

## Prerequisites

List supported Python, Node, and pnpm requirements. Distinguish developer prerequisites from packaged-user prerequisites.

## Start On Windows

Document `start.bat` and the expected local URL.

## Start On Unix

Document `start.sh` and the expected local URL.

## Frontend Development

Document the Vite development command and API proxy behavior.

## Served Interface

State that FastAPI serves the built React application from `frontend/dist/` at `/` and describe the missing-build response.

## Persistence

Describe application-owned persistence, reset scopes, and retained configuration without exposing user data.

## LLM Configuration

Describe runtime configuration, enable/disable behavior, health states, and graceful behavior when disabled.

## Tests

List backend, frontend, browser, standard, and packaging checks. Separate checks executed from checks recommended.

## Limitations

List current product and technical limitations.

## Standard Deviations

Document each approved deviation, its reason, scope, owner or validator, and review condition. Write `None` when there are no known deviations.

## Technical References

Link to application-specific architecture notes, API contracts, and relevant ADRs. Link to shared standards instead of reproducing them.
