"""Customer CRUD service — mirrors app.services.vendors."""
from sqlalchemy import select

from app.models.customer import Customer


def list_customers(session):
    return session.execute(select(Customer)).scalars().all()


def create_customer(session, name, phone, address, type_tag=None, credit_days=None, branch_id=1):
    if not name or not name.strip():
        raise ValueError("Customer name is required")
    customer = Customer(
        name=name.strip(), phone=phone, address=address,
        type_tag=type_tag.strip() if type_tag else None,
        credit_days=int(credit_days) if credit_days else None,
        branch_id=branch_id,
    )
    session.add(customer)
    session.commit()
    return customer


def update_customer(session, customer_id, name=None, phone=None, address=None,
                     type_tag=None, credit_days=None):
    customer = session.get(Customer, customer_id)
    if customer is None:
        raise ValueError(f"No such customer: {customer_id}")
    if name is not None:
        if not name.strip():
            raise ValueError("Customer name is required")
        customer.name = name.strip()
    if phone is not None:
        customer.phone = phone
    if address is not None:
        customer.address = address
    if type_tag is not None:
        customer.type_tag = type_tag.strip() or None
    if credit_days is not None:
        customer.credit_days = int(credit_days) if credit_days else None
    session.commit()
    return customer


def delete_customer(session, customer_id):
    customer = session.get(Customer, customer_id)
    if customer is None:
        raise ValueError(f"No such customer: {customer_id}")
    if customer.orders:
        raise ValueError(
            "Can't delete a customer with existing order history — "
            "this would break the ledger. Consider archiving instead."
        )
    session.delete(customer)
    session.commit()
