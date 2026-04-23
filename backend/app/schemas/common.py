from pydantic import BaseModel


class UserMini(BaseModel):
    id: int
    name: str
    email: str

    class Config:
        from_attributes = True
    