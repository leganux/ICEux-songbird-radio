from datetime import datetime, timezone

from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from app.models import AIJob, MediaAsset


def create_ai_job(session: Session, *, job_type: str, topic: str, prompt: str = "", voice: str = "") -> AIJob:
    script = (
        f"Capsula generada para ICEux Songbird Radio sobre {topic}. "
        "Este borrador espera conexion con el proveedor de IA y TTS configurado."
    )
    job = AIJob(
        job_type=job_type or "capsule",
        topic=topic,
        prompt=prompt,
        script=script,
        script_provider="stub",
        tts_provider="stub",
        voice=voice,
        status="script_ready",
    )
    session.add(job)
    session.commit()
    session.refresh(job)
    return job


def mark_ai_job_ready_without_audio(session: Session, job_id: int) -> AIJob:
    job = session.get(AIJob, job_id)
    if not job:
        raise ValueError("job not found")
    asset = MediaAsset(
        type="capsule" if job.job_type == "capsule" else "ai_voice",
        title=job.topic or f"AI {job.job_type}",
        artist="ICEux AI",
        category="ai",
        local_cache_path=f"/radio/data/ai/pending-{job.id}.mp3",
        metadata_json='{"status":"pending_tts","playable":false}',
        enabled=False,
        tags="ai,pending",
    )
    session.add(asset)
    session.flush()
    job.audio_asset_id = asset.id
    job.status = "tts_pending"
    job.updated_at = datetime.now(timezone.utc)
    session.commit()
    session.refresh(job)
    return job


def list_ai_jobs(session: Session, limit: int = 20) -> list[AIJob]:
    statement = select(AIJob).options(selectinload(AIJob.audio_asset)).order_by(AIJob.created_at.desc()).limit(limit)
    return list(session.scalars(statement))


def serialize_ai_job(job: AIJob) -> dict:
    return {
        "id": job.id,
        "job_type": job.job_type,
        "topic": job.topic,
        "script": job.script,
        "script_provider": job.script_provider,
        "tts_provider": job.tts_provider,
        "voice": job.voice,
        "status": job.status,
        "audio_asset_id": job.audio_asset_id,
        "created_at": job.created_at.isoformat(),
    }
