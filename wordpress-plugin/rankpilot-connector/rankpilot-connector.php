<?php
/**
 * Plugin Name:       RankPilot Connector
 * Plugin URI:        https://rankpilot.ai
 * Description:       Connects your WordPress site to RankPilot AI. Exposes a secure REST health-check that RankPilot uses to verify the connection, and manages the API key you paste into RankPilot.
 * Version:           0.1.0
 * Requires at least: 5.6
 * Requires PHP:      7.4
 * Author:            RankPilot AI
 * Author URI:        https://rankpilot.ai
 * License:           GPL-2.0-or-later
 * License URI:       https://www.gnu.org/licenses/gpl-2.0.html
 * Text Domain:       rankpilot-connector
 *
 * @package RankPilot\Connector
 */

if ( ! defined( 'ABSPATH' ) ) {
	exit; // No direct access.
}

define( 'RANKPILOT_CONNECTOR_VERSION', '0.1.0' );
define( 'RANKPILOT_CONNECTOR_FILE', __FILE__ );
define( 'RANKPILOT_CONNECTOR_DIR', plugin_dir_path( __FILE__ ) );
// Must match app.core.config.WORDPRESS_API_NAMESPACE on the RankPilot backend.
define( 'RANKPILOT_CONNECTOR_REST_NAMESPACE', 'rankpilot/v1' );
define( 'RANKPILOT_CONNECTOR_OPTION_KEY', 'rankpilot_connector_api_key' );

require_once RANKPILOT_CONNECTOR_DIR . 'includes/class-rankpilot-connector-auth.php';
require_once RANKPILOT_CONNECTOR_DIR . 'includes/class-rankpilot-connector-rest.php';
require_once RANKPILOT_CONNECTOR_DIR . 'includes/class-rankpilot-connector-admin.php';
require_once RANKPILOT_CONNECTOR_DIR . 'includes/class-rankpilot-connector.php';

// Generate an API key on activation so the site is connectable immediately.
register_activation_hook(
	__FILE__,
	array( 'RankPilot_Connector_Auth', 'maybe_generate_key' )
);

// Bootstrap once all plugins are loaded.
add_action( 'plugins_loaded', array( 'RankPilot_Connector', 'instance' ) );
