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
	 * Render the settings screen.
	 *
	 * @return void
	 */
	public function render_page() {
		if ( ! current_user_can( 'manage_options' ) ) {
			return;
		}

		$key         = RankPilot_Connector_Auth::get_key();
		$health_url  = rest_url( RANKPILOT_CONNECTOR_REST_NAMESPACE . '/health' );
		$regenerated = isset( $_GET['regenerated'] ); // phpcs:ignore WordPress.Security.NonceVerification.Recommended -- read-only notice flag.
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
					<td><code><?php echo esc_html( $health_url ); ?></code></td>
				</tr>
			</table>

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
