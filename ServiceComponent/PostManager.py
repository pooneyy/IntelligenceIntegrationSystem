import os
import hashlib
import markdown


def generate_html_from_markdown(md_file_path: str) -> str:
    """
    Convert Markdown file to HTML with caching mechanism and enhanced styling.

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
    os.makedirs(output_dir, exist_ok=True)

    # Generate file names
    base_name = os.path.splitext(os.path.basename(md_file_path))[0]
    html_file = os.path.join(output_dir, f"{base_name}.html")
    hash_file = os.path.join(output_dir, f"{base_name}.hash")

    try:
        # Calculate current file hash
        with open(md_file_path, "rb") as f:
            current_hash = hashlib.md5(f.read()).hexdigest()

        # Check cache validity
        if (os.path.exists(html_file) and
                os.path.exists(hash_file) and
                open(hash_file, "r").read() == current_hash):
            return html_file  # Valid cache exists

        # Read and convert Markdown
        with open(md_file_path, "r", encoding="utf-8") as f:
            md_content = f.read()
        html_content = markdown.markdown(md_content, extensions=["fenced_code", "tables"])

        full_html = f"""<!DOCTYPE html>
        <html>
        <head>
            <meta charset="utf-8">
            <title>{base_name}</title>
            <link rel="stylesheet" href="/static/github-markdown.css" id="base-css">
            <style>
                /* 马卡龙渐变背景 */
                body {{
                    background: linear-gradient(135deg, 
                        #F8C3CD 0%,   /* 浅粉色 */
                        #A2E4B8 30%,  /* 薄荷绿 */
                        #87CEEB 70%,  /* 天蓝色 */
                        #FFF5C3 100%  /* 奶油黄 */
                    ) fixed;
                    background-size: 300% 300%;
                    animation: gradientBG 15s ease infinite;
                    padding: 20px 0;
                    min-height: 100vh;
                }}
                
                /* 动态背景动画 */
                @keyframes gradientBG {{
                    0% {{ background-position: 0% 50% }}
                    50% {{ background-position: 100% 50% }}
                    100% {{ background-position: 0% 50% }}
                }}
                
                /* 内容区域样式 */
                .markdown-body {{
                    max-width: 800px;
                    margin: 0 auto;
                    padding: 30px;
                    background: rgba(255, 255, 255, 0.85); /* 半透明白色 */
                    border-radius: 12px;
                    box-shadow: 0 8px 32px rgba(162, 228, 184, 0.2); /* 薄荷绿阴影 */
                    backdrop-filter: blur(4px); /* 毛玻璃效果 */
                    border: 1px solid rgba(255, 245, 195, 0.3); /* 奶油黄边框 */
                }}
                
                /* 主题选择器优化 */
                .theme-selector {{
                    background: rgba(255, 255, 255, 0.9) !important;
                    border: 1px solid #F8C3CD !important; /* 浅粉色边框 */
                }}
            </style>
        </head>
        <body>
            <div class="theme-selector">
                <select id="cssSelector" onchange="changeTheme()">
                    <option value="">-- 选择样式 --</option>
                    <option value="https://cdnjs.cloudflare.com/ajax/libs/github-markdown-css/5.1.0/github-markdown-dark.min.css" selected>GitHub风格（暗色）</option>
                    <option value="https://cdnjs.cloudflare.com/ajax/libs/github-markdown-css/5.1.0/github-markdown.min.css">GitHub风格（亮色）</option>
                    <option value="https://cdn.jsdelivr.net/npm/water.css@2/out/dark.min.css">Water.css（暗色）</option>
                    <option value="https://cdn.jsdelivr.net/npm/@picocss/pico@1/css/pico.min.css">Pico.css（暗色）</option>
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

            <div class="markdown-body">
                {html_content}
            </div>

            <script>
                function changeTheme() {{
                    const selectedUrl = document.getElementById("cssSelector").value;
                    if (selectedUrl) {{
                        // 创建新link元素替换现有样式
                        const newLink = document.createElement('link');
                        newLink.rel = 'stylesheet';
                        newLink.href = selectedUrl;

                        // 替换页面中的样式表
                        const existingLinks = document.querySelectorAll('link[rel="stylesheet"]');
                        existingLinks[0].replaceWith(newLink);
                    }}
                }}
            </script>
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
