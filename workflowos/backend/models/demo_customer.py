# workflowos/backend/models/demo_customer.py
import datetime
from sqlalchemy import Column, Integer, String, DateTime, ForeignKey, Text
from sqlalchemy.orm import relationship
from ..database import Base

class DemoCustomer(Base):
    __tablename__ = "demo_customers"
    id = Column(Integer, primary_key=True, index=True)
    name = Column(String, nullable=False, index=True)
    email = Column(String, unique=True, nullable=False, index=True)
    company = Column(String, nullable=True)
    status = Column(String, default="NEW")
    created_at = Column(DateTime, default=datetime.datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.datetime.utcnow, onupdate=datetime.datetime.utcnow)

    requests = relationship("CustomerRequest", backref="customer", cascade="all, delete-orphan")

class CustomerRequest(Base):
    __tablename__ = "customer_requests"
    id = Column(Integer, primary_key=True, index=True)
    customer_id = Column(Integer, ForeignKey("demo_customers.id"), nullable=False)
    subject = Column(String, nullable=True)
    request_text = Column(Text, nullable=True)
    attachment_path = Column(String, nullable=True)
    status = Column(String, default="RECEIVED")
    created_at = Column(DateTime, default=datetime.datetime.utcnow)

