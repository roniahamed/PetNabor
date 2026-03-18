# API Usage Guide: Post & Report

Base URL: `http://localhost:8001/api`

## Posts API

### 1. Create a Post
- **Endpoint**: `POST /posts/`
- **Body** (multipart/form-data):
  - `content_text`: (string) Post content
  - `privacy`: (string) "PUBLIC", "FRIENDS_ONLY", or "PRIVATE"
  - `location_point`: (string, optional) e.g., "POINT(0 0)"
  - `media`: (files) One or more image/video files

### 2. List Feed
- **Endpoint**: `GET /posts/feed/`
- **Description**: Returns a paginated list of posts from yourself and your friends.

### 3. Get Post Detail
- **Endpoint**: `GET /posts/{id}/`
- **Response**: Full post object including comments, likes, and media.

### 4. Like/Unlike a Post
- **Endpoint**: `POST /posts/{id}/like/` (to like)
- **Endpoint**: `DELETE /posts/{id}/like/` (to unlike)
- **Body** (for POST):
  - `reaction_type`: (string, optional) "LIKE", "LOVE", "HAHA", "SAD", "ANGRY" (Default: "LIKE")

### 5. Save/Unsave a Post
- **Endpoint**: `POST /posts/{id}/save_post/` (to save)
- **Endpoint**: `DELETE /posts/{id}/save_post/` (to unsave)

### 6. Delete a Post (Soft Delete)
- **Endpoint**: `DELETE /posts/{id}/`

---

## Comments API

### 1. Create a Comment/Reply
- **Endpoint**: `POST /comments/`
- **Body** (application/json):
  - `post`: (UUID) ID of the post
  - `comment_text`: (string) Text content
  - `parent_comment`: (UUID, optional) ID of the parent comment for replies
  - `media_file`: (file, optional) Optional attachment

### 2. List Comments for a Post
- **Endpoint**: `GET /comments/?post_id={uuid}`

### 3. List Replies for a Comment
- **Endpoint**: `GET /comments/{id}/replies/`

---

## Reports API

### 1. Submit a Report
- **Endpoint**: `POST /report/`
- **Body** (application/json):
  - `target_type`: (string) "USER", "POST", "COMMENT", "STORY", "BLOG", "MEETING"
  - `target_id`: (UUID) ID of the content being reported
  - `reason`: (string) Short reason
  - `description`: (string, optional) Detailed explanation

### 2. Mark Report as Resolved (Admin Only)
- **Endpoint**: `POST /report/{id}/resolve/`
