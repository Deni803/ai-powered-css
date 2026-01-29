app_name = "ai_powered_css"
app_title = "AI Powered CSS"
app_publisher = "Local Dev"
app_description = "AI-powered customer support system"
app_email = "local@example.com"
app_license = "MIT"

# Website pages live under ai_powered_css/www

# Override specific Helpdesk APIs with Postgres-safe variants.
override_whitelisted_methods = {
    "helpdesk.api.doc.get_filterable_fields": "ai_powered_css.api.helpdesk_overrides.get_filterable_fields",
    "helpdesk.helpdesk.doctype.hd_ticket.api.get_ticket_customizations": "ai_powered_css.api.helpdesk_overrides.get_ticket_customizations",
    "helpdesk.helpdesk.doctype.hd_ticket.api.get_recent_similar_tickets": "ai_powered_css.api.helpdesk_overrides.get_recent_similar_tickets",
}
