# RankPilot Connector (WordPress plugin)

Connects a WordPress site to **RankPilot AI**. It exposes a secure REST
health-check that RankPilot calls to verify the connection, and manages the
API key you paste into RankPilot's **Connect Your Site** flow.

## What it does

- Registers `GET /wp-json/rankpilot/v1/health`, protected by a Bearer API key.
- Generates an API key on activation and shows it under **Settings → RankPilot**
  (with a "Regenerate key" button).
- Verifies incoming keys with a constant-time comparison (`hash_equals`).
- Exposes a **Core Web Vitals fix engine** (`/snapshot`, `/apply-fix`,
  `/revert`) that RankPilot's auto-fix system drives — every change is recorded
  in `wp_rankpilot_changes` so it can be reverted.

## The contract (must match the backend)

The RankPilot backend (`app/services/wordpress_service.py`) calls:

```
GET {site_url}/wp-json/rankpilot/v1/health
Authorization: Bearer {api_key}
Accept: application/json
```

and expects:

| Situation                     | HTTP | Backend interprets as            |
| ----------------------------- | ---- | -------------------------------- |
| Valid key                     | 200  | Connected (JSON `status: "ok"`)  |
| Missing / wrong key           | 401  | "Plugin rejected the API key"    |
| Plugin not installed/active   | 404  | "Install/activate the plugin"    |

The namespace (`rankpilot/v1`) mirrors `settings.WORDPRESS_API_NAMESPACE`.
A successful response body looks like:

```json
{
  "status": "ok",
  "plugin": "rankpilot-connector",
  "plugin_version": "0.1.0",
  "wp_version": "6.5",
  "site_url": "https://example.com",
  "name": "Example Blog",
  "timestamp": "2026-08-22T12:00:00+00:00"
}
```

## Fix engine contract (snapshot → apply → revert)

All three are `POST`, share the `rankpilot/v1` namespace, and require the same
`Authorization: Bearer {api_key}` header. They drive the WordPress side of the
Core Web Vitals auto-fix system; the backend
(`app/services/fix_service.py`) calls `/snapshot` then `/apply-fix`, stores the
returned `change_id` as its `external_change_id`, and calls `/revert` from the
Fix History "Revert" button.

Supported `change_type` / `fix_type` values: `image_compression`, `lazy_load`,
`defer_css`, `font_display`, `image_dimensions`. `target` meaning by type:

| change_type        | target                                   | what's snapshotted/edited        |
| ------------------ | ---------------------------------------- | -------------------------------- |
| image_compression  | attachment id, image URL, or file path   | the image file bytes (in uploads)|
| lazy_load          | post/page id or URL                      | the post_content HTML            |
| image_dimensions   | post/page id or URL                      | the post_content HTML            |
| defer_css          | a registered stylesheet **handle**       | the deferred-handles option      |
| font_display       | a CSS file path inside the active theme  | the CSS file content             |

### `POST /rankpilot/v1/snapshot`

Request:
```json
{ "change_type": "lazy_load", "target": "https://example.com/post" }
```
Response `200`:
```json
{ "change_id": 12, "status": "snapshotted" }
```

### `POST /rankpilot/v1/apply-fix`

Request:
```json
{ "change_id": 12, "fix_type": "lazy_load" }
```
Response `200` (snapshots are strings; base64 for images, HTML/CSS otherwise):
```json
{ "change_id": 12, "status": "applied", "before_snapshot": "…", "after_snapshot": "…" }
```

### `POST /rankpilot/v1/revert`

Request:
```json
{ "change_id": 12 }
```
Response `200`:
```json
{ "change_id": 12, "status": "reverted" }
```

### Status codes

| Code | When |
| ---- | ---- |
| 200  | Success |
| 400  | Bad/absent `change_type`/`target`/`change_id`, unresolvable target, or a target outside uploads/theme |
| 401  | Missing / wrong API key |
| 404  | `change_id` (or the resolved file/post) not found |
| 409  | `apply-fix` on a non-`snapshotted` row, or `revert` on an already-`reverted` row |
| 500  | Read/write failure on the host |

Writes are confined to the **uploads** directory (images) and the **active
theme** (CSS); `defer_css` uses a `style_loader_tag` filter, and `lazy_load` /
`image_dimensions` edit `post_content` (fully reverted from the snapshot).

## Install (development)

1. Copy the `rankpilot-connector/` directory into your site's
   `wp-content/plugins/` folder (or zip it and upload via **Plugins → Add New →
   Upload**).
2. Activate **RankPilot Connector**.
3. Open **Settings → RankPilot**, copy the API key.
4. In RankPilot, go to **Connect Your Site → WordPress**, enter your site URL
   and paste the key.

## Layout

```
rankpilot-connector/
├── rankpilot-connector.php                       # Plugin header + bootstrap
├── includes/
│   ├── class-rankpilot-connector.php             # Hook wiring (singleton)
│   ├── class-rankpilot-connector-rest.php        # health + fix routes + permission
│   ├── class-rankpilot-connector-auth.php        # Key storage + Bearer check
│   ├── class-rankpilot-connector-fixes.php       # snapshot/apply/revert + changes table
│   └── class-rankpilot-connector-admin.php       # Settings → RankPilot screen
├── uninstall.php                                 # Removes the key + drops the table
└── README.md
```

## Notes

- Some servers strip the `Authorization` header; the plugin also reads
  `HTTP_AUTHORIZATION` / `REDIRECT_HTTP_AUTHORIZATION` and `getallheaders()` as
  fallbacks. If auth still fails, add this to `.htaccess`:
  `SetEnvIf Authorization "(.*)" HTTP_AUTHORIZATION=$1`.
- The key is stored as a WordPress option and never exposed except on the
  authenticated settings screen. Regenerating invalidates the old key.
