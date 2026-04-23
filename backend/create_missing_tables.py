# create_missing_tables.py

from app.core.database import Base, engine
import app.models
import app.models.company_permission
import app.models.user_permission

print("A criar tabelas em falta...")
Base.metadata.create_all(bind=engine)
print("Concluído.")