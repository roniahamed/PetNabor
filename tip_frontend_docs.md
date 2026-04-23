# 📱 PetNabor Tip System — Frontend Integration Guide

This guide is designed for the React Native/Frontend developer to integrate the Stripe Tip processing and Withdrawal features.

---

## 1. Environment Variables needed on Frontend

Make sure you have access to your Stripe Publishable Key:
```env
# It is returned by the Send Tip API, but good to have if needed for other Stripe contexts.
STRIPE_PUBLISHABLE_KEY=pk_test_...
```

---

## 2. Tip Setup (Onboarding & Checking Status)

Before a user can **receive** tips, they must create a Stripe Connect account.

### A. Check if the user is ready to receive tips

**`GET /api/tip/connect/status/`**

Checks if the currently logged-in user has connected their Stripe account.

**Response:**
```json
{
  "stripe_account_id": "acct_1OuXXXXX",
  "is_onboarding_complete": true,
  "is_charges_enabled": true,
  "is_payouts_enabled": true,
  "is_fully_verified": true, // The user can fully receive tips
  "created_at": "2026-04-23T20:47:45Z",
  "updated_at": "2026-04-23T20:47:45Z"
}
```

### B. Start Stripe Connect Onboarding

If `is_fully_verified` is `false` (or 404), call this API to get the onboarding URL.

**`POST /api/tip/connect/onboard/`**

**Response:**
```json
{
  "onboarding_url": "https://connect.stripe.com/setup/c/acct_1OuX.../xxxx"
}
```

**What you need to do:**
Open `onboarding_url` in the device browser (Using `Linking.openURL()` in React Native).
Once the user is done, Stripe will redirect them back to the app using the deep link:
`petnabor://tip/onboard/return`

You must catch this deep link in your app and then re-fetch `GET /api/tip/connect/status/` to update the UI.

---

## 3. Sending a Tip

When User A wants to send a tip to User B.

**`POST /api/tip/send/`**

**Request Body:**
```json
{
  "recipient_id": "uuid-of-recipient-user",
  "meeting_id": "uuid-of-meeting", // Optional, if tip is tied to a meeting
  "amount": "20.00",               // Minimum 1.00 usually (string or float)
  "note": "Thanks for being awesome!" // Optional message
}
```

**Response (201 Created):**
```json
{
  "tip": {
    "id": "uuid-of-tip",
    "tipper": { "id": "uuid...", "first_name": "John", "last_name": "Doe", "email": "john@test.com" },
    "recipient": { "id": "uuid...", "first_name": "Jane", "last_name": "Doe", "email": "jane@test.com" },
    "meeting_id": "uuid-of-meeting",
    "amount": "20.00",
    "status": "pending", // OR "held" if recipient hasn't onboarded yet
    "is_held": false,    // true if payment is kept on hold waiting for recipient to connect Stripe
    "currency": "usd"
  },
  "client_secret": "pi_3Pxxxx_secret_xxxxx",
  "publishable_key": "pk_test_xxxxxx"
}
```

**What you need to do:**
Pass the `client_secret` (and `publishable_key` if needed) to the React Native Stripe SDK (e.g., `PaymentSheet` or `useConfirmPayment()`) to complete the payment UI.

---

## 4. Tip History

Shows tips sent and received by the current user. **(Paginatated Response)**

**`GET /api/tip/history/?direction=all&page=1`**
- `direction` (optional): "sent" | "received" | "all"
- `status` (optional): "pending" | "held" | "succeeded" | "failed"
- `page` (optional): 1, 2, 3...

**Response:**
```json
{
  "count": 45,
  "next": "https://api.petnabor.com/api/tip/history/?page=2",
  "previous": null,
  "results": [
    {
      "id": "uuid-of-tip",
      "tipper": { ... },
      "recipient": { ... },
      "amount": "20.00",
      "status": "succeeded",
      "is_held": false,
      "created_at": "2026-04-23T20:47:45Z"
    }
  ]
}
```

---

## 5. Withdraw Earnings (Payout)

For the receiver to transfer their earned tips to their bank account.

### A. Check Wallet Balance

**`GET /api/tip/balance/`**

**Response:**
```json
{
  "available_balance": "150.00",
  "currency": "usd",
  "minimum_withdrawal": "10.00"
}
```

### B. Request Payout

Withdraw money to their connected bank account.

**`POST /api/tip/withdraw/`**

**Request Body:**
```json
{
  "amount": "50.00" // Must be <= available_balance and >= minimum_withdrawal
}
```

**Response (201 Created):**
```json
{
  "id": "uuid-of-withdrawal",
  "amount": "50.00",
  "currency": "usd",
  "status": "pending",
  "stripe_payout_id": "po_1Qyyyyyyy",
  "failure_message": "",
  "created_at": "2026-04-23T20:47:45Z"
}
```

### C. Withdrawal History

Check past withdrawal requests. **(Paginatated Response)**

**`GET /api/tip/withdraw/history/?page=1`**

**Response:**
```json
{
  "count": 12,
  "next": "...",
  "previous": null,
  "results": [
     {
        "id": "uuid...",
        "amount": "50.00",
        "status": "paid", // or pending / failed
        "created_at": "2026-04-23T20:47:45Z"
     }
  ]
}
```

---

## Important System Logic (Payment Hold & Release)

If User A tips User B, but User B has **not** connected their Stripe account yet:
1. The `POST /api/tip/send/` API will still accept the payment.
2. The `is_held` flag in the response will be `true`, and `status` will be `"held"`.
3. The platform will temporarily hold the fund.
4. User B will receive a Push Notification: *"Someone sent you a tip! Connect your bank account to receive it."*
5. As soon as User B completes Stripe Onboarding (`POST /api/tip/connect/onboard/`), the backend will automatically release all held tips to User B's account. No action needed from frontend.
