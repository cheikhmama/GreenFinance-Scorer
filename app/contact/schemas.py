from pydantic import BaseModel, ConfigDict, EmailStr, Field, field_validator


class ContactMessageRequest(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True, extra="forbid")

    name: str = Field(min_length=2, max_length=100)
    email: EmailStr = Field(max_length=254)
    subject: str = Field(min_length=3, max_length=150)
    message: str = Field(min_length=20, max_length=5000)

    @field_validator("name", "subject")
    @classmethod
    def single_line(cls, value: str) -> str:
        if any(ord(character) < 32 or ord(character) == 127 for character in value):
            raise ValueError("Ce champ doit tenir sur une seule ligne.")
        return value
