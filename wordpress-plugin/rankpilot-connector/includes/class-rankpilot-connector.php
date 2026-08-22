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
		$this->admin = new RankPilot_Connector_Admin();
		$this->register_hooks();
	}

	/**
	 * Register WordPress hooks.
	 *
	 * @return void
	 */
	private function register_hooks() {
		add_action( 'rest_api_init', array( $this->rest, 'register_routes' ) );

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
