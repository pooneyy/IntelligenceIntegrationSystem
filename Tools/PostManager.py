import os
import hashlib
import markdown


def generate_html_from_markdown(md_file_path: str) -> str:
    """
    Convert Markdown file to HTML with caching mechanism.

    Args:
        md_file_path: Path to the Markdown file

    Returns:
        str: Path to generated HTML file if successful, empty string otherwise
    """
    # Validate input file
    if not os.path.isfile(md_file_path):
        return ""

    # Configure output directory
    output_dir = "templates/generated"
    os.makedirs(output_dir, exist_ok=True)  # [2,5](@ref)

    # Generate file names
    base_name = os.path.splitext(os.path.basename(md_file_path))[0]
    html_file = os.path.join(output_dir, f"{base_name}.html")
    hash_file = os.path.join(output_dir, f"{base_name}.hash")

    try:
        # Calculate current file hash
        with open(md_file_path, "rb") as f:
            current_hash = hashlib.md5(f.read()).hexdigest()  # [1](@ref)

        # Check cache validity
        if (os.path.exists(html_file) and
                os.path.exists(hash_file) and
                open(hash_file, "r").read() == current_hash):
            return html_file  # Valid cache exists

        # Read and convert Markdown
        with open(md_file_path, "r", encoding="utf-8") as f:
            md_content = f.read()
        html_content = markdown.markdown(md_content, extensions=["fenced_code", "tables"])

        # Generate full HTML document
        # Generate full HTML document with dynamic CSS selector
        full_html = f"""<!DOCTYPE html>
        <html>
        <head>
            <meta charset="utf-8">
            <title>{base_name}</title>
            <link rel="stylesheet" href="/static/github-markdown.css" id="base-css">
            <link rel="stylesheet" href="" id="dynamic-css">
            <script>
                function changeTheme() {{
                    var selectedUrl = document.getElementById("cssSelector").value;
                    document.getElementById("dynamic-css").href = selectedUrl;
                }}
            </script>
            <style>
                .theme-selector {{
                    position: fixed;
                    top: 15px;
                    right: 15px;
                    z-index: 1000;
                    background: rgba(255,255,255,0.9);
                    padding: 8px 12px;
                    border-radius: 4px;
                    box-shadow: 0 2px 5px rgba(0,0,0,0.1);
                }}
                select {{
                    padding: 6px 10px;
                    border: 1px solid #ddd;
                    border-radius: 4px;
                    background: white;
                }}
            </style>
        </head>
        <body class="markdown-body">
            <div class="theme-selector">
                <select id="cssSelector" onchange="changeTheme()">
                    <option value="">-- 选择样式 --</option>
                    <option value="/static/github-markdown.css">GitHub风格</option>
                    <option value="https://cdn.jsdelivr.net/npm/water.css@2/out/water.css">Water.css（轻量）</option>
                    <option value="https://cdn.jsdelivr.net/npm/bootstrap@5.1.3/dist/css/bootstrap.min.css">Bootstrap 5</option>
                    <option value="https://cdn.jsdelivr.net/npm/milligram@1.4.1/dist/milligram.min.css">Milligram（极简）</option>
                    <option value="https://cdn.jsdelivr.net/npm/@picocss/pico@1/css/pico.min.css">Pico.css</option>
                    <option value="https://cdn.jsdelivr.net/npm/bulma@0.9.3/css/bulma.min.css">Bulma</option>
                    <option value="https://cdn.jsdelivr.net/npm/sakura.css/css/sakura.css">Sakura（樱花）</option>
                    <option value="https://cdn.jsdelivr.net/npm/holiday.css@0.9.8">Holiday.css</option>
                    <option value="https://cdn.jsdelivr.net/npm/awsm.css@3.0.7/dist/awsm.min.css">awsm.css</option>
                    <option value="https://cdn.jsdelivr.net/npm/mvp.css@1.12/mvp.min.css">MVP.css</option>
                    <option value="https://cdn.jsdelivr.net/npm/papercss@1.6.1/dist/paper.min.css">PaperCSS（手绘风）</option>
                    <option value="https://cdn.jsdelivr.net/npm/retro.css@1.2.0/dist/retro.css">Retro（复古）</option>
                </select>
            </div>
            {html_content}
        </body>
        </html>"""

        # Save files
        with open(html_file, "w", encoding="utf-8") as f:
            f.write(full_html)
        with open(hash_file, "w", encoding="utf-8") as f:
            f.write(current_hash)

        return html_file

    except Exception as e:
        print(f"Error processing {md_file_path}: {str(e)}")
        return ""