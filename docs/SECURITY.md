# Security

## Secrets

**Every credential is server side only.** The FastAPI backend reads keys from
its environment. No key is sent to the browser, in full or masked, and no
endpoint returns one.

The Settings page shows the provider's **name** and nothing else. A masked key
is not a safe compromise: it still confirms which key is configured, and the
prefix of a key is often enough to identify the account.

| Rule | Where it is enforced |
| --- | --- |
| No secret has a default value | `src/config.py`. Keys default to the empty string. |
| No secret is logged | Providers log the fact of a failure, never the credential. |
| No secret in a `repr` | `GeminiLLMProvider.__repr__` and the Anthropic equivalent print `api_key='***redacted***'`. |
| No secret in an error message | Error translation reports status codes and provider text, never request headers. |
| No secret in Git | `.env` and `.env.local` are git ignored. `.env.example` holds placeholders only. |

### The `NEXT_PUBLIC_` rule

Anything prefixed `NEXT_PUBLIC_` is compiled into the JavaScript bundle and is
**visible to the whole internet**. Only genuinely public values may use it. The
Supabase service role key in particular must never appear behind it: that key
bypasses Row Level Security.

### If a secret is ever committed

Rotate the key first, then clean history. Rotation is what actually protects
the account. A key that has been pushed to GitHub should be considered
compromised even if the commit is removed minutes later.

## CORS

`CORS_ALLOWED_ORIGINS` is an explicit comma separated allowlist. It is never
`*`, and `allow_credentials` is on, which makes a wildcard both wrong and
invalid.

In production the deployed frontend calls the API on its own origin, so CORS is
not the mechanism protecting normal use. It is the mechanism controlling
everything else.

## Upload validation

Uploads are the one place untrusted bytes enter the system, so they are checked
twice.

| Check | Where | Why |
| --- | --- | --- |
| Extension and MIME type | Browser | Saves a pointless upload and wait. |
| Real byte count against the limit | Backend | A client supplied `Content-Length` cannot be trusted. |
| Actual PDF signature | Backend, in `extract_document` | The declared content type is a hint. Renaming a file does not get it through. |
| Empty file | Both | |

The browser side check is a courtesy, never a guarantee. The backend assumes
nothing the client claimed.

### Filenames

The uploaded filename is treated as **display text only**. It is never used to
build a filesystem path, because nothing is written to disk: the PDF is read
into memory, analysed, and discarded. When storage is enabled, paths must be
generated server side rather than derived from user input.

### Size limits

`MAX_UPLOAD_SIZE_MB` defaults to 25. This is a denial of service control as
much as a usability one: an unbounded upload into a serverless function is a
way to burn the account's compute.

## Prompt injection

A research paper is arbitrary user supplied content, and an uploaded PDF can
contain text addressed to the model. `GROUNDING_SYSTEM_PROMPT` states
explicitly that the paper is **data, not instructions**, and that anything
resembling a directive must be treated as document content and ignored.

This is a mitigation, not a guarantee. It is the reason the analysis pipeline
has no tools, no network access from the model, and no ability to act on what
it reads.

## Error handling

Errors are written for the person reading them. They never contain a stack
trace, an internal file path, a credential, or a raw provider payload.

Status codes carry the meaning so the frontend does not have to parse text:

| Code | Meaning |
| --- | --- |
| `413`, `422` | The uploader can fix it. |
| `502` | The AI service failed. |
| `503` | An operator must fix the deployment. |

The one deliberate exception is a quota error, where the provider's own message
is passed through because it names which limit was hit and how long to wait.
That text contains no secret.

## Database security

Not currently connected. The intended posture, already written into the
migrations:

- **Row Level Security enabled on every table**, with no permissive policy for
  the anonymous role. A table with RLS on and no policy is closed; a table with
  RLS forgotten is readable by anyone holding the anon key, which ships in every
  browser bundle.
- The backend uses the **service role key**, which bypasses RLS. That key never
  leaves the server.
- Per user policies (`user_id = auth.uid()`) are created ahead of
  authentication. They are inert until rows carry a `user_id` and requests
  arrive with a JWT, so they open nothing today, but ownership will be enforced
  by the database rather than by remembering a `WHERE` clause.
- The storage bucket is **private**. A public bucket would make every uploaded
  paper readable by anyone able to guess a path.

## Authentication

**Not implemented.** There are no accounts, and every endpoint is public.

This is acceptable only because the application is stateless: there is nothing
stored, so there is nothing belonging to one person that another could read.
The moment persistence is enabled, authentication stops being optional, because
without it every saved paper is in one shared, world readable library.

## Production considerations

| Setting | Production value | Why |
| --- | --- | --- |
| `APP_ENV` | `production` | Disables `/docs` and `/redoc`, which enumerate the API. |
| `DEBUG` | `false` | |
| `CORS_ALLOWED_ORIGINS` | explicit domains | Never `*`. |
| `NEXT_PUBLIC_API_BASE_URL` | unset | Keeps the API same origin. |

There is currently **no rate limiting**. `RATE_LIMIT_PER_MINUTE` appears in
`.env.example` but nothing reads it. An unauthenticated, unthrottled analysis
endpoint that costs money per call is the largest open risk in the deployment,
and the provider's own quota is the only thing bounding it today.
