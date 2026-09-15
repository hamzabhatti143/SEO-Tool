<?php
/**
 * Admin settings screen: display and regenerate the API key.
 *
 * @package RankPilot\Connector
 */

if ( ! defined( 'ABSPATH' ) ) {
	exit;
}

/**
 * Renders Settings → RankPilot and handles key regeneration.
 */
class RankPilot_Connector_Admin {

	const PAGE_SLUG         = 'rankpilot-connector';
	const REGENERATE_ACTION = 'rankpilot_regenerate_key';

	/**
	 * Register the settings page under the Settings menu.
	 *
	 * @return void
	 */
	public function register_menu() {
		add_options_page(
			__( 'RankPilot Connector', 'rankpilot-connector' ),
			__( 'RankPilot', 'rankpilot-connector' ),
			'manage_options',
			self::PAGE_SLUG,
			array( $this, 'render_page' )
		);
	}

	/**
	 * Add a "Settings" link on the Plugins list row.
	 *
	 * @param string[] $links Existing action links.
	 * @return string[]
	 */
	public function action_links( $links ) {
		$settings = sprintf(
			'<a href="%s">%s</a>',
			esc_url( admin_url( 'options-general.php?page=' . self::PAGE_SLUG ) ),
			esc_html__( 'Settings', 'rankpilot-connector' )
		);
		array_unshift( $links, $settings );
		return $links;
	}

	/**
	 * Handle the "regenerate key" form POST (via admin-post.php).
	 *
	 * @return void
	 */
	public function handle_regenerate() {
		if ( ! current_user_can( 'manage_options' ) ) {
			wp_die(
				esc_html__( 'You do not have permission to do this.', 'rankpilot-connector' )
			);
		}

		check_admin_referer( self::REGENERATE_ACTION );
		RankPilot_Connector_Auth::regenerate_key();

		wp_safe_redirect(
			add_query_arg(
				array(
					'page'        => self::PAGE_SLUG,
					'regenerated' => '1',
				),
				admin_url( 'options-general.php' )
			)
		);
		exit;
	}

	/**
	 * Internal loopback check: does this URL actually answer with a valid
	 * RankPilot JSON response right now? Used to self-test both transports
	 * from inside WordPress, so problems show up here instead of only
	 * surfacing as a confusing error in the RankPilot dashboard later.
	 *
	 * @param string $url Endpoint to test.
	 * @param string $key Current API key (sent as a request param, since
	 *                    this is the same fallback path used when headers
	 *                    don't survive the trip).
	 * @return bool
	 */
	private function self_test( $url, $key ) {
		if ( '' === $key ) {
			return false;
		}

		$response = wp_remote_get(
			add_query_arg( 'rankpilot_key', $key, $url ),
			array(
				'timeout'   => 8,
				'sslverify' => true,
			)
		);

		if ( is_wp_error( $response ) ) {
			return false;
		}

		if ( 200 !== (int) wp_remote_retrieve_response_code( $response ) ) {
			return false;
		}

		$body = json_decode( (string) wp_remote_retrieve_body( $response ), true );
		return is_array( $body ) && isset( $body['status'] ) && 'ok' === $body['status'];
	}

	/**
	 * Render the settings screen.
	 *
	 * @return void
	 */
	public function render_page() {
		if ( ! current_user_can( 'manage_options' ) ) {
			return;
		}

		$key          = RankPilot_Connector_Auth::get_key();
		$health_url   = rest_url( RANKPILOT_CONNECTOR_REST_NAMESPACE . '/health' );
		$fallback_url = add_query_arg( 'action', 'rankpilot_health', admin_url( 'admin-ajax.php' ) );
		$regenerated  = isset( $_GET['regenerated'] ); // phpcs:ignore WordPress.Security.NonceVerification.Recommended -- read-only notice flag.

		// Self-test both transports right here on page load, using an
		// internal loopback request - this is exactly what RankPilot does
		// from the outside, so a fail here reliably predicts a fail there.
		$rest_ok     = $this->self_test( $health_url, $key );
		$fallback_ok = $this->self_test( $fallback_url, $key );
		?>
		<div class="wrap">
			<h1><?php esc_html_e( 'RankPilot Connector', 'rankpilot-connector' ); ?></h1>

			<?php if ( $regenerated ) : ?>
				<div class="notice notice-success is-dismissible">
					<p><?php esc_html_e( 'A new API key was generated. Reconnect this site in RankPilot with the new key.', 'rankpilot-connector' ); ?></p>
				</div>
			<?php endif; ?>

			<p><?php esc_html_e( 'Copy this API key and paste it into RankPilot when connecting your WordPress site.', 'rankpilot-connector' ); ?></p>

			<table class="form-table" role="presentation">
				<tr>
					<th scope="row">
						<label for="rankpilot-api-key"><?php esc_html_e( 'API key', 'rankpilot-connector' ); ?></label>
					</th>
					<td>
						<input
							type="text"
							id="rankpilot-api-key"
							class="regular-text code"
							readonly
							value="<?php echo esc_attr( $key ); ?>"
							onfocus="this.select();"
						/>
					</td>
				</tr>
				<tr>
					<th scope="row"><?php esc_html_e( 'Site URL', 'rankpilot-connector' ); ?></th>
					<td><code><?php echo esc_html( home_url() ); ?></code></td>
				</tr>
				<tr>
					<th scope="row"><?php esc_html_e( 'Health endpoint', 'rankpilot-connector' ); ?></th>
					<td>
						<code><?php echo esc_html( $health_url ); ?></code>
						<?php echo $rest_ok ? '<span style="color:#00a32a;">&#10003; ' . esc_html__( 'reachable', 'rankpilot-connector' ) . '</span>' : '<span style="color:#d63638;">&#10007; ' . esc_html__( 'not reachable right now', 'rankpilot-connector' ) . '</span>'; ?>
					</td>
				</tr>
				<tr>
					<th scope="row"><?php esc_html_e( 'Fallback endpoint', 'rankpilot-connector' ); ?></th>
					<td>
						<code><?php echo esc_html( $fallback_url ); ?></code>
						<?php echo $fallback_ok ? '<span style="color:#00a32a;">&#10003; ' . esc_html__( 'reachable', 'rankpilot-connector' ) . '</span>' : '<span style="color:#d63638;">&#10007; ' . esc_html__( 'not reachable right now', 'rankpilot-connector' ) . '</span>'; ?>
						<p class="description">
							<?php esc_html_e( 'Use this URL instead in RankPilot if the health endpoint above shows a connection error (common on hosts where the site root doesn\'t route to WordPress the same way /wp-admin/ does).', 'rankpilot-connector' ); ?>
						</p>
					</td>
				</tr>
			</table>

			<?php if ( ! $rest_ok && ! $fallback_ok ) : ?>
				<div class="notice notice-error">
					<p>
						<strong><?php esc_html_e( 'Neither endpoint is reachable from this server right now.', 'rankpilot-connector' ); ?></strong>
						<?php esc_html_e( 'This usually means something outside WordPress (a CDN cache, a reverse proxy, or an extra index.html in the site root) is answering requests before they reach WordPress at all - no plugin can route around that from the inside. Check with your host or hosting control panel, or ask RankPilot support to help diagnose it.', 'rankpilot-connector' ); ?>
					</p>
				</div>
			<?php elseif ( ! $rest_ok && $fallback_ok ) : ?>
				<div class="notice notice-warning">
					<p><?php esc_html_e( 'The REST health endpoint isn\'t reachable, but the fallback endpoint is working - use the Fallback endpoint URL above when connecting this site in RankPilot.', 'rankpilot-connector' ); ?></p>
				</div>
			<?php endif; ?>

			<form method="post" action="<?php echo esc_url( admin_url( 'admin-post.php' ) ); ?>">
				<input type="hidden" name="action" value="<?php echo esc_attr( self::REGENERATE_ACTION ); ?>" />
				<?php wp_nonce_field( self::REGENERATE_ACTION ); ?>
				<?php submit_button( __( 'Regenerate key', 'rankpilot-connector' ), 'secondary' ); ?>
				<p class="description">
					<?php esc_html_e( 'Regenerating invalidates the old key — you will need to reconnect in RankPilot.', 'rankpilot-connector' ); ?>
				</p>
			</form>
		</div>
		<?php
	}
}
