import html2text
from bs4 import BeautifulSoup


def html_content_converter(html_content, selector, output_format='markdown'):
    """
    Extract the content of the specified HTML element and convert it to the target format

    :param html_content: original HTML string
    :param selector: CSS selector string, such as 'div.left_zw'
    :param output_format: output format, optional 'markdown' or 'text'
    :return: converted text content
    """
    soup = BeautifulSoup(html_content, 'html.parser')
    target_element = soup.select_one(selector)

    if not target_element:
        return ""

    if output_format == 'text':
        return target_element.get_text(separator='\n', strip=True)
    elif output_format == 'markdown':
        converter = html2text.HTML2Text()
        converter.ignore_links = False
        converter.ignore_images = True
        return converter.handle(target_element.decode_contents()).strip()
    else:
        raise ValueError("Unsupported output format, please select 'markdown' or 'text'")
