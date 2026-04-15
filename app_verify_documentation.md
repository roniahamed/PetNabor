# Central Verification Integration Documentation

## Understanding `app_user_id` & `reference_id`
In RevenueCat, every purchase is tied to an `app_user_id`. In Persona, every inquiry is tied to a `reference_id`. For our backend to correctly flag a user as verified upon a successful payment or a successful ID Verification, these values MUST strictly map to the exact `id` of the User object (UUID) in our Django database.

**How to sync this up for RevenueCat?**
When initializing the RevenueCat SDK in your mobile app, configure RevenueCat with the currently logged-in user's `id`.
```javascript
// React Native Example
Purchases.configure({ apiKey: "YOUR_REVENUECAT_KEY", appUserID: user.id });
```

**How to sync this up for Persona? (Hacker-Proof Architecture)**
Instead of letting the frontend randomly pass any UUID into the SDK (which a hacker could easily intercept and manipulate to verify someone else's account), our Django backend establishes the session securely behind the scenes!

1. Your mobile app simply calls `POST /api/verification/persona-init/` equipped with the user's standard `Bearer Token` header.
2. Our backend securely identifies the user through the token, talks to the **withpersona.com** API servers, and generates a pre-authenticated `inquiry_id`.
3. Our backend returns `{"inquiry_id": "inq_xyz..."}` down to the mobile app.
4. Your mobile developer then instantly launches the Persona SDK by binding to the securely verified Inquiry block:
```javascript
// React Native Example
import Persona from 'react-native-persona';
Persona.Inquiry.fromInquiry('inq_xyz...')
  .build()
  .start();
```

When either service completes correctly, their backend servers will send payloads to our backend endpoints equipped exactly with that assigned UUID, mapping their success straight home!

## Critical Environment (`.env`) Variables

By default, any open connection to a webhook can be simulated or maliciously abused. 

1. Generate strong access keys for each service.
2. In your `.env` file across your development, staging, and production servers, add:
```env
REVENUECAT_WEBHOOK_SECRET=your_super_secret_token_here
PERSONA_API_KEY=your_persona_api_key_here
PERSONA_TEMPLATE_ID=itm_your_template_id_here
PERSONA_WEBHOOK_SECRET=your_persona_webhook_token
```

### Dashboard Setup for RevenueCat:
Inside your **RevenueCat Dashboard**, head over to project settings and configure the **Webhook URL**:
- **URL:** `https://your-domain.com/api/verification/webhook/`
- **Authorization Header:** `Bearer your_super_secret_token_here`

### Dashboard Setup for Persona:
Inside your **Persona Dashboard**, go to **Integration > Webhooks** and add an endpoint:
- **URL:** `https://your-domain.com/api/verification/persona-webhook/`
- **Subscribed Events:** Enable `inquiry.completed` and `inquiry.failed`.
- Persona will automatically provide you a Webhook Secret. Copy that and place it into your backend `.env` as `PERSONA_WEBHOOK_SECRET`.

Our backend will automatically evaluate the `X-Persona-Signature` cryptographic header to ensure no hacker can trigger false successful accounts!

## Postman Testing
We have generated the file `app_verify_postman_collection.json` containing endpoints testing workflows:
1. `GET /api/verification/config/` (Public)
2. `GET /api/verification/status/` (Authenticated)
3. `POST /api/verification/persona-init/` (Authenticated generation)
4. `POST /api/verification/webhook/`
5. `POST /api/verification/persona-webhook/`

You can immediately import this into your Postman application. When testing the Persona Webhook locally, just disable the `.env` `PERSONA_WEBHOOK_SECRET` locally to bypass the signature check during manual dev testing!
