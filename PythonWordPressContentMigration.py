import requests
import json
from datetime import datetime
import time
from typing import List, Dict, Any
import xml.etree.ElementTree as ET
import sys
import getpass
from urllib.parse import urlparse
import os
from rich.console import Console
from rich.progress import Progress, SpinnerColumn, TextColumn, BarColumn, TaskProgressColumn
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

class WordPressMigrator:
    def __init__(self, source_url: str, destination_url: str, username: str, app_password: str):
        """
        Initialize the WordPress migrator with source and destination credentials.
        
        Args:
            source_url: URL of the source WordPress site
            destination_url: URL of the destination WordPress site
            username: WordPress username for the destination site
            app_password: Application password for WordPress authentication
        """
        self.source_url = source_url.rstrip('/')
        self.destination_url = destination_url.rstrip('/')
        self.auth = (username, app_password)
        self.console = Console()
        
        # Configure session with retries
        self.session = requests.Session()
        retries = Retry(
            total=5,
            backoff_factor=0.5,
            status_forcelist=[500, 502, 503, 504]
        )
        self.session.mount('http://', HTTPAdapter(max_retries=retries))
        self.session.mount('https://', HTTPAdapter(max_retries=retries))
    def get_post_by_url(self, url: str) -> Dict[Any, Any]:
        """Fetch post data using its URL"""
        try:
            # Try to get post ID from URL
            post_id = None
            if '/?p=' in url:
                post_id = url.split('/?p=')[-1]
            else:
                # Try to get post by slug
                slug = url.split('/')[-2] if url.endswith('/') else url.split('/')[-1]
                endpoint = f"{self.source_url}/wp-json/wp/v2/posts"
                params = {'slug': slug}
                response = self.session.get(endpoint, params=params)
                if response.status_code == 200:
                    posts = response.json()
                    if posts:
                        post_id = posts[0]['id']

            if post_id:
                endpoint = f"{self.source_url}/wp-json/wp/v2/posts/{post_id}"
                params = {'_embed': 1}  # Include featured images and other embedded content
                response = self.session.get(endpoint, params=params)
                response.raise_for_status()
                return response.json()
            return None

        except Exception as e:
            self.console.print(f"[yellow]Warning: Could not fetch post from {url}: {str(e)}[/yellow]")
            return None
    def get_all_sitemaps(self) -> List[str]:
        """Get all available sitemap URLs"""
        sitemap_urls = []
        potential_sitemaps = [
            '/sitemap.xml',
            '/wp-sitemap.xml',
            '/post-sitemap.xml',
            '/wp-sitemap-posts-post-1.xml'
        ]
        
        for sitemap in potential_sitemaps:
            try:
                response = self.session.get(f"{self.source_url}{sitemap}")
                if response.status_code == 200:
                    sitemap_urls.append(f"{self.source_url}{sitemap}")
            except:
                continue
                
        return sitemap_urls
    def create_post(self, post_data: Dict[Any, Any]) -> Dict[Any, Any]:
        """Create new post on destination site"""
        try:
            endpoint = f"{self.destination_url}/wp-json/wp/v2/posts"
            
            # Prepare post data
            new_post = {
                'title': post_data['title']['rendered'],
                'content': post_data['content']['rendered'],
                'status': 'publish',
                'slug': post_data['slug'],
                'excerpt': post_data.get('excerpt', {}).get('rendered', ''),
                'categories': post_data.get('categories', []),
                'tags': post_data.get('tags', []),
                'meta': post_data.get('meta', {}),
                'date': post_data.get('date', None),
                'modified': post_data.get('modified', None)
            }
            
            # Handle author mapping (optional)
            # new_post['author'] = self.map_author(post_data['author'])
            
            headers = {
                'Content-Type': 'application/json'
            }
            
            response = self.session.post(
                endpoint,
                auth=self.auth,
                json=new_post,
                headers=headers
            )
            response.raise_for_status()
            return response.json()
            
        except Exception as e:
            self.console.print(f"[red]Error creating post: {str(e)}[/red]")
            raise
    def get_media(self, media_url: str) -> bytes:
        """Download media file from source site"""
        try:
            response = self.session.get(media_url)
            response.raise_for_status()
            return response.content
        except Exception as e:
            self.console.print(f"[yellow]Warning: Could not download media from {media_url}: {str(e)}[/yellow]")
            return None

    def upload_media(self, media_content: bytes, filename: str) -> Dict[str, Any]:
        """Upload media to destination site"""
        try:
            if not media_content:
                raise ValueError("No media content provided")
                
            endpoint = f"{self.destination_url}/wp-json/wp/v2/media"
            
            # Detect content type based on file extension
            content_type = self.get_content_type(filename)
            
            headers = {
                'Content-Type': content_type,
                'Content-Disposition': f'attachment; filename={filename}'
            }
            
            response = self.session.post(
                endpoint,
                auth=self.auth,
                data=media_content,
                headers=headers
            )
            response.raise_for_status()
            return response.json()
            
        except Exception as e:
            self.console.print(f"[red]Error uploading media: {str(e)}[/red]")
            raise

    def get_content_type(self, filename: str) -> str:
        """Determine content type based on file extension"""
        ext = filename.lower().split('.')[-1]
        content_types = {
            'jpg': 'image/jpeg',
            'jpeg': 'image/jpeg',
            'png': 'image/png',
            'gif': 'image/gif',
            'webp': 'image/webp',
            'pdf': 'application/pdf'
        }
        return content_types.get(ext, 'application/octet-stream')

    def set_featured_image(self, post_id: int, media_id: int) -> Dict[str, Any]:
        """Set featured image for a post"""
        try:
            endpoint = f"{self.destination_url}/wp-json/wp/v2/posts/{post_id}"
            data = {
                'featured_media': media_id
            }
            
            response = self.session.post(
                endpoint,
                auth=self.auth,
                json=data
            )
            response.raise_for_status()
            return response.json()
            
        except Exception as e:
            self.console.print(f"[yellow]Warning: Could not set featured image: {str(e)}[/yellow]")
            return None

    def handle_featured_image(self, post: Dict[Any, Any], new_post_id: int, progress: Progress) -> None:
        """Handle featured image migration with better error handling"""
        try:
            if '_embedded' in post and 'wp:featuredmedia' in post['_embedded']:
                media_info = post['_embedded']['wp:featuredmedia'][0]
                media_url = media_info.get('source_url')
                
                if not media_url:
                    return
                    
                filename = media_url.split('/')[-1]
                
                progress.log(f"Downloading media: {filename}")
                media_content = self.get_media(media_url)
                
                if media_content:
                    progress.log(f"Uploading media: {filename}")
                    uploaded_media = self.upload_media(media_content, filename)
                    
                    if uploaded_media:
                        self.set_featured_image(new_post_id, uploaded_media['id'])
                        
        except Exception as e:
            progress.log(f"[yellow]Warning: Could not migrate featured image: {str(e)}[/yellow]")
    def get_sitemap_urls(self) -> List[str]:
        """Extract all post URLs from all available sitemaps"""
        urls = set()  # Use set to avoid duplicates
        
        sitemap_urls = self.get_all_sitemaps()
        if not sitemap_urls:
            self.console.print("[yellow]No sitemaps found. Will use API fallback.[/yellow]")
            return list(urls)
            
        for sitemap_url in sitemap_urls:
            try:
                response = self.session.get(sitemap_url)
                response.raise_for_status()
                root = ET.fromstring(response.content)
                
                # Handle both regular sitemaps and sitemap index files
                if 'sitemapindex' in root.tag:
                    # Process each sitemap in the index
                    for sitemap in root.findall('.//{http://www.sitemaps.org/schemas/sitemap/0.9}loc'):
                        if 'post' in sitemap.text.lower():
                            sub_response = self.session.get(sitemap.text)
                            sub_root = ET.fromstring(sub_response.content)
                            urls.update([
                                url.text for url in 
                                sub_root.findall('.//{http://www.sitemaps.org/schemas/sitemap/0.9}loc')
                            ])
                else:
                    # Process regular sitemap
                    urls.update([
                        url.text for url in 
                        root.findall('.//{http://www.sitemaps.org/schemas/sitemap/0.9}loc')
                    ])
                    
            except Exception as e:
                self.console.print(f"[yellow]Warning: Could not process sitemap {sitemap_url}: {str(e)}[/yellow]")
                continue
        
        # Filter only post URLs and remove duplicates
        post_urls = {url for url in urls if '/posts/' in url or '/?p=' in url or '/blog/' in url}
        return list(post_urls)

    def get_all_posts_via_api(self) -> List[Dict[Any, Any]]:
        """Fetch all posts using WordPress API with pagination"""
        all_posts = []
        page = 1
        per_page = 100  # Maximum allowed by WordPress
        
        while True:
            try:
                endpoint = f"{self.source_url}/wp-json/wp/v2/posts"
                params = {
                    'page': page,
                    'per_page': per_page,
                    'status': 'publish',
                    '_embed': 1
                }
                
                response = self.session.get(endpoint, params=params)
                
                # Check if we've reached the end of posts
                if response.status_code == 400:  # WordPress returns 400 when page exceeds max
                    break
                    
                response.raise_for_status()
                posts = response.json()
                
                if not posts:  # Empty page
                    break
                    
                all_posts.extend(posts)
                page += 1
                time.sleep(1)  # Rate limiting
                
            except Exception as e:
                self.console.print(f"[yellow]Warning: Error fetching page {page}: {str(e)}[/yellow]")
                break
                
        return all_posts

    def migrate_content(self) -> None:
        """Main migration function to copy all posts from source to destination."""
        with Progress(
            SpinnerColumn(),
            TextColumn("[progress.description]{task.description}"),
            BarColumn(),
            TaskProgressColumn(),
            console=self.console
        ) as progress:
            # First try sitemap approach
            task = progress.add_task("[cyan]Reading sitemaps...", total=None)
            post_urls = self.get_sitemap_urls()
            progress.update(task, completed=True)
            
            if post_urls:
                self.console.print(f"[green]Found {len(post_urls)} posts in sitemaps[/green]")
                migration_task = progress.add_task(
                    "[cyan]Migrating posts from sitemap...", 
                    total=len(post_urls)
                )
                
                for url in post_urls:
                    try:
                        progress.log(f"Processing: {url}")
                        post = self.get_post_by_url(url)
                        
                        if not post:
                            progress.log(f"[yellow]Skipping {url} - could not fetch content[/yellow]")
                            continue
                            
                        new_post = self.create_post(post)
                        self.handle_featured_image(post, new_post['id'], progress)
                        
                        progress.update(migration_task, advance=1)
                        time.sleep(1)  # Rate limiting
                        
                    except Exception as e:
                        progress.log(f"[red]Error migrating {url}: {str(e)}[/red]")
                        continue
            else:
                # Fallback to API approach
                self.console.print("[yellow]Falling back to API method...[/yellow]")
                task = progress.add_task("[cyan]Fetching posts via API...", total=None)
                posts = self.get_all_posts_via_api()
                progress.update(task, completed=True)
                
                if not posts:
                    self.console.print("[red]No posts found to migrate![/red]")
                    return
                    
                self.console.print(f"[green]Found {len(posts)} posts via API[/green]")
                migration_task = progress.add_task(
                    "[cyan]Migrating posts from API...", 
                    total=len(posts)
                )
                
                for post in posts:
                    try:
                        progress.log(f"Migrating: {post['title']['rendered']}")
                        new_post = self.create_post(post)
                        self.handle_featured_image(post, new_post['id'], progress)
                        
                        progress.update(migration_task, advance=1)
                        time.sleep(1)  # Rate limiting
                        
                    except Exception as e:
                        progress.log(f"[red]Error migrating post {post.get('title', {}).get('rendered', 'Unknown')}: {str(e)}[/red]")
                        continue

    def handle_featured_image(self, post: Dict[Any, Any], new_post_id: int, progress: Progress) -> None:
        """Handle featured image migration with better error handling"""
        try:
            if '_embedded' in post and 'wp:featuredmedia' in post['_embedded']:
                media_url = post['_embedded']['wp:featuredmedia'][0]['source_url']
                filename = media_url.split('/')[-1]
                
                progress.log(f"Downloading media: {filename}")
                media_content = self.get_media(media_url)
                
                progress.log(f"Uploading media: {filename}")
                uploaded_media = self.upload_media(media_content, filename)
                
                self.set_featured_image(new_post_id, uploaded_media['id'])
        except Exception as e:
            progress.log(f"[yellow]Warning: Could not migrate featured image: {str(e)}[/yellow]")
def get_wordpress_app_password():
    """Guide user through getting a WordPress application password"""
    console = Console()
    console.print("\n[bold cyan]How to generate a WordPress Application Password:[/bold cyan]")
    console.print("""
1. Log in to your WordPress admin panel at yoursite.com/wp-admin
2. Navigate to Users → Profile (or Users → Your Profile)
3. Scroll down to the 'Application Passwords' section
   - If you don't see this section, ask your admin to enable it or check if your hosting provider supports it
   - You may need to enable two-factor authentication first on some installations

4. Under 'Add New Application Password':
   - Enter a name for this application (e.g., 'Content Migration Tool')
   - Click 'Add New'

5. WordPress will generate a password that looks like: xxxx xxxx xxxx xxxx
   - Copy this password immediately
   - You won't be able to see it again after closing the window
   
6. Important Settings to Check:
   - Ensure the REST API is enabled in WordPress
   - Verify your user has administrator privileges
   - Check that your hosting provider allows REST API access
   
[yellow]Common Issues:[/yellow]
• If you get 401 errors: Verify your username and application password
• If you get 403 errors: Check your user permissions and REST API settings
• If the Application Passwords section is missing: 
  - Add this to wp-config.php: define('WP_REST_APPLICATION_PASSWORD_ENABLED', true);
  - Or update to WordPress 5.6 or later
    """)
    
    # Verify basic requirements
    console.print("\n[bold green]Requirements Checklist:[/bold green]")
    console.print("""
□ WordPress 5.6 or later installed
□ Administrator account access
□ REST API enabled
□ Application Passwords enabled
""")
    
    input("\nPress Enter when you have your application password ready...")
def main():
    """Interactive main function"""
    console = Console()
    
    # Install required packages if they're not present
    try:
        import rich
    except ImportError:
        console.print("[yellow]Installing required packages...[/yellow]")
        os.system('pip install rich')
        import rich
    
    console.print("[bold green]WordPress Content Migration Tool[/bold green]")
    console.print("This tool will migrate ALL content between WordPress sites.\n")
    
    # Get source site URL
    source_site = input("Enter source WordPress site URL: ").strip()
    destination_site = input("Enter destination WordPress site URL: ").strip()
    username = input("Enter your WordPress username: ").strip()
    
    # Show instructions for app password
    get_wordpress_app_password()
    app_password = getpass.getpass("Enter your WordPress application password: ").strip()
    
    # Initialize migrator and start migration
    try:
        migrator = WordPressMigrator(
            source_url=source_site,
            destination_url=destination_site,
            username=username,
            app_password=app_password
        )
        
        console.print("\n[bold cyan]Starting migration...[/bold cyan]")
        console.print("This will migrate ALL posts from the source site. Press Ctrl+C to cancel.\n")
        
        migrator.migrate_content()
        console.print("[bold green]Migration completed successfully![/bold green]")
        
    except KeyboardInterrupt:
        console.print("\n[yellow]Migration cancelled by user.[/yellow]")
        sys.exit(0)
    except Exception as e:
        console.print(f"[bold red]Error during migration: {str(e)}[/bold red]")
        sys.exit(1)

if __name__ == "__main__":
    main()