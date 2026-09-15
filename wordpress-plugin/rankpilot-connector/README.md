# RankPilot Connector (WordPress plugin)

Connects a WordPress site to **RankPilot AI**. It exposes a secure REST
health-check that RankPilot calls to verify the connection, and manages the
API key you paste into RankPilot's **Connect Your Site** flow.

## What it does

- Registers `GET /wp-json/rankpilot/v1/health`, protected by a Bearer API key.
- Generates an API key on activation and shows it under **Settings → RankPilot**
  (with a "Regenerate key" button).
- Verifies incoming keys with a constant-time comparison (`hash_equals`).
- Exposes a **fix engine** (`/snapshot`, `/apply-fix`, `/revert`) that
  RankPilot's auto-fix system drives — every change is recorded in
  `wp_rankpilot_changes` so it can be reverted. It covers **Core Web Vitals**
  fixes and **Technical-SEO** fixes (redirects, canonicals, sitemap, broken
  internal links, mixed content, image alt text).

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

Some fixes need extra parameters (a final destination, a replacement URL, AI
alt text, …). Pass them as a **`data`** object on `/snapshot`; the plugin
stores it (in the `data` column) so both `/apply-fix` and `/revert` can use it.

**Core Web Vitals** `change_type` / `fix_type` values:

| change_type        | target                                   | what's snapshotted/edited        |
| ------------------ | ---------------------------------------- | -------------------------------- |
| image_compression  | attachment id, image URL, or file path   | the image file bytes (in uploads)|
| lazy_load          | post/page id or URL                      | the post_content HTML            |
| image_dimensions   | post/page id or URL                      | the post_content HTML            |
| defer_css          | a stylesheet **handle** or its **URL**   | the deferred-targets option      |
| font_display       | a CSS file path inside the active theme  | the CSS file content             |

**Technical-SEO** `change_type` / `fix_type` values (backend only calls these
for **`auto`**-confidence issues; `suggest`/`manual` items — broken *external*
links, duplicate content, orphan pages, low-confidence broken internal links —
are **not** applied via the plugin, they surface as recommendations in the UI):

| change_type          | target                        | `data`                              | mechanism (all revertible)                                   |
| -------------------- | ----------------------------- | ----------------------------------- | ------------------------------------------------------------ |
| redirect_chain       | source URL or path            | `{ "final_url": "…" }`               | managed source→final 301 via a `template_redirect` hook (option-backed; bypasses intermediate hops). No file edits. |
| missing_canonical    | post/page id or URL           | `{ "canonical": "…" }` (optional; defaults to the page's own permalink) | stores `_rankpilot_canonical` post-meta; printed in `wp_head` for that post, replacing WP's default canonical |
| incorrect_canonical  | post/page id or URL           | `{ "canonical": "…" }`               | same as above (corrects the canonical URL)                   |
| missing_sitemap      | `"site"` (any non-empty)      | —                                   | force-enables WordPress's built-in sitemap (`/wp-sitemap.xml`) via the `wp_sitemaps_enabled` filter (option-backed) |
| broken_internal_link | post/page id or URL           | `{ "broken_url": "…", "replacement_url": "…" }` | find-and-replace the broken `href` with the replacement in `post_content` (snapshots full content) |
| mixed_content        | post/page id or URL           | `{ "resources": ["http://…", …] }`  | replaces the given `http://` resource URLs with `https://` in `post_content` (only URLs the backend confirmed reachable) |
| missing_alt_text     | attachment id or image URL    | `{ "alt": "AI-generated alt text" }`| sets `_wp_attachment_image_alt` on the attachment             |

### `POST /rankpilot/v1/snapshot`

Request (CWV):
```json
{ "change_type": "lazy_load", "target": "https://example.com/post" }
```
Request (Technical SEO, with `data`):
```json
{
  "change_type": "redirect_chain",
  "target": "https://example.com/old-page",
  "data": { "final_url": "https://example.com/new-page" }
}
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
| 400  | Bad/absent `change_type`/`target`/`change_id`, missing required `data` (e.g. `final_url`, `replacement_url`, `alt`), unresolvable target, or a target outside uploads/theme |
| 401  | Missing / wrong API key |
| 404  | `change_id` (or the resolved file/post) not found |
| 409  | `apply-fix` on a non-`snapshotted` row, or `revert` on an already-`reverted` row |
| 500  | Read/write failure on the host |

Writes are confined to the **uploads** directory (images) and the **active
theme** (CSS); `defer_css` uses a `style_loader_tag` filter, and content fixes
(`lazy_load`, `image_dimensions`, `broken_internal_link`, `mixed_content`) edit
`post_content` (fully reverted from the snapshot). The Technical-SEO fixes make
**no file edits**: redirects, canonicals and the sitemap toggle are stored as
managed WordPress **options / post-meta** and applied via runtime hooks
(`template_redirect`, `wp_head`, `wp_sitemaps_enabled`), so every change is safe
and reverts cleanly. Reverting a change restores the prior option/meta/content.

## Install (development)

1. Copy the `rankpilot-connector/` directory into your site's
   `wp-content/plugins/` folder (or zip it and upload via **Plugins → Add New →
   Upload**).
2. Activate **RankPilot Connector**.
3. Open **Settings → RankPilot**, copy the API key.
4. In RankPilot, go to **Connect Your Site → WordPress**, enter your site URL
   and paste the key.

## Fallback transport (admin-ajax.php)

The REST routes above only run once a request reaches WordPress's
`index.php` with permalinks resolved. On some hosts the public site root
never reaches WordPress at all — a stray static `index.html` in the web
root, a CDN/reverse-proxy rule, a cached response — even though
`/wp-admin/` works fine, because files under `/wp-admin/` are requested
directly and don't depend on WordPress's rewrite layer. `admin-ajax.php`
is in that same category: a real, always-present file, reachable even
when `/` and `/wp-json/*` are not.

Every route also exists as an `admin-ajax.php` action with the identical
JSON contract:

| REST route              | admin-ajax.php equivalent                                    |
| ------------------------ | ------------------------------------------------------------ |
| `GET /rankpilot/v1/health`     | `GET/POST admin-ajax.php?action=rankpilot_health`       |
| `POST /rankpilot/v1/snapshot`  | `POST admin-ajax.php?action=rankpilot_snapshot`          |
| `POST /rankpilot/v1/apply-fix` | `POST admin-ajax.php?action=rankpilot_apply_fix`         |
| `POST /rankpilot/v1/revert`    | `POST admin-ajax.php?action=rankpilot_revert`            |

Auth is the same Bearer key. If the `Authorization` header doesn't survive
the trip (common on some AJAX/CDN setups), pass the key as a
`rankpilot_key` request parameter instead — still checked with
`hash_equals()`, so this only changes where the key is allowed to travel,
not how strictly it's checked.

**Settings → RankPilot** self-tests both transports on page load (an
internal loopback request, the same check RankPilot's backend would make)
and shows which one is actually reachable right now, with the exact URL to
paste into RankPilot's **Connect Your Site** form.

This does not fix a misrouted site root — visitors are still served
whatever the server/CDN is serving there, which is a hosting-level problem
outside any plugin's reach — it only gives RankPilot a reliable channel to
this plugin regardless of that problem.

## Layout

```
rankpilot-connector/
├── rankpilot-connector.php                       # Plugin header + bootstrap
├── includes/
│   ├── class-rankpilot-connector.php             # Hook wiring (singleton)
│   ├── class-rankpilot-connector-rest.php        # health + fix routes + permission
│   ├── class-rankpilot-connector-ajax.php        # admin-ajax.php fallback transport (same contract)
│   ├── class-rankpilot-connector-auth.php        # Key storage + Bearer/param check
│   ├── class-rankpilot-connector-fixes.php       # snapshot/apply/revert + changes table
│   └── class-rankpilot-connector-admin.php       # Settings → RankPilot screen + self-test
├── uninstall.php                                 # Removes the key + drops the table
└── README.md
```

## Notes

- Some servers strip the `Authorization` header; the plugin also reads
  `HTTP_AUTHORIZATION` / `REDIRECT_HTTP_AUTHORIZATION`, `getallheaders()`,
  and a `rankpilot_key` request parameter as fallbacks. If REST auth still
  fails, add this to `.htaccess`: `SetEnvIf Authorization "(.*)" HTTP_AUTHORIZATION=$1`.
- If `/wp-json/rankpilot/v1/health` isn't reachable at all (not a 401, but
  a timeout, a 404, or the wrong site's content) the problem is upstream of
  WordPress — check **Settings → RankPilot** for a self-test, and use the
  **Fallback endpoint** (admin-ajax.php) shown there instead.
- The key is stored as a WordPress option and never exposed except on the
  authenticated settings screen. Regenerating invalidates the old key.
