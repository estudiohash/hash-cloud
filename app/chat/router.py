from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.responses import StreamingResponse, Response
from pydantic import BaseModel
from app.core.jwt import require_auth
from app.voice.factory import get_voice_provider
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
    provider: str | None = None


class SynthesizeRequest(BaseModel):
    text: str
    voice_id: str | None = None


def _build_system_prompt() -> str:
    sources = get_hash_sources()
    base_context = compile_base_context(sources)
    style_context = compile_style_context(sources)
    return (
        f"Identidad de HASH:\n{base_context['sources']['cognitive_base']}\n\n"
        f"Log personal:\n{base_context['sources']['personal_log']}\n\n"
        f"Destilador:\n{base_context['sources']['destilador']}\n\n"
        f"Estilo:\n{style_context['sources']['style']}"
    )


def _is_quota_error(e: Exception) -> bool:
    msg = str(e)
    return "429" in msg or "503" in msg or "fallaron" in msg


def _get_fallback_provider(provider_name: str):
    """Devuelve el provider de fallback según el principal."""
    if provider_name != "groq":
        from app.llm.groq import GroqProvider
        return GroqProvider()
    return None


@router.post("")
def chat(body: ChatRequest, user: dict = Depends(require_auth)):
    try:
        system_prompt = _build_system_prompt()
        messages = [{"role": "system", "content": system_prompt}] + [m.model_dump() for m in body.messages]
        llm = get_llm_provider(body.provider)
        try:
            reply = llm.generate(messages)
        except RuntimeError as e:
            if _is_quota_error(e):
                fallback = _get_fallback_provider(llm.__class__.__name__.lower().replace("provider", ""))
                if fallback:
                    reply = fallback.generate(messages)
                else:
                    raise
            else:
                raise
        return {"reply": reply}
    except NotImplementedError as e:
        raise HTTPException(status_code=status.HTTP_501_NOT_IMPLEMENTED, detail=str(e))
    except Exception as e:
        traceback.print_exc()
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(e))


@router.post("/stream")
def chat_stream(body: ChatRequest, user: dict = Depends(require_auth)):
    try:
        system_prompt = _build_system_prompt()
        messages = [{"role": "system", "content": system_prompt}] + [m.model_dump() for m in body.messages]
        llm = get_llm_provider()

        def event_stream():
            try:
                for chunk in llm.generate_stream(messages):
                    escaped = chunk.replace("\n", "\\n")
                    yield f"data: {escaped}\n\n"
            except RuntimeError as e:
                if _is_quota_error(e):
                    # Fallback a Groq en streaming
                    try:
                        from app.llm.groq import GroqProvider
                        fallback = GroqProvider()
                        for chunk in fallback.generate_stream(messages):
                            escaped = chunk.replace("\n", "\\n")
                            yield f"data: {escaped}\n\n"
                    except Exception as fe:
                        yield f"data: [ERROR] {str(fe)}\n\n"
                else:
                    yield f"data: [ERROR] {str(e)}\n\n"
            except Exception as e:
                yield f"data: [ERROR] {str(e)}\n\n"
            finally:
                yield "data: [DONE]\n\n"

        return StreamingResponse(
            event_stream(),
            media_type="text/event-stream",
            headers={
                "Cache-Control": "no-cache",
                "X-Accel-Buffering": "no",
            },
        )
    except Exception as e:
        traceback.print_exc()
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(e))


@router.post("/synthesize")
def synthesize(body: SynthesizeRequest, user: dict = Depends(require_auth)):
    try:
        voice = get_voice_provider()
        audio = voice.synthesize(body.text, voice_id=body.voice_id)
        return Response(content=audio, media_type="audio/mpeg")
    except RuntimeError as e:
        raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail=str(e))
    except Exception as e:
        traceback.print_exc()
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(e))


@router.post("/synthesize/stream")
def synthesize_stream(body: SynthesizeRequest, user: dict = Depends(require_auth)):
    try:
        voice = get_voice_provider()

        def audio_chunks():
            try:
                for chunk in voice.synthesize_stream(body.text, voice_id=body.voice_id):
                    yield chunk
            except Exception as e:
                print(f"Error en stream de audio: {e}")

        return StreamingResponse(
            audio_chunks(),
            media_type="audio/mpeg",
            headers={"Cache-Control": "no-cache"},
        )
    except RuntimeError as e:
        raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail=str(e))
    except Exception as e:
        traceback.print_exc()
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(e))
