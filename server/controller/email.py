from typing import Optional
from pydantic import BaseModel, EmailStr, Field
from pathlib import Path
import logging
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from email.mime.application import MIMEApplication

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

class EmailConfig(BaseModel):
    """Configuration for email settings with validation"""
    smtp_server: str = Field(default="smtp.gmail.com", description="SMTP server address")
    smtp_port: int = Field(default=587, description="SMTP server port")
    sender_email: EmailStr = Field(default="distributionautopartscanada@gmail.com", description="Email address to send from")
    app_password: str = Field(default="gqreujpsbregrqua", description="App password for email authentication")
    recipient_email: EmailStr = Field(
        default="maxime.letourneau@pasuper.com",
        description="Default recipient email address"
    )

    class Config:
        from_attributes = True

class EmailService:
    """Handles all email-related operations"""
    
    def __init__(self, config: EmailConfig):
        self.config = config

    def _format_body_html(self, body: str) -> str:
        """Format the body text for HTML, preserving line breaks"""
        # Replace newlines with HTML line breaks, preserving paragraph spacing
        formatted_body = body.replace('\n\n', '</p><p>').replace('\n', '<br>')
        # Wrap the content in paragraph tags if not already done
        if not formatted_body.startswith('<p>'):
            formatted_body = f'<p>{formatted_body}</p>'
        return formatted_body

    def _create_html_template(self, body: str) -> str:
        """Create an HTML email template with professional styling"""
        formatted_body = self._format_body_html(body)
        return f"""
    <!DOCTYPE html>
    <html>
    <head>
        <style>
            body {{
                font-family: -apple-system, BlinkMacSystemFont, 'Helvetica Neue', sans-serif;
                line-height: 1.6;
                color: #333;
                margin: 0;
                padding: 0;
                background-color: white;
            }}
            .container {{
                max-width: 580px;
                margin: 0 auto;
                padding: 40px 20px;
            }}
            .logo {{
                margin-bottom: 30px;
                font-size: 16px;
                color: #666;
                text-transform: uppercase;
                letter-spacing: 2px;
            }}
            .content {{
                padding-bottom: 30px;
            }}
            .content p {{
                margin: 0 0 1em 0;
            }}
            .footer {{
                padding-top: 20px;
                border-top: 1px solid #eee;
                font-size: 12px;
                color: #999;
            }}
        </style>
    </head>
    <body>
        <div class="container">
            <div class="logo">
                Distribution Auto Parts Canada
            </div>
            <div class="content">
                {formatted_body}
            </div>
            <div class="footer">
                <p>Sent via Distribution Auto Parts Canada automated system</p>
            </div>
        </div>
    </body>
    </html>
    """

    async def send_email_with_attachment(
        self,
        subject: str,
        body: str,
        attachment_path: Path,
        attachment_name: Optional[str] = None
    ) -> None:
        """Send an email with an attachment"""
        try:
            msg = self._create_email_message(subject, body)
            self._attach_file(msg, attachment_path, attachment_name)
            await self._send_email(msg)
            logger.info(f"Email sent successfully to {self.config.recipient_email}")
        except Exception as e:
            logger.error(f"Failed to send email: {str(e)}")
            raise IOError(f"Email sending failed: {str(e)}")

    def _create_email_message(self, subject: str, body: str) -> MIMEMultipart:
        """Create the email message with headers and HTML body"""
        msg = MIMEMultipart('alternative')
        msg['From'] = self.config.sender_email
        msg['To'] = self.config.recipient_email
        msg['Subject'] = subject

        # Add plain text version for email clients that don't support HTML
        text_part = MIMEText(body, 'plain')
        msg.attach(text_part)

        # Add HTML version
        html_content = self._create_html_template(body)
        html_part = MIMEText(html_content, 'html')
        msg.attach(html_part)

        return msg

    def _attach_file(
        self,
        msg: MIMEMultipart,
        file_path: Path,
        attachment_name: Optional[str] = None
    ) -> None:
        """Attach a file to the email message"""
        with open(file_path, 'rb') as file:
            attachment = MIMEApplication(file.read(), _subtype='csv')
            attachment.add_header(
                'Content-Disposition',
                'attachment',
                filename=attachment_name or file.name
            )
            msg.attach(attachment)

    async def _send_email(self, msg: MIMEMultipart) -> None:
        """Send the email using SMTP"""
        try:
            with smtplib.SMTP(self.config.smtp_server, self.config.smtp_port) as server:
                server.ehlo()
                server.starttls()
                server.ehlo()
                
                try:
                    server.login(self.config.sender_email, self.config.app_password)
                except smtplib.SMTPAuthenticationError as auth_error:
                    logger.error(f"Authentication failed: {auth_error}")
                    raise IOError(
                        "Email authentication failed. Please verify your credentials "
                        "and ensure you're using an App Password if using Gmail."
                    )

                server.send_message(msg)
        except smtplib.SMTPConnectError as conn_error:
            logger.error(f"Connection error: {conn_error}")
            raise IOError(f"Failed to connect to email server: {conn_error}")