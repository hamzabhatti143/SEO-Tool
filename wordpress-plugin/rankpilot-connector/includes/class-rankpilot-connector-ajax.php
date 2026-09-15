<?php
/**
 * Fallback transport: the same health / snapshot / apply-fix / revert
 * actions, exposed over wp-admin/admin-ajax.php instead of /wp-json/.
 *
 * Why this exists: the REST routes in class-rankpilot-connector-rest.php
 * only run once a request reaches WordPress's index.php with pretty
 * permalinks resolved. On some hosts the public site root never reaches
 * WordPress at all (a stray static index.html in the web root, a
 * misconfigured reverse proxy/CDN rule, a server that's pointed somewhere
 * else) even though /wp-admin/ works fine, because /wp-admin/*.php files
 * are requested directly and don't depend on WordPress's rewrite/routing
 * layer. admin-ajax.php is in that same category: it's a real, always-
 * present PHP file, so it's reachable even when '/' and '/wp-json/*' are
 * not. This does not fix a broken root domain (visitors are still shown
 * the wrong site) - it only gives RankPilot a reliable channel to reach
 * this plugin regardless of that problem.
 *
 * Contract mirrors the REST routes exactly: same JSON shapes, same
 * Bearer-key auth. Because some AJAX/CDN setups strip the Authorization
 * header, the key may also be supplied as a request parameter
 * (rankpilot_key) - see RankPilot_Connector_Auth::get_bearer_token().
 *
 * @package RankPilot\Connector
 */

if ( ! defined( 'ABSPATH' ) ) {
	exit;
}

/**
 * Registers admin-ajax.php actions that mirror the REST routes.
 */
class RankPilot_Connector_Ajax {

	/**
	 * Register the wp_ajax_* / wp_ajax_nopriv_* hooks.
	 *
	 * nopriv is required because RankPilot calls this as an outside
	 * service, not as a logged-in WordPress user - authorization is done
	 * entirely via the Bearer/param API key, the same as the REST routes.
	 *
	 * @return void
	 */
	public function register() {
		$actions = array(
			'rankpilot_health'     => 'health',
			'rankpilot_snapshot'   => 'snapshot',
			'rankpilot_apply_fix'  => 'apply_fix',
			'rankpilot_revert'     => 'revert',
		);

		foreach ( $actions as $action => $method ) {
			add_action( 'wp_ajax_' . $action, array( $this, $method ) );
			add_action( 'wp_ajax_nopriv_' . $action, array( $this, $method ) );
		}
	}

	/**
	 * Shared guard: verify the API key before running any action.
	 * Sends a 401 JSON response and exits when unauthorized.
	 *
	 * @return void
	 */
	private function require_auth() {
		if ( RankPilot_Connector_Auth::is_authorized( null ) ) {
			return;
		}

		wp_send_json(
			array(
				'code'    => 'rankpilot_unauthorized',
				'message' => __( 'Invalid or missing RankPilot API key.', 'rankpilot-connector' ),
				'data'    => array( 'status' => 401 ),
			),
			401
		);
	}

	/**
	 * GET/POST action=rankpilot_health - same payload as the REST /health route.
	 *
	 * @return void
	 */
	public function health() {
		$this->require_auth();

		wp_send_json(
			array(
				'status'         => 'ok',
				'plugin'         => 'rankpilot-connector',
				'plugin_version' => RANKPILOT_CONNECTOR_VERSION,
				'wp_version'     => get_bloginfo( 'version' ),
				'site_url'       => home_url(),
				'name'           => get_bloginfo( 'name' ),
				'timestamp'      => gmdate( 'c' ),
				'transport'      => 'admin-ajax',
			),
			200
		);
	}

	/**
	 * POST action=rankpilot_snapshot - delegates to the same handler the
	 * REST route uses, so the two transports can never drift apart.
	 *
	 * @return void
	 */
	public function snapshot() {
		$this->require_auth();
		$this->relay( array( 'RankPilot_Connector_Fixes', 'snapshot' ) );
	}

	/**
	 * POST action=rankpilot_apply_fix.
	 *
	 * @return void
	 */
	public function apply_fix() {
		$this->require_auth();
		$this->relay( array( 'RankPilot_Connector_Fixes', 'apply_fix' ) );
	}

	/**
	 * POST action=rankpilot_revert.
	 *
	 * @return void
	 */
	public function revert() {
		$this->require_auth();
		$this->relay( array( 'RankPilot_Connector_Fixes', 'revert' ) );
	}

	/**
	 * Build a minimal WP_REST_Request from the raw POST body/params so the
	 * existing Fixes handlers (written for REST) can be reused as-is, and
	 * send their WP_REST_Response back out as plain JSON.
	 *
	 * @param callable $callback REST-style handler: fn( WP_REST_Request ).
	 * @return void
	 */
	private function relay( $callback ) {
		$request = new WP_REST_Request( 'POST' );

		$raw  = (string) file_get_contents( 'php://input' );
		$json = json_decode( $raw, true );
		if ( is_array( $json ) ) {
			// The Fixes handlers read $request->get_json_params(), so the
			// request must carry a JSON body + content-type exactly like a
			// real REST request. set_body_params() alone leaves get_json_params()
			// empty over admin-ajax, which made every call fail with
			// "Unknown or missing change_type".
			$request->set_header( 'Content-Type', 'application/json' );
			$request->set_body( $raw );
			$request->set_body_params( $json );
		}
		// phpcs:ignore WordPress.Security.NonceVerification.Missing -- key-based auth, not cookie auth.
		foreach ( $_POST as $k => $v ) {
			if ( 'action' === $k ) {
				continue;
			}
			$request->set_param( sanitize_key( $k ), wp_unslash( $v ) );
		}

		$response = call_user_func( $callback, $request );

		if ( is_wp_error( $response ) ) {
			$data   = $response->get_error_data();
			$status = isset( $data['status'] ) ? (int) $data['status'] : 500;
			wp_send_json(
				array(
					'code'    => $response->get_error_code(),
					'message' => $response->get_error_message(),
					'data'    => $data,
				),
				$status
			);
			return;
		}

		if ( $response instanceof WP_REST_Response ) {
			wp_send_json( $response->get_data(), $response->get_status() );
			return;
		}

		wp_send_json( $response, 200 );
	}
}
