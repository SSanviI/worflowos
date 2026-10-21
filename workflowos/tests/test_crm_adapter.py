# workflowos/tests/test_crm_adapter.py
"""Tests for Local CRM Database Adapter."""

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from workflowos.backend.database import Base
from workflowos.backend.models.demo_customer import DemoCustomer, CustomerRequest
from workflowos.automation.adapters.crm import CRMAdapter


@pytest.fixture
def db_session():
    engine = create_engine("sqlite:///:memory:", connect_args={"check_same_thread": False})
    Base.metadata.create_all(bind=engine)
    Session = sessionmaker(bind=engine)
    session = Session()

    # Seed test customer
    cust = DemoCustomer(name="Test Customer", email="testcustomer@example.com", company="ACME Corp", status="NEW")
    session.add(cust)
    session.commit()
    session.refresh(cust)

    yield session
    session.close()


def test_find_customer_success(db_session):
    context = {}
    success, result, err = CRMAdapter.find_customer(
        db=db_session,
        params={"name": "Test Customer"},
        context=context,
    )

    assert success is True
    assert err is None
    assert result["status"] == "SUCCESS"
    assert result["mode"] == "REAL_DATABASE"
    assert result["connector"] == "Local CRM DB"
    assert result["name"] == "Test Customer"
    assert context["customer_id"] == 1
    assert context["customer_name"] == "Test Customer"


def test_find_customer_not_found(db_session):
    context = {}
    success, result, err = CRMAdapter.find_customer(
        db=db_session,
        params={"name": "Nonexistent Customer Name"},
        context=context,
    )

    assert success is False
    assert result["status"] == "customer_not_found"
    assert "not found in Local CRM database" in err


def test_update_customer_success(db_session):
    context = {"customer_id": 1, "email_subject": "WorkFlowOS Request", "email_body": "Please process request"}
    success, result, err = CRMAdapter.update_customer(
        db=db_session,
        params={"status": "PROCESSED"},
        context=context,
    )

    assert success is True
    assert err is None
    assert result["status"] == "SUCCESS"
    assert result["mode"] == "REAL_DATABASE"
    assert result["connector"] == "Local CRM DB"

    # Verify database update
    cust = db_session.query(DemoCustomer).filter(DemoCustomer.id == 1).first()
    assert cust.status == "PROCESSED"

    # Verify request record in database
    reqs = db_session.query(CustomerRequest).filter(CustomerRequest.customer_id == 1).all()
    assert len(reqs) == 1
    assert reqs[0].subject == "WorkFlowOS Request"
