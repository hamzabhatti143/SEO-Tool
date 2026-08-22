<?php
/**
 * Uninstall cleanup — remove the stored API key option.
 *
 * @package RankPilot\Connector
 */

// Only run when WordPress itself is uninstalling this plugin.
if ( ! defined( 'WP_UNINSTALL_PLUGIN' ) ) {
	exit;
}

delete_option( 'rankpilot_connector_api_key' );
