from sqlalchemy import Column, Integer, String, DateTime, func, Boolean, relationship

from .database import Base


class User(Base):
    __tablename__ = "User"
    id = Column(Integer, primary_key=True, autoincrement=True)
    created_at = Column(DateTime, default=func.now())
    updated_at = Column(DateTime, onupdate=func.now(), default=func.now())
    clerk_id = Column(String, unique=True, index=True)
    organization_id = Column(String, default="")
    email = Column(String, unique=True, index=True)
    firstname = Column(String, default=True)
    lastname = Column(String, default=True)
    fullname = Column(String, default=True)
    stripe_customer_id = Column(String, default=True)
    stripe_subscription_id = Column(String, default=True)
    stripe_payment_method = Column(String, default=True)
    slack_auth_state_id = Column(String, default=True)
    zendesk_auth_state_id = Column(String, default=True)
    slack = relationship("Slack", backref=backref("user"))
    zendesk = relationship("Zendesk", backref=backref("user"))
    organization = relationship("Organization", backref=backref("users"))


class Slack(Base):
    __tablename__ = 'Slack'
    id = Column(Integer, primary_key=True, autoincrement=True)
    created_at = Column(DateTime, default=func.now())
    updated_at = Column(DateTime, onupdate=func.now(), default=func.now())
    user_id = Column(String(191, 'utf8mb4_unicode_ci'), nullable=False, unique=True)
    access_token = Column(String(191, 'utf8mb4_unicode_ci'), nullable=False, server_default="")
    team_id = Column(String(191, 'utf8mb4_unicode_ci'), nullable=False, server_default="")
    team_name = Column(String(191, 'utf8mb4_unicode_ci'), nullable=False, server_default="")
    bot_id = Column(String(191, 'utf8mb4_unicode_ci'), nullable=False, server_default="")
    bot_access_token = Column(String(191, 'utf8mb4_unicode_ci'), nullable=False, server_default="")
    scopes = Column(String(191, 'utf8mb4_unicode_ci'), nullable=False, server_default="")


class Zendesk(Base):
    __tablename__ = 'Zendesk'
    id = Column(Integer, primary_key=True, autoincrement=True)
    created_at = Column(DateTime, default=func.now())
    updated_at = Column(DateTime, onupdate=func.now(), default=func.now())
    user_id = Column(String, unique=True)
    access_token = Column(String, nullable=False)
    subdomain = Column(String, unique=True)
    account_email = Column(String, default="")
    account_id = Column(String, default="")
    guide = Column(Boolean, default=False)
    support = Column(Boolean, default=False)


class Issue(Base):
    __tablename__ = 'issue'

    id = Column(Integer, primary_key=True, autoincrement=True)
    created_at = Column(DateTime, default=func.now())
    updated_at = Column(DateTime, onupdate=func.now())
    user_id = Column(String)
    org_name = Column(String, default="")
    channel = Column(Enum('slack', 'teams', 'gmail', 'zoom', 'yammer'))
    org_id = Column(String)
    employee_id = Column(String)
    employee_name = Column(String, default="")
    employee_email = Column(String, default="")
    category = Column(Enum('leave_policy', 'password_reset', 'benefits_info', 'hardware_issue', 'payroll_info', 'software_issue', 'onboarding_offboarding'))
    messageHistory = Column(String)
    status = Column(Enum('open', 'resolved', 'unresolved', 'closed'))
    is_satisfied = Column(Boolean)
    reason = Column(String)
    user = relationship("User", backref=backref("issues"))
    organization = relationship("Organization", backref=backref("issues"))
