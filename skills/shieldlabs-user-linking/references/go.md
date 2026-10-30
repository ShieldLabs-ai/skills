# User HID in Go

`shieldlabs.UserHID(userID, secret string) (string, error)` returns HMAC-SHA256 as 64 lowercase
hex characters, and an error matching `shieldlabs.ErrValidation` on empty input.

```go
var userHIDSecret = os.Getenv("USER_HID_SECRET") // check it at startup

func userHIDFor(u *User) (string, error) {
	return shieldlabs.UserHID(strconv.FormatInt(u.ID, 10), userHIDSecret)
}
```

## `html/template`

```go
func (a *app) checkoutPage(w http.ResponseWriter, r *http.Request) {
	user := currentUser(r)
	hid, err := userHIDFor(user)
	if err != nil {
		http.Error(w, "internal error", http.StatusInternalServerError)
		return
	}
	a.templates.ExecuteTemplate(w, "checkout.html", map[string]any{"UserHID": hid})
}
```

```html
<form id="checkout" data-user-hid="{{.UserHID}}">...</form>
```

`html/template` escapes the value for the attribute. The page script passes `form.dataset.userHid || undefined` to `identify({ userId })`: for a visitor who is not signed in the attribute is empty, and an empty `userId` is rejected with `invalid_options`, while `undefined` runs an anonymous identification.

## Session endpoint for single-page apps

```go
func (a *app) session(w http.ResponseWriter, r *http.Request) {
	user := currentUser(r)
	if user == nil {
		writeJSON(w, http.StatusOK, map[string]any{"user": nil})
		return
	}
	hid, err := userHIDFor(user)
	if err != nil {
		http.Error(w, "internal error", http.StatusInternalServerError)
		return
	}
	writeJSON(w, http.StatusOK, map[string]any{"user": map[string]string{"name": user.Name, "userHid": hid}})
}
```

## Check it on the server

```go
expected, _ := userHIDFor(user)
if ident != nil && (ident.UserHID == nil || *ident.UserHID != expected) {
	// treat as unverified: another account's identification, or an anonymous one
}
```

## Read the account's History card

Read the `user` card with the exact generated HID, in the selected public domain UUID.
Preserve risk, signals, High-Risk Events and nullable related counts. Fetch additional cards
only when their IDs are known. Use the application database for its account/device associations.
See [current History](../../shieldlabs-server/references/current-history.md) and the
[account-abuse workflow](../../shieldlabs-account-abuse/references/high-risk-events.md).
