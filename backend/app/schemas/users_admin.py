from pydantic import BaseModel, EmailStr, Field

class StaffCreate(BaseModel):
    name: str = Field(..., min_length=2, max_length=120)
    email: EmailStr
    password: str = Field(..., min_length=6, max_length=128)
    role: str | None = None  # opcional, mas vamos ignorar e forçar STAFF