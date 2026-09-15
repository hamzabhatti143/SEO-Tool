<?php
/**
 * Core Web Vitals fix engine: snapshot → apply → revert.
 *
 * Exposes three REST actions (registered by the REST controller under the same
 * `rankpilot/v1` namespace + Bearer auth) and a `wp_rankpilot_changes` table
 * that records every change so it can be reverted:
 *
 *   POST /rankpilot/v1/snapshot   → capture the target's current state
 *   POST /rankpilot/v1/apply-fix  → apply the fix, record the "after" state
 *   POST /rankpilot/v1/revert     → restore the "before" state
 *
 * Supported change types:
 *   Core Web Vitals: image_compression, lazy_load, defer_css, font_display,
 *   image_dimensions.
 *   Technical SEO (auto-confidence fixes only): redirect_chain,
 *   missing_canonical, incorrect_canonical, missing_sitemap,
 *   broken_internal_link, mixed_content, missing_alt_text.
 *
 * All file/CSS writes are confined to the uploads directory (images) or the
 * active theme (CSS). Redirects, canonicals and the sitemap toggle are stored
 * as managed WordPress options / post-meta (no file edits) and applied via
 * runtime hooks, so every change is safe and fully revertible.
 *
 * Fix-specific parameters (final destination, replacement URL, AI alt text,
 * etc.) are passed on /snapshot as `data` (JSON) and stored in the `data`
 * column, so both apply-fix and revert can read them.
 *
 * @package RankPilot\Connector
 */

if ( ! defined( 'ABSPATH' ) ) {
	exit;
}

/**
 * Static utility: table management, REST handlers, and per-type fix logic.
 */
class RankPilot_Connector_Fixes {

	const TABLE           = 'rankpilot_changes';
	const DEFER_OPTION    = 'rankpilot_connector_deferred_handles';
	const REDIRECTS_OPTION = 'rankpilot_connector_redirects';
	const SITEMAP_OPTION  = 'rankpilot_connector_force_sitemap';
	const CANONICAL_META  = '_rankpilot_canonical';
	const CHANGE_TYPES    = array(
		// Core Web Vitals.
		'image_compression',
		'lazy_load',
		'defer_css',
		'font_display',
		'image_dimensions',
		// Technical SEO (auto-confidence only).
		'redirect_chain',
		'missing_canonical',
		'incorrect_canonical',
		'missing_sitemap',
		'broken_internal_link',
		'mixed_content',
		'missing_alt_text',
	);
	// Change types whose fix edits post_content (target = post id or URL).
	const CONTENT_TYPES   = array(
		'lazy_load',
		'image_dimensions',
		'broken_internal_link',
		'mixed_content',
	);

	// --- Table -----------------------------------------------------------

	public static function table_name() {
		global $wpdb;
		return $wpdb->prefix . self::TABLE;
	}

	/**
	 * Create/upgrade the changes table (idempotent, via dbDelta).
	 *
	 * @return void
	 */
	public static function create_table() {
		global $wpdb;
		require_once ABSPATH . 'wp-admin/includes/upgrade.php';
		$table   = self::table_name();
		$collate = $wpdb->get_charset_collate();

		// dbDelta is whitespace-sensitive: two spaces after PRIMARY KEY, each
		// column on its own line.
		$sql = "CREATE TABLE $table (
  id BIGINT UNSIGNED NOT NULL AUTO_INCREMENT,
  change_type VARCHAR(40) NOT NULL,
  target TEXT NOT NULL,
  data LONGTEXT NULL,
  before_snapshot LONGTEXT NULL,
  after_snapshot LONGTEXT NULL,
  status VARCHAR(20) NOT NULL DEFAULT 'snapshotted',
  created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
  PRIMARY KEY  (id)
) $collate;";

		dbDelta( $sql );
		update_option( 'rankpilot_connector_db_version', RANKPILOT_CONNECTOR_DB_VERSION );
	}

	/**
	 * Run the table migration when the stored schema version is behind.
	 *
	 * @return void
	 */
	public static function maybe_upgrade() {
		if ( get_option( 'rankpilot_connector_db_version' ) !== RANKPILOT_CONNECTOR_DB_VERSION ) {
			self::create_table();
		}
	}

	private static function get_row( $change_id ) {
		global $wpdb;
		// Table name is derived from the trusted $wpdb->prefix + a constant.
		return $wpdb->get_row(
			$wpdb->prepare(
				'SELECT * FROM ' . self::table_name() . ' WHERE id = %d', // phpcs:ignore WordPress.DB.PreparedSQL.InterpolatedNotPrepared
				$change_id
			)
		);
	}

	/**
	 * Decode the stored per-fix `data` JSON into an array.
	 *
	 * @param object $row Changes-table row.
	 * @return array
	 */
	private static function decode_data( $row ) {
		if ( empty( $row->data ) ) {
			return array();
		}
		$decoded = json_decode( (string) $row->data, true );
		return is_array( $decoded ) ? $decoded : array();
	}

	// --- REST handlers ---------------------------------------------------

	/**
	 * POST /snapshot — capture the target's current state and store a row.
	 *
	 * @param WP_REST_Request $request REST request.
	 * @return WP_REST_Response|WP_Error
	 */
	public static function snapshot( $request ) {
		$params      = (array) $request->get_json_params();
		$change_type = isset( $params['change_type'] ) ? sanitize_key( $params['change_type'] ) : '';
		$target      = isset( $params['target'] ) ? (string) $params['target'] : '';
		// Fix-specific parameters (final destination, replacement URL, alt
		// text, http resources to upgrade, …). Stored so apply/revert can use them.
		$data        = isset( $params['data'] ) && is_array( $params['data'] ) ? $params['data'] : array();

		if ( ! in_array( $change_type, self::CHANGE_TYPES, true ) ) {
			return self::error( 'invalid_change_type', 'Unknown or missing change_type.', 400 );
		}
		if ( '' === trim( $target ) ) {
			return self::error( 'missing_target', 'A target is required.', 400 );
		}

		$before = self::capture_before( $change_type, $target );
		if ( is_wp_error( $before ) ) {
			return $before;
		}

		global $wpdb;
		$ok = $wpdb->insert( // phpcs:ignore WordPress.DB.DirectDatabaseQuery
			self::table_name(),
			array(
				'change_type'     => $change_type,
				'target'          => $target,
				'data'            => wp_json_encode( $data ),
				'before_snapshot' => $before,
				'status'          => 'snapshotted',
				'created_at'      => gmdate( 'Y-m-d H:i:s' ),
			),
			array( '%s', '%s', '%s', '%s', '%s', '%s' )
		);
		if ( ! $ok ) {
			return self::error( 'db_error', 'Could not store the snapshot.', 500 );
		}

		return new WP_REST_Response(
			array(
				'change_id' => (int) $wpdb->insert_id,
				'status'    => 'snapshotted',
			),
			200
		);
	}

	/**
	 * POST /apply-fix — apply the recorded change and store the "after" state.
	 *
	 * @param WP_REST_Request $request REST request.
	 * @return WP_REST_Response|WP_Error
	 */
	public static function apply_fix( $request ) {
		$params    = (array) $request->get_json_params();
		$change_id = isset( $params['change_id'] ) ? (int) $params['change_id'] : 0;
		$fix_type  = isset( $params['fix_type'] ) ? sanitize_key( $params['fix_type'] ) : '';

		if ( $change_id <= 0 ) {
			return self::error( 'missing_change_id', 'A valid change_id is required.', 400 );
		}
		$row = self::get_row( $change_id );
		if ( ! $row ) {
			return self::error( 'not_found', 'Change not found.', 404 );
		}
		if ( 'snapshotted' !== $row->status ) {
			return self::error( 'invalid_state', 'Change is not in a snapshotted state.', 409 );
		}
		if ( '' !== $fix_type && $fix_type !== $row->change_type ) {
			return self::error( 'type_mismatch', 'fix_type does not match the snapshot.', 400 );
		}

		$data  = self::decode_data( $row );
		$after = self::apply_change( $row->change_type, $row->target, $row->before_snapshot, $data );
		if ( is_wp_error( $after ) ) {
			return $after;
		}

		global $wpdb;
		$wpdb->update( // phpcs:ignore WordPress.DB.DirectDatabaseQuery
			self::table_name(),
			array(
				'after_snapshot' => $after,
				'status'         => 'applied',
			),
			array( 'id' => $change_id ),
			array( '%s', '%s' ),
			array( '%d' )
		);

		return new WP_REST_Response(
			array(
				'change_id'       => $change_id,
				'status'          => 'applied',
				'before_snapshot' => $row->before_snapshot,
				'after_snapshot'  => $after,
			),
			200
		);
	}

	/**
	 * POST /revert — restore the recorded "before" state.
	 *
	 * @param WP_REST_Request $request REST request.
	 * @return WP_REST_Response|WP_Error
	 */
	public static function revert( $request ) {
		$params    = (array) $request->get_json_params();
		$change_id = isset( $params['change_id'] ) ? (int) $params['change_id'] : 0;

		if ( $change_id <= 0 ) {
			return self::error( 'missing_change_id', 'A valid change_id is required.', 400 );
		}
		$row = self::get_row( $change_id );
		if ( ! $row ) {
			return self::error( 'not_found', 'Change not found.', 404 );
		}
		if ( 'reverted' === $row->status ) {
			return self::error( 'already_reverted', 'Change is already reverted.', 409 );
		}

		$data   = self::decode_data( $row );
		$result = self::revert_change( $row->change_type, $row->target, $row->before_snapshot, $data );
		if ( is_wp_error( $result ) ) {
			return $result;
		}

		global $wpdb;
		$wpdb->update( // phpcs:ignore WordPress.DB.DirectDatabaseQuery
			self::table_name(),
			array( 'status' => 'reverted' ),
			array( 'id' => $change_id ),
			array( '%s' ),
			array( '%d' )
		);

		return new WP_REST_Response(
			array(
				'change_id' => $change_id,
				'status'    => 'reverted',
			),
			200
		);
	}

	// --- Snapshot / apply / revert dispatchers ---------------------------

	private static function capture_before( $type, $target ) {
		switch ( $type ) {
			case 'image_compression':
				$path = self::resolve_image_path( $target );
				if ( is_wp_error( $path ) ) {
					return $path;
				}
				$bytes = file_get_contents( $path ); // phpcs:ignore WordPress.WP.AlternativeFunctions
				if ( false === $bytes ) {
					return self::error( 'read_failed', 'Could not read the image file.', 500 );
				}
				return base64_encode( $bytes ); // phpcs:ignore WordPress.PHP.DiscouragedPHPFunctions

			case 'lazy_load':
			case 'image_dimensions':
				$post = self::resolve_post( $target );
				if ( is_wp_error( $post ) ) {
					return $post;
				}
				return (string) $post->post_content;

			case 'defer_css':
				return wp_json_encode(
					array( 'deferred' => in_array( $target, self::deferred_handles(), true ) )
				);

			case 'font_display':
				$path = self::resolve_css_path( $target );
				if ( is_wp_error( $path ) ) {
					return $path;
				}
				$css = file_get_contents( $path ); // phpcs:ignore WordPress.WP.AlternativeFunctions
				if ( false === $css ) {
					return self::error( 'read_failed', 'Could not read the CSS file.', 500 );
				}
				return $css;

			// --- Technical SEO -------------------------------------------
			case 'redirect_chain':
				$source = self::redirect_key( $target );
				$map    = self::redirects();
				return wp_json_encode(
					array( 'existing' => isset( $map[ $source ] ) ? $map[ $source ] : null )
				);

			case 'missing_canonical':
			case 'incorrect_canonical':
				$post = self::resolve_post( $target );
				if ( is_wp_error( $post ) ) {
					return $post;
				}
				return (string) get_post_meta( $post->ID, self::CANONICAL_META, true );

			case 'missing_sitemap':
				return wp_json_encode(
					array(
						'was_enabled' => (bool) self::builtin_sitemaps_enabled(),
						'forced'      => (bool) get_option( self::SITEMAP_OPTION, false ),
					)
				);

			case 'broken_internal_link':
			case 'mixed_content':
				$post = self::resolve_post( $target );
				if ( is_wp_error( $post ) ) {
					return $post;
				}
				return (string) $post->post_content;

			case 'missing_alt_text':
				$att = self::resolve_attachment( $target );
				if ( is_wp_error( $att ) ) {
					return $att;
				}
				return (string) get_post_meta( $att, '_wp_attachment_image_alt', true );
		}
		return self::error( 'invalid_change_type', 'Unknown change_type.', 400 );
	}

	private static function apply_change( $type, $target, $before, $data = array() ) {
		switch ( $type ) {
			case 'image_compression':
				return self::apply_image_compression( $target );
			case 'lazy_load':
				return self::apply_content_change( $target, 'add_lazy_load' );
			case 'image_dimensions':
				return self::apply_content_change( $target, 'add_image_dimensions' );
			case 'defer_css':
				self::set_deferred_handles( array_merge( self::deferred_handles(), array( $target ) ) );
				return wp_json_encode( array( 'deferred' => true ) );
			case 'font_display':
				return self::apply_font_display( $target );

			// --- Technical SEO -------------------------------------------
			case 'redirect_chain':
				return self::apply_redirect( $target, $data );
			case 'missing_canonical':
			case 'incorrect_canonical':
				return self::apply_canonical( $target, $data );
			case 'missing_sitemap':
				return self::apply_sitemap();
			case 'broken_internal_link':
				return self::apply_link_replacement( $target, $data );
			case 'mixed_content':
				return self::apply_mixed_content( $target, $data );
			case 'missing_alt_text':
				return self::apply_alt_text( $target, $data );
		}
		return self::error( 'invalid_change_type', 'Unknown change_type.', 400 );
	}

	private static function revert_change( $type, $target, $before, $data = array() ) {
		switch ( $type ) {
			case 'image_compression':
				$path = self::resolve_image_path( $target );
				if ( is_wp_error( $path ) ) {
					return $path;
				}
				$bytes = base64_decode( (string) $before, true ); // phpcs:ignore WordPress.PHP.DiscouragedPHPFunctions
				if ( false === $bytes ) {
					return self::error( 'bad_snapshot', 'Stored image snapshot is invalid.', 500 );
				}
				file_put_contents( $path, $bytes ); // phpcs:ignore WordPress.WP.AlternativeFunctions
				$webp = preg_replace( '#\.(jpe?g|png)$#i', '.webp', $path );
				if ( $webp !== $path && is_file( $webp ) ) {
					wp_delete_file( $webp );
				}
				return true;

			case 'lazy_load':
			case 'image_dimensions':
			case 'broken_internal_link':
			case 'mixed_content':
				$post = self::resolve_post( $target );
				if ( is_wp_error( $post ) ) {
					return $post;
				}
				wp_update_post(
					array(
						'ID'           => $post->ID,
						'post_content' => (string) $before,
					)
				);
				return true;

			case 'defer_css':
				self::set_deferred_handles(
					array_diff( self::deferred_handles(), array( $target ) )
				);
				return true;

			case 'font_display':
				$path = self::resolve_css_path( $target );
				if ( is_wp_error( $path ) ) {
					return $path;
				}
				file_put_contents( $path, (string) $before ); // phpcs:ignore WordPress.WP.AlternativeFunctions
				return true;

			// --- Technical SEO -------------------------------------------
			case 'redirect_chain':
				$source   = self::redirect_key( $target );
				$existing = json_decode( (string) $before, true );
				$map      = self::redirects();
				if ( is_array( $existing ) && ! empty( $existing['existing'] ) ) {
					$map[ $source ] = (string) $existing['existing'];
				} else {
					unset( $map[ $source ] );
				}
				self::set_redirects( $map );
				return true;

			case 'missing_canonical':
			case 'incorrect_canonical':
				$post = self::resolve_post( $target );
				if ( is_wp_error( $post ) ) {
					return $post;
				}
				if ( '' === (string) $before ) {
					delete_post_meta( $post->ID, self::CANONICAL_META );
				} else {
					update_post_meta( $post->ID, self::CANONICAL_META, (string) $before );
				}
				return true;

			case 'missing_sitemap':
				$state = json_decode( (string) $before, true );
				if ( ! is_array( $state ) || empty( $state['forced'] ) ) {
					delete_option( self::SITEMAP_OPTION );
				}
				return true;

			case 'missing_alt_text':
				$att = self::resolve_attachment( $target );
				if ( is_wp_error( $att ) ) {
					return $att;
				}
				if ( '' === (string) $before ) {
					delete_post_meta( $att, '_wp_attachment_image_alt' );
				} else {
					update_post_meta( $att, '_wp_attachment_image_alt', (string) $before );
				}
				return true;
		}
		return self::error( 'invalid_change_type', 'Unknown change_type.', 400 );
	}

	// --- Per-type fix implementations ------------------------------------

	private static function apply_image_compression( $target ) {
		$path = self::resolve_image_path( $target );
		if ( is_wp_error( $path ) ) {
			return $path;
		}
		$editor = wp_get_image_editor( $path );
		if ( is_wp_error( $editor ) ) {
			return $editor;
		}
		$editor->set_quality( 60 );
		$saved = $editor->save( $path );
		if ( is_wp_error( $saved ) ) {
			return $saved;
		}
		// Best-effort WebP sibling (ignored if the host lacks WebP support).
		$webp = preg_replace( '#\.(jpe?g|png)$#i', '.webp', $path );
		if ( $webp !== $path ) {
			$editor->save( $webp, 'image/webp' );
		}
		$bytes = file_get_contents( $path ); // phpcs:ignore WordPress.WP.AlternativeFunctions
		return false === $bytes ? '' : base64_encode( $bytes ); // phpcs:ignore WordPress.PHP.DiscouragedPHPFunctions
	}

	/**
	 * Rewrite a post's content with the given transform callback and save it.
	 *
	 * @param string $target    Post id or URL.
	 * @param string $transform Static method name applied to post_content.
	 * @return string|WP_Error  New content, or an error.
	 */
	private static function apply_content_change( $target, $transform ) {
		$post = self::resolve_post( $target );
		if ( is_wp_error( $post ) ) {
			return $post;
		}
		$new = call_user_func( array( __CLASS__, $transform ), (string) $post->post_content );
		$result = wp_update_post(
			array(
				'ID'           => $post->ID,
				'post_content' => $new,
			),
			true
		);
		if ( is_wp_error( $result ) ) {
			return $result;
		}
		return $new;
	}

	private static function apply_font_display( $target ) {
		$path = self::resolve_css_path( $target );
		if ( is_wp_error( $path ) ) {
			return $path;
		}
		$css = file_get_contents( $path ); // phpcs:ignore WordPress.WP.AlternativeFunctions
		if ( false === $css ) {
			return self::error( 'read_failed', 'Could not read the CSS file.', 500 );
		}
		$new = self::add_font_display( $css );
		if ( false === file_put_contents( $path, $new ) ) { // phpcs:ignore WordPress.WP.AlternativeFunctions
			return self::error( 'write_failed', 'Could not write the CSS file.', 500 );
		}
		return $new;
	}

	private static function add_lazy_load( $html ) {
		return preg_replace_callback(
			'#<img\b[^>]*>#i',
			function ( $m ) {
				$tag = $m[0];
				if ( preg_match( '#\sloading\s*=#i', $tag ) ) {
					return $tag;
				}
				return preg_replace( '#<img\b#i', '<img loading="lazy"', $tag, 1 );
			},
			$html
		);
	}

	private static function add_image_dimensions( $html ) {
		return preg_replace_callback(
			'#<img\b[^>]*>#i',
			function ( $m ) {
				$tag = $m[0];
				if ( preg_match( '#\swidth\s*=#i', $tag ) && preg_match( '#\sheight\s*=#i', $tag ) ) {
					return $tag;
				}
				if ( ! preg_match( '#\ssrc\s*=\s*["\']([^"\']+)["\']#i', $tag, $s ) ) {
					return $tag;
				}
				$dims = self::image_dimensions_for_url( $s[1] );
				if ( ! $dims ) {
					return $tag;
				}
				$attr = sprintf( ' width="%d" height="%d"', $dims[0], $dims[1] );
				return preg_replace( '#<img\b#i', '<img' . $attr, $tag, 1 );
			},
			$html
		);
	}

	private static function image_dimensions_for_url( $src ) {
		$id = attachment_url_to_postid( $src );
		if ( $id ) {
			$meta = wp_get_attachment_metadata( $id );
			if ( ! empty( $meta['width'] ) && ! empty( $meta['height'] ) ) {
				return array( (int) $meta['width'], (int) $meta['height'] );
			}
		}
		$uploads = wp_upload_dir();
		$path    = str_replace( $uploads['baseurl'], $uploads['basedir'], $src );
		if ( is_file( $path ) ) {
			$size = @getimagesize( $path ); // phpcs:ignore WordPress.PHP.NoSilencedErrors
			if ( $size ) {
				return array( (int) $size[0], (int) $size[1] );
			}
		}
		return null;
	}

	private static function add_font_display( $css ) {
		return preg_replace_callback(
			'#@font-face\s*\{[^}]*\}#i',
			function ( $m ) {
				$block = $m[0];
				if ( preg_match( '#font-display\s*:#i', $block ) ) {
					return $block;
				}
				return preg_replace( '#\}\s*$#', "  font-display: swap;\n}", $block, 1 );
			},
			$css
		);
	}

	// --- defer_css runtime filter ----------------------------------------

	private static function deferred_handles() {
		$value = get_option( self::DEFER_OPTION, array() );
		return is_array( $value ) ? $value : array();
	}

	private static function set_deferred_handles( $handles ) {
		update_option( self::DEFER_OPTION, array_values( array_unique( $handles ) ), false );
	}

	/**
	 * Front-end filter: load deferred stylesheets asynchronously
	 * (media="print" onload swap + noscript fallback). Hooked to
	 * style_loader_tag from the bootstrap. A deferred target may be a
	 * stylesheet **handle** or its **href/URL** (the backend targets
	 * render-blocking CSS by URL, since it doesn't know WP handles).
	 *
	 * @param string $tag    The <link> tag HTML.
	 * @param string $handle The stylesheet handle.
	 * @param string $href   The stylesheet URL.
	 * @return string
	 */
	public static function filter_defer_css( $tag, $handle, $href = '' ) {
		$targets = self::deferred_handles();
		if ( ! in_array( $handle, $targets, true ) && ! in_array( $href, $targets, true ) ) {
			return $tag;
		}
		$deferred = preg_replace(
			'#\smedia=([\'"])[^\'"]*\1#i',
			' media="print" onload="this.media=\'all\'"',
			$tag,
			1
		);
		if ( $deferred === $tag ) {
			$deferred = preg_replace(
				'#<link\b#i',
				'<link media="print" onload="this.media=\'all\'"',
				$tag,
				1
			);
		}
		return $deferred . '<noscript>' . $tag . '</noscript>';
	}

	// --- Technical-SEO fix implementations -------------------------------

	/**
	 * redirect_chain — register a managed source → final-destination redirect
	 * (applied at runtime by do_managed_redirects). No file edits; fully
	 * revertible. Bypasses intermediate hops by going straight to `final_url`.
	 *
	 * @param string $target Source URL or path.
	 * @param array  $data   { final_url }.
	 * @return string|WP_Error After-state JSON.
	 */
	private static function apply_redirect( $target, $data ) {
		$final = isset( $data['final_url'] ) ? esc_url_raw( (string) $data['final_url'] ) : '';
		if ( '' === $final ) {
			return self::error( 'missing_data', 'redirect_chain requires data.final_url.', 400 );
		}
		$source        = self::redirect_key( $target );
		$map           = self::redirects();
		$map[ $source ] = $final;
		self::set_redirects( $map );
		return wp_json_encode( array( 'source' => $source, 'final_url' => $final ) );
	}

	/**
	 * missing_canonical / incorrect_canonical — store the canonical URL as
	 * post meta; output_canonical() prints it in wp_head for that post only.
	 *
	 * @param string $target Post id or URL.
	 * @param array  $data   { canonical }.
	 * @return string|WP_Error
	 */
	private static function apply_canonical( $target, $data ) {
		$post = self::resolve_post( $target );
		if ( is_wp_error( $post ) ) {
			return $post;
		}
		$canonical = isset( $data['canonical'] ) ? esc_url_raw( (string) $data['canonical'] ) : '';
		if ( '' === $canonical ) {
			// Default to the page's own permalink (self-referential canonical).
			$canonical = get_permalink( $post->ID );
		}
		update_post_meta( $post->ID, self::CANONICAL_META, $canonical );
		return wp_json_encode( array( 'canonical' => $canonical ) );
	}

	/**
	 * missing_sitemap — force-enable WordPress's built-in sitemaps (WP 5.5+,
	 * exposed at /wp-sitemap.xml) via the wp_sitemaps_enabled filter, backed
	 * by an option so it survives requests and is revertible.
	 *
	 * @return string|WP_Error
	 */
	private static function apply_sitemap() {
		update_option( self::SITEMAP_OPTION, '1', false );
		$has_builtin = function_exists( 'wp_sitemaps_get_server' );
		return wp_json_encode(
			array(
				'forced_enabled' => true,
				'builtin'        => $has_builtin,
				'sitemap_url'    => home_url( '/wp-sitemap.xml' ),
			)
		);
	}

	/**
	 * broken_internal_link — replace the broken href with the suggested
	 * replacement in the specific post's content. Auto-confidence only.
	 *
	 * @param string $target Post id or URL.
	 * @param array  $data   { broken_url, replacement_url }.
	 * @return string|WP_Error
	 */
	private static function apply_link_replacement( $target, $data ) {
		$broken      = isset( $data['broken_url'] ) ? (string) $data['broken_url'] : '';
		$replacement = isset( $data['replacement_url'] ) ? esc_url_raw( (string) $data['replacement_url'] ) : '';
		if ( '' === $broken || '' === $replacement ) {
			return self::error( 'missing_data', 'broken_internal_link requires data.broken_url and data.replacement_url.', 400 );
		}
		return self::apply_content_transform(
			$target,
			function ( $content ) use ( $broken, $replacement ) {
				return self::replace_href( $content, $broken, $replacement );
			}
		);
	}

	/**
	 * mixed_content — upgrade the given http:// resource URLs to https:// in
	 * the specific post's content (only URLs whose https version was confirmed
	 * reachable by the backend).
	 *
	 * @param string $target Post id or URL.
	 * @param array  $data   { resources: [http url, …] }.
	 * @return string|WP_Error
	 */
	private static function apply_mixed_content( $target, $data ) {
		$resources = isset( $data['resources'] ) && is_array( $data['resources'] ) ? $data['resources'] : array();
		if ( empty( $resources ) ) {
			return self::error( 'missing_data', 'mixed_content requires a non-empty data.resources list.', 400 );
		}
		return self::apply_content_transform(
			$target,
			function ( $content ) use ( $resources ) {
				foreach ( $resources as $http ) {
					$http = (string) $http;
					if ( 0 === strpos( $http, 'http://' ) ) {
						$https   = 'https://' . substr( $http, 7 );
						$content = str_replace( $http, $https, $content );
					}
				}
				return $content;
			}
		);
	}

	/**
	 * missing_alt_text — set the AI-generated alt text on the attachment's
	 * `_wp_attachment_image_alt` meta.
	 *
	 * @param string $target Attachment id or image URL.
	 * @param array  $data   { alt }.
	 * @return string|WP_Error
	 */
	private static function apply_alt_text( $target, $data ) {
		$att = self::resolve_attachment( $target );
		if ( is_wp_error( $att ) ) {
			return $att;
		}
		$alt = isset( $data['alt'] ) ? sanitize_text_field( (string) $data['alt'] ) : '';
		if ( '' === $alt ) {
			return self::error( 'missing_data', 'missing_alt_text requires data.alt.', 400 );
		}
		update_post_meta( $att, '_wp_attachment_image_alt', $alt );
		return wp_json_encode( array( 'attachment_id' => $att, 'alt' => $alt ) );
	}

	/**
	 * Rewrite a post's content with a transform closure and save it.
	 *
	 * @param string   $target    Post id or URL.
	 * @param callable $transform fn(string $content): string.
	 * @return string|WP_Error    New content, or an error.
	 */
	private static function apply_content_transform( $target, $transform ) {
		$post = self::resolve_post( $target );
		if ( is_wp_error( $post ) ) {
			return $post;
		}
		$new    = call_user_func( $transform, (string) $post->post_content );
		$result = wp_update_post( array( 'ID' => $post->ID, 'post_content' => $new ), true );
		if ( is_wp_error( $result ) ) {
			return $result;
		}
		return $new;
	}

	/**
	 * Replace a broken href value with a replacement, matching the URL inside
	 * href="…"/href='…' attributes (and the bare URL as a fallback).
	 *
	 * @param string $content     Post content.
	 * @param string $broken      Broken URL.
	 * @param string $replacement Replacement URL.
	 * @return string
	 */
	private static function replace_href( $content, $broken, $replacement ) {
		$content = str_replace(
			array( 'href="' . $broken . '"', "href='" . $broken . "'" ),
			array( 'href="' . $replacement . '"', "href='" . $replacement . "'" ),
			$content
		);
		return $content;
	}

	// --- Runtime hooks (registered by the bootstrap) ---------------------

	/**
	 * wp_head (priority 9): output the managed canonical for the current
	 * singular post, replacing WordPress's default rel_canonical for it.
	 *
	 * @return void
	 */
	public static function output_canonical() {
		if ( ! is_singular() ) {
			return;
		}
		$canonical = get_post_meta( get_queried_object_id(), self::CANONICAL_META, true );
		if ( ! $canonical ) {
			return;
		}
		remove_action( 'wp_head', 'rel_canonical' );
		echo '<link rel="canonical" href="' . esc_url( $canonical ) . '" />' . "\n";
	}

	/**
	 * template_redirect: apply managed source → final redirects (301),
	 * bypassing intermediate hops.
	 *
	 * @return void
	 */
	public static function do_managed_redirects() {
		$map = self::redirects();
		if ( empty( $map ) ) {
			return;
		}
		$request = isset( $_SERVER['REQUEST_URI'] ) ? esc_url_raw( wp_unslash( $_SERVER['REQUEST_URI'] ) ) : '';
		$key     = self::redirect_key( $request );
		if ( isset( $map[ $key ] ) && $map[ $key ] ) {
			wp_redirect( $map[ $key ], 301 ); // phpcs:ignore WordPress.Security.SafeRedirect
			exit;
		}
	}

	/**
	 * wp_sitemaps_enabled filter: force-enable the built-in sitemap when the
	 * missing_sitemap fix is active.
	 *
	 * @param bool $enabled Current state.
	 * @return bool
	 */
	public static function force_sitemap_enabled( $enabled ) {
		return get_option( self::SITEMAP_OPTION, false ) ? true : $enabled;
	}

	// --- Technical-SEO helpers -------------------------------------------

	private static function redirects() {
		$value = get_option( self::REDIRECTS_OPTION, array() );
		return is_array( $value ) ? $value : array();
	}

	private static function set_redirects( $map ) {
		update_option( self::REDIRECTS_OPTION, $map, false );
	}

	/**
	 * Normalize a URL or path to a redirect-map key: path (+ query), leading
	 * slash, trailing slash stripped (root stays '/').
	 *
	 * @param string $target URL or path.
	 * @return string
	 */
	private static function redirect_key( $target ) {
		$parts = wp_parse_url( $target );
		$path  = isset( $parts['path'] ) ? $parts['path'] : (string) $target;
		$query = isset( $parts['query'] ) && '' !== $parts['query'] ? '?' . $parts['query'] : '';
		$path  = '/' . ltrim( $path, '/' );
		$path  = rtrim( $path, '/' );
		if ( '' === $path ) {
			$path = '/';
		}
		return $path . $query;
	}

	private static function builtin_sitemaps_enabled() {
		if ( ! function_exists( 'wp_sitemaps_get_server' ) ) {
			return false;
		}
		return (bool) apply_filters( 'wp_sitemaps_enabled', true );
	}

	/**
	 * Resolve a target (attachment id or image URL) to an attachment post id.
	 *
	 * @param string $target Attachment id or URL.
	 * @return int|WP_Error
	 */
	private static function resolve_attachment( $target ) {
		$id = 0;
		if ( ctype_digit( (string) $target ) ) {
			$id = (int) $target;
		} elseif ( preg_match( '#^https?://#i', $target ) ) {
			$id = attachment_url_to_postid( $target );
		}
		if ( ! $id || 'attachment' !== get_post_type( $id ) ) {
			return self::error( 'not_found', 'Could not resolve an attachment for the target.', 400 );
		}
		return $id;
	}

	// --- Resolution + containment helpers --------------------------------

	private static function resolve_image_path( $target ) {
		$uploads = wp_upload_dir();
		$basedir = $uploads['basedir'];
		$baseurl = $uploads['baseurl'];

		if ( ctype_digit( (string) $target ) ) {
			$path = get_attached_file( (int) $target );
		} elseif ( preg_match( '#^https?://#i', $target ) ) {
			$id   = attachment_url_to_postid( $target );
			$path = $id ? get_attached_file( $id ) : str_replace( $baseurl, $basedir, $target );
		} else {
			$path = $target;
		}
		if ( ! $path ) {
			return self::error( 'not_found', 'Could not resolve the image target.', 400 );
		}

		$real     = realpath( $path );
		$realbase = realpath( $basedir );
		if ( ! $real || ! $realbase || 0 !== strpos( $real, $realbase ) ) {
			return self::error( 'forbidden', 'Image target is outside the uploads directory.', 400 );
		}
		if ( ! is_file( $real ) ) {
			return self::error( 'not_found', 'Image file does not exist.', 404 );
		}
		return $real;
	}

	private static function resolve_css_path( $target ) {
		$theme = realpath( get_stylesheet_directory() );
		if ( preg_match( '#^([A-Za-z]:[\\\\/]|/)#', $target ) ) {
			$candidate = $target;
		} else {
			$candidate = trailingslashit( get_stylesheet_directory() ) . ltrim( $target, '/\\' );
		}
		$real = realpath( $candidate );
		if ( ! $real || ! $theme || 0 !== strpos( $real, $theme ) || ! is_file( $real ) ) {
			return self::error( 'forbidden', 'CSS target must be a file inside the active theme.', 400 );
		}
		if ( ! is_writable( $real ) ) {
			return self::error( 'readonly', 'CSS file is not writable on this host.', 400 );
		}
		return $real;
	}

	private static function resolve_post( $target ) {
		$post_id = 0;
		if ( ctype_digit( (string) $target ) ) {
			$post_id = (int) $target;
		} elseif ( preg_match( '#^https?://#i', $target ) ) {
			$url     = strtok( $target, '#' ); // drop any fragment
			$post_id = url_to_postid( $url );

			// http<->https mismatch (common behind proxies/CDNs) makes
			// url_to_postid() miss — retry with the opposite scheme.
			if ( ! $post_id ) {
				$alt = ( 0 === strpos( $url, 'https://' ) )
					? 'http://' . substr( $url, 8 )
					: 'https://' . substr( $url, 7 );
				$post_id = url_to_postid( $alt );
			}

			// url_to_postid() never resolves the site front page. If the
			// target is the home URL and a static page is set as the front
			// page, use that page (compare host+path, ignoring scheme).
			if ( ! $post_id ) {
				$strip = '#^https?://#i';
				$home  = untrailingslashit( preg_replace( $strip, '', home_url() ) );
				$t     = untrailingslashit( preg_replace( $strip, '', strtok( $url, '?' ) ) );
				if ( $t === $home && 'page' === get_option( 'show_on_front' ) ) {
					$post_id = (int) get_option( 'page_on_front' );
				}
			}
		}
		if ( ! $post_id ) {
			return self::error( 'not_found', 'Could not resolve a post/page for the target.', 400 );
		}
		$post = get_post( $post_id );
		if ( ! $post ) {
			return self::error( 'not_found', 'Post not found.', 404 );
		}
		return $post;
	}

	private static function error( $code, $message, $status ) {
		return new WP_Error( 'rankpilot_' . $code, $message, array( 'status' => $status ) );
	}
}
