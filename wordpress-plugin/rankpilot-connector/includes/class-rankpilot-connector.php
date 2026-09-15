<?php
/**
 * Plugin bootstrap: wires the REST + admin components to WordPress hooks.
 *
 * @package RankPilot\Connector
 */

if ( ! defined( 'ABSPATH' ) ) {
	exit;
}

/**
 * Singleton that boots the plugin's components.
 */
class RankPilot_Connector {

	/**
	 * Singleton instance.
	 *
	 * @var RankPilot_Connector|null
	 */
	private static $instance = null;

	/**
	 * REST controller.
	 *
	 * @var RankPilot_Connector_REST
	 */
	private $rest;

	/**
	 * admin-ajax.php fallback controller (used when /wp-json/ can't be
	 * reached - see class-rankpilot-connector-ajax.php).
	 *
	 * @var RankPilot_Connector_Ajax
	 */
	private $ajax;

	/**
	 * Admin screen controller.
	 *
	 * @var RankPilot_Connector_Admin
	 */
	private $admin;

	/**
	 * Boot (or return) the singleton.
	 *
	 * @return RankPilot_Connector
	 */
	public static function instance() {
		if ( null === self::$instance ) {
			self::$instance = new self();
		}
		return self::$instance;
	}

	/**
	 * Wire up components on construction.
	 */
	private function __construct() {
		$this->rest  = new RankPilot_Connector_REST();
		$this->ajax  = new RankPilot_Connector_Ajax();
		$this->admin = new RankPilot_Connector_Admin();
		// Create/upgrade the changes table for sites updated in place (not just
		// on fresh activation).
		RankPilot_Connector_Fixes::maybe_upgrade();
		$this->register_hooks();
	}

	/**
	 * Register WordPress hooks.
	 *
	 * @return void
	 */
	private function register_hooks() {
		add_action( 'rest_api_init', array( $this->rest, 'register_routes' ) );
		// Fallback transport - reachable even when /wp-json/ isn't (see
		// class-rankpilot-connector-ajax.php for why).
		add_action( 'init', array( $this->ajax, 'register' ) );

		// Front-end: apply the defer_css fix to any deferred stylesheet handles
		// or URLs (3rd arg is the href).
		add_filter(
			'style_loader_tag',
			array( 'RankPilot_Connector_Fixes', 'filter_defer_css' ),
			10,
			3
		);

		// Technical-SEO fixes applied at runtime (managed, revertible):
		// canonical override, source→final redirects, and forced sitemap.
		add_action(
			'wp_head',
			array( 'RankPilot_Connector_Fixes', 'output_canonical' ),
			9
		);
		add_action(
			'template_redirect',
			array( 'RankPilot_Connector_Fixes', 'do_managed_redirects' ),
			1
		);
		add_filter(
			'wp_sitemaps_enabled',
			array( 'RankPilot_Connector_Fixes', 'force_sitemap_enabled' )
		);

		if ( is_admin() ) {
			add_action( 'admin_menu', array( $this->admin, 'register_menu' ) );
			add_action(
				'admin_post_' . RankPilot_Connector_Admin::REGENERATE_ACTION,
				array( $this->admin, 'handle_regenerate' )
			);
			add_filter(
				'plugin_action_links_' . plugin_basename( RANKPILOT_CONNECTOR_FILE ),
				array( $this->admin, 'action_links' )
			);
		}
	}
}
