from playwright.sync_api import sync_playwright
import requests
import re
import socket
import dns.resolver
from imager import es_imager
from urllib.parse import urlsplit


def handle_seo(url):
    result_dict = {}
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        context = browser.new_context()
        page = context.new_page()
        response = page.goto(url, wait_until="load")

        result_dict["title"] = page.title()
        headings = page.query_selector_all("h1")
        heading_texts = [element.inner_text() for element in headings]
        result_dict["h1s"] = heading_texts

        h2_elements = page.query_selector_all("h2")
        h2_texts = [element.inner_text() for element in h2_elements]
        result_dict["h2s"] = h2_texts

        try:
            meta_description = page.eval_on_selector(
                'meta[name="description"]', "el => el.content"
            )
            result_dict["meta_description"] = meta_description
        except Exception as e:
            result_dict["meta_description"] = None

        result_dict["og_title"] = (
            page.query_selector('meta[property="og:title"]') or None
        )
        result_dict["og_description"] = (
            page.query_selector('meta[property="og:description"]') or None
        )
        result_dict["twitter_title"] = (
            page.query_selector('meta[name="twitter:title"]') or None
        )
        result_dict["twitter_description"] = (
            page.query_selector('meta[name="twitter:description"]') or None
        )

        sitemap_url = f"{url}/sitemap.xml"
        sitemap_exists = requests.head(sitemap_url).status_code == 200
        result_dict["has_sitemap"] = sitemap_exists

        # Check for robots.txt
        robots_url = f"{url}/robots.txt"
        robots_exists = requests.head(robots_url).status_code == 200
        result_dict["has_robots"] = robots_exists

        response = requests.get(robots_url)
        robots_content = response.text
        disallow_directive = [
            line.strip()
            for line in robots_content.split("\n")
            if line.lower().startswith("disallow:")
        ]
        result_dict["disallow_directives"] = disallow_directive

        # Check for ads.txt
        ads_url = f"{url}/ads.txt"
        ads_exists = requests.head(ads_url).status_code == 200
        result_dict["has_ads"] = ads_exists

        favicon_element = (
            page.query_selector('link[rel="icon"], link[rel="shortcut icon"]') or None
        )
        result_dict["favicon"] = (
            url + favicon_element.get_attribute("href") if favicon_element else None
        )
        # check deprecated html tags
        deprected_tags = [
            "font",
            "center",
            "strike",
            "u",
            "applet",
            "basefont",
            "big",
            "frame",
            "frameset",
            "noframes",
            "marquee",
            "blink",
            "acronym",
            "dir",
            "tt",
        ]
        page_source = page.content()
        found_deprecated_tags = [
            tag for tag in deprected_tags if f"<{tag}" in page_source
        ]
        result_dict["deprecated_tags"] = found_deprecated_tags
        inline_styles = page.evaluate("document.querySelectorAll('[style]').length > 0")
        result_dict["inline_styles"] = inline_styles
        images = page.query_selector_all("img")
        image_info = es_imager.check_image_info(images)
        result_dict["images"] = image_info

        all_links = page.query_selector_all("a")
        non_seo_friendly = {"friend": True, "link_details": []}
        for link in all_links:
            link_details = {
                "href": link.get_attribute("href"),
                "text": link.inner_text().strip(),
                "rel": link.get_attribute("rel"),
                "target": link.get_attribute("target"),
                "title": link.get_attribute("title"),
            }
            txt = link.inner_text().strip()
            # link has descriptive text
            if not link_details["text"]:
                non_seo_friendly["friend"] = False
            if txt.lower() in [
                "click here",
                "more",
                "read more",
            ]:
                non_seo_friendly["friend"] = False
            if len(txt) > 60:
                non_seo_friendly["friend"] = False

            non_seo_friendly["link_details"].append(link_details)
        result_dict["non_seofriendly_links"] = non_seo_friendly
        if any(
            script in page_source
            for script in [
                "www.googletagmanager.com/gtag/js",
                "analytics.js",
                "gtag('js', new Date())",
            ]
        ):
            result_dict["has_analytics"] = True
        else:
            result_dict["has_analytics"] = None
        charset = response.headers["content-type"]
        result_dict["charset"] = charset
        # check socia media integration
        social_media = page.query_selector_all(
            'a[href*="facebook.com"], a[href*="twitter.com"], a[href*="instagram.com"], a[href*="linkedin.com"]'
        )
        if social_media:
            socials = []
            for item in social_media:
                href = item.get_attribute("href")
                socials.append(href)
            result_dict["socials"] = socials
        else:
            result_dict["socials"] = None
        # count dom nodes
        dom_nodes = page.evaluate('() => document.querySelectorAll("*").length')
        result_dict["domsize"] = f"{dom_nodes} of 1500"
        # check load time
        timing = page.evaluate("window.performance.timing")
        loading_time = (timing["loadEventEnd"] - timing["navigationStart"]) / 1000
        loc = get_geolocation()
        result_dict[
            "load_time"
        ] = f"site loads in {loading_time} from {loc}. Recommended is under 5 seconds"
        # check flask multimedia content
        object_elements = page.query_selector_all(
            'object[type="application/x-shockwave-flash"]'
        )
        embed_elements = page.query_selector_all(
            'embed[type="application/x-shockwave-flash"]'
        )
        flash_elements = object_elements + embed_elements
        if not flash_elements:
            result_dict["has_flash_multimedia"] = None
        else:
            all_flash = []
            for flash_item in flash_elements:
                all_flash.append(flash_item.outer_html())
            result_dict["has_flash_multimedia"] = all_flash
        # check render blocking resources
        render_blocking_resources = page.evaluate(
            """() => {
            const resources = performance.getEntriesByType('resource');
            return resources.filter(resource => resource.requestStart < resource.startTime);
        }"""
        )
        if render_blocking_resources:
            r_blocks = []
            for resource in render_blocking_resources:
                r_blocks.append(resource["name"])
            result_dict["has_render_blocking"] = r_blocks
        else:
            result_dict["has_render_blocking"] = None
        # has nested tables
        nested_tables = page.evaluate(
            """() => {
            const tables = document.querySelectorAll('table');
            for (const table of tables) {
                if (table.querySelector('table')) {
                    return true;  // Found nested table
                }
            }
            return false;  // No nested tables found
        }"""
        )
        result_dict["has_nested_tables"] = True if nested_tables else None
        # check doctype
        doctype_declaration = page_source.startswith("<!DOCTYPE")
        result_dict["has_doctype_declaration"] = True if doctype_declaration else None
        has_redirects = has_redirect(url)
        result_dict["has_redirect"] = has_redirects
        # canonization check
        has_canonized = resolve_to_same_url(url)
        result_dict["has_canonized"] = has_canonized
        # check plaintext email
        email_addrs = re.findall(
            r"\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b", page_source
        )
        if email_addrs:
            result_dict["plaintext_emails"] = email_addrs
        else:
            result_dict["plaintext_emails"] = None
        viewport_meta = page.evaluate(
            """() => {
            const viewportMeta = document.querySelector('meta[name="viewport"]');
            return viewportMeta ? viewportMeta.getAttribute('content') : null;
        }"""
        )
        if viewport_meta:
            result_dict[
                "viewport_content"
            ] = f"The webpage at {url} is using a viewport meta tag with content: {viewport_meta}"
        else:
            result_dict[
                "viewport_content"
            ] = f"The webpage at {url} does not appear to be using a viewport meta tag."
        # take mobile snapshot
        # check noindex tag
        if 'name="robots" content="noindex"' in page_source:
            result_dict["noindex_tag"] = True
        else:
            result_dict["noindex_tag"] = None
        # canonical tag
        if 'rel="canonical"' in page_source:
            canonical_url = page.query_selector('link[rel="canonical"]').get_attribute(
                "href"
            )
            result_dict["canonical_tag"] = canonical_url
        else:
            result_dict["canonical_tag"] = None
        # check no-follow
        if 'name="robots" content="nofollow"' in page_source:
            result_dict["nofollow_tag"] = True
        else:
            result_dict["nofollow_tag"] = None
        # uses meta refresh
        if 'http-quiv="refresh"' in page_source:
            result_dict["meta_refresh"] = True
        else:
            result_dict["meta_refresh"] = None
        # check spf and domain props
        dns_props = check_spf_record(url)
        print(dns_props)
        result_dict["dns_spf_record"] = dns_props

        # check media query
        stylesheets = page.evaluate(
            """() => {
            return Array.from(document.styleSheets).map(styleSheet => styleSheet.href);
        }"""
        )
        media_queries_found = False
        media_queries_found = page.evaluate(
            """() => {
            // Get the computed styles of the body element
            const styles = window.getComputedStyle(document.body);

            // Check if any media queries are present
            return styles.media !== 'none';
        }"""
        )
        if media_queries_found:
            result_dict["media_query_responsive"] = True
        else:
            for stylesheet in stylesheets:
                css_content = page.evaluate(
                    f"""(href) => {{
                    const stylesheet = document.styleSheets.find(sheet => sheet.href === href);
                    return stylesheet ? Array.from(stylesheet.cssRules).map(rule => rule.cssText) : [];
                }}""",
                    stylesheet,
                )
                for rule in css_content:
                    if "@media" in rule:
                        media_queries_found = True
                        break
                if media_queries_found:
                    break
            if media_queries_found:
                result_dict["media_query_responsive"] = True
            else:
                result_dict["media_query_responsive"] = None

    return result_dict


def get_geolocation():
    # Use a geolocation service to determine the approximate location
    response = requests.get("https://ipinfo.io/json")
    data = response.json()
    location = (
        data.get("city", "Unknown City")
        + ", "
        + data.get("region", "Unknown Region")
        + ", "
        + data.get("country", "Unknown Country")
    )
    return location


def has_redirect(url):
    try:
        response = requests.head(url, allow_redirects=False)
        # Check the status code for redirects
        if 300 <= response.status_code < 400:
            return response.headers["Location"]
        else:
            return None
    except requests.RequestException as e:
        print(f"Error {e}")


def resolve_to_same_url(url1):
    try:
        original_string = url1
        url2 = original_string.replace("https://", "https://www.")

        # Resolve IP addresses for both URLs
        ip_address_1 = socket.gethostbyname(url1)
        ip_address_2 = socket.gethostbyname(url2)

        # Check if the resolved IP addresses are the same
        if ip_address_1 == ip_address_2:
            return f"The URLs {url1} and {url2} resolve to the same IP address: {ip_address_1}"

        else:
            return f"The URLs {url1} and {url2} do not resolve to the same IP address. {url1} - {ip_address_1}, {url2} - {ip_address_2}"

    except socket.error as e:
        print(f"Error: {e}")
        return None


def check_spf_record(url):
    domain = urlsplit(url).netloc
    try:
        # Perform a DNS query for SPF records
        answers = dns.resolver.resolve(domain, "TXT")
        # Check if any TXT record contains "v=spf1"
        for rdata in answers:
            for txt_string in rdata.strings:
                if b"v=spf1" in txt_string:
                    return txt_string
                else:
                    return False

        print(f"No SPF record found for {domain}.")
        return False

    except dns.resolver.NXDOMAIN:
        print(f"Domain {domain} does not exist.")
        return False
    except dns.resolver.NoAnswer:
        print(f"No TXT records found for {domain}.")
        return False
    except dns.resolver.Timeout:
        print("DNS query timeout. Check your internet connection or DNS server.")
        return False
    except Exception as e:
        print(f"An error occurred: {e}")
        return False
