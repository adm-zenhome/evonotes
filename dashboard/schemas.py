from pydantic import BaseModel, Field
from typing import Optional, List, Dict, Any

class PromptRequest(BaseModel):
    prompt: str
    context: Optional[str] = None
    model: Optional[str] = "gpt-4o-mini"
    meeting_id: Optional[str] = None

class PlaudConnectRequest(BaseModel):
    email: str
    password: Optional[str] = ""
    token: Optional[str] = ""

class TaskStatusUpdateRequest(BaseModel):
    status: str

class TaskCreateRequest(BaseModel):
    action: str
    owner: Optional[str] = "Felipe Donato"
    deadline_or_context: Optional[str] = "Hoje"
    meeting_id: Optional[str] = "general"

class TaskActionUpdateRequest(BaseModel):
    action: str

class TaskDeadlineUpdateRequest(BaseModel):
    deadline: str

class TaskOwnerUpdateRequest(BaseModel):
    owner: str

class MeetingTitleUpdateRequest(BaseModel):
    title: str

class ProfileUpdateRequest(BaseModel):
    profession_area: str = "general"
    user_name: Optional[str] = "Felipe Donato"
    user_role: Optional[str] = "CEO / Liderança"

class CategoryCreateRequest(BaseModel):
    name: str
    icon: Optional[str] = "📁"
    color: Optional[str] = "gray"

class ChannelCreateRequest(BaseModel):
    name: str
    type: Optional[str] = "custom"
    enabled: Optional[bool] = True

class SendEmailRequest(BaseModel):
    to_email: str
    subject: str
    body: str
    meeting_id: Optional[str] = None

class ZApiConfigUpdateRequest(BaseModel):
    instance_id: str
    token: str
    client_token: Optional[str] = None

class ProcessItemRequest(BaseModel):
    item_id: str
    source: Optional[str] = "plaud"
