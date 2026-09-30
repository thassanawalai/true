def create_html_dashboard(report_title: str, summary_data: str, user_company: str) -> dict:
    """
    Generate an HTML dashboard for customer summary reports.
    """
    print(f"[Report Engine] Generating HTML dashboard for: {user_company}")

    # Predefined HTML/CSS template designed for a clean, professional corporate dashboard.
    html_template = f"""
    <!DOCTYPE html>
    <html lang="en">
    <head>
        <meta charset="UTF-8">
        <title>{report_title}</title>
        <style>
            body {{ font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif; background: #f8f9fa; color: #333; margin: 0; padding: 20px; }}
            .report-card {{ background: #ffffff; max-width: 600px; margin: 0 auto; padding: 30px; border-radius: 12px; box-shadow: 0 4px 15px rgba(0, 0, 0, 0.05); border-top: 5px solid #007bff; }}
            h1 {{ color: #007bff; font-size: 22px; margin-top: 0; }}
            .meta {{ font-size: 13px; color: #6c757d; margin-bottom: 20px; border-bottom: 1px solid #eee; padding-bottom: 10px; }}
            .content-box {{ background: #f1f3f5; padding: 15px; border-radius: 8px; line-height: 1.6; white-space: pre-line; }}
            .footer {{ margin-top: 25px; text-align: center; font-size: 12px; color: #adb5bd; }}
        </style>
    </head>
    <body>
        <div class="report-card">
            <h1>{report_title}</h1>
            <div class="meta">Company: <b>{user_company}</b> | Report Status: Automatically updated by the system</div>
            <div class="content-box">{summary_data}</div>
            <div class="footer">AI Support Assistant - Report Module</div>
        </div>
    </body>
    </html>
    """

    return {
        "success": True,
        "report_title": report_title,
        "html_code": html_template,
        "message": "The HTML dashboard report was generated successfully. The generated code can be displayed or provided to the customer.",
    }