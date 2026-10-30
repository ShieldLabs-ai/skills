# User HID in Java

`ai.shieldlabs.UserHid.fromUserId(String userId, String secret)` returns HMAC-SHA256 as 64
lowercase hex characters and throws `ValidationException` on empty input.

```java
String userHidSecret = System.getenv("USER_HID_SECRET"); // from your secret store; check it at startup
String userHid = UserHid.fromUserId(String.valueOf(user.getId()), userHidSecret);
```

## Spring MVC with Thymeleaf

```java
@ControllerAdvice
class ShieldLabsModel {
    private final String userHidSecret;

    ShieldLabsModel(@Value("${USER_HID_SECRET}") String userHidSecret) {
        this.userHidSecret = userHidSecret;
    }

    @ModelAttribute("shieldlabsUserHid")
    String shieldlabsUserHid(@AuthenticationPrincipal AppUser user) {
        return user == null ? null : UserHid.fromUserId(String.valueOf(user.getId()), userHidSecret);
    }
}
```

```html
<form id="checkout" th:attr="data-user-hid=${shieldlabsUserHid}">...</form>
```

Thymeleaf leaves the attribute out when the value is `null`. The page script passes `form.dataset.userHid || undefined` to `identify({ userId })`: for a visitor who is not signed in the attribute is empty, and an empty `userId` is rejected with `invalid_options`, while `undefined` runs an anonymous identification.

## REST session endpoint for single-page apps

```java
@GetMapping("/api/session")
Map<String, Object> session(@AuthenticationPrincipal AppUser user) {
    if (user == null) {
        return Collections.singletonMap("user", null);
    }
    return Map.of("user", Map.of(
            "name", user.getName(),
            "userHid", UserHid.fromUserId(String.valueOf(user.getId()), userHidSecret)));
}
```

## Check it on the server

```java
String expected = UserHid.fromUserId(String.valueOf(user.getId()), userHidSecret);
if (identification != null && !expected.equals(identification.getUserHid())) {
    // treat as unverified: another account's identification, or an anonymous one
}
```

## Read the account's History card

Read the `user` card with the exact generated HID, in the selected public domain UUID.
Preserve risk, signals, High-Risk Events and nullable related counts. Fetch additional cards
only when their IDs are known. Use the application database for its account/device associations.
See [current History](../../shieldlabs-server/references/current-history.md) and the
[account-abuse workflow](../../shieldlabs-account-abuse/references/high-risk-events.md).
