# Infrastructure

This directory contains the container build definitions used by the current Cloud Run deployment, alongside the repository's local-development configuration.

Implemented here:

- `api.Dockerfile` and `web.Dockerfile` for the two Cloud Run services;
- `cloudbuild.api.yaml` and `cloudbuild.web.yaml` for Artifact Registry images built from the repository root;
- the root `docker-compose.yml` for local Firestore and Pub/Sub emulators plus the API.

Shared infrastructure is coordinated by both workstreams. Richard owns the definitions specific to the policy refresh job, policy event delivery, and policy administration deployment path.

Cloud resources are currently created and updated with documented `gcloud` commands rather than Terraform or another declarative infrastructure stack. See [`docs/deployment.md`](../docs/deployment.md) for the live topology, build, deploy, rollback, access, and persistence boundaries. Cloud Scheduler, durable asynchronous review workers, and Cloud Storage-backed uploads remain future infrastructure work.
