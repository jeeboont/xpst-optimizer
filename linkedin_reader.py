import streamlit as st
import requests
from bs4 import BeautifulSoup
import time
import random
from urllib.parse import urlparse

# Configure Streamlit page
st.set_page_config(
    page_title="LinkedIn Post Reader",
    page_icon="🔗",
    layout="wide"
)

def get_headers():
    """Generate realistic browser headers to avoid detection"""
    user_agents = [
        'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36',
        'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36',
        'Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
    ]
    
    return {
        'User-Agent': random.choice(user_agents),
        'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8',
        'Accept-Language': 'en-US,en;q=0.5',
        'Accept-Encoding': 'gzip, deflate',
        'Connection': 'keep-alive',
        'Upgrade-Insecure-Requests': '1',
    }

def extract_linkedin_post(url):
    """Attempt to extract LinkedIn post content"""
    try:
        # Add random delay to avoid rate limiting
        time.sleep(random.uniform(1, 3))
        
        session = requests.Session()
        headers = get_headers()
        
        response = session.get(url, headers=headers, timeout=10)
        response.raise_for_status()
        
        soup = BeautifulSoup(response.content, 'html.parser')
        
        # Try different selectors that LinkedIn might use
        post_content = None
        author_name = None
        
        # Common selectors for LinkedIn post content
        content_selectors = [
            '.feed-shared-text',
            '.feed-shared-update-v2__description-wrapper',
            '[data-test-id="main-feed-activity-card"]',
            '.share-update-card__update-text',
            '.attributed-text-segment-list__content'
        ]
        
        for selector in content_selectors:
            element = soup.select_one(selector)
            if element:
                post_content = element.get_text(strip=True)
                break
        
        # Try to get author name
        author_selectors = [
            '.feed-shared-actor__name',
            '.update-components-actor__name',
            '.feed-shared-actor__title'
        ]
        
        for selector in author_selectors:
            element = soup.select_one(selector)
            if element:
                author_name = element.get_text(strip=True)
                break
        
        return {
            'success': True,
            'content': post_content or "Could not extract post content",
            'author': author_name or "Unknown author",
            'url': url
        }
        
    except requests.RequestException as e:
        return {
            'success': False,
            'error': f"Network error: {str(e)}",
            'content': None,
            'author': None,
            'url': url
        }
    except Exception as e:
        return {
            'success': False,
            'error': f"Parsing error: {str(e)}",
            'content': None,
            'author': None,
            'url': url
        }

def main():
    st.title("🔗 LinkedIn Post Reader")
    st.markdown("---")
    
    # Warning about limitations
    st.warning("""
    ⚠️ **Important Limitations:**
    - LinkedIn actively blocks automated scraping
    - This may not work consistently due to anti-bot measures
    - LinkedIn requires login for most content
    - Consider using LinkedIn's official API for production use
    """)
    
    # URL input
    linkedin_url = st.text_input(
        "Enter LinkedIn Post URL:",
        placeholder="https://www.linkedin.com/posts/...",
        help="Paste the full LinkedIn post URL here"
    )
    
    if st.button("Extract Post Content", type="primary"):
        if linkedin_url:
            if "linkedin.com" not in linkedin_url:
                st.error("Please enter a valid LinkedIn URL")
                return
            
            with st.spinner("Attempting to extract post content..."):
                result = extract_linkedin_post(linkedin_url)
                
            if result['success']:
                st.success("✅ Content extracted successfully!")
                
                col1, col2 = st.columns([1, 3])
                
                with col1:
                    st.subheader("Post Details")
                    if result['author']:
                        st.write(f"**Author:** {result['author']}")
                    st.write(f"**URL:** [Link]({result['url']})")
                
                with col2:
                    st.subheader("Post Content")
                    if result['content']:
                        st.write(result['content'])
                    else:
                        st.info("No content could be extracted from this post")
                
                # Download option
                if result['content']:
                    st.download_button(
                        label="Download as Text File",
                        data=f"Author: {result['author']}\nURL: {result['url']}\n\nContent:\n{result['content']}",
                        file_name="linkedin_post.txt",
                        mime="text/plain"
                    )
                        
            else:
                st.error(f"❌ Failed to extract content: {result['error']}")
                st.info("""
                **Possible solutions:**
                1. Try copying and pasting the post content directly
                2. The post might require login to view
                3. LinkedIn may be blocking automated access
                4. The post URL might be invalid or expired
                """)
        else:
            st.warning("Please enter a LinkedIn URL")
    
    # Alternative method section
    st.markdown("---")
    st.subheader("📋 Alternative: Manual Content Input")
    st.info("If the automatic extraction doesn't work, you can paste the content directly:")
    
    manual_content = st.text_area(
        "Paste LinkedIn Post Content:",
        placeholder="Copy and paste the LinkedIn post content here...",
        height=200
    )
    
    if manual_content:
        st.subheader("Processed Content")
        st.write(manual_content)
        
        st.download_button(
            label="Download Manual Content",
            data=manual_content,
            file_name="linkedin_post_manual.txt",
            mime="text/plain"
        )

if __name__ == "__main__":
    main()
