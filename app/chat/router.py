from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel
from app.core.jwt import require_auth
from app.llm.factory import get_llm_provider
from app.context.provider import get_hash_sources
from app.compiler.base_compiler import compile_base_context
from app.compiler.style_compiler import compile_style_context
import traceback

router = APIRouter(prefix="/chat", tags=["chat"])


class Message(BaseModel):
    role: str
    content: str


class ChatRequest(BaseModel):
    messages: list[Message]


@router.post("")
def chat(body: ChatRequest, user: dict = Depends(require_auth)):
    try:
        sources = get_hash_sources()
        base_context = compile_base_context(sources)
        style_context = compile_style_context(sources)

        system_prompt = (
            f"Identidad de HASH:\n{base_context['sources']['cognitive_base']}\n\n"
            f"Log personal:\n{base_context['sources']['personal_log']}\n\n"
            f"Destilador:\n{base_context['sources']['destilador']}\n\n"
            f"Estilo:\n{style_context['sources']['style']}"
        )

        messages = [{"role": "system", "content": system_prompt}] + [m.model_dump() for m in body.messages]

        llm = get_llm_provider()
        reply = llm.generate(messages)
        return {"reply": reply}
    except NotImplementedError as e:
        raise HTTPException(status_code=status.HTTP_501_NOT_IMPLEMENTED, detail=str(e))
    except Exception as e:
        traceback.print_exc()
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(e))
