import frappe
from frappe.utils.caching import redis_cache
from pypika import Criterion

from helpdesk.api.doc import get_visible_custom_fields
from helpdesk.helpdesk.doctype.hd_form_script.hd_form_script import (
    get_form_script as _core_get_form_script,
)
from helpdesk.helpdesk.doctype.hd_ticket import api as hd_ticket_api
from helpdesk.utils import agent_only, check_permissions


def _is_postgres() -> bool:
    return frappe.db.db_type == "postgres"


def _bool_literal(value: bool) -> int | bool:
    # In Postgres, some Helpdesk tables still store boolean-like fields as smallint.
    # Casting booleans to 0/1 avoids "smallint = boolean" errors during queries.
    return int(bool(value)) if _is_postgres() else value


@frappe.whitelist()
@redis_cache()
def get_filterable_fields(
    doctype: str, show_customer_portal_fields: bool = False, ignore_team_restrictions: bool = False
):
    """Postgres-safe wrapper for Helpdesk filterable fields query."""
    check_permissions(doctype, None)
    QBDocField = frappe.qb.DocType("DocField")
    QBCustomField = frappe.qb.DocType("Custom Field")
    allowed_fieldtypes = [
        "Check",
        "Data",
        "Float",
        "Int",
        "Link",
        "Long Text",
        "Select",
        "Small Text",
        "Text Editor",
        "Text",
        "Rating",
        "Duration",
        "Date",
        "Datetime",
    ]

    hidden_value = _bool_literal(False)
    visible_custom_fields = get_visible_custom_fields()
    customer_portal_fields = [
        "name",
        "subject",
        "status",
        "priority",
        "response_by",
        "resolution_by",
        "creation",
    ]

    from_doc_fields = (
        frappe.qb.from_(QBDocField)
        .select(
            QBDocField.fieldname,
            QBDocField.fieldtype,
            QBDocField.label,
            QBDocField.name,
            QBDocField.options,
        )
        .where(QBDocField.parent == doctype)
        .where(QBDocField.hidden == hidden_value)
        .where(Criterion.any([QBDocField.fieldtype == i for i in allowed_fieldtypes]))
    )

    from_custom_fields = (
        frappe.qb.from_(QBCustomField)
        .select(
            QBCustomField.fieldname,
            QBCustomField.fieldtype,
            QBCustomField.label,
            QBCustomField.name,
            QBCustomField.options,
        )
        .where(QBCustomField.dt == doctype)
        .where(QBCustomField.hidden == hidden_value)
        .where(Criterion.any([QBCustomField.fieldtype == i for i in allowed_fieldtypes]))
    )

    if show_customer_portal_fields:
        from_doc_fields = from_doc_fields.where(
            QBDocField.fieldname.isin(customer_portal_fields)
        )
        if visible_custom_fields:
            from_custom_fields = from_custom_fields.where(
                QBCustomField.fieldname.isin(visible_custom_fields)
            )
            from_custom_fields = from_custom_fields.run(as_dict=True)
        else:
            from_custom_fields = []

    if not show_customer_portal_fields:
        from_custom_fields = from_custom_fields.run(as_dict=True)

    from_doc_fields = from_doc_fields.run(as_dict=True)

    res = []
    res.extend(from_doc_fields)
    res.extend(from_custom_fields)
    if not show_customer_portal_fields and doctype == "HD Ticket":
        res.append(
            {
                "fieldname": "_assign",
                "fieldtype": "Link",
                "label": "Assigned to",
                "name": "_assign",
                "options": "HD Agent",
            }
        )

    if not ignore_team_restrictions:
        enable_restrictions = frappe.db.get_single_value(
            "HD Settings", "restrict_tickets_by_agent_group"
        )
        if enable_restrictions and doctype == "HD Ticket":
            res = [r for r in res if r.get("fieldname") != "agent_group"]

    standard_fields = [
        {"fieldname": "name", "fieldtype": "Link", "label": "ID", "options": doctype},
        {"fieldname": "modified", "fieldtype": "Datetime", "label": "Last Modified"},
        {"fieldname": "owner", "fieldtype": "Link", "label": "Owner", "options": "User"},
        {"fieldname": "creation", "fieldtype": "Datetime", "label": "Created On"},
    ]

    return standard_fields + res


def get_form_script(
    dt: str,
    apply_to: str = "Form",
    is_customer_portal: bool = False,
    apply_on_new_page: bool = False,
):
    """Postgres-safe wrapper for Helpdesk form scripts query."""
    if not _is_postgres():
        return _core_get_form_script(
            dt,
            apply_to=apply_to,
            is_customer_portal=is_customer_portal,
            apply_on_new_page=apply_on_new_page,
        )

    FormScript = frappe.qb.DocType("HD Form Script")
    query = (
        frappe.qb.from_(FormScript)
        .select("script")
        .where(FormScript.dt == dt)
        .where(FormScript.apply_to == apply_to)
        .where(FormScript.enabled == 1)
        .where(FormScript.apply_on_new_page == _bool_literal(apply_on_new_page))
        .where(FormScript.apply_to_customer_portal == _bool_literal(is_customer_portal))
    )

    doc = query.run(as_dict=True)
    if doc:
        return [d.script for d in doc]
    return None


@frappe.whitelist()
@agent_only
def get_ticket_customizations():
    """Postgres-safe ticket customization fetch for the Helpdesk UI."""
    custom_fields = frappe.get_all(
        "HD Ticket Template Field",
        filters={"parent": "Default"},
        fields=["fieldname", "required", "placeholder", "url_method"],
        order_by="idx",
    )
    form_scripts = get_form_script("HD Ticket")
    return {"custom_fields": custom_fields, "_form_script": form_scripts}


@frappe.whitelist()
def get_recent_similar_tickets(ticket: str):
    """Avoid MySQL fulltext SQL on Postgres; return recent-only matches."""
    if _is_postgres():
        if not frappe.db.exists("HD Ticket", ticket):
            return {"recent_tickets": [], "similar_tickets": []}
        return {
            "recent_tickets": hd_ticket_api.get_recent_tickets(ticket),
            "similar_tickets": [],
        }
    return {
        "recent_tickets": hd_ticket_api.get_recent_tickets(ticket),
        "similar_tickets": hd_ticket_api.get_similar_tickets(ticket),
    }
