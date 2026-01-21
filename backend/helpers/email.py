from redmail import gmail
from jinja2 import Environment, FileSystemLoader
import os
from dotenv import load_dotenv
from pathlib import Path

load_dotenv()

gmail.username = os.getenv("SENDER_EMAIL")
gmail.password = os.getenv("EMAIL_PASSWORD") 

template_dir = os.path.join(os.getcwd(), "routers", "templates")
env = Environment(loader=FileSystemLoader(template_dir))

def auth_send_email(email_type: str, email: str, name: str, subject: str):
    """
    Handles dynamic email sending for registration and password resets.
    email_type: should be "register" or "password_reset"
    """
    # 1. Load the template using the email_type argument
    template = env.get_template(f"{email_type}.html")
    
    link = "http://localhost:3000/" if email_type == "register" else f"http://localhost:3000/reset-password?email={email}"
    
    rendered_html = template.render(
        user_name=name,
        reset_link=link
    )
    
    gmail.send(
        subject=subject,
        receivers=[email],
        html=rendered_html
    )


def order_notification_email(email: str, name: str, Order):
    """
    Handles dynamic email sending for Order confirmation
    """
   
    template = env.get_template("order-confirmation.html")
    
    link = "http://localhost:3000/profile/orders"
    
    rendered_html = template.render(
        user_name=name,
        order_id=Order.id,
        reset_link=link,
        total_price=Order.total_price,
        items=Order.order_items
    )
    
    gmail.send(
        subject="Thank you for your order",
        receivers=[email],
        html=rendered_html
    )
