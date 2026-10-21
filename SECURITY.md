# Security

## Reporting a problem

Write to **hello@nways.ng** with "Security" in the subject. Describe the problem, how to reproduce it, and what it affects (the engine, the server, the registry or a deployment). Please do not open a public issue for a vulnerability before it is fixed.

We acknowledge a report within three working days, tell you what we will do, and credit you in the fix if you wish.

## What counts

- A way to issue or change codes without a valid issuing key, or beyond a key's daily limit, on the server in `server/`.
- A way to make the server answer with a code that is not in its database, or to corrupt the database through the API.
- A registry file whose content does not match the SHA-256 in `registry/MANIFEST.json`.
- Personal data found anywhere in this repository. The registry describes places only; if you find a person's name, phone number or identity number, report it so it can be removed.

## Running a deployment safely

- Run read-only (no `ISSUE_KEYS`) unless your deployment is the designated issuer.
- Put the server behind a reverse proxy with TLS; never send issuing keys over plain HTTP.
- Give each issuing office its own key, so that one can be withdrawn without the others.
- Keep the database file readable only by the server's user, and back it up (server/README.md).
