# WordPress Content Migration Tool

A robust Python tool for migrating content between WordPress sites using the WordPress REST API. This tool handles post content, featured images, and metadata while providing a user-friendly interface with progress tracking.

## Features

- Complete post content migration including:
  - Post titles and content
  - Featured images
  - Categories and tags
  - Post metadata
  - Publication dates
- Smart content discovery using both sitemap and API approaches
- Progress tracking with rich console interface
- Robust error handling and retry mechanisms
- Rate limiting to prevent server overload
- Support for WordPress application passwords
- Detailed logging of migration progress

## Prerequisites

- Python 3.6 or higher
- WordPress 5.6 or higher on both source and destination sites
- Administrator access to both WordPress installations
- REST API enabled on both sites
- Application Passwords feature enabled

## Installation

1. Clone the repository:
```bash
git clone https://github.com/jasonpoonia/PythonWordPressContentMigration.git
cd PythonWordPressContentMigration
```

2. Install required dependencies:
```bash
pip install requests rich
```

## Configuration Requirements

### WordPress Settings

1. Ensure REST API is enabled on both WordPress sites
2. Enable Application Passwords feature (WordPress 5.6+)
3. Verify administrator privileges on the destination site
4. Check that your hosting provider allows REST API access

### Application Password Generation

1. Log in to your WordPress admin panel (destination site)
2. Navigate to Users → Profile
3. Scroll to 'Application Passwords' section
4. Enter a name for the application (e.g., "Content Migration Tool")
5. Click 'Add New' and copy the generated password

## Usage

Run the script:
```bash
python PythonWordPressContentMigration.py
```

Follow the interactive prompts:
1. Enter source WordPress site URL
2. Enter destination WordPress site URL
3. Enter your WordPress username
4. Enter your application password when prompted

The tool will:
1. Attempt to discover content via sitemaps
2. Fall back to API-based content discovery if needed
3. Migrate posts with progress tracking
4. Handle media uploads automatically
5. Provide detailed progress and error logging

## Error Handling

The tool includes comprehensive error handling for common issues:
- Network connectivity problems
- Authentication failures
- API rate limits
- Media upload issues
- Missing permissions

## Troubleshooting

### Common Issues

1. **401 Unauthorized Errors**
   - Verify username and application password
   - Ensure user has administrator privileges

2. **403 Forbidden Errors**
   - Check REST API settings
   - Verify user permissions
   - Confirm hosting provider allows REST API access

3. **Missing Application Passwords Section**
   - Add to wp-config.php:
     ```php
     define('WP_REST_APPLICATION_PASSWORD_ENABLED', true);
     ```
   - Update WordPress to version 5.6 or later

4. **Slow Migration**
   - Tool includes built-in rate limiting
   - Adjust sleep intervals in code if needed
   - Check network connectivity

## Security Considerations

- Store application passwords securely
- Use HTTPS for both source and destination sites
- Revoke application passwords after migration
- Back up destination site before migration
- Consider server load during migration

## Contributing

Contributions are welcome! Please feel free to submit a Pull Request.

## License

This project is licensed under the MIT License - see the LICENSE file for details.

## Acknowledgments

- Built using the WordPress REST API
- Uses the `rich` library for console interface
- Inspired by the need for reliable WordPress content migration

## Support

For issues and feature requests, please create an issue in the GitHub repository.
