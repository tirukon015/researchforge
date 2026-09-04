# Authentication

How sign-in works, and the Supabase settings it depends on.

## ⚠️ Required Supabase dashboard configuration

**Authentication in production does not work until this is set.** It cannot be
done from code: it needs the dashboard, or a Supabase management token that is
not part of this deployment.

Go to **Supabase Dashboard → Authentication → URL Configuration**.

### Site URL

```
https://researchforge.rukon.dev
```

If this is left as `http://localhost:3000`, **every** sign-in and every email
link sends real users to a machine that is not running. It is the single most
important field on the page, because of the fallback behaviour described below.

### Redirect URLs (allow-list)

All four. The first two are production; the last two keep local development
working and are harmless in production.

```
https://researchforge.rukon.dev/auth/callback
https://researchforge.rukon.dev/reset-password
http://localhost:3000/auth/callback
http://localhost:3000/reset-password
```

Optionally, to make preview deployments work too:

```
https://researchforge-*-rpoms.vercel.app/auth/callback
https://researchforge-*-rpoms.vercel.app/reset-password
```

### Why a missing entry is so confusing

Supabase does **not** reject an unlisted `redirect_to` when the flow starts. A
blatantly invalid one still returns `302` to Google. It validates on the way
**back**, and silently substitutes the project's **Site URL**.

So a missing allow-list entry does not look like a permissions error. It looks
like this:

```
http://localhost:3000/?access_token=...
```

Two tells, and each names its own cause:

| What you see | What it means |
| --- | --- |
| Landed on `/`, not the path you asked for | `redirect_to` was rejected and replaced by the Site URL |
| The host is `localhost:3000` | that **is** the Site URL |
| `access_token` in the URL | the implicit flow (see below) |

## Which flow, and why

`flowType` is pinned to `pkce` in `app/src/lib/supabase.ts`.

Plain `@supabase/supabase-js` defaults to **`implicit`**, which returns the
session by putting the access and refresh tokens directly in the URL of the
page the provider redirects back to. Those tokens land in browser history and
can be sent in a `Referer` header to any third-party asset the landing page
loads.

PKCE returns a single-use `?code=` instead, which is worthless without the
verifier held in that browser's own storage. Nothing secret is ever in a URL.

`@supabase/ssr` defaults to `pkce`; `supabase-js` does not. It is set
explicitly so this does not depend on which package a future refactor reaches
for.

## The three redirect destinations

| Flow | Returns to | Why |
| --- | --- | --- |
| Google sign-in | `/auth/callback` | needs a page that can wait for the session |
| Email confirmation | `/auth/callback` | same, and shares the one allow-listed URL |
| Password reset | `/reset-password` | see below |

Password reset is the exception. A reset link is opened from an email,
possibly in a different browser, so nothing the original tab stored is
available to tell `/auth/callback` where to send the user afterwards. The
destination therefore has to be the URL itself.

## How the origin is chosen

`authRedirectUrl()` in `app/src/lib/supabase.ts` builds every redirect from
`window.location.origin`:

- local development → `http://localhost:3000/...`
- production → `https://researchforge.rukon.dev/...`
- a preview deployment → that preview's own URL

Nothing is hard-coded, so there is no variable to remember to change and no way
for a production build to point at a developer's machine.

`NEXT_PUBLIC_SITE_URL` overrides it, for the one case the origin cannot cover:
a deployment behind a proxy serving a different public hostname than the
browser reports. **Leave it unset** unless that applies — setting it to the
production URL would break local development.

## Why `/auth/callback` waits instead of exchanging the code

The obvious implementation calls `exchangeCodeForSession(code)` on the
callback page. In this configuration that is a bug: the client is created with
`detectSessionInUrl: true`, so it has already consumed the one-time code by the
time the component mounts. A code cannot be redeemed twice, so the explicit
call fails and the page reports a failure on a sign-in that actually
succeeded.

Waiting for the session is correct, and it is also flow-agnostic: it works
unchanged whether the URL carried a PKCE `?code=` or an implicit-flow token
fragment, which is what lets a link issued before the switch to PKCE still
work.

## Session restoration

`AuthProvider` calls `getSession()` on mount and subscribes to
`onAuthStateChange`. Until the first resolves, the state is `loading` — not
`anonymous`. That distinction matters: treating "we do not know yet" as "not
signed in" would redirect a signed-in reader to the sign-in page on every
reload, which is the bug that makes an app feel like it logs you out at random.

## Protected routes

`AuthGate` sends a signed-out visitor to `/sign-in?next=<where they were>`.

**It is not the security boundary.** Anyone can edit the bundle. What actually
protects the data is the API refusing an unauthenticated request (`401`) and,
underneath that, Row Level Security in Postgres. The gate exists so a
signed-out visitor sees the sign-in page instead of an app frame full of
errors.

`?next=` is validated by `isSafeReturnPath()` on the way into storage and again
on the way out. Only same-site absolute paths pass; `//evil.example` and
`/\evil.example` are both rejected, because a browser reads them as hosts.

## Local development

```bash
cd app && npm run dev     # http://localhost:3000
```

Works with no extra configuration, as long as the two `localhost` entries are
in the redirect allow-list. `authRedirectUrl` picks up the dev origin on its
own.

## Testing

```bash
cd app && npm test        # redirect construction, open-redirect rejection
pytest                    # the API side: 401/403, ownership, RLS
```
