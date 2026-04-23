DEFAULT_STAFF_PERMS = {
  "clients":   {"read": True,  "create": True,  "update": True,  "delete": False},
  "services":  {"read": True,  "create": False, "update": False, "delete": False},
  "appointments": {"read": True, "create": True, "update": True, "delete": True, "sync_google": True},
  "schedule":  {"read": True},
  "invoices":  {"read": False, "create": False, "update": False, "delete": False},
  "expenses":  {"read": False, "create": False, "update": False, "delete": False},
  "stock":     {"read": True,  "create": True,  "update": True,  "delete": False, "move": True},
  "audit":     {"read": False},
  "company":   {"read": False, "update": False},
  "users":     {"read": False, "create": False, "update": False, "delete": False},
  "site_maps": {"view": True, "create": True, "edit": True, "delete": True},
  "company": {"view": True, "edit": False},
}