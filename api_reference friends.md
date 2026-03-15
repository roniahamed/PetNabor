# Friend System API Professional Reference

This document serves as the official integration and testing guide for the **PatNabor Friend System**. 

## Global Configuration
- **Base URL:** `{{baseUrl}}/api`
- **Authentication:** `Authorization: Bearer <access_token>`
- **Content-Type:** `application/json`
- **Pagination:** Most list endpoints use `PageNumberPagination`.
    - `page`: Page number (default: 1)
    - `page_size`: Number of results per page (default: 20, max: 100)
    - **Paginated Response Structure:**
      ```json
      {
          "count": 125,
          "next": "http://api.example.com/path/?page=2",
          "previous": null,
          "results": [...]
      }
      ```

---

## 1. Discovery & Search
Endpoints used to find users to interact with.

### Search Nearby Users
Find candidates based on location and type.
- **Method:** `GET`
- **Path:** `/friends/search/`
- **Params:**
    - [type](file:///home/roni/Desktop/PatNabor/api/friends/filters.py#10-16): `patpal` or `patnabor` (Optional, omit for all)
    - [radius](file:///home/roni/Desktop/PatNabor/api/friends/filters.py#17-26): distance in miles (Use [all](file:///home/roni/Desktop/PatNabor/api/notifications/views.py#86-90) or `none` for global search)
    - [search](file:///home/roni/Desktop/PatNabor/api/friends/tests.py#226-238): name/username filter
    - [city](file:///home/roni/Desktop/PatNabor/api/friends/filters.py#27-30): Filter by city name (e.g., `Dhaka`)
    - [state](file:///home/roni/Desktop/PatNabor/api/friends/filters.py#31-34): Filter by state/region
    - [include_friends](file:///home/roni/Desktop/PatNabor/api/friends/filters.py#39-43): `true` (default) or `false` to exclude established connections.
- **Postman Automation (Tests):**
  ```javascript
  // Auto-save the first user ID found to "receiver_id"
  const jsonData = pm.response.json();
  if (jsonData.length > 0) {
      pm.collectionVariables.set("receiver_id", jsonData[0].id);
      console.log("Saved receiver_id: " + jsonData[0].id);
  }
  ```

---

## 2. Friend Request Lifecycle
Complete flow for managing friend connections.

### Send Friend Request
Initiate a request to a user.
- **Method:** `POST`
- **Path:** `/friends/requests/`
- **Body:** 
  ```json
  {
      "receiver_id": "{{receiver_id}}"
  }
  ```

### List Friend Requests
View pending, sent, or received requests.
- **Method:** `GET`
- **Path:** `/friends/requests/`
- **Params:** `type=sent` or `type=received`
- **Postman Automation (Tests):**
  ```javascript
  // Auto-save the first request ID to "request_id" for accept/reject/cancel
  const jsonData = pm.response.json();
  if (jsonData.length > 0) {
      pm.collectionVariables.set("request_id", jsonData[0].id);
      console.log("Saved request_id: " + jsonData[0].id);
  }
  ```

### Accept / Reject / Cancel Request
Action endpoints using the Request ID.
- **Accept:** `POST /friends/requests/{{request_id}}/accept/`
- **Reject:** `POST /friends/requests/{{request_id}}/reject/`
- **Cancel:** `POST /friends/requests/{{request_id}}/cancel/`
- **Body:** `{}` (Empty JSON object)

---

## 3. Relationship Management
Managing established friendships.

### List Friends
View current friend list.
- **Method:** `GET`
- **Path:** `/friends/list/`
- **Params:** `type=petpals` or `type=petnabors`
- **Postman Automation (Tests):**
  ```javascript
  // Save first friend's ID to "friend_user_id" for unfriending
  const jsonData = pm.response.json();
  if (jsonData.length > 0) {
      const friendId = jsonData[0].user1 === pm.environment.get("my_id") ? jsonData[0].user2 : jsonData[0].user1;
      pm.collectionVariables.set("friend_user_id", friendId);
  }
  ```

### Unfriend (Remove Friend)
Terminate a friendship.
- **Method:** `POST`
- **Path:** `/friends/remove/`
- **Body:** 
  ```json
  {
      "user_id": "{{friend_user_id}}"
  }
  ```

---

## 4. Security & Blocking
Preventing unwanted interactions.

### View Block List
Retrieve users you have blocked.
- **Method:** `GET`
- **Path:** `/friends/block/`
- **Postman Automation (Tests):**
  ```javascript
  // Save first blocked user ID to "blocked_user_id" for unblocking
  const jsonData = pm.response.json();
  if (jsonData.length > 0) {
      pm.collectionVariables.set("blocked_user_id", jsonData[0].blocked_user);
  }
  ```

### Block User
Block a user by their ID.
- **Method:** `POST`
- **Path:** `/friends/block/`
- **Body:** 
  ```json
  {
      "user_id": "{{some_user_id}}"
  }
  ```

### Unblock User
Remove a user from your block list.
- **Method:** `DELETE`
- **Path:** `/friends/block/`
- **Body:** 
  ```json
  {
      "user_id": "{{blocked_user_id}}"
  }
  ```

---

## Postman Setup Guide
1. Set `baseUrl` variable to your direct API root (e.g., `http://127.0.0.1:8000`).
2. The endpoints above are relative to `{{baseUrl}}/api`.
3. Use the **Tests** tab in Postman to paste the JavaScript snippets provided; this makes testing 100% automated by chaining the IDs together.
