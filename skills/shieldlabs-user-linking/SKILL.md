---
name: shieldlabs-user-linking
description: Links ShieldLabs identifications to your user accounts with a User HID. Computes a stable, irreversible HMAC-SHA256 User HID on the server with the SDK userHid helpers (Node.js, Python, Go, PHP, Java, .NET), passes it to the browser SDK for signed-in users, checks it on the server, and keeps raw emails, phone numbers and database IDs out of ShieldLabs. Use when the user asks to pass a user ID or userId to ShieldLabs, identify signed-in or authenticated users, hash user IDs for ShieldLabs, set up checkAuthenticatedUser, look up history by user_hid, bind a request ID to the logged-in account, or fix identifications that show up as anonymous.
---

# Link identifications to your users

A **User HID** is your own hashed or pseudonymous account ID, passed to the browser SDK as
`userId`. With it:

- the History API returns every identification of one account (`user_hid` lookups), which the
  account-abuse checks need (shieldlabs-account-abuse skill,
  [../shieldlabs-account-abuse/SKILL.md](../shieldlabs-account-abuse/SKILL.md));
- the backend can check that a request ID belongs to the signed-in user;
- ShieldLabs builds users, account-level risk and the High-Risk Events shown in the analytics
  dashboard on it.

Identifications without a User HID are anonymous (`user_hid` is `"anonymous"`): they belong to a
device, a visitor and IP addresses, but to no account.

## Workflow

1. Create a User HID secret once: a long random value in `USER_HID_SECRET` on the server, separate
   from the ShieldLabs keys. Generate it with `openssl rand -hex 32`.
2. Compute the User HID on the server with the SDK helper, from a stable internal account ID.
3. Hand it to the page for signed-in users: a session payload, a rendered data attribute or a
   server component prop.
4. In the browser pass it as `userId` to `identify()` at protected actions, and to `check()` or
   `checkOnLoad` for passive monitoring of signed-in pages. Omit it for anonymous visitors.
5. On the server compare `identification.user_hid` with the User HID of the session user before
   trusting a signed-in action.

## Compute it on the server

Every server SDK has the same helper: HMAC-SHA256 with the secret as the key and the account ID as
the message, as 64 lowercase hex characters. It fails with a validation error on empty input.

| Language | Helper | Reference |
|---|---|---|
| Node.js | `userHid(String(user.id), process.env.USER_HID_SECRET!)`; in edge runtimes `await userHidAsync(...)` | [node.md](references/node.md) |
| Python | `user_hid(str(user.id), os.environ["USER_HID_SECRET"])` | [python.md](references/python.md) |
| Go | `shieldlabs.UserHID(userID, secret)` returns `(string, error)` | [go.md](references/go.md) |
| PHP | `UserHid::fromUserId((string) $user->id, $secret)` | [php.md](references/php.md) |
| Java | `UserHid.fromUserId(String.valueOf(user.getId()), secret)` | [java.md](references/java.md) |
| .NET | `UserHid.FromUserId(user.Id.ToString(), secret)` | [dotnet.md](references/dotnet.md) |

```ts
import { userHid } from '@shieldlabs/node';

// Same account, same User HID, on every device. Irreversible without the secret.
const hid = userHid(String(user.id), process.env.USER_HID_SECRET!);
```

## Pass it to the browser SDK

| Browser package | Pass the User HID |
|---|---|
| `@shieldlabs/js` | `agent.identify({ userId: hid })`, `agent.check({ userId: hid })` |
| `@shieldlabs/react`, `@shieldlabs/next` | `useIdentify({ userId: hid })`, or `identify({ userId })` per call |
| `@shieldlabs/vue` | `useIdentify({ userId: () => props.userHid })` (a string, ref or getter) |
| `@shieldlabs/angular` | `injectIdentify({ userId: session.userHid })` (a string, a signal or a function) |
| `@shieldlabs/svelte` | `useIdentify(() => ({ userId: data.userHid }))` |
| Background checks | `check({ userId })`, or `checkOnLoad: { userId }` on the provider, plugin or setup |

`identify()` resolves `{ requestId, userId }`: `userId` is the User HID that was sent (the
framework identify helpers resolve `null` when there is no identification). Details per framework:
shieldlabs-browser skill ([../shieldlabs-browser/SKILL.md](../shieldlabs-browser/SKILL.md)).

## Which ID to hash

- A stable internal account ID that is never reused: the primary key or an account UUID.
- Not the email address or username: they change, and a changed input gives a new User HID and
  splits the account's history.
- Convert it the same way everywhere (`String(42)` is `"42"`; `"0042"` would be another User HID).
- One secret for the whole product. Changing it changes every User HID, so treat it as permanent.

## Signup, login and logout

- **Signup**: the account does not exist yet, so identify anonymously when the form is submitted.
  After the account is created, signed-in pages pass its User HID. Store `identification.device_id`
  with the new account for later checks.
- **Login**: identify anonymously on the login form, because the visitor is not authenticated yet.
  Pass the User HID only after the password check succeeds (for example with `check({ userId })`
  on the next page). Passing the claimed account's User HID before that would attach another
  person's attempts to the account.
- **Logout**: stop passing the User HID; identifications are anonymous again.

## Bind a request ID to the session user

For every action of a signed-in user, the identification must carry that user's User HID:

```ts
const expected = userHid(String(session.userId), process.env.USER_HID_SECRET!);
if (identification && identification.user_hid !== expected) {
  // Another account's identification, or an anonymous one: treat the action as unverified.
}
```

The `decide()` policy of the shieldlabs-risk-decisions skill takes `expectedUserHid` and does this
check for you.

## Rules

- Never pass a raw email address, phone number, username or database ID, and never compute the
  User HID in the browser: the secret would reach the client, and a plain hash of an email address
  can be reversed by guessing.
- The browser SDK rejects the reserved values `"anonymous"`, `"fail"`, `"-1"` and `"unknown"`, and
  warns about values that look like an email address, contain `/`, `?`, `#` or `%`, or are `.` or
  `..`. The hex output of the helpers avoids both.
- Lookups by `user_hid` are exact and case-sensitive: search with the value the page sent. The
  value travels as one URL path segment, so the server SDKs (and the MCP tools) refuse a User HID
  that contains `/` or is `.` or `..` with a validation error, because the History API cannot
  match it, and escape every other character the way the History API matches it.
- The User HID is pseudonymous. Keep treating it as account data in your own records.

## Pitfalls

- Identifications show `"anonymous"`: the page did not pass `userId`, or passed `null` or
  `undefined`. With a framework helper, the `userId` key in the options of one call counts too:
  `identify({ userId: undefined })` overrides the helper's User HID and runs anonymously. An empty
  string is different: the browser SDK rejects it with `invalid_options` and no identification
  runs. A template renders a missing User HID as an empty attribute, so pass
  `form.dataset.userHid || undefined`.
- `user_mismatch` on every signed-in action: the backend and the page compute the User HID from
  different inputs or with different secrets.
- A User HID on public pages for visitors who are not signed in.
- Using the session ID or a per-login token: the User HID must stay the same for the account.

## Versions

This skill targets the 1.x SDKs. Before pinning, confirm the current version on the package
registry and at https://docs.shieldlabs.ai.
