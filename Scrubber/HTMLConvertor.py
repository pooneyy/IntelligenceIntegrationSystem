import html2text
from bs4 import BeautifulSoup
import copy


def html_content_converter(html_content, selectors, exclude_selectors=None, output_format='markdown'):
    """
    Extracts content from HTML using multiple CSS selectors, removes excluded elements,
    and converts to specified format.

    :param html_content: Original HTML string
    :param selectors: CSS selector(s) for target content (str or list of str).
                      Elements are extracted in specified order.
    :param exclude_selectors: CSS selector(s) for elements to remove (str or list of str).
                              Applied within each extracted element.
    :param output_format: Output format ('markdown' or 'text')
    :return: Converted text content

    Selector Format:
    - Single selector: 'div.content'
    - Multiple selectors: ['.article', '#main'] (extracts .article first, then #main)

    Exclude Format:
    - Single exclude: '.ads'
    - Multiple excludes: ['.ads', '.footer'] (removes both from extracted content)
    """
    # Parse HTML
    soup = BeautifulSoup(html_content, 'html.parser')
    converter = html2text.HTML2Text()
    converter.ignore_links = False
    converter.ignore_images = True

    # Normalize selectors to list
    if isinstance(selectors, str):
        selectors = [selectors]

    # Normalize exclude_selectors to list
    if exclude_selectors is None:
        exclude_selectors = []
    elif isinstance(exclude_selectors, str):
        exclude_selectors = [exclude_selectors]

    # Extract elements in order
    extracted_elements = []
    for selector in selectors:
        elements = soup.select(selector)
        for element in elements:
            # Work on a copy to avoid modifying original
            element_copy = copy.copy(element)

            # Remove excluded elements
            for ex_selector in exclude_selectors:
                for unwanted in element_copy.select(ex_selector):
                    unwanted.decompose()

            extracted_elements.append(element_copy)

    # No elements found
    if not extracted_elements:
        return ""

    # Convert based on format
    if output_format == 'text':
        return '\n\n'.join(
            el.get_text(separator='\n', strip=True)
            for el in extracted_elements
        )
    elif output_format == 'markdown':
        return '\n\n'.join(
            converter.handle(str(el)).strip()
            for el in extracted_elements
        )
    else:
        raise ValueError("Unsupported output format. Use 'markdown' or 'text'")
