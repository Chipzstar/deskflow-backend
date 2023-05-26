from sqlalchemy import Column, Integer, String

from .database import Base


class User(Base):
    __tablename__ = "User"
    id = Column(Integer, primary_key=True, index=True)
    created_at = Column(String, default=True)
    updated_at = Column(String, default=True)
    clerk_id = Column(String, unique=True, index=True)
    email = Column(String, unique=True, index=True)
    firstname = Column(String, default=True)
    lastname = Column(String, default=True)
    fullname = Column(String, default=True)
    stripe_customer_id = Column(String, default=True)
    stripe_subscription_id = Column(String, default=True)
    slack_access_token = Column(String, default=True)
    stripe_payment_method = Column(String, default=True)
    slack_auth_state_id = Column(String, default=True)


class Slack(Base):
    __tablename__ = 'Slack'
    id = Column(Integer, primary_key=True)
    user_id = Column(String(191, 'utf8mb4_unicode_ci'), nullable=False, unique=True)
    access_token = Column(String(191, 'utf8mb4_unicode_ci'), nullable=False, server_default="")
    team_id = Column(String(191, 'utf8mb4_unicode_ci'), nullable=False, server_default="")
    team_name = Column(String(191, 'utf8mb4_unicode_ci'), nullable=False, server_default="")
    bot_id = Column(String(191, 'utf8mb4_unicode_ci'), nullable=False, server_default="")
    bot_access_token = Column(String(191, 'utf8mb4_unicode_ci'), nullable=False, server_default="")
    scopes = Column(String(191, 'utf8mb4_unicode_ci'), nullable=False, server_default="")
