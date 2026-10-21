# workflowos/automation/adapters/crm.py
"""Local CRM Database Adapter for WorkFlowOS.

Executes REAL database operations against SQLite CRM store:
- Queries `demo_customers` table for customer profile lookup.
- Modifies customer record status and logs `customer_requests` in SQLite DB.
- Returns authentic execution results directly from database queries.
"""

import logging
import re
from typing import Dict, Any, Tuple, Optional
from .base import BaseAdapter
from ...backend.models.demo_customer import DemoCustomer, CustomerRequest

logger = logging.getLogger("workflowos.automation.crm")


class CRMAdapter(BaseAdapter):
    """Executes authentic Local CRM database operations."""

    @classmethod
    def find_customer(
        cls,
        db: Any,
        params: Dict[str, Any],
        context: Dict[str, Any]
    ) -> Tuple[bool, Any, Optional[str]]:
        resolved = cls.resolve_params(params, context)

        # Look up query name or email from params, context, or parsed email body
        query_name = (
            resolved.get("name")
            or resolved.get("customer_name")
            or context.get("customer_name")
        )
        query_email = (
            resolved.get("email")
            or resolved.get("customer_email")
            or context.get("email_sender")
        )

        clean_name = query_name
        clean_email = query_email

        if query_email and "<" in query_email and ">" in query_email:
            parts = query_email.split("<")
            if not clean_name and parts[0].strip():
                clean_name = parts[0].strip().strip('"').strip("'")
            clean_email = parts[1].split(">")[0].strip()

        # If name is still missing, attempt regex extraction from email body text
        if not clean_name and context.get("email_body"):
            body_text = context["email_body"]
            match = re.search(r"Customer:\s*([^\n\r]+)", body_text, re.IGNORECASE)
            if match:
                clean_name = match.group(1).strip()

        if db is None:
            return False, {
                "action": "FIND_CUSTOMER",
                "connector": "Local CRM DB",
                "mode": "REAL_DATABASE",
                "status": "db_unavailable",
            }, "Database session is unavailable."

        query = db.query(DemoCustomer)
        cust = None

        if clean_email:
            cust = query.filter(DemoCustomer.email.ilike(f"%{clean_email}%")).first()
        if not cust and clean_name:
            cust = query.filter(DemoCustomer.name.ilike(f"%{clean_name}%")).first()

        if cust:
            # Store resolved customer profile in context
            context["customer_id"] = cust.id
            context["customer_name"] = cust.name
            context["customer_email"] = cust.email
            context["current_app"] = "Local CRM Database"

            return True, {
                "action": "FIND_CUSTOMER",
                "connector": "Local CRM DB",
                "mode": "REAL_DATABASE",
                "status": "SUCCESS",
                "customer_id": cust.id,
                "name": cust.name,
                "email": cust.email,
                "company": cust.company or "N/A",
                "current_status": cust.status,
            }, None

        target_str = clean_name or clean_email or query_name or query_email or "any customer"
        return False, {
            "action": "FIND_CUSTOMER",
            "connector": "Local CRM DB",
            "mode": "REAL_DATABASE",
            "status": "customer_not_found",
            "searched_for": target_str,
        }, f"Customer '{target_str}' not found in Local CRM database. Human intervention required."

    @classmethod
    def update_customer(
        cls,
        db: Any,
        params: Dict[str, Any],
        context: Dict[str, Any]
    ) -> Tuple[bool, Any, Optional[str]]:
        resolved = cls.resolve_params(params, context)
        customer_id = resolved.get("customer_id") or context.get("customer_id")

        if not customer_id:
            return False, {
                "action": "UPDATE_CUSTOMER",
                "connector": "Local CRM DB",
                "mode": "REAL_DATABASE",
                "status": "missing_customer_id",
            }, "Cannot update customer: No customer_id resolved from prior step or context."

        if db is None:
            return False, {
                "action": "UPDATE_CUSTOMER",
                "connector": "Local CRM DB",
                "mode": "REAL_DATABASE",
                "status": "db_unavailable",
            }, "Database session is unavailable."

        cust = db.query(DemoCustomer).filter(DemoCustomer.id == customer_id).first()
        if not cust:
            return False, {
                "action": "UPDATE_CUSTOMER",
                "connector": "Local CRM DB",
                "mode": "REAL_DATABASE",
                "status": "customer_not_found",
                "customer_id": customer_id,
            }, f"Customer ID {customer_id} not found in Local CRM database to update."

        # Perform actual database updates
        new_status = resolved.get("status") or "REQUEST_PROCESSED"
        cust.status = new_status

        # Create record in customer_requests table
        req_record = CustomerRequest(
            customer_id=cust.id,
            subject=context.get("email_subject", "WorkFlowOS Request"),
            request_text=context.get("email_body", "Processed by WorkFlowOS engine"),
            attachment_path=context.get("attachment_path", ""),
            status="PROCESSED",
        )
        db.add(req_record)
        db.commit()
        db.refresh(cust)
        db.refresh(req_record)

        return True, {
            "action": "UPDATE_CUSTOMER",
            "connector": "Local CRM DB",
            "mode": "REAL_DATABASE",
            "status": "SUCCESS",
            "customer_id": cust.id,
            "customer_name": cust.name,
            "new_status": cust.status,
            "request_record_id": req_record.id,
        }, None
