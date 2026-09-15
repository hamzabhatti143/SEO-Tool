<?php
/**
 * API-key generation and Bearer-token verification.
 *
 * @package RankPilot\Connector
 */

if ( ! defined( 'ABSPATH' ) ) {
	exit;
}

/**
 * Handles the stored API key and authenticating incoming requests against it.
 */
class RankPilot_Connector_Auth {

	/**
	 * Generate and store an API key on activation if one isn't set yet.
	 *
	 * @return void
	 */
	public static function maybe_generate_key() {
		if ( '' === self::get_key() ) {
			self::regenerate_key();
		}
	}

	/**
	 * Return the stored API key (empty string when none is set).
	 *
	 * @return string
	 */
	public static function get_key() {
		return (string) get_option( RANKPILOT_CONNECTOR_OPTION_KEY, '' );
	}

	/**
	 * Generate a fresh API key, persist it, and return it.
	 *
	 * Uses alphanumeric-only characters so the key is safe to paste into an
	 * HTTP header and into the RankPilot UI.
	 *
	 * @return string
	 */
	public static function regenerate_key() {
		$key = wp_generate_password( 48, false, false );
		update_option( RANKPILOT_CONNECTOR_OPTION_KEY, $key, false );
		return $key;
	}

	/**
	 * Extract the Bearer token from the current request.
	 *
	 * Prefers the parsed REST header, then falls back to raw $_SERVER keys
	 * because some server configs (e.g. CGI/FastCGI, and some CDN/proxy
	 * layers) drop or rename the Authorization header. As a last resort,
	 * accepts the key as a plain request parameter (rankpilot_key) - used
	 * by the admin-ajax.php fallback transport for hosts where the header
	 * never survives the trip. Still compared with hash_equals(), so this
	 * doesn't weaken the check, only where the key is allowed to travel.
	 *
	 * @param WP_REST_Request|null $request Optional REST request.
	 * @return string The token, or '' if none present.
	 */
	public static function get_bearer_token( $request = null ) {
		$header = '';

		if ( $request instanceof WP_REST_Request ) {
			$header = (string) $request->get_header( 'authorization' );
		}

		if ( '' === $header && isset( $_SERVER['HTTP_AUTHORIZATION'] ) ) {
			$header = wp_unslash( $_SERVER['HTTP_AUTHORIZATION'] );
		}

		if ( '' === $header && isset( $_SERVER['REDIRECT_HTTP_AUTHORIZATION'] ) ) {
			$header = wp_unslash( $_SERVER['REDIRECT_HTTP_AUTHORIZATION'] );
		}

		if ( '' === $header && function_exists( 'getallheaders' ) ) {
			foreach ( getallheaders() as $name => $value ) {
				if ( 'authorization' === strtolower( (string) $name ) ) {
					$header = (string) $value;
					break;
				}
			}
		}

		$header = trim( (string) $header );
		if ( 0 === stripos( $header, 'bearer ' ) ) {
			return trim( substr( $header, 7 ) );
		}

		// Last resort: explicit key parameter (admin-ajax fallback, or a
		// REST call made with ?rankpilot_key=... when headers are stripped
		// somewhere upstream).
		if ( $request instanceof WP_REST_Request ) {
			$param = $request->get_param( 'rankpilot_key' );
			if ( is_string( $param ) && '' !== $param ) {
				return trim( $param );
			}
		}
		// phpcs:ignore WordPress.Security.NonceVerification.Recommended -- key-based auth, not cookie auth; value is hash_equals-checked.
		if ( isset( $_REQUEST['rankpilot_key'] ) ) {
			return trim( wp_unslash( $_REQUEST['rankpilot_key'] ) ); // phpcs:ignore WordPress.Security.ValidatedSanitizedInput.MissingUnslash
		}

		return '';
	}

	/**
	 * Verify the request carries the correct API key.
	 *
	 * Uses hash_equals() for a constant-time comparison so the key can't be
	 * discovered via a timing side-channel.
	 *
	 * @param WP_REST_Request $request REST request.
	 * @return bool
	 */
	public static function is_authorized( $request ) {
		$stored = self::get_key();
		if ( '' === $stored ) {
			return false;
		}

		$provided = self::get_bearer_token( $request );
		if ( '' === $provided ) {
			return false;
		}

		return hash_equals( $stored, $provided );
	}
}
