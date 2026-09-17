<?php
/**
 * Uninstall cleanup — remove stored options and the changes table.
 *
 * @package RankPilot\Connector
 */

// Only run when WordPress itself is uninstalling this plugin.
if ( ! defined( 'WP_UNINSTALL_PLUGIN' ) ) {
	exit;
}

global $wpdb;

delete_option( 'rankpilot_connector_api_key' );
delete_option( 'rankpilot_connector_deferred_handles' );
delete_option( 'rankpilot_connector_deferred_js' );
delete_option( 'rankpilot_connector_media_reserve' );
delete_option( 'rankpilot_connector_db_version' );

// Drop the fix-tracking table. Name is derived from the trusted prefix.
$table = $wpdb->prefix . 'rankpilot_changes';
$wpdb->query( "DROP TABLE IF EXISTS {$table}" ); // phpcs:ignore WordPress.DB
