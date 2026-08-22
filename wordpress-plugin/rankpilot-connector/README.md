# RankPilot Connector (WordPress plugin)

Connects a WordPress site to **RankPilot AI**. It exposes a secure REST
health-check that RankPilot calls to verify the connection, and manages the
API key you paste into RankPilot's **Connect Your Site** flow.

## What it does

- Registers `GET /wp-json/rankpilot/v1/health`, protected by a Bearer API key.
- Generates an API key on activation and shows it under **Settings → RankPilot**
  (with a "Regenerate key" button).
- Verifies incoming keys with a constant-time comparison (`hash_equals`).

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
│   ├── class-rankpilot-connector-rest.php        # /health route + permission
│   ├── class-rankpilot-connector-auth.php        # Key storage + Bearer check
│   └── class-rankpilot-connector-admin.php       # Settings → RankPilot screen
├── uninstall.php                                 # Removes the stored key
└── README.md
```

## Notes

- Some servers strip the `Authorization` header; the plugin also reads
  `HTTP_AUTHORIZATION` / `REDIRECT_HTTP_AUTHORIZATION` and `getallheaders()` as
  fallbacks. If auth still fails, add this to `.htaccess`:
  `SetEnvIf Authorization "(.*)" HTTP_AUTHORIZATION=$1`.
- The key is stored as a WordPress option and never exposed except on the
  authenticated settings screen. Regenerating invalidates the old key.
