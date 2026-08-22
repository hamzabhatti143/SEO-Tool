<?php
/**
 * REST API routes exposed by the connector.
 *
 * The health-check is what the RankPilot backend calls to verify a
 * connection: GET /wp-json/rankpilot/v1/health with the API key as a
 * Bearer token. It returns { "status": "ok", ... } when the key is valid.
 *
 * @package RankPilot\Connector
 */

if ( ! defined( 'ABSPATH' ) ) {
	exit;
}

/**
 * Registers and handles the connector's REST endpoints.
 */
class RankPilot_Connector_REST {

	/**
	 * Register routes. Hooked to rest_api_init.
	 *
	 * The route is always registered while the plugin is active, so an absent
	 * route (HTTP 404) reliably signals "plugin not installed" to RankPilot,
	 * while a bad key returns 401.
	 *
	 * @return void
	 */
	public function register_routes() {
		register_rest_route(
			RANKPILOT_CONNECTOR_REST_NAMESPACE,
			'/health',
			array(
				'methods'             => WP_REST_Server::READABLE,
				'callback'            => array( $this, 'health' ),
				'permission_callback' => array( $this, 'authorize' ),
			)
		);
	}

	/**
	 * Permission callback: require a valid RankPilot API key.
	 *
	 * @param WP_REST_Request $request REST request.
	 * @return true|WP_Error True when authorized, else a 401 error.
	 */
	public function authorize( $request ) {
		if ( RankPilot_Connector_Auth::is_authorized( $request ) ) {
			return true;
		}

		return new WP_Error(
			'rankpilot_unauthorized',
			__( 'Invalid or missing RankPilot API key.', 'rankpilot-connector' ),
			array( 'status' => 401 )
		);
	}

	/**
	 * Health-check handler. RankPilot polls this to verify the connection.
	 *
	 * @return WP_REST_Response
	 */
	public function health() {
		return new WP_REST_Response(
			array(
				'status'         => 'ok',
				'plugin'         => 'rankpilot-connector',
				'plugin_version' => RANKPILOT_CONNECTOR_VERSION,
				'wp_version'     => get_bloginfo( 'version' ),
				'site_url'       => home_url(),
				'name'           => get_bloginfo( 'name' ),
				'timestamp'      => gmdate( 'c' ),
			),
			200
		);
	}
}
